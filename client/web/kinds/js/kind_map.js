/**
 * Kind map — every artifact kind in the sealed snapshot, and how kinds refer to kinds.
 *
 * The page is the answer to one `si.` operation, sent as
 *
 *     POST /si   { "operation": "si.kind.map", "params": {} }
 *
 * or, in a page written by `scripts/export_kind_map.py`, that same answer embedded as
 * `window.KIND_MAP_RESULT`. Either way the page renders the answer and derives nothing: kinds,
 * counts, field shares and edges all come from the operation. Placement on the drawing is the one
 * thing this file decides, and a kind it has no place for still appears, in the bottom row.
 */
(function () {
    const OPERATION_ROUTE = '/si';
    const NS = 'http://www.w3.org/2000/svg';
    const W = 150, H = 52;

    // Where each kind sits: boundary on the left, execution through the middle, governance on top,
    // definitions at the bottom.
    const PLACE = {
        CONSTITUTION: [320, 24], INVARIANT: [570, 24], SURFACE: [820, 24],
        TEST_DATA: [820, 168],
        TI: [20, 250], TE: [20, 384],
        IN: [215, 168], WF: [215, 318], AC: [215, 470],
        RB: [420, 168], CC: [420, 318], EV: [420, 470],
        CT: [620, 250], CS: [620, 400],
        STRUCTURE: [620, 560], VOCAB: [820, 560],
    };
    const NAME = {
        WF: 'Workflow', CC: 'Capability contract', CT: 'Capability transform', CS: 'Capability side effect',
        IN: 'Intent', TI: 'Transport ingress', TE: 'Transport egress', RB: 'Runtime binding', EV: 'Event',
        AC: 'Actor', STRUCTURE: 'Structure', VOCAB: 'Vocabulary', CONSTITUTION: 'Constitution',
        INVARIANT: 'Invariant', TEST_DATA: 'Test data', SURFACE: 'Surface contract',
    };
    // Every kind carries these; the detail lists what a kind declares beyond them.
    const ENVELOPE = ['fqdn', 'artifact_kind', 'version', 'governed_by', 'authority', 'concern', 'core'];
    // Constitutions are referred to by nearly every kind; those arrows are drawn on request.
    const GOVERNANCE_TARGET = 'CONSTITUTION';
    const GOVERNANCE_KEEP = ['INVARIANT', 'CONSTITUTION'];
    // One colour per semantic category, in the order the ontology lists them; the categories
    // themselves are the answer's, so a kind without one is drawn uncoloured.
    const CATEGORY_COLOURS = ['#2d6fa3', '#a3443f', '#5b6b7a', '#2f7d5b', '#8a5a9e', '#b07a16'];

    const svg = document.getElementById('kinds-diagram');
    const detail = document.getElementById('kinds-detail');
    let answer = null, selected = null;
    const boxes = {};
    let drawn = [];

    function escapeHtml(str) {
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    async function ask(operation, params) {
        const response = await fetch(OPERATION_ROUTE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ operation: operation, params: params || {} }),
        });
        const envelope = await response.json();
        if (envelope.outcome !== 'SUCCESS') {
            const why = (envelope.errors || []).map((e) => e.message).join('; ');
            throw new Error(operation + ': ' + (envelope.result_class || 'FAILURE') + (why ? ' — ' + why : ''));
        }
        return envelope.result;
    }

    function el(tag, attrs, parent) {
        const node = document.createElementNS(NS, tag);
        Object.keys(attrs || {}).forEach((k) => node.setAttribute(k, attrs[k]));
        if (parent) parent.appendChild(node);
        return node;
    }

    function nameOf(kind) { return NAME[kind] || kind; }

    function colourOf(category) {
        const i = (answer.categories || []).indexOf(category);
        return i < 0 ? null : CATEGORY_COLOURS[i % CATEGORY_COLOURS.length];
    }

    function label(symbol) { return symbol ? symbol.replace(/_/g, ' ') : '—'; }

    function place(kinds) {
        const at = {};
        let spare = 0;
        kinds.forEach((k) => {
            at[k.kind] = PLACE[k.kind] || [20 + (spare++ % 5) * 200, 640];
        });
        const rows = Math.ceil(spare / 5);
        svg.setAttribute('viewBox', '0 0 1000 ' + (640 + rows * 80));
        return at;
    }

    function centre(at, kind) { return [at[kind][0] + W / 2, at[kind][1] + H / 2]; }

    function rim(at, kind, tx, ty) {
        const c = centre(at, kind), dx = tx - c[0], dy = ty - c[1];
        if (!dx && !dy) return c;
        const s = Math.min((W / 2) / Math.abs(dx || 1e-9), (H / 2) / Math.abs(dy || 1e-9));
        return [c[0] + dx * s, c[1] + dy * s];
    }

    function weight(n) { return Math.max(1, Math.min(4.5, 0.9 + Math.log10(n + 1) * 1.4)); }

    function isGovernance(e) { return e.to === GOVERNANCE_TARGET && GOVERNANCE_KEEP.indexOf(e.from) < 0; }

    function draw() {
        svg.innerHTML = '';
        const defs = el('defs', {}, svg);
        const marker = el('marker', { id: 'kind-arrow', viewBox: '0 0 10 10', refX: 9, refY: 5,
            markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' }, defs);
        el('path', { d: 'M0,0 L10,5 L0,10 z', class: 'arrow' }, marker);
        const at = place(answer.kinds);
        const edgeLayer = el('g', {}, svg), boxLayer = el('g', {}, svg);
        const showGovernance = document.getElementById('show-governance').checked;
        const showCounts = document.getElementById('show-counts').checked;
        const linked = {};
        answer.edges.forEach((e) => { linked[e.from + '>' + e.to] = true; });

        drawn = [];
        answer.edges.forEach((e) => {
            if (!at[e.from] || !at[e.to]) return;
            const governance = isGovernance(e);
            if (governance && !showGovernance) return;
            const g = el('g', { class: 'edge' + (governance ? ' governance' : '') }, edgeLayer);
            let lx, ly;
            if (e.from === e.to) {
                const x = at[e.from][0], y = at[e.from][1];
                el('path', { d: 'M' + (x + W - 30) + ',' + y + ' c 10,-26 44,-22 30,10',
                    'stroke-width': weight(e.pairs), 'marker-end': 'url(#kind-arrow)' }, g);
                lx = x + W + 6; ly = y - 10;
            } else {
                const a = centre(at, e.from), b = centre(at, e.to);
                const off = linked[e.to + '>' + e.from] ? 16 : 0;
                const nx = -(b[1] - a[1]), ny = b[0] - a[0], len = Math.hypot(nx, ny) || 1;
                const ox = nx / len * off, oy = ny / len * off;
                const s = rim(at, e.from, b[0] + ox, b[1] + oy), t = rim(at, e.to, a[0] + ox, a[1] + oy);
                lx = (s[0] + t[0]) / 2 + ox; ly = (s[1] + t[1]) / 2 + oy;
                el('path', { d: 'M' + (s[0] + ox) + ',' + (s[1] + oy) + ' Q' + lx + ',' + ly + ' ' + (t[0] + ox) + ',' + (t[1] + oy),
                    'stroke-width': weight(e.pairs), 'marker-end': 'url(#kind-arrow)' }, g);
            }
            const title = el('title', {}, g);
            title.textContent = nameOf(e.from) + ' → ' + nameOf(e.to) + ': ' + e.pairs + ' pairs from '
                + e.sources + ' artifacts\n' + Object.keys(e.edge_kinds).map((k) => k + ' ' + e.edge_kinds[k]).join('\n');
            if (showCounts) {
                const label = el('text', { x: lx, y: ly, 'text-anchor': 'middle', 'dominant-baseline': 'middle' }, g);
                label.textContent = e.pairs;
            }
            drawn.push({ edge: e, g: g });
        });

        answer.kinds.forEach((k) => {
            const x = at[k.kind][0], y = at[k.kind][1];
            const g = el('g', { class: 'box', tabindex: 0, role: 'button',
                'aria-label': nameOf(k.kind) + ', ' + k.count + ' artifacts' }, boxLayer);
            el('rect', { class: 'frame', x: x, y: y, width: W, height: H, rx: 4 }, g);
            const colour = colourOf(k.category);
            if (colour) el('rect', { x: x, y: y, width: 5, height: H, fill: colour }, g);
            el('text', { x: x + 10, y: y + 20, class: 'kind' }, g).textContent = k.kind;
            el('text', { x: x + W - 10, y: y + 20, class: 'count', 'text-anchor': 'end' }, g).textContent = k.count;
            el('text', { x: x + 10, y: y + 39, class: 'name' }, g).textContent = nameOf(k.kind);
            if (!k.schema) {
                el('text', { x: x + W - 10, y: y + 39, class: 'pending', 'text-anchor': 'end' }, g).textContent = 'no schema';
            }
            g.addEventListener('click', () => select(k.kind));
            g.addEventListener('keydown', (ev) => {
                if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); select(k.kind); }
            });
            boxes[k.kind] = g;
        });
        highlight();
    }

    function highlight() {
        svg.classList.toggle('focus', !!selected);
        Object.keys(boxes).forEach((k) => {
            boxes[k].classList.toggle('selected', k === selected);
            boxes[k].classList.remove('hot');
        });
        if (!selected) return;
        boxes[selected].classList.add('hot');
        drawn.forEach((d) => {
            const hot = d.edge.from === selected || d.edge.to === selected;
            d.g.classList.toggle('hot', hot);
            if (hot) {
                if (boxes[d.edge.from]) boxes[d.edge.from].classList.add('hot');
                if (boxes[d.edge.to]) boxes[d.edge.to].classList.add('hot');
            }
        });
    }

    function relations(list, other, empty) {
        if (!list.length) return '<p class="note">' + empty + '</p>';
        return '<table>' + list.map((e) => {
            const via = Object.keys(e.edge_kinds).map((k) => k + ' ' + e.edge_kinds[k]).join(' · ');
            return '<tr><td><button class="link" data-kind="' + escapeHtml(e[other]) + '">' + escapeHtml(nameOf(e[other]))
                + '</button><span class="via">' + escapeHtml(via) + '</span></td><td class="n">' + e.pairs + '</td></tr>';
        }).join('') + '</table>';
    }

    function select(kind) {
        selected = kind;
        highlight();
        const k = answer.kinds.find((x) => x.kind === kind);
        const out = answer.edges.filter((e) => e.from === kind);
        const inc = answer.edges.filter((e) => e.to === kind && e.from !== kind);
        const schema = k.schema
            ? '<code>' + escapeHtml(k.schema) + '</code>'
            : '<span class="warn">not dispatched</span>' + (k.schema_pending ? '<p class="note">' + escapeHtml(k.schema_pending) + '</p>' : '');
        const namespaces = Object.keys(k.namespaces).map((n) => '<span class="chip">' + escapeHtml(n) + ' ' + k.namespaces[n] + '</span>').join('');
        const fields = k.fields.filter((f) => ENVELOPE.indexOf(f.name) < 0 && f.share >= 0.1).map((f) =>
            '<div class="field"><span class="fname">' + escapeHtml(f.name) + '</span><span class="bar"><i style="width:'
            + Math.round(f.share * 100) + '%"></i></span><span class="pct">' + Math.round(f.share * 100) + '%</span></div>').join('');
        detail.innerHTML = '<span class="code">' + escapeHtml(kind) + (k.artifact_kind ? ' · ' + escapeHtml(k.artifact_kind) : '') + '</span>'
            + '<h3>' + escapeHtml(nameOf(kind)) + '</h3>'
            + '<table><tr><td>Artifacts</td><td>' + k.count + '</td></tr>'
            + '<tr><td>Category</td><td>' + (k.category ? '<span class="swatch" style="background:' + colourOf(k.category) + '"></span>' : '') + escapeHtml(label(k.category)) + '</td></tr>'
            + '<tr><td>Provenance</td><td>' + escapeHtml(label(k.provenance)) + '</td></tr>'
            + '<tr><td>Runtime</td><td>' + escapeHtml(label(k.runtime_disposition)) + '</td></tr>'
            + '<tr><td>Schema</td><td>' + schema + '</td></tr>'
            + '<tr><td>Example</td><td><code>' + escapeHtml(k.example) + '</code></td></tr></table>'
            + '<h4>Namespaces</h4><div class="chips">' + namespaces + '</div>'
            + '<h4>Refers to</h4>' + relations(out, 'to', 'Refers to no other kind.')
            + '<h4>Referred to by</h4>' + relations(inc, 'from', 'No kind refers to it.')
            + '<h4>Declares, beyond the envelope</h4>' + (fields || '<p class="note">Only the envelope.</p>')
            + '<p class="note">Share of its artifacts that carry the field. Every kind also carries '
            + ENVELOPE.slice(0, 6).map((f) => '<code>' + f + '</code>').join(', ') + '.</p>';
        detail.querySelectorAll('.link').forEach((b) => b.addEventListener('click', () => select(b.dataset.kind)));
    }

    function start(result) {
        answer = result;
        document.getElementById('kinds-stats').innerHTML =
            '<b>' + result.artifact_count + '</b><span>artifacts</span>'
            + '<b>' + result.kind_count + '</b><span>kinds</span>'
            + '<b>' + result.edge_count + '</b><span>kind-to-kind relations</span>'
            + '<span>snapshot ' + escapeHtml(String(result.snapshot_id).slice(0, 12)) + '…</span>';
        document.getElementById('kinds-legend').innerHTML = result.ontology_declared
            ? result.categories.map((c) => '<span><i class="swatch" style="background:' + colourOf(c) + '"></i>' + escapeHtml(label(c)) + '</span>').join('')
            : '<span>This snapshot seals no ontology, so kinds are not classified.</span>';
        draw();
        select(result.kinds.some((k) => k.kind === 'WF') ? 'WF' : result.kinds[0].kind);
        document.getElementById('show-governance').addEventListener('change', draw);
        document.getElementById('show-counts').addEventListener('change', draw);
    }

    function fail(err) {
        const box = document.getElementById('kinds-error');
        box.hidden = false;
        box.textContent = 'The kind map could not be read: ' + err.message;
    }

    if (window.KIND_MAP_RESULT) {
        start(window.KIND_MAP_RESULT);
    } else {
        ask('si.kind.map', {}).then(start).catch(fail);
    }
})();
