/* Admin - Gestión de acciones */

let dataTable = null;
let stocksData = [];

document.addEventListener('DOMContentLoaded', loadStocks);

async function loadStocks() {
    try {
        const resp = await fetch(`${BASE_PATH}/api/admin/stocks`);
        const data = await resp.json();
        stocksData = data.stocks || [];
        renderStocks(stocksData);
    } catch (e) {
        document.getElementById('stocks-tbody').innerHTML =
            '<tr><td colspan="5" class="loading">Error al cargar acciones</td></tr>';
    }
}

function renderStocks(stocks) {
    // Destruir DataTable anterior si existe
    if (dataTable) {
        dataTable.destroy();
        dataTable = null;
    }

    const tbody = document.getElementById('stocks-tbody');
    if (!stocks.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="loading">No hay acciones registradas</td></tr>';
        return;
    }

    tbody.innerHTML = stocks.map(s => `
        <tr>
            <td><strong>${esc(s.ticker)}</strong></td>
            <td>${esc(s.name)}</td>
            <td>${esc(s.exchange)}</td>
            <td class="text-center" data-sort="${s.active ? 1 : 0}">
                <button class="badge ${s.active ? 'badge-buy' : 'badge-sell'} btn-toggle"
                        onclick="toggleActive(${s.id}, ${s.active})"
                        title="${s.active ? 'Desactivar' : 'Activar'}">
                    ${s.active ? 'Activa' : 'Inactiva'}
                </button>
            </td>
            <td class="text-center" data-sortable="false">
                <button class="btn btn-sm btn-primary" onclick="editStock(${s.id}, '${esc(s.ticker)}', '${esc(s.name)}', '${esc(s.exchange)}')">Editar</button>
                <button class="btn btn-sm btn-danger" onclick="deleteStock(${s.id}, '${esc(s.ticker)}')">Eliminar</button>
            </td>
        </tr>
    `).join('');

    // Inicializar Simple-DataTables
    dataTable = new simpleDatatables.DataTable('#stocks-table', {
        perPage: 10,
        perPageSelect: [10, 25, 50, 100],
        labels: {
            placeholder: "Buscar...",
            noRows: "No hay acciones",
            info: "Mostrando {start} a {end} de {rows} acciones",
            perPage: "acciones por página",
        },
        columns: [
            { select: 4, sortable: false }
        ]
    });
}

function esc(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
              .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function showAddForm() {
    document.getElementById('form-title').textContent = 'Añadir acción';
    document.getElementById('edit-stock-id').value = '';
    document.getElementById('form-ticker').value = '';
    document.getElementById('form-ticker').disabled = false;
    document.getElementById('form-name').value = '';
    document.getElementById('form-exchange').value = '';
    document.getElementById('form-error').style.display = 'none';
    document.getElementById('stock-form').style.display = 'block';
    document.getElementById('form-ticker').focus();
}

function editStock(id, ticker, name, exchange) {
    document.getElementById('form-title').textContent = 'Editar acción: ' + ticker;
    document.getElementById('edit-stock-id').value = id;
    document.getElementById('form-ticker').value = ticker;
    document.getElementById('form-ticker').disabled = true;
    document.getElementById('form-name').value = name;
    document.getElementById('form-exchange').value = exchange;
    document.getElementById('form-error').style.display = 'none';
    document.getElementById('stock-form').style.display = 'block';
    document.getElementById('form-name').focus();
}

function hideForm() {
    document.getElementById('stock-form').style.display = 'none';
}

async function saveStock() {
    const stockId = document.getElementById('edit-stock-id').value;
    const ticker = document.getElementById('form-ticker').value.trim();
    const name = document.getElementById('form-name').value.trim();
    const exchange = document.getElementById('form-exchange').value.trim();
    const errorEl = document.getElementById('form-error');

    if (!stockId && !ticker) {
        errorEl.textContent = 'El ticker es obligatorio';
        errorEl.style.display = 'block';
        return;
    }

    try {
        let resp;
        if (stockId) {
            resp = await fetch(`${BASE_PATH}/api/admin/stocks/${stockId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, exchange})
            });
        } else {
            resp = await fetch(`${BASE_PATH}/api/admin/stocks`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticker, name, exchange})
            });
        }

        const data = await resp.json();
        if (!resp.ok) {
            errorEl.textContent = data.error || 'Error al guardar';
            errorEl.style.display = 'block';
            return;
        }

        hideForm();
        showAlert(stockId ? 'Acción actualizada' : 'Acción creada correctamente', 'success');
        loadStocks();
    } catch (e) {
        errorEl.textContent = 'Error de conexión';
        errorEl.style.display = 'block';
    }
}

async function toggleActive(id, currentActive) {
    try {
        const resp = await fetch(`${BASE_PATH}/api/admin/stocks/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({active: !currentActive})
        });
        if (resp.ok) loadStocks();
    } catch (e) {
        showAlert('Error al cambiar estado', 'error');
    }
}

async function deleteStock(id, ticker) {
    if (!confirm(`¿Eliminar ${ticker}? Se borrarán TODOS los datos históricos de esta acción. Esta acción no se puede deshacer.`)) {
        return;
    }
    try {
        const resp = await fetch(`${BASE_PATH}/api/admin/stocks/${id}`, {method: 'DELETE'});
        if (resp.ok) {
            showAlert(`${ticker} eliminada`, 'success');
            loadStocks();
        } else {
            const data = await resp.json();
            showAlert(data.error || 'Error al eliminar', 'error');
        }
    } catch (e) {
        showAlert('Error de conexión', 'error');
    }
}

function showAlert(msg, type) {
    const el = document.getElementById('stocks-alert');
    el.textContent = msg;
    el.className = 'alert alert-' + (type === 'error' ? 'error' : 'success');
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 3000);
}

async function clearPortfolioHistory() {
    if (!confirm('¿Borrar TODO el historial de operaciones cerradas? Esta acción no se puede deshacer.')) return;
    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio/history`, {method: 'DELETE'});
        const data = await resp.json();
        const el = document.getElementById('portfolio-admin-alert');
        if (!resp.ok) {
            el.textContent = data.error || 'Error al borrar historial';
            el.className = 'alert alert-error';
        } else {
            el.textContent = data.message || 'Historial borrado correctamente';
            el.className = 'alert alert-success';
        }
        el.style.display = 'block';
        setTimeout(() => { el.style.display = 'none'; }, 4000);
    } catch (e) {
        const el = document.getElementById('portfolio-admin-alert');
        el.textContent = 'Error de conexión';
        el.className = 'alert alert-error';
        el.style.display = 'block';
    }
}
