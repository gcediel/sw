#!/usr/bin/env python3
"""
Script para análisis inicial completo
Ejecutar UNA SOLA VEZ después de la agregación inicial

Analiza:
- Todas las etapas de todas las acciones (histórico completo)
- Genera todas las señales históricas

Uso:
    python scripts/analyze_initial.py
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from app.database import SessionLocal, Stock, WeeklyData, Signal
from app.analyzer import WeinsteinAnalyzer
from app.signals import SignalGenerator
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/analyze_initial.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Análisis inicial completo"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info("ANÁLISIS INICIAL WEINSTEIN - HISTÓRICO COMPLETO")
    logger.info("=" * 60)
    logger.info(f"Fecha/Hora: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Obtener todas las acciones
        stocks = db.query(Stock).filter(Stock.active == True).all()
        total = len(stocks)
        
        logger.info(f"\n📊 Procesando {total} acciones...\n")
        
        # ==========================================
        # FASE 1: ANÁLISIS DE ETAPAS
        # ==========================================
        logger.info("=" * 60)
        logger.info("FASE 1: ANÁLISIS DE ETAPAS")
        logger.info("=" * 60)
        
        analyzer = WeinsteinAnalyzer(db)
        
        success_analysis = 0
        failed_analysis = []
        
        for idx, stock in enumerate(stocks, 1):
            logger.info(f"[{idx}/{total}] Analizando etapas de {stock.ticker}...")
            
            try:
                # Analizar todas las semanas (weeks_back=0)
                processed = analyzer.analyze_stock_stages(stock.id, weeks_back=0)
                
                if processed >= 0:
                    success_analysis += 1
                    
                    # Mostrar resumen
                    summary = analyzer.get_stock_stage_summary(stock.id, weeks=5)
                    logger.info(f"  ✓ {stock.ticker}: Etapa actual: {summary['current_stage']}, "
                              f"{summary['weeks_in_current_stage']} semanas en esta etapa")
                else:
                    failed_analysis.append(stock.ticker)
                    logger.warning(f"  ⚠ {stock.ticker}: Sin datos para analizar")
                    
            except Exception as e:
                logger.error(f"  ✗ Error analizando {stock.ticker}: {e}")
                failed_analysis.append(stock.ticker)
        
        # ==========================================
        # FASE 2: GENERACIÓN DE SEÑALES
        # ==========================================
        logger.info("\n" + "=" * 60)
        logger.info("FASE 2: GENERACIÓN DE SEÑALES")
        logger.info("=" * 60)
        
        generator = SignalGenerator(db)
        
        success_signals = 0
        total_signals = 0
        failed_signals = []
        
        for idx, stock in enumerate(stocks, 1):
            logger.info(f"[{idx}/{total}] Generando señales de {stock.ticker}...")
            
            try:
                # Generar todas las señales (weeks_back=0)
                signals = generator.generate_signals_for_stock(stock.id, weeks_back=0)
                
                total_signals += signals
                
                if signals > 0:
                    success_signals += 1
                    logger.info(f"  ✓ {stock.ticker}: {signals} señales generadas")
                else:
                    logger.debug(f"  - {stock.ticker}: Sin cambios de etapa")
                    
            except Exception as e:
                logger.error(f"  ✗ Error generando señales para {stock.ticker}: {e}")
                failed_signals.append(stock.ticker)
        
        # ==========================================
        # RESUMEN FINAL
        # ==========================================
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN ANÁLISIS INICIAL")
        logger.info("=" * 60)
        
        logger.info("\nFASE 1 - Análisis de Etapas:")
        logger.info(f"  Total procesadas:  {total}")
        logger.info(f"  Exitosas:          {success_analysis} ({success_analysis/total*100:.1f}%)")
        logger.info(f"  Fallidas:          {len(failed_analysis)} ({len(failed_analysis)/total*100:.1f}%)")
        
        logger.info("\nFASE 2 - Generación de Señales:")
        logger.info(f"  Acciones con señales:  {success_signals}")
        logger.info(f"  Total señales:         {total_signals}")
        logger.info(f"  Fallidas:              {len(failed_signals)}")
        
        logger.info(f"\nDuración total:      {duration:.0f} segundos ({duration/60:.1f} minutos)")
        
        if failed_analysis or failed_signals:
            logger.warning("\n⚠ Acciones con errores:")
            for ticker in set(failed_analysis + failed_signals):
                logger.warning(f"  - {ticker}")
        
        # Estadísticas de BD
        total_weeks = db.query(WeeklyData).count()
        weeks_with_stage = db.query(WeeklyData).filter(WeeklyData.stage.isnot(None)).count()
        total_signals_db = db.query(Signal).count()
        
        logger.info("\n📊 Estadísticas finales:")
        logger.info(f"  Total semanas en BD:      {total_weeks}")
        logger.info(f"  Semanas con etapa:        {weeks_with_stage}")
        logger.info(f"  Total señales en BD:      {total_signals_db}")
        
        # Distribución de etapas
        logger.info("\n📈 Distribución de acciones por etapa actual:")
        for stage in [1, 2, 3, 4]:
            stocks_in_stage = analyzer.get_stocks_by_stage(stage)
            logger.info(f"  Etapa {stage}: {len(stocks_in_stage)} acciones")
        
        # Distribución de señales
        logger.info("\n🔔 Distribución de señales:")
        buy_signals = db.query(Signal).filter(Signal.signal_type == 'BUY').count()
        sell_signals = db.query(Signal).filter(Signal.signal_type == 'SELL').count()
        stage_change_signals = db.query(Signal).filter(Signal.signal_type == 'STAGE_CHANGE').count()
        
        logger.info(f"  BUY:          {buy_signals}")
        logger.info(f"  SELL:         {sell_signals}")
        logger.info(f"  STAGE_CHANGE: {stage_change_signals}")
        
        logger.info("=" * 60)
        logger.info("ANÁLISIS INICIAL COMPLETADO")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Error crítico: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()
    
    sys.exit(0)


if __name__ == '__main__':
    main()
