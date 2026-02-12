// Sistema Weinstein - Dashboard JavaScript

const BASE_PATH = window.BASE_PATH || '';

// Cargar datos al iniciar la página
document.addEventListener('DOMContentLoaded', function() {
    loadDashboardStats();
    loadRecentSignals();
    loadTopStage2();
});

// Cargar estadísticas del dashboard
async function loadDashboardStats() {
    try {
        const response = await fetch(`${BASE_PATH}/api/dashboard/stats`);
        const data = await response.json();
        
        // Total acciones
        document.getElementById('total-stocks').textContent = data.total_stocks;
        
        // Señales última semana
        document.getElementById('buy-signals').textContent = data.signals_last_week.BUY || 0;
        document.getElementById('sell-signals').textContent = data.signals_last_week.SELL || 0;
        
        // Acciones en Etapa 2
        document.getElementById('stage2-count').textContent = data.stages[2].count;
        
        // Distribución por etapas
        const total = data.total_stocks;
        for (let stage = 1; stage <= 4; stage++) {
            const count = data.stages[stage].count;
            const percent = ((count / total) * 100).toFixed(1);
            
            document.getElementById(`stage-${stage}-count`).textContent = count;
            document.getElementById(`stage-${stage}-percent`).textContent = `${percent}%`;
        }
        
        // Última actualización
        if (data.last_update) {
            const date = new Date(data.last_update);
            document.getElementById('last-update').textContent = formatDate(date);
        }
        
    } catch (error) {
        console.error('Error cargando estadísticas:', error);
    }
}

// Cargar señales recientes
async function loadRecentSignals() {
    try {
        const response = await fetch(`${BASE_PATH}/api/signals?signal_type=BUY&days=30&limit=5`);
        const data = await response.json();
        
        const tbody = document.getElementById('recent-signals');
        tbody.innerHTML = '';
        
        if (data.signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center">No hay señales recientes</td></tr>';
            return;
        }
        
        data.signals.forEach(signal => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><a href="${BASE_PATH}/stock/${signal.ticker}" class="ticker-link">${signal.ticker}</a></td>
                <td>${truncate(signal.name, 30)}</td>
                <td>${formatDate(signal.date)}</td>
                <td><span class="badge badge-${signal.type.toLowerCase()}">${signal.type}</span></td>
                <td><span class="badge badge-stage">Etapa ${signal.stage_from} → ${signal.stage_to}</span></td>
                <td>$${signal.price.toFixed(2)}</td>
            `;
            tbody.appendChild(row);
        });
        
        // Inicializar ordenación (asegurar que el DOM está actualizado)
        requestAnimationFrame(() => {
            if (typeof initTableSort === 'function') {
                initTableSort('recent-signals-table', [
                    { index: 0, type: 'string' },
                    { index: 1, type: 'string' },
                    { index: 2, type: 'date' },
                    { index: 3, type: 'string' },
                    { index: 4, type: 'string' },
                    { index: 5, type: 'currency' }
                ]);
            }
        });
        
    } catch (error) {
        console.error('Error cargando señales:', error);
    }
}

// Cargar top acciones en Etapa 2
async function loadTopStage2() {
    try {
        const response = await fetch(`${BASE_PATH}/api/watchlist`);
        const data = await response.json();
        
        const tbody = document.getElementById('top-stage2');
        tbody.innerHTML = '';
        
        if (data.stocks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No hay acciones en Etapa 2</td></tr>';
            return;
        }
        
        // Top 10
        const top10 = data.stocks.slice(0, 10);
        
        top10.forEach((stock, index) => {
            const row = document.createElement('tr');
            const slopePercent = ((stock.slope || 0) * 100).toFixed(2);
            const slopeClass = stock.slope > 0 ? 'positive' : 'negative';
            
            row.innerHTML = `
                <td>${index + 1}</td>
                <td><a href="${BASE_PATH}/stock/${stock.ticker}" class="ticker-link">${stock.ticker}</a></td>
                <td>${truncate(stock.name, 35)}</td>
                <td>$${stock.close.toFixed(2)}</td>
                <td class="${slopeClass}">${slopePercent > 0 ? '+' : ''}${slopePercent}%</td>
            `;
            tbody.appendChild(row);
        });
        
        // Inicializar ordenación (asegurar que el DOM está actualizado)
        requestAnimationFrame(() => {
            if (typeof initTableSort === 'function') {
                initTableSort('top-stage2-table', [
                    { index: 0, type: 'number' },
                    { index: 1, type: 'string' },
                    { index: 2, type: 'string' },
                    { index: 3, type: 'currency' },
                    { index: 4, type: 'percentage' }
                ]);
            }
        });
        
    } catch (error) {
        console.error('Error cargando watchlist:', error);
    }
}

// Utilidades
function formatDate(dateString) {
    const date = new Date(dateString);
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return date.toLocaleDateString('es-ES', options);
}

function truncate(str, maxLength) {
    if (str.length <= maxLength) return str;
    return str.substr(0, maxLength) + '...';
}
