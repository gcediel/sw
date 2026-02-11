#!/usr/bin/env python3
"""
Script de debug para ver la estructura del DataFrame de Twelve Data
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from twelvedata import TDClient
from app.config import TWELVEDATA_API_KEY
import pandas as pd

print("=== DEBUG TWELVE DATA DATAFRAME ===\n")

# Crear cliente
td = TDClient(apikey=TWELVEDATA_API_KEY)

# Descargar datos de AAPL
print("Descargando AAPL...")
ts = td.time_series(
    symbol="AAPL",
    interval="1day",
    outputsize=5
)

# Convertir a DataFrame
df = ts.as_pandas()

print("\n1. DataFrame original (antes de reset_index):")
print(f"   Tipo de índice: {type(df.index)}")
print(f"   Nombre del índice: {df.index.name}")
print(f"   Columnas: {list(df.columns)}")
print(f"   Shape: {df.shape}")
print("\nPrimeras filas:")
print(df.head())

print("\n" + "="*60)
print("\n2. Después de reset_index:")
df_reset = df.reset_index()
print(f"   Columnas: {list(df_reset.columns)}")
print(f"   Shape: {df_reset.shape}")
print("\nPrimeras filas:")
print(df_reset.head())

print("\n" + "="*60)
print("\n3. Verificando acceso a datos:")
for idx, row in df_reset.iterrows():
    print(f"\nRegistro {idx}:")
    print(f"   Columnas disponibles: {list(row.index)}")
    print(f"   Primera columna: {row.iloc[0]} (tipo: {type(row.iloc[0])})")
    if idx >= 1:  # Solo mostrar 2 registros
        break

print("\n" + "="*60)
