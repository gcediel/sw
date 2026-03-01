// Sistema Weinstein - Signals JavaScript

const BASE_PATH = window.BASE_PATH || '';

let currentFilter = 'all';
let currentDays = 30;
let signalsDT = null;

document.addEventListener('DOMContentLoaded', function() {
    setupFilters();
    loadSignals();
});

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

async function loadSignals() {
    try {
        let url = `${BASE_PATH}/api/signals?days=${currentDays}&limit=500`;
        if (currentFilter !== 'all') {
            url += `&signal_type=${currentFilter}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        updateStats(data.signals);

        if (signalsDT) { signalsDT.destroy(); signalsDT = null; }

        const tbody = document.getElementById('signals-tbody');

        if (data.signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">No hay señales en este período</td></tr>';
            return;
        }

        tbody.innerHTML = data.signals.map(signal => {
            const badgeClass = signal.type === 'BUY' ? 'badge-buy' : 'badge-sell';
            return `
            <tr>
                <td>${formatDate(signal.date)}</td>
                <td><a href="${BASE_PATH}/stock/${signal.ticker}" class="ticker-link">${signal.ticker}</a></td>
                <td>${truncate(signal.name, 30)}</td>
                <td><span class="badge ${badgeClass}">${signal.type}</span></td>
                <td><span class="badge badge-stage">Etapa ${signal.stage_from} → ${signal.stage_to}</span></td>
                <td>$${signal.price.toFixed(2)}</td>
                <td>${signal.ma30 ? '$' + signal.ma30.toFixed(2) : 'N/A'}</td>
            </tr>`;
        }).join('');

        signalsDT = new simpleDatatables.DataTable('#signals-table', {
            perPage: 25,
            perPageSelect: [25, 50, 100],
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
