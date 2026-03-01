// Sistema Weinstein - Dashboard JavaScript

const BASE_PATH = window.BASE_PATH || '';

let signalsDataTable = null;

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

        // Indicadores de actualización
        const statusRow = document.getElementById('update-status-row');
        statusRow.style.display = '';

        // Diario
        const dailyBadge = document.getElementById('daily-status-badge');
        const dailyIcon = document.getElementById('daily-status-icon');
        const dailyText = document.getElementById('daily-status-text');
        if (data.outdated_daily > 0) {
            dailyBadge.className = 'update-status-badge warning';
            dailyIcon.textContent = '⚠️';
            dailyText.textContent = `${data.outdated_daily} acciones sin datos diarios al ${formatDate(data.last_daily_date)}`;
        } else {
            dailyBadge.className = 'update-status-badge ok';
            dailyIcon.textContent = '✅';
            dailyText.textContent = data.last_daily_date
                ? `Datos diarios al día (${formatDate(data.last_daily_date)})`
                : 'Sin datos diarios';
        }

        // Semanal
        const weeklyBadge = document.getElementById('weekly-status-badge');
        const weeklyIcon = document.getElementById('weekly-status-icon');
        const weeklyText = document.getElementById('weekly-status-text');
        if (data.outdated_weekly > 0) {
            weeklyBadge.className = 'update-status-badge warning';
            weeklyIcon.textContent = '⚠️';
            weeklyText.textContent = `${data.outdated_weekly} acciones sin datos semanales al ${formatDate(data.last_weekly_date)}`;
        } else {
            weeklyBadge.className = 'update-status-badge ok';
            weeklyIcon.textContent = '✅';
            weeklyText.textContent = data.last_weekly_date
                ? `Datos semanales al día (${formatDate(data.last_weekly_date)})`
                : 'Sin datos semanales';
        }

    } catch (error) {
        console.error('Error cargando estadísticas:', error);
    }
}

// Calcular la fecha del viernes anterior (o hoy si es viernes)
function getPreviousFriday() {
    const today = new Date();
    const day = today.getDay(); // 0=Dom, 1=Lun, ..., 5=Vie, 6=Sáb
    const daysBack = day === 5 ? 0 : day === 6 ? 1 : day + 2;
    const d = new Date(today);
    d.setDate(today.getDate() - daysBack);
    // Usar fecha local (no UTC) para evitar desfase de zona horaria
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day2 = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day2}`;
}

// Cargar señales BUY del viernes anterior
async function loadRecentSignals() {
    try {
        const fridayDate = getPreviousFriday();
        const response = await fetch(`${BASE_PATH}/api/signals?date=${fridayDate}&signal_type=BUY`);
        const data = await response.json();

        // Destruir DataTable anterior si existe
        if (signalsDataTable) {
            signalsDataTable.destroy();
            signalsDataTable = null;
        }

        const tbody = document.getElementById('recent-signals');

        if (data.signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">No hay señales BUY para esta fecha</td></tr>';
            return;
        }

        // Construir HTML en bloque (como admin.js) para que DataTable lo lea correctamente
        tbody.innerHTML = data.signals.map(signal => `
            <tr>
                <td>${formatDate(signal.date)}</td>
                <td><a href="${BASE_PATH}/stock/${signal.ticker}" class="ticker-link">${signal.ticker}</a></td>
                <td>${truncate(signal.name, 30)}</td>
                <td><span class="badge badge-buy">BUY</span></td>
                <td><span class="badge badge-stage">Etapa ${signal.stage_from} → ${signal.stage_to}</span></td>
                <td>$${signal.price.toFixed(2)}</td>
                <td>${signal.ma30 ? '$' + signal.ma30.toFixed(2) : 'N/A'}</td>
            </tr>
        `).join('');

        // Inicializar DataTable
        signalsDataTable = new simpleDatatables.DataTable('#recent-signals-table', {
            perPage: 15,
            perPageSelect: [15, 25, 50],
            sanitize: false,
            labels: {
                placeholder: "Buscar...",
                noRows: "No hay señales",
                info: "Mostrando {start} a {end} de {rows} señales",
                perPage: "por página",
            },
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
