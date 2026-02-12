# Instalación del Dashboard Web - Sistema Weinstein

Guía completa para instalar y configurar el dashboard web del Sistema Weinstein.

## 📋 Requisitos Previos

- Python 3.9+
- MariaDB/MySQL configurado con el schema del proyecto
- Apache 2.4+ (para producción)
- Sistema base del proyecto funcionando

## 📦 Dependencias

El dashboard web requiere estas librerías adicionales:

```bash
fastapi==0.109.0
uvicorn[standard]==0.27.0
jinja2==3.1.3
python-multipart==0.0.6
```

Instalar con:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

## 📁 Estructura del Dashboard

```
stanweinstein/
└── web/
    ├── main.py                 # FastAPI application
    ├── templates/              # Plantillas HTML
    │   ├── dashboard.html      # Página principal
    │   ├── stocks.html         # Lista de acciones
    │   ├── signals.html        # Historial de señales
    │   ├── watchlist.html      # Watchlist Etapa 2
    │   └── stock_detail.html   # Detalle de acción
    └── static/                 # Archivos estáticos
        ├── style.css           # Estilos CSS
        ├── table-sort.js       # Librería de ordenación
        ├── dashboard.js        # Lógica dashboard
        ├── stocks.js           # Lógica stocks
        ├── signals.js          # Lógica signals
        ├── watchlist.js        # Lógica watchlist
        └── stock_detail.js     # Lógica detalle
```

## 🚀 Instalación

### 1. Verificar archivos del proyecto

```bash
cd /home/stanweinstein

# Verificar estructura web/
ls -la web/
ls -la web/templates/
ls -la web/static/
```

**Archivos requeridos en `web/static/`:**
- ✅ style.css
- ✅ table-sort.js
- ✅ dashboard.js
- ✅ stocks.js
- ✅ signals.js
- ✅ watchlist.js
- ✅ stock_detail.js

**Archivos requeridos en `web/templates/`:**
- ✅ dashboard.html
- ✅ stocks.html
- ✅ signals.html
- ✅ watchlist.html
- ✅ stock_detail.html

### 2. Configurar main.py

El archivo `web/main.py` debe tener configurado el `root_path="/sw"`:

```python
app = FastAPI(
    title="Sistema Weinstein",
    root_path="/sw"  # IMPORTANTE: para subdirectorio Apache
)
```

Y todas las respuestas de templates deben pasar `base_path="/sw"`:

```python
return templates.TemplateResponse("dashboard.html", {
    "request": request,
    "base_path": "/sw"  # Hardcoded para Apache
})
```

### 3. Verificar IDs de tablas en HTML

**IMPORTANTE**: Los IDs deben estar en el elemento `<table>`, NO en `<tbody>`:

```html
<!-- ✅ CORRECTO -->
<table id="stocks-table">
    <thead>...</thead>
    <tbody id="stocks-tbody">...</tbody>
</table>

<!-- ❌ INCORRECTO -->
<table>
    <thead>...</thead>
    <tbody id="stocks-table">...</tbody>
</table>
```

### 4. Verificar que JS busca tbody correcto

En cada archivo JS (`stocks.js`, `signals.js`, `watchlist.js`, `dashboard.js`):

```javascript
// Buscar el TBODY para insertar filas
const tbody = document.getElementById('stocks-tbody'); // NO 'stocks-table'

// Inicializar ordenación en la TABLA
initTableSort('stocks-table', [...]);  // NO 'stocks-tbody'
```

## ⚙️ Configuración de Desarrollo

### Ejecutar en local

```bash
cd /home/stanweinstein/web
source ../venv/bin/activate

# Iniciar servidor de desarrollo
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Acceder en navegador
http://localhost:8000/
```

**Nota**: En desarrollo, acceder directamente a `http://localhost:8000/` (sin `/sw`)

## 🌐 Configuración de Producción

### 1. Crear servicio systemd

Crear archivo `/etc/systemd/system/weinstein-web.service`:

```ini
[Unit]
Description=Sistema Weinstein Web Dashboard
After=network.target mariadb.service

[Service]
Type=simple
User=stanweinstein
Group=stanweinstein
WorkingDirectory=/home/stanweinstein
Environment="PATH=/home/stanweinstein/venv/bin"
ExecStart=/home/stanweinstein/venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activar servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable weinstein-web
sudo systemctl start weinstein-web
sudo systemctl status weinstein-web
```

### 2. Configurar Apache como proxy

Crear archivo `/etc/httpd/conf.d/sw.conf`:

```apache
<Location /sw>
    ProxyPass http://127.0.0.1:8000
    ProxyPassReverse http://127.0.0.1:8000
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Prefix "/sw"
    ProxyPreserveHost On
</Location>
```

Habilitar módulos necesarios:

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
sudo systemctl restart httpd
```

### 3. Verificar configuración

```bash
# Ver logs del servicio
sudo journalctl -u weinstein-web -f

# Verificar que está escuchando
sudo netstat -tlnp | grep 8000

# Verificar Apache
sudo apachectl configtest
sudo systemctl status httpd
```

### 4. Acceder al dashboard

```
https://www.tudominio.com:8443/sw
```

## 🎨 Funcionalidades del Dashboard

### 1. Dashboard Principal (`/sw`)

**Características:**
- Estadísticas generales (total acciones, señales semanales, Etapa 2)
- Distribución por etapas (4 cards con %)
- Top 10 acciones Etapa 2 (ordenable)
- Últimas 5 señales BUY (ordenable)
- Última actualización

**Ordenación:**
- Click en headers de tabla para ordenar
- Soporta: Ticker, Nombre, Fecha, Tipo, Precio, Pendiente

### 2. Lista de Acciones (`/sw/stocks`)

**Características:**
- Búsqueda en tiempo real (ticker o nombre)
- Filtros por etapa (All, 1, 2, 3, 4)
- Paginación (50 acciones por página)
- 7 columnas ordenables
- Contador de resultados

**Columnas ordenables:**
- Ticker, Nombre, Exchange, Etapa, Precio, MA30, Pendiente MA30

### 3. Señales (`/sw/signals`)

**Características:**
- Filtro por tipo (All, BUY, SELL)
- Filtro por período (30, 90, 180, 365 días)
- Estadísticas (Total, BUY, SELL)
- Límite 100 señales
- 7 columnas ordenables

**Columnas ordenables:**
- Fecha, Ticker, Nombre, Tipo, Transición, Precio, MA30

### 4. Watchlist (`/sw/watchlist`)

**Características:**
- Solo acciones en Etapa 2
- Ordenado por pendiente MA30 (más fuerte primero)
- 7 columnas ordenables
- Contador total Etapa 2

**Columnas ordenables:**
- #, Ticker, Nombre, Precio, MA30, Distancia MA30, Pendiente MA30

### 5. Detalle de Acción (`/sw/stock/{TICKER}`)

**Características:**
- Información actual (6 stats cards)
- **Gráfico interactivo** con Chart.js:
  - Selector de período: **6M** | **1A** | **2A** | **Todo**
  - Botón activo resaltado (fondo azul)
  - Precio con fondo coloreado por etapa
  - Línea MA30 (naranja, discontinua)
  - Tooltips interactivos
- Señales generadas (historial completo)
- Historial de cambios de etapa (últimos 10)

**Selector de período:**
- **6M**: 26 semanas (6 meses)
- **1A**: 52 semanas (1 año) - Por defecto
- **2A**: 104 semanas (2 años)
- **Todo**: Histórico completo

## 🔧 Ordenación de Tablas

### Implementación

La ordenación se implementa con `table-sort.js`:

1. **Añadir ID a la tabla**:
```html
<table id="stocks-table">
```

2. **Inicializar en JavaScript**:
```javascript
initTableSort('stocks-table', [
    { index: 0, type: 'string' },   // Ticker
    { index: 1, type: 'string' },   // Nombre
    { index: 2, type: 'date' },     // Fecha
    { index: 3, type: 'currency' }, // Precio
    { index: 4, type: 'percentage' } // Pendiente
]);
```

3. **Llamar dentro de requestAnimationFrame**:
```javascript
requestAnimationFrame(() => {
    if (typeof initTableSort === 'function') {
        initTableSort('stocks-table', [...]);
    }
});
```

### Tipos soportados

- `string`: Texto alfabético
- `number`: Números enteros/decimales
- `currency`: Monedas ($)
- `percentage`: Porcentajes (%)
- `date`: Fechas

### Indicadores visuales

- **↕**: Columna sin ordenar (gris, opacidad 0.3)
- **↑**: Ordenado ascendente (azul)
- **↓**: Ordenado descendente (azul)
- **Hover**: Fondo gris claro

## 🐛 Solución de Problemas

### 1. Ordenación no funciona

**Problema**: No aparecen flechitas en los headers

**Diagnóstico:**
```bash
# Verificar que table-sort.js existe
ls -la /home/stanweinstein/web/static/table-sort.js

# Verificar que HTML lo carga
grep "table-sort.js" /home/stanweinstein/web/templates/*.html
```

**Solución:**
- Verificar que `table-sort.js` se carga **ANTES** que otros JS
- Limpiar caché del navegador (Ctrl+Shift+R)
- Verificar consola del navegador (F12) para errores

### 2. Headers de tabla desaparecen

**Problema**: Al cargar datos, desaparecen los headers

**Causa**: ID está en `<tbody>` en lugar de `<table>`

**Solución:**
```html
<!-- ANTES (incorrecto) -->
<table>
    <thead>...</thead>
    <tbody id="stocks-table">

<!-- DESPUÉS (correcto) -->
<table id="stocks-table">
    <thead>...</thead>
    <tbody id="stocks-tbody">
```

Y en JavaScript:
```javascript
// Cambiar
const tbody = document.getElementById('stocks-table');
// Por
const tbody = document.getElementById('stocks-tbody');
```

### 3. CSS/JS no cargan

**Problema**: Página sin estilos o sin funcionalidad

**Diagnóstico:**
```bash
# Ver qué carga el navegador (F12 → Network)
# Estado 304: Caché
# Estado 404: Archivo no existe
# Estado 200: OK

# Verificar rutas en HTML
curl -s http://127.0.0.1:8000/ | grep '<script\|<link'
```

**Solución:**
- Limpiar caché navegador (Ctrl+Shift+Delete)
- Verificar `base_path="/sw"` en main.py
- Verificar archivos en `/home/stanweinstein/web/static/`

### 4. Gráfico no cambia de período

**Problema**: Botones no responden o período no cambia

**Diagnóstico:**
```javascript
// En consola del navegador (F12)
console.log(typeof loadChart);  // Debe ser "function"
console.log(fullHistoryData);   // Debe tener datos
```

**Solución:**
- Verificar que `stock_detail.js` tiene función `loadChart(weeks)`
- Verificar que botones tienen `onclick="loadChart(26)"`
- Verificar que clases CSS `.period-btn` y `.active` existen

### 5. Botón activo no se resalta

**Problema**: No se ve qué período está seleccionado

**Solución:**

Añadir estilos CSS en `stock_detail.html`:

```html
<style>
.period-btn {
    padding: 0.375rem 0.75rem;
    border: 1px solid #2563eb;
    background: transparent;
    color: #2563eb;
    border-radius: 0.375rem;
    cursor: pointer;
    transition: all 0.2s;
}

.period-btn:hover {
    background: rgba(37, 99, 235, 0.1);
}

.period-btn.active {
    background: #2563eb;
    color: white;
    font-weight: 600;
}
</style>
```

## 📊 API Endpoints

El dashboard expone estos endpoints:

```
GET /                           → Dashboard principal
GET /stocks                     → Lista de acciones
GET /signals                    → Señales históricas
GET /watchlist                  → Watchlist Etapa 2
GET /stock/{ticker}            → Detalle de acción

GET /api/dashboard/stats       → Estadísticas JSON
GET /api/stocks                → Acciones JSON (filtros, paginación)
GET /api/stock/{ticker}        → Acción JSON (detalle completo)
GET /api/signals               → Señales JSON (filtros)
GET /api/watchlist             → Watchlist JSON
GET /api/health                → Health check
```

## 📈 Mantenimiento

### Ver logs

```bash
# Logs del servicio
sudo journalctl -u weinstein-web -f

# Logs de Apache
sudo tail -f /var/log/httpd/error_log
sudo tail -f /var/log/httpd/access_log
```

### Reiniciar servicio

```bash
sudo systemctl restart weinstein-web
sudo systemctl status weinstein-web
```

### Actualizar código

```bash
cd /home/stanweinstein
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart weinstein-web
```

### Verificar funcionamiento

```bash
# 1. Servicio activo
sudo systemctl is-active weinstein-web

# 2. Puerto escuchando
sudo netstat -tlnp | grep 8000

# 3. Logs sin errores
sudo journalctl -u weinstein-web --since "1 hour ago"

# 4. Acceso web
curl -I http://127.0.0.1:8000/
```

## 🔐 Seguridad

### Configuración recomendada

1. **Ejecutar como usuario sin privilegios** (stanweinstein)
2. **Acceso solo desde localhost** (127.0.0.1:8000)
3. **Apache como proxy reverso** con HTTPS
4. **Firewall** bloqueando acceso directo al puerto 8000

### Permisos de archivos

```bash
# Propietario correcto
sudo chown -R stanweinstein:stanweinstein /home/stanweinstein/web

# Permisos restrictivos
chmod 755 /home/stanweinstein/web
chmod 644 /home/stanweinstein/web/static/*
chmod 644 /home/stanweinstein/web/templates/*
chmod 644 /home/stanweinstein/web/main.py
```

## ✅ Checklist de Instalación

- [ ] Dependencias instaladas (`pip install -r requirements.txt`)
- [ ] Archivos `web/` completos (templates + static)
- [ ] `main.py` configurado con `root_path="/sw"` y `base_path="/sw"`
- [ ] IDs de tablas en `<table>`, no en `<tbody>`
- [ ] JavaScript busca tbody correcto (`*-tbody`)
- [ ] `table-sort.js` se carga ANTES que otros JS
- [ ] Servicio systemd creado y activo
- [ ] Apache configurado con proxy a puerto 8000
- [ ] Logs sin errores
- [ ] Dashboard accesible en `https://dominio.com/sw`
- [ ] Ordenación de tablas funciona (flechitas visibles)
- [ ] Selector de período funciona (botón activo resaltado)

## 📞 Soporte

Si encuentras problemas:

1. Revisa los logs: `sudo journalctl -u weinstein-web -f`
2. Verifica la consola del navegador (F12)
3. Comprueba la sección "Solución de Problemas"
4. Verifica el checklist de instalación

---

**Sistema Weinstein v0.3 - Dashboard Web Completo**
