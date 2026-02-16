# Documentacion Tecnica - Sistema Weinstein

## Indice

1. [Descripcion General](#1-descripcion-general)
2. [Estructura del Proyecto](#2-estructura-del-proyecto)
3. [Requisitos y Dependencias](#3-requisitos-y-dependencias)
4. [Configuracion](#4-configuracion)
5. [Base de Datos](#5-base-de-datos)
6. [Modulos de la Aplicacion](#6-modulos-de-la-aplicacion)
7. [Aplicacion Web (FastAPI)](#7-aplicacion-web-fastapi)
8. [Frontend](#8-frontend)
9. [Scripts Automatizados (Cron)](#9-scripts-automatizados-cron)
10. [Scripts de Inicializacion](#10-scripts-de-inicializacion)
11. [Flujo de Datos](#11-flujo-de-datos)
12. [Parametros de Weinstein](#12-parametros-de-weinstein)
13. [Autenticacion](#13-autenticacion)
14. [Despliegue en Produccion](#14-despliegue-en-produccion)
15. [Logs y Monitorizacion](#15-logs-y-monitorizacion)
16. [Seguridad](#16-seguridad)

---

## 1. Descripcion General

Sistema de analisis tecnico basado en la metodologia de las 4 etapas de Stan Weinstein. Monitoriza ~396 acciones de distintos mercados (NASDAQ, NYSE, BME), detecta automaticamente la etapa en la que se encuentra cada accion, genera senales de compra/venta y las notifica via Telegram.

**Stack tecnologico:**
- **Backend:** Python 3.11 + FastAPI
- **Base de datos:** MariaDB/MySQL + SQLAlchemy ORM
- **Fuentes de datos:** TwelveData (primario), yfinance (respaldo)
- **Notificaciones:** Telegram Bot API
- **Frontend:** Jinja2 + JavaScript + Lightweight Charts (TradingView)
- **Servidor ASGI:** Uvicorn
- **Proxy inverso:** Apache con mod_proxy

**Metodologia Weinstein - Las 4 etapas:**
- **Etapa 1 - Base/Consolidacion:** Precio cerca de la MA30, MA30 plana
- **Etapa 2 - Tendencia Alcista:** Precio por encima de MA30, MA30 subiendo
- **Etapa 3 - Techo/Distribucion:** Precio cerca de MA30, MA30 aplanandose (tras Etapa 2)
- **Etapa 4 - Tendencia Bajista:** Precio por debajo de MA30, MA30 bajando

---

## 2. Estructura del Proyecto

```
stanweinstein/
├── app/                            # Modulos de la aplicacion
│   ├── __init__.py
│   ├── auth.py                     # Autenticacion (bcrypt)
│   ├── config.py                   # Credenciales y parametros (NO en git)
│   ├── config.example.py           # Plantilla de configuracion
│   ├── database.py                 # Modelos ORM (SQLAlchemy)
│   ├── data_collector.py           # Descarga de datos OHLCV
│   ├── aggregator.py               # Agregacion diaria→semanal + MA30
│   ├── analyzer.py                 # Deteccion de etapas Weinstein
│   └── signals.py                  # Generacion de senales BUY/SELL
├── scripts/                        # Scripts de cron y utilidades
│   ├── daily_update.py             # Actualizacion diaria (cron L-V)
│   ├── weekly_process.py           # Proceso semanal (cron sabado)
│   ├── telegram_bot.py             # Notificaciones Telegram (NO en git)
│   ├── init_historical.py          # Carga inicial historica
│   ├── init_weekly_aggregation.py  # Agregacion historica inicial
│   ├── analyze_initial.py          # Analisis historico inicial
│   ├── load_stocks_from_csv.py     # Carga acciones desde CSV
│   ├── load_missing_historical.py  # Carga datos faltantes
│   └── backtest_*.py               # Scripts de backtesting
├── web/                            # Aplicacion web
│   ├── main.py                     # FastAPI: rutas, API, middleware
│   ├── static/
│   │   ├── style.css               # Estilos CSS
│   │   ├── favicon.svg             # Icono de velas japonesas
│   │   ├── dashboard.js            # Logica del dashboard
│   │   ├── stocks.js               # Logica de lista de acciones
│   │   ├── signals.js              # Logica de senales
│   │   ├── stock_detail.js         # Logica de detalle + grafico velas
│   │   ├── watchlist.js            # Logica de watchlist
│   │   ├── admin.js                # Logica CRUD de acciones
│   │   └── table-sort.js           # Ordenacion de tablas
│   └── templates/
│       ├── login.html              # Pagina de login
│       ├── dashboard.html          # Dashboard principal
│       ├── stocks.html             # Lista de acciones
│       ├── stock_detail.html       # Detalle de accion (velas japonesas)
│       ├── signals.html            # Historial de senales
│       ├── watchlist.html          # Watchlist (Etapa 2)
│       └── admin.html              # Administracion (cambio contrasena)
├── data/
│   └── auth.json                   # Hash de contrasena (NO en git)
├── database_schema.sql             # Esquema de la base de datos
├── cleanup_stocks.sql              # Script de limpieza de datos
├── crontab                         # Configuracion de tareas programadas
├── requirements.txt                # Dependencias Python
├── .gitignore                      # Ficheros excluidos de git
└── DOCUMENTACION_TECNICA.md        # Este documento
```

---

## 3. Requisitos y Dependencias

### Requisitos del sistema
- Python 3.11+
- MariaDB/MySQL
- Apache con mod_proxy (produccion)
- Acceso a internet (APIs de datos financieros)

### Dependencias Python principales

| Paquete | Version | Funcion |
|---------|---------|---------|
| fastapi | 0.109.0 | Framework web |
| uvicorn | 0.27.0 | Servidor ASGI |
| SQLAlchemy | 2.0.25 | ORM para base de datos |
| PyMySQL | 1.1.0 | Conector MySQL |
| pandas | 2.2.0 | Manipulacion de datos |
| twelvedata | 1.2.28 | API de datos financieros (primaria) |
| yfinance | 0.2.35 | API Yahoo Finance (respaldo) |
| python-telegram-bot | 20.7 | Notificaciones Telegram |
| bcrypt | 5.0.0 | Hashing de contrasenas |
| itsdangerous | 2.2.0 | Firma de cookies de sesion |
| python-multipart | 0.0.22 | Procesamiento de formularios |
| Jinja2 | 3.1.3 | Motor de plantillas |

### Instalacion de dependencias

```bash
cd /home/stanweinstein
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Configuracion

### Fichero: `app/config.py`

Este fichero contiene credenciales y parametros. No se incluye en git. Usar `app/config.example.py` como plantilla.

```python
# Base de datos
DB_CONFIG = {
    'host': 'localhost',
    'user': 'stanweinstein',
    'password': '...',
    'database': 'stanweinstein',
    'charset': 'utf8mb4'
}

# APIs
TWELVEDATA_API_KEY = "..."
TELEGRAM_BOT_TOKEN = "..."
TELEGRAM_CHAT_ID = "..."

# Fuentes de datos (orden de prioridad)
DATA_SOURCES = ['twelvedata', 'yfinance']

# Rate limiting
RATE_LIMIT_DELAY = 2      # segundos entre peticiones API
MAX_RETRIES = 3            # intentos maximos
RETRY_DELAY = 5            # segundos entre reintentos

# Parametros de analisis Weinstein
MIN_WEEKS_FOR_ANALYSIS = 35
VOLUME_SPIKE_THRESHOLD = 1.5
MA30_SLOPE_THRESHOLD = 0.02
TRADING_DAYS_PER_WEEK = 5
```

### Variable de entorno: `BASE_PATH`

Controla el prefijo de URL para la aplicacion web:
- **Produccion:** `BASE_PATH=/sw` (detras del proxy Apache)
- **Desarrollo:** sin definir (se usa vacio por defecto)

---

## 5. Base de Datos

### Esquema (fichero: `database_schema.sql`)

#### Tabla `stocks` - Acciones monitorizadas

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | INT, PK | Identificador |
| ticker | VARCHAR(20), UNIQUE | Simbolo (ej: AAPL, SAN.MC) |
| name | VARCHAR(255) | Nombre de la empresa |
| exchange | VARCHAR(50) | Mercado (NASDAQ, NYSE, BME) |
| active | BOOLEAN | Si se monitoriza activamente |
| created_at | TIMESTAMP | Fecha de creacion |

#### Tabla `daily_data` - Datos diarios OHLCV

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | BIGINT, PK | Identificador |
| stock_id | INT, FK | Referencia a stocks |
| date | DATE | Fecha |
| open, high, low, close | DECIMAL(12,4) | Precios OHLC |
| volume | BIGINT | Volumen |

Indice unico: `(stock_id, date)`

#### Tabla `weekly_data` - Datos semanales + analisis

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | BIGINT, PK | Identificador |
| stock_id | INT, FK | Referencia a stocks |
| week_end_date | DATE | Viernes de la semana |
| open, high, low, close | DECIMAL(12,4) | Precios OHLC semanales |
| volume | BIGINT | Volumen acumulado |
| ma30 | DECIMAL(12,4) | Media movil de 30 semanas |
| ma30_slope | DECIMAL(8,4) | Pendiente de la MA30 |
| stage | TINYINT | Etapa Weinstein (1-4) |

Indice unico: `(stock_id, week_end_date)`

#### Tabla `signals` - Senales de trading

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | BIGINT, PK | Identificador |
| stock_id | INT, FK | Referencia a stocks |
| signal_date | DATE | Fecha de la senal |
| signal_type | ENUM | BUY, SELL, STAGE_CHANGE |
| stage_from | TINYINT | Etapa de origen |
| stage_to | TINYINT | Etapa de destino |
| price | DECIMAL(12,4) | Precio en el momento |
| ma30 | DECIMAL(12,4) | MA30 en el momento |
| notified | BOOLEAN | Si se ha notificado via Telegram |

---

## 6. Modulos de la Aplicacion

### 6.1 `app/database.py` - Modelos ORM

Define la conexion a MariaDB y los modelos SQLAlchemy.

**Clases ORM:** `Stock`, `DailyData`, `WeeklyData`, `Signal`

**Funciones:**
- `init_db()` - Crea todas las tablas
- `get_db()` - Dependency de FastAPI para obtener sesion
- `test_connection()` - Verifica conectividad

**Pool de conexiones:**
- Tamano: 5 conexiones
- Overflow maximo: 10
- Reciclaje: cada 3600 segundos

### 6.2 `app/data_collector.py` - Descarga de datos

Clase `DataCollector` que gestiona la obtencion de datos OHLCV.

**Fuentes de datos con fallback automatico:**
1. TwelveData (primario)
2. yfinance (respaldo)

**Metodos principales:**
- `download_stock_data(ticker, start_date, end_date)` - Descarga con fallback
- `save_daily_data(stock_id, ticker, data_dict)` - Guarda en BD
- `load_historical_data(ticker, years=2)` - Carga historico completo
- `update_daily_data(ticker, days_back=5)` - Actualiza ultimos dias

**Conversion de tickers entre formatos:**
- Yahoo Finance: `SAN.MC` (punto + sufijo de mercado)
- TwelveData: `SAN:BME` (dos puntos + codigo de bolsa)

### 6.3 `app/aggregator.py` - Agregacion semanal

Clase `WeeklyAggregator` que transforma datos diarios en semanales.

**Proceso de agregacion:**
- Open: apertura del primer dia de la semana
- High: maximo de la semana
- Low: minimo de la semana
- Close: cierre del ultimo dia
- Volume: suma de la semana

**Calculo de MA30:**
- Media movil simple de los ultimos 30 cierres semanales
- Pendiente (slope) = `(MA30_actual - MA30_anterior) / MA30_anterior`

**Metodos principales:**
- `aggregate_stock_weekly_data(stock_id, weeks_back=4)` - Agrega una accion
- `aggregate_all_stocks(weeks_back=4)` - Agrega todas
- `calculate_ma30(stock_id, current_week_end)` - Calcula MA30
- `calculate_ma30_slope(stock_id, current_week_end)` - Calcula pendiente
- `get_week_end_date(date)` - Devuelve el viernes de la semana

### 6.4 `app/analyzer.py` - Deteccion de etapas

Clase `WeinsteinAnalyzer` que implementa la logica de clasificacion por etapas.

**Logica de deteccion:**

```
Etapa 2: precio > MA30 Y pendiente > +2%
Etapa 4: precio < MA30 Y pendiente < -2%
Etapa 3: (precio cerca o encima de MA30) Y pendiente plana Y etapa_anterior == 2
Etapa 1: (precio cerca o debajo de MA30) Y (pendiente plana o bajando)
```

**Metodos principales:**
- `detect_stage(weekly_data, previous_stage)` - Detecta etapa de una semana
- `analyze_stock_stages(stock_id, weeks_back=10)` - Analiza una accion
- `analyze_all_stocks(weeks_back=10)` - Analiza todas
- `get_stocks_by_stage(stage)` - Lista acciones en una etapa

### 6.5 `app/signals.py` - Generacion de senales

Clase `SignalGenerator` que detecta transiciones entre etapas.

**Tipos de senal:**
- **BUY:** Etapa 1 → 2 (ruptura alcista)
- **SELL:** Etapa 2 → 4 o Etapa 3 → 4 (ruptura bajista)
- **STAGE_CHANGE:** Cualquier otra transicion

**Metodos principales:**
- `detect_stage_change(stock_id, current_week, previous_week)` - Detecta cambio
- `classify_signal(stage_from, stage_to)` - Clasifica tipo de senal
- `generate_signals_for_all_stocks(weeks_back=10)` - Genera para todas
- `get_unnotified_signals()` - Obtiene senales pendientes de notificar
- `mark_signals_as_notified(signal_ids)` - Marca como notificadas

### 6.6 `app/auth.py` - Autenticacion

Gestion de contrasena con hash bcrypt almacenado en fichero JSON.

**Fichero:** `data/auth.json`
**Contrasena por defecto:** `Weinstein` (se crea automaticamente si no existe el fichero)

**Funciones:**
- `verify_password(password)` - Verifica contra el hash almacenado
- `save_password(password)` - Genera hash y guarda nueva contrasena
- `get_password_hash()` - Lee el hash del fichero
- `_ensure_auth_file()` - Crea fichero con contrasena por defecto si no existe

---

## 7. Aplicacion Web (FastAPI)

### Fichero: `web/main.py`

### Autenticacion y Middleware

La aplicacion usa sesiones con cookie firmada:

1. `SessionMiddleware` (Starlette) - Gestiona la cookie de sesion
2. `AuthMiddleware` (custom) - Redirige a `/login` si no hay sesion activa

**Rutas publicas** (sin autenticacion): `/login`, `/static/*`

### Paginas HTML

| Ruta | Template | Descripcion |
|------|----------|-------------|
| `/login` | login.html | Formulario de contrasena |
| `/` | dashboard.html | Dashboard principal con estadisticas |
| `/stocks` | stocks.html | Lista de acciones con filtros y busqueda |
| `/stock/{ticker}` | stock_detail.html | Detalle de accion con grafico |
| `/signals` | signals.html | Historial de senales BUY/SELL |
| `/watchlist` | watchlist.html | Acciones en Etapa 2 ordenadas por fuerza |
| `/admin` | admin.html | Cambio de contrasena |
| `/logout` | - | Cierra sesion y redirige a login |

### Endpoints API (JSON)

| Endpoint | Parametros | Descripcion |
|----------|------------|-------------|
| `GET /api/dashboard/stats` | - | Estadisticas: total acciones, distribucion por etapas, senales recientes, acciones no actualizadas (diario/semanal) |
| `GET /api/stocks` | stage, search, limit, offset | Lista paginada de acciones con filtros |
| `GET /api/stock/{ticker}` | - | Detalle completo: metricas, historial 104 semanas (OHLC), senales |
| `GET /api/signals` | signal_type, days, limit | Senales recientes con filtros |
| `GET /api/watchlist` | - | Acciones en Etapa 2 ordenadas por pendiente MA30 |
| `GET /api/health` | - | Estado del servicio |

---

## 8. Frontend

### JavaScript

Cada pagina tiene su fichero JS que consume la API y actualiza el DOM:

- **dashboard.js** - Carga estadisticas de `/api/dashboard/stats`, muestra distribucion por etapas, senales recientes, top acciones en Etapa 2 e indicadores de acciones no actualizadas (badges verde/amarillo para datos diarios y semanales)
- **stocks.js** - Filtrado por etapa, busqueda por ticker/nombre, paginacion
- **stock_detail.js** - Grafico de velas japonesas (OHLC) con MA30 superpuesta usando Lightweight Charts, periodos seleccionables (6M, 1Y, 2Y, Todo), historial de etapas y senales
- **signals.js** - Filtros por tipo (BUY/SELL) y periodo (30/90/180/365 dias)
- **watchlist.js** - Carga acciones en Etapa 2 desde `/api/watchlist`
- **table-sort.js** - Ordenacion de tablas haciendo click en las cabeceras

### Estilos CSS (`style.css`)

Colores por etapa:
- Etapa 1 (Base): Gris `#6c757d`
- Etapa 2 (Alcista): Verde `#28a745`
- Etapa 3 (Techo): Ambar `#ffc107`
- Etapa 4 (Bajista): Rojo `#dc3545`

Diseno responsive con grid layout y tarjetas.

---

## 9. Scripts Automatizados (Cron)

### Fichero: `crontab`

```
# Actualizacion diaria - Lunes a Viernes 23:00
0 23 * * 1-5 python /home/stanweinstein/scripts/daily_update.py

# Proceso semanal - Sabado 01:00
0 1 * * 6 python /home/stanweinstein/scripts/weekly_process.py

# Notificaciones Telegram - Sabado 08:00
0 8 * * 6 python /home/stanweinstein/scripts/telegram_bot.py --notify
```

### `scripts/daily_update.py` - Actualizacion diaria

**Cuando:** Lunes a Viernes a las 23:00
**Que hace:**
1. Obtiene la lista de acciones activas
2. Para cada accion, descarga los ultimos 5 dias de datos
3. Inserta o actualiza registros en `daily_data`
4. Aplica rate limiting entre peticiones a la API

**Log:** `/var/log/stanweinstein/daily_update.log`

### `scripts/weekly_process.py` - Proceso semanal

**Cuando:** Sabados a la 01:00
**Que hace (3 fases):**
1. **Fase 1 - Agregacion:** Convierte datos diarios en semanales, calcula MA30 y su pendiente
2. **Fase 2 - Analisis:** Detecta la etapa Weinstein de cada accion
3. **Fase 3 - Senales:** Genera senales BUY/SELL por cambios de etapa

**Log:** `/var/log/stanweinstein/weekly_process.log`

### `scripts/telegram_bot.py` - Notificaciones

**Cuando:** Sabados a las 08:00
**Que hace:**
1. Consulta senales no notificadas
2. Formatea mensaje para cada senal
3. Envia via Telegram Bot API
4. Marca las senales como notificadas

---

## 10. Scripts de Inicializacion

Estos scripts se ejecutan una sola vez para la puesta en marcha:

| Script | Funcion |
|--------|---------|
| `init_historical.py` | Carga 2 anos de datos historicos para todas las acciones |
| `init_weekly_aggregation.py` | Agrega todo el historico diario a semanal |
| `analyze_initial.py` | Detecta etapas para todo el historico |
| `load_stocks_from_csv.py` | Carga lista de acciones desde fichero CSV |
| `load_missing_historical.py` | Carga datos faltantes para acciones sin historico |

**Orden de ejecucion para puesta en marcha:**
1. Crear la base de datos con `database_schema.sql`
2. Configurar `app/config.py` con credenciales
3. `load_stocks_from_csv.py` (cargar lista de acciones)
4. `init_historical.py` (descargar historico)
5. `init_weekly_aggregation.py` (agregar a semanal)
6. `analyze_initial.py` (detectar etapas)

---

## 11. Flujo de Datos

```
┌─────────────────────────────────────────────────────┐
│          ACTUALIZACION DIARIA (L-V 23:00)           │
│                                                     │
│  TwelveData/yfinance → daily_data (ultimos 5 dias)  │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│           PROCESO SEMANAL (Sab 01:00)               │
│                                                     │
│  Fase 1: daily_data → weekly_data (OHLCV + MA30)   │
│  Fase 2: weekly_data → stage (etapa 1-4)           │
│  Fase 3: stage changes → signals (BUY/SELL)        │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│          NOTIFICACIONES (Sab 08:00)                 │
│                                                     │
│  signals (notified=false) → Telegram → notified=true │
└─────────────────────────────────────────────────────┘
```

---

## 12. Parametros de Weinstein

| Parametro | Valor | Descripcion |
|-----------|-------|-------------|
| `MIN_WEEKS_FOR_ANALYSIS` | 35 | Semanas minimas para analizar (30 para MA30 + 5 margen) |
| `MA30_SLOPE_THRESHOLD` | 0.02 (2%) | Cambio minimo para considerar tendencia |
| `PRICE_MA30_THRESHOLD` | 0.05 (5%) | Distancia maxima para considerar "cerca de MA30" |
| `VOLUME_SPIKE_THRESHOLD` | 1.5 (150%) | Umbral de pico de volumen |
| `RATE_LIMIT_DELAY` | 2 seg | Pausa entre peticiones API |
| `MAX_RETRIES` | 3 | Reintentos maximos por peticion |
| `RETRY_DELAY` | 5 seg | Pausa entre reintentos |

---

## 13. Autenticacion

### Flujo

1. El usuario accede a cualquier ruta
2. El middleware `AuthMiddleware` comprueba si hay sesion activa
3. Sin sesion → redirige a `/login`
4. Introduce la contrasena → se verifica contra hash bcrypt → crea sesion
5. Con sesion activa → accede normalmente
6. "Salir" → destruye sesion → redirige a `/login`

### Almacenamiento

- La contrasena se almacena como hash bcrypt en `data/auth.json`
- Si el fichero no existe, se crea automaticamente con la contrasena por defecto `Weinstein`
- El cambio de contrasena se realiza desde la pagina `/admin`

### Cookie de sesion

- Firmada con `itsdangerous` via `SessionMiddleware` de Starlette
- Secret key definida en `web/main.py`

---

## 14. Despliegue en Produccion

### Rutas

| Elemento | Ruta |
|----------|------|
| Aplicacion | `/home/stanweinstein/` |
| Entorno virtual | `/home/stanweinstein/venv/` |
| Logs | `/var/log/stanweinstein/` |
| Contrasena auth | `/home/stanweinstein/data/auth.json` |

### Servicio systemd

Fichero: `/etc/systemd/system/stanweinstein.service`

```ini
[Unit]
Description=Stan Weinstein Trading System - FastAPI Application
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=stanweinstein
Group=stanweinstein
WorkingDirectory=/home/stanweinstein
Environment="PATH=/home/stanweinstein/venv/bin"
Environment="BASE_PATH=/sw"
ExecStart=/home/stanweinstein/venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=append:/var/log/stanweinstein/app.log
StandardError=append:/var/log/stanweinstein/app_error.log

[Install]
WantedBy=multi-user.target
```

**Comandos utiles:**
```bash
sudo systemctl start stanweinstein
sudo systemctl stop stanweinstein
sudo systemctl restart stanweinstein
sudo systemctl status stanweinstein
sudo journalctl -u stanweinstein -n 50 --no-pager
```

### Apache (proxy inverso)

Fichero: `/etc/httpd/conf.d/sw.conf`

```apache
<Location /sw>
    ProxyPass http://127.0.0.1:8000
    ProxyPassReverse http://127.0.0.1:8000
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Prefix "/sw"
    ProxyPreserveHost On
</Location>
```

La aplicacion es accesible en `https://<dominio>/sw/`

### Crontab

Configurado para el usuario `stanweinstein`:
```bash
sudo crontab -u stanweinstein -e
```

### Actualizacion del codigo

```bash
cd /home/stanweinstein
git pull
# Si hay nuevas dependencias:
venv/bin/pip install -r requirements.txt
# Reiniciar servicio:
sudo systemctl restart stanweinstein
```

---

## 15. Logs y Monitorizacion

### Ficheros de log

| Fichero | Contenido |
|---------|-----------|
| `/var/log/stanweinstein/app.log` | Salida de uvicorn (peticiones HTTP) |
| `/var/log/stanweinstein/app_error.log` | Errores de la aplicacion web |
| `/var/log/stanweinstein/daily_update.log` | Proceso de actualizacion diaria |
| `/var/log/stanweinstein/weekly_process.log` | Proceso semanal (agregacion+analisis+senales) |
| `/var/log/stanweinstein/cron.log` | Salida general de cron |

### Verificacion del estado

```bash
# Estado del servicio
sudo systemctl status stanweinstein

# Health check
curl http://127.0.0.1:8000/api/health

# Ultimos errores
tail -50 /var/log/stanweinstein/app_error.log

# Ultimo proceso semanal
tail -50 /var/log/stanweinstein/weekly_process.log
```

---

## 16. Seguridad

### Ficheros sensibles (excluidos de git)

| Fichero | Contenido |
|---------|-----------|
| `app/config.py` | Credenciales de BD, API keys, token Telegram |
| `scripts/telegram_bot.py` | Token del bot de Telegram |
| `data/auth.json` | Hash de la contrasena de acceso web |

### Consideraciones

- La contrasena de acceso web se almacena como hash bcrypt (no en texto plano)
- Las credenciales de base de datos y API keys estan en `config.py` en texto plano
- La aplicacion web solo escucha en `127.0.0.1` (no accesible desde fuera sin proxy)
- La cookie de sesion esta firmada pero no cifrada
- Los endpoints API no tienen autenticacion propia (dependen del middleware de sesion)
