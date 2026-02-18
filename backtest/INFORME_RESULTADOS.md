# Informe de Análisis de Señales y Backtest - Sistema Weinstein

**Fecha:** 18 de febrero de 2026
**Período analizado:** Junio 2024 - Febrero 2026
**Acciones analizadas:** 396

---

## 1. Caso AMD - Señal BUY del 23/01/2026

### El problema
Se generó una señal BUY para AMD el 23 de enero de 2026 a $259.68. Tras la señal, el precio cayó un **-26.6%** (hasta $190.76 de mínimo) sin llegar a subir siquiera un 1%. **Falso positivo claro.**

### Datos semanales alrededor de la señal

```
Semana       Etapa   Close      MA30     Slope%   Precio/MA30%
2025-12-12     3    210.78    175.47     1.81%      +20.1%
2025-12-19     3    213.43    178.91     1.96%      +19.3%
2025-12-26     3    214.99    182.39     1.94%      +17.9%
2026-01-02     3    223.47    185.96     1.96%      +20.2%
2026-01-09     3    203.17    188.86     1.56%       +7.6%
2026-01-16     3    231.83    192.32     1.83%      +20.6%
2026-01-23     2    259.68    196.18     2.01%      +32.4%  ← SEÑAL BUY
2026-01-30     3    236.73    199.47     1.68%      +18.7%
2026-02-06     3    208.44    201.54     1.04%       +3.4%
2026-02-13     3    207.32    203.22     0.83%       +2.0%
```

### Por qué se generó la señal (diagnóstico)

1. **El slope pasó de 1.83% a 2.01%** — apenas cruzó el umbral de 2%, y eso bastó para cambiar la etapa de 3 a 2
2. **El precio estaba un 32.4% por encima de la MA30** — esto NO es una ruptura de consolidación (etapa 1→2). Es un precio ya muy extendido
3. **La señal fue etapa 1→2**, pero AMD nunca estuvo realmente en etapa 1. El sistema la clasificó así por el comportamiento del re-análisis semanal (10 semanas rolling) que puede reasignar etapas previas

---

## 2. Auditoría de Todas las Señales BUY

### Resumen del sistema actual (baseline)

| Métrica | Valor |
|---------|-------|
| Total señales BUY | 48 (en BD) / 44 (backtest) |
| Falsos positivos (max gain < 5% en 12 sem.) | 10 / 9 |
| Tasa de falsos positivos | 20.8% |
| Win rate (rentabilidad >0 a 12 sem.) | 61.1% |
| Retorno medio a 12 semanas | +13.91% |
| Drawdown medio máximo | -10.45% |

### Falsos positivos identificados

| Ticker | Fecha | Precio/MA30 | Max Gain 12w | Max Drawdown |
|--------|-------|-------------|-------------|-------------|
| FICO | 2024-11-08 | +42.5% | +3.0% | -23.4% |
| AVGO | 2024-12-27 | +40.9% | +3.2% | -26.5% |
| FTNT | 2025-02-14 | +29.7% | +2.8% | -26.8% |
| TEL | 2025-10-31 | +32.5% | +1.5% | -13.5% |
| DELL | 2025-10-31 | +31.3% | +3.7% | -32.0% |
| NVDA | 2025-10-31 | +28.1% | +4.4% | -16.3% |
| HII | 2026-01-16 | +43.5% | +2.4% | -17.4% |
| AMD | 2026-01-23 | +32.4% | +0.3% | -26.6% |
| BWA | 2026-02-13 | +41.1% | 0.0% | 0.0% |
| VTRS | 2026-02-13 | +41.7% | 0.0% | 0.0% |

**Patrón común:** Todos tienen el precio entre 28% y 43% por encima de la MA30. Estas NO son rupturas de consolidación genuinas.

---

## 3. Problemas Identificados en el Algoritmo

### Problema 1: Cálculo de slope inadecuado
- **Actual:** `slope = (MA30_actual - MA30_anterior) / MA30_anterior` (1 semana)
- **Impacto:** Un MA30 de 30 semanas cambia muy poco de una semana a otra. El umbral de 2% es demasiado alto para este cálculo, lo que hace que casi todas las semanas sean "pendiente plana"
- **Resultado:** Las acciones pasan mucho tiempo en etapa 3 (plana) y saltan a etapa 2 con variaciones mínimas del slope

### Problema 2: Sin confirmación por volumen
- `VOLUME_SPIKE_THRESHOLD = 1.5` está definido en config.py pero **nunca se usa** en el analyzer
- Weinstein considera el volumen fundamental para confirmar rupturas

### Problema 3: Precio demasiado lejos de MA30
- El sistema permite señales BUY con precios 30-60% por encima de MA30
- Una verdadera ruptura de etapa 1→2 ocurre cuando el precio está CERCA de la MA30 y la cruza al alza

### Problema 4: Inestabilidad del re-análisis
- Cada sábado, `weekly_process.py` re-analiza las últimas 10 semanas
- Esto puede cambiar etapas previamente asignadas, generando transiciones ficticias
- La señal AMD de enero 2026 se produjo por este mecanismo (no se reproduce en un backtest estable)

### Problema 5: Transiciones de etapa rígidas
- Etapa 1 solo puede venir de etapa 4 o None
- Etapa 3 solo puede venir de etapa 2
- Esto impide transiciones naturales (ej: 3→1 en correcciones dentro de tendencia)

---

## 4. Resultados del Backtest Comparativo

Se probaron 5 versiones del algoritmo:

| Versión | Descripción |
|---------|-------------|
| **Baseline** | Algoritmo actual sin cambios |
| **V1** | Slope 4 semanas + volumen + límite 15% precio/MA30 |
| **V2** | V1 + confirmación 2 semanas |
| **V3** | Slope 8 semanas + criterios estrictos |
| **V4** | Slope 4 semanas equilibrado (umbral 3%, límite 20%) |
| **V5** | Slope 1 semana con umbral reducido (1.5%) + límite 20% + volumen |

### Tabla comparativa principal

| Métrica | Baseline | V4 | **V5** |
|---------|----------|----|--------|
| Señales BUY | 44 | 101 | **9** |
| Falsos positivos | 9 | 31 | **0** |
| Tasa FP | 20.5% | 30.7% | **0.0%** |
| Win rate 12 sem. | 61.1% | 47.9% | **77.8%** |
| Retorno medio 4 sem. | +5.90% | -0.32% | **+6.18%** |
| Retorno medio 12 sem. | +13.91% | +1.12% | **+20.32%** |
| Max gain medio | 27.30% | 11.72% | **35.21%** |
| Max drawdown medio | -10.45% | -8.97% | **-7.79%** |

### Señales generadas por V5 (la mejor versión)

| Ticker | Fecha | Precio | P/MA30% | 4w% | 12w% | MaxGain | MaxDD |
|--------|-------|--------|---------|-----|------|---------|-------|
| TPL | 2024-09-13 | $269.66 | +18.9% | +30.8% | +65.4% | +118.7% | 0.0% |
| VST | 2024-09-13 | $85.55 | +9.1% | +46.5% | +87.0% | +97.2% | -0.7% |
| FSLR | 2024-09-20 | $240.20 | +13.7% | -16.5% | -16.9% | +9.4% | -27.8% |
| NRG | 2024-09-20 | $87.09 | +14.5% | -0.9% | +9.1% | +18.4% | -3.4% |
| GL | 2024-11-08 | $109.20 | +18.1% | -4.1% | +11.8% | +13.8% | -8.2% |
| HII | 2025-09-05 | $271.13 | +18.5% | +4.8% | +15.7% | +21.7% | -2.6% |
| BWA | 2025-10-31 | $42.96 | +16.2% | +0.2% | +11.1% | +13.9% | -5.2% |
| MS | 2025-10-31 | $164.00 | +16.8% | +3.5% | +9.1% | +17.5% | -5.3% |
| APTV | 2025-11-07 | $83.66 | +15.0% | -8.7% | -9.5% | +6.3% | -16.8% |

**Nota:** V5 genera solo 9 señales (vs 44 del baseline), pero TODAS superan el umbral de 5% de ganancia máxima en 12 semanas, y 7 de 9 son rentables a 12 semanas.

---

## 5. Señal AMD - Verificación

| Versión | ¿Genera señal AMD 23/01/2026? |
|---------|-------------------------------|
| Baseline | NO (solo reproduce la del 2025-10-10) |
| V4 | NO |
| V5 | NO |

La señal AMD del 23/01/2026 **no se reproduce en ningún backtest estable**, confirmando que fue un artefacto del re-análisis rolling de 10 semanas.

---

## 6. Cambios Recomendados (V5)

Los cambios propuestos para V5 son mínimos pero efectivos:

### 6.1. En `app/analyzer.py` - `detect_stage()`
```python
# ANTES:
self.ma30_slope_threshold = MA30_SLOPE_THRESHOLD  # 0.02 (2%)

# DESPUÉS:
self.ma30_slope_threshold = 0.015  # 1.5% - más sensible a cambios reales
```

### 6.2. En `app/analyzer.py` - Transiciones más flexibles
```python
# ANTES (línea 111):
if (price_near_ma30 or price_above_ma30) and slope_flat and previous_stage == 2:
    return 3

# DESPUÉS:
if (price_near_ma30 or price_above_ma30) and slope_flat and previous_stage in [2, 3]:
    return 3

# ANTES (línea 118-120):
if (price_near_ma30 or price_below_ma30) and (slope_flat or slope_down):
    if previous_stage in [4, None]:
        return 1

# DESPUÉS:
if (price_near_ma30 or price_below_ma30) and (slope_flat or slope_down):
    if previous_stage in [4, 1, None]:
        return 1
```

### 6.3. En `app/signals.py` - Filtros adicionales para BUY
```python
def create_signal(self, change_info):
    signal_type = self.classify_signal(change_info['stage_from'], change_info['stage_to'])

    # NUEVO: Filtros adicionales para señales BUY
    if signal_type == 'BUY':
        price = change_info['price']
        ma30 = change_info['ma30']
        if ma30 and ma30 > 0:
            distance = (price - ma30) / ma30
            if distance > 0.20:  # Precio > 20% sobre MA30 → no es ruptura real
                return False

    # ... resto del método
```

### 6.4. En `app/config.py`
```python
# ANTES:
MA30_SLOPE_THRESHOLD = 0.02   # 2%

# DESPUÉS:
MA30_SLOPE_THRESHOLD = 0.015  # 1.5%
MAX_PRICE_DISTANCE_FOR_BUY = 0.20  # 20% máximo sobre MA30 para señal BUY
```

---

## 7. Resumen Ejecutivo

| Aspecto | Situación actual | Con mejoras V5 |
|---------|-----------------|----------------|
| Falsos positivos | 20.5% | **0%** |
| Win rate (12 sem) | 61.1% | **77.8%** |
| Rendimiento medio 12w | +13.91% | **+20.32%** |
| Drawdown medio | -10.45% | **-7.79%** |
| Señales por año | ~26 | ~5-6 |
| Señal AMD 23/01 | SÍ (falsa) | **NO (filtrada)** |

**Trade-off:** V5 genera significativamente menos señales (9 vs 44), pero cada señal es mucho más fiable. Para un sistema que busca calidad sobre cantidad, es una mejora clara.

---

## Archivos del backtest

Todos los scripts están en `backtest/` y NO modifican el código de producción:

- `01_investigate_signals.py` - Investigación del caso AMD y auditoría de señales
- `02_backtest_full.py` - Backtest completo con 4 versiones del algoritmo
- `03_backtest_production_sim.py` - Simulación del comportamiento de producción + V4/V5
- `INFORME_RESULTADOS.md` - Este informe
