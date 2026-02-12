// Sistema Weinstein - Stock Detail JavaScript

const BASE_PATH = window.BASE_PATH || '';
const TICKER = window.TICKER;

let chartInstance = null;
let fullHistoryData = null; // Guardar datos completos

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
    
    // Marcar botón correspondiente como activo
    const buttonTexts = {
        26: '6M',
        52: '1A',
        104: '2A',
        0: 'Todo'
    };
    
    const buttons = document.querySelectorAll('.period-btn');
    buttons.forEach(btn => {
        if (btn.textContent === buttonTexts[weeks]) {
            btn.classList.add('active');
        }
    });
    
    // Crear/actualizar gráfico
    createChart(filteredData);
}

// Mostrar información actual
function displayCurrentInfo(current) {
    // Etapa
    const stageName = getStageInfo(current.stage);
    document.getElementById('current-stage').innerHTML = 
        `<span style="font-size: 3rem;">${current.stage}</span><br>${stageName.name}`;
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

// Crear gráfico con Chart.js
function createChart(history) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    // Preparar datos
    const labels = history.map(h => formatDateShort(h.week_end_date));
    const prices = history.map(h => h.close);
    const ma30 = history.map(h => h.ma30);
    
    // Colores por etapa para el fondo
    const backgroundColors = history.map(h => {
        const info = getStageInfo(h.stage);
        return info.color + '10'; // Añadir transparencia
    });
    
    // Destruir gráfico anterior si existe
    if (chartInstance) {
        chartInstance.destroy();
    }
    
    // Crear gráfico
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Precio',
                    data: prices,
                    borderColor: '#2563eb',
                    backgroundColor: backgroundColors,
                    borderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    fill: true,
                    tension: 0.1
                },
                {
                    label: 'MA30',
                    data: ma30,
                    borderColor: '#f59e0b',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    fill: false,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += '$' + context.parsed.y.toFixed(2);
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toFixed(0);
                        }
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
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
