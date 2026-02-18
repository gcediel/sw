"""
Script para resetear señales y re-analizar todo el histórico
con los nuevos parámetros V5.

1. Borra todas las señales existentes
2. Re-analiza etapas de todas las acciones (histórico completo)
3. Regenera señales sobre todo el histórico
"""
import sys
sys.path.insert(0, '/home/gcb/Nextcloud/Desarrollo/stanweinstein_test')

# Apuntar a BD de producción desde dev
from app import config
config.DB_CONFIG['host'] = '192.168.100.11'

# Reimportar database para que use el host correcto
from importlib import reload
from app import database
reload(database)

from app.database import SessionLocal, Signal
from app.analyzer import WeinsteinAnalyzer
from app.signals import SignalGenerator
from app.config import MA30_SLOPE_THRESHOLD, MAX_PRICE_DISTANCE_FOR_BUY

db = SessionLocal()

print("=" * 60)
print("  RESET DE SEÑALES - Nuevos parámetros V5")
print("=" * 60)
print(f"\n  MA30_SLOPE_THRESHOLD = {MA30_SLOPE_THRESHOLD}")
print(f"  MAX_PRICE_DISTANCE_FOR_BUY = {MAX_PRICE_DISTANCE_FOR_BUY}")

# Paso 1: Borrar señales
count = db.query(Signal).count()
print(f"\n[1/3] Borrando {count} señales existentes...")
db.query(Signal).delete()
db.commit()
print(f"  ✓ {count} señales eliminadas")

# Paso 2: Re-analizar etapas (histórico completo)
print(f"\n[2/3] Re-analizando etapas (histórico completo)...")
analyzer = WeinsteinAnalyzer(db)
result = analyzer.analyze_all_stocks(weeks_back=0)
print(f"  ✓ {result['success']}/{result['total']} acciones analizadas")
if result['failed'] > 0:
    print(f"  ✗ Fallidas: {result['failed_tickers']}")

# Paso 3: Regenerar señales
print(f"\n[3/3] Regenerando señales (histórico completo)...")
generator = SignalGenerator(db)
result = generator.generate_signals_for_all_stocks(weeks_back=0)
print(f"  ✓ {result['total_signals']} señales generadas en {result['stocks_with_signals']} acciones")
if result['failed'] > 0:
    print(f"  ✗ Fallidas: {result['failed_tickers']}")

# Resumen
print(f"\n{'=' * 60}")
buy_count = db.query(Signal).filter(Signal.signal_type == 'BUY').count()
sell_count = db.query(Signal).filter(Signal.signal_type == 'SELL').count()
change_count = db.query(Signal).filter(Signal.signal_type == 'STAGE_CHANGE').count()
print(f"  Señales generadas: BUY={buy_count}, SELL={sell_count}, STAGE_CHANGE={change_count}")

# Verificar AMD
from app.database import Stock
amd = db.query(Stock).filter(Stock.ticker == 'AMD').first()
if amd:
    amd_signals = db.query(Signal).filter(Signal.stock_id == amd.id, Signal.signal_type == 'BUY').all()
    print(f"\n  Señales BUY de AMD: {[str(s.signal_date) for s in amd_signals] if amd_signals else 'Ninguna'}")

db.close()
print("\n[Completado]")
