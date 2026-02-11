# Instalación del Dashboard Web - Sistema Weinstein

**Versión:** 0.3.0  
**Stack:** FastAPI + HTML/CSS/JS

---

## 📋 Requisitos

- Python 3.9+ (ya instalado)
- FastAPI + Uvicorn
- Nginx o Apache como proxy reverso

---

## 🚀 Instalación Paso a Paso

### **1. Instalar Dependencias**

```bash
su - stanweinstein
cd /home/stanweinstein
source venv/bin/activate

# Instalar FastAPI y Uvicorn
pip install fastapi uvicorn jinja2 --break-system-packages
```

---

### **2. Crear Estructura de Directorios**

```bash
cd /home/stanweinstein

# Crear directorios web
mkdir -p web/static web/templates

# Verificar estructura
ls -la web/
```

Estructura esperada:
```
/home/stanweinstein/
├── app/              (ya existe)
├── scripts/          (ya existe)
└── web/              (nuevo)
    ├── main.py       (FastAPI app)
    ├── static/       (CSS, JS)
    │   ├── style.css
    │   └── dashboard.js
    └── templates/    (HTML)
        └── dashboard.html
```

---

### **3. Copiar Archivos**

```bash
# Copiar FastAPI app
cp web_main.py /home/stanweinstein/web/main.py

# Copiar archivos estáticos
cp style.css /home/stanweinstein/web/static/
cp dashboard.js /home/stanweinstein/web/static/

# Copiar templates
cp dashboard.html /home/stanweinstein/web/templates/

# Dar permisos
chmod 644 /home/stanweinstein/web/main.py
chmod 644 /home/stanweinstein/web/static/*
chmod 644 /home/stanweinstein/web/templates/*
```

---

### **4. Probar FastAPI en Desarrollo**

```bash
cd /home/stanweinstein
source venv/bin/activate

# Ejecutar servidor de desarrollo
uvicorn web.main:app --host 0.0.0.0 --port 8000 --reload
```

**Abrir navegador:** http://servidor:8000

Deberías ver el dashboard cargando.

---

### **5. Crear Servicio Systemd (Producción)**

```bash
# Como root
sudo nano /etc/systemd/system/weinstein-web.service
```

Contenido:
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

**Activar servicio:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable weinstein-web
sudo systemctl start weinstein-web

# Verificar estado
sudo systemctl status weinstein-web

# Ver logs
sudo journalctl -u weinstein-web -f
```

---

### **6. Configurar Nginx como Proxy Reverso**

#### **Opción A: Puerto 80 (HTTP)**

```bash
# Instalar Nginx
sudo dnf install -y nginx  # AlmaLinux/Rocky
# sudo apt install -y nginx  # Debian/Ubuntu

# Crear configuración
sudo nano /etc/nginx/conf.d/weinstein.conf
```

Contenido:
```nginx
server {
    listen 80;
    server_name _;  # O tu dominio/IP

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /home/stanweinstein/web/static;
        expires 30d;
    }
}
```

**Activar Nginx:**
```bash
sudo systemctl enable nginx
sudo systemctl start nginx

# Verificar configuración
sudo nginx -t

# Recargar
sudo systemctl reload nginx

# Abrir firewall
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

#### **Opción B: Puerto Personalizado (ej: 8080)**

```nginx
server {
    listen 8080;
    server_name _;

    # ... resto igual ...
}
```

```bash
# Abrir puerto en firewall
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

---

### **7. Configurar Apache como Proxy (Alternativa)**

Si prefieres Apache en lugar de Nginx:

```bash
# Instalar Apache
sudo dnf install -y httpd  # AlmaLinux/Rocky
# sudo apt install -y apache2  # Debian/Ubuntu

# Habilitar módulos necesarios
sudo a2enmod proxy proxy_http  # Debian/Ubuntu

# Crear configuración
sudo nano /etc/httpd/conf.d/weinstein.conf  # AlmaLinux/Rocky
```

Contenido:
```apache
<VirtualHost *:80>
    ServerName weinstein.local
    
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
    
    <Directory /home/stanweinstein/web/static>
        Require all granted
    </Directory>
    
    Alias /static /home/stanweinstein/web/static
</VirtualHost>
```

**Activar Apache:**
```bash
sudo systemctl enable httpd
sudo systemctl start httpd

# Abrir firewall
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

---

## ✅ Verificación

### **1. Verificar Servicio FastAPI**

```bash
sudo systemctl status weinstein-web

# Debería mostrar: Active: active (running)
```

### **2. Verificar Nginx/Apache**

```bash
sudo systemctl status nginx
# o
sudo systemctl status httpd
```

### **3. Probar Endpoints API**

```bash
# Health check
curl http://localhost:8000/api/health

# Dashboard stats
curl http://localhost:8000/api/dashboard/stats

# Watchlist
curl http://localhost:8000/api/watchlist
```

### **4. Abrir en Navegador**

Visitar: **http://tu-servidor**

Deberías ver:
- Dashboard con estadísticas
- Distribución por etapas
- Señales recientes
- Top acciones en Etapa 2

---

## 📊 Endpoints API Disponibles

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML |
| `/stocks` | GET | Lista de acciones HTML |
| `/stock/{ticker}` | GET | Detalle de acción HTML |
| `/signals` | GET | Señales HTML |
| `/watchlist` | GET | Watchlist HTML |
| `/api/health` | GET | Health check |
| `/api/dashboard/stats` | GET | Estadísticas dashboard |
| `/api/stocks` | GET | Lista acciones JSON |
| `/api/stock/{ticker}` | GET | Detalle acción JSON |
| `/api/signals` | GET | Señales JSON |
| `/api/watchlist` | GET | Acciones Etapa 2 JSON |

---

## 🔧 Troubleshooting

### **Problema: 502 Bad Gateway**

```bash
# Verificar que FastAPI está corriendo
sudo systemctl status weinstein-web

# Ver logs
sudo journalctl -u weinstein-web -n 50

# Reiniciar servicio
sudo systemctl restart weinstein-web
```

### **Problema: No carga CSS/JS**

```bash
# Verificar permisos
ls -la /home/stanweinstein/web/static/

# Dar permisos a Nginx
sudo chmod 755 /home/stanweinstein
sudo chmod 755 /home/stanweinstein/web
sudo chmod 755 /home/stanweinstein/web/static
sudo chmod 644 /home/stanweinstein/web/static/*
```

### **Problema: Error de módulo**

```bash
# Reinstalar dependencias
source /home/stanweinstein/venv/bin/activate
pip install fastapi uvicorn jinja2 --break-system-packages

# Verificar instalación
python -c "import fastapi; print(fastapi.__version__)"
```

### **Problema: SELinux bloquea conexión**

```bash
# Verificar si SELinux está activo
getenforce

# Permitir conexión HTTP de Nginx a backend
sudo setsebool -P httpd_can_network_connect 1

# O deshabilitar temporalmente para probar
sudo setenforce 0
```

---

## 🔄 Actualización del Código

```bash
# Cuando hagas cambios en el código
sudo systemctl restart weinstein-web

# O en desarrollo (auto-reload)
uvicorn web.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📝 Próximos Pasos

Una vez funcionando el dashboard básico:

1. ✅ Crear página de **lista de acciones** (stocks.html)
2. ✅ Crear página de **detalle de acción** con gráfico (stock_detail.html)
3. ✅ Crear página de **señales** (signals.html)
4. ✅ Crear página de **watchlist** (watchlist.html)
5. Añadir gráficos con Chart.js
6. Implementar filtros y búsqueda
7. Añadir paginación

---

**Dashboard web instalado v0.3.0** - Sistema Weinstein
