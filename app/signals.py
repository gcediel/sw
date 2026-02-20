"""
Generador de señales de trading - Sistema Weinstein
Señales BUY: cruce de precio sobre MA30 con base sólida previa
Señales SELL: transición a Etapa 3/4
"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import Stock, WeeklyData, Signal, SessionLocal
from app.config import (
    BUY_MIN_BASE_WEEKS, BUY_MAX_BASE_SLOPE,
    BUY_MAX_DIST_ENTRY, MIN_WEEKS_FOR_ANALYSIS
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Generador de señales de trading basado en la metodología Weinstein.

    Señales BUY: cruce de precio sobre MA30 con base sólida (16+ semanas
    de consolidación con MA30 plana), filtrado por estado del mercado (SPY).

    Señales SELL: cambio de etapa a 3 ó 4 detectado por el analizador.
    """

    def __init__(self, db: Session):
        self.db = db
        self._spy_states = None  # caché SPY cargado bajo demanda

    # ------------------------------------------------------------------
    # SPY — Filtro de mercado
    # ------------------------------------------------------------------

    def _load_spy_states(self) -> dict:
        """
        Carga el estado del mercado (alcista/bajista) de SPY para cada semana.
        Alcista = precio >= MA30 * 0.97  Y  slope >= 0
        """
        if self._spy_states is not None:
            return self._spy_states

        spy = self.db.query(Stock).filter(Stock.ticker == 'SPY').first()
        if not spy:
            logger.warning("SPY no encontrado en BD; filtro de mercado desactivado")
            self._spy_states = {}
            return self._spy_states

        weekly = self.db.query(WeeklyData).filter(
            WeeklyData.stock_id == spy.id,
            WeeklyData.ma30.isnot(None)
        ).order_by(WeeklyData.week_end_date.asc()).all()

        self._spy_states = {}
        for w in weekly:
            ma30  = float(w.ma30)
            close = float(w.close)
            slope = float(w.ma30_slope) if w.ma30_slope else 0
            self._spy_states[w.week_end_date] = (close >= ma30 * 0.97) and (slope >= 0)

        return self._spy_states

    def _market_is_bullish(self, week_date) -> bool:
        """Devuelve True si el mercado (SPY) era alcista en la semana dada."""
        states = self._load_spy_states()
        if not states:
            return True  # sin datos SPY: no filtrar

        # Buscar la semana SPY más cercana anterior o igual a week_date
        best = None
        for d in sorted(states.keys()):
            if d <= week_date:
                best = d
            else:
                break
        return states.get(best, True)

    # ------------------------------------------------------------------
    # Señales BUY — Cruce precio/MA30 con base sólida
    # ------------------------------------------------------------------

    def _is_valid_buy_breakout(self, weekly_all: list, idx: int) -> bool:
        """
        Verifica si la semana `idx` es un cruce válido de precio sobre MA30.

        Criterios:
        1. Semana anterior: precio < 2% sobre MA30
        2. Semana actual:   precio > 2% sobre MA30 y <= BUY_MAX_DIST_ENTRY
        3. MA30 girando al alza en la semana del cruce (slope > 0)
        4. Últimas BUY_MIN_BASE_WEEKS semanas: precio dentro del rango [-10%, +5%]
           respecto a MA30 en al menos BUY_MIN_BASE_WEEKS-2 semanas
           (filtra acciones en Stage 4 con precio muy por debajo de MA30)
        5. MA30 no ha caído más de 5% durante la base (no tendencia bajista)
        6. Últimas BUY_MIN_BASE_WEEKS semanas: MA30 plana (|slope| <= BUY_MAX_BASE_SLOPE)
           al menos en el 75% de las semanas
        7. Suficiente histórico: idx >= MIN_WEEKS_FOR_ANALYSIS + BUY_MIN_BASE_WEEKS
        """
        if idx < MIN_WEEKS_FOR_ANALYSIS + BUY_MIN_BASE_WEEKS:
            return False

        curr = weekly_all[idx]
        prev = weekly_all[idx - 1]

        if not (curr.ma30 and prev.ma30):
            return False

        curr_close = float(curr.close)
        curr_ma30  = float(curr.ma30)
        prev_close = float(prev.close)
        prev_ma30  = float(prev.ma30)

        curr_dist = (curr_close - curr_ma30) / curr_ma30
        prev_dist = (prev_close - prev_ma30) / prev_ma30

        # Cruce: de bajo/cerca MA30 a por encima
        if not (prev_dist < 0.02 and curr_dist > 0.02):
            return False
        if curr_dist > BUY_MAX_DIST_ENTRY:
            return False

        # MA30 debe estar girando al alza en la semana del cruce
        if not curr.ma30_slope or float(curr.ma30_slope) <= 0:
            return False

        # Validar base previa
        base = weekly_all[idx - BUY_MIN_BASE_WEEKS:idx]

        # Precio dentro del rango [-10%, +5%] de MA30 (no en Stage 4 profunda)
        base_near = sum(
            1 for w in base
            if w.ma30 and float(w.ma30) > 0
            and -0.10 <= (float(w.close) - float(w.ma30)) / float(w.ma30) < 0.05
        )

        # MA30 no debe haber caído más del 5% durante la base (no bajista sostenida)
        if base[0].ma30 and float(base[0].ma30) > 0:
            ma30_change = (curr_ma30 - float(base[0].ma30)) / float(base[0].ma30)
            if ma30_change < -0.05:
                return False

        slopes_flat = sum(
            1 for w in base
            if w.ma30_slope and abs(float(w.ma30_slope)) <= BUY_MAX_BASE_SLOPE
        )

        if base_near < BUY_MIN_BASE_WEEKS - 2:
            return False
        if slopes_flat < int(BUY_MIN_BASE_WEEKS * 0.75):
            return False

        return True

    def _generate_buy_signals(self, stock_id: int, stock_ticker: str,
                               weekly_all: list, weeks_back: int) -> int:
        """
        Genera señales BUY para las últimas `weeks_back` semanas de una acción.
        Si weeks_back=0 se revisa todo el histórico.
        """
        if len(weekly_all) < MIN_WEEKS_FOR_ANALYSIS + BUY_MIN_BASE_WEEKS:
            return 0

        # Índice del primer punto a revisar
        if weeks_back > 0:
            start_idx = max(1, len(weekly_all) - weeks_back)
        else:
            start_idx = 1

        signals_created = 0

        for i in range(start_idx, len(weekly_all)):
            if not self._is_valid_buy_breakout(weekly_all, i):
                continue

            curr = weekly_all[i]

            # Filtro mercado
            if not self._market_is_bullish(curr.week_end_date):
                logger.debug(f"{stock_ticker}: BUY descartada {curr.week_end_date} — mercado bajista")
                continue

            change_info = {
                'stock_id': stock_id,
                'week_end_date': curr.week_end_date,
                'stage_from': 1,
                'stage_to': 2,
                'price': float(curr.close),
                'ma30': float(curr.ma30),
            }

            if self._create_signal_record(change_info, 'BUY'):
                dist = (float(curr.close) - float(curr.ma30)) / float(curr.ma30) * 100
                logger.info(f"✓ {stock_ticker}: BUY {curr.week_end_date} "
                            f"(cruce MA30, dist={dist:.1f}%)")
                signals_created += 1

        return signals_created

    # ------------------------------------------------------------------
    # Señales SELL — Cambio de etapa a 3/4
    # ------------------------------------------------------------------

    def _generate_sell_signals(self, stock_id: int, stock_ticker: str,
                                weekly_stage: list, weeks_back: int) -> int:
        """
        Genera señales SELL cuando la etapa cambia a 3 ó 4.
        Usa el histórico de etapas calculado por el analizador.
        """
        if len(weekly_stage) < 2:
            return 0

        if weeks_back > 0:
            check = weekly_stage[-weeks_back:]
        else:
            check = weekly_stage

        signals_created = 0

        for i in range(1, len(check)):
            prev = check[i - 1]
            curr = check[i]

            if prev.stage is None or curr.stage is None:
                continue
            if prev.stage == curr.stage:
                continue

            stage_from = prev.stage
            stage_to   = curr.stage

            # SELL: transición a Etapa 4 desde 2 o 3
            if stage_to == 4 and stage_from in [2, 3]:
                signal_type = 'SELL'
            # STAGE_CHANGE: cualquier otro cambio relevante
            elif stage_to == 3 and stage_from == 2:
                signal_type = 'STAGE_CHANGE'
            else:
                continue

            change_info = {
                'stock_id': stock_id,
                'week_end_date': curr.week_end_date,
                'stage_from': stage_from,
                'stage_to': stage_to,
                'price': float(curr.close),
                'ma30': float(curr.ma30) if curr.ma30 else None,
            }

            if self._create_signal_record(change_info, signal_type):
                logger.info(f"✓ {stock_ticker}: {signal_type} {curr.week_end_date} "
                            f"(Etapa {stage_from}→{stage_to})")
                signals_created += 1

        return signals_created

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def _create_signal_record(self, change_info: dict, signal_type: str) -> bool:
        """Crea el registro Signal en BD si no existe ya."""
        existing = self.db.query(Signal).filter(
            and_(
                Signal.stock_id == change_info['stock_id'],
                Signal.signal_date == change_info['week_end_date'],
                Signal.signal_type == signal_type
            )
        ).first()

        if existing:
            return False

        signal = Signal(
            stock_id=change_info['stock_id'],
            signal_date=change_info['week_end_date'],
            signal_type=signal_type,
            stage_from=change_info['stage_from'],
            stage_to=change_info['stage_to'],
            price=change_info['price'],
            ma30=change_info['ma30'],
            notified=False
        )
        self.db.add(signal)
        return True

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def generate_signals_for_stock(self, stock_id: int, weeks_back: int = 10) -> int:
        """
        Genera señales BUY y SELL para una acción.

        Args:
            stock_id: ID de la acción
            weeks_back: Semanas hacia atrás a revisar (0 = todas)

        Returns:
            Número de señales creadas
        """
        stock = self.db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            return 0
        ticker = stock.ticker

        # Datos con MA30 (para BUY) — todo el histórico necesario
        weekly_ma30 = self.db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock_id,
                WeeklyData.ma30.isnot(None),
                WeeklyData.ma30_slope.isnot(None)
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()

        # Datos con etapa (para SELL)
        weekly_stage = self.db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock_id,
                WeeklyData.stage.isnot(None)
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()

        buy_signals  = self._generate_buy_signals(stock_id, ticker, weekly_ma30, weeks_back)
        sell_signals = self._generate_sell_signals(stock_id, ticker, weekly_stage, weeks_back)

        total = buy_signals + sell_signals
        if total > 0:
            try:
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                logger.error(f"✗ Error guardando señales de {ticker}: {e}")
                return 0

        return total

    def generate_signals_for_all_stocks(self, weeks_back: int = 10) -> dict:
        """
        Genera señales para todas las acciones activas (excluye índices).

        Args:
            weeks_back: Semanas hacia atrás (0 = todas)

        Returns:
            Dict con estadísticas
        """
        stocks = self.db.query(Stock).filter(
            Stock.active == True,
            Stock.exchange != 'INDEX'
        ).all()

        logger.info(f"Generando señales para {len(stocks)} acciones "
                    f"(últimas {weeks_back} semanas)")

        total_signals = 0
        stocks_with_signals = 0
        failed = []

        for stock in stocks:
            try:
                n = self.generate_signals_for_stock(stock.id, weeks_back)
                total_signals += n
                if n > 0:
                    stocks_with_signals += 1
            except Exception as e:
                logger.error(f"✗ Error en {stock.ticker}: {e}")
                failed.append(stock.ticker)

        return {
            'total_stocks': len(stocks),
            'stocks_with_signals': stocks_with_signals,
            'total_signals': total_signals,
            'failed': len(failed),
            'failed_tickers': failed
        }

    def get_recent_signals(self, days: int = 7, signal_type: Optional[str] = None) -> List[dict]:
        """Obtener señales recientes."""
        cutoff_date = datetime.now().date() - timedelta(days=days)

        query = self.db.query(Signal, Stock).join(
            Stock, Signal.stock_id == Stock.id
        ).filter(
            Signal.signal_date >= cutoff_date
        )

        if signal_type:
            query = query.filter(Signal.signal_type == signal_type)

        results = []
        for signal, stock in query.order_by(Signal.signal_date.desc()).all():
            results.append({
                'ticker': stock.ticker,
                'name': stock.name,
                'signal_date': signal.signal_date,
                'signal_type': signal.signal_type,
                'stage_from': signal.stage_from,
                'stage_to': signal.stage_to,
                'price': float(signal.price) if signal.price else None,
                'ma30': float(signal.ma30) if signal.ma30 else None,
                'notified': signal.notified
            })

        return results

    def get_unnotified_signals(self, days: int = 14) -> List[dict]:
        """Obtener señales pendientes de notificar (últimos N días)."""
        cutoff_date = datetime.now().date() - timedelta(days=days)

        results = self.db.query(Signal, Stock).join(
            Stock, Signal.stock_id == Stock.id
        ).filter(
            Signal.notified == False,
            Signal.signal_date >= cutoff_date
        ).order_by(Signal.signal_date.desc()).all()

        signals = []
        for signal, stock in results:
            signals.append({
                'id': signal.id,
                'ticker': stock.ticker,
                'name': stock.name,
                'signal_date': signal.signal_date,
                'signal_type': signal.signal_type,
                'stage_from': signal.stage_from,
                'stage_to': signal.stage_to,
                'price': float(signal.price) if signal.price else None,
                'ma30': float(signal.ma30) if signal.ma30 else None,
            })

        return signals

    def mark_signals_as_notified(self, signal_ids: List[int]) -> int:
        """Marcar señales como notificadas."""
        if not signal_ids:
            return 0

        updated = self.db.query(Signal).filter(
            Signal.id.in_(signal_ids)
        ).update({Signal.notified: True}, synchronize_session=False)

        self.db.commit()
        return updated


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def generate_all_signals_initial() -> dict:
    """
    Genera TODAS las señales históricas. Usar solo en inicialización.
    """
    db = SessionLocal()
    generator = SignalGenerator(db)
    logger.info("Generando todas las señales (histórico completo)")
    result = generator.generate_signals_for_all_stocks(weeks_back=0)
    db.close()
    return result


if __name__ == '__main__':
    print("=== TEST GENERADOR DE SEÑALES ===\n")

    db = SessionLocal()
    generator = SignalGenerator(db)

    recent = generator.get_recent_signals(days=30)
    print(f"Señales de los últimos 30 días: {len(recent)}\n")

    for sig_type in ['BUY', 'SELL', 'STAGE_CHANGE']:
        sigs = generator.get_recent_signals(days=30, signal_type=sig_type)
        print(f"  {sig_type}: {len(sigs)} señales")

    db.close()
