// Sistema Weinstein - Watchlist JavaScript

const BASE_PATH = window.BASE_PATH || '';

// Cargar datos al iniciar
document.addEventListener('DOMContentLoaded', function() {
    loadWatchlist();
});

// Cargar watchlist
async function loadWatchlist() {
    try {
        const response = await fetch(`${BASE_PATH}/api/watchlist`);
        const data = await response.json();
        
        document.getElementById('total-stage2').textContent = data.total;
        
        const tbody = document.getElementById('watchlist-tbody');
        tbody.innerHTML = '';
        
        if (data.stocks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">No hay acciones en Etapa 2</td></tr>';
            return;
        }
        
        data.stocks.forEach((stock, index) => {
            const row = document.createElement('tr');
            
            const distanceMA30 = stock.ma30 
                ? (((stock.close - stock.ma30) / stock.ma30) * 100).toFixed(2)
                : 'N/A';
            
            const slopePct = stock.slope 
                ? (stock.slope * 100).toFixed(2)
                : 'N/A';
            
            const distanceClass = distanceMA30 !== 'N/A' && distanceMA30 > 0 ? 'positive' : '';
            const slopeClass = slopePct !== 'N/A' && slopePct > 0 ? 'positive' : '';
            
            row.innerHTML = `
                <td>${index + 1}</td>
                <td><a href="${BASE_PATH}/stock/${stock.ticker}" class="ticker-link">${stock.ticker}</a></td>
                <td>${truncate(stock.name, 40)}</td>
                <td>$${stock.close.toFixed(2)}</td>
                <td>$${stock.ma30 ? stock.ma30.toFixed(2) : 'N/A'}</td>
                <td class="${distanceClass}">${distanceMA30 !== 'N/A' ? '+' + distanceMA30 + '%' : 'N/A'}</td>
                <td class="${slopeClass}">${slopePct !== 'N/A' ? '+' + slopePct + '%' : 'N/A'}</td>
            `;
            
            tbody.appendChild(row);
        });
        
        // Inicializar ordenación
        requestAnimationFrame(() => {
            if (typeof initTableSort === 'function') {
                initTableSort('watchlist-table', [
                    { index: 0, type: 'number' },
                    { index: 1, type: 'string' },
                    { index: 2, type: 'string' },
                    { index: 3, type: 'currency' },
                    { index: 4, type: 'currency' },
                    { index: 5, type: 'percentage' },
                    { index: 6, type: 'percentage' }
                ]);
            }
        });
        
    } catch (error) {
        console.error('Error cargando watchlist:', error);
        document.getElementById('watchlist-table').innerHTML = 
            '<tr><td colspan="7" class="text-center">Error cargando datos</td></tr>';
    }
}

function truncate(str, maxLength) {
    if (str.length <= maxLength) return str;
    return str.substr(0, maxLength) + '...';
}
