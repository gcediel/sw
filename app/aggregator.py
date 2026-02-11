"""
Agregador de datos semanales
Convierte datos diarios en velas semanales y calcula MA30
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import Stock, DailyData, WeeklyData, SessionLocal
from app.config import MIN_WEEKS_FOR_ANALYSIS

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeeklyAggregator:
    """Agregador de datos diarios a semanales con cálculo de MA30"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_week_end_date(self, date) -> datetime:
        """
        Obtener la fecha de fin de semana (viernes)
        Si la fecha es sábado/domingo, retorna el viernes anterior
        
        Args:
            date: Fecha a procesar
        
        Returns:
            Fecha del viernes de esa semana
        """
        # Convertir a datetime si es necesario
        if isinstance(date, str):
            date = pd.to_datetime(date).date()
        elif hasattr(date, 'date'):
            date = date.date()
        
        # 0 = lunes, 4 = viernes, 5 = sábado, 6 = domingo
        weekday = date.weekday()
        
        if weekday == 4:  # Viernes
            return date
        elif weekday == 5:  # Sábado
            return date - timedelta(days=1)
        elif weekday == 6:  # Domingo
            return date - timedelta(days=2)
        else:  # Lunes a jueves
            return date + timedelta(days=(4 - weekday))
    
    def aggregate_week(self, stock_id: int, week_end_date: datetime) -> Optional[dict]:
        """
        Agregar datos de una semana específica
        
        Args:
            stock_id: ID de la acción
            week_end_date: Fecha de fin de semana (viernes)
        
        Returns:
            Dict con OHLCV semanal o None si no hay datos
        """
        # Calcular inicio de semana (lunes)
        week_start_date = week_end_date - timedelta(days=4)
        
        # Obtener datos diarios de esa semana
        daily_data = self.db.query(DailyData).filter(
            and_(
                DailyData.stock_id == stock_id,
                DailyData.date >= week_start_date,
                DailyData.date <= week_end_date
            )
        ).order_by(DailyData.date.asc()).all()
        
        if not daily_data:
            return None
        
        # Agregar OHLCV
        weekly_open = daily_data[0].open  # Apertura del primer día
        weekly_high = max([d.high for d in daily_data])  # Máximo de la semana
        weekly_low = min([d.low for d in daily_data])  # Mínimo de la semana
        weekly_close = daily_data[-1].close  # Cierre del último día
        weekly_volume = sum([d.volume for d in daily_data])  # Volumen acumulado
        
        return {
            'open': weekly_open,
            'high': weekly_high,
            'low': weekly_low,
            'close': weekly_close,
            'volume': weekly_volume
        }
    
    def calculate_ma30(self, stock_id: int, current_week_end: datetime, periods: int = 30) -> Optional[float]:
        """
        Calcular media móvil de N semanas
        
        Args:
            stock_id: ID de la acción
            current_week_end: Fecha de fin de la semana actual
            periods: Número de períodos (default: 30)
        
        Returns:
            MA30 o None si no hay suficientes datos
        """
        # Obtener las últimas N semanas (incluyendo la actual)
        weekly_data = self.db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock_id,
                WeeklyData.week_end_date <= current_week_end
            )
        ).order_by(WeeklyData.week_end_date.desc()).limit(periods).all()
        
        if len(weekly_data) < periods:
            return None
        
        # Calcular media de los cierres
        closes = [w.close for w in weekly_data]
        ma = sum(closes) / len(closes)
        
        return float(ma)
    
    def calculate_ma30_slope(self, stock_id: int, current_week_end: datetime) -> Optional[float]:
        """
        Calcular pendiente de MA30
        Pendiente = (MA30_actual - MA30_anterior) / MA30_anterior
        
        Args:
            stock_id: ID de la acción
            current_week_end: Fecha de fin de semana actual
        
        Returns:
            Pendiente (decimal) o None
        """
        # Obtener semana actual
        current_week = self.db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock_id,
                WeeklyData.week_end_date == current_week_end
            )
        ).first()
        
        if not current_week or current_week.ma30 is None:
            return None
        
        # Obtener semana anterior
        previous_week = self.db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock_id,
                WeeklyData.week_end_date < current_week_end
            )
        ).order_by(WeeklyData.week_end_date.desc()).first()
        
        if not previous_week or previous_week.ma30 is None:
            return None
        
        # Calcular pendiente
        ma30_current = float(current_week.ma30)
        ma30_previous = float(previous_week.ma30)
        
        if ma30_previous == 0:
            return None
        
        slope = (ma30_current - ma30_previous) / ma30_previous
        
        return float(slope)
    
    def aggregate_stock_weekly_data(self, stock_id: int, weeks_back: int = 4) -> int:
        """
        Agregar datos semanales de una acción
        
        Args:
            stock_id: ID de la acción
            weeks_back: Número de semanas hacia atrás a procesar (default: 4)
        
        Returns:
            Número de semanas procesadas
        """
        # Obtener fecha de fin de la última semana completa
        today = datetime.now().date()
        last_week_end = self.get_week_end_date(today - timedelta(days=7))
        
        # Obtener ticker para logs
        stock = self.db.query(Stock).filter(Stock.id == stock_id).first()
        ticker = stock.ticker if stock else f"ID:{stock_id}"
        
        logger.info(f"Agregando datos semanales de {ticker} (últimas {weeks_back} semanas)")
        
        processed = 0
        
        # Procesar las últimas N semanas
        for i in range(weeks_back):
            week_end_date = last_week_end - timedelta(days=7 * i)
            
            # Agregar datos de la semana
            weekly_ohlcv = self.aggregate_week(stock_id, week_end_date)
            
            if not weekly_ohlcv:
                logger.debug(f"  {ticker}: Sin datos para semana {week_end_date}")
                continue
            
            # Verificar si ya existe el registro
            existing = self.db.query(WeeklyData).filter(
                and_(
                    WeeklyData.stock_id == stock_id,
                    WeeklyData.week_end_date == week_end_date
                )
            ).first()
            
            if existing:
                # Actualizar
                existing.open = weekly_ohlcv['open']
                existing.high = weekly_ohlcv['high']
                existing.low = weekly_ohlcv['low']
                existing.close = weekly_ohlcv['close']
                existing.volume = weekly_ohlcv['volume']
            else:
                # Crear nuevo
                weekly = WeeklyData(
                    stock_id=stock_id,
                    week_end_date=week_end_date,
                    open=weekly_ohlcv['open'],
                    high=weekly_ohlcv['high'],
                    low=weekly_ohlcv['low'],
                    close=weekly_ohlcv['close'],
                    volume=weekly_ohlcv['volume']
                )
                self.db.add(weekly)
            
            processed += 1
        
        # Commit de OHLCV
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"✗ Error guardando datos semanales de {ticker}: {e}")
            return 0
        
        # Calcular MA30 para las semanas procesadas
        for i in range(weeks_back):
            week_end_date = last_week_end - timedelta(days=7 * i)
            
            # Calcular MA30
            ma30 = self.calculate_ma30(stock_id, week_end_date)
            
            # Actualizar registro
            weekly = self.db.query(WeeklyData).filter(
                and_(
                    WeeklyData.stock_id == stock_id,
                    WeeklyData.week_end_date == week_end_date
                )
            ).first()
            
            if weekly:
                weekly.ma30 = ma30
        
        # Commit de MA30
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"✗ Error guardando MA30 de {ticker}: {e}")
        
        # Calcular pendiente MA30 para las semanas procesadas
        for i in range(weeks_back):
            week_end_date = last_week_end - timedelta(days=7 * i)
            
            slope = self.calculate_ma30_slope(stock_id, week_end_date)
            
            # Actualizar registro
            weekly = self.db.query(WeeklyData).filter(
                and_(
                    WeeklyData.stock_id == stock_id,
                    WeeklyData.week_end_date == week_end_date
                )
            ).first()
            
            if weekly:
                weekly.ma30_slope = slope
        
        # Commit de pendiente
        try:
            self.db.commit()
            logger.info(f"✓ {ticker}: {processed} semanas procesadas")
        except Exception as e:
            self.db.rollback()
            logger.error(f"✗ Error guardando pendiente de {ticker}: {e}")
        
        return processed
    
    def aggregate_all_stocks(self, weeks_back: int = 4) -> dict:
        """
        Agregar datos semanales de todas las acciones activas
        
        Args:
            weeks_back: Número de semanas hacia atrás
        
        Returns:
            Dict con estadísticas de la agregación
        """
        # Obtener todas las acciones activas
        stocks = self.db.query(Stock).filter(Stock.active == True).all()
        
        logger.info(f"Iniciando agregación semanal de {len(stocks)} acciones")
        
        total = len(stocks)
        success = 0
        failed = []
        
        for stock in stocks:
            try:
                processed = self.aggregate_stock_weekly_data(stock.id, weeks_back)
                if processed > 0:
                    success += 1
                else:
                    failed.append(stock.ticker)
            except Exception as e:
                logger.error(f"✗ Error procesando {stock.ticker}: {e}")
                failed.append(stock.ticker)
        
        return {
            'total': total,
            'success': success,
            'failed': len(failed),
            'failed_tickers': failed
        }
    
    def get_stock_weekly_stats(self, stock_id: int) -> dict:
        """
        Obtener estadísticas de datos semanales de una acción
        
        Args:
            stock_id: ID de la acción
        
        Returns:
            Dict con estadísticas
        """
        total_weeks = self.db.query(WeeklyData).filter(
            WeeklyData.stock_id == stock_id
        ).count()
        
        weeks_with_ma30 = self.db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock_id,
                WeeklyData.ma30.isnot(None)
            )
        ).count()
        
        stock = self.db.query(Stock).filter(Stock.id == stock_id).first()
        
        return {
            'ticker': stock.ticker if stock else None,
            'total_weeks': total_weeks,
            'weeks_with_ma30': weeks_with_ma30,
            'ready_for_analysis': weeks_with_ma30 >= MIN_WEEKS_FOR_ANALYSIS
        }


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def aggregate_initial_historical(years: int = 2) -> dict:
    """
    Agregar TODO el histórico de todas las acciones
    Usar solo una vez tras la carga inicial
    
    Args:
        years: Años de histórico (default: 2)
    
    Returns:
        Dict con estadísticas
    """
    db = SessionLocal()
    aggregator = WeeklyAggregator(db)
    
    # Calcular número de semanas
    weeks = years * 52
    
    logger.info(f"Agregando {weeks} semanas de histórico para todas las acciones")
    
    result = aggregator.aggregate_all_stocks(weeks_back=weeks)
    
    db.close()
    
    return result


if __name__ == '__main__':
    # Script de prueba
    print("=== TEST AGREGADOR SEMANAL ===\n")
    
    db = SessionLocal()
    aggregator = WeeklyAggregator(db)
    
    # Obtener primera acción
    stock = db.query(Stock).first()
    
    if stock:
        print(f"Probando con {stock.ticker}...\n")
        
        # Agregar últimas 10 semanas
        processed = aggregator.aggregate_stock_weekly_data(stock.id, weeks_back=10)
        print(f"Semanas procesadas: {processed}\n")
        
        # Ver estadísticas
        stats = aggregator.get_stock_weekly_stats(stock.id)
        print("Estadísticas:")
        print(f"  Total semanas: {stats['total_weeks']}")
        print(f"  Semanas con MA30: {stats['weeks_with_ma30']}")
        print(f"  Listo para análisis: {stats['ready_for_analysis']}")
        
        # Mostrar últimas 5 semanas
        weekly_data = db.query(WeeklyData).filter(
            WeeklyData.stock_id == stock.id
        ).order_by(WeeklyData.week_end_date.desc()).limit(5).all()
        
        print(f"\nÚltimas 5 semanas:")
        for w in weekly_data:
            print(f"  {w.week_end_date}: Close={w.close:.2f}, MA30={w.ma30:.2f if w.ma30 else 'N/A'}, Slope={w.ma30_slope:.4f if w.ma30_slope else 'N/A'}")
    
    db.close()
