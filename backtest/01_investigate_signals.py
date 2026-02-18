"""
Investigación de señales BUY - Caso AMD y auditoría general
Analiza los datos semanales alrededor de cada señal BUY para detectar falsos positivos.
"""
import sys
sys.path.insert(0, '/home/gcb/Nextcloud/Desarrollo/stanweinstein_test')

from datetime import timedelta
from sqlalchemy import and_, text
from app.database import SessionLocal, Stock, WeeklyData, Signal

# Conectar a BD remota (dev)
from app import config
config.DB_CONFIG['host'] = '192.168.100.11'

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
DB_URL = f"mysql+pymysql://{config.DB_CONFIG['user']}:{config.DB_CONFIG['password']}@{config.DB_CONFIG['host']}/{config.DB_CONFIG['database']}?charset={config.DB_CONFIG['charset']}"
engine = create_engine(DB_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
db = Session()


def get_weekly_context(stock_id, signal_date, weeks_before=8, weeks_after=4):
    """Obtener datos semanales alrededor de una fecha de señal"""
    start_date = signal_date - timedelta(weeks=weeks_before)
    end_date = signal_date + timedelta(weeks=weeks_after)

    weeks = db.query(WeeklyData).filter(
        and_(
            WeeklyData.stock_id == stock_id,
            WeeklyData.week_end_date >= start_date,
            WeeklyData.week_end_date <= end_date
        )
    ).order_by(WeeklyData.week_end_date.asc()).all()

    return weeks


def analyze_signal_quality(stock_id, signal_date, signal_price):
    """
    Analizar calidad de una señal BUY.
    Retorna métricas de calidad y rendimiento post-señal.
    """
    weeks = get_weekly_context(stock_id, signal_date, weeks_before=8, weeks_after=12)

    if not weeks:
        return None

    # Encontrar la semana de la señal
    signal_week_idx = None
    for i, w in enumerate(weeks):
        if w.week_end_date == signal_date:
            signal_week_idx = i
            break

    if signal_week_idx is None:
        return None

    signal_week = weeks[signal_week_idx]

    # Métricas pre-señal
    pre_weeks = weeks[:signal_week_idx]
    post_weeks = weeks[signal_week_idx + 1:]

    # Calcular rendimiento post-señal (4, 8, 12 semanas)
    returns = {}
    for target_weeks in [4, 8, 12]:
        if len(post_weeks) >= target_weeks:
            future_close = float(post_weeks[target_weeks - 1].close)
            ret = (future_close - signal_price) / signal_price * 100
            returns[f'{target_weeks}w'] = ret
        else:
            returns[f'{target_weeks}w'] = None

    # Calcular drawdown máximo post-señal (12 semanas)
    max_drawdown = 0.0
    for pw in post_weeks[:12]:
        dd = (float(pw.low) - signal_price) / signal_price * 100
        if dd < max_drawdown:
            max_drawdown = dd

    # Verificar si la señal fue "verdadera" - el precio subió >5% en las 12 semanas siguientes
    max_gain = 0.0
    for pw in post_weeks[:12]:
        gain = (float(pw.high) - signal_price) / signal_price * 100
        if gain > max_gain:
            max_gain = gain

    # Métricas de la señal
    slope = float(signal_week.ma30_slope) if signal_week.ma30_slope else 0
    ma30 = float(signal_week.ma30) if signal_week.ma30 else 0
    price_vs_ma30 = (signal_price - ma30) / ma30 * 100 if ma30 else 0

    # Volumen relativo (semana señal vs promedio 8 semanas previas)
    if pre_weeks:
        avg_vol = sum(w.volume for w in pre_weeks if w.volume) / max(len(pre_weeks), 1)
        vol_ratio = signal_week.volume / avg_vol if avg_vol > 0 else 1.0
    else:
        vol_ratio = 1.0

    # Slope promedio de las 4 semanas previas
    pre_slopes = [float(w.ma30_slope) for w in pre_weeks[-4:] if w.ma30_slope is not None]
    avg_pre_slope = sum(pre_slopes) / len(pre_slopes) if pre_slopes else 0

    # Clasificación de calidad
    is_false_positive = max_gain < 5.0  # No llegó a subir >5% en 12 semanas

    return {
        'slope': slope,
        'ma30': ma30,
        'price_vs_ma30_pct': price_vs_ma30,
        'volume_ratio': vol_ratio,
        'avg_pre_slope': avg_pre_slope,
        'returns': returns,
        'max_drawdown': max_drawdown,
        'max_gain_12w': max_gain,
        'is_false_positive': is_false_positive,
        'stage_history': [(w.week_end_date, w.stage, float(w.close),
                          float(w.ma30) if w.ma30 else None,
                          float(w.ma30_slope) if w.ma30_slope else None)
                         for w in weeks]
    }


def main():
    print("=" * 100)
    print("INVESTIGACIÓN DE SEÑALES BUY - Sistema Weinstein")
    print("=" * 100)

    # =========================================
    # PARTE 1: CASO AMD
    # =========================================
    print("\n" + "=" * 100)
    print("PARTE 1: CASO AMD - Señal BUY del 23/01/2026")
    print("=" * 100)

    amd = db.query(Stock).filter(Stock.ticker == 'AMD').first()
    if not amd:
        print("ERROR: AMD no encontrado en la BD")
        return

    amd_signal = db.query(Signal).filter(
        and_(
            Signal.stock_id == amd.id,
            Signal.signal_type == 'BUY'
        )
    ).order_by(Signal.signal_date.desc()).all()

    print(f"\nTodas las señales BUY de AMD:")
    for s in amd_signal:
        ma30_str = f"${float(s.ma30):.2f}" if s.ma30 else "N/A"
        print(f"  {s.signal_date} | Precio: ${float(s.price):.2f} | MA30: {ma30_str} | "
              f"Etapa {s.stage_from} → {s.stage_to}")

    # Señal específica del 23 de enero (o la más cercana)
    target_signal = None
    for s in amd_signal:
        if s.signal_date.year == 2026 and s.signal_date.month == 1:
            target_signal = s
            break

    if not target_signal:
        print("\nNo se encontró señal BUY de AMD en enero 2026.")
        print("Buscando señales BUY más recientes de AMD...")
        if amd_signal:
            target_signal = amd_signal[0]
            print(f"  Última señal: {target_signal.signal_date}")

    if target_signal:
        print(f"\n--- Datos semanales de AMD alrededor de la señal ({target_signal.signal_date}) ---")
        weeks = get_weekly_context(amd.id, target_signal.signal_date, weeks_before=10, weeks_after=6)

        print(f"\n{'Semana':<14} {'Etapa':>5} {'Close':>10} {'MA30':>10} {'Slope%':>10} {'Precio/MA30%':>14} {'Volumen':>14}")
        print("-" * 85)
        for w in weeks:
            close = float(w.close)
            ma30 = float(w.ma30) if w.ma30 else None
            slope = float(w.ma30_slope) if w.ma30_slope else None
            pct = ((close - ma30) / ma30 * 100) if ma30 else None

            marker = " <<<" if w.week_end_date == target_signal.signal_date else ""
            ma30_s = f"{ma30:>10.2f}" if ma30 else "       N/A"
            slope_s = f"{slope*100:>10.4f}" if slope else "       N/A"
            pct_s = f"{pct:>14.2f}" if pct else "           N/A"
            print(f"{w.week_end_date}  {w.stage or '-':>5} {close:>10.2f} "
                  f"{ma30_s} {slope_s} {pct_s} {w.volume:>14,}{marker}")

        quality = analyze_signal_quality(amd.id, target_signal.signal_date, float(target_signal.price))
        if quality:
            print(f"\n--- Análisis de calidad de la señal AMD ---")
            print(f"  Slope en señal: {quality['slope']*100:.4f}%")
            print(f"  Precio vs MA30: {quality['price_vs_ma30_pct']:.2f}%")
            print(f"  Ratio volumen: {quality['volume_ratio']:.2f}x")
            print(f"  Slope promedio 4 sem. previas: {quality['avg_pre_slope']*100:.4f}%")
            print(f"  Rendimiento 4 sem: {quality['returns']['4w']:.2f}%" if quality['returns']['4w'] is not None else "  Rendimiento 4 sem: N/A")
            print(f"  Rendimiento 8 sem: {quality['returns']['8w']:.2f}%" if quality['returns']['8w'] is not None else "  Rendimiento 8 sem: N/A")
            print(f"  Rendimiento 12 sem: {quality['returns']['12w']:.2f}%" if quality['returns']['12w'] is not None else "  Rendimiento 12 sem: N/A")
            print(f"  Max ganancia 12 sem: {quality['max_gain_12w']:.2f}%")
            print(f"  Max drawdown: {quality['max_drawdown']:.2f}%")
            print(f"  ¿Falso positivo? {'SÍ' if quality['is_false_positive'] else 'NO'}")

    # =========================================
    # PARTE 2: AUDITORÍA DE TODAS LAS SEÑALES BUY
    # =========================================
    print("\n\n" + "=" * 100)
    print("PARTE 2: AUDITORÍA DE TODAS LAS SEÑALES BUY")
    print("=" * 100)

    all_buy_signals = db.query(Signal, Stock).join(
        Stock, Signal.stock_id == Stock.id
    ).filter(
        Signal.signal_type == 'BUY'
    ).order_by(Signal.signal_date.asc()).all()

    print(f"\nTotal señales BUY encontradas: {len(all_buy_signals)}")

    results = []
    false_positives = []
    true_positives = []
    no_data = []

    for signal, stock in all_buy_signals:
        quality = analyze_signal_quality(stock.id, signal.signal_date, float(signal.price))

        if quality is None:
            no_data.append((stock.ticker, signal.signal_date))
            continue

        result = {
            'ticker': stock.ticker,
            'date': signal.signal_date,
            'price': float(signal.price),
            **quality
        }
        results.append(result)

        if quality['is_false_positive']:
            false_positives.append(result)
        else:
            true_positives.append(result)

    print(f"\nResultados:")
    print(f"  Verdaderos positivos: {len(true_positives)}")
    print(f"  Falsos positivos: {len(false_positives)}")
    print(f"  Sin datos suficientes: {len(no_data)}")
    if results:
        fp_rate = len(false_positives) / len(results) * 100
        print(f"  Tasa de falsos positivos: {fp_rate:.1f}%")

    # Tabla detallada de señales
    print(f"\n{'Ticker':<8} {'Fecha':<12} {'Precio':>8} {'Slope%':>8} {'P/MA30%':>8} {'VolRat':>7} "
          f"{'4w%':>7} {'8w%':>7} {'12w%':>7} {'MaxDD%':>7} {'MaxG%':>7} {'FP?':>4}")
    print("-" * 110)

    for r in sorted(results, key=lambda x: x['date']):
        ret_4w = f"{r['returns']['4w']:.1f}" if r['returns']['4w'] is not None else "N/A"
        ret_8w = f"{r['returns']['8w']:.1f}" if r['returns']['8w'] is not None else "N/A"
        ret_12w = f"{r['returns']['12w']:.1f}" if r['returns']['12w'] is not None else "N/A"
        fp = "SÍ" if r['is_false_positive'] else ""

        print(f"{r['ticker']:<8} {str(r['date']):<12} {r['price']:>8.2f} {r['slope']*100:>8.4f} "
              f"{r['price_vs_ma30_pct']:>8.2f} {r['volume_ratio']:>7.2f} "
              f"{ret_4w:>7} {ret_8w:>7} {ret_12w:>7} "
              f"{r['max_drawdown']:>7.1f} {r['max_gain_12w']:>7.1f} {fp:>4}")

    # =========================================
    # PARTE 3: PATRONES DE FALSOS POSITIVOS
    # =========================================
    print("\n\n" + "=" * 100)
    print("PARTE 3: ANÁLISIS DE PATRONES EN FALSOS POSITIVOS")
    print("=" * 100)

    if false_positives:
        avg_slope_fp = sum(r['slope'] for r in false_positives) / len(false_positives)
        avg_slope_tp = sum(r['slope'] for r in true_positives) / len(true_positives) if true_positives else 0

        avg_vol_fp = sum(r['volume_ratio'] for r in false_positives) / len(false_positives)
        avg_vol_tp = sum(r['volume_ratio'] for r in true_positives) / len(true_positives) if true_positives else 0

        avg_pma_fp = sum(r['price_vs_ma30_pct'] for r in false_positives) / len(false_positives)
        avg_pma_tp = sum(r['price_vs_ma30_pct'] for r in true_positives) / len(true_positives) if true_positives else 0

        avg_preslope_fp = sum(r['avg_pre_slope'] for r in false_positives) / len(false_positives)
        avg_preslope_tp = sum(r['avg_pre_slope'] for r in true_positives) / len(true_positives) if true_positives else 0

        print(f"\n{'Métrica':<30} {'Falsos Positivos':>20} {'Verdaderos Positivos':>20}")
        print("-" * 72)
        print(f"{'Slope promedio (%):':<30} {avg_slope_fp*100:>20.4f} {avg_slope_tp*100:>20.4f}")
        print(f"{'Ratio volumen promedio:':<30} {avg_vol_fp:>20.2f} {avg_vol_tp:>20.2f}")
        print(f"{'Precio vs MA30 (%) promedio:':<30} {avg_pma_fp:>20.2f} {avg_pma_tp:>20.2f}")
        print(f"{'Slope pre-señal (%) promedio:':<30} {avg_preslope_fp*100:>20.4f} {avg_preslope_tp*100:>20.4f}")

        print(f"\nDetalle de falsos positivos:")
        for r in false_positives:
            print(f"  {r['ticker']} ({r['date']}): slope={r['slope']*100:.4f}%, "
                  f"vol_ratio={r['volume_ratio']:.2f}, "
                  f"price/MA30={r['price_vs_ma30_pct']:.2f}%, "
                  f"max_gain={r['max_gain_12w']:.1f}%, "
                  f"max_dd={r['max_drawdown']:.1f}%")

    # =========================================
    # PARTE 4: PROBLEMAS IDENTIFICADOS EN EL ALGORITMO
    # =========================================
    print("\n\n" + "=" * 100)
    print("PARTE 4: PROBLEMAS IDENTIFICADOS EN EL ALGORITMO ACTUAL")
    print("=" * 100)

    print("""
    1. SLOPE MA30 CALCULADO SEMANA A SEMANA (no multi-período):
       - slope = (MA30_actual - MA30_anterior) / MA30_anterior
       - Esto mide el cambio % de MA30 en UNA sola semana
       - Un MA30 (30 semanas) cambia muy poco de semana a semana
       - Un umbral de 2% es DEMASIADO ALTO para un cambio semanal de MA30
       - Resultado: slope casi siempre es "plano" (< 2%)

    2. SIN CONFIRMACIÓN POR VOLUMEN:
       - VOLUME_SPIKE_THRESHOLD (1.5x) está definido pero NO SE USA en el analyzer
       - Weinstein requiere volumen alto en rupturas de Etapa 1 → 2

    3. TRANSICIONES DE ETAPA RÍGIDAS:
       - Etapa 1 solo puede venir de Etapa 4 o None
       - Si una acción oscila entre etapa 1 y 2, puede generar señales BUY repetidas

    4. SIN CONFIRMACIÓN TEMPORAL:
       - Un solo dato de slope > threshold cambia la etapa inmediatamente
       - Debería requerir N semanas consecutivas de condición

    5. UMBRAL FIJO PARA TODAS LAS ACCIONES:
       - 5% de distancia precio/MA30 puede ser mucho o poco según volatilidad
    """)

    db.close()
    print("\n[Investigación completada]")


if __name__ == '__main__':
    main()
