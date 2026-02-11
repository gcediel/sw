#!/usr/bin/env python3
"""
Script para cargar datos históricos de acciones sin datos
Lee automáticamente de BD las acciones que no tienen datos en daily_data
Luego ejecuta carga histórica para cada una

Uso:
    python scripts/load_missing_historical.py
    
Opciones:
    --limit N     : Limitar a N acciones (para probar o por límite API)
    --dry-run     : Simular sin cargar datos
    --continue    : Continuar desde donde quedó (salta acciones ya procesadas)
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

import argparse
from datetime import datetime
from app.database import SessionLocal, Stock, DailyData
from app.data_collector import DataCollector
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/load_missing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_stocks_without_data(limit: int = None) -> list:
    """
    Obtener lista de acciones sin datos históricos
    
    Args:
        limit: Limitar número de resultados
    
    Returns:
        Lista de objetos Stock
    """
    db = SessionLocal()
    
    try:
        # Subconsulta: IDs de acciones con datos
        stocks_with_data_ids = db.query(DailyData.stock_id).distinct().subquery()
        
        # Acciones activas sin datos
        query = db.query(Stock).filter(
            Stock.active == True,
            ~Stock.id.in_(stocks_with_data_ids)
        ).order_by(Stock.ticker)
        
        if limit:
            query = query.limit(limit)
        
        stocks = query.all()
        
        logger.info(f"✓ Acciones sin datos encontradas: {len(stocks)}")
        
        return stocks
        
    finally:
        db.close()


def load_historical_for_stocks(stocks: list, dry_run: bool = False) -> dict:
    """
    Cargar datos históricos para lista de acciones
    
    Args:
        stocks: Lista de objetos Stock
        dry_run: Si es True, solo simula
    
    Returns:
        Dict con estadísticas
    """
    db = SessionLocal()
    collector = DataCollector(db)
    
    success = 0
    failed = []
    skipped = []
    
    total = len(stocks)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"CARGA HISTÓRICA: {total} acciones")
    
    if not dry_run:
        logger.info(f"⏳ Tiempo estimado: {total * 8 / 60:.0f} minutos")
        logger.info(f"📊 Peticiones API: ~{total}")
    else:
        logger.info("MODO: DRY-RUN (simulación)")
    
    logger.info(f"{'='*60}\n")
    
    for idx, stock in enumerate(stocks, 1):
        ticker = stock.ticker
        
        # Verificar si ya tiene datos (por si continúa proceso)
        has_data = db.query(DailyData).filter(
            DailyData.stock_id == stock.id
        ).first() is not None
        
        if has_data:
            logger.debug(f"[{idx}/{total}] {ticker}: Ya tiene datos, saltando")
            skipped.append(ticker)
            continue
        
        logger.info(f"[{idx}/{total}] Cargando {ticker} ({stock.name})...")
        
        if dry_run:
            logger.info(f"  [DRY-RUN] {ticker}: Se cargaría")
            success += 1
            continue
        
        try:
            result = collector.load_historical_data(ticker, years=2)
            
            if result:
                success += 1
            else:
                failed.append(ticker)
                logger.warning(f"⚠ {ticker}: Sin datos descargados")
                
        except KeyboardInterrupt:
            logger.warning("\n⚠ Proceso interrumpido por el usuario")
            logger.info(f"✓ Progreso: {success}/{idx} exitosas")
            logger.info(f"💡 Para continuar, ejecuta de nuevo con --continue")
            db.close()
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"✗ {ticker}: Error - {e}")
            failed.append(ticker)
    
    db.close()
    
    return {
        'total': total,
        'success': success,
        'failed': len(failed),
        'skipped': len(skipped),
        'failed_tickers': failed
    }


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Cargar datos históricos de acciones sin datos'
    )
    parser.add_argument(
        '--limit', 
        type=int, 
        help='Limitar a N acciones (útil para probar o por límite API)'
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Simular sin cargar datos'
    )
    parser.add_argument(
        '--continue', 
        dest='continue_mode',
        action='store_true', 
        help='Continuar desde donde quedó (salta acciones con datos)'
    )
    
    args = parser.parse_args()
    
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info("CARGA DE DATOS HISTÓRICOS - ACCIONES FALTANTES")
    logger.info("=" * 60)
    logger.info(f"Fecha/Hora: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.dry_run:
        logger.info("MODO: DRY-RUN (simulación)")
    if args.limit:
        logger.info(f"LÍMITE: {args.limit} acciones")
    if args.continue_mode:
        logger.info("MODO: Continuación (salta acciones con datos)")
    
    logger.info("=" * 60)
    
    # Obtener acciones sin datos
    logger.info("\nObteniendo lista de acciones sin datos...")
    stocks = get_stocks_without_data(limit=args.limit)
    
    if not stocks:
        logger.info("\n✓ No hay acciones sin datos. Todo al día.")
        sys.exit(0)
    
    # Mostrar resumen
    logger.info(f"\n📊 Resumen:")
    logger.info(f"  Acciones sin datos: {len(stocks)}")
    
    if not args.dry_run:
        logger.info(f"  Peticiones API:     ~{len(stocks)}")
        logger.info(f"  Tiempo estimado:    {len(stocks) * 8 / 60:.0f} minutos")
    
    # Mostrar primeras 10 acciones
    logger.info(f"\n📋 Primeras acciones a cargar:")
    for stock in stocks[:10]:
        logger.info(f"  - {stock.ticker}: {stock.name}")
    if len(stocks) > 10:
        logger.info(f"  ... y {len(stocks) - 10} más")
    
    # Advertencia si son muchas acciones
    if len(stocks) > 100 and not args.dry_run:
        logger.warning(f"\n⚠ ADVERTENCIA:")
        logger.warning(f"  Se van a cargar {len(stocks)} acciones")
        logger.warning(f"  Esto consumirá ~{len(stocks)} peticiones de API")
        logger.warning(f"  Límite diario Twelve Data: 800 peticiones")
        
        if len(stocks) > 800:
            logger.error(f"\n✗ ERROR: {len(stocks)} acciones superan el límite diario")
            logger.error(f"  Usa --limit para cargar en lotes")
            logger.error(f"  Ejemplo: --limit 700")
            sys.exit(1)
        
        response = input("\n¿Continuar? (s/n): ")
        if response.lower() != 's':
            logger.info("Carga cancelada por el usuario")
            sys.exit(0)
    
    # Ejecutar carga
    logger.info("\n" + "=" * 60)
    logger.info("INICIANDO CARGA...")
    logger.info("=" * 60)
    logger.info("💡 Presiona Ctrl+C para interrumpir (puedes continuar después)")
    logger.info("=" * 60)
    
    result = load_historical_for_stocks(stocks, dry_run=args.dry_run)
    
    # Resumen final
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN FINAL")
    logger.info("=" * 60)
    logger.info(f"Acciones procesadas:   {result['total']}")
    logger.info(f"Exitosas:              {result['success']} ({result['success']/result['total']*100:.1f}%)")
    logger.info(f"Fallidas:              {result['failed']}")
    
    if result['skipped'] > 0:
        logger.info(f"Saltadas (ya tenían datos): {result['skipped']}")
    
    logger.info(f"\nDuración:              {duration:.0f} segundos ({duration/60:.1f} minutos)")
    
    if result['failed_tickers']:
        logger.warning(f"\n⚠ Acciones sin datos ({len(result['failed_tickers'])}):")
        for ticker in result['failed_tickers'][:20]:
            logger.warning(f"  - {ticker}")
        if result['failed'] > 20:
            logger.warning(f"  ... y {result['failed'] - 20} más")
    
    logger.info("=" * 60)
    
    # Siguientes pasos
    if not args.dry_run and result['success'] > 0:
        logger.info("\n📋 SIGUIENTES PASOS:")
        logger.info("  1. Ejecutar agregación semanal:")
        logger.info("     python scripts/init_weekly_aggregation.py")
        logger.info("  2. Ejecutar análisis inicial:")
        logger.info("     python scripts/analyze_initial.py")
    
    logger.info("\n✓ Proceso completado")
    
    # Exit code según resultado
    if result['failed'] > result['success'] / 2:
        logger.warning("\n⚠ Más del 50% de acciones fallaron")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == '__main__':
    main()
