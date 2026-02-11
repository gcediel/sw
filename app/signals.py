"""
Generador de señales de trading
Detecta cambios de etapa y genera señales BUY/SELL
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import Stock, WeeklyData, Signal, SessionLocal

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generador de señales de trading basado en cambios de etapa"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_stage_change(self, stock_id: int, current_week: WeeklyData, previous_week: WeeklyData) -> Optional[dict]:
        """
        Detectar cambio de etapa entre dos semanas consecutivas
        
        Args:
            stock_id: ID de la acción
            current_week: Semana actual
            previous_week: Semana anterior
        
        Returns:
            Dict con info del cambio o None si no hay cambio
        """
        if previous_week.stage is None or current_week.stage is None:
            return None
        
        if previous_week.stage == current_week.stage:
            return None  # No hay cambio
        
        return {
            'stock_id': stock_id,
            'week_end_date': current_week.week_end_date,
            'stage_from': previous_week.stage,
            'stage_to': current_week.stage,
            'price': float(current_week.close),
            'ma30': float(current_week.ma30) if current_week.ma30 else None
        }
    
    def classify_signal(self, stage_from: int, stage_to: int) -> str:
        """
        Clasificar el tipo de señal según el cambio de etapa
        
        Señales importantes:
        - BUY: Etapa 1 → 2 (ruptura alcista)
        - SELL: Etapa 2/3 → 4 (ruptura bajista)
        - STAGE_CHANGE: Otros cambios
        
        Args:
            stage_from: Etapa origen
            stage_to: Etapa destino
        
        Returns:
            Tipo de señal ('BUY', 'SELL', 'STAGE_CHANGE')
        """
        # Señal de COMPRA: Etapa 1 → 2
        if stage_from == 1 and stage_to == 2:
            return 'BUY'
        
        # Señal de VENTA: Etapa 2 → 4
        if stage_from == 2 and stage_to == 4:
            return 'SELL'
        
        # Señal de VENTA: Etapa 3 → 4
        if stage_from == 3 and stage_to == 4:
            return 'SELL'
        
        # Otros cambios
        return 'STAGE_CHANGE'
    
    def create_signal(self, change_info: dict) -> bool:
        """
        Crear señal en la base de datos
        
        Args:
            change_info: Diccionario con información del cambio
        
        Returns:
            True si se creó la señal
        """
        signal_type = self.classify_signal(change_info['stage_from'], change_info['stage_to'])
        
        # Verificar si ya existe la señal
        existing = self.db.query(Signal).filter(
            and_(
                Signal.stock_id == change_info['stock_id'],
                Signal.signal_date == change_info['week_end_date'],
                Signal.signal_type == signal_type
            )
        ).first()
        
        if existing:
            logger.debug(f"Señal ya existe: {signal_type} para stock_id {change_info['stock_id']}")
            return False
        
        # Crear nueva señal
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
    
    def generate_signals_for_stock(self, stock_id: int, weeks_back: int = 10) -> int:
        """
        Generar señales para una acción
        
        Args:
            stock_id: ID de la acción
            weeks_back: Número de semanas hacia atrás a revisar
        
        Returns:
            Número de señales generadas
        """
        # Obtener ticker para logs
        stock = self.db.query(Stock).filter(Stock.id == stock_id).first()
        ticker = stock.ticker if stock else f"ID:{stock_id}"
        
        # Obtener datos semanales ordenados cronológicamente
        weekly_data = self.db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock_id,
                WeeklyData.stage.isnot(None)
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()
        
        if len(weekly_data) < 2:
            logger.debug(f"{ticker}: Insuficientes datos para generar señales")
            return 0
        
        # Limitar a las últimas N semanas si se especifica
        if weeks_back > 0:
            weekly_data = weekly_data[-weeks_back:]
        
        signals_created = 0
        
        # Comparar semanas consecutivas
        for i in range(1, len(weekly_data)):
            previous_week = weekly_data[i - 1]
            current_week = weekly_data[i]
            
            # Detectar cambio de etapa
            change = self.detect_stage_change(stock_id, current_week, previous_week)
            
            if change:
                # Crear señal
                if self.create_signal(change):
                    signal_type = self.classify_signal(change['stage_from'], change['stage_to'])
                    logger.info(f"✓ {ticker}: {signal_type} señal generada (Etapa {change['stage_from']} → {change['stage_to']})")
                    signals_created += 1
        
        # Commit cambios
        try:
            if signals_created > 0:
                self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"✗ Error guardando señales de {ticker}: {e}")
            return 0
        
        return signals_created
    
    def generate_signals_for_all_stocks(self, weeks_back: int = 10) -> dict:
        """
        Generar señales para todas las acciones activas
        
        Args:
            weeks_back: Número de semanas hacia atrás (0 = todas)
        
        Returns:
            Dict con estadísticas
        """
        stocks = self.db.query(Stock).filter(Stock.active == True).all()
        
        logger.info(f"Generando señales para {len(stocks)} acciones")
        
        total = len(stocks)
        stocks_with_signals = 0
        total_signals = 0
        failed = []
        
        for stock in stocks:
            try:
                signals = self.generate_signals_for_stock(stock.id, weeks_back)
                total_signals += signals
                if signals > 0:
                    stocks_with_signals += 1
            except Exception as e:
                logger.error(f"✗ Error generando señales para {stock.ticker}: {e}")
                failed.append(stock.ticker)
        
        return {
            'total_stocks': total,
            'stocks_with_signals': stocks_with_signals,
            'total_signals': total_signals,
            'failed': len(failed),
            'failed_tickers': failed
        }
    
    def get_recent_signals(self, days: int = 7, signal_type: Optional[str] = None) -> List[dict]:
        """
        Obtener señales recientes
        
        Args:
            days: Días hacia atrás
            signal_type: Filtrar por tipo ('BUY', 'SELL', 'STAGE_CHANGE') o None para todos
        
        Returns:
            Lista de señales
        """
        from datetime import timedelta
        cutoff_date = datetime.now().date() - timedelta(days=days)
        
        query = self.db.query(Signal, Stock).join(
            Stock, Signal.stock_id == Stock.id
        ).filter(
            Signal.signal_date >= cutoff_date
        )
        
        if signal_type:
            query = query.filter(Signal.signal_type == signal_type)
        
        query = query.order_by(Signal.signal_date.desc())
        
        results = []
        for signal, stock in query.all():
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
    
    def get_unnotified_signals(self) -> List[dict]:
        """
        Obtener señales que aún no han sido notificadas
        
        Returns:
            Lista de señales pendientes de notificar
        """
        results = self.db.query(Signal, Stock).join(
            Stock, Signal.stock_id == Stock.id
        ).filter(
            Signal.notified == False
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
                'ma30': float(signal.ma30) if signal.ma30 else None
            })
        
        return signals
    
    def mark_signals_as_notified(self, signal_ids: List[int]) -> int:
        """
        Marcar señales como notificadas
        
        Args:
            signal_ids: Lista de IDs de señales
        
        Returns:
            Número de señales actualizadas
        """
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
    Generar TODAS las señales de todas las acciones
    Usar solo en generación inicial
    
    Returns:
        Dict con estadísticas
    """
    db = SessionLocal()
    generator = SignalGenerator(db)
    
    logger.info("Generando todas las señales (histórico completo)")
    
    result = generator.generate_signals_for_all_stocks(weeks_back=0)  # 0 = todas
    
    db.close()
    
    return result


if __name__ == '__main__':
    # Script de prueba
    print("=== TEST GENERADOR DE SEÑALES ===\n")
    
    db = SessionLocal()
    generator = SignalGenerator(db)
    
    # Generar señales para primera acción
    stock = db.query(Stock).first()
    
    if stock:
        print(f"Generando señales para {stock.ticker}...\n")
        
        signals = generator.generate_signals_for_stock(stock.id, weeks_back=20)
        print(f"Señales generadas: {signals}\n")
    
    # Ver señales recientes
    recent = generator.get_recent_signals(days=30)
    print(f"Señales de los últimos 30 días: {len(recent)}\n")
    
    if recent:
        print("Últimas 5 señales:")
        for sig in recent[:5]:
            print(f"  {sig['signal_date']}: {sig['ticker']} - {sig['signal_type']} "
                  f"(Etapa {sig['stage_from']} → {sig['stage_to']})")
    
    # Ver señales por tipo
    print("\n" + "="*50)
    print("Señales por tipo (últimos 30 días):\n")
    for sig_type in ['BUY', 'SELL', 'STAGE_CHANGE']:
        signals = generator.get_recent_signals(days=30, signal_type=sig_type)
        print(f"{sig_type}: {len(signals)} señales")
    
    db.close()
