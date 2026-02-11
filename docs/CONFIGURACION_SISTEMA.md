# Configuración del Sistema - Stan Weinstein Trading System

## 1. Configuración Apache (Proxy Inverso)

### Crear archivo de configuración

```bash
# Como root
nano /etc/httpd/conf.d/stanweinstein.conf
```

Contenido del archivo:

```apache
# Configuración proxy inverso para Stan Weinstein Trading System
<Location /stanweinstein>
    ProxyPass http://127.0.0.1:8000
    ProxyPassReverse http://127.0.0.1:8000
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Prefix "/stanweinstein"
    ProxyPreserveHost On
</Location>
```

### Verificar y aplicar

```bash
# Verificar sintaxis de configuración
httpd -t

# Si la sintaxis es correcta, reiniciar Apache
systemctl restart httpd

# Verificar que Apache está funcionando
systemctl status httpd
```

---

## 2. Servicio Systemd para FastAPI

### Crear archivo de servicio

```bash
# Como root
nano /etc/systemd/system/stanweinstein.service
```

Contenido del archivo:

```ini
[Unit]
Description=Stan Weinstein Trading System - FastAPI Application
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=stanweinstein
Group=stanweinstein
WorkingDirectory=/home/stanweinstein/stanweinstein
Environment="PATH=/home/stanweinstein/stanweinstein/venv/bin"
ExecStart=/home/stanweinstein/stanweinstein/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --root-path /stanweinstein
Restart=always
RestartSec=10
StandardOutput=append:/var/log/stanweinstein/app.log
StandardError=append:/var/log/stanweinstein/app_error.log

[Install]
WantedBy=multi-user.target
```

### Activar y gestionar el servicio

```bash
# Recargar configuración de systemd
systemctl daemon-reload

# Habilitar inicio automático al arrancar el sistema
systemctl enable stanweinstein

# Iniciar el servicio
systemctl start stanweinstein

# Verificar estado
systemctl status stanweinstein

# Ver logs en tiempo real
journalctl -u stanweinstein -f

# Otros comandos útiles:
systemctl stop stanweinstein      # Detener
systemctl restart stanweinstein   # Reiniciar
systemctl disable stanweinstein   # Deshabilitar inicio automático
```

---

## 3. Configuración de Cron (Actualización Diaria)

### Crear archivo de cron

```bash
# Como root
nano /etc/cron.d/stanweinstein
```

Contenido del archivo:

```cron
# Stan Weinstein - Actualización diaria de datos
# Se ejecuta a las 23:00 hora local (después del cierre de mercados)
# De lunes a viernes (1-5)

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Actualización diaria
0 23 * * 1-5 stanweinstein /home/stanweinstein/stanweinstein/venv/bin/python /home/stanweinstein/stanweinstein/scripts/daily_update.py >> /var/log/stanweinstein/cron.log 2>&1

# Opcional: Limpieza de logs antiguos cada domingo a las 2:00 AM
# 0 2 * * 0 stanweinstein find /var/log/stanweinstein -name "*.log" -mtime +30 -delete
```

### Aplicar configuración

```bash
# Establecer permisos correctos
chmod 644 /etc/cron.d/stanweinstein

# Reiniciar servicio cron
systemctl restart crond

# Verificar que cron está activo
systemctl status crond

# Ver logs de cron
tail -f /var/log/stanweinstein/cron.log
```

### Probar manualmente el script de actualización

```bash
# Como usuario stanweinstein
su - stanweinstein
cd ~/stanweinstein
source venv/bin/activate
python scripts/daily_update.py
```

---

## 4. Rotación de Logs (logrotate)

### Crear configuración de logrotate

```bash
# Como root
nano /etc/logrotate.d/stanweinstein
```

Contenido del archivo:

```
/var/log/stanweinstein/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 stanweinstein stanweinstein
    sharedscripts
    postrotate
        systemctl reload stanweinstein > /dev/null 2>&1 || true
    endscript
}
```

### Probar configuración

```bash
# Verificar sintaxis
logrotate -d /etc/logrotate.d/stanweinstein

# Forzar rotación manual (para probar)
logrotate -f /etc/logrotate.d/stanweinstein
```

---

## 5. Firewall y SELinux

### Firewall (firewalld)

```bash
# Verificar servicios permitidos
firewall-cmd --list-all

# Asegurar que HTTP/HTTPS están permitidos
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
```

### SELinux

```bash
# Verificar estado
getenforce

# Si está en Enforcing, permitir conexiones de proxy
setsebool -P httpd_can_network_connect 1

# Verificar contextos de archivos
ls -Z /home/stanweinstein/stanweinstein
```

---

## 6. Monitorización y Mantenimiento

### Ver logs en tiempo real

```bash
# Logs de aplicación FastAPI
tail -f /var/log/stanweinstein/app.log

# Logs de errores
tail -f /var/log/stanweinstein/app_error.log

# Logs de actualización diaria
tail -f /var/log/stanweinstein/daily_update.log

# Logs de carga histórica
tail -f /var/log/stanweinstein/historical_load.log

# Logs del sistema (systemd)
journalctl -u stanweinstein -f
```

### Verificar estado general del sistema

```bash
# Estado de servicios
systemctl status httpd
systemctl status mariadb
systemctl status stanweinstein

# Espacio en disco
df -h

# Uso de memoria
free -h

# Procesos de la aplicación
ps aux | grep stanweinstein
```

### Comandos útiles de mantenimiento

```bash
# Reiniciar todo el sistema tras cambios
systemctl restart mariadb
systemctl restart stanweinstein
systemctl restart httpd

# Limpiar logs antiguos manualmente
find /var/log/stanweinstein -name "*.log" -mtime +30 -delete

# Backup de base de datos
mysqldump -u stanweinstein -p stanweinstein > backup_$(date +%Y%m%d).sql

# Verificar integridad de base de datos
mysqlcheck -u stanweinstein -p stanweinstein
```

---

## 7. Acceso a la Aplicación

Una vez configurado todo:

- **URL Web**: https://www.tudominio.com/stanweinstein
- **Puerto interno**: 8000 (solo localhost)
- **Logs**: /var/log/stanweinstein/

---

## 8. Troubleshooting

### Problema: La aplicación no inicia

```bash
# Ver logs de systemd
journalctl -u stanweinstein -n 50

# Ver logs de la aplicación
tail -100 /var/log/stanweinstein/app_error.log

# Probar manualmente
su - stanweinstein
cd ~/stanweinstein
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Problema: Cron no ejecuta actualización

```bash
# Ver logs de cron del sistema
tail -f /var/log/cron

# Ver logs específicos de actualización
tail -f /var/log/stanweinstein/cron.log

# Verificar permisos del script
ls -la /home/stanweinstein/stanweinstein/scripts/daily_update.py

# Ejecutar manualmente para ver errores
su - stanweinstein -c "cd /home/stanweinstein/stanweinstein && source venv/bin/activate && python scripts/daily_update.py"
```

### Problema: Apache no sirve la aplicación

```bash
# Ver logs de Apache
tail -f /var/log/httpd/error_log

# Verificar proxy
httpd -M | grep proxy

# Probar conexión local
curl http://127.0.0.1:8000

# Verificar configuración
httpd -t
```

### Problema: Error de conexión a MariaDB

```bash
# Verificar que MariaDB está corriendo
systemctl status mariadb

# Probar conexión manual
mysql -u stanweinstein -p stanweinstein

# Ver logs de MariaDB
tail -f /var/log/mariadb/mariadb.log

# Verificar credenciales en config.py
cat /home/stanweinstein/stanweinstein/app/config.py | grep DB_CONFIG
```

---

## 9. Actualización del Código

Cuando actualices el código desde GitHub:

```bash
# Como usuario stanweinstein
cd ~/stanweinstein
git pull origin main

# Activar entorno virtual
source venv/bin/activate

# Actualizar dependencias (si es necesario)
pip install -r requirements.txt --upgrade

# Reiniciar servicio
sudo systemctl restart stanweinstein

# Verificar que funciona
systemctl status stanweinstein
```

---

## Resumen de Comandos Rápidos

```bash
# Ver estado general
systemctl status stanweinstein httpd mariadb

# Reiniciar aplicación
sudo systemctl restart stanweinstein

# Ver logs en tiempo real
tail -f /var/log/stanweinstein/app.log

# Ejecutar actualización manual
su - stanweinstein -c "cd ~/stanweinstein && source venv/bin/activate && python scripts/daily_update.py"

# Actualizar código desde git
cd ~/stanweinstein && git pull && sudo systemctl restart stanweinstein
```
