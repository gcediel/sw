/* Cartera (Portfolio) - Sistema Weinstein */

const BASE_PATH = window.BASE_PATH || '';

let openDT = null;
let historyDT = null;
let openPositionsMap = {};    // id -> position data (abiertas)
let historyPositionsMap = {}; // id -> position data (cerradas)

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('bf-date').value = new Date().toISOString().slice(0, 10);
    loadPortfolio();
    loadHistory();
    loadSummary();
});

// ============================================================
// TABS
// ============================================================

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    event.target.classList.add('active');
}

// ============================================================
// FORMULARIO NUEVA COMPRA
// ============================================================

function toggleBuyForm(ticker, price, stopSuggestion) {
    const card = document.getElementById('buy-form-card');
    const visible = card.style.display === 'block';
    if (visible) {
        card.style.display = 'none';
        return;
    }
    if (ticker) document.getElementById('bf-ticker').value = ticker;
    if (price) document.getElementById('bf-price').value = price;
    if (stopSuggestion) document.getElementById('bf-stop').value = stopSuggestion;
    document.getElementById('bf-date').value = new Date().toISOString().slice(0, 10);
    document.getElementById('buy-form-error').style.display = 'none';
    hideAllCards();
    card.style.display = 'block';
    document.getElementById('bf-ticker').focus();
}

async function saveBuy() {
    const ticker = document.getElementById('bf-ticker').value.trim().toUpperCase();
    const entry_date = document.getElementById('bf-date').value;
    const entry_price = parseFloat(document.getElementById('bf-price').value);
    const quantity = parseFloat(document.getElementById('bf-qty').value);
    const stop_loss = parseFloat(document.getElementById('bf-stop').value);
    const notes = document.getElementById('bf-notes').value.trim();
    const errEl = document.getElementById('buy-form-error');

    if (!ticker || !entry_date || isNaN(entry_price) || isNaN(quantity) || isNaN(stop_loss)) {
        errEl.textContent = 'Completa todos los campos obligatorios';
        errEl.style.display = 'block';
        return;
    }
    if (entry_price <= 0 || quantity <= 0 || stop_loss <= 0) {
        errEl.textContent = 'Precio, cantidad y stop loss deben ser positivos';
        errEl.style.display = 'block';
        return;
    }

    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ticker, entry_date, entry_price, quantity, stop_loss, notes})
        });
        const data = await resp.json();
        if (!resp.ok) {
            errEl.textContent = data.error || data.detail || 'Error al guardar';
            errEl.style.display = 'block';
            return;
        }
        document.getElementById('buy-form-card').style.display = 'none';
        clearBuyForm();
        showAlert('Posición abierta correctamente', 'success');
        loadPortfolio();
        loadSummary();
    } catch (e) {
        errEl.textContent = 'Error de conexión';
        errEl.style.display = 'block';
    }
}

function clearBuyForm() {
    ['bf-ticker','bf-price','bf-qty','bf-stop','bf-notes'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('bf-date').value = new Date().toISOString().slice(0, 10);
    document.getElementById('buy-form-error').style.display = 'none';
}

function hideAllCards() {
    ['buy-form-card', 'edit-open-card', 'close-open-card', 'edit-closed-card'].forEach(id => {
        document.getElementById(id).style.display = 'none';
    });
}

// ============================================================
// CARGAR POSICIONES ABIERTAS
// ============================================================

async function loadPortfolio() {
    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio`);
        const data = await resp.json();
        renderOpenPositions(data.positions || []);
    } catch (e) {
        document.getElementById('open-positions-tbody').innerHTML =
            '<tr><td colspan="11" class="text-center">Error al cargar posiciones</td></tr>';
    }
}

function renderOpenPositions(positions) {
    if (openDT) { openDT.destroy(); openDT = null; }
    openPositionsMap = {};

    const tbody = document.getElementById('open-positions-tbody');
    if (!positions.length) {
        tbody.innerHTML = '<tr><td colspan="11" class="text-center" style="color:#6b7280; padding:2rem;">No hay posiciones abiertas. Abre una nueva posición con el botón "Nueva posición".</td></tr>';
        return;
    }

    positions.forEach(p => { openPositionsMap[p.id] = p; });

    tbody.innerHTML = positions.map(p => {
        const rowClass = p.stop_triggered ? 'stop-triggered-row' : '';
        const pnlClass = p.pnl_eur >= 0 ? 'pnl-positive' : 'pnl-negative';
        const distClass = p.dist_stop_pct < 5 ? 'pnl-negative' : (p.dist_stop_pct < 10 ? '' : 'pnl-positive');
        const stopIcon = p.stop_triggered ? '<span class="stop-icon" title="Stop Loss disparado">&#9888;</span> ' : '';
        const notesHtml = p.notes
            ? `<span class="notes-cell" title="${esc(p.notes)}">${esc(p.notes)}</span>`
            : '-';
        return `
        <tr class="${rowClass}">
            <td><strong><a href="${BASE_PATH}/stock/${p.ticker}">${esc(p.ticker)}</a></strong></td>
            <td>${p.entry_date}</td>
            <td>${fmtPrice(p.entry_price)}</td>
            <td>${p.quantity}</td>
            <td>${fmtPrice(p.current_price)}</td>
            <td class="${pnlClass}">${fmtEur(p.pnl_eur)}</td>
            <td class="${pnlClass}">${fmtPct(p.pnl_pct)}</td>
            <td>${stopIcon}${fmtPrice(p.stop_loss)}</td>
            <td class="${distClass}">${fmtPct(p.dist_stop_pct)}</td>
            <td>${notesHtml}</td>
            <td style="white-space:nowrap;">
                <button class="btn btn-sm btn-primary" onclick="openEditForm(${p.id})">Editar</button>
                <button class="btn btn-sm" style="background:#f59e0b;color:#fff;" onclick="openCloseForm(${p.id}, ${p.current_price})">Cerrar</button>
                <button class="btn btn-sm btn-danger" onclick="deletePosition(${p.id}, '${esc(p.ticker)}')">Eliminar</button>
            </td>
        </tr>`;
    }).join('');

    openDT = new simpleDatatables.DataTable('#open-positions-table', {
        perPage: 25,
        perPageSelect: [25, 50],
        sanitize: false,
        labels: {
            placeholder: "Buscar...",
            noRows: "No hay posiciones abiertas",
            info: "Mostrando {start} a {end} de {rows} posiciones",
            perPage: "por página",
        },
        columns: [{ select: 10, sortable: false }],
    });
}

// ============================================================
// CARD: EDITAR POSICIÓN ABIERTA
// ============================================================

function openEditForm(id) {
    const p = openPositionsMap[id];
    if (!p) return;

    document.getElementById('eo-id').value = id;
    document.getElementById('eo-entry-date').value = p.entry_date;
    document.getElementById('eo-entry-price').value = p.entry_price;
    document.getElementById('eo-qty').value = p.quantity;
    document.getElementById('eo-stop').value = p.stop_loss;
    document.getElementById('eo-notes').value = p.notes || '';
    document.getElementById('eo-error').style.display = 'none';

    hideAllCards();
    const card = document.getElementById('edit-open-card');
    card.style.display = 'block';
    card.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function cancelEditOpen() {
    document.getElementById('edit-open-card').style.display = 'none';
}

async function saveEdit() {
    const id = document.getElementById('eo-id').value;
    const entry_date = document.getElementById('eo-entry-date').value;
    const entry_price = parseFloat(document.getElementById('eo-entry-price').value);
    const quantity = parseFloat(document.getElementById('eo-qty').value);
    const stop_loss = parseFloat(document.getElementById('eo-stop').value);
    const notes = document.getElementById('eo-notes').value.trim();
    const errEl = document.getElementById('eo-error');

    if (!entry_date || isNaN(entry_price) || isNaN(quantity) || isNaN(stop_loss)) {
        errEl.textContent = 'Completa todos los campos';
        errEl.style.display = 'block';
        return;
    }
    if (entry_price <= 0 || quantity <= 0 || stop_loss <= 0) {
        errEl.textContent = 'Precio, cantidad y stop loss deben ser positivos';
        errEl.style.display = 'block';
        return;
    }

    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({entry_date, entry_price, quantity, stop_loss, notes})
        });
        const data = await resp.json();
        if (!resp.ok) {
            errEl.textContent = data.error || data.detail || 'Error al guardar';
            errEl.style.display = 'block';
            return;
        }
        document.getElementById('edit-open-card').style.display = 'none';
        showAlert('Posición actualizada', 'success');
        loadPortfolio();
        loadSummary();
    } catch (e) {
        errEl.textContent = 'Error de conexión';
        errEl.style.display = 'block';
    }
}

// ============================================================
// CARD: CERRAR POSICIÓN ABIERTA
// ============================================================

function openCloseForm(id, suggestedPrice) {
    document.getElementById('co-id').value = id;
    document.getElementById('co-exit-date').value = new Date().toISOString().slice(0, 10);
    document.getElementById('co-exit-price').value = suggestedPrice;
    document.getElementById('co-error').style.display = 'none';

    hideAllCards();
    const card = document.getElementById('close-open-card');
    card.style.display = 'block';
    card.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function cancelCloseOpen() {
    document.getElementById('close-open-card').style.display = 'none';
}

async function closePosition() {
    const id = document.getElementById('co-id').value;
    const exit_date = document.getElementById('co-exit-date').value;
    const exit_price = parseFloat(document.getElementById('co-exit-price').value);
    const errEl = document.getElementById('co-error');

    if (!exit_date || isNaN(exit_price) || exit_price <= 0) {
        errEl.textContent = 'Completa fecha y precio de venta';
        errEl.style.display = 'block';
        return;
    }

    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio/${id}/close`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({exit_date, exit_price})
        });
        const data = await resp.json();
        if (!resp.ok) {
            errEl.textContent = data.error || data.detail || 'Error al cerrar posición';
            errEl.style.display = 'block';
            return;
        }
        document.getElementById('close-open-card').style.display = 'none';
        showAlert('Posición cerrada y movida al historial', 'success');
        loadPortfolio();
        loadHistory();
        loadSummary();
    } catch (e) {
        errEl.textContent = 'Error de conexión';
        errEl.style.display = 'block';
    }
}

async function deletePosition(id, ticker) {
    if (!confirm(`¿Eliminar la posición de ${ticker}? Se borrará definitivamente sin registrar cierre.`)) return;
    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio/${id}`, {method: 'DELETE'});
        const data = await resp.json();
        if (!resp.ok) {
            const msg = data.error || (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
            showAlert(msg || 'Error al eliminar', 'error');
            return;
        }
        showAlert(`Posición de ${ticker} eliminada`, 'success');
        loadPortfolio();
        loadHistory();
        loadSummary();
    } catch (e) {
        showAlert('Error de conexión', 'error');
    }
}

// ============================================================
// HISTORIAL
// ============================================================

async function loadHistory() {
    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio/history`);
        const data = await resp.json();
        renderHistory(data.positions || [], data.total_pnl || 0);
    } catch (e) {
        document.getElementById('history-tbody').innerHTML =
            '<tr><td colspan="10" class="text-center">Error al cargar historial</td></tr>';
    }
}

function renderHistory(positions, totalPnl) {
    if (historyDT) { historyDT.destroy(); historyDT = null; }
    historyPositionsMap = {};

    const tbody = document.getElementById('history-tbody');

    const totalDiv = document.getElementById('history-total');
    if (totalDiv) {
        const totalClass = totalPnl >= 0 ? 'pnl-positive' : 'pnl-negative';
        totalDiv.innerHTML = `P&L total acumulado cerradas: <span class="${totalClass}">${fmtEur(totalPnl)}</span>`;
    }

    if (!positions.length) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center" style="color:#6b7280; padding:2rem;">No hay posiciones cerradas en el historial.</td></tr>';
        return;
    }

    positions.forEach(p => { historyPositionsMap[p.id] = p; });

    tbody.innerHTML = positions.map(p => {
        const pnlClass = p.pnl_eur >= 0 ? 'pnl-positive' : 'pnl-negative';
        const notesHtml = p.notes
            ? `<span class="notes-cell" title="${esc(p.notes)}">${esc(p.notes)}</span>`
            : '-';
        return `
        <tr>
            <td><strong><a href="${BASE_PATH}/stock/${p.ticker}">${esc(p.ticker)}</a></strong></td>
            <td>${p.entry_date}</td>
            <td>${p.exit_date || '-'}</td>
            <td>${fmtPrice(p.entry_price)}</td>
            <td>${fmtPrice(p.exit_price)}</td>
            <td>${p.quantity}</td>
            <td class="${pnlClass}">${fmtEur(p.pnl_eur)}</td>
            <td class="${pnlClass}">${fmtPct(p.pnl_pct)}</td>
            <td>${notesHtml}</td>
            <td style="white-space:nowrap;">
                <button class="btn btn-sm btn-primary" onclick="openEditClosedCard(${p.id})">Editar</button>
                <button class="btn btn-sm btn-danger" onclick="deletePosition(${p.id}, '${esc(p.ticker)}')">Eliminar</button>
            </td>
        </tr>`;
    }).join('');

    historyDT = new simpleDatatables.DataTable('#history-table', {
        perPage: 25,
        perPageSelect: [25, 50],
        sanitize: false,
        labels: {
            placeholder: "Buscar...",
            noRows: "No hay posiciones cerradas",
            info: "Mostrando {start} a {end} de {rows} posiciones",
            perPage: "por página",
        },
        columns: [{ select: 9, sortable: false }],
    });
}

// ============================================================
// CARD: EDITAR POSICIÓN CERRADA
// ============================================================

function openEditClosedCard(id) {
    const p = historyPositionsMap[id];
    if (!p) return;

    document.getElementById('ec-id').value = id;
    document.getElementById('ec-entry-date').value = p.entry_date;
    document.getElementById('ec-exit-date').value = p.exit_date || '';
    document.getElementById('ec-entry-price').value = p.entry_price;
    document.getElementById('ec-exit-price').value = p.exit_price;
    document.getElementById('ec-qty').value = p.quantity;
    document.getElementById('ec-notes').value = p.notes || '';
    document.getElementById('ec-error').style.display = 'none';

    hideAllCards();
    const card = document.getElementById('edit-closed-card');
    card.style.display = 'block';
    card.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function cancelEditClosed() {
    document.getElementById('edit-closed-card').style.display = 'none';
}

async function saveEditClosed() {
    const id = document.getElementById('ec-id').value;
    const entry_date = document.getElementById('ec-entry-date').value;
    const exit_date = document.getElementById('ec-exit-date').value;
    const entry_price = parseFloat(document.getElementById('ec-entry-price').value);
    const exit_price = parseFloat(document.getElementById('ec-exit-price').value);
    const quantity = parseFloat(document.getElementById('ec-qty').value);
    const notes = document.getElementById('ec-notes').value.trim();
    const errEl = document.getElementById('ec-error');

    if (!entry_date || !exit_date || isNaN(entry_price) || isNaN(exit_price) || isNaN(quantity)) {
        errEl.textContent = 'Completa todos los campos obligatorios';
        errEl.style.display = 'block';
        return;
    }
    if (entry_price <= 0 || exit_price <= 0 || quantity <= 0) {
        errEl.textContent = 'Precios y cantidad deben ser positivos';
        errEl.style.display = 'block';
        return;
    }

    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({entry_date, exit_date, entry_price, exit_price, quantity, notes})
        });
        const data = await resp.json();
        if (!resp.ok) {
            errEl.textContent = data.error || data.detail || 'Error al guardar';
            errEl.style.display = 'block';
            return;
        }
        document.getElementById('edit-closed-card').style.display = 'none';
        showAlert('Posición cerrada actualizada', 'success');
        loadHistory();
        loadSummary();
    } catch (e) {
        errEl.textContent = 'Error de conexión';
        errEl.style.display = 'block';
    }
}

async function clearHistory() {
    if (!confirm('¿Borrar todo el historial de posiciones cerradas? Esta acción no se puede deshacer.')) return;
    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio/history`, {method: 'DELETE'});
        const data = await resp.json();
        if (!resp.ok) {
            showAlert(data.error || 'Error al borrar historial', 'error');
            return;
        }
        showAlert(data.message || 'Historial borrado', 'success');
        loadHistory();
    } catch (e) {
        showAlert('Error de conexión', 'error');
    }
}

// ============================================================
// SUMMARY / STATS
// ============================================================

async function loadSummary() {
    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio/summary`);
        const data = await resp.json();
        document.getElementById('stat-open').textContent = data.open_count;
        document.getElementById('stat-invested').textContent = fmtEur(data.total_invested);

        const pnlEl = document.getElementById('stat-pnl');
        pnlEl.textContent = fmtEur(data.total_pnl_eur);
        pnlEl.className = 'stat-value ' + (data.total_pnl_eur >= 0 ? 'pnl-positive' : 'pnl-negative');

        const avgEl = document.getElementById('stat-avg');
        avgEl.textContent = fmtPct(data.avg_pnl_pct);
        avgEl.className = 'stat-value ' + (data.avg_pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative');

        const closedEl = document.getElementById('stat-closed-pnl');
        closedEl.textContent = fmtEur(data.closed_pnl_eur);
        closedEl.className = 'stat-value ' + (data.closed_pnl_eur >= 0 ? 'pnl-positive' : 'pnl-negative');

        const globalEl = document.getElementById('stat-global-pnl');
        globalEl.textContent = fmtEur(data.global_pnl_eur);
        globalEl.className = 'stat-value ' + (data.global_pnl_eur >= 0 ? 'pnl-positive' : 'pnl-negative');
    } catch (e) {
        // silencioso
    }
}

// ============================================================
// UTILIDADES
// ============================================================

function fmtPrice(v) {
    if (v === null || v === undefined) return '-';
    return parseFloat(v).toLocaleString('es-ES', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €';
}

function fmtEur(v) {
    if (v === null || v === undefined) return '-';
    const val = parseFloat(v);
    const sign = val >= 0 ? '+' : '';
    return sign + val.toLocaleString('es-ES', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €';
}

function fmtPct(v) {
    if (v === null || v === undefined) return '-';
    const val = parseFloat(v);
    const sign = val >= 0 ? '+' : '';
    return sign + val.toFixed(2) + '%';
}

function esc(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
              .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function showAlert(msg, type) {
    const el = document.getElementById('portfolio-alert');
    el.textContent = msg;
    el.className = 'alert alert-' + (type === 'error' ? 'error' : 'success');
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 4000);
}
