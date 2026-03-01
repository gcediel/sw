// Sistema Weinstein - Watchlist JavaScript

const BASE_PATH = window.BASE_PATH || '';

let watchlistDT = null;

document.addEventListener('DOMContentLoaded', function() {
    loadWatchlist();
});

async function loadWatchlist() {
    try {
        const response = await fetch(`${BASE_PATH}/api/watchlist`);
        const data = await response.json();

        document.getElementById('total-stage2').textContent = data.total;

        if (watchlistDT) { watchlistDT.destroy(); watchlistDT = null; }

        const tbody = document.getElementById('watchlist-tbody');

        if (data.stocks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">No hay acciones en Etapa 2</td></tr>';
            return;
        }

        tbody.innerHTML = data.stocks.map((stock, index) => {
            const distanceMA30 = stock.ma30
                ? (((stock.close - stock.ma30) / stock.ma30) * 100).toFixed(2)
                : 'N/A';
            const slopePct = stock.slope
                ? (stock.slope * 100).toFixed(2)
                : 'N/A';
            const distanceClass = distanceMA30 !== 'N/A' && distanceMA30 > 0 ? 'positive' : '';
            const slopeClass = slopePct !== 'N/A' && slopePct > 0 ? 'positive' : '';
            return `
            <tr>
                <td>${index + 1}</td>
                <td><a href="${BASE_PATH}/stock/${stock.ticker}" class="ticker-link">${stock.ticker}</a></td>
                <td>${truncate(stock.name, 40)}</td>
                <td>$${stock.close.toFixed(2)}</td>
                <td>$${stock.ma30 ? stock.ma30.toFixed(2) : 'N/A'}</td>
                <td class="${distanceClass}">${distanceMA30 !== 'N/A' ? '+' + distanceMA30 + '%' : 'N/A'}</td>
                <td class="${slopeClass}">${slopePct !== 'N/A' ? '+' + slopePct + '%' : 'N/A'}</td>
            </tr>`;
        }).join('');

        watchlistDT = new simpleDatatables.DataTable('#watchlist-table', {
            perPage: 25,
            perPageSelect: [25, 50, 100],
            sanitize: false,
            labels: {
                placeholder: "Buscar...",
                noRows: "No hay acciones",
                info: "Mostrando {start} a {end} de {rows} acciones",
                perPage: "por página",
            },
        });

    } catch (error) {
        console.error('Error cargando watchlist:', error);
    }
}

function truncate(str, maxLength) {
    if (str.length <= maxLength) return str;
    return str.substr(0, maxLength) + '...';
}
