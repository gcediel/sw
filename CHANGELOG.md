# Changelog - Sistema Weinstein

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
