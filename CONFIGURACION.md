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
WorkingDirectory=/home/stanweinstein
Environment="PATH=/home/stanweinstein/venv/bin"
ExecStart=/home/stanweinstein/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --root-path /stanweinstein
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

## 3. Configuración de Cron (Automatización)

### Crear archivo de cron

```bash
# Como root
nano /etc/cron.d/stanweinstein
```

Contenido del archivo:

```cron
# Stan Weinstein Trading System - Automatización
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# ============================================
# ACTUALIZACIÓN DIARIA DE DATOS
# ============================================
# Ejecutar L-V a las 23:00 (después del cierre de mercados)
# Descarga datos OHLC del día para todas las acciones activas
0 23 * * 1-5 stanweinstein /home/stanweinstein/venv/bin/python /home/stanweinstein/scripts/daily_update.py >> /var/log/stanweinstein/cron.log 2>&1

# ============================================
# PROCESAMIENTO SEMANAL
# ============================================
# Ejecutar domingo a las 01:00
# Agrega datos diarios en velas semanales
# Calcula MA30 y pendiente
# Ejecuta análisis Weinstein (cuando esté implementado)
0 1 * * 0 stanweinstein /home/stanweinstein/venv/bin/python /home/stanweinstein/scripts/weekly_process.py >> /var/log/stanweinstein/cron.log 2>&1

# ============================================
# OPCIONAL: LIMPIEZA DE LOGS ANTIGUOS
# ============================================
# Ejecutar primer día del mes a las 02:00
# Elimina logs de más de 90 días
0 2 1 * * stanweinstein find /var/log/stanweinstein -name "*.log" -mtime +90 -delete
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

### Probar manualmente los scripts

```bash
# Actualización diaria
su - stanweinstein -c "cd /home/stanweinstein && source venv/bin/activate && python scripts/daily_update.py"

# Procesamiento semanal
su - stanweinstein -c "cd /home/stanweinstein && source venv/bin/activate && python scripts/weekly_process.py"
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
ls -Z /home/stanweinstein
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

# Logs de procesamiento semanal
tail -f /var/log/stanweinstein/weekly_process.log

# Logs de carga histórica
tail -f /var/log/stanweinstein/historical_load.log

# Logs de agregación inicial
tail -f /var/log/stanweinstein/weekly_init.log

# Logs del sistema (systemd)
journalctl -u stanweinstein -f

# Logs de cron
tail -f /var/log/stanweinstein/cron.log
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

# Ver próximas ejecuciones de cron
grep stanweinstein /etc/cron.d/stanweinstein
```

### Monitorización de base de datos

```bash
# Estado general
mysql -u stanweinstein -p stanweinstein << 'EOF'
SELECT 
    'Total acciones' as metrica,
    COUNT(*) as valor
FROM stocks
UNION ALL
SELECT 
    'Registros diarios',
    COUNT(*)
FROM daily_data
UNION ALL
SELECT 
    'Semanas agregadas',
    COUNT(*)
FROM weekly_data
UNION ALL
SELECT 
    'Señales generadas',
    COUNT(*)
FROM signals;
EOF

# Acciones listas para análisis
mysql -u stanweinstein -p stanweinstein << 'EOF'
SELECT 
    s.ticker,
    COUNT(w.id) as semanas,
    SUM(CASE WHEN w.ma30 IS NOT NULL THEN 1 ELSE 0 END) as con_ma30,
    CASE 
        WHEN SUM(CASE WHEN w.ma30 IS NOT NULL THEN 1 ELSE 0 END) >= 35 THEN 'SÍ'
        ELSE 'NO'
    END as listo
FROM stocks s
LEFT JOIN weekly_data w ON s.id = w.stock_id
GROUP BY s.id
ORDER BY con_ma30 DESC;
EOF
```

### Monitorización de API Twelve Data

```bash
# Crear script de monitorización
cat > /home/stanweinstein/scripts/check_api_usage.sh << 'EOF'
#!/bin/bash
LOG_FILE="/var/log/stanweinstein/daily_update.log"
TODAY=$(date +%Y-%m-%d)

echo "=== Uso de Twelve Data - $TODAY ==="

SUCCESSFUL=$(grep "$TODAY" "$LOG_FILE" | grep -c "twelvedata.*registros")
ERRORS=$(grep "$TODAY" "$LOG_FILE" | grep -c "twelvedata.*falló")
TOTAL=$((SUCCESSFUL + ERRORS))
LIMIT=800
REMAINING=$((LIMIT - TOTAL))

echo "Peticiones exitosas: $SUCCESSFUL"
echo "Errores: $ERRORS"
echo "Total peticiones: $TOTAL"
echo "Restantes hoy: $REMAINING / $LIMIT"

if [ $REMAINING -lt 100 ]; then
    echo "⚠️ ALERTA: Quedan menos de 100 peticiones!"
fi
EOF

chmod +x /home/stanweinstein/scripts/check_api_usage.sh

# Ejecutar
/home/stanweinstein/scripts/check_api_usage.sh
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

# Ver tamaño de tablas
mysql -u stanweinstein -p stanweinstein -e "
SELECT 
    table_name AS 'Tabla',
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Tamaño (MB)'
FROM information_schema.TABLES 
WHERE table_schema = 'stanweinstein'
ORDER BY (data_length + index_length) DESC;
"
```

---

## 7. Acceso a la Aplicación

Una vez configurado todo:

- **URL Web**: https://www.tudominio.com/stanweinstein [EN DESARROLLO]
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
cd /home/stanweinstein
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
ls -la /home/stanweinstein/scripts/daily_update.py

# Ejecutar manualmente como lo haría cron
su - stanweinstein -c "cd /home/stanweinstein && source venv/bin/activate && python scripts/daily_update.py"
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
cat /home/stanweinstein/app/config.py | grep DB_CONFIG
```

### Problema: Twelve Data API bloqueada

```bash
# Ver uso de API hoy
grep "$(date +%Y-%m-%d)" /var/log/stanweinstein/daily_update.log | grep "twelvedata" | wc -l

# Ver errores
grep "$(date +%Y-%m-%d)" /var/log/stanweinstein/daily_update.log | grep "429\|bloqueado"

# Esperar 24h o aumentar RATE_LIMIT_DELAY en config.py
nano /home/stanweinstein/app/config.py
# Cambiar: RATE_LIMIT_DELAY = 8  # 8 segundos entre peticiones
```

### Problema: No se agregan datos semanales

```bash
# Ver log de procesamiento semanal
tail -100 /var/log/stanweinstein/weekly_process.log

# Verificar que hay datos diarios
mysql -u stanweinstein -p stanweinstein -e "SELECT COUNT(*) FROM daily_data;"

# Ejecutar agregación manualmente
su - stanweinstein
cd /home/stanweinstein
source venv/bin/activate
python scripts/weekly_process.py
```

---

## 9. Actualización del Código

Cuando actualices el código desde GitHub:

```bash
# Como usuario stanweinstein
cd /home/stanweinstein
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

## 10. Verificación Post-Instalación

### Checklist completo

```bash
# 1. Servicios activos
systemctl status httpd mariadb crond

# 2. Cron configurado
cat /etc/cron.d/stanweinstein

# 3. Logs creados y accesibles
ls -la /var/log/stanweinstein/

# 4. Base de datos poblada
mysql -u stanweinstein -p stanweinstein -e "
SELECT 
    (SELECT COUNT(*) FROM stocks) as acciones,
    (SELECT COUNT(*) FROM daily_data) as datos_diarios,
    (SELECT COUNT(*) FROM weekly_data) as datos_semanales;
"

# 5. Última actualización
tail -20 /var/log/stanweinstein/daily_update.log

# 6. Última agregación semanal
tail -20 /var/log/stanweinstein/weekly_process.log

# 7. Próximas ejecuciones de cron
systemctl status crond
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
su - stanweinstein -c "cd /home/stanweinstein && source venv/bin/activate && python scripts/daily_update.py"

# Ejecutar procesamiento semanal manual
su - stanweinstein -c "cd /home/stanweinstein && source venv/bin/activate && python scripts/weekly_process.py"

# Actualizar código desde git
cd /home/stanweinstein && git pull && sudo systemctl restart stanweinstein

# Monitorizar uso de API
/home/stanweinstein/scripts/check_api_usage.sh

# Backup de base de datos
mysqldump -u stanweinstein -p stanweinstein > backup_$(date +%Y%m%d).sql
```

---

**Última actualización**: Febrero 2026 - v0.2 (Agregación Semanal Implementada)
