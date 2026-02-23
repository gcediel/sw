// Sistema Weinstein - Stock Detail JavaScript (Lightweight Charts)

const BASE_PATH = window.BASE_PATH || '';
const TICKER = window.TICKER;

let chart = null;
let candleSeries = null;
let ma30Series = null;
let volumeSeries = null;
let rsSeries = null;
let fullHistoryData = null;

// Cargar datos al iniciar
document.addEventListener('DOMContentLoaded', function() {
    loadStockDetail();
});

// Cargar detalle de acción
async function loadStockDetail() {
    try {
        const response = await fetch(`${BASE_PATH}/api/stock/${TICKER}`);

        if (!response.ok) {
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // Guardar datos completos para filtrado posterior
        fullHistoryData = data.history;

        // Mostrar contenido
        document.getElementById('loading').style.display = 'none';
        document.getElementById('content').style.display = 'block';

        // Actualizar título
        document.getElementById('page-title').textContent = `${data.ticker} - Sistema Weinstein`;
        document.getElementById('stock-title').textContent = data.ticker;
        document.getElementById('stock-name').textContent = data.name;

        // Mostrar información actual
        displayCurrentInfo(data.current);

        // Crear gráfico por defecto (1 año = 52 semanas)
        loadChart(52);

        // Mostrar señales
        displaySignals(data.signals);

        // Mostrar historial de etapas
        displayStageHistory(data.history);

    } catch (error) {
        console.error('Error cargando acción:', error);
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'block';
        document.getElementById('error-message').textContent =
            `No se pudo cargar la información de ${TICKER}. ${error.message}`;
    }
}

// Cargar gráfico con período específico
function loadChart(weeks) {
    if (!fullHistoryData) return;

    // Filtrar datos según período
    let filteredData = fullHistoryData;
    if (weeks > 0 && fullHistoryData.length > weeks) {
        filteredData = fullHistoryData.slice(-weeks);
    }

    // Actualizar botones activos
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    const buttonTexts = {
        26: '6M',
        52: '1A',
        104: '2A',
        0: 'Todo'
    };

    document.querySelectorAll('.period-btn').forEach(btn => {
        if (btn.textContent === buttonTexts[weeks]) {
            btn.classList.add('active');
        }
    });

    createChart(filteredData);
}

// Crear gráfico con Lightweight Charts
function createChart(history) {
    const container = document.getElementById('priceChart');

    // Destruir gráfico anterior si existe
    if (chart) {
        chart.remove();
        chart = null;
    }

    // Crear chart
    chart = LightweightCharts.createChart(container, {
        autoSize: true,
        layout: {
            background: { type: 'solid', color: '#ffffff' },
            textColor: '#333',
            fontFamily: "'Segoe UI', sans-serif",
        },
        grid: {
            vertLines: { color: '#f0f0f0' },
            horzLines: { color: '#f0f0f0' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#d1d5db',
        },
        timeScale: {
            borderColor: '#d1d5db',
            timeVisible: false,
        },
    });

    // Serie de velas
    candleSeries = chart.addSeries(
        LightweightCharts.CandlestickSeries,
        {
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderDownColor: '#ef4444',
            borderUpColor: '#22c55e',
            wickDownColor: '#ef4444',
            wickUpColor: '#22c55e',
        }
    );

    // Serie de línea MA30
    ma30Series = chart.addSeries(
        LightweightCharts.LineSeries,
        {
            color: '#f59e0b',
            lineWidth: 2,
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
        }
    );

    // Panel RS: fuerza relativa vs SPY (zona central)
    rsSeries = chart.addSeries(
        LightweightCharts.LineSeries,
        {
            color: '#8b5cf6',
            lineWidth: 1.5,
            priceScaleId: 'rs',
            lastValueVisible: false,
            priceLineVisible: false,
            crosshairMarkerVisible: true,
        }
    );
    chart.priceScale('rs').applyOptions({
        scaleMargins: { top: 0.62, bottom: 0.22 },
        borderVisible: false,
    });

    // Serie de volumen (histograma en panel inferior)
    volumeSeries = chart.addSeries(
        LightweightCharts.HistogramSeries,
        {
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
            lastValueVisible: false,
            priceLineVisible: false,
        }
    );
    chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.84, bottom: 0 },
    });

    // Precio ocupa el panel superior (60%)
    chart.priceScale('right').applyOptions({
        scaleMargins: { top: 0.02, bottom: 0.42 },
    });

    // Preparar datos de velas
    const candleData = history
        .filter(h => h.open !== null && h.high !== null && h.low !== null)
        .map(h => ({
            time: h.week_end_date,
            open: h.open,
            high: h.high,
            low: h.low,
            close: h.close,
        }));

    // Preparar datos MA30
    const ma30Data = history
        .filter(h => h.ma30 !== null)
        .map(h => ({
            time: h.week_end_date,
            value: h.ma30,
        }));

    // Preparar datos de fuerza relativa (normalizada a 100 al inicio del período)
    const rsRaw = history.filter(h => h.rs !== null);
    const rsBase = rsRaw.length > 0 ? rsRaw[0].rs : null;
    const rsData = rsBase ? rsRaw.map(h => ({
        time: h.week_end_date,
        value: parseFloat((h.rs / rsBase * 100).toFixed(4)),
    })) : [];

    // Preparar datos de volumen
    const volumeData = history
        .filter(h => h.volume !== null)
        .map(h => ({
            time: h.week_end_date,
            value: h.volume,
            color: (h.close >= h.open) ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)',
        }));

    candleSeries.setData(candleData);
    ma30Series.setData(ma30Data);
    rsSeries.setData(rsData);
    volumeSeries.setData(volumeData);

    // Línea base RS en 100 (referencia: paridad con SPY)
    if (rsData.length > 0) {
        rsSeries.createPriceLine({
            price: 100,
            color: '#94a3b8',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: false,
        });
    }

    // Ajustar vista
    chart.timeScale().fitContent();

    // Leyenda con tooltip
    const legendEl = document.createElement('div');
    legendEl.style.cssText = 'position:absolute;top:8px;left:12px;z-index:2;font-size:13px;font-family:sans-serif;color:#333;pointer-events:none;';
    container.style.position = 'relative';
    container.appendChild(legendEl);

    function updateLegend(param) {
        if (!param || !param.time) {
            legendEl.innerHTML = '';
            return;
        }
        const candle = param.seriesData.get(candleSeries);
        const ma = param.seriesData.get(ma30Series);
        if (!candle) return;

        const color = candle.close >= candle.open ? '#22c55e' : '#ef4444';
        let html = `<span style="color:${color}">O:${candle.open.toFixed(2)} H:${candle.high.toFixed(2)} L:${candle.low.toFixed(2)} C:${candle.close.toFixed(2)}</span>`;
        if (ma) {
            html += ` <span style="color:#f59e0b">MA30:${ma.value.toFixed(2)}</span>`;
        }
        const rs = param.seriesData.get(rsSeries);
        if (rs) {
            const rsColor = rs.value >= 100 ? '#8b5cf6' : '#a78bfa';
            html += ` <span style="color:${rsColor}">RS:${rs.value.toFixed(1)}</span>`;
        }
        const vol = param.seriesData.get(volumeSeries);
        if (vol) {
            html += ` <span style="color:#94a3b8">Vol:${formatVolume(vol.value)}</span>`;
        }
        legendEl.innerHTML = html;
    }

    chart.subscribeCrosshairMove(updateLegend);
}

// Mostrar información actual
function displayCurrentInfo(current) {
    // Etapa
    const stageName = getStageInfo(current.stage);
    document.getElementById('current-stage').innerHTML =
        `<span style="font-size: 3rem;">${current.stage}</span><br><span style="font-size: 0.8rem; font-weight: 500;">${stageName.name}</span>`;
    document.getElementById('current-stage').parentElement.parentElement.style.borderLeft =
        `4px solid ${stageName.color}`;

    // Precio
    document.getElementById('current-price').textContent = `$${current.price.toFixed(2)}`;

    // MA30
    document.getElementById('current-ma30').textContent =
        current.ma30 ? `$${current.ma30.toFixed(2)}` : 'N/A';

    // Distancia MA30
    if (current.distance_from_ma30 !== null) {
        const distance = current.distance_from_ma30;
        const distanceEl = document.getElementById('current-distance');
        distanceEl.textContent = `${distance > 0 ? '+' : ''}${distance.toFixed(2)}%`;
        distanceEl.className = 'stat-value ' + (distance > 0 ? 'positive' : distance < 0 ? 'negative' : '');
    } else {
        document.getElementById('current-distance').textContent = 'N/A';
    }

    // Pendiente MA30
    if (current.ma30_slope !== null) {
        const slope = current.ma30_slope * 100;
        const slopeEl = document.getElementById('current-slope');
        slopeEl.textContent = `${slope > 0 ? '+' : ''}${slope.toFixed(2)}%`;
        slopeEl.className = 'stat-value ' + (slope > 0 ? 'positive' : slope < 0 ? 'negative' : '');
    } else {
        document.getElementById('current-slope').textContent = 'N/A';
    }

    // Última actualización
    document.getElementById('last-update').textContent = formatDate(current.week_end_date);
}

// Mostrar señales
function displaySignals(signals) {
    const container = document.getElementById('signals-list');

    if (signals.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6c757d;">No hay señales generadas para esta acción</p>';
        return;
    }

    let html = '<div style="display: flex; flex-direction: column; gap: 1rem;">';

    signals.forEach(signal => {
        const badgeClass = signal.type === 'BUY' ? 'badge-buy' : 'badge-sell';
        const icon = signal.type === 'BUY' ? '🟢' : '🔴';

        html += `
            <div style="padding: 1rem; background: #f9fafb; border-radius: 0.5rem; border-left: 4px solid ${signal.type === 'BUY' ? '#10b981' : '#ef4444'};">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                    <span class="badge ${badgeClass}">${icon} ${signal.type}</span>
                    <span style="font-size: 0.875rem; color: #6c757d;">${formatDate(signal.date)}</span>
                </div>
                <div style="font-size: 0.875rem;">
                    <strong>Transición:</strong> Etapa ${signal.stage_from} → ${signal.stage_to}<br>
                    <strong>Precio:</strong> $${signal.price.toFixed(2)}
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

// Mostrar historial de etapas
function displayStageHistory(history) {
    const container = document.getElementById('stage-history');

    // Detectar cambios de etapa
    const changes = [];
    let previousStage = null;

    history.forEach((week, index) => {
        if (week.stage !== previousStage) {
            changes.push({
                date: week.week_end_date,
                stage: week.stage,
                previous: previousStage,
                index: index
            });
            previousStage = week.stage;
        }
    });

    if (changes.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6c757d;">Sin cambios de etapa en el período</p>';
        return;
    }

    // Mostrar últimos 10 cambios
    const recentChanges = changes.slice(-10).reverse();

    let html = '<div style="display: flex; flex-direction: column; gap: 0.75rem;">';

    recentChanges.forEach(change => {
        const stageInfo = getStageInfo(change.stage);
        const arrow = change.previous !== null ? `Etapa ${change.previous} → ${change.stage}` : `Etapa ${change.stage}`;

        html += `
            <div style="padding: 0.75rem; background: #f9fafb; border-radius: 0.5rem; border-left: 4px solid ${stageInfo.color};">
                <div style="font-weight: 600; margin-bottom: 0.25rem;">${arrow}</div>
                <div style="font-size: 0.875rem; color: #6c757d;">${formatDate(change.date)}</div>
                <div style="font-size: 0.875rem; color: #4b5563; margin-top: 0.25rem;">${stageInfo.name}</div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

// Obtener información de etapa
function getStageInfo(stage) {
    const stages = {
        1: { name: 'Base/Consolidación', color: '#6c757d' },
        2: { name: 'Tendencia Alcista', color: '#10b981' },
        3: { name: 'Techo/Distribución', color: '#f59e0b' },
        4: { name: 'Tendencia Bajista', color: '#ef4444' }
    };
    return stages[stage] || { name: 'Desconocida', color: '#6c757d' };
}

// ============================================================
// MODAL COMPRA
// ============================================================

function openBuyModal() {
    const modal = document.getElementById('buy-modal');
    if (!modal) return;
    // Pre-rellenar ticker y precio
    const ticker = window.TICKER || '';
    document.getElementById('bm-ticker-label').textContent = ticker;
    document.getElementById('bm-date').value = new Date().toISOString().slice(0, 10);

    // Precio: último precio semanal disponible
    let price = null;
    let ma30 = null;
    if (fullHistoryData && fullHistoryData.length > 0) {
        const last = fullHistoryData[fullHistoryData.length - 1];
        price = last.close;
        ma30 = last.ma30;
    }
    if (price) document.getElementById('bm-price').value = price.toFixed(2);
    if (ma30) document.getElementById('bm-stop').value = ma30.toFixed(2);

    document.getElementById('bm-error').style.display = 'none';
    modal.style.display = 'block';
    document.getElementById('bm-qty').focus();
}

function closeBuyModal() {
    document.getElementById('buy-modal').style.display = 'none';
}

async function saveBuyModal() {
    const ticker = window.TICKER || '';
    const entry_date = document.getElementById('bm-date').value;
    const entry_price = parseFloat(document.getElementById('bm-price').value);
    const quantity = parseFloat(document.getElementById('bm-qty').value);
    const stop_loss = parseFloat(document.getElementById('bm-stop').value);
    const notes = document.getElementById('bm-notes').value.trim();
    const errEl = document.getElementById('bm-error');

    if (!entry_date || isNaN(entry_price) || isNaN(quantity) || isNaN(stop_loss)) {
        errEl.textContent = 'Completa todos los campos obligatorios';
        errEl.style.display = 'block';
        return;
    }
    if (entry_price <= 0 || quantity <= 0 || stop_loss <= 0) {
        errEl.textContent = 'Precio, cantidad y stop loss deben ser positivos';
        errEl.style.display = 'block';
        return;
    }

    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ticker, entry_date, entry_price, quantity, stop_loss, notes})
        });
        const data = await resp.json();
        if (!resp.ok) {
            errEl.textContent = data.error || 'Error al guardar';
            errEl.style.display = 'block';
            return;
        }
        closeBuyModal();
        window.location.href = `${BASE_PATH}/portfolio`;
    } catch (e) {
        errEl.textContent = 'Error de conexión';
        errEl.style.display = 'block';
    }
}

// Utilidades
function formatDate(dateString) {
    const date = new Date(dateString);
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return date.toLocaleDateString('es-ES', options);
}

function formatDateShort(dateString) {
    const date = new Date(dateString);
    const day = date.getDate();
    const month = date.toLocaleDateString('es-ES', { month: 'short' });
    return `${day} ${month}`;
}

function formatVolume(v) {
    if (v >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
    return v.toString();
}
