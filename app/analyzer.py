"""
Analizador Weinstein - Detección de las 4 etapas del precio
Basado en la metodología de Stan Weinstein
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import Stock, WeeklyData, SessionLocal
from app.config import MA30_SLOPE_THRESHOLD, VOLUME_SPIKE_THRESHOLD

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeinsteinAnalyzer:
    """
    Analizador de etapas según metodología Weinstein
    
    Etapas:
    1 - Base/Consolidación
    2 - Tendencia Alcista
    3 - Techo/Distribución
    4 - Tendencia Bajista
    """
    
    def __init__(self, db: Session):
        self.db = db
        
        # Umbrales configurables
        self.ma30_slope_threshold = MA30_SLOPE_THRESHOLD  # 2% por defecto
        self.price_ma30_threshold = 0.05  # 5% de distancia de MA30 para considerar "cerca"
    
    def calculate_price_distance_from_ma30(self, close: float, ma30: float) -> Optional[float]:
        """
        Calcular distancia del precio respecto a MA30
        Positivo = precio por encima, Negativo = precio por debajo
        
        Returns:
            Distancia en porcentaje (0.05 = 5%)
        """
        if ma30 is None or ma30 == 0:
            return None
        
        return (close - ma30) / ma30
    
    def detect_stage(self, weekly_data: WeeklyData, previous_stage: Optional[int] = None) -> int:
        """
        Detectar etapa actual según criterios Weinstein
        
        Args:
            weekly_data: Datos de la semana a analizar
            previous_stage: Etapa de la semana anterior (para contexto)
        
        Returns:
            Número de etapa (1, 2, 3, 4)
        """
        close = float(weekly_data.close)
        ma30 = float(weekly_data.ma30) if weekly_data.ma30 else None
        slope = float(weekly_data.ma30_slope) if weekly_data.ma30_slope else None
        
        # Si no hay MA30, no podemos determinar etapa
        if ma30 is None:
            return previous_stage if previous_stage else 1
        
        # Calcular distancia del precio a MA30
        price_distance = self.calculate_price_distance_from_ma30(close, ma30)
        
        if price_distance is None:
            return previous_stage if previous_stage else 1
        
        # Determinar si el precio está sobre/bajo/cerca de MA30
        price_above_ma30 = price_distance > self.price_ma30_threshold
        price_below_ma30 = price_distance < -self.price_ma30_threshold
        price_near_ma30 = not price_above_ma30 and not price_below_ma30
        
        # Determinar tendencia de MA30
        if slope is None:
            slope_flat = True
            slope_up = False
            slope_down = False
        else:
            slope_flat = abs(slope) <= self.ma30_slope_threshold
            slope_up = slope > self.ma30_slope_threshold
            slope_down = slope < -self.ma30_slope_threshold
        
        # DETECCIÓN DE ETAPAS
        
        # Etapa 2: Tendencia Alcista
        # - Precio claramente sobre MA30
        # - MA30 con pendiente alcista
        if price_above_ma30 and slope_up:
            return 2
        
        # Etapa 4: Tendencia Bajista
        # - Precio claramente bajo MA30
        # - MA30 con pendiente bajista
        if price_below_ma30 and slope_down:
            return 4
        
        # Etapa 3: Techo/Distribución
        # - Precio cerca de MA30 o ligeramente arriba
        # - MA30 se aplana
        # - Viene después de Etapa 2 o ya estaba en Etapa 3
        if (price_near_ma30 or price_above_ma30) and slope_flat and previous_stage in [2, 3]:
            return 3

        # Etapa 1: Base/Consolidación
        # - Precio cerca de MA30 o ligeramente abajo
        # - MA30 plana o ligeramente bajista
        # - Viene después de Etapa 4, ya estaba en Etapa 1, o al inicio
        if (price_near_ma30 or price_below_ma30) and (slope_flat or slope_down):
            if previous_stage in [4, 1, None]:
                return 1
        
        # Casos ambiguos: mantener etapa anterior o defaultear
        if previous_stage:
            return previous_stage
        
        # Default: Etapa 1
        return 1
    
    def analyze_stock_stages(self, stock_id: int, weeks_back: int = 10) -> int:
        """
        Analizar etapas de una acción
        
        Args:
            stock_id: ID de la acción
            weeks_back: Número de semanas hacia atrás a analizar
        
        Returns:
            Número de semanas analizadas
        """
        # Obtener ticker para logs
        stock = self.db.query(Stock).filter(Stock.id == stock_id).first()
        ticker = stock.ticker if stock else f"ID:{stock_id}"
        
        # Obtener datos semanales ordenados cronológicamente
        weekly_data = self.db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock_id,
                WeeklyData.ma30.isnot(None)  # Solo semanas con MA30
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()
        
        if not weekly_data:
            logger.debug(f"{ticker}: Sin datos con MA30 para analizar")
            return 0

        # Limitar a las últimas N semanas si se especifica
        previous_stage = None
        if weeks_back > 0 and len(weekly_data) > weeks_back:
            # Obtener la etapa de la semana justo anterior al bloque para tener contexto
            previous_stage = weekly_data[-(weeks_back + 1)].stage
            weekly_data = weekly_data[-weeks_back:]

        processed = 0
        
        for week in weekly_data:
            # Detectar etapa
            current_stage = self.detect_stage(week, previous_stage)
            
            # Actualizar si cambió
            if week.stage != current_stage:
                week.stage = current_stage
                processed += 1
            
            previous_stage = current_stage
        
        # Commit cambios
        try:
            self.db.commit()
            if processed > 0:
                logger.info(f"✓ {ticker}: {processed} etapas actualizadas")
        except Exception as e:
            self.db.rollback()
            logger.error(f"✗ Error guardando etapas de {ticker}: {e}")
            return 0
        
        return processed
    
    def analyze_all_stocks(self, weeks_back: int = 10) -> dict:
        """
        Analizar etapas de todas las acciones activas
        
        Args:
            weeks_back: Número de semanas hacia atrás (0 = todas)
        
        Returns:
            Dict con estadísticas
        """
        stocks = self.db.query(Stock).filter(Stock.active == True).all()
        
        logger.info(f"Analizando etapas de {len(stocks)} acciones")
        
        total = len(stocks)
        success = 0
        failed = []
        
        for stock in stocks:
            try:
                processed = self.analyze_stock_stages(stock.id, weeks_back)
                if processed >= 0:  # >= 0 porque puede no haber cambios
                    success += 1
            except Exception as e:
                logger.error(f"✗ Error analizando {stock.ticker}: {e}")
                failed.append(stock.ticker)
        
        return {
            'total': total,
            'success': success,
            'failed': len(failed),
            'failed_tickers': failed
        }
    
    def get_stock_stage_summary(self, stock_id: int, weeks: int = 10) -> dict:
        """
        Obtener resumen de etapas de una acción
        
        Args:
            stock_id: ID de la acción
            weeks: Número de semanas a incluir
        
        Returns:
            Dict con resumen
        """
        stock = self.db.query(Stock).filter(Stock.id == stock_id).first()
        
        # Últimas N semanas
        weekly_data = self.db.query(WeeklyData).filter(
            WeeklyData.stock_id == stock_id
        ).order_by(WeeklyData.week_end_date.desc()).limit(weeks).all()
        
        if not weekly_data:
            return {
                'ticker': stock.ticker if stock else None,
                'current_stage': None,
                'weeks_in_current_stage': 0,
                'stage_history': []
            }
        
        # Etapa actual
        current_stage = weekly_data[0].stage
        
        # Contar semanas en etapa actual
        weeks_in_stage = 0
        for week in weekly_data:
            if week.stage == current_stage:
                weeks_in_stage += 1
            else:
                break
        
        # Historial de etapas
        stage_history = []
        for week in reversed(weekly_data):
            stage_history.append({
                'week_end_date': week.week_end_date,
                'stage': week.stage,
                'close': float(week.close),
                'ma30': float(week.ma30) if week.ma30 else None,
                'slope': float(week.ma30_slope) if week.ma30_slope else None
            })
        
        return {
            'ticker': stock.ticker if stock else None,
            'current_stage': current_stage,
            'weeks_in_current_stage': weeks_in_stage,
            'stage_history': stage_history
        }
    
    def get_stocks_by_stage(self, stage: int) -> List[dict]:
        """
        Obtener acciones que están en una etapa específica
        
        Args:
            stage: Número de etapa (1, 2, 3, 4)
        
        Returns:
            Lista de dicts con info de las acciones
        """
        # Subconsulta para obtener la semana más reciente de cada acción
        subq = self.db.query(
            WeeklyData.stock_id,
            func.max(WeeklyData.week_end_date).label('max_date')
        ).group_by(WeeklyData.stock_id).subquery()
        
        # Obtener acciones en la etapa solicitada
        results = self.db.query(Stock, WeeklyData).join(
            WeeklyData, Stock.id == WeeklyData.stock_id
        ).join(
            subq,
            and_(
                WeeklyData.stock_id == subq.c.stock_id,
                WeeklyData.week_end_date == subq.c.max_date
            )
        ).filter(
            WeeklyData.stage == stage
        ).all()
        
        stocks = []
        for stock, weekly in results:
            stocks.append({
                'ticker': stock.ticker,
                'name': stock.name,
                'stage': weekly.stage,
                'week_end_date': weekly.week_end_date,
                'close': float(weekly.close),
                'ma30': float(weekly.ma30) if weekly.ma30 else None,
                'slope': float(weekly.ma30_slope) if weekly.ma30_slope else None
            })
        
        return stocks


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def analyze_all_stages_initial() -> dict:
    """
    Analizar TODAS las etapas de todas las acciones
    Usar solo en análisis inicial
    
    Returns:
        Dict con estadísticas
    """
    db = SessionLocal()
    analyzer = WeinsteinAnalyzer(db)
    
    logger.info("Analizando todas las etapas (histórico completo)")
    
    result = analyzer.analyze_all_stocks(weeks_back=0)  # 0 = todas las semanas
    
    db.close()
    
    return result


if __name__ == '__main__':
    # Script de prueba
    print("=== TEST ANALIZADOR WEINSTEIN ===\n")
    
    db = SessionLocal()
    analyzer = WeinsteinAnalyzer(db)
    
    # Obtener primera acción con datos
    stock = db.query(Stock).first()
    
    if stock:
        print(f"Probando con {stock.ticker}...\n")
        
        # Analizar últimas 10 semanas
        processed = analyzer.analyze_stock_stages(stock.id, weeks_back=10)
        print(f"Semanas procesadas: {processed}\n")
        
        # Ver resumen
        summary = analyzer.get_stock_stage_summary(stock.id, weeks=10)
        print(f"Etapa actual: {summary['current_stage']}")
        print(f"Semanas en esta etapa: {summary['weeks_in_current_stage']}\n")
        
        print("Últimas 5 semanas:")
        for entry in summary['stage_history'][-5:]:
            print(f"  {entry['week_end_date']}: Etapa {entry['stage']}, "
                  f"Close={entry['close']:.2f}, MA30={entry['ma30']:.2f if entry['ma30'] else 'N/A'}")
    
    # Ver distribución de etapas
    print("\n" + "="*50)
    print("Distribución de acciones por etapa:\n")
    for stage in [1, 2, 3, 4]:
        stocks_in_stage = analyzer.get_stocks_by_stage(stage)
        print(f"Etapa {stage}: {len(stocks_in_stage)} acciones")
    
    db.close()
