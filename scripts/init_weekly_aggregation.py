#!/usr/bin/env python3
"""
Script para agregación inicial de histórico completo
Ejecutar UNA SOLA VEZ después de la carga histórica inicial

Uso:
    python scripts/init_weekly_aggregation.py
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from app.database import SessionLocal, Stock, WeeklyData
from app.aggregator import WeeklyAggregator
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/weekly_init.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Agregación inicial de TODO el histórico"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info("AGREGACIÓN INICIAL DE HISTÓRICO COMPLETO")
    logger.info("=" * 60)
    logger.info(f"Fecha/Hora: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    aggregator = WeeklyAggregator(db)
    
    try:
        # Obtener todas las acciones
        stocks = db.query(Stock).filter(Stock.active == True).all()
        total = len(stocks)
        
        logger.info(f"\n📊 Procesando {total} acciones...")
        logger.info("⏳ Esto puede tardar varios minutos...\n")
        
        success = 0
        failed = []
        
        # Procesar cada acción (2 años = ~104 semanas)
        for idx, stock in enumerate(stocks, 1):
            logger.info(f"[{idx}/{total}] Procesando {stock.ticker}...")
            
            try:
                # Agregar 2 años de datos semanales
                processed = aggregator.aggregate_stock_weekly_data(stock.id, weeks_back=104)
                
                if processed > 0:
                    success += 1
                    
                    # Mostrar estadísticas
                    stats = aggregator.get_stock_weekly_stats(stock.id)
                    logger.info(f"  ✓ {stock.ticker}: {stats['total_weeks']} semanas, "
                              f"{stats['weeks_with_ma30']} con MA30, "
                              f"Análisis: {'✓' if stats['ready_for_analysis'] else '✗'}")
                else:
                    failed.append(stock.ticker)
                    logger.warning(f"  ⚠ {stock.ticker}: Sin datos para procesar")
                    
            except Exception as e:
                logger.error(f"  ✗ Error procesando {stock.ticker}: {e}")
                failed.append(stock.ticker)
        
        # Resumen final
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN AGREGACIÓN INICIAL")
        logger.info("=" * 60)
        logger.info(f"Total procesadas:  {total}")
        logger.info(f"Exitosas:          {success} ({success/total*100:.1f}%)")
        logger.info(f"Fallidas:          {len(failed)} ({len(failed)/total*100:.1f}%)")
        logger.info(f"Duración:          {duration:.0f} segundos ({duration/60:.1f} minutos)")
        
        if failed:
            logger.warning(f"\n⚠ Acciones fallidas ({len(failed)}):")
            for ticker in failed:
                logger.warning(f"  - {ticker}")
        
        # Estadísticas finales de la base de datos
        total_weeks = db.query(WeeklyData).count()
        weeks_with_ma30 = db.query(WeeklyData).filter(WeeklyData.ma30.isnot(None)).count()
        
        logger.info(f"\n📊 Estadísticas de weekly_data:")
        logger.info(f"  Total semanas:     {total_weeks}")
        logger.info(f"  Semanas con MA30:  {weeks_with_ma30}")
        
        # Acciones listas para análisis
        stocks_ready = 0
        for stock in stocks:
            stats = aggregator.get_stock_weekly_stats(stock.id)
            if stats['ready_for_analysis']:
                stocks_ready += 1
        
        logger.info(f"\n✓ Acciones listas para análisis Weinstein: {stocks_ready}/{total}")
        
        logger.info("=" * 60)
        logger.info("AGREGACIÓN INICIAL COMPLETADA")
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
