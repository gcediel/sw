"""
Backtest que simula el comportamiento REAL de producción.
En producción, weekly_process re-analiza solo las últimas 10 semanas,
lo cual puede cambiar las etapas asignadas previamente y generar señales espurias.

También incluye V4: versión mejorada equilibrada.
"""
import sys
sys.path.insert(0, '/home/gcb/Nextcloud/Desarrollo/stanweinstein_test')

from datetime import timedelta, date
from collections import defaultdict
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Stock, WeeklyData
from app import config

config.DB_CONFIG['host'] = '192.168.100.11'
DB_URL = (f"mysql+pymysql://{config.DB_CONFIG['user']}:{config.DB_CONFIG['password']}"
          f"@{config.DB_CONFIG['host']}/{config.DB_CONFIG['database']}"
          f"?charset={config.DB_CONFIG['charset']}")
engine = create_engine(DB_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
db = Session()


def load_all_weekly_data():
    """Cargar datos semanales"""
    stocks = db.query(Stock).filter(Stock.active == True).all()
    data = {}
    for stock in stocks:
        weeks = db.query(WeeklyData).filter(
            WeeklyData.stock_id == stock.id
        ).order_by(WeeklyData.week_end_date.asc()).all()
        if len(weeks) < 35:
            continue
        data[stock.ticker] = [{
            'date': w.week_end_date,
            'close': float(w.close) if w.close else None,
            'high': float(w.high) if w.high else None,
            'low': float(w.low) if w.low else None,
            'volume': w.volume,
            'ma30': float(w.ma30) if w.ma30 else None,
            'ma30_slope': float(w.ma30_slope) if w.ma30_slope else None,
        } for w in weeks]
    return data


def recalculate_slopes(weeks_data):
    """Recalcular MA30 y slopes"""
    for i, w in enumerate(weeks_data):
        if i >= 29:
            closes = [weeks_data[j]['close'] for j in range(i - 29, i + 1)]
            w['ma30_calc'] = sum(closes) / 30
        else:
            w['ma30_calc'] = None

        if i >= 30 and weeks_data[i-1].get('ma30_calc') and w.get('ma30_calc'):
            prev = weeks_data[i-1]['ma30_calc']
            w['slope_1w'] = (w['ma30_calc'] - prev) / prev if prev else None
        else:
            w['slope_1w'] = None

        if i >= 33 and weeks_data[i-4].get('ma30_calc') and w.get('ma30_calc'):
            prev4 = weeks_data[i-4]['ma30_calc']
            w['slope_4w'] = (w['ma30_calc'] - prev4) / prev4 if prev4 else None
        else:
            w['slope_4w'] = None
    return weeks_data


# ============================================================================
# Detector baseline (replica producción)
# ============================================================================

class BaselineDetector:
    def __init__(self):
        self.name = "BASELINE"
        self.slope_threshold = 0.02
        self.price_threshold = 0.05

    def detect_stage(self, week, previous_stage):
        close = week['close']
        ma30 = week.get('ma30')
        slope = week.get('ma30_slope')
        if not ma30 or ma30 == 0:
            return previous_stage or 1
        pd = (close - ma30) / ma30
        above = pd > self.price_threshold
        below = pd < -self.price_threshold
        near = not above and not below
        if slope is None:
            s_flat, s_up, s_down = True, False, False
        else:
            s_flat = abs(slope) <= self.slope_threshold
            s_up = slope > self.slope_threshold
            s_down = slope < -self.slope_threshold

        if above and s_up: return 2
        if below and s_down: return 4
        if (near or above) and s_flat and previous_stage == 2: return 3
        if (near or below) and (s_flat or s_down) and previous_stage in [4, None]: return 1
        return previous_stage or 1


# ============================================================================
# V4: Versión mejorada equilibrada
# ============================================================================

class ImprovedDetectorV4:
    """
    V4: Mejoras equilibradas al baseline:
    1. Slope de 4 semanas en vez de 1 (más estable)
    2. Umbral de slope adaptado: 0.03 (3% en 4 semanas ≈ 0.75%/semana)
    3. Precio no puede estar >20% sobre MA30 para considerarse etapa 1
    4. Volumen >1.0x promedio para confirmar BUY (mínimo: no caída de volumen)
    5. Etapa 3 puede venir de etapa 2 O 3 (no solo de 2)
    6. Etapa 1 puede venir de etapa 4 O 1 (no solo de 4)
    """

    def __init__(self):
        self.name = "V4: Equilibrada (slope 4w, vol, límite 20%)"
        self.slope_threshold = 0.03   # 3% en 4 semanas
        self.price_threshold = 0.03   # 3% distancia precio/MA30
        self.max_price_for_buy = 0.20  # 20% máx sobre MA30 para BUY

    def detect_stage(self, week, previous_stage):
        close = week['close']
        ma30 = week.get('ma30_calc') or week.get('ma30')
        slope = week.get('slope_4w')  # Slope 4 semanas

        if not ma30 or ma30 == 0:
            return previous_stage or 1

        pd_val = (close - ma30) / ma30
        above = pd_val > self.price_threshold
        below = pd_val < -self.price_threshold
        near = not above and not below

        if slope is None:
            s_flat, s_up, s_down = True, False, False
        else:
            s_flat = abs(slope) <= self.slope_threshold
            s_up = slope > self.slope_threshold
            s_down = slope < -self.slope_threshold

        if above and s_up: return 2
        if below and s_down: return 4
        if (near or above) and s_flat and previous_stage in [2, 3]: return 3
        if (near or below) and (s_flat or s_down) and previous_stage in [4, 1, None]: return 1
        return previous_stage or 1

    def validate_buy(self, week, weeks_history):
        """Validaciones extra para BUY"""
        close = week['close']
        ma30 = week.get('ma30_calc') or week.get('ma30')

        # Límite de distancia precio/MA30
        if ma30 and ma30 > 0:
            if (close - ma30) / ma30 > self.max_price_for_buy:
                return False

        # Verificar que volumen no sea anormalmente bajo
        if weeks_history and len(weeks_history) >= 4:
            vols = [w.get('volume', 0) or 0 for w in weeks_history[-4:]]
            avg_vol = sum(vols) / len(vols) if vols else 0
            curr_vol = week.get('volume', 0) or 0
            if avg_vol > 0 and curr_vol / avg_vol < 0.8:
                return False  # Volumen < 80% del promedio → no confirma

        return True


# ============================================================================
# V5: Como V4 pero con slope 1w y umbral original ajustado
# ============================================================================

class ImprovedDetectorV5:
    """
    V5: Mantiene slope 1w (como baseline) pero:
    1. Reduce umbral slope a 0.015 (1.5%)
    2. Limita precio/MA30 a 20% para BUY
    3. Añade verificación de volumen
    4. Permite transiciones más flexibles entre etapas
    """

    def __init__(self):
        self.name = "V5: Slope 1w ajustado + filtros BUY"
        self.slope_threshold = 0.015   # 1.5% slope semanal
        self.price_threshold = 0.05    # 5% como original
        self.max_price_for_buy = 0.20

    def detect_stage(self, week, previous_stage):
        close = week['close']
        ma30 = week.get('ma30')
        slope = week.get('ma30_slope')  # Slope original 1 semana
        if not ma30 or ma30 == 0:
            return previous_stage or 1
        pd_val = (close - ma30) / ma30
        above = pd_val > self.price_threshold
        below = pd_val < -self.price_threshold
        near = not above and not below

        if slope is None:
            s_flat, s_up, s_down = True, False, False
        else:
            s_flat = abs(slope) <= self.slope_threshold
            s_up = slope > self.slope_threshold
            s_down = slope < -self.slope_threshold

        if above and s_up: return 2
        if below and s_down: return 4
        if (near or above) and s_flat and previous_stage in [2, 3]: return 3
        if (near or below) and (s_flat or s_down) and previous_stage in [4, 1, None]: return 1
        return previous_stage or 1

    def validate_buy(self, week, weeks_history):
        close = week['close']
        ma30 = week.get('ma30')
        if ma30 and ma30 > 0:
            if (close - ma30) / ma30 > self.max_price_for_buy:
                return False
        if weeks_history and len(weeks_history) >= 4:
            vols = [w.get('volume', 0) or 0 for w in weeks_history[-4:]]
            avg_vol = sum(vols) / len(vols) if vols else 0
            curr_vol = week.get('volume', 0) or 0
            if avg_vol > 0 and curr_vol / avg_vol < 0.8:
                return False
        return True


# ============================================================================
# Simulación de producción (re-análisis rolling de 10 semanas)
# ============================================================================

def simulate_production(ticker_data, detector, start_date, end_date, reanalysis_window=10):
    """
    Simula el comportamiento de producción donde cada sábado
    se re-analizan las últimas 10 semanas.
    """
    weeks = ticker_data
    n = len(weeks)

    # Stages almacenados (como en la BD)
    stored_stages = [None] * n

    # Primera ejecución: analizar todo el histórico
    prev = None
    for i in range(n):
        if weeks[i].get('ma30') is None:
            stored_stages[i] = prev or 1
        else:
            stored_stages[i] = detector.detect_stage(weeks[i], prev)
        prev = stored_stages[i]

    # Simular re-análisis semanal
    signals = []
    # Para cada semana en el período de test, simular un re-análisis
    for current_idx in range(reanalysis_window + 1, n):
        if weeks[current_idx]['date'] < start_date or weeks[current_idx]['date'] > end_date:
            continue

        # Re-analizar últimas `reanalysis_window` semanas
        window_start = current_idx - reanalysis_window
        context_idx = window_start - 1
        prev_stage = stored_stages[context_idx] if context_idx >= 0 else None

        old_stages = stored_stages[window_start:current_idx + 1].copy()

        for j in range(window_start, current_idx + 1):
            if weeks[j].get('ma30') is None:
                stored_stages[j] = prev_stage or 1
            else:
                stored_stages[j] = detector.detect_stage(weeks[j], prev_stage)
            prev_stage = stored_stages[j]

        # Detectar cambios de etapa en la última semana del window
        new_stages = stored_stages[window_start:current_idx + 1]

        # Buscar transiciones 1→2 que se crearon en este re-análisis
        for j in range(1, len(new_stages)):
            global_j = window_start + j
            if old_stages[j - 1] is not None and new_stages[j] is not None:
                # Checar si hay una transición nueva
                pass

        # Checar la semana actual vs la anterior
        curr_stage = stored_stages[current_idx]
        prev_week_stage = stored_stages[current_idx - 1] if current_idx > 0 else None

        # Si hay transición 1→2
        if prev_week_stage == 1 and curr_stage == 2:
            w = weeks[current_idx]

            # Validar BUY si el detector tiene validate_buy
            if hasattr(detector, 'validate_buy'):
                history = weeks[max(0, current_idx - 8):current_idx]
                if not detector.validate_buy(w, history):
                    continue

            # Calcular rendimientos
            future = weeks[current_idx + 1:]
            returns = {}
            for t in [4, 8, 12]:
                if len(future) >= t:
                    returns[f'{t}w'] = (future[t-1]['close'] - w['close']) / w['close'] * 100
                else:
                    returns[f'{t}w'] = None

            max_gain, max_dd = 0.0, 0.0
            for fw in future[:12]:
                if fw['high']:
                    max_gain = max(max_gain, (fw['high'] - w['close']) / w['close'] * 100)
                if fw['low']:
                    max_dd = min(max_dd, (fw['low'] - w['close']) / w['close'] * 100)

            ma30 = w.get('ma30_calc') or w.get('ma30')
            pma = ((w['close'] - ma30) / ma30 * 100) if ma30 else None

            signals.append({
                'date': w['date'],
                'price': w['close'],
                'price_vs_ma30': pma,
                'returns': returns,
                'max_gain_12w': max_gain,
                'max_drawdown_12w': max_dd,
                'is_false_positive': max_gain < 5.0,
            })

    return signals


def run_full_production_sim(all_data, detector, start_date, end_date):
    """Ejecutar simulación para todas las acciones"""
    all_signals = []

    for ticker, weeks in all_data.items():
        weeks = recalculate_slopes(weeks)
        signals = simulate_production(weeks, detector, start_date, end_date)
        for s in signals:
            s['ticker'] = ticker
            all_signals.append(s)

    return sorted(all_signals, key=lambda x: x['date'])


def print_summary(name, signals):
    """Imprimir resumen de resultados"""
    print(f"\n{'=' * 90}")
    print(f"  {name}")
    print(f"{'=' * 90}")

    total = len(signals)
    fp = sum(1 for s in signals if s.get('is_false_positive'))
    rets_12w = [s['returns']['12w'] for s in signals if s['returns'].get('12w') is not None]
    rets_4w = [s['returns']['4w'] for s in signals if s['returns'].get('4w') is not None]
    wins = sum(1 for r in rets_12w if r > 0)

    print(f"  Señales BUY: {total}")
    print(f"  Falsos positivos: {fp} ({fp/total*100:.1f}%)" if total else "  Sin señales")
    print(f"  Win rate 12w: {wins/len(rets_12w)*100:.1f}%" if rets_12w else "  Win rate: N/A")
    print(f"  Retorno medio 4w: {sum(rets_4w)/len(rets_4w):+.2f}%" if rets_4w else "  Ret 4w: N/A")
    print(f"  Retorno medio 12w: {sum(rets_12w)/len(rets_12w):+.2f}%" if rets_12w else "  Ret 12w: N/A")

    gains = [s['max_gain_12w'] for s in signals]
    dds = [s['max_drawdown_12w'] for s in signals]
    if gains:
        print(f"  Max gain medio 12w: {sum(gains)/len(gains):.2f}%")
    if dds:
        print(f"  Max drawdown medio 12w: {sum(dds)/len(dds):.2f}%")

    # Detalle
    if signals:
        print(f"\n  {'Ticker':<8} {'Fecha':<12} {'Precio':>8} {'P/MA30%':>8} "
              f"{'4w%':>7} {'8w%':>7} {'12w%':>7} {'MaxG%':>7} {'MaxDD%':>7} {'FP?':>4}")
        print(f"  {'-' * 80}")
        for s in signals:
            r4 = f"{s['returns']['4w']:.1f}" if s['returns'].get('4w') is not None else "N/A"
            r8 = f"{s['returns']['8w']:.1f}" if s['returns'].get('8w') is not None else "N/A"
            r12 = f"{s['returns']['12w']:.1f}" if s['returns'].get('12w') is not None else "N/A"
            pma = f"{s['price_vs_ma30']:.1f}" if s.get('price_vs_ma30') is not None else "N/A"
            fp_str = "SÍ" if s.get('is_false_positive') else ""
            print(f"  {s['ticker']:<8} {str(s['date']):<12} {s['price']:>8.2f} {pma:>8} "
                  f"{r4:>7} {r8:>7} {r12:>7} "
                  f"{s['max_gain_12w']:>7.1f} {s['max_drawdown_12w']:>7.1f} {fp_str:>4}")

    # Verificar AMD
    amd_signals = [s for s in signals if s['ticker'] == 'AMD']
    print(f"\n  Señales AMD: {[str(s['date']) for s in amd_signals] if amd_signals else 'Ninguna'}")

    return {
        'total': total,
        'fp': fp,
        'fp_rate': fp / total * 100 if total else 0,
        'avg_ret_4w': sum(rets_4w) / len(rets_4w) if rets_4w else None,
        'avg_ret_12w': sum(rets_12w) / len(rets_12w) if rets_12w else None,
        'win_rate': wins / len(rets_12w) * 100 if rets_12w else 0,
        'avg_gain': sum(gains) / len(gains) if gains else 0,
        'avg_dd': sum(dds) / len(dds) if dds else 0,
    }


def main():
    print("=" * 90)
    print("  BACKTEST CON SIMULACIÓN DE PRODUCCIÓN (re-análisis 10 semanas)")
    print("  Período: 2024-06-01 a 2026-02-14")
    print("=" * 90)

    print("\nCargando datos...")
    all_data = load_all_weekly_data()
    print(f"  Acciones: {len(all_data)}")

    start = date(2024, 6, 1)
    end = date(2026, 2, 14)

    detectors = [
        ("BASELINE (simula producción)", BaselineDetector()),
        ("V4: Equilibrada", ImprovedDetectorV4()),
        ("V5: Slope 1w ajustado + filtros", ImprovedDetectorV5()),
    ]

    results = []
    for name, det in detectors:
        print(f"\nEjecutando: {name}...")
        signals = run_full_production_sim(all_data, det, start, end)
        metrics = print_summary(name, signals)
        results.append((name, metrics))

    # Tabla comparativa final
    print(f"\n\n{'=' * 90}")
    print(f"  TABLA COMPARATIVA - Simulación Producción")
    print(f"{'=' * 90}")

    print(f"\n  {'Métrica':<30}", end="")
    for name, _ in results:
        print(f" {name[:20]:>20}", end="")
    print()
    print(f"  {'-' * (30 + 21 * len(results))}")

    rows = [
        ('Señales BUY', 'total', '{:d}'),
        ('Falsos positivos', 'fp', '{:d}'),
        ('Tasa FP (%)', 'fp_rate', '{:.1f}'),
        ('Win rate 12w (%)', 'win_rate', '{:.1f}'),
        ('Retorno medio 4w (%)', 'avg_ret_4w', '{:+.2f}'),
        ('Retorno medio 12w (%)', 'avg_ret_12w', '{:+.2f}'),
        ('Max gain medio (%)', 'avg_gain', '{:.2f}'),
        ('Max drawdown medio (%)', 'avg_dd', '{:.2f}'),
    ]

    for label, key, fmt in rows:
        print(f"  {label:<30}", end="")
        for _, m in results:
            val = m.get(key)
            if val is not None:
                print(f" {fmt.format(val):>20}", end="")
            else:
                print(f" {'N/A':>20}", end="")
        print()

    db.close()
    print("\n[Simulación completada]")


if __name__ == '__main__':
    main()
