# Sistema Weinstein v0.3

Sistema automatizado de análisis técnico basado en la metodología de Stan Weinstein para detectar las 4 etapas del mercado y generar señales de trading.

## 🎯 Características

### Análisis Técnico
- **396 acciones monitorizadas** (S&P 500 + empresas relevantes)
- **Análisis semanal** automático
- **Detección de 4 etapas** de Weinstein
- **Media móvil de 30 semanas** (MA30) como indicador principal
- **Generación automática** de señales BUY/SELL

### Dashboard Web Completo
- **5 páginas interactivas** con FastAPI
- **Ordenación por columnas** en todas las tablas
- **Gráficos interactivos** con selector de período (6M/1A/2A/Todo)
- **Búsqueda y filtros** en tiempo real
- **Diseño responsive**

### Automatización
- **Cron semanal** (sábados)
- **Notificaciones Telegram**
- **Base de datos MariaDB**

## 📊 Metodología Weinstein

### Las 4 Etapas

1. **Etapa 1 - Base/Consolidación**: Precio lateral, preparación
2. **Etapa 2 - Alcista** ⭐: Breakout por encima de MA30 → 🟢 **COMPRA**
3. **Etapa 3 - Techo/Distribución**: Pérdida de impulso
4. **Etapa 4 - Bajista**: Break por debajo de MA30 → 🔴 **VENTA**

## 🚀 Instalación Rápida

```bash
# 1. Clonar repositorio
git clone https://github.com/tuusuario/stanweinstein.git
cd stanweinstein

# 2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar base de datos
mysql -u root -p < schema.sql

# 5. Configurar credenciales
cp config.py.example config.py
nano config.py

# 6. Ejecutar actualización inicial
python update_stocks.py

# 7. Iniciar dashboard web
cd web
uvicorn main:app --host 127.0.0.1 --port 8000
```

Ver `INSTALACION_WEB.md` para configuración completa del dashboard.

## 🌐 Dashboard Web

### Páginas disponibles

1. **Dashboard** (`/sw`): Resumen general y señales recientes
2. **Acciones** (`/sw/stocks`): Lista completa con búsqueda y filtros
3. **Señales** (`/sw/signals`): Historial de señales BUY/SELL
4. **Watchlist** (`/sw/watchlist`): Acciones en Etapa 2
5. **Detalle** (`/sw/stock/{TICKER}`): Gráfico interactivo y análisis

### Funcionalidades

✅ **Ordenación de tablas**: Click en cualquier header  
✅ **Selector de período**: 6M, 1A, 2A, Todo  
✅ **Búsqueda en tiempo real**  
✅ **Filtros por etapa y tipo**  
✅ **Paginación automática**

## 📁 Estructura

```
stanweinstein/
├── app/                    # Modelos y configuración
├── analyzer.py             # Motor de análisis
├── signal_generator.py     # Generador de señales
├── update_stocks.py        # Script de actualización
├── telegram_bot.py.example # Plantilla del bot
├── web/
│   ├── main.py            # FastAPI app
│   ├── templates/         # HTML
│   └── static/            # CSS/JS
│       ├── table-sort.js  # Ordenación de tablas
│       └── *.js          # Lógica de páginas
├── requirements.txt
├── README.md
└── .gitignore
```

## 🔐 Seguridad

**Archivos NO incluidos en Git:**
- `config.py`
- `telegram_bot.py`
- `*.log`

**Usar plantillas:**
- `config.py.example`
- `telegram_bot.py.example`

## 📈 Uso

### Actualización manual

```bash
python update_stocks.py
```

### Acceder al dashboard

```
https://tudominio.com/sw
```

### Ordenar tablas

- **Click**: Ascendente ↑
- **2º click**: Descendente ↓
- **3º click**: Original ↕

### Cambiar período del gráfico

Click en botones: **6M** | **1A** | **2A** | **Todo**

## 🛠️ Mantenimiento

```bash
# Ver logs
tail -f logs/update.log
sudo journalctl -u weinstein-web -f

# Backup BD
mysqldump -u usuario -p weinstein_db > backup.sql

# Actualizar
git pull
pip install -r requirements.txt
sudo systemctl restart weinstein-web
```

## 🐛 Solución de problemas

### Ordenación no funciona
```bash
# Verificar table-sort.js existe
ls -la web/static/table-sort.js

# Verificar HTML lo carga
grep "table-sort" web/templates/*.html

# Limpiar caché navegador
Ctrl + Shift + R
```

### Dashboard no carga estilos
```bash
# Verificar archivos
ls -la web/static/

# Limpiar caché
Ctrl + Shift + Delete
```

## 📚 Referencias

- **Libro**: "Secrets for Profiting in Bull and Bear Markets" - Stan Weinstein
- **Datos**: Yahoo Finance API
- **Web**: FastAPI + Chart.js

## ⚖️ Licencia

Proyecto educativo. No constituye asesoramiento financiero.

---

**📊 Estadísticas**: 396 acciones | Actualización semanal | Señales automáticas

**⚠️ DISCLAIMER**: Solo fines educativos. Opera bajo tu propio riesgo.
