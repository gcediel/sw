"""
Archivo de configuración de ejemplo
Copiar a config.py y modificar valores según tu entorno
"""
import os
from pathlib import Path

# Rutas base
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = Path("/var/log/stanweinstein")

# Configuración de base de datos
DB_CONFIG = {
    'host': 'localhost',
    'user': 'stanweinstein',
    'password': 'CAMBIAR_PASSWORD_AQUI',  # ← Cambiar por password real
    'database': 'stanweinstein',
    'charset': 'utf8mb4'
}

# Telegram (obtener después de crear bot)
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"  # ← Token real
TELEGRAM_CHAT_ID = "123456789"  # ← Chat ID real

# Configuración yfinance - Rate limiting
RATE_LIMIT_DELAY = 2  # segundos entre peticiones
MAX_RETRIES = 3       # reintentos en caso de fallo
RETRY_DELAY = 5       # segundos entre reintentos

# Configuración análisis Weinstein
MIN_WEEKS_FOR_ANALYSIS = 35  # 30 para MA30 + 5 de margen
VOLUME_SPIKE_THRESHOLD = 1.5  # 150% del volumen promedio
MA30_SLOPE_THRESHOLD = 0.02   # 2% para considerar tendencia significativa

# Días de trading por semana
TRADING_DAYS_PER_WEEK = 5
