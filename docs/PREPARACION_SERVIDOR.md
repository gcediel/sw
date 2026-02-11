# Preparación del Servidor - Sistema Stan Weinstein

## Requisitos del Sistema

- **Sistema Operativo**: AlmaLinux 9.4 (o similar RHEL-based)
- **Apache**: 2.4.57+
- **MariaDB**: 10.5+
- **Python**: 3.9+
- **Espacio en disco**: Mínimo 10GB libres
- **Memoria RAM**: Mínimo 2GB

## 1. Instalación de Paquetes Base

```bash
# Como root
dnf update -y

# Instalar Python y herramientas de desarrollo
dnf install -y python3 python3-pip python3-devel python3-virtualenv

# Instalar MariaDB server (si no está instalado)
dnf install -y mariadb-server mariadb

# Iniciar y habilitar MariaDB
systemctl start mariadb
systemctl enable mariadb

# Asegurar instalación de MariaDB (solo primera vez)
mysql_secure_installation
```

## 2. Crear Usuario del Sistema

```bash
# Crear usuario stanweinstein con directorio home
useradd -m -s /bin/bash stanweinstein

# Establecer password (opcional, para login directo)
passwd stanweinstein

# Crear directorio de logs
mkdir -p /var/log/stanweinstein
chown stanweinstein:stanweinstein /var/log/stanweinstein
chmod 755 /var/log/stanweinstein
```

## 3. Configuración de MariaDB

```bash
# Conectar como root
mysql -u root -p
```

Ejecutar el script SQL (ver archivo `database_schema.sql`):

```bash
# Desde el servidor
mysql -u root -p < /ruta/al/database_schema.sql
```

O ejecutar manualmente:

```sql
-- Crear base de datos
CREATE DATABASE stanweinstein CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Crear usuario
CREATE USER 'stanweinstein'@'localhost' IDENTIFIED BY 'PASSWORD_SEGURO_AQUI';

-- Otorgar permisos
GRANT ALL PRIVILEGES ON stanweinstein.* TO 'stanweinstein'@'localhost';
FLUSH PRIVILEGES;

-- Salir
EXIT;
```

**IMPORTANTE**: Cambia `PASSWORD_SEGURO_AQUI` por una contraseña fuerte.

## 4. Verificar Módulos de Apache

```bash
# Verificar que mod_proxy esté habilitado
httpd -M | grep proxy

# Deberías ver:
# proxy_module (shared)
# proxy_http_module (shared)
```

Si no están habilitados (aunque en AlmaLinux 9.4 vienen por defecto):

```bash
# Cargar módulos (normalmente ya están)
# Editar /etc/httpd/conf.modules.d/00-proxy.conf
```

## 5. Configuración de Apache para Proxy Inverso

Crear archivo de configuración:

```bash
nano /etc/httpd/conf.d/stanweinstein.conf
```

Contenido:

```apache
# Proxy inverso para aplicación Stan Weinstein
<Location /stanweinstein>
    ProxyPass http://127.0.0.1:8000
    ProxyPassReverse http://127.0.0.1:8000
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Prefix "/stanweinstein"
    ProxyPreserveHost On
</Location>
```

Verificar configuración y reiniciar:

```bash
# Verificar sintaxis
httpd -t

# Reiniciar Apache
systemctl restart httpd
```

## 6. Configuración de Firewall (si aplica)

```bash
# Verificar que el puerto 80/443 esté abierto
firewall-cmd --list-all

# Si no está abierto:
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
```

## 7. SELinux (si está activo)

```bash
# Verificar estado de SELinux
getenforce

# Si está en Enforcing, permitir conexiones de proxy
setsebool -P httpd_can_network_connect 1
```

## 8. Preparación del Entorno Python

```bash
# Como usuario stanweinstein
su - stanweinstein

# Clonar repositorio
cd ~
git clone https://github.com/TU-USUARIO/stanweinstein.git
cd stanweinstein

# Crear entorno virtual
python3 -m venv venv

# Activar entorno
source venv/bin/activate

# Actualizar pip
pip install --upgrade pip

# Instalar dependencias
pip install -r requirements.txt
```

## 9. Configuración de la Aplicación

```bash
# Copiar archivo de configuración de ejemplo
cp app/config.example.py app/config.py

# Editar con tus credenciales
nano app/config.py
```

Cambiar los siguientes valores:
- `DB_CONFIG['password']`: Password de MariaDB
- `TELEGRAM_BOT_TOKEN`: Token del bot de Telegram (cuando lo tengas)
- `TELEGRAM_CHAT_ID`: ID del chat de Telegram (cuando lo tengas)

## 10. Inicializar Base de Datos (Tablas)

```bash
# Como stanweinstein, con venv activado
cd /home/stanweinstein/stanweinstein
source venv/bin/activate

# Ejecutar script de inicialización
python -c "from app.database import init_db; init_db()"
```

Deberías ver: `Base de datos inicializada correctamente`

## 11. Verificación

```bash
# Verificar conexión a base de datos
mysql -u stanweinstein -p stanweinstein -e "SHOW TABLES;"

# Deberías ver:
# +------------------------+
# | Tables_in_stanweinstein|
# +------------------------+
# | daily_data             |
# | signals                |
# | stocks                 |
# | weekly_data            |
# +------------------------+
```

## Siguiente Paso

Una vez completada la preparación, continuar con la **Configuración del Sistema** (ver `CONFIGURACION_SISTEMA.md`).
