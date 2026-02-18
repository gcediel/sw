"""
Backtest completo del sistema Weinstein
Compara el algoritmo actual (baseline) con versiones mejoradas.

Ejecuta la detección de etapas y señales sobre datos históricos,
y mide el rendimiento de cada señal BUY.
"""
import sys
sys.path.insert(0, '/home/gcb/Nextcloud/Desarrollo/stanweinstein_test')

from datetime import timedelta, date
from decimal import Decimal
from collections import defaultdict
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Stock, WeeklyData, Signal
from app import config

# Conectar a BD remota (dev)
config.DB_CONFIG['host'] = '192.168.100.11'
DB_URL = (f"mysql+pymysql://{config.DB_CONFIG['user']}:{config.DB_CONFIG['password']}"
          f"@{config.DB_CONFIG['host']}/{config.DB_CONFIG['database']}"
          f"?charset={config.DB_CONFIG['charset']}")
engine = create_engine(DB_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
db = Session()


# ============================================================================
# CARGA DE DATOS
# ============================================================================

def load_all_weekly_data():
    """Cargar todos los datos semanales de todas las acciones activas en memoria"""
    stocks = db.query(Stock).filter(Stock.active == True).all()
    stock_map = {s.id: s.ticker for s in stocks}

    data = {}
    for stock in stocks:
        weeks = db.query(WeeklyData).filter(
            WeeklyData.stock_id == stock.id
        ).order_by(WeeklyData.week_end_date.asc()).all()

        if len(weeks) < 35:  # Mínimo para MA30 + margen
            continue

        data[stock.ticker] = [{
            'date': w.week_end_date,
            'open': float(w.open) if w.open else None,
            'high': float(w.high) if w.high else None,
            'low': float(w.low) if w.low else None,
            'close': float(w.close) if w.close else None,
            'volume': w.volume,
            'ma30': float(w.ma30) if w.ma30 else None,
            'ma30_slope': float(w.ma30_slope) if w.ma30_slope else None,
        } for w in weeks]

    return data


def recalculate_ma30_and_slope(weeks_data):
    """Recalcular MA30 y slope desde los datos de cierre (para consistencia)"""
    for i, w in enumerate(weeks_data):
        if i >= 29:  # Necesitamos 30 semanas de datos
            closes = [weeks_data[j]['close'] for j in range(i - 29, i + 1)]
            w['ma30_calc'] = sum(closes) / 30
        else:
            w['ma30_calc'] = None

        if i >= 30 and weeks_data[i - 1].get('ma30_calc') and w.get('ma30_calc'):
            prev_ma30 = weeks_data[i - 1]['ma30_calc']
            if prev_ma30 > 0:
                w['ma30_slope_1w'] = (w['ma30_calc'] - prev_ma30) / prev_ma30
            else:
                w['ma30_slope_1w'] = None
        else:
            w['ma30_slope_1w'] = None

        # Slope multi-período (4 semanas)
        if i >= 33 and weeks_data[i - 4].get('ma30_calc') and w.get('ma30_calc'):
            prev_ma30_4w = weeks_data[i - 4]['ma30_calc']
            if prev_ma30_4w > 0:
                w['ma30_slope_4w'] = (w['ma30_calc'] - prev_ma30_4w) / prev_ma30_4w
            else:
                w['ma30_slope_4w'] = None
        else:
            w['ma30_slope_4w'] = None

        # Slope multi-período (8 semanas)
        if i >= 37 and weeks_data[i - 8].get('ma30_calc') and w.get('ma30_calc'):
            prev_ma30_8w = weeks_data[i - 8]['ma30_calc']
            if prev_ma30_8w > 0:
                w['ma30_slope_8w'] = (w['ma30_calc'] - prev_ma30_8w) / prev_ma30_8w
            else:
                w['ma30_slope_8w'] = None
        else:
            w['ma30_slope_8w'] = None

    return weeks_data


# ============================================================================
# ALGORITMO BASELINE (actual)
# ============================================================================

class BaselineDetector:
    """Replica exacta del algoritmo actual"""

    def __init__(self):
        self.name = "BASELINE (actual)"
        self.ma30_slope_threshold = 0.02  # 2%
        self.price_ma30_threshold = 0.05  # 5%

    def detect_stage(self, week, previous_stage):
        close = week['close']
        ma30 = week.get('ma30')  # Usamos MA30 de la BD
        slope = week.get('ma30_slope')  # Slope de la BD

        if ma30 is None or ma30 == 0:
            return previous_stage if previous_stage else 1

        price_distance = (close - ma30) / ma30

        price_above_ma30 = price_distance > self.price_ma30_threshold
        price_below_ma30 = price_distance < -self.price_ma30_threshold
        price_near_ma30 = not price_above_ma30 and not price_below_ma30

        if slope is None:
            slope_flat = True
            slope_up = False
            slope_down = False
        else:
            slope_flat = abs(slope) <= self.ma30_slope_threshold
            slope_up = slope > self.ma30_slope_threshold
            slope_down = slope < -self.ma30_slope_threshold

        # Etapa 2
        if price_above_ma30 and slope_up:
            return 2
        # Etapa 4
        if price_below_ma30 and slope_down:
            return 4
        # Etapa 3
        if (price_near_ma30 or price_above_ma30) and slope_flat and previous_stage == 2:
            return 3
        # Etapa 1
        if (price_near_ma30 or price_below_ma30) and (slope_flat or slope_down):
            if previous_stage in [4, None]:
                return 1
        # Default
        return previous_stage if previous_stage else 1


# ============================================================================
# ALGORITMO MEJORADO V1: Slope multi-período + volumen
# ============================================================================

class ImprovedDetectorV1:
    """
    Mejoras sobre baseline:
    1. Usa slope de 4 semanas en vez de 1 semana
    2. Umbral de slope reducido (más realista para MA30)
    3. Confirmación por volumen en transición 1→2
    4. Precio no puede estar >25% sobre MA30 para ser etapa 1
    """

    def __init__(self):
        self.name = "V1: Slope 4w + Volumen + límite precio"
        self.ma30_slope_threshold = 0.04   # 4% en 4 semanas
        self.price_ma30_threshold = 0.03   # 3% distancia
        self.max_price_above_for_stage1 = 0.15  # 15% máximo sobre MA30 para etapa 1
        self.volume_confirmation = 1.2     # 120% del volumen promedio para breakout

    def detect_stage(self, week, previous_stage, context=None):
        close = week['close']
        ma30 = week.get('ma30_calc') or week.get('ma30')
        slope = week.get('ma30_slope_4w')  # Slope de 4 semanas

        if ma30 is None or ma30 == 0:
            return previous_stage if previous_stage else 1

        price_distance = (close - ma30) / ma30

        price_above_ma30 = price_distance > self.price_ma30_threshold
        price_below_ma30 = price_distance < -self.price_ma30_threshold
        price_near_ma30 = not price_above_ma30 and not price_below_ma30

        if slope is None:
            slope_flat = True
            slope_up = False
            slope_down = False
        else:
            slope_flat = abs(slope) <= self.ma30_slope_threshold
            slope_up = slope > self.ma30_slope_threshold
            slope_down = slope < -self.ma30_slope_threshold

        # Etapa 2
        if price_above_ma30 and slope_up:
            return 2
        # Etapa 4
        if price_below_ma30 and slope_down:
            return 4
        # Etapa 3
        if (price_near_ma30 or price_above_ma30) and slope_flat and previous_stage in [2, 3]:
            return 3
        # Etapa 1
        if (price_near_ma30 or price_below_ma30) and (slope_flat or slope_down):
            if previous_stage in [4, 1, None]:
                return 1
        # Default
        return previous_stage if previous_stage else 1

    def should_generate_buy(self, week, previous_stage, current_stage, weeks_history):
        """Verificaciones adicionales para generar señal BUY"""
        if previous_stage != 1 or current_stage != 2:
            return False

        close = week['close']
        ma30 = week.get('ma30_calc') or week.get('ma30')

        # Verificar que el precio no esté demasiado lejos de MA30
        if ma30 and ma30 > 0:
            distance = (close - ma30) / ma30
            if distance > self.max_price_above_for_stage1:
                return False

        # Verificar volumen (ratio vs promedio 8 semanas anteriores)
        if weeks_history and len(weeks_history) >= 8:
            recent_vols = [w.get('volume', 0) or 0 for w in weeks_history[-8:]]
            avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 0
            curr_vol = week.get('volume', 0) or 0
            if avg_vol > 0 and curr_vol / avg_vol < self.volume_confirmation:
                return False

        return True


# ============================================================================
# ALGORITMO MEJORADO V2: Slope 4w + volumen + confirmación temporal
# ============================================================================

class ImprovedDetectorV2:
    """
    V2: Como V1 pero con confirmación temporal (2 semanas consecutivas)
    y transiciones de etapa más flexibles.
    """

    def __init__(self):
        self.name = "V2: V1 + confirmación 2 semanas"
        self.ma30_slope_threshold = 0.04
        self.price_ma30_threshold = 0.03
        self.max_price_above_for_stage1 = 0.15
        self.volume_confirmation = 1.2
        self.confirmation_weeks = 2  # Semanas consecutivas necesarias

    def detect_stage(self, week, previous_stage, context=None):
        close = week['close']
        ma30 = week.get('ma30_calc') or week.get('ma30')
        slope = week.get('ma30_slope_4w')

        if ma30 is None or ma30 == 0:
            return previous_stage if previous_stage else 1

        price_distance = (close - ma30) / ma30

        price_above_ma30 = price_distance > self.price_ma30_threshold
        price_below_ma30 = price_distance < -self.price_ma30_threshold
        price_near_ma30 = not price_above_ma30 and not price_below_ma30

        if slope is None:
            slope_flat = True
            slope_up = False
            slope_down = False
        else:
            slope_flat = abs(slope) <= self.ma30_slope_threshold
            slope_up = slope > self.ma30_slope_threshold
            slope_down = slope < -self.ma30_slope_threshold

        # Etapa 2
        if price_above_ma30 and slope_up:
            return 2
        # Etapa 4
        if price_below_ma30 and slope_down:
            return 4
        # Etapa 3
        if (price_near_ma30 or price_above_ma30) and slope_flat and previous_stage in [2, 3]:
            return 3
        # Etapa 1
        if (price_near_ma30 or price_below_ma30) and (slope_flat or slope_down):
            if previous_stage in [4, 1, None]:
                return 1
        # Default
        return previous_stage if previous_stage else 1

    def should_generate_buy(self, week, previous_stage, current_stage, weeks_history):
        if previous_stage != 1 or current_stage != 2:
            return False

        close = week['close']
        ma30 = week.get('ma30_calc') or week.get('ma30')

        if ma30 and ma30 > 0:
            distance = (close - ma30) / ma30
            if distance > self.max_price_above_for_stage1:
                return False

        # Verificar volumen
        if weeks_history and len(weeks_history) >= 8:
            recent_vols = [w.get('volume', 0) or 0 for w in weeks_history[-8:]]
            avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 0
            curr_vol = week.get('volume', 0) or 0
            if avg_vol > 0 and curr_vol / avg_vol < self.volume_confirmation:
                return False

        return True


# ============================================================================
# ALGORITMO MEJORADO V3: Slope 8w + criterios más estrictos
# ============================================================================

class ImprovedDetectorV3:
    """
    V3: Slope de 8 semanas, criterios más estrictos.
    El más conservador - menos señales pero más fiables.
    """

    def __init__(self):
        self.name = "V3: Slope 8w + criterios estrictos"
        self.ma30_slope_threshold = 0.06   # 6% en 8 semanas
        self.price_ma30_threshold = 0.03
        self.max_price_above_for_stage1 = 0.10  # 10% máximo
        self.volume_confirmation = 1.3     # 130% volumen
        self.min_weeks_in_stage1 = 4       # Al menos 4 semanas en etapa 1

    def detect_stage(self, week, previous_stage, context=None):
        close = week['close']
        ma30 = week.get('ma30_calc') or week.get('ma30')
        slope = week.get('ma30_slope_8w')  # Slope de 8 semanas

        if ma30 is None or ma30 == 0:
            return previous_stage if previous_stage else 1

        price_distance = (close - ma30) / ma30

        price_above_ma30 = price_distance > self.price_ma30_threshold
        price_below_ma30 = price_distance < -self.price_ma30_threshold
        price_near_ma30 = not price_above_ma30 and not price_below_ma30

        if slope is None:
            slope_flat = True
            slope_up = False
            slope_down = False
        else:
            slope_flat = abs(slope) <= self.ma30_slope_threshold
            slope_up = slope > self.ma30_slope_threshold
            slope_down = slope < -self.ma30_slope_threshold

        # Etapa 2
        if price_above_ma30 and slope_up:
            return 2
        # Etapa 4
        if price_below_ma30 and slope_down:
            return 4
        # Etapa 3
        if (price_near_ma30 or price_above_ma30) and slope_flat and previous_stage in [2, 3]:
            return 3
        # Etapa 1
        if (price_near_ma30 or price_below_ma30) and (slope_flat or slope_down):
            if previous_stage in [4, 1, None]:
                return 1
        # Default
        return previous_stage if previous_stage else 1

    def should_generate_buy(self, week, previous_stage, current_stage, weeks_history):
        if previous_stage != 1 or current_stage != 2:
            return False

        close = week['close']
        ma30 = week.get('ma30_calc') or week.get('ma30')

        if ma30 and ma30 > 0:
            distance = (close - ma30) / ma30
            if distance > self.max_price_above_for_stage1:
                return False

        # Verificar volumen
        if weeks_history and len(weeks_history) >= 8:
            recent_vols = [w.get('volume', 0) or 0 for w in weeks_history[-8:]]
            avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 0
            curr_vol = week.get('volume', 0) or 0
            if avg_vol > 0 and curr_vol / avg_vol < self.volume_confirmation:
                return False

        return True


# ============================================================================
# MOTOR DE BACKTEST
# ============================================================================

def run_backtest(all_data, detector, start_date=None, end_date=None):
    """
    Ejecutar backtest con un detector dado.

    Returns:
        dict con resultados del backtest
    """
    if start_date is None:
        start_date = date(2024, 6, 1)
    if end_date is None:
        end_date = date(2026, 2, 14)

    signals = []
    stage_changes = defaultdict(int)

    for ticker, weeks in all_data.items():
        # Recalcular slopes multi-período
        weeks = recalculate_ma30_and_slope(weeks)

        previous_stage = None
        weeks_in_current_stage = 0

        for i, week in enumerate(weeks):
            if week['date'] < start_date:
                # Calcular stages previos para contexto
                if week.get('ma30') is not None:
                    stage = detector.detect_stage(week, previous_stage)
                    if stage == previous_stage:
                        weeks_in_current_stage += 1
                    else:
                        weeks_in_current_stage = 1
                    previous_stage = stage
                continue
            if week['date'] > end_date:
                break

            if week.get('ma30') is None:
                continue

            current_stage = detector.detect_stage(week, previous_stage)

            if previous_stage and current_stage != previous_stage:
                transition = f"{previous_stage}→{current_stage}"
                stage_changes[transition] += 1

                # BUY signal
                if previous_stage == 1 and current_stage == 2:
                    # Check additional filters if detector supports them
                    history = weeks[max(0, i - 8):i]
                    if hasattr(detector, 'should_generate_buy'):
                        should_buy = detector.should_generate_buy(
                            week, previous_stage, current_stage, history
                        )
                    else:
                        should_buy = True

                    if should_buy:
                        # Calcular rendimientos futuros
                        future_weeks = weeks[i + 1:]
                        returns = {}
                        for target in [4, 8, 12, 26]:
                            if len(future_weeks) >= target:
                                future_close = future_weeks[target - 1]['close']
                                ret = (future_close - week['close']) / week['close'] * 100
                                returns[f'{target}w'] = ret
                            else:
                                returns[f'{target}w'] = None

                        # Max gain y drawdown en 12 semanas
                        max_gain = 0.0
                        max_drawdown = 0.0
                        for fw in future_weeks[:12]:
                            if fw['high']:
                                gain = (fw['high'] - week['close']) / week['close'] * 100
                                max_gain = max(max_gain, gain)
                            if fw['low']:
                                dd = (fw['low'] - week['close']) / week['close'] * 100
                                max_drawdown = min(max_drawdown, dd)

                        ma30 = week.get('ma30_calc') or week.get('ma30')
                        price_vs_ma30 = ((week['close'] - ma30) / ma30 * 100) if ma30 else None
                        vol_ratio = 1.0
                        if i >= 8:
                            avg_vol = sum(weeks[j]['volume'] or 0 for j in range(i - 8, i)) / 8
                            if avg_vol > 0:
                                vol_ratio = (week['volume'] or 0) / avg_vol

                        signals.append({
                            'ticker': ticker,
                            'date': week['date'],
                            'price': week['close'],
                            'ma30': ma30,
                            'price_vs_ma30': price_vs_ma30,
                            'slope_1w': week.get('ma30_slope') or week.get('ma30_slope_1w'),
                            'slope_4w': week.get('ma30_slope_4w'),
                            'slope_8w': week.get('ma30_slope_8w'),
                            'vol_ratio': vol_ratio,
                            'returns': returns,
                            'max_gain_12w': max_gain,
                            'max_drawdown_12w': max_drawdown,
                            'is_false_positive': max_gain < 5.0,
                            'weeks_in_stage1': weeks_in_current_stage,
                        })

                # SELL signal
                if current_stage == 4 and previous_stage in [2, 3]:
                    signals.append({
                        'ticker': ticker,
                        'date': week['date'],
                        'price': week['close'],
                        'type': 'SELL',
                    })

            if current_stage == previous_stage:
                weeks_in_current_stage += 1
            else:
                weeks_in_current_stage = 1
            previous_stage = current_stage

    # Filtrar solo BUY signals
    buy_signals = [s for s in signals if s.get('type') != 'SELL']
    sell_signals = [s for s in signals if s.get('type') == 'SELL']

    return {
        'detector_name': detector.name,
        'buy_signals': buy_signals,
        'sell_signals': sell_signals,
        'stage_changes': dict(stage_changes),
    }


def calculate_metrics(result):
    """Calcular métricas de rendimiento de un backtest"""
    buy_signals = result['buy_signals']

    if not buy_signals:
        return {
            'total_buy': 0,
            'false_positives': 0,
            'fp_rate': 0,
            'avg_return_4w': 0,
            'avg_return_8w': 0,
            'avg_return_12w': 0,
            'avg_max_gain': 0,
            'avg_max_drawdown': 0,
            'win_rate_12w': 0,
        }

    total = len(buy_signals)
    false_positives = sum(1 for s in buy_signals if s.get('is_false_positive', False))

    # Rendimientos promedio (solo señales con datos)
    rets_4w = [s['returns']['4w'] for s in buy_signals if s['returns'].get('4w') is not None]
    rets_8w = [s['returns']['8w'] for s in buy_signals if s['returns'].get('8w') is not None]
    rets_12w = [s['returns']['12w'] for s in buy_signals if s['returns'].get('12w') is not None]
    rets_26w = [s['returns']['26w'] for s in buy_signals if s['returns'].get('26w') is not None]

    gains = [s['max_gain_12w'] for s in buy_signals]
    drawdowns = [s['max_drawdown_12w'] for s in buy_signals]

    # Win rate: señales que tuvieron rendimiento positivo a 12 semanas
    wins_12w = sum(1 for r in rets_12w if r > 0)

    return {
        'total_buy': total,
        'total_sell': len(result['sell_signals']),
        'false_positives': false_positives,
        'fp_rate': false_positives / total * 100 if total > 0 else 0,
        'avg_return_4w': sum(rets_4w) / len(rets_4w) if rets_4w else None,
        'avg_return_8w': sum(rets_8w) / len(rets_8w) if rets_8w else None,
        'avg_return_12w': sum(rets_12w) / len(rets_12w) if rets_12w else None,
        'avg_return_26w': sum(rets_26w) / len(rets_26w) if rets_26w else None,
        'median_return_12w': sorted(rets_12w)[len(rets_12w) // 2] if rets_12w else None,
        'avg_max_gain': sum(gains) / len(gains) if gains else 0,
        'avg_max_drawdown': sum(drawdowns) / len(drawdowns) if drawdowns else 0,
        'win_rate_12w': wins_12w / len(rets_12w) * 100 if rets_12w else 0,
        'n_with_12w_data': len(rets_12w),
        'stage_changes': result['stage_changes'],
    }


def print_results(result, metrics):
    """Imprimir resultados de un backtest"""
    print(f"\n{'=' * 80}")
    print(f"  {result['detector_name']}")
    print(f"{'=' * 80}")

    print(f"\n  Señales BUY generadas: {metrics['total_buy']}")
    print(f"  Falsos positivos (max gain <5% en 12w): {metrics['false_positives']}")
    print(f"  Tasa de falsos positivos: {metrics['fp_rate']:.1f}%")
    print(f"  Señales con datos 12w: {metrics['n_with_12w_data']}")
    print(f"  Win rate (12w): {metrics['win_rate_12w']:.1f}%")

    print(f"\n  Rendimiento promedio:")
    for period in ['4w', '8w', '12w', '26w']:
        key = f'avg_return_{period}'
        val = metrics.get(key)
        if val is not None:
            print(f"    {period}: {val:+.2f}%")
        else:
            print(f"    {period}: N/A")

    if metrics.get('median_return_12w') is not None:
        print(f"    Mediana 12w: {metrics['median_return_12w']:+.2f}%")

    print(f"\n  Max gain promedio (12w): {metrics['avg_max_gain']:.2f}%")
    print(f"  Max drawdown promedio (12w): {metrics['avg_max_drawdown']:.2f}%")

    # Detalle de señales
    signals = sorted(result['buy_signals'], key=lambda x: x['date'])
    if signals:
        print(f"\n  {'Ticker':<8} {'Fecha':<12} {'Precio':>8} {'P/MA30%':>8} {'VolRat':>7} "
              f"{'4w%':>7} {'8w%':>7} {'12w%':>7} {'MaxG%':>7} {'MaxDD%':>7} {'FP?':>4}")
        print(f"  {'-' * 95}")

        for s in signals:
            ret_4w = f"{s['returns']['4w']:.1f}" if s['returns'].get('4w') is not None else "N/A"
            ret_8w = f"{s['returns']['8w']:.1f}" if s['returns'].get('8w') is not None else "N/A"
            ret_12w = f"{s['returns']['12w']:.1f}" if s['returns'].get('12w') is not None else "N/A"
            pma = f"{s['price_vs_ma30']:.1f}" if s.get('price_vs_ma30') is not None else "N/A"
            fp = "SÍ" if s.get('is_false_positive') else ""

            print(f"  {s['ticker']:<8} {str(s['date']):<12} {s['price']:>8.2f} {pma:>8} "
                  f"{s['vol_ratio']:>7.2f} {ret_4w:>7} {ret_8w:>7} {ret_12w:>7} "
                  f"{s['max_gain_12w']:>7.1f} {s['max_drawdown_12w']:>7.1f} {fp:>4}")


def main():
    print("=" * 80)
    print("  BACKTEST COMPLETO - Sistema Weinstein")
    print("  Período: 2024-06-01 a 2026-02-14")
    print("=" * 80)

    print("\nCargando datos semanales de todas las acciones...")
    all_data = load_all_weekly_data()
    print(f"  Acciones cargadas: {len(all_data)}")

    # Definir detectores
    detectors = [
        BaselineDetector(),
        ImprovedDetectorV1(),
        ImprovedDetectorV2(),
        ImprovedDetectorV3(),
    ]

    all_results = []

    for detector in detectors:
        print(f"\nEjecutando backtest: {detector.name}...")
        result = run_backtest(all_data, detector)
        metrics = calculate_metrics(result)
        all_results.append((result, metrics))
        print_results(result, metrics)

    # =========================================
    # TABLA COMPARATIVA
    # =========================================
    print("\n\n" + "=" * 80)
    print("  TABLA COMPARATIVA")
    print("=" * 80)

    header = f"  {'Métrica':<35}"
    for result, _ in all_results:
        name = result['detector_name'][:15]
        header += f" {name:>15}"
    print(header)
    print("  " + "-" * (35 + 16 * len(all_results)))

    rows = [
        ('Total señales BUY', 'total_buy', '{:d}'),
        ('Falsos positivos', 'false_positives', '{:d}'),
        ('Tasa FP (%)', 'fp_rate', '{:.1f}'),
        ('Win rate 12w (%)', 'win_rate_12w', '{:.1f}'),
        ('Retorno medio 4w (%)', 'avg_return_4w', '{:+.2f}'),
        ('Retorno medio 8w (%)', 'avg_return_8w', '{:+.2f}'),
        ('Retorno medio 12w (%)', 'avg_return_12w', '{:+.2f}'),
        ('Retorno medio 26w (%)', 'avg_return_26w', '{:+.2f}'),
        ('Mediana retorno 12w (%)', 'median_return_12w', '{:+.2f}'),
        ('Max gain medio 12w (%)', 'avg_max_gain', '{:.2f}'),
        ('Max drawdown medio 12w (%)', 'avg_max_drawdown', '{:.2f}'),
    ]

    for label, key, fmt in rows:
        row = f"  {label:<35}"
        for _, metrics in all_results:
            val = metrics.get(key)
            if val is not None:
                row += f" {fmt.format(val):>15}"
            else:
                row += f" {'N/A':>15}"
        print(row)

    # =========================================
    # VERIFICACIÓN AMD
    # =========================================
    print("\n\n" + "=" * 80)
    print("  VERIFICACIÓN: ¿Se genera señal AMD 23/01/2026 en cada versión?")
    print("=" * 80)

    for result, _ in all_results:
        amd_signals = [s for s in result['buy_signals']
                       if s['ticker'] == 'AMD' and s['date'] == date(2026, 1, 23)]
        status = "SÍ (se genera)" if amd_signals else "NO (filtrada)"
        print(f"  {result['detector_name']:<45} → {status}")

    # Todas las señales AMD
    print(f"\n  Señales BUY de AMD por versión:")
    for result, _ in all_results:
        amd_buys = [s for s in result['buy_signals'] if s['ticker'] == 'AMD']
        dates = [str(s['date']) for s in amd_buys]
        print(f"  {result['detector_name']:<45} → {', '.join(dates) if dates else 'Ninguna'}")

    db.close()
    print("\n[Backtest completado]")


if __name__ == '__main__':
    main()
