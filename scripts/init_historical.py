#!/usr/bin/env python3
"""
Script para carga inicial de datos históricos
Ejecutar una sola vez al inicializar el sistema

Uso:
    python scripts/init_historical.py
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from app.database import init_db, SessionLocal
from app.data_collector import DataCollector
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/historical_load.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# LISTA DE ACCIONES A MONITORIZAR
# ============================================
# IMPORTANTE: Ampliar esta lista con tus acciones reales
# Formato: {'ticker': 'SIMBOLO', 'name': 'Nombre', 'exchange': 'Mercado'}

STOCKS_TO_MONITOR = [
    # ===== NYSE/NASDAQ (USA) =====
    {'ticker': 'AAPL', 'name': 'Apple Inc.', 'exchange': 'NASDAQ'},
    {'ticker': 'MSFT', 'name': 'Microsoft Corporation', 'exchange': 'NASDAQ'},
    {'ticker': 'GOOGL', 'name': 'Alphabet Inc.', 'exchange': 'NASDAQ'},
    {'ticker': 'AMZN', 'name': 'Amazon.com Inc.', 'exchange': 'NASDAQ'},
    {'ticker': 'TSLA', 'name': 'Tesla Inc.', 'exchange': 'NASDAQ'},
    {'ticker': 'NVDA', 'name': 'NVIDIA Corporation', 'exchange': 'NASDAQ'},
    {'ticker': 'META', 'name': 'Meta Platforms Inc.', 'exchange': 'NASDAQ'},
    {'ticker': 'JPM', 'name': 'JPMorgan Chase', 'exchange': 'NYSE'},
    {'ticker': 'V', 'name': 'Visa Inc.', 'exchange': 'NYSE'},
    {'ticker': 'JNJ', 'name': 'Johnson & Johnson', 'exchange': 'NYSE'},
    
    # ===== ESPAÑA (Sufijo .MC para Madrid) =====
    {'ticker': 'SAN.MC', 'name': 'Banco Santander', 'exchange': 'BME'},
    {'ticker': 'TEF.MC', 'name': 'Telefónica', 'exchange': 'BME'},
    {'ticker': 'IBE.MC', 'name': 'Iberdrola', 'exchange': 'BME'},
    {'ticker': 'ITX.MC', 'name': 'Inditex', 'exchange': 'BME'},
    {'ticker': 'BBVA.MC', 'name': 'BBVA', 'exchange': 'BME'},
    {'ticker': 'REP.MC', 'name': 'Repsol', 'exchange': 'BME'},
    {'ticker': 'CABK.MC', 'name': 'CaixaBank', 'exchange': 'BME'},
    {'ticker': 'FER.MC', 'name': 'Ferrovial', 'exchange': 'BME'},
    {'ticker': 'ENG.MC', 'name': 'Enagás', 'exchange': 'BME'},
    {'ticker': 'ACS.MC', 'name': 'ACS', 'exchange': 'BME'},
    
    # ===== EUROPA (Ejemplos) =====
    # Alemania (XETRA)
    {'ticker': 'SAP', 'name': 'SAP SE', 'exchange': 'XETRA'},
    {'ticker': 'SIE.DE', 'name': 'Siemens AG', 'exchange': 'XETRA'},
    {'ticker': 'VOW3.DE', 'name': 'Volkswagen', 'exchange': 'XETRA'},
    
    # Holanda
    {'ticker': 'ASML', 'name': 'ASML Holding', 'exchange': 'AMS'},
    
    # Francia (Sufijo .PA para París)
    {'ticker': 'MC.PA', 'name': 'LVMH', 'exchange': 'EPA'},
    {'ticker': 'OR.PA', 'name': "L'Oréal", 'exchange': 'EPA'},
    
    # Reino Unido (Sufijo .L para Londres)
    {'ticker': 'BP.L', 'name': 'BP plc', 'exchange': 'LSE'},
    {'ticker': 'HSBA.L', 'name': 'HSBC Holdings', 'exchange': 'LSE'},
    
    # Italia (Sufijo .MI para Milán)
    {'ticker': 'ENI.MI', 'name': 'Eni S.p.A.', 'exchange': 'BIT'},
]


def main():
    """Función principal de carga histórica"""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("INICIO CARGA HISTÓRICA DE DATOS")
    logger.info("=" * 60)
    logger.info(f"Fecha/Hora: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Total de acciones: {len(STOCKS_TO_MONITOR)}")
    logger.info("=" * 60)
    
    # Inicializar base de datos (crear tablas si no existen)
    logger.info("\n📊 Inicializando esquema de base de datos...")
    try:
        init_db()
    except Exception as e:
        logger.error(f"✗ Error inicializando base de datos: {e}")
        return
    
    # Crear sesión y collector
    db = SessionLocal()
    collector = DataCollector(db)
    
    # Contadores
    total = len(STOCKS_TO_MONITOR)
    success = 0
    failed = []
    
    # Procesar cada acción
    for idx, stock_info in enumerate(STOCKS_TO_MONITOR, 1):
        ticker = stock_info['ticker']
        
        logger.info("\n" + "-" * 60)
        logger.info(f"[{idx}/{total}] Procesando {ticker} - {stock_info['name']}")
        logger.info("-" * 60)
        
        try:
            # Cargar 2 años de histórico (≈104 semanas)
            if collector.load_historical_data(ticker, years=2):
                success += 1
                logger.info(f"✓ {ticker} completado exitosamente")
            else:
                failed.append(ticker)
                logger.warning(f"⚠ {ticker} sin datos o error")
        except Exception as e:
            logger.error(f"✗ Error crítico con {ticker}: {e}")
            failed.append(ticker)
    
    # Cerrar sesión
    db.close()
    
    # Resumen final
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN DE CARGA HISTÓRICA")
    logger.info("=" * 60)
    logger.info(f"Total procesadas:  {total}")
    logger.info(f"Exitosas:          {success} ({success/total*100:.1f}%)")
    logger.info(f"Fallidas:          {len(failed)} ({len(failed)/total*100:.1f}%)")
    logger.info(f"Duración:          {duration:.0f} segundos ({duration/60:.1f} minutos)")
    
    if failed:
        logger.warning(f"\n⚠ Tickers fallidos ({len(failed)}):")
        for ticker in failed:
            logger.warning(f"  - {ticker}")
    
    logger.info("=" * 60)
    logger.info("CARGA HISTÓRICA FINALIZADA")
    logger.info("=" * 60)
    
    # Código de salida
    sys.exit(0 if len(failed) == 0 else 1)


if __name__ == '__main__':
    main()
