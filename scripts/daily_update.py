#!/usr/bin/env python3
"""
Script para actualización diaria de datos
Se ejecuta automáticamente vía cron cada día

Uso:
    python scripts/daily_update.py
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from app.database import SessionLocal, Stock
from app.data_collector import DataCollector
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/daily_update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Función principal de actualización diaria"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"ACTUALIZACIÓN DIARIA - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Obtener todas las acciones activas
        stocks = db.query(Stock).filter(Stock.active == True).all()
        
        if not stocks:
            logger.warning("⚠ No hay acciones activas para actualizar")
            return
        
        total = len(stocks)
        logger.info(f"📈 Acciones a actualizar: {total}")
        logger.info("-" * 60)
        
        collector = DataCollector(db)
        success = 0
        failed = []
        
        # Actualizar cada acción
        for idx, stock in enumerate(stocks, 1):
            ticker = stock.ticker
            logger.info(f"[{idx}/{total}] Actualizando {ticker}...")
            
            try:
                # Actualizar últimos 5 días (cubre fines de semana y festivos)
                if collector.update_daily_data(ticker, days_back=5):
                    success += 1
                else:
                    failed.append(ticker)
                    logger.warning(f"⚠ {ticker}: sin nuevos datos")
            except Exception as e:
                logger.error(f"✗ Error actualizando {ticker}: {e}")
                failed.append(ticker)
        
        # Resumen
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN ACTUALIZACIÓN DIARIA")
        logger.info("=" * 60)
        logger.info(f"Total:             {total}")
        logger.info(f"Actualizadas:      {success} ({success/total*100:.1f}%)")
        logger.info(f"Con errores:       {len(failed)} ({len(failed)/total*100:.1f}%)")
        logger.info(f"Duración:          {duration:.0f} segundos")
        
        if failed:
            logger.warning(f"\n⚠ Tickers con problemas ({len(failed)}):")
            for ticker in failed:
                logger.warning(f"  - {ticker}")
        
        logger.info("=" * 60)
        logger.info("ACTUALIZACIÓN DIARIA COMPLETADA")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Error crítico en actualización diaria: {e}")
        sys.exit(1)
    finally:
        db.close()
    
    sys.exit(0)


if __name__ == '__main__':
    main()
