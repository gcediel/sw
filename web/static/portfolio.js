/* Cartera (Portfolio) - Sistema Weinstein */

const BASE_PATH = window.BASE_PATH || '';

// Estado de formularios inline por posición
let activeInlineForm = null;  // { positionId, type }

document.addEventListener('DOMContentLoaded', () => {
    // Fecha de hoy como default del formulario de compra
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
    // Pre-rellenar si se pasaron datos
    if (ticker) document.getElementById('bf-ticker').value = ticker;
    if (price) document.getElementById('bf-price').value = price;
    if (stopSuggestion) document.getElementById('bf-stop').value = stopSuggestion;
    document.getElementById('bf-date').value = new Date().toISOString().slice(0, 10);
    document.getElementById('buy-form-error').style.display = 'none';
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
            errEl.textContent = data.error || 'Error al guardar';
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
            '<tr><td colspan="10" class="text-center">Error al cargar posiciones</td></tr>';
    }
}

function renderOpenPositions(positions) {
    const tbody = document.getElementById('open-positions-tbody');
    if (!positions.length) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center" style="color:#6b7280; padding:2rem;">No hay posiciones abiertas. Abre una nueva posición con el botón "Nueva posición".</td></tr>';
        return;
    }

    tbody.innerHTML = positions.map(p => {
        const rowClass = p.stop_triggered ? 'stop-triggered-row' : '';
        const pnlClass = p.pnl_eur >= 0 ? 'pnl-positive' : 'pnl-negative';
        const distClass = p.dist_stop_pct < 5 ? 'pnl-negative' : (p.dist_stop_pct < 10 ? '' : 'pnl-positive');
        const stopIcon = p.stop_triggered ? '🚨 ' : '';

        return `
        <tr class="${rowClass}" id="row-${p.id}">
            <td><strong><a href="${BASE_PATH}/stock/${p.ticker}">${esc(p.ticker)}</a></strong></td>
            <td>${p.entry_date}</td>
            <td>${fmtPrice(p.entry_price)}</td>
            <td>${p.quantity}</td>
            <td>${fmtPrice(p.current_price)}</td>
            <td class="${pnlClass}">${fmtEur(p.pnl_eur)}</td>
            <td class="${pnlClass}">${fmtPct(p.pnl_pct)}</td>
            <td>${stopIcon}${fmtPrice(p.stop_loss)}</td>
            <td class="${distClass}">${fmtPct(p.dist_stop_pct)}</td>
            <td style="white-space:nowrap;">
                <button class="btn btn-sm btn-primary" onclick="openEditStopForm(${p.id}, ${p.stop_loss}, '${esc(p.notes)}')">Editar stop</button>
                <button class="btn btn-sm" style="background:#f59e0b;color:#fff;" onclick="openCloseForm(${p.id}, ${p.current_price})">Cerrar</button>
            </td>
        </tr>
        <tr id="inline-${p.id}" style="display:none;">
            <td colspan="10" style="padding:0;">
                <div id="inline-content-${p.id}"></div>
            </td>
        </tr>
        `;
    }).join('');
}

// ============================================================
// FORMULARIO INLINE: EDITAR STOP
// ============================================================

function openEditStopForm(id, currentStop, currentNotes) {
    closeActiveInline();
    activeInlineForm = {id, type: 'stop'};

    const content = document.getElementById(`inline-content-${id}`);
    content.innerHTML = `
        <div class="inline-form">
            <div class="form-row">
                <div class="form-group">
                    <label>Nuevo Stop Loss</label>
                    <input type="number" id="edit-stop-${id}" step="0.01" min="0.01" value="${currentStop}">
                </div>
                <div class="form-group">
                    <label>Notas</label>
                    <input type="text" id="edit-notes-${id}" value="${esc(currentNotes)}" placeholder="Observaciones..." style="width:240px;">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <div style="display:flex; gap:0.5rem;">
                        <button class="btn btn-sm btn-primary" onclick="saveStop(${id})">Guardar</button>
                        <button class="btn btn-sm btn-cancel" onclick="closeActiveInline()">Cancelar</button>
                    </div>
                </div>
            </div>
            <div id="edit-stop-error-${id}" class="alert alert-error" style="display:none; margin-top:0.5rem;"></div>
        </div>
    `;
    document.getElementById(`inline-${id}`).style.display = '';
}

async function saveStop(id) {
    const stop_loss = parseFloat(document.getElementById(`edit-stop-${id}`).value);
    const notes = document.getElementById(`edit-notes-${id}`).value.trim();
    const errEl = document.getElementById(`edit-stop-error-${id}`);

    if (isNaN(stop_loss) || stop_loss <= 0) {
        errEl.textContent = 'El stop loss debe ser un número positivo';
        errEl.style.display = 'block';
        return;
    }

    try {
        const resp = await fetch(`${BASE_PATH}/api/portfolio/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({stop_loss, notes})
        });
        const data = await resp.json();
        if (!resp.ok) {
            errEl.textContent = data.error || 'Error al guardar';
            errEl.style.display = 'block';
            return;
        }
        closeActiveInline();
        showAlert('Stop loss actualizado', 'success');
        loadPortfolio();
        loadSummary();
    } catch (e) {
        errEl.textContent = 'Error de conexión';
        errEl.style.display = 'block';
    }
}

// ============================================================
// FORMULARIO INLINE: CERRAR POSICIÓN
// ============================================================

function openCloseForm(id, suggestedPrice) {
    closeActiveInline();
    activeInlineForm = {id, type: 'close'};

    const content = document.getElementById(`inline-content-${id}`);
    content.innerHTML = `
        <div class="inline-form" style="background:#fff5f5; border-color:#fca5a5;">
            <div class="form-row">
                <div class="form-group">
                    <label>Fecha de venta</label>
                    <input type="date" id="close-date-${id}" value="${new Date().toISOString().slice(0,10)}">
                </div>
                <div class="form-group">
                    <label>Precio de venta</label>
                    <input type="number" id="close-price-${id}" step="0.01" min="0.01" value="${suggestedPrice}">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <div style="display:flex; gap:0.5rem;">
                        <button class="btn btn-sm btn-danger" onclick="closePosition(${id})">Confirmar cierre</button>
                        <button class="btn btn-sm btn-cancel" onclick="closeActiveInline()">Cancelar</button>
                    </div>
                </div>
            </div>
            <div id="close-error-${id}" class="alert alert-error" style="display:none; margin-top:0.5rem;"></div>
        </div>
    `;
    document.getElementById(`inline-${id}`).style.display = '';
}

async function closePosition(id) {
    const exit_date = document.getElementById(`close-date-${id}`).value;
    const exit_price = parseFloat(document.getElementById(`close-price-${id}`).value);
    const errEl = document.getElementById(`close-error-${id}`);

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
            errEl.textContent = data.error || 'Error al cerrar posición';
            errEl.style.display = 'block';
            return;
        }
        closeActiveInline();
        showAlert('Posición cerrada y movida al historial', 'success');
        loadPortfolio();
        loadHistory();
        loadSummary();
    } catch (e) {
        errEl.textContent = 'Error de conexión';
        errEl.style.display = 'block';
    }
}

function closeActiveInline() {
    if (!activeInlineForm) return;
    const row = document.getElementById(`inline-${activeInlineForm.id}`);
    if (row) {
        row.style.display = 'none';
        document.getElementById(`inline-content-${activeInlineForm.id}`).innerHTML = '';
    }
    activeInlineForm = null;
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
            '<tr><td colspan="8" class="text-center">Error al cargar historial</td></tr>';
    }
}

function renderHistory(positions, totalPnl) {
    const tbody = document.getElementById('history-tbody');
    if (!positions.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="color:#6b7280; padding:2rem;">No hay posiciones cerradas en el historial.</td></tr>';
        return;
    }

    let rows = positions.map(p => {
        const pnlClass = p.pnl_eur >= 0 ? 'pnl-positive' : 'pnl-negative';
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
        </tr>
        `;
    }).join('');

    // Fila resumen
    const totalClass = totalPnl >= 0 ? 'pnl-positive' : 'pnl-negative';
    rows += `
        <tr class="total-row">
            <td colspan="6" style="text-align:right;">P&L total acumulado:</td>
            <td class="${totalClass}">${fmtEur(totalPnl)}</td>
            <td></td>
        </tr>
    `;
    tbody.innerHTML = rows;
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
