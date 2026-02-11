# Sistema de Trading Automático - Metodología Stan Weinstein

**Versión:** 0.3.0 - Sistema Completo con Backtesting y Alertas  
**Fecha:** Febrero 2026  
**Estado:** Producción

---

## 📊 Estado Actual del Sistema

### **Datos monitorizados:**
- **396 acciones activas** (USA: ~390)
- **~198,000 datos diarios** (~500 días por acción)
- **~41,000 semanas agregadas** (~104 semanas por acción)
- **~29,000 semanas analizadas** (con MA30 y etapa)
- **236 señales históricas** (42 BUY, 0 SELL, 194 cambios)

### **Distribución actual del mercado:**
- **Etapa 1 (Base)**: 349 acciones (88.1%)
- **Etapa 2 (Alcista)**: 11 acciones (2.8%)
- **Etapa 3 (Techo)**: 31 acciones (7.8%)
- **Etapa 4 (Bajista)**: 5 acciones (1.3%)

---

## 🎯 Descripción

Sistema automatizado de trading que identifica las **4 etapas del ciclo de precios** según la metodología de Stan Weinstein:

1. **Etapa 1 - Base/Consolidación**: Precio cerca de MA30, pendiente plana
2. **Etapa 2 - Tendencia Alcista**: Precio > MA30 (+5%), pendiente > +2%
3. **Etapa 3 - Techo/Distribución**: Precio cerca de MA30 tras Etapa 2
4. **Etapa 4 - Tendencia Bajista**: Precio < MA30 (-5%), pendiente < -2%

### **Señales de Trading:**
- 🟢 **BUY**: Transición Etapa 1 → 2 (ruptura alcista)
- 🔴 **SELL**: Transición Etapa 2/3 → 4 (ruptura bajista)

### **Gestión de Riesgo:**
- **Stop Loss Inicial**: 8% por debajo del precio de entrada
- **Trailing Stop**: 15% desde máximo alcanzado
- **Salida por cambio de etapa**: Si pasa a Etapa 3 o 4
- **Salida por MA30**: Si rompe MA30 a la baja

---

## 🏗️ Arquitectura del Sistema

```
Twelve Data / Yahoo Finance
         ↓
   data_collector.py
         ↓
    daily_data (MariaDB)
         ↓
    aggregator.py
         ↓
   weekly_data (MA30 + slope)
         ↓
    analyzer.py
         ↓
   weekly_data (+ stage)
         ↓
    signals.py
         ↓
    signals (BUY/SELL)
         ↓
   telegram_bot.py (sábados 08:00)
```

---

## 📅 Automatización

### **Cron Jobs:**

- **L-V 23:00**: Actualización diaria (`daily_update.py`)
- **Sábado 01:00**: Proceso semanal (`weekly_process.py`)
- **Sábado 08:00**: 🔔 Alertas Telegram (`telegram_bot.py`)

---

## 🚀 Quick Start

```bash
# 1. Setup inicial
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --break-system-packages

# 2. Configurar API keys
nano app/config.py  # TWELVEDATA_API_KEY

# 3. Crear BD
mysql -u root -p < schema.sql

# 4. Cargar acciones
python scripts/load_stocks_from_csv.py empresas.csv

# 5. Carga datos históricos
python scripts/load_missing_historical.py

# 6. Agregación inicial
python scripts/init_weekly_aggregation.py

# 7. Análisis inicial
python scripts/analyze_initial.py

# 8. Configurar Telegram
nano scripts/telegram_bot.py  # TOKEN, CHAT_ID
python scripts/telegram_bot.py --test

# 9. Instalar cron
sudo cp stanweinstein_cron /etc/cron.d/stanweinstein
```

---

## 📁 Estructura del Proyecto

```
stanweinstein/
├── app/
│   ├── config.py
│   ├── database.py
│   ├── data_collector.py
│   ├── aggregator.py
│   ├── analyzer.py
│   └── signals.py
├── scripts/
│   ├── daily_update.py
│   ├── weekly_process.py
│   ├── telegram_bot.py
│   ├── load_stocks_from_csv.py
│   ├── load_missing_historical.py
│   ├── init_weekly_aggregation.py
│   ├── analyze_initial.py
│   ├── backtest_weinstein.py
│   └── backtest_with_stoploss.py
├── docs/
│   ├── PREPARACION_SERVIDOR.md
│   └── CONFIGURACION_SISTEMA.md
├── README.md
└── stanweinstein_cron
```

---

## 🧪 Testing

```bash
# Backtesting sin stops
python scripts/backtest_weinstein.py

# Backtesting con stops (realista)
python scripts/backtest_with_stoploss.py

# Test telegram
python scripts/telegram_bot.py --test
```

---

## 📊 Consultas Útiles

### Estado del sistema:
```sql
SELECT 'Acciones' as metrica, COUNT(*) FROM stocks
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

---

## 📚 Documentación Completa

- **[PREPARACION_SERVIDOR.md](docs/PREPARACION_SERVIDOR.md)**: Setup del servidor
- **[CONFIGURACION_SISTEMA.md](docs/CONFIGURACION_SISTEMA.md)**: Configuración detallada
- **[INSTALACION_TELEGRAM.md](INSTALACION_TELEGRAM.md)**: Setup del bot

---

## 📝 Changelog

### v0.3.0 (Febrero 2026)
- ✅ Bot de Telegram con alertas
- ✅ Backtesting con stop loss
- ✅ Sistema validado (396 acciones)
- ✅ Documentación completa

### v0.2.0 (Febrero 2026)
- ✅ Agregación semanal
- ✅ Análisis de etapas
- ✅ Generación de señales

### v0.1.0 (Febrero 2026)
- ✅ Setup inicial
- ✅ Data collector
- ✅ Base de datos

---

**⚠️ DISCLAIMER**: Sistema educativo. No constituye asesoramiento financiero.
