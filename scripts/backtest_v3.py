#!/usr/bin/env python3
"""
Backtesting v3 - Sistema Weinstein
Aplica los mismos filtros que signals.py (ruptura de resistencia, base sólida,
volumen y MRS) para evaluar únicamente señales de calidad.

Uso:
    python scripts/backtest_v3.py
    python scripts/backtest_v3.py --stop 8 --trailing 15
    python scripts/backtest_v3.py --csv resultados.csv
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import csv
from datetime import datetime, timedelta
from app.database import SessionLocal, Stock, WeeklyData, DailyData
from app.config import (
    BUY_RESISTANCE_WEEKS, BUY_MIN_BASE_WEEKS, BUY_MAX_BASE_SLOPE,
    BUY_MAX_DIST_ENTRY, MIN_WEEKS_FOR_ANALYSIS, VOLUME_SPIKE_THRESHOLD,
)
from sqlalchemy import and_


def get_daily_prices(db, stock_id, start_date, days=500):
    """Obtener precios diarios tras la entrada."""
    end_date = start_date + timedelta(days=days)
    return db.query(DailyData).filter(
        and_(
            DailyData.stock_id == stock_id,
            DailyData.date > start_date,
            DailyData.date <= end_date
        )
    ).order_by(DailyData.date.asc()).all()


def simulate_trade(db, stock_id, ticker, entry_date, entry_price,
                   initial_stop_pct, trailing_stop_pct):
    """
    Simula una operación completa con stop loss y trailing stop.
    Salida por: stop loss, etapa 3/4 o precio bajo MA30.
    """
    initial_stop = entry_price * (1 - initial_stop_pct / 100)
    highest = entry_price
    current_stop = initial_stop

    # Cargar datos semanales posteriores para detectar cambios de etapa
    weekly_after = db.query(WeeklyData).filter(
        and_(
            WeeklyData.stock_id == stock_id,
            WeeklyData.week_end_date > entry_date,
            WeeklyData.stage.isnot(None)
        )
    ).order_by(WeeklyData.week_end_date.asc()).all()

    # Índice rápido por fecha
    weekly_by_date = {w.week_end_date: w for w in weekly_after}
    weekly_dates = sorted(weekly_by_date.keys())

    daily_prices = get_daily_prices(db, stock_id, entry_date)

    exit_reason = None
    exit_date = None
    exit_price = None

    for day in daily_prices:
        price = float(day.close)
        low = float(day.low)
        date = day.date

        # Actualizar trailing stop cuando sube el precio
        if price > highest:
            highest = price
            new_trailing = highest * (1 - trailing_stop_pct / 100)
            if new_trailing > current_stop:
                current_stop = new_trailing

        # Regla 1: Stop loss alcanzado
        if low <= current_stop:
            exit_reason = 'STOP_LOSS'
            exit_date = date
            exit_price = current_stop
            break

        # Buscar la última semana cerrada hasta esta fecha
        last_week = None
        for wd in weekly_dates:
            if wd <= date:
                last_week = weekly_by_date[wd]
            else:
                break

        if last_week:
            # Regla 2: Cambio a etapa 3 o 4
            if last_week.stage in [3, 4]:
                exit_reason = f'STAGE_{last_week.stage}'
                exit_date = date
                exit_price = price
                break

            # Regla 3: Cierre semanal bajo MA30 (margen 3%)
            if last_week.ma30 and float(last_week.close) < float(last_week.ma30) * 0.97:
                exit_reason = 'BELOW_MA30'
                exit_date = date
                exit_price = price
                break

    # Sin salida activada: mantener hasta último precio disponible
    if not exit_date:
        if daily_prices:
            last = daily_prices[-1]
            exit_reason = 'HOLD'
            exit_date = last.date
            exit_price = float(last.close)
        else:
            return None

    ret_pct = (exit_price - entry_price) / entry_price * 100
    days_held = (exit_date - entry_date).days

    return {
        'ticker': ticker,
        'entry_date': entry_date,
        'entry_price': entry_price,
        'initial_stop': initial_stop,
        'exit_date': exit_date,
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'highest_price': highest,
        'final_stop': current_stop,
        'days_held': days_held,
        'return_pct': ret_pct,
        'winner': ret_pct > 0,
    }


def _compute_mrs(weekly, idx, spy_closes):
    """
    Mansfield Relative Strength en la semana idx.
    MRS = (rs_ratio / MA52_rs_ratio - 1) × 100
    Devuelve None si no hay suficientes datos.
    """
    if idx < 52 or not spy_closes:
        return None
    rs_window = []
    for j in range(idx - 51, idx + 1):
        spy_c = spy_closes.get(weekly[j].week_end_date)
        if spy_c and spy_c > 0:
            rs_window.append(float(weekly[j].close) / spy_c)
    if len(rs_window) < 52:
        return None
    ma52 = sum(rs_window) / len(rs_window)
    spy_curr = spy_closes.get(weekly[idx].week_end_date)
    if not spy_curr or spy_curr <= 0:
        return None
    return (float(weekly[idx].close) / spy_curr / ma52 - 1) * 100


def find_buy_transitions(db):
    """
    Encuentra señales BUY aplicando exactamente los mismos criterios que signals.py.
    Trabaja sobre la lista filtrada por MA30+slope (igual que _is_valid_buy_breakout):
      1. Ruptura de resistencia: precio > máx de últimas 30 semanas × 1.01
      2. MA30 slope > 0 en la semana de ruptura
      3. Precio no muy extendido sobre MA30 (≤ BUY_MAX_DIST_ENTRY)
      4. Base sólida: MA30 plana en ≥ 75% de las últimas 16 semanas
      5. Volumen de ruptura ≥ VOLUME_SPIKE_THRESHOLD × media de la base
      6. MRS > 0 (Mansfield Relative Strength positivo vs SPY)
    """
    MIN_IDX = BUY_RESISTANCE_WEEKS  # 30 — ventana de resistencia

    # Cargar cierres de SPY para MRS
    spy_stock = db.query(Stock).filter(Stock.ticker == 'SPY').first()
    spy_closes = {}
    if spy_stock:
        spy_rows = db.query(WeeklyData).filter(
            WeeklyData.stock_id == spy_stock.id
        ).order_by(WeeklyData.week_end_date.asc()).all()
        spy_closes = {w.week_end_date: float(w.close) for w in spy_rows}

    stocks = db.query(Stock).filter(Stock.active == True).all()
    transitions = []

    for stock in stocks:
        # Misma lista que usa signals.py: filtrada por MA30 y slope
        weekly = db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock.id,
                WeeklyData.ma30.isnot(None),
                WeeklyData.ma30_slope.isnot(None),
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()

        for i in range(MIN_IDX, len(weekly)):
            curr  = weekly[i]
            price = float(curr.close)
            ma30  = float(curr.ma30)
            slope = float(curr.ma30_slope)

            # MA30 debe estar en subida
            if slope <= 0:
                continue

            # Precio no muy extendido sobre MA30
            if (price - ma30) / ma30 > BUY_MAX_DIST_ENTRY:
                continue

            # Ruptura de resistencia: precio > máx de últimas 30 semanas × 1.01
            resistance_window = weekly[i - BUY_RESISTANCE_WEEKS:i]
            resistance = max(float(w.close) for w in resistance_window)
            if price <= resistance * 1.01:
                continue

            # Base sólida: MA30 plana en ≥ 75% de las últimas 16 semanas
            base = weekly[i - BUY_MIN_BASE_WEEKS:i]
            slopes_flat = sum(
                1 for w in base
                if abs(float(w.ma30_slope)) <= BUY_MAX_BASE_SLOPE
            )
            if slopes_flat < int(BUY_MIN_BASE_WEEKS * 0.75):
                continue

            # Volumen: semana de ruptura ≥ VOLUME_SPIKE_THRESHOLD × media de la base
            if curr.volume and curr.volume > 0:
                base_vols = [float(w.volume) for w in base if w.volume and w.volume > 0]
                if len(base_vols) >= 8:
                    if float(curr.volume) < sum(base_vols) / len(base_vols) * VOLUME_SPIKE_THRESHOLD:
                        continue

            # MRS > 0
            mrs = _compute_mrs(weekly, i, spy_closes)
            if mrs is not None and mrs <= 0:
                continue

            transitions.append({
                'stock_id': stock.id,
                'ticker': stock.ticker,
                'name': stock.name or '',
                'entry_date': curr.week_end_date,
                'entry_price': price,
                'ma30': ma30,
            })

    return transitions


def run_backtest(initial_stop_pct=8.0, trailing_stop_pct=15.0, csv_path=None):
    db = SessionLocal()

    print("=" * 65)
    print("BACKTEST SISTEMA WEINSTEIN v3")
    print(f"Fecha:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Stop inicial:   {initial_stop_pct}%")
    print(f"Trailing stop:  {trailing_stop_pct}%")
    print(f"Fuente:         weekly_data (filtros: resistencia+base+volumen+MRS)")
    print("=" * 65)

    # --- Fase 1: detectar transiciones BUY ---
    print("\nBuscando transiciones Etapa 1→2...")
    transitions = find_buy_transitions(db)
    print(f"Transiciones encontradas: {len(transitions)}")

    if not transitions:
        print("Sin transiciones. Saliendo.")
        db.close()
        return

    # --- Fase 2: simular operaciones ---
    print(f"\nSimulando {len(transitions)} operaciones...")
    results = []
    skipped = 0

    for idx, t in enumerate(transitions, 1):
        if idx % 200 == 0:
            print(f"  [{idx}/{len(transitions)}]...")

        r = simulate_trade(
            db, t['stock_id'], t['ticker'],
            t['entry_date'], t['entry_price'],
            initial_stop_pct, trailing_stop_pct
        )

        if r:
            r['name'] = t['name']
            r['ma30_entry'] = t['ma30']
            results.append(r)
        else:
            skipped += 1

    db.close()

    if skipped:
        print(f"  (Sin datos de precio para simular: {skipped} operaciones descartadas)")

    if not results:
        print("No se generaron resultados.")
        return

    # --- Fase 3: calcular estadísticas ---
    returns = [r['return_pct'] for r in results]
    winners = [r for r in results if r['winner']]
    losers  = [r for r in results if not r['winner']]

    win_rate       = len(winners) / len(results) * 100
    avg_return     = sum(returns) / len(returns)
    avg_winner     = sum(r['return_pct'] for r in winners) / len(winners) if winners else 0
    avg_loser      = sum(r['return_pct'] for r in losers)  / len(losers)  if losers  else 0
    profit_factor  = abs(avg_winner / avg_loser) if avg_loser != 0 else float('inf')
    avg_days       = sum(r['days_held'] for r in results) / len(results)
    median_return  = sorted(returns)[len(returns) // 2]

    exit_counts = {}
    for r in results:
        exit_counts[r['exit_reason']] = exit_counts.get(r['exit_reason'], 0) + 1

    # Estadísticas por año (de entrada)
    yearly = {}
    for r in results:
        year = r['entry_date'].year
        if year not in yearly:
            yearly[year] = {'ret': [], 'w': 0, 'l': 0}
        yearly[year]['ret'].append(r['return_pct'])
        if r['winner']:
            yearly[year]['w'] += 1
        else:
            yearly[year]['l'] += 1

    # --- Fase 4: imprimir informe ---
    print("\n" + "=" * 65)
    print("RESULTADOS GLOBALES")
    print("=" * 65)
    print(f"  Total operaciones:       {len(results)}")
    print(f"  Ganadoras:               {len(winners):4d}  ({win_rate:.1f}%)")
    print(f"  Perdedoras:              {len(losers):4d}  ({100 - win_rate:.1f}%)")
    print()
    print(f"  Retorno promedio:        {avg_return:+.2f}%")
    print(f"  Retorno mediano:         {median_return:+.2f}%")
    print(f"  Promedio ganadoras:      {avg_winner:+.2f}%")
    print(f"  Promedio perdedoras:     {avg_loser:+.2f}%")
    print(f"  Retorno máximo:          {max(returns):+.2f}%")
    print(f"  Retorno mínimo:          {min(returns):+.2f}%")
    print(f"  Ratio ganancia/pérdida:  {profit_factor:.2f}:1")
    print()
    print(f"  Duración media:          {avg_days:.0f} días")

    print()
    print("  Razones de salida:")
    for reason, count in sorted(exit_counts.items(), key=lambda x: x[1], reverse=True):
        pct = count / len(results) * 100
        print(f"    {reason:22s}: {count:4d}  ({pct:5.1f}%)")

    print("\n" + "=" * 65)
    print("RESULTADOS POR AÑO DE ENTRADA")
    print("=" * 65)
    print(f"  {'Año':>5}  {'Ops':>5}  {'Win%':>7}  {'Avg':>8}  {'Max':>8}  {'Min':>8}")
    print("  " + "-" * 55)
    for year in sorted(yearly.keys()):
        y = yearly[year]
        n  = len(y['ret'])
        wr = y['w'] / n * 100
        av = sum(y['ret']) / n
        mx = max(y['ret'])
        mn = min(y['ret'])
        print(f"  {year:>5}  {n:>5}  {wr:>7.1f}%  {av:>+8.2f}%  {mx:>+8.2f}%  {mn:>+8.2f}%")

    print("\n" + "=" * 65)
    print("TOP 15 MEJORES OPERACIONES")
    print("=" * 65)
    top = sorted(results, key=lambda x: x['return_pct'], reverse=True)[:15]
    for i, r in enumerate(top, 1):
        print(f"  {i:2d}. {r['ticker']:8s}  {r['entry_date']} → {r['exit_date']}  "
              f"{r['return_pct']:+7.2f}%  {r['days_held']:3d}d  {r['exit_reason']}")

    print("\n" + "=" * 65)
    print("TOP 15 PEORES OPERACIONES")
    print("=" * 65)
    worst = sorted(results, key=lambda x: x['return_pct'])[:15]
    for i, r in enumerate(worst, 1):
        print(f"  {i:2d}. {r['ticker']:8s}  {r['entry_date']} → {r['exit_date']}  "
              f"{r['return_pct']:+7.2f}%  {r['days_held']:3d}d  {r['exit_reason']}")

    print("\n" + "=" * 65)
    print("CONCLUSIONES")
    print("=" * 65)

    if win_rate > 60:
        print(f"  ✅ Win rate {win_rate:.1f}% — Sistema EFECTIVO")
    elif win_rate > 50:
        print(f"  ⚠️  Win rate {win_rate:.1f}% — Sistema MARGINAL")
    else:
        print(f"  ❌ Win rate {win_rate:.1f}% — Sistema INEFECTIVO")

    if avg_return > 5:
        print(f"  ✅ Retorno promedio {avg_return:+.2f}% — BUENO")
    elif avg_return > 0:
        print(f"  ⚠️  Retorno promedio {avg_return:+.2f}% — MODERADO")
    else:
        print(f"  ❌ Retorno promedio {avg_return:+.2f}% — NEGATIVO")

    if profit_factor > 2:
        print(f"  ✅ Ratio G/P {profit_factor:.2f}:1 — Ganadoras compensan ampliamente")
    elif profit_factor > 1.5:
        print(f"  ⚠️  Ratio G/P {profit_factor:.2f}:1 — Ganadoras compensan las perdedoras")
    else:
        print(f"  ❌ Ratio G/P {profit_factor:.2f}:1 — Ganadoras NO compensan bien")

    # --- Fase 5: exportar CSV ---
    if csv_path:
        fields = [
            'ticker', 'name', 'entry_date', 'entry_price', 'ma30_entry',
            'exit_date', 'exit_price', 'return_pct', 'days_held',
            'exit_reason', 'winner', 'highest_price', 'initial_stop', 'final_stop'
        ]
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)
        print(f"\n  📄 Resultados detallados exportados a: {csv_path}")

    print("\n" + "=" * 65)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backtest v3 - Sistema Weinstein')
    parser.add_argument('--stop',     type=float, default=8.0,  help='Stop loss inicial en %% (default: 8)')
    parser.add_argument('--trailing', type=float, default=15.0, help='Trailing stop en %% desde maximo (default: 15)')
    parser.add_argument('--csv',      type=str,   default=None, help='Exportar resultados a CSV')
    args = parser.parse_args()

    run_backtest(args.stop, args.trailing, args.csv)
