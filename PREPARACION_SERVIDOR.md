# Preparación del Servidor - Sistema Weinstein v0.3

**SO Recomendado:** AlmaLinux 9 / Rocky Linux 9 / Debian 12  
**Última actualización:** Febrero 2026

---

## 📋 Requisitos del Sistema

### **Hardware Mínimo:**
- **CPU**: 2 cores
- **RAM**: 2 GB
- **Disco**: 20 GB
- **Red**: Conexión estable a Internet

### **Software:**
- Python 3.9+
- MariaDB 10.5+ / MySQL 8.0+
- pip, venv
- cron

---

## 🚀 Instalación Paso a Paso

### **1. Actualizar Sistema**

```bash
# AlmaLinux / Rocky Linux
sudo dnf update -y
sudo dnf install -y epel-release

# Debian / Ubuntu
sudo apt update
sudo apt upgrade -y
```

---

### **2. Instalar MariaDB**

```bash
# AlmaLinux / Rocky Linux
sudo dnf install -y mariadb-server mariadb
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo mysql_secure_installation

# Debian / Ubuntu
sudo apt install -y mariadb-server mariadb-client
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo mysql_secure_installation
```

**Configuración segura:**
- Set root password: **Sí**
- Remove anonymous users: **Sí**
- Disallow root login remotely: **Sí**
- Remove test database: **Sí**
- Reload privilege tables: **Sí**

---

### **3. Crear Base de Datos y Usuario**

```bash
sudo mysql -u root -p
```

```sql
-- Crear base de datos
CREATE DATABASE stanweinstein CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Crear usuario
CREATE USER 'stanweinstein'@'localhost' IDENTIFIED BY 'tu_password_segura';

-- Dar permisos
GRANT SELECT, INSERT, UPDATE, DELETE ON stanweinstein.* TO 'stanweinstein'@'localhost';
FLUSH PRIVILEGES;

-- Verificar
SHOW DATABASES;
SELECT User, Host FROM mysql.user WHERE User='stanweinstein';

EXIT;
```

---

### **4. Instalar Python y Dependencias**

```bash
# AlmaLinux / Rocky Linux
sudo dnf install -y python3 python3-pip python3-devel gcc mariadb-devel

# Debian / Ubuntu
sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential libmariadb-dev
```

---

### **5. Crear Usuario del Sistema**

```bash
# Crear usuario stanweinstein
sudo useradd -m -s /bin/bash stanweinstein

# Establecer password (opcional, para login manual)
sudo passwd stanweinstein

# Crear directorio de logs
sudo mkdir -p /var/log/stanweinstein
sudo chown stanweinstein:stanweinstein /var/log/stanweinstein
sudo chmod 755 /var/log/stanweinstein
```

---

### **6. Configurar Proyecto**

```bash
# Cambiar a usuario stanweinstein
sudo su - stanweinstein

# Crear estructura
cd /home/stanweinstein
mkdir -p app scripts docs

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install pymysql sqlalchemy pandas yfinance requests --break-system-packages
```

---

### **7. Crear Esquema de Base de Datos**

```bash
# Como usuario stanweinstein
mysql -u stanweinstein -p stanweinstein < schema.sql
```

**Archivo `schema.sql`:**
```sql
-- Tabla de acciones
CREATE TABLE stocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200),
    exchange VARCHAR(50),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ticker (ticker),
    INDEX idx_active (active)
);

-- Datos diarios
CREATE TABLE daily_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    UNIQUE KEY unique_stock_date (stock_id, date),
    INDEX idx_daily_stock_date (stock_id, date),
    INDEX idx_daily_date (date)
);

-- Datos semanales
CREATE TABLE weekly_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    week_end_date DATE NOT NULL,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    volume BIGINT,
    ma30 DECIMAL(12,4),
    ma30_slope DECIMAL(8,6),
    stage TINYINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    UNIQUE KEY unique_stock_week (stock_id, week_end_date),
    INDEX idx_weekly_stock_date (stock_id, week_end_date),
    INDEX idx_weekly_stage (stage)
);

-- Señales
CREATE TABLE signals (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    signal_date DATE NOT NULL,
    signal_type VARCHAR(20) NOT NULL,
    stage_from TINYINT,
    stage_to TINYINT,
    price DECIMAL(12,4),
    ma30 DECIMAL(12,4),
    notified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    INDEX idx_signals_stock (stock_id),
    INDEX idx_signals_date (signal_date),
    INDEX idx_signals_type (signal_type),
    INDEX idx_signals_notified (notified)
);
```

---

### **8. Obtener API Key de Twelve Data**

1. Registrarse en: https://twelvedata.com/pricing
2. Seleccionar **Free Tier**:
   - 800 peticiones/día
   - 8 peticiones/minuto
   - Datos de acciones USA gratuitos
3. Copiar API Key del dashboard
4. Configurar en `app/config.py`:

```python
TWELVEDATA_API_KEY = "tu_api_key_aqui"
```

---

### **9. Configurar Telegram Bot**

1. Abrir Telegram → Buscar **@BotFather**
2. Enviar: `/newbot`
3. Nombre: `Sistema Weinstein`
4. Username: `weinstein_trading_bot`
5. Copiar **TOKEN**

6. Obtener CHAT_ID:
   - Buscar **@userinfobot**
   - Enviar: `/start`
   - Copiar **Chat ID**

7. Configurar en `scripts/telegram_bot.py`:

```python
TELEGRAM_TOKEN = "123456789:ABC..."
TELEGRAM_CHAT_ID = "123456789"
```

8. Probar:
```bash
python scripts/telegram_bot.py --test
```

---

### **10. Cargar Datos Iniciales**

```bash
# Como stanweinstein
cd /home/stanweinstein
source venv/bin/activate

# 1. Cargar lista de acciones
python scripts/load_stocks_from_csv.py empresas.csv

# 2. Cargar datos históricos (2 años)
python scripts/load_missing_historical.py
# Esto tarda ~70 minutos para 400 acciones

# 3. Agregación semanal inicial
python scripts/init_weekly_aggregation.py
# Tarda ~5 minutos

# 4. Análisis inicial de etapas
python scripts/analyze_initial.py
# Tarda ~2 minutos
```

---

### **11. Instalar Cron Jobs**

```bash
# Como root
sudo cp /home/stanweinstein/stanweinstein_cron /etc/cron.d/stanweinstein
sudo chmod 644 /etc/cron.d/stanweinstein
sudo chown root:root /etc/cron.d/stanweinstein

# Verificar
sudo cat /etc/cron.d/stanweinstein

# Ver logs de cron
sudo tail -f /var/log/cron
```

---

### **12. Configurar Logrotate**

```bash
# Como root
sudo nano /etc/logrotate.d/stanweinstein
```

```bash
/var/log/stanweinstein/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 stanweinstein stanweinstein
}
```

---

## ✅ Verificación Final

### **1. Base de Datos:**
```bash
mysql -u stanweinstein -p stanweinstein << 'EOF'
SELECT COUNT(*) as acciones FROM stocks;
SELECT COUNT(*) as datos_diarios FROM daily_data;
SELECT COUNT(*) as semanas FROM weekly_data;
SELECT COUNT(*) as senales FROM signals;
EOF
```

**Resultado esperado:**
```
acciones: 396
datos_diarios: ~198000
semanas: ~41000
senales: ~236
```

---

### **2. Telegram:**
```bash
python scripts/telegram_bot.py --test
```

**Deberías recibir mensaje:**
```
🤖 Test Sistema Weinstein
Fecha: 10/02/2026 15:30
✅ Bot funcionando correctamente
```

---

### **3. Cron:**
```bash
sudo grep stanweinstein /var/log/cron
```

**Deberías ver:**
```
Feb 10 23:00:01 CROND[12345]: (stanweinstein) CMD (/home/stanweinstein/venv/bin/python /home/stanweinstein/scripts/daily_update.py)
```

---

### **4. Logs:**
```bash
ls -lh /var/log/stanweinstein/
```

**Deberías ver:**
```
-rw-r--r-- stanweinstein stanweinstein  daily_update.log
-rw-r--r-- stanweinstein stanweinstein  weekly_process.log
-rw-r--r-- stanweinstein stanweinstein  telegram.log
```

---

## 🔒 Seguridad

### **Firewall:**
```bash
# Permitir solo SSH (si es servidor remoto)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload

# MariaDB solo local (no exponer)
sudo firewall-cmd --remove-service=mysql --permanent
```

### **Permisos:**
```bash
# Directorio principal
sudo chown -R stanweinstein:stanweinstein /home/stanweinstein
sudo chmod 755 /home/stanweinstein

# Config (contiene API keys)
sudo chmod 600 /home/stanweinstein/app/config.py

# Scripts
sudo chmod 755 /home/stanweinstein/scripts/*.py

# Logs
sudo chmod 755 /var/log/stanweinstein
sudo chmod 644 /var/log/stanweinstein/*.log
```

### **Backup:**
```bash
# Script de backup diario
#!/bin/bash
# /home/stanweinstein/scripts/backup.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR="/home/stanweinstein/backups"

mkdir -p $BACKUP_DIR

# Backup BD
mysqldump -u stanweinstein -p stanweinstein | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup config
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /home/stanweinstein/app/config.py

# Eliminar backups >30 días
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
```

---

## 📊 Monitorización

### **Script de health check:**
```bash
#!/bin/bash
# /home/stanweinstein/scripts/health_check.sh

echo "=== HEALTH CHECK - Sistema Weinstein ==="
echo ""

# Última actualización
LAST_UPDATE=$(mysql -u stanweinstein -pPASSWORD -N -e "
    SELECT MAX(date) FROM stanweinstein.daily_data
" | xargs)

echo "Última actualización: $LAST_UPDATE"

# Señales pendientes
PENDING=$(mysql -u stanweinstein -pPASSWORD -N -e "
    SELECT COUNT(*) FROM stanweinstein.signals WHERE notified = 0
")

echo "Señales pendientes: $PENDING"

# Uso disco
echo ""
df -h /home/stanweinstein | tail -1

echo ""
echo "✓ Health check completado"
```

---

## 🔧 Troubleshooting Común

### MariaDB no inicia:
```bash
sudo systemctl status mariadb
sudo journalctl -xe
sudo systemctl restart mariadb
```

### Cron no ejecuta:
```bash
# Verificar sintaxis
sudo cat /etc/cron.d/stanweinstein

# Ver errores
sudo grep stanweinstein /var/log/cron
sudo tail -50 /var/log/stanweinstein/cron.log
```

### Python no encuentra módulos:
```bash
# Verificar venv activado
source /home/stanweinstein/venv/bin/activate
pip list

# Reinstalar
pip install pymysql sqlalchemy pandas yfinance requests --break-system-packages
```

---

## 📚 Recursos Adicionales

- **Documentación Twelve Data**: https://twelvedata.com/docs
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **Stan Weinstein**: "Secrets for Profiting in Bull and Bear Markets"

---

**Servidor preparado v0.3.0** - Sistema Weinstein Trading
