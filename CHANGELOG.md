# Changelog - Sistema Weinstein

## [0.4.0] - 2026-03-02

### ✨ Nuevas Funcionalidades

#### Mansfield Relative Strength (MRS)
- **Gráfico:** panel central sustituye la RS normalizada a 100 por el MRS real, oscilando alrededor de 0. Linea base punteada en 0. Color morado cuando MRS > 0, mas claro cuando MRS < 0. Tooltip muestra "MRS:X.X"
- **Backend:** calculo correcto del MRS en `web/main.py`: se cargan 156 semanas (104 visibles + 52 de precalentamiento para la MA52). Formula: `MRS = (rs_ratio / MA52_rs_ratio - 1) × 100`
- **Filtro de senales:** `signals.py` descarta senales BUY cuando MRS ≤ 0 (la accion no supera al SPY respecto a su media historica de 52 semanas)

#### Filtro de Volumen en Ruptura
- Las senales BUY requieren que el volumen de la semana de ruptura sea ≥ 1.5× la media de las semanas de la base (parametro `VOLUME_SPIKE_THRESHOLD`). Confirma que la ruptura esta respaldada por interes real del mercado

#### Script `regenerate_buy_signals.py`
- Utilidad para borrar senales BUY de un periodo y regenerarlas con los filtros actuales
- Uso: `python scripts/regenerate_buy_signals.py [--weeks N] [--dry-run]`
- Permite aplicar nuevos filtros retroactivamente sin esperar al proximo proceso semanal

### 🔧 Mejoras Tecnicas

#### Backtest alineado con signals.py
- `backtest_v3.py` reescrito para replicar exactamente la logica de `_is_valid_buy_breakout`: trabaja sobre la lista filtrada por MA30/slope (igual que el generador de senales), aplica todos los criterios (resistencia, base solida, volumen y MRS)
- Resultado: backtest coherente con lo que el sistema generaria en produccion

### 📊 Impacto de los Nuevos Filtros

Comparativa backtest antes/despues de los nuevos filtros:

| Metrica | Sin filtros | Con filtros |
|---------|-------------|-------------|
| Operaciones | 191 | 108 |
| Win rate | 35.6% | 52.8% |
| Retorno promedio | +1.35% | +2.36% |
| Retorno mediano | -7.35% | +0.94% |
| Salidas por stop loss | 92.7% | 35.2% |
| Duracion media | 27 dias | 80 dias |

Las señales del 27-feb-2026 se redujeron de 52 a 6 tras aplicar los filtros retroactivamente.

---

## [0.3.0] - 2025-02-12

### ✨ Nuevas Funcionalidades

#### Dashboard Web Completo
- **5 páginas interactivas** con FastAPI:
  - Dashboard principal con estadísticas y resumen
  - Lista completa de acciones con búsqueda y filtros
  - Historial de señales BUY/SELL con filtros temporales
  - Watchlist de acciones en Etapa 2
  - Página de detalle individual por acción

#### Ordenación de Tablas
- **Ordenación dinámica** en todas las tablas por cualquier columna
- Click en header para ordenar: Ascendente → Descendente → Original
- Indicadores visuales: ↕ (sin ordenar), ↑ (asc), ↓ (desc)
- Soporta múltiples tipos de datos: texto, números, fechas, monedas, porcentajes
- Librería reutilizable `table-sort.js`

#### Selector de Período en Gráficos
- **4 opciones de visualización**:
  - **6M**: Últimos 6 meses (26 semanas)
  - **1A**: Último año (52 semanas) - Por defecto
  - **2A**: Últimos 2 años (104 semanas)
  - **Todo**: Histórico completo
- Botón activo visualmente resaltado (fondo azul)
- Cambio dinámico sin recargar página

#### Gráficos Interactivos
- Chart.js para visualización de precios y MA30
- Fondo coloreado por etapa del mercado
- Tooltips informativos al pasar el ratón
- MA30 con línea discontinua naranja
- Responsive y optimizado para móviles

### 🔧 Mejoras Técnicas

#### Arquitectura Web
- FastAPI como framework principal
- Jinja2 para templates HTML
- Separación clara entre backend (Python) y frontend (JavaScript)
- API REST completa con 10 endpoints
- Paginación eficiente (50 elementos por página)

#### Optimizaciones
- Búsqueda en tiempo real con debounce (500ms)
- Carga asíncrona de datos con fetch API
- Actualización dinámica sin recargar página
- Cache de datos históricos para filtrado rápido
- RequestAnimationFrame para sincronización de DOM

#### UX/UI
- Diseño responsive para móvil/tablet/desktop
- Badges visuales para etapas y tipos de señales
- Colores semánticos (verde=alcista, rojo=bajista, gris=base, amarillo=techo)
- Loading states y mensajes informativos
- Navegación consistente entre páginas

### 🔐 Seguridad

#### Git Security
- Separación de credenciales del código fuente
- Archivos `.example` como plantillas públicas
- `.gitignore` completo para proteger datos sensibles
- `telegram_bot.py` excluido de Git
- `config.py` excluido de Git

#### Configuración Segura
- Variables de entorno para credenciales
- Ejecución como usuario sin privilegios
- Proxy reverso con Apache (acceso indirecto)
- Puerto 8000 solo accesible desde localhost

### 🐛 Correcciones

#### Problema: IDs en tbody
- **Síntoma**: Headers de tabla desaparecían al cargar datos
- **Causa**: IDs estaban en `<tbody>` en lugar de `<table>`
- **Solución**: Mover IDs a `<table>` y usar IDs separados (`*-table` y `*-tbody`)

#### Problema: base_path vacío
- **Síntoma**: CSS/JS no cargaban en producción
- **Causa**: `request.scope.get("root_path")` devolvía string vacío
- **Solución**: Hardcodear `base_path="/sw"` en todas las respuestas

#### Problema: Caché del navegador
- **Síntoma**: Cambios no se reflejaban al actualizar
- **Causa**: Navegador cacheaba archivos JS/CSS antiguos
- **Solución**: Documentar uso de Ctrl+Shift+R para hard refresh

#### Problema: Ordenación duplicada
- **Síntoma**: `grep -c` mostraba el doble de llamadas esperadas
- **Causa**: Cuenta líneas, no llamadas (verificación + llamada)
- **Solución**: Verificación correcta entendiendo que son 2 líneas por tabla

### 📚 Documentación

#### Nuevos Documentos
- `README.md` - Resumen general del proyecto
- `INSTALACION_WEB.md` - Guía completa del dashboard web
- `CHANGELOG.md` - Historial de cambios

#### Documentación Actualizada
- Instrucciones de instalación paso a paso
- Sección de solución de problemas expandida
- Ejemplos de uso de todas las funcionalidades
- Checklist de verificación post-instalación

### 📊 Estadísticas

- **396 acciones** monitorizadas
- **5 páginas** web interactivas
- **10 endpoints** API REST
- **7 tablas** con ordenación dinámica
- **4 opciones** de período en gráficos

---

## [0.2.0] - 2025-02-11

### ✨ Nuevas Funcionalidades

#### Dashboard Web Inicial
- Página principal con estadísticas básicas
- API REST para acceso a datos
- Integración con Chart.js

#### Automatización
- Cron semanal configurado (sábados 8:00 AM)
- Notificaciones Telegram de señales nuevas
- Bot de Telegram interactivo

### 🔧 Mejoras

- Optimización del análisis de etapas
- Mejora en detección de breakouts
- Validación de volumen en señales

---

## [0.1.0] - 2025-02-06

### ✨ Primera Versión

#### Funcionalidades Core
- Análisis de 4 etapas de Weinstein
- Cálculo de MA30 y pendientes
- Generación de señales BUY/SELL
- Base de datos MariaDB
- Script de actualización (`update_stocks.py`)

#### Análisis Técnico
- 396 acciones del S&P 500
- Datos históricos desde 2020
- Detección automática de cambios de etapa
- Análisis de volumen

---

## Leyenda

- ✨ Nueva funcionalidad
- 🔧 Mejora técnica
- 🐛 Corrección de bug
- 🔐 Seguridad
- 📚 Documentación
- 📊 Estadísticas
- ⚡ Performance
- 🎨 UI/UX

---

**Sistema Weinstein - Trading Algorítmico Basado en Análisis Técnico**
