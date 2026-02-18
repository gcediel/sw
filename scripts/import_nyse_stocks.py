#!/usr/bin/env python3
"""
Importar acciones NYSE desde CSV a la base de datos.
Solo inserta metadatos (no descarga datos históricos).
Las acciones ya existentes se ignoran.

Uso:
    python scripts/import_nyse_stocks.py nyse_top1100.csv
    python scripts/import_nyse_stocks.py nyse_top1100.csv --dry-run

La carga de datos históricos se hace por separado con:
    python scripts/load_missing_historical.py --limit 100
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

import csv
import argparse
from datetime import datetime
from app.database import SessionLocal, Stock
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/import_nyse.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Importar acciones NYSE desde CSV')
    parser.add_argument('csv_file', help='Ruta al archivo CSV (Nombre;Ticker;País)')
    parser.add_argument('--dry-run', action='store_true', help='Simular sin insertar')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("IMPORTACIÓN DE ACCIONES NYSE")
    logger.info("=" * 60)
    logger.info(f"Archivo: {args.csv_file}")
    if args.dry_run:
        logger.info("MODO: DRY-RUN (simulación)")

    # Leer CSV
    stocks_csv = []
    with open(args.csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        for row in reader:
            if len(row) < 3:
                continue
            name = row[0].strip()
            ticker = row[1].strip()
            if not ticker or ticker.startswith('^'):
                continue
            stocks_csv.append({'name': name, 'ticker': ticker})

    logger.info(f"Acciones en CSV: {len(stocks_csv)}")

    # Comparar con BD
    db = SessionLocal()
    try:
        existing_tickers = {s.ticker for s in db.query(Stock.ticker).all()}
        logger.info(f"Acciones ya en BD: {len(existing_tickers)}")

        new_stocks = [s for s in stocks_csv if s['ticker'] not in existing_tickers]
        duplicates = len(stocks_csv) - len(new_stocks)

        logger.info(f"Duplicadas (se ignoran): {duplicates}")
        logger.info(f"Nuevas a insertar: {len(new_stocks)}")

        if len(new_stocks) == 0:
            logger.info("\nNo hay acciones nuevas. Nada que hacer.")
            return

        if args.dry_run:
            logger.info("\n[DRY-RUN] Primeras 20 acciones nuevas:")
            for s in new_stocks[:20]:
                logger.info(f"  {s['ticker']:>6} - {s['name']}")
            if len(new_stocks) > 20:
                logger.info(f"  ... y {len(new_stocks) - 20} más")
            return

        # Insertar nuevas acciones
        inserted = 0
        failed = []
        for s in new_stocks:
            try:
                stock = Stock(
                    ticker=s['ticker'],
                    name=s['name'],
                    exchange='NYSE',
                    active=True
                )
                db.add(stock)
                db.commit()
                inserted += 1
                logger.info(f"  ✓ {s['ticker']:>6} - {s['name']}")
            except Exception as e:
                db.rollback()
                failed.append(s['ticker'])
                logger.error(f"  ✗ {s['ticker']}: {e}")

        logger.info(f"\n{'=' * 60}")
        logger.info(f"RESULTADO")
        logger.info(f"{'=' * 60}")
        logger.info(f"Insertadas: {inserted}")
        logger.info(f"Fallidas:   {len(failed)}")
        if failed:
            logger.warning(f"Tickers fallidos: {failed}")

        logger.info(f"\nSIGUIENTE PASO:")
        logger.info(f"  Ejecutar carga gradual de datos históricos:")
        logger.info(f"  python scripts/load_missing_historical.py --limit 100")
        logger.info(f"  (repetir cada día hasta que no queden acciones sin datos)")

    finally:
        db.close()


if __name__ == '__main__':
    main()
