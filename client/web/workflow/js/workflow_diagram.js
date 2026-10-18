/**
 * workflow_diagram.js — Draws a workflow from the snapshot's compiled graph (`*.graph.json`), with
 * its entrance in front, as an SVG the page can mark.
 *
 * Nothing here is particular to Collatz: the boxes, their order and the endings all come from the
 * graph the compiler sealed. The main row follows each node's ACK/SUCCESS route; every other ending
 * sits below the first box that can reach it. Two routes between the same boxes are one edge.
 *
 * The Collatz client draws its workflow with this file too, served to it at `/diagram/`.
 * Styling is the page's: classes `box`, `edge`, `taken`, `selected`, `clickable`, `ending`.
 */
(function () {
    const BW = 132, BH = 54, GX = 58, PAD = 16, ROW1 = 34, ROW2 = 168;
    const NS = 'http://www.w3.org/2000/svg';
    const FORWARD = ['ACK', 'SUCCESS'];

    function el(name, attrs, parent) {
        const node = document.createElementNS(NS, name);
        for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
        if (parent) parent.appendChild(node);
        return node;
    }

    function label(id) {
        return id.replace(/^(TI|IN|CC|EXIT)_/, '').replace(/_V\d+$/, '').toLowerCase().replace(/_/g, ' ');
    }

    function wrap(text, max) {
        const lines = [''];
        for (const w of text.split(' ')) {
            const cur = lines[lines.length - 1];
            if (cur && (cur + ' ' + w).length > max) lines.push(w);
            else lines[lines.length - 1] = cur ? cur + ' ' + w : w;
        }
        return lines.slice(0, 2);
    }

    function layout(graph, entrance) {
        const kinds = Object.fromEntries(graph.nodes.map((n) => [n.id, n.type]));
        // A workflow reached through an entrance (TI) is drawn behind it, with the entrance's own
        // refusal as an ending; one with no entrance starts at its entry node.
        const edges = entrance ? [
            { from: entrance, to: graph.entry, label: 'admit' },
            { from: entrance, to: 'REFUSED', label: 'refuse' },
        ] : [];
        for (const e of graph.edges) {
            const same = edges.find((x) => x.from === e.from && x.to === e.to);
            if (same) same.label += ' / ' + e.condition;
            else edges.push({ from: e.from, to: e.to, label: e.condition });
        }
        if (entrance) {
            kinds[entrance] = 'TI';
            kinds.REFUSED = 'REFUSED';
        }

        const main = entrance ? [entrance, graph.entry] : [graph.entry];
        for (let cur = graph.entry; kinds[cur] !== 'EXIT';) {
            const next = edges.find((e) => e.from === cur && FORWARD.includes(e.label));
            if (!next || main.includes(next.to)) break;
            main.push(next.to);
            cur = next.to;
        }

        const pos = {};
        main.forEach((id, i) => (pos[id] = { x: PAD + i * (BW + GX), y: ROW1, row: 1 }));
        const taken = new Set();
        for (const id of main) {
            for (const e of edges.filter((x) => x.from === id)) {
                if (pos[e.to]) continue;
                let slot = main.indexOf(id);
                while (taken.has(slot)) slot += 1;
                taken.add(slot);
                pos[e.to] = { x: PAD + slot * (BW + GX), y: ROW2, row: 2 };
            }
        }
        const columns = Math.max(main.length, ...[...taken].map((s) => s + 1));
        return { kinds, edges, pos, width: PAD * 2 + columns * (BW + GX) - GX, height: ROW2 + BH + PAD };
    }

    function draw(svg, graph, options) {
        const opts = options || {};
        const { kinds, edges, pos, width, height } = layout(graph, opts.entrance);
        svg.innerHTML = '';
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
        svg.classList.add('workflow');
        const marker = el('marker', { id: 'wf-arrow', viewBox: '0 0 10 10', refX: 9, refY: 5,
            markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' }, el('defs', {}, svg));
        el('path', { d: 'M0,0 L10,5 L0,10 z', class: 'arrow' }, marker);

        const edgeEls = {}, boxEls = {}, outCount = {}, outIndex = {};
        edges.forEach((e) => { if (pos[e.to].row === 2) outCount[e.from] = (outCount[e.from] || 0) + 1; });

        edges.forEach((e, i) => {
            const a = pos[e.from], b = pos[e.to];
            const g = el('g', { class: 'edge' }, svg);
            let d, lx, ly;
            if (a.row === b.row) {
                d = `M${a.x + BW},${a.y + BH / 2} H${b.x - 2}`;
                lx = (a.x + BW + b.x) / 2; ly = a.y + BH / 2 - 6;
            } else {
                const k = outIndex[e.from] = (outIndex[e.from] || 0) + 1;
                const sx = a.x + (BW * k) / ((outCount[e.from] || 1) + 1);
                const cx = b.x + BW / 2;
                const tx = cx + (cx === sx ? 0 : (sx < cx ? -14 : 14));
                const mid = a.y + BH + 22 + (i % 4) * 9;
                d = `M${sx},${a.y + BH} V${mid} H${tx} V${b.y - 2}`;
                lx = sx + 4; ly = a.y + BH + 15;
            }
            el('path', { d, 'marker-end': 'url(#wf-arrow)' }, g);
            el('text', { x: lx, y: ly, 'text-anchor': a.row === b.row ? 'middle' : 'start' }, g).textContent = e.label;
            edgeEls[`${e.from}>${e.to}`] = g;
        });

        for (const [id, p] of Object.entries(pos)) {
            const kind = kinds[id];
            const ending = kind === 'EXIT' || kind === 'REFUSED';
            const g = el('g', { class: 'box' + (ending ? ' ending' : '') + (opts.onSelect ? ' clickable' : ''),
                transform: `translate(${p.x},${p.y})` }, svg);
            el('rect', { width: BW, height: BH, rx: ending ? 22 : 7 }, g);
            el('text', { x: BW / 2, y: 17, 'text-anchor': 'middle', class: 'kind' }, g).textContent = kind;
            const name = kind === 'REFUSED' ? 'at the entrance' : label(id);
            wrap(name, 18).forEach((line, j) =>
                (el('text', { x: BW / 2, y: 33 + j * 15, 'text-anchor': 'middle', class: 'name' }, g).textContent = line));
            if (opts.onSelect) g.addEventListener('click', () => opts.onSelect(id, kind));
            el('title', {}, g).textContent = id;
            boxEls[id] = g;
        }

        return {
            kinds,
            clear() {
                Object.values(boxEls).forEach((b) => b.classList.remove('taken', 'selected'));
                Object.values(edgeEls).forEach((e) => e.classList.remove('taken'));
            },
            mark(path) {
                for (const id of path.nodes) boxEls[id] && boxEls[id].classList.add('taken');
                for (const [a, b] of path.edges) edgeEls[`${a}>${b}`] && edgeEls[`${a}>${b}`].classList.add('taken');
            },
            select(id) {
                Object.values(boxEls).forEach((b) => b.classList.remove('selected'));
                boxEls[id] && boxEls[id].classList.add('selected');
            },
        };
    }

    window.WorkflowDiagram = { draw, label };
})();
