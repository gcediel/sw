#!/usr/bin/env python3
"""
Script para cargar acciones desde archivo CSV
Lee CSV con formato: Nombre;Ticker;País
Inserta en BD solo las nuevas acciones
Luego ejecuta carga histórica completa

Uso:
    python scripts/load_stocks_from_csv.py empresas.csv
    
Opciones:
    --dry-run     : Simular sin insertar en BD
    --skip-load   : Solo insertar en BD, no cargar datos
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

import csv
import argparse
from datetime import datetime
from app.database import SessionLocal, Stock
from app.data_collector import DataCollector
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/csv_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def is_index(ticker: str) -> bool:
    """Determinar si un ticker es un índice (no acción)"""
    # Índices comienzan con ^
    return ticker.startswith('^')


def normalize_ticker(ticker: str) -> str:
    """
    Normalizar ticker para evitar duplicados
    Ejemplo: BRK-B → BRK.B
    """
    # Reemplazar guiones por puntos (formato Yahoo/Twelve Data)
    return ticker.replace('-', '.')


def read_csv_stocks(csv_path: str) -> list:
    """
    Leer archivo CSV y extraer acciones
    
    Returns:
        Lista de dicts con {ticker, name, country}
    """
    stocks = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            # Detectar separador (puede ser ; o ,)
            first_line = f.readline()
            f.seek(0)
            
            delimiter = ';' if ';' in first_line else ','
            
            reader = csv.reader(f, delimiter=delimiter)
            
            for idx, row in enumerate(reader, 1):
                if len(row) < 3:
                    logger.warning(f"Línea {idx}: Formato incorrecto, saltando")
                    continue
                
                name = row[0].strip()
                ticker = row[1].strip()
                country = row[2].strip()
                
                # Filtrar índices
                if is_index(ticker):
                    logger.debug(f"Línea {idx}: {ticker} es un índice, saltando")
                    continue
                
                # Normalizar ticker
                ticker = normalize_ticker(ticker)
                
                stocks.append({
                    'ticker': ticker,
                    'name': name,
                    'country': country
                })
        
        logger.info(f"✓ CSV leído: {len(stocks)} acciones válidas encontradas")
        return stocks
        
    except FileNotFoundError:
        logger.error(f"✗ Archivo no encontrado: {csv_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ Error leyendo CSV: {e}")
        sys.exit(1)


def insert_stocks_in_db(stocks: list, dry_run: bool = False) -> dict:
    """
    Insertar acciones en la base de datos
    
    Returns:
        Dict con estadísticas {new, existing, failed}
    """
    db = SessionLocal()
    
    new_stocks = []
    existing = []
    failed = []
    
    try:
        for stock_data in stocks:
            ticker = stock_data['ticker']
            
            # Verificar si ya existe
            existing_stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            
            if existing_stock:
                logger.debug(f"{ticker}: Ya existe en BD")
                existing.append(ticker)
                continue
            
            if dry_run:
                logger.info(f"[DRY-RUN] {ticker}: Se insertaría")
                new_stocks.append(stock_data)
                continue
            
            # Insertar nueva acción
            try:
                # Determinar exchange basado en ticker
                if ticker.endswith('.MC'):
                    exchange = 'BME'
                elif '.' in ticker:
                    exchange = ticker.split('.')[-1]
                else:
                    exchange = 'NASDAQ'  # Asumimos US por defecto
                
                new_stock = Stock(
                    ticker=ticker,
                    name=stock_data['name'],
                    exchange=exchange,
                    active=True
                )
                
                db.add(new_stock)
                db.commit()
                
                logger.info(f"✓ {ticker}: Insertado en BD")
                new_stocks.append(stock_data)
                
            except Exception as e:
                db.rollback()
                logger.error(f"✗ {ticker}: Error insertando - {e}")
                failed.append(ticker)
        
        return {
            'new': len(new_stocks),
            'new_stocks': new_stocks,
            'existing': len(existing),
            'failed': len(failed),
            'failed_tickers': failed
        }
        
    finally:
        db.close()


def load_historical_data_for_stocks(stocks: list) -> dict:
    """
    Cargar datos históricos para lista de acciones
    
    Args:
        stocks: Lista de dicts con ticker info
    
    Returns:
        Dict con estadísticas
    """
    db = SessionLocal()
    collector = DataCollector(db)
    
    success = 0
    failed = []
    
    total = len(stocks)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"CARGA HISTÓRICA: {total} acciones")
    logger.info(f"{'='*60}")
    logger.info("⏳ Esto tardará aproximadamente {:.0f} minutos".format(total * 8 / 60))
    logger.info(f"{'='*60}\n")
    
    for idx, stock_data in enumerate(stocks, 1):
        ticker = stock_data['ticker']
        
        logger.info(f"[{idx}/{total}] Cargando {ticker} ({stock_data['name']})...")
        
        try:
            result = collector.load_historical_data(ticker, years=2)
            
            if result:
                success += 1
            else:
                failed.append(ticker)
                logger.warning(f"⚠ {ticker}: Sin datos descargados")
                
        except Exception as e:
            logger.error(f"✗ {ticker}: Error - {e}")
            failed.append(ticker)
    
    db.close()
    
    return {
        'total': total,
        'success': success,
        'failed': len(failed),
        'failed_tickers': failed
    }


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Importar acciones desde CSV')
    parser.add_argument('csv_file', help='Ruta al archivo CSV')
    parser.add_argument('--dry-run', action='store_true', help='Simular sin insertar')
    parser.add_argument('--skip-load', action='store_true', help='Solo insertar, no cargar datos')
    
    args = parser.parse_args()
    
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info("IMPORTACIÓN DE ACCIONES DESDE CSV")
    logger.info("=" * 60)
    logger.info(f"Archivo: {args.csv_file}")
    logger.info(f"Fecha/Hora: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.dry_run:
        logger.info("MODO: DRY-RUN (simulación)")
    if args.skip_load:
        logger.info("MODO: Solo inserción (sin carga de datos)")
    
    logger.info("=" * 60)
    
    # FASE 1: Leer CSV
    logger.info("\nFASE 1: Lectura del archivo CSV...")
    stocks = read_csv_stocks(args.csv_file)
    
    logger.info(f"\n📊 Acciones encontradas en CSV:")
    logger.info(f"  Total acciones válidas: {len(stocks)}")
    
    # Contar por país
    countries = {}
    for stock in stocks:
        country = stock['country']
        countries[country] = countries.get(country, 0) + 1
    
    logger.info(f"\n  Distribución por país:")
    for country, count in sorted(countries.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"    {country}: {count}")
    
    # FASE 2: Insertar en BD
    logger.info("\n" + "=" * 60)
    logger.info("FASE 2: Inserción en base de datos...")
    logger.info("=" * 60)
    
    insert_result = insert_stocks_in_db(stocks, dry_run=args.dry_run)
    
    logger.info(f"\n✓ Inserción completada:")
    logger.info(f"  Nuevas:      {insert_result['new']}")
    logger.info(f"  Ya existían: {insert_result['existing']}")
    logger.info(f"  Fallidas:    {insert_result['failed']}")
    
    if insert_result['failed_tickers']:
        logger.warning(f"\n⚠ Acciones fallidas en inserción:")
        for ticker in insert_result['failed_tickers']:
            logger.warning(f"  - {ticker}")
    
    # FASE 3: Carga histórica
    if not args.skip_load and not args.dry_run and insert_result['new'] > 0:
        logger.info("\n" + "=" * 60)
        logger.info("FASE 3: Carga de datos históricos...")
        logger.info("=" * 60)
        
        # Advertencia si son muchas acciones
        if insert_result['new'] > 100:
            logger.warning(f"\n⚠ ADVERTENCIA:")
            logger.warning(f"  Se van a cargar {insert_result['new']} acciones")
            logger.warning(f"  Esto consumirá ~{insert_result['new']} peticiones de API")
            logger.warning(f"  Límite diario Twelve Data: 800 peticiones")
            logger.warning(f"  Tiempo estimado: {insert_result['new'] * 8 / 60:.0f} minutos")
            
            response = input("\n¿Continuar? (s/n): ")
            if response.lower() != 's':
                logger.info("Carga cancelada por el usuario")
                sys.exit(0)
        
        load_result = load_historical_data_for_stocks(insert_result['new_stocks'])
        
        logger.info(f"\n✓ Carga histórica completada:")
        logger.info(f"  Exitosas:    {load_result['success']}/{load_result['total']}")
        logger.info(f"  Fallidas:    {load_result['failed']}")
        
        if load_result['failed_tickers']:
            logger.warning(f"\n⚠ Acciones sin datos:")
            for ticker in load_result['failed_tickers'][:20]:  # Mostrar max 20
                logger.warning(f"  - {ticker}")
            if load_result['failed'] > 20:
                logger.warning(f"  ... y {load_result['failed'] - 20} más")
    
    elif args.skip_load:
        logger.info("\n⏭ Carga de datos históricos omitida (--skip-load)")
    elif args.dry_run:
        logger.info("\n⏭ Carga de datos históricos omitida (--dry-run)")
    elif insert_result['new'] == 0:
        logger.info("\n⏭ No hay acciones nuevas para cargar")
    
    # RESUMEN FINAL
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN FINAL")
    logger.info("=" * 60)
    logger.info(f"Acciones en CSV:       {len(stocks)}")
    logger.info(f"Nuevas insertadas:     {insert_result['new']}")
    logger.info(f"Ya existían:           {insert_result['existing']}")
    
    if not args.skip_load and not args.dry_run and insert_result['new'] > 0:
        logger.info(f"\nCarga histórica:")
        logger.info(f"  Exitosas:            {load_result['success']}")
        logger.info(f"  Fallidas:            {load_result['failed']}")
    
    logger.info(f"\nDuración total:        {duration:.0f} segundos ({duration/60:.1f} minutos)")
    logger.info("=" * 60)
    
    # Siguientes pasos
    if not args.dry_run and not args.skip_load and insert_result['new'] > 0:
        logger.info("\n📋 SIGUIENTES PASOS:")
        logger.info("  1. Ejecutar agregación semanal:")
        logger.info("     python scripts/init_weekly_aggregation.py")
        logger.info("  2. Ejecutar análisis inicial:")
        logger.info("     python scripts/analyze_initial.py")
    
    logger.info("\n✓ Proceso completado")


if __name__ == '__main__':
    main()
