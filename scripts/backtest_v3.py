#!/usr/bin/env python3
"""
Backtesting v3 - Sistema Weinstein
Lee transiciones de etapa 1→2 directamente de weekly_data (histórico completo)
Simula operaciones con stop loss y genera informe completo

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
from app.config import MAX_PRICE_DISTANCE_FOR_BUY
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


def find_buy_transitions(db):
    """
    Buscar todas las transiciones Etapa 1→2 en weekly_data.
    Aplica el filtro MAX_PRICE_DISTANCE_FOR_BUY igual que el generador de señales.
    """
    stocks = db.query(Stock).filter(Stock.active == True).all()
    transitions = []

    for stock in stocks:
        weekly = db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock.id,
                WeeklyData.stage.isnot(None),
                WeeklyData.ma30.isnot(None)
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()

        for i in range(1, len(weekly)):
            prev = weekly[i - 1]
            curr = weekly[i]

            if prev.stage == 1 and curr.stage == 2:
                price = float(curr.close)
                ma30 = float(curr.ma30)

                # Descartar rupturas demasiado alejadas de MA30
                if ma30 > 0 and (price - ma30) / ma30 > MAX_PRICE_DISTANCE_FOR_BUY:
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
    print(f"Fuente:         weekly_data (historico completo)")
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
