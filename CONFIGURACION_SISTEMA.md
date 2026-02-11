# Configuración del Sistema Weinstein v0.3

**Última actualización:** Febrero 2026

---

## 📋 Componentes del Sistema

| Componente | Archivo | Función |
|------------|---------|---------|
| Data Collector | `app/data_collector.py` | Descarga datos (Twelve Data + yfinance) |
| Aggregator | `app/aggregator.py` | Agrega semanalmente + MA30 |
| Analyzer | `app/analyzer.py` | Detecta las 4 etapas |
| Signal Generator | `app/signals.py` | Genera señales BUY/SELL |
| Telegram Bot | `scripts/telegram_bot.py` | Envía alertas automáticas |

---

## ⚙️ Parámetros Principales (`app/config.py`)

```python
# API
TWELVEDATA_API_KEY = "tu_api_key"
RATE_LIMIT_DELAY = 8  # segundos (7.5 req/min)

# Weinstein
MA30_SLOPE_THRESHOLD = 0.02  # 2% pendiente significativa
PRICE_MA30_THRESHOLD = 0.05  # 5% cerca de MA30
MIN_WEEKS_FOR_ANALYSIS = 35  # Mínimo para MA30

# Stop Loss (backtesting)
INITIAL_STOP_PCT = 8.0    # Stop inicial 8%
TRAILING_STOP_PCT = 15.0  # Trailing 15%
```

---

## 📅 Cron Jobs (`/etc/cron.d/stanweinstein`)

```bash
# L-V 23:00 - Actualización diaria
0 23 * * 1-5 stanweinstein python scripts/daily_update.py

# Sábado 01:00 - Proceso semanal
0 1 * * 6 stanweinstein python scripts/weekly_process.py

# Sábado 08:00 - Alertas Telegram
0 8 * * 6 stanweinstein python scripts/telegram_bot.py --notify
```

**Instalación:**
```bash
sudo cp stanweinstein_cron /etc/cron.d/stanweinstein
sudo chmod 644 /etc/cron.d/stanweinstein
```

---

## 📊 Logs

**Ubicación:** `/var/log/stanweinstein/`

```bash
# Ver en tiempo real
tail -f /var/log/stanweinstein/weekly_process.log
tail -f /var/log/stanweinstein/telegram.log

# Buscar errores
grep -i error /var/log/stanweinstein/*.log

# Uso API hoy
grep "$(date +%Y-%m-%d)" /var/log/stanweinstein/daily_update.log | grep -c "twelvedata"
```

---

## 🔍 Consultas SQL Útiles

### Estado del sistema:
```sql
SELECT 'Acciones' as m, COUNT(*) as v FROM stocks
UNION ALL SELECT 'Datos diarios', COUNT(*) FROM daily_data
UNION ALL SELECT 'Semanas', COUNT(*) FROM weekly_data  
UNION ALL SELECT 'Señales', COUNT(*) FROM signals;
```

### Distribución de etapas:
```sql
SELECT 
    CONCAT('Etapa ', stage) as etapa,
    COUNT(*) as acciones
FROM (
    SELECT w.stage
    FROM stocks s
    JOIN weekly_data w ON s.id = w.stock_id
    WHERE w.week_end_date = (
        SELECT MAX(week_end_date) 
        FROM weekly_data 
        WHERE stock_id = w.stock_id
    )
) as latest
GROUP BY stage;
```

### Acciones en Etapa 2:
```sql
SELECT 
    s.ticker,
    ROUND(w.close, 2) as precio,
    ROUND(w.ma30_slope * 100, 2) as pendiente_pct
FROM stocks s
JOIN weekly_data w ON s.id = w.stock_id
WHERE w.week_end_date = (
    SELECT MAX(week_end_date) 
    FROM weekly_data 
    WHERE stock_id = w.stock_id
)
AND w.stage = 2
ORDER BY w.ma30_slope DESC;
```

---

## 🛠️ Troubleshooting

### No llegan alertas Telegram:
```bash
python scripts/telegram_bot.py --test
tail -50 /var/log/stanweinstein/telegram.log
```

### Actualización diaria falla:
```bash
tail -100 /var/log/stanweinstein/daily_update.log
grep "$(date +%Y-%m-%d)" /var/log/stanweinstein/daily_update.log | grep -c "twelvedata"
```

### Verificar cron:
```bash
sudo cat /etc/cron.d/stanweinstein
sudo grep stanweinstein /var/log/cron
```

---

**Sistema v0.3.0** - Configuración Completa
