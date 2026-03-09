#!/usr/bin/env python3
"""
Script de procesamiento semanal
Ejecutar cada domingo/lunes para:
- Agregar datos de la semana anterior
- Analizar etapas Weinstein
- Generar señales BUY/SELL

Uso:
    python scripts/weekly_process.py
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from app.database import SessionLocal
from app.aggregator import WeeklyAggregator
from app.analyzer import WeinsteinAnalyzer
from app.signals import SignalGenerator
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/weekly_process.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Función principal de procesamiento semanal"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"PROCESAMIENTO SEMANAL - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # ==========================================
        # FASE 1: AGREGACIÓN SEMANAL
        # ==========================================
        logger.info("\nFASE 1: Agregación de datos semanales...")
        aggregator = WeeklyAggregator(db)
        
        # Agregar últimas 4 semanas (para asegurar que la última está completa)
        result_agg = aggregator.aggregate_all_stocks(weeks_back=4)
        
        logger.info(f"✓ Agregación: {result_agg['success']}/{result_agg['total']} acciones procesadas")
        
        # ==========================================
        # FASE 2: ANÁLISIS DE ETAPAS
        # ==========================================
        logger.info("\nFASE 2: Análisis de etapas Weinstein...")
        analyzer = WeinsteinAnalyzer(db)
        
        # Analizar últimas 10 semanas (suficiente para detectar cambios recientes)
        result_analysis = analyzer.analyze_all_stocks(weeks_back=10)
        
        logger.info(f"✓ Análisis: {result_analysis['success']}/{result_analysis['total']} acciones procesadas")
        
        # ==========================================
        # FASE 3: GENERACIÓN DE SEÑALES
        # ==========================================
        logger.info("\nFASE 3: Generación de señales...")
        generator = SignalGenerator(db)
        
        # Generar señales únicamente para el último viernes
        result_signals = generator.generate_signals_for_all_stocks(weeks_back=1)
        
        logger.info(f"✓ Señales: {result_signals['total_signals']} señales generadas para {result_signals['stocks_with_signals']} acciones")
        
        # Ver señales recientes
        recent_signals = generator.get_recent_signals(days=7)
        if recent_signals:
            logger.info(f"\n📊 Señales de los últimos 7 días: {len(recent_signals)}")
            for sig in recent_signals[:5]:  # Mostrar máximo 5
                logger.info(f"  - {sig['ticker']}: {sig['signal_type']} (Etapa {sig['stage_from']} → {sig['stage_to']})")
        
        # ==========================================
        # RESUMEN FINAL
        # ==========================================
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN PROCESAMIENTO SEMANAL")
        logger.info("=" * 60)
        logger.info(f"Agregación:")
        logger.info(f"  Exitosas:          {result_agg['success']} ({result_agg['success']/result_agg['total']*100:.1f}%)")
        logger.info(f"  Con errores:       {result_agg['failed']}")
        
        logger.info(f"\nAnálisis de etapas:")
        logger.info(f"  Exitosas:          {result_analysis['success']} ({result_analysis['success']/result_analysis['total']*100:.1f}%)")
        logger.info(f"  Con errores:       {result_analysis['failed']}")
        
        logger.info(f"\nGeneración de señales:")
        logger.info(f"  Acciones:          {result_signals['stocks_with_signals']}")
        logger.info(f"  Total señales:     {result_signals['total_signals']}")
        logger.info(f"  Con errores:       {result_signals['failed']}")
        
        logger.info(f"\nDuración:          {duration:.0f} segundos")
        
        # Advertencias de errores
        all_failed = list(set(
            result_agg.get('failed_tickers', []) + 
            result_analysis.get('failed_tickers', []) + 
            result_signals.get('failed_tickers', [])
        ))
        
        if all_failed:
            logger.warning(f"\n⚠ Acciones con errores ({len(all_failed)}):")
            for ticker in all_failed:
                logger.warning(f"  - {ticker}")
        
        logger.info("=" * 60)
        logger.info("PROCESAMIENTO SEMANAL COMPLETADO")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Error crítico en procesamiento semanal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()
    
    sys.exit(0)


if __name__ == '__main__':
    main()
