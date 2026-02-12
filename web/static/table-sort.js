// Sistema Weinstein - Table Sort Utility
// Funcionalidad de ordenación para tablas

/**
 * Inicializar ordenación en una tabla
 * @param {string} tableId - ID de la tabla
 * @param {Array} columns - Array de objetos con configuración de columnas
 *   Ejemplo: [
 *     { index: 0, type: 'string' },
 *     { index: 1, type: 'number' },
 *     { index: 2, type: 'date' }
 *   ]
 */
function initTableSort(tableId, columns) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const thead = table.querySelector('thead');
    if (!thead) return;
    
    const headers = thead.querySelectorAll('th');
    
    columns.forEach(col => {
        const th = headers[col.index];
        if (!th) return;
        
        // Añadir clase sortable
        th.classList.add('sortable');
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        
        // Añadir indicador de ordenación
        const indicator = document.createElement('span');
        indicator.className = 'sort-indicator';
        indicator.innerHTML = ' ↕';
        th.appendChild(indicator);
        
        // Click handler
        th.addEventListener('click', function() {
            sortTable(table, col.index, col.type, th);
        });
    });
}

/**
 * Ordenar tabla por columna
 */
function sortTable(table, columnIndex, type, headerElement) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Determinar dirección actual
    const currentDirection = headerElement.dataset.sortDirection || 'none';
    let newDirection = 'asc';
    
    if (currentDirection === 'asc') {
        newDirection = 'desc';
    } else if (currentDirection === 'desc') {
        newDirection = 'asc';
    }
    
    // Resetear otros headers
    table.querySelectorAll('th').forEach(th => {
        th.dataset.sortDirection = 'none';
        const indicator = th.querySelector('.sort-indicator');
        if (indicator) {
            indicator.innerHTML = ' ↕';
            indicator.style.opacity = '0.3';
        }
    });
    
    // Actualizar header actual
    headerElement.dataset.sortDirection = newDirection;
    const indicator = headerElement.querySelector('.sort-indicator');
    if (indicator) {
        indicator.innerHTML = newDirection === 'asc' ? ' ↑' : ' ↓';
        indicator.style.opacity = '1';
    }
    
    // Ordenar filas
    rows.sort((a, b) => {
        let aValue = getCellValue(a, columnIndex);
        let bValue = getCellValue(b, columnIndex);
        
        // Convertir según tipo
        if (type === 'number' || type === 'currency' || type === 'percentage') {
            aValue = parseFloat(aValue.replace(/[^0-9.-]/g, '')) || 0;
            bValue = parseFloat(bValue.replace(/[^0-9.-]/g, '')) || 0;
        } else if (type === 'date') {
            aValue = new Date(aValue).getTime() || 0;
            bValue = new Date(bValue).getTime() || 0;
        } else {
            // string
            aValue = aValue.toLowerCase();
            bValue = bValue.toLowerCase();
        }
        
        let comparison = 0;
        if (aValue > bValue) comparison = 1;
        if (aValue < bValue) comparison = -1;
        
        return newDirection === 'asc' ? comparison : -comparison;
    });
    
    // Re-insertar filas ordenadas
    rows.forEach(row => tbody.appendChild(row));
}

/**
 * Obtener valor de celda
 */
function getCellValue(row, columnIndex) {
    const cells = row.querySelectorAll('td');
    const cell = cells[columnIndex];
    if (!cell) return '';
    
    // Intentar obtener el texto sin HTML
    return cell.textContent.trim();
}

/**
 * Añadir estilos CSS para ordenación
 */
function addSortStyles() {
    const styleId = 'table-sort-styles';
    
    // No añadir si ya existe
    if (document.getElementById(styleId)) return;
    
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
        .sortable {
            position: relative;
            padding-right: 1.5rem !important;
        }
        
        .sortable:hover {
            background-color: var(--gray-100, #f3f4f6);
        }
        
        .sort-indicator {
            position: absolute;
            right: 0.5rem;
            opacity: 0.3;
            font-size: 0.875rem;
            transition: opacity 0.2s;
        }
        
        .sortable:hover .sort-indicator {
            opacity: 0.6;
        }
        
        th[data-sort-direction="asc"] .sort-indicator,
        th[data-sort-direction="desc"] .sort-indicator {
            opacity: 1 !important;
            color: var(--primary-color, #2563eb);
        }
    `;
    
    document.head.appendChild(style);
}

// Añadir estilos al cargar
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addSortStyles);
} else {
    addSortStyles();
}
