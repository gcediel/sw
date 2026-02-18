"""
Obtener las 1100 acciones con más volumen del NYSE.
Usa TwelveData para la lista de acciones y yfinance para el volumen medio.
Genera CSV en formato: Nombre;Ticker;País
"""
import sys
sys.path.insert(0, '/home/gcb/Nextcloud/Desarrollo/stanweinstein_test')

import requests
import yfinance as yf
import pandas as pd
from app.config import TWELVEDATA_API_KEY

OUTPUT_FILE = '/home/gcb/Nextcloud/Desarrollo/stanweinstein_test/nyse_top1100.csv'
TARGET_COUNT = 1100

# ============================================================
# Paso 1: Obtener lista completa de acciones NYSE desde TwelveData
# ============================================================
print("=" * 60)
print("  Generando CSV: Top 1100 NYSE por volumen")
print("=" * 60)

print("\n[1/3] Obteniendo lista de acciones NYSE desde TwelveData...")
url = "https://api.twelvedata.com/stocks"
params = {
    'exchange': 'NYSE',
    'country': 'United States',
    'type': 'Common Stock',
    'apikey': TWELVEDATA_API_KEY,
}
resp = requests.get(url, params=params)
data = resp.json()

if 'data' not in data:
    print(f"  ERROR: {data}")
    sys.exit(1)

stocks = data['data']
print(f"  ✓ {len(stocks)} acciones comunes en NYSE")

# Filtrar: excluir tickers con caracteres raros (warrants, units, preferreds)
clean_stocks = []
for s in stocks:
    ticker = s['symbol']
    # Excluir tickers con ., -, / o más de 5 caracteres (suelen ser preferreds/warrants)
    if '.' in ticker or '/' in ticker or len(ticker) > 5:
        continue
    # Excluir si el nombre sugiere preferred, warrant, unit, right
    name_lower = s.get('name', '').lower()
    skip_words = ['preferred', 'warrant', 'unit', 'right', 'debenture', 'note', 'bond']
    if any(w in name_lower for w in skip_words):
        continue
    clean_stocks.append({
        'ticker': ticker,
        'name': s.get('name', ticker),
    })

print(f"  ✓ {len(clean_stocks)} tras filtrar preferreds/warrants/units")

# ============================================================
# Paso 2: Obtener volumen medio con yfinance (en lotes)
# ============================================================
print(f"\n[2/3] Obteniendo volumen medio de {len(clean_stocks)} acciones (yfinance)...")
print("  (Esto puede tardar unos minutos...)")

tickers_list = [s['ticker'] for s in clean_stocks]
ticker_to_name = {s['ticker']: s['name'] for s in clean_stocks}

# Descargar datos de 3 meses en lotes de 200
BATCH_SIZE = 200
all_avg_volumes = {}

for i in range(0, len(tickers_list), BATCH_SIZE):
    batch = tickers_list[i:i + BATCH_SIZE]
    batch_str = ' '.join(batch)
    batch_num = i // BATCH_SIZE + 1
    total_batches = (len(tickers_list) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"  Lote {batch_num}/{total_batches} ({len(batch)} tickers)...", end=' ', flush=True)

    try:
        df = yf.download(batch_str, period='3mo', progress=False, threads=True)
        if 'Volume' in df.columns:
            # Multi-ticker: Volume tiene columnas por ticker
            if isinstance(df.columns, pd.MultiIndex):
                vol_df = df['Volume']
                for ticker in batch:
                    if ticker in vol_df.columns:
                        avg_vol = vol_df[ticker].mean()
                        if pd.notna(avg_vol) and avg_vol > 0:
                            all_avg_volumes[ticker] = avg_vol
            else:
                # Single ticker
                if len(batch) == 1:
                    avg_vol = df['Volume'].mean()
                    if pd.notna(avg_vol) and avg_vol > 0:
                        all_avg_volumes[batch[0]] = avg_vol
        print(f"✓ ({len([t for t in batch if t in all_avg_volumes])} con datos)")
    except Exception as e:
        print(f"✗ Error: {e}")

print(f"\n  ✓ Volumen obtenido para {len(all_avg_volumes)} acciones")

# ============================================================
# Paso 3: Ordenar por volumen y generar CSV
# ============================================================
print(f"\n[3/3] Generando CSV con top {TARGET_COUNT}...")

# Ordenar por volumen descendente
sorted_stocks = sorted(all_avg_volumes.items(), key=lambda x: x[1], reverse=True)

# Tomar las top N
top_stocks = sorted_stocks[:TARGET_COUNT]

# Generar CSV
lines = []
for ticker, avg_vol in top_stocks:
    name = ticker_to_name.get(ticker, ticker)
    lines.append(f"{name};{ticker};Estados Unidos")

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print(f"  ✓ {len(lines)} acciones escritas en {OUTPUT_FILE}")

# Estadísticas
if top_stocks:
    print(f"\n  Volumen medio diario:")
    print(f"    Top 1:    {top_stocks[0][0]:>6} → {top_stocks[0][1]:>15,.0f}")
    print(f"    Top 10:   {top_stocks[9][0]:>6} → {top_stocks[9][1]:>15,.0f}")
    print(f"    Top 100:  {top_stocks[99][0]:>6} → {top_stocks[99][1]:>15,.0f}")
    print(f"    Top 500:  {top_stocks[499][0]:>6} → {top_stocks[499][1]:>15,.0f}")
    if len(top_stocks) >= TARGET_COUNT:
        last = top_stocks[-1]
        print(f"    Top {TARGET_COUNT}: {last[0]:>6} → {last[1]:>15,.0f}")

print("\n[Completado]")
