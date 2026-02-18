"""
Obtener las 1100 acciones con más volumen del NYSE usando Finviz.
Genera CSV en formato: Nombre;Ticker;País
"""
import sys
sys.path.insert(0, '/home/gcb/Nextcloud/Desarrollo/stanweinstein_test')

import time
from finvizfinance.screener.overview import Overview

OUTPUT_FILE = '/home/gcb/Nextcloud/Desarrollo/stanweinstein_test/nyse_top1100.csv'
TARGET_COUNT = 1100

print("=" * 60)
print("  Generando CSV: Top 1100 NYSE por volumen (Finviz)")
print("=" * 60)

print("\n[1/2] Obteniendo acciones NYSE desde Finviz screener...")
print("  (Esto puede tardar unos minutos...)")

foverview = Overview()
filters_dict = {
    'Exchange': 'NYSE',
    'Average Volume': 'Over 100K',
    'Industry': 'Stocks only (ex-Funds)',
}
foverview.set_filter(filters_dict=filters_dict)
df = foverview.screener_view(order='Average Volume (3 Month)', ascend=False)

print(f"  ✓ {len(df)} acciones obtenidas")

if df is None or len(df) == 0:
    print("  ERROR: No se obtuvieron datos")
    sys.exit(1)

print(f"\n  Columnas: {list(df.columns)}")
print(f"  Primeras 5 filas:")
print(df.head())

# Tomar las top N
top_df = df.head(TARGET_COUNT)

print(f"\n[2/2] Generando CSV con top {TARGET_COUNT}...")

lines = []
for _, row in top_df.iterrows():
    ticker = row.get('Ticker', '')
    company = row.get('Company', ticker)
    # Limpiar nombre de empresa
    company = company.replace(';', ',')
    lines.append(f"{company};{ticker};Estados Unidos")

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print(f"  ✓ {len(lines)} acciones escritas en {OUTPUT_FILE}")

# Estadísticas
if 'Volume' in df.columns or 'Avg Volume' in df.columns:
    vol_col = 'Avg Volume' if 'Avg Volume' in df.columns else 'Volume'
    print(f"\n  Volumen medio ({vol_col}):")
    print(f"    Top 1:    {top_df.iloc[0]['Ticker']:>6} → {top_df.iloc[0].get(vol_col, 'N/A')}")
    print(f"    Top 10:   {top_df.iloc[9]['Ticker']:>6} → {top_df.iloc[9].get(vol_col, 'N/A')}")
    if len(top_df) >= 100:
        print(f"    Top 100:  {top_df.iloc[99]['Ticker']:>6} → {top_df.iloc[99].get(vol_col, 'N/A')}")
    if len(top_df) >= 500:
        print(f"    Top 500:  {top_df.iloc[499]['Ticker']:>6} → {top_df.iloc[499].get(vol_col, 'N/A')}")
    if len(top_df) >= TARGET_COUNT:
        print(f"    Top {TARGET_COUNT}: {top_df.iloc[-1]['Ticker']:>6} → {top_df.iloc[-1].get(vol_col, 'N/A')}")

print("\n[Completado]")
