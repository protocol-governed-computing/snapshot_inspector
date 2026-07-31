/**
 * inspection_surface.js — the Protocol Inspection Surface.
 *
 * A THIN client of the governed boundary. It selects, fetches, formats, filters and navigates;
 * it derives no PGC semantic relationship. References and impact closures are *rendered*, never
 * computed here — the moment this file walked an artifact graph it would be a second inspection
 * engine, and the surface would stop honestly demonstrating the boundary it exists to show.
 *
 * Everything on screen arrives from one route:
 *
 *     POST /si   { "operation": "si.<...>", "params": { ... } }
 *
 * The route is bound by the adapter's External Protocol Binding; the `si.` namespace is an
 * admission constraint, and each identity resolves against its own governed TI/TE pair. The
 * client never names a workflow, a handler, or a file path in the snapshot.
 *
 * Even the MENU comes from the boundary (`si.catalog`), so what you can click is exactly what
 * can be answered. Nothing here enumerates the operations.
 */

const OPERATION_ROUTE = '/si';

/* ── boundary ─────────────────────────────────────────────────── */

async function callOperation(operation, params) {
    const response = await fetch(OPERATION_ROUTE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operation: operation, params: params || {} })
    });
    // The Canonical Transport Response is the contract, on success AND failure
    // (TRANSPORT_RESPONSE_V0): { request_id, outcome, result_class, result, evidence, errors }.
    return await response.json();
}

/* ── window manager ───────────────────────────────────────────── */

const WindowManager = {
    layer: null,
    zTop: 100,
    opened: 0,
    windows: new Set(),

    init() { this.layer = document.getElementById('window-layer'); },

    nextPosition() {
        // Cascade, wrapping before a new window can land off-screen.
        const step = 28;
        const index = this.opened++;
        const column = Math.floor(index / 8);
        return {
            left: Math.min(40 + column * 120 + (index % 8) * step, Math.max(20, window.innerWidth - 560)),
            top: 150 + (index % 8) * step
        };
    },

    open(title, subtitle, buildBody) {
        const win = document.createElement('section');
        win.className = 'win';
        const pos = this.nextPosition();
        win.style.left = pos.left + 'px';
        win.style.top = pos.top + 'px';

        const bar = document.createElement('div');
        bar.className = 'win-title';
        const label = document.createElement('span');
        label.className = 't-label';
        label.textContent = title;
        const id = document.createElement('span');
        id.className = 't-id';
        id.textContent = subtitle;
        const close = document.createElement('button');
        close.type = 'button';
        close.title = 'Close';
        close.innerHTML = '&times;';
        close.onclick = (e) => { e.stopPropagation(); this.close(win); };
        bar.append(label, id, close);

        const body = document.createElement('div');
        body.className = 'win-body';

        win.append(bar, body);
        this.layer.appendChild(win);
        this.windows.add(win);
        this.focus(win);

        // Focus follows the click, and never blocks anything: raising a window changes only
        // z-order. No window is ever disabled by another being open.
        win.addEventListener('mousedown', () => this.focus(win));
        this.makeDraggable(win, bar);

        buildBody(body, win);
        return win;
    },

    focus(win) {
        this.windows.forEach(w => w.classList.remove('focused'));
        win.classList.add('focused');
        win.style.zIndex = String(++this.zTop);
    },

    close(win) {
        this.windows.delete(win);
        win.remove();
    },

    closeAll() {
        Array.from(this.windows).forEach(w => this.close(w));
        this.opened = 0;
    },

    tile() {
        // Re-lay every open window on a grid, preserving stacking order.
        const list = Array.from(this.windows);
        const perRow = Math.max(1, Math.floor(window.innerWidth / 560));
        list.forEach((win, i) => {
            win.style.left = (20 + (i % perRow) * 545) + 'px';
            win.style.top = (150 + Math.floor(i / perRow) * 320) + 'px';
        });
        this.opened = list.length;
    },

    makeDraggable(win, handle) {
        let startX = 0, startY = 0, originLeft = 0, originTop = 0, dragging = false;

        const onMove = (e) => {
            if (!dragging) return;
            const left = originLeft + (e.clientX - startX);
            const top = originTop + (e.clientY - startY);
            win.style.left = Math.max(0, left) + 'px';
            win.style.top = Math.max(0, top) + 'px';
        };
        const onUp = () => {
            dragging = false;
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
        };
        handle.addEventListener('mousedown', (e) => {
            if (e.target.tagName === 'BUTTON') return;
            dragging = true;
            startX = e.clientX; startY = e.clientY;
            originLeft = parseInt(win.style.left, 10) || 0;
            originTop = parseInt(win.style.top, 10) || 0;
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
            e.preventDefault();
        });
    }
};

/* ── operation windows ────────────────────────────────────────── */

function openOperationWindow(op, presetParams) {
    WindowManager.open(op.label, op.operation, (body) => {
        const form = document.createElement('div');
        form.className = 'win-params';
        const inputs = {};

        op.params.forEach(param => {
            const isFlag = (op.flags || []).indexOf(param) !== -1;
            if (isFlag) {
                const wrap = document.createElement('label');
                wrap.className = 'p-flag';
                const box = document.createElement('input');
                box.type = 'checkbox';
                if (presetParams && presetParams[param]) box.checked = true;
                wrap.append(box, document.createTextNode(param));
                form.appendChild(wrap);
                inputs[param] = () => box.checked ? true : undefined;
            } else {
                const field = document.createElement('div');
                field.className = 'p-field';
                const label = document.createElement('label');
                label.textContent = param;
                if (op.required.indexOf(param) !== -1) {
                    const req = document.createElement('span');
                    req.className = 'req';
                    req.textContent = ' *';
                    label.appendChild(req);
                }
                const input = document.createElement('input');
                input.type = 'text';
                input.placeholder = param;
                if (presetParams && presetParams[param] !== undefined) input.value = presetParams[param];
                field.append(label, input);
                form.appendChild(field);
                inputs[param] = () => input.value.trim() || undefined;
            }
        });

        const run = document.createElement('button');
        run.className = 'win-run';
        run.textContent = 'Run';
        form.appendChild(run);

        const status = document.createElement('div');
        status.className = 'win-status';
        const output = document.createElement('div');

        body.append(form, status, output);

        const invoke = async () => {
            const params = {};
            Object.keys(inputs).forEach(key => {
                const value = inputs[key]();
                if (value !== undefined) params[key] = value;
            });
            run.disabled = true;
            status.innerHTML = '<span class="meta">calling the boundary&hellip;</span>';
            output.innerHTML = '';
            try {
                const envelope = await callOperation(op.operation, params);
                renderEnvelope(status, output, envelope, op);
            } catch (e) {
                status.innerHTML = '<span class="rc err">TRANSPORT ERROR</span>';
                output.innerHTML = '<div class="err-box">' + escapeHtml(e.message) + '</div>';
            } finally {
                run.disabled = false;
            }
        };

        run.onclick = invoke;
        form.addEventListener('keydown', (e) => { if (e.key === 'Enter') invoke(); });

        // An operation that needs nothing, or arrives with everything it needs, answers at once.
        const satisfied = op.required.every(p => presetParams && presetParams[p] !== undefined);
        if (op.required.length === 0 || satisfied) invoke();
    });
}

function renderEnvelope(status, output, envelope, op) {
    const rc = envelope.result_class || 'ERROR';
    const cls = rc === 'SUCCESS' ? 'ok' : (rc === 'NOT_FOUND' ? 'warn' : 'err');
    status.innerHTML = '<span class="rc ' + cls + '">' + escapeHtml(rc) + '</span>'
        + '<span class="meta">' + escapeHtml(op.kind) + ' &middot; request '
        + escapeHtml(String(envelope.request_id || '').slice(0, 8)) + '</span>';

    if (rc !== 'SUCCESS') {
        const errors = envelope.errors || [];
        output.innerHTML = errors.length
            ? errors.map(e => '<div class="err-box"><span class="code">' + escapeHtml(e.code || 'ERROR')
                + '</span> ' + escapeHtml(e.message || '') + '</div>').join('')
            : '<div class="err-box">no result</div>';
        return;
    }

    output.innerHTML = '';
    const result = envelope.result || {};

    // A rendered projection is a binary asset, fetched directly from the snapshot mount rather
    // than inlined in a governed response (Plan §3 rule 6). Fail-soft: a missing PNG hides.
    if (result.projection_path) {
        const img = document.createElement('img');
        img.className = 'bl-img';
        img.src = '/snapshot/' + result.projection_path;
        img.alt = 'behaviour-logic projection';
        img.onerror = () => img.remove();
        output.appendChild(img);
    }

    output.appendChild(renderValue(result));
}

/* ── rendering (format + navigate only; never derive) ─────────── */

const FQDN_PATTERN = /^[a-z0-9_.]+::[A-Z][A-Z0-9_]*$/;

function renderValue(value) {
    const box = document.createElement('div');
    box.className = 'tree';
    box.appendChild(renderNode(value, true));
    return box;
}

function renderNode(value, open) {
    if (Array.isArray(value)) return renderArray(value, open);
    if (value && typeof value === 'object') return renderObject(value, open);
    return renderScalar(value);
}

function renderScalar(value) {
    const span = document.createElement('span');
    if (value === null || value === undefined) {
        span.className = 'null'; span.textContent = 'null';
    } else if (typeof value === 'number') {
        span.className = 'n'; span.textContent = String(value);
    } else if (typeof value === 'boolean') {
        span.className = 'b'; span.textContent = String(value);
    } else {
        span.className = 's';
        span.textContent = String(value);
        if (FQDN_PATTERN.test(String(value))) makeNavigable(span, String(value));
    }
    return span;
}

/** Clicking an FQDN opens `si.artifact.show` for it. That is NAVIGATION — a new governed
 *  request for a named subject — not a relationship the client worked out for itself. */
function makeNavigable(span, fqdn) {
    span.classList.add('linkish');
    span.title = 'Show ' + fqdn;
    span.onclick = (e) => {
        e.stopPropagation();
        const op = Catalog.byIdentity['si.artifact.show'];
        if (op) openOperationWindow(op, { artifact: fqdn });
    };
}

function renderObject(obj, open) {
    const keys = Object.keys(obj);
    const wrap = document.createElement('div');
    keys.forEach(key => {
        const value = obj[key];
        if (value !== null && typeof value === 'object') {
            const size = Array.isArray(value) ? value.length : Object.keys(value).length;
            if (size === 0) {
                wrap.appendChild(rowOf(key, emptyMarker()));
                return;
            }
            const details = document.createElement('details');
            if (open) details.open = true;
            const summary = document.createElement('summary');
            summary.innerHTML = '<span class="k">' + escapeHtml(key) + '</span> '
                + '<span class="count">(' + size + ')</span>';
            details.append(summary, renderNode(value, false));
            wrap.appendChild(details);
        } else {
            wrap.appendChild(rowOf(key, renderScalar(value)));
        }
    });
    return wrap;
}

function renderArray(items, open) {
    // A list of flat objects sharing a shape reads as a table; anything else stays a tree.
    const flat = items.length > 0 && items.every(
        it => it && typeof it === 'object' && !Array.isArray(it)
            && Object.keys(it).every(k => it[k] === null || typeof it[k] !== 'object'));
    if (flat) return renderTable(items);

    const wrap = document.createElement('div');
    items.forEach((item, i) => {
        if (item !== null && typeof item === 'object') {
            const details = document.createElement('details');
            if (open && i === 0) details.open = true;
            const summary = document.createElement('summary');
            summary.innerHTML = '<span class="count">[' + i + ']</span>';
            details.append(summary, renderNode(item, false));
            wrap.appendChild(details);
        } else {
            const row = document.createElement('div');
            row.className = 'row';
            row.appendChild(renderScalar(item));
            wrap.appendChild(row);
        }
    });
    return wrap;
}

function renderTable(rows) {
    const columns = [];
    rows.forEach(row => Object.keys(row).forEach(k => { if (columns.indexOf(k) === -1) columns.push(k); }));
    const table = document.createElement('table');
    table.className = 'res-table';
    const head = document.createElement('tr');
    columns.forEach(c => {
        const th = document.createElement('th');
        th.textContent = c;
        head.appendChild(th);
    });
    table.appendChild(head);
    rows.forEach(row => {
        const tr = document.createElement('tr');
        columns.forEach(c => {
            const td = document.createElement('td');
            td.appendChild(renderScalar(row[c]));
            tr.appendChild(td);
        });
        table.appendChild(tr);
    });
    return table;
}

function rowOf(key, valueNode) {
    const row = document.createElement('div');
    row.className = 'row';
    const k = document.createElement('span');
    k.className = 'k';
    k.textContent = key + ': ';
    row.append(k, valueNode);
    return row;
}

function emptyMarker() {
    const span = document.createElement('span');
    span.className = 'null';
    span.textContent = '—';
    return span;
}

function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* ── catalog / launcher ───────────────────────────────────────── */

const Catalog = { byIdentity: {} };

function renderCatalogFailure(line, container, resultClass, message, guidance) {
    line.textContent = 'catalog unavailable';
    container.innerHTML =
        '<div class="catalog-group catalog-failure">'
        + '<span class="status-badge">' + escapeHtml(resultClass) + '</span>'
        + '<h3>Inspection catalog unavailable</h3>'
        + '<p class="failure-message">' + escapeHtml(message) + '</p>'
        + '<pre class="failure-guidance">' + escapeHtml(guidance) + '</pre>'
        + '</div>';
}

async function loadCatalog() {
    const line = document.getElementById('snapshot-line');
    const container = document.getElementById('catalog');

    let envelope;
    try {
        envelope = await callOperation('si.catalog', {});
    } catch (e) {
        renderCatalogFailure(line, container, 'TRANSPORT ERROR', e.message,
            'The boundary did not answer. Is the surface still running?');
        return;
    }
    if (envelope.result_class !== 'SUCCESS') {
        // The catalog is the one call everything else depends on, so its failure must be the
        // loudest thing on the page. Reporting it quietly leaves an empty launcher that reads as
        // a broken client, and sends the reader looking in the wrong place entirely.
        const error = envelope.errors && envelope.errors[0] ? envelope.errors[0] : {};
        renderCatalogFailure(
            line, container, envelope.result_class, error.message || 'no operations returned',
            envelope.result_class === 'OPERATION_NOT_FOUND'
                ? 'The snapshot THIS SERVER BOOTED WITH declares no inspection boundary.\n\n'
                  + 'The boundary is read once, at startup — so if you have already rebuilt, the\n'
                  + 'running process still holds the old one and only a restart will pick it up.\n'
                  + 'Check the server banner: it prints the snapshot_id and operations it booted\n'
                  + 'with.\n\n'
                  + '  protocol_compiler/compile_domain.sh <workspace>/snapshot_inspector\n'
                  + '  snapshot_assembler/assemble.sh\n'
                  + '  # then restart the surface — re-assembling alone will not help\n'
                  + '  snapshot_inspector/client/serve.sh'
                : 'The snapshot could not answer for the operation catalog.');
        return;
    }
    const operations = envelope.result.operations;
    operations.forEach(op => { Catalog.byIdentity[op.operation] = op; });

    const groups = {};
    const order = envelope.result.categories;
    operations.forEach(op => {
        (groups[op.category] = groups[op.category] || []).push(op);
    });

    order.forEach(category => {
        const ops = groups[category] || [];
        const group = document.createElement('div');
        group.className = 'catalog-group';
        const title = document.createElement('h3');
        title.textContent = category;
        const grid = document.createElement('div');
        grid.className = 'catalog-ops';

        ops.forEach(op => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'op-button';
            const chip = op.kind === 'SNAPSHOT_QUERY' ? 'query' : 'read';
            button.innerHTML =
                '<span class="kind-chip ' + chip + '">' + (chip === 'query' ? 'query' : 'read') + '</span>'
                + '<span class="op-label">' + escapeHtml(op.label) + '</span>'
                + '<span class="op-id">' + escapeHtml(op.operation) + '</span>'
                + '<span class="op-summary">' + escapeHtml(op.summary) + '</span>';
            button.onclick = () => openOperationWindow(op, null);
            grid.appendChild(button);
        });

        group.append(title, grid);
        container.appendChild(group);
    });

    // Identify the snapshot being inspected — through the boundary, like everything else.
    const summary = await callOperation('si.snapshot.summary', {});
    if (summary.result_class === 'SUCCESS') {
        const r = summary.result;
        line.innerHTML = 'snapshot <span class="sid">' + escapeHtml(String(r.snapshot_id).slice(0, 16))
            + '&hellip;</span> &middot; ' + r.artifact_count + ' artifacts &middot; '
            + r.domains.length + ' domains &middot; ' + operations.length + ' operations';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    WindowManager.init();
    document.getElementById('nav-tile').onclick = (e) => { e.preventDefault(); WindowManager.tile(); };
    document.getElementById('nav-close-all').onclick = (e) => { e.preventDefault(); WindowManager.closeAll(); };
    loadCatalog();
});
