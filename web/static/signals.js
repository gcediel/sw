// Sistema Weinstein - Signals JavaScript

const BASE_PATH = window.BASE_PATH || '';

let currentFilter = 'all';
let currentDays = 30;

// Cargar datos al iniciar
document.addEventListener('DOMContentLoaded', function() {
    setupFilters();
    loadSignals();
});

// Configurar filtros
function setupFilters() {
    document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn[data-filter]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            currentFilter = this.dataset.filter;
            loadSignals();
        });
    });
    
    document.querySelectorAll('.filter-btn[data-days]').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn[data-days]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            currentDays = parseInt(this.dataset.days);
            loadSignals();
        });
    });
}

// Cargar señales
async function loadSignals() {
    try {
        let url = `${BASE_PATH}/api/signals?days=${currentDays}&limit=100`;
        if (currentFilter !== 'all') {
            url += `&signal_type=${currentFilter}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        updateStats(data.signals);
        
        const tbody = document.getElementById('signals-tbody');
        tbody.innerHTML = '';
        
        if (data.signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">No hay señales en este período</td></tr>';
            return;
        }
        
        data.signals.forEach(signal => {
            const row = document.createElement('tr');
            
            const badgeClass = signal.type === 'BUY' ? 'badge-buy' : 'badge-sell';
            
            row.innerHTML = `
                <td>${formatDate(signal.date)}</td>
                <td><a href="${BASE_PATH}/stock/${signal.ticker}" class="ticker-link">${signal.ticker}</a></td>
                <td>${truncate(signal.name, 30)}</td>
                <td><span class="badge ${badgeClass}">${signal.type}</span></td>
                <td><span class="badge badge-stage">Etapa ${signal.stage_from} → ${signal.stage_to}</span></td>
                <td>$${signal.price.toFixed(2)}</td>
                <td>${signal.ma30 ? '$' + signal.ma30.toFixed(2) : 'N/A'}</td>
            `;
            
            tbody.appendChild(row);
        });
        
        // Inicializar ordenación
        requestAnimationFrame(() => {
            if (typeof initTableSort === 'function') {
                initTableSort('signals-table', [
                    { index: 0, type: 'date' },
                    { index: 1, type: 'string' },
                    { index: 2, type: 'string' },
                    { index: 3, type: 'string' },
                    { index: 4, type: 'string' },
                    { index: 5, type: 'currency' },
                    { index: 6, type: 'currency' }
                ]);
            }
        });
        
    } catch (error) {
        console.error('Error cargando señales:', error);
        document.getElementById('signals-table').innerHTML = 
            '<tr><td colspan="7" class="text-center">Error cargando datos</td></tr>';
    }
}

function updateStats(signals) {
    const buyCount = signals.filter(s => s.type === 'BUY').length;
    const sellCount = signals.filter(s => s.type === 'SELL').length;
    
    document.getElementById('total-signals').textContent = signals.length;
    document.getElementById('buy-signals').textContent = buyCount;
    document.getElementById('sell-signals').textContent = sellCount;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return date.toLocaleDateString('es-ES', options);
}

function truncate(str, maxLength) {
    if (str.length <= maxLength) return str;
    return str.substr(0, maxLength) + '...';
}
