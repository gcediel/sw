// Sistema Weinstein - Stocks JavaScript

const BASE_PATH = window.BASE_PATH || '';

let currentStage = 'all';
let stocksDT = null;

document.addEventListener('DOMContentLoaded', function() {
    setupFilters();
    loadStocks();
    loadStats();
});

function setupFilters() {
    document.querySelectorAll('.filter-btn[data-stage]').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn[data-stage]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentStage = this.dataset.stage;
            loadStocks();
        });
    });
}

async function loadStats() {
    try {
        const response = await fetch(`${BASE_PATH}/api/dashboard/stats`);
        const data = await response.json();
        document.getElementById('total-stocks').textContent = data.total_stocks;
        document.getElementById('stage1-count').textContent = data.stages[1].count;
        document.getElementById('stage2-count').textContent = data.stages[2].count;
        document.getElementById('stage3-count').textContent = data.stages[3].count;
        document.getElementById('stage4-count').textContent = data.stages[4].count;
    } catch (error) {
        console.error('Error cargando estadísticas:', error);
    }
}

async function loadStocks() {
    try {
        let url = `${BASE_PATH}/api/stocks?limit=500`;
        if (currentStage !== 'all') {
            url += `&stage=${currentStage}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        if (stocksDT) { stocksDT.destroy(); stocksDT = null; }

        const tbody = document.getElementById('stocks-tbody');

        if (data.stocks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">No se encontraron acciones</td></tr>';
            return;
        }

        tbody.innerHTML = data.stocks.map(stock => {
            const stageBadge = getStageBadge(stock.stage);
            const slopePct = stock.ma30_slope
                ? (stock.ma30_slope * 100).toFixed(2)
                : 'N/A';
            const slopeClass = slopePct !== 'N/A' && stock.ma30_slope > 0 ? 'positive' :
                              slopePct !== 'N/A' && stock.ma30_slope < 0 ? 'negative' : '';
            return `
            <tr>
                <td><a href="${BASE_PATH}/stock/${stock.ticker}" class="ticker-link">${stock.ticker}</a></td>
                <td>${truncate(stock.name, 35)}</td>
                <td>${stock.exchange || 'N/A'}</td>
                <td>${stageBadge}</td>
                <td>$${stock.price.toFixed(2)}</td>
                <td>${stock.ma30 ? '$' + stock.ma30.toFixed(2) : 'N/A'}</td>
                <td class="${slopeClass}">${slopePct !== 'N/A' ? (slopePct > 0 ? '+' : '') + slopePct + '%' : 'N/A'}</td>
            </tr>`;
        }).join('');

        stocksDT = new simpleDatatables.DataTable('#stocks-table', {
            perPage: 25,
            perPageSelect: [25, 50, 100],
            sanitize: false,
            labels: {
                placeholder: "Buscar...",
                noRows: "No se encontraron acciones",
                info: "Mostrando {start} a {end} de {rows} acciones",
                perPage: "por página",
            },
        });

    } catch (error) {
        console.error('Error cargando acciones:', error);
    }
}

function getStageBadge(stage) {
    const colors = { 1: '#6c757d', 2: '#28a745', 3: '#ffc107', 4: '#dc3545' };
    const names  = { 1: 'Base', 2: 'Alcista', 3: 'Techo', 4: 'Bajista' };
    return `<span class="badge" style="background-color:${colors[stage]||'#6c757d'}20;color:${colors[stage]||'#6c757d'};border:1px solid ${colors[stage]||'#6c757d'};">Etapa ${stage} - ${names[stage]}</span>`;
}

function truncate(str, maxLength) {
    if (str.length <= maxLength) return str;
    return str.substr(0, maxLength) + '...';
}
