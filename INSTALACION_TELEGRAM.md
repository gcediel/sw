# INSTALACIÓN DEL BOT DE TELEGRAM

## 1. INSTALAR DEPENDENCIAS

```bash
su - stanweinstein
cd /home/stanweinstein
source venv/bin/activate

# Instalar requests para llamadas API
pip install requests --break-system-packages
```

## 2. OBTENER CREDENCIALES DE TELEGRAM

### **2.1 Crear Bot con @BotFather**

1. Abrir Telegram → Buscar **@BotFather**
2. Enviar: `/newbot`
3. Nombre del bot: `Sistema Weinstein` (o el que prefieras)
4. Username: `weinstein_trading_bot` (debe terminar en _bot)
5. **Copiar el TOKEN** que te da (ejemplo: `123456789:ABCdefGHI...`)

### **2.2 Obtener tu CHAT_ID**

1. Buscar en Telegram: **@userinfobot**
2. Enviar: `/start`
3. **Copiar tu Chat ID** (ejemplo: `123456789` o `-1002317902170`)

## 3. CONFIGURAR BOT

```bash
# Copiar plantilla a archivo real
cp /home/stanweinstein/scripts/telegram_bot.py.example /home/stanweinstein/scripts/telegram_bot.py

# Editar y configurar credenciales
nano /home/stanweinstein/scripts/telegram_bot.py
```

**Buscar las líneas 48-50 y editar:**
```python
# CONFIGURACIÓN TELEGRAM - EDITAR AQUÍ
TELEGRAM_TOKEN = "123456789:ABCdefGHI..."  # ← Tu TOKEN de @BotFather
TELEGRAM_CHAT_ID = "123456789"             # ← Tu CHAT_ID de @userinfobot
```

**Guardar:** Ctrl+O, Enter, Ctrl+X

```bash
# Dar permisos de ejecución
chmod +x /home/stanweinstein/scripts/telegram_bot.py
```

## 4. PROBAR EL BOT

```bash
# Enviar mensaje de prueba
python scripts/telegram_bot.py --test
```

Deberías recibir en Telegram:
```
🤖 Test Sistema Weinstein

Fecha: 10/02/2026 15:30
✅ Bot funcionando correctamente
```

## 4. ACTUALIZAR CRON

```bash
# Como root
sudo cp stanweinstein_cron /etc/cron.d/stanweinstein

# Verificar
sudo cat /etc/cron.d/stanweinstein
```

## 5. CALENDARIO DE EJECUCIÓN

**Lunes a Viernes 23:00**
- Actualización diaria de datos

**Sábado 01:00**
- Agregación semanal
- Análisis de etapas
- Generación de señales

**Sábado 08:00**
- 🔔 NOTIFICACIÓN TELEGRAM (si hay señales)

## 6. LOGS

```bash
# Ver log del bot
tail -f /var/log/stanweinstein/telegram.log

# Ver log del cron
tail -f /var/log/stanweinstein/cron.log
```

## 7. COMANDOS DEL BOT (para implementar después)

Los siguientes comandos se pueden implementar más adelante:

```
/señales  - Ver señales de los últimos 7 días
/etapa2   - Ver acciones en Etapa 2
/buscar AAPL - Info de una acción
```

Para activarlos, necesitarías ejecutar el bot en modo escucha:
```bash
python scripts/telegram_bot.py --listen
```

## 8. SEGURIDAD - PROTEGER CREDENCIALES

**IMPORTANTE:** El archivo `telegram_bot.py` contiene credenciales y NO debe subirse a Git.

### **8.1 Verificar .gitignore**

```bash
cat .gitignore | grep telegram_bot.py
```

Debería mostrar:
```
scripts/telegram_bot.py
```

Si NO está, añadirlo:
```bash
echo "scripts/telegram_bot.py" >> .gitignore
```

### **8.2 Verificar que NO esté en Git**

```bash
git status
```

`telegram_bot.py` NO debería aparecer en la lista de archivos a subir.

### **8.3 Subir solo el archivo .example**

```bash
# Añadir solo el ejemplo (sin credenciales)
git add scripts/telegram_bot.py.example
git add .gitignore
git commit -m "Add telegram bot template (credentials not included)"
git push
```

**✅ Ahora puedes hacer push seguro:** Solo se sube `telegram_bot.py.example` (plantilla) pero NO `telegram_bot.py` (con credenciales reales).

## 9. TROUBLESHOOTING

**No llegan mensajes:**
```bash
# Verificar TOKEN y CHAT_ID en telegram_bot.py
grep "TELEGRAM_TOKEN\|TELEGRAM_CHAT_ID" /home/stanweinstein/scripts/telegram_bot.py

# Probar envío manual
python scripts/telegram_bot.py --test
```

**Error "Module not found: requests":**
```bash
pip install requests --break-system-packages
```

**Cron no ejecuta:**
```bash
# Verificar permisos
ls -l /etc/cron.d/stanweinstein

# Debe ser: -rw-r--r-- root root

# Verificar logs
tail -50 /var/log/stanweinstein/cron.log
```

## 10. TESTING MANUAL

```bash
# Forzar notificación (sin esperar al sábado)
python scripts/telegram_bot.py --notify
```

Esto enviará las señales no notificadas que haya en la BD.
