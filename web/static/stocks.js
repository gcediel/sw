// Sistema Weinstein - Stocks JavaScript

const BASE_PATH = window.BASE_PATH || '';

let currentStage = 'all';
let currentSearch = '';
let currentOffset = 0;
const LIMIT = 50;

// Cargar datos al iniciar
document.addEventListener('DOMContentLoaded', function() {
    setupFilters();
    setupSearch();
    loadStocks();
    loadStats();
});

// Configurar filtros
function setupFilters() {
    document.querySelectorAll('.filter-btn[data-stage]').forEach(btn => {
        btn.addEventListener('click', function() {
            // Actualizar botones activos
            document.querySelectorAll('.filter-btn[data-stage]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            currentStage = this.dataset.stage;
            currentOffset = 0;
            loadStocks();
        });
    });
}

// Configurar búsqueda
function setupSearch() {
    const searchInput = document.getElementById('search-input');
    let timeout;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            currentSearch = this.value.trim();
            currentOffset = 0;
            loadStocks();
        }, 500); // Esperar 500ms después de que el usuario deje de escribir
    });
}

// Cargar estadísticas
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

// Cargar acciones
async function loadStocks() {
    try {
        // Construir URL con filtros
        let url = `${BASE_PATH}/api/stocks?limit=${LIMIT}&offset=${currentOffset}`;
        
        if (currentStage !== 'all') {
            url += `&stage=${currentStage}`;
        }
        
        if (currentSearch) {
            url += `&search=${encodeURIComponent(currentSearch)}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        // Actualizar contador de resultados
        document.getElementById('results-count').textContent = 
            `Mostrando ${data.stocks.length} de ${data.total} acciones`;
        
        const tbody = document.getElementById('stocks-table');
        tbody.innerHTML = '';
        
        if (data.stocks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">No se encontraron acciones</td></tr>';
            renderPagination(0, 0);
            return;
        }
        
        // Renderizar tabla
        data.stocks.forEach(stock => {
            const row = document.createElement('tr');
            
            const stageBadge = getStageBadge(stock.stage);
            const slopePct = stock.ma30_slope 
                ? (stock.ma30_slope * 100).toFixed(2)
                : 'N/A';
            const slopeClass = slopePct !== 'N/A' && stock.ma30_slope > 0 ? 'positive' : 
                              slopePct !== 'N/A' && stock.ma30_slope < 0 ? 'negative' : '';
            
            row.innerHTML = `
                <td><a href="${BASE_PATH}/stock/${stock.ticker}" class="ticker-link">${stock.ticker}</a></td>
                <td>${truncate(stock.name, 35)}</td>
                <td>${stock.exchange || 'N/A'}</td>
                <td>${stageBadge}</td>
                <td>$${stock.price.toFixed(2)}</td>
                <td>${stock.ma30 ? '$' + stock.ma30.toFixed(2) : 'N/A'}</td>
                <td class="${slopeClass}">${slopePct !== 'N/A' ? (slopePct > 0 ? '+' : '') + slopePct + '%' : 'N/A'}</td>
            `;
            
            tbody.appendChild(row);
        });
        
        // Renderizar paginación
        renderPagination(data.total, data.offset);
        
    } catch (error) {
        console.error('Error cargando acciones:', error);
        document.getElementById('stocks-table').innerHTML = 
            '<tr><td colspan="7" class="text-center">Error cargando datos</td></tr>';
    }
}

// Obtener badge de etapa
function getStageBadge(stage) {
    const colors = {
        1: '#6c757d',
        2: '#28a745',
        3: '#ffc107',
        4: '#dc3545'
    };
    
    const names = {
        1: 'Base',
        2: 'Alcista',
        3: 'Techo',
        4: 'Bajista'
    };
    
    return `<span class="badge" style="background-color: ${colors[stage] || '#6c757d'}20; color: ${colors[stage] || '#6c757d'}; border: 1px solid ${colors[stage] || '#6c757d'};">Etapa ${stage} - ${names[stage]}</span>`;
}

// Renderizar paginación
function renderPagination(total, offset) {
    const pagination = document.getElementById('pagination');
    
    if (total <= LIMIT) {
        pagination.innerHTML = '';
        return;
    }
    
    const totalPages = Math.ceil(total / LIMIT);
    const currentPage = Math.floor(offset / LIMIT) + 1;
    
    let html = '<div style="display: inline-flex; gap: 0.5rem;">';
    
    // Botón anterior
    if (currentPage > 1) {
        html += `<button class="btn btn-primary" onclick="changePage(${currentPage - 2})">← Anterior</button>`;
    }
    
    // Info de página
    html += `<span style="padding: 0.5rem 1rem; background: #f3f4f6; border-radius: 0.375rem;">Página ${currentPage} de ${totalPages}</span>`;
    
    // Botón siguiente
    if (currentPage < totalPages) {
        html += `<button class="btn btn-primary" onclick="changePage(${currentPage})">Siguiente →</button>`;
    }
    
    html += '</div>';
    
    pagination.innerHTML = html;
}

// Cambiar página
function changePage(page) {
    currentOffset = page * LIMIT;
    loadStocks();
    window.scrollTo(0, 0);
}

// Utilidades
function truncate(str, maxLength) {
    if (str.length <= maxLength) return str;
    return str.substr(0, maxLength) + '...';
}
