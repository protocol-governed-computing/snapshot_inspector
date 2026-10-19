/**
 * workflow_map.js — One workflow as a map: its compiled graph, drawn with its entrance in front,
 * each box opening the declaration behind it.
 *
 * A THIN client of the governed boundary, like the inspection surface beside it. Every fact on this
 * page is the answer to a `si.` operation, sent as
 *
 *     POST /si   { "operation": "si.<...>", "params": { ... } }
 *
 *   si.artifact.list         the workflows (kind WF), when none is named
 *   si.behavior_logic.show   the workflow's compiled graph
 *   si.artifact.refs         its entrance (TI_INVOKES_WF) and the FQDN of every node it contains
 *   si.artifact.show         the declaration behind a box
 *
 * It renders answers and derives nothing: no FQDN is assembled from a name, and no relationship is
 * computed here that the inspector did not return.
 *
 *   /workflow/?wf=workload::WF_COLLATZ_CONJECTURE_V0#TI_COLLATZ_COMPUTE_V0
 *
 * opens that workflow, and the box named after `#`.
 */
(function () {
    const OPERATION_ROUTE = '/si';
    const detail = document.getElementById('detail');
    let graph = null, diagram = null, wfFqdn = null, wfCanonical = null;
    const fqdns = {};            // node code -> FQDN, as si.artifact.refs returned it

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

    function codeOf(fqdn) { return fqdn.split('::').pop(); }

    // The declaration as authored: the Machine block of the artifact's content.
    function authored(canonical) {
        const block = /```yaml\n([\s\S]*?)```/.exec(canonical.content || '');
        return block ? block[1] : JSON.stringify(canonical.frontmatter, null, 2);
    }

    function show(title, intro, text, highlight) {
        const lines = text.split('\n').map((line) =>
            highlight && highlight.test(line) ? '<mark>' + escapeHtml(line) + '</mark>' : escapeHtml(line));
        detail.hidden = false;
        detail.innerHTML = '<h3><code>' + escapeHtml(title) + '</code></h3><p class="map-sub">' + intro + '</p>'
            + '<pre class="declaration">' + lines.join('\n') + '</pre>';
    }

    function button(label, onClick) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'pick-btn';
        b.textContent = label;
        b.addEventListener('click', onClick);
        return b;
    }

    const INTRO = {
        TI: 'The entrance. It declares what a caller may send and the workflow it starts. Its limits are highlighted.',
        IN: 'The entry point. It declares what a request must carry to be admitted.',
        CC: 'A contract: one unit of work and the steps inside it. Open a step to read it.',
        CT: 'A transform: one computation, and the only kind of declaration that names code.',
        CS: 'A side effect: the only way a step may read or write stored data.',
    };

    async function openArtifact(fqdn, kind) {
        detail.hidden = false;
        detail.innerHTML = '<p class="map-sub">Reading ' + escapeHtml(fqdn) + '…</p>';
        const canonical = (await ask('si.artifact.show', { artifact: fqdn })).canonical;
        show(fqdn, INTRO[kind] || '', authored(canonical), kind === 'TI' ? /^\s*(min|max):/ : null);

        if (kind === 'CC') {
            const node = graph.nodes.find((n) => n.cc_code && fqdns[n.cc_code] === fqdn)
                || graph.nodes.find((n) => n.id === codeOf(fqdn));
            const steps = (node && node.projection && node.projection.steps) || [];
            const bar = document.createElement('div');
            bar.className = 'step-bar';
            for (const step of steps) {
                bar.appendChild(button('Open ' + step.kind + ' ' + step.id, () => openArtifact(step.fqdn, step.kind).catch(fail)));
            }
            detail.appendChild(bar);
        }
        if (kind === 'CT') {
            const impl = (canonical.frontmatter.machine || {}).implementation;
            if (impl) {
                const note = document.createElement('p');
                note.className = 'map-sub';
                note.innerHTML = 'This transform names the code <code>' + escapeHtml(impl.module) + '.'
                    + escapeHtml(impl.callable) + '</code>. Read it with '
                    + '<code>python -m inspect ' + escapeHtml(impl.module) + '</code>.';
                detail.appendChild(note);
            }
        }
    }

    async function openEnding(id) {
        wfCanonical = wfCanonical || (await ask('si.artifact.show', { artifact: wfFqdn })).canonical;
        const node = wfCanonical.frontmatter.core.nodes[id];
        show(id, 'An ending, declared inside <code>' + escapeHtml(wfFqdn) + '</code>. A run can finish '
            + 'only at an ending its workflow declares.', JSON.stringify({ [id]: node }, null, 2), null);
    }

    function openRefusal(entrance) {
        detail.hidden = false;
        detail.innerHTML = '<h3>Refused at the entrance</h3><p class="map-sub">When a value breaks the '
            + "entrance's input contract, PGC refuses it here and names the reason. No workflow starts, so "
            + 'no step runs and no trace is written. The refusal has no declaration of its own: it is the '
            + "entrance's contract, applied.</p>";
        detail.appendChild(button("Read the entrance's contract", () => select(entrance, 'TI')));
    }

    function fail(err) {
        detail.hidden = false;
        detail.innerHTML = '<p class="map-error">' + escapeHtml(err.message) + '</p>';
    }

    function select(id, kind) {
        diagram.select(id);
        if (kind === 'REFUSED') return openRefusal(Object.keys(diagram.kinds).find((k) => diagram.kinds[k] === 'TI'));
        if (kind === 'EXIT') return openEnding(id).catch(fail);
        const node = graph.nodes.find((n) => n.id === id);
        const code = node && node.cc_code ? node.cc_code : id;
        if (!fqdns[code]) return fail(new Error('si.artifact.refs returned no FQDN for ' + code));
        return openArtifact(fqdns[code], kind).catch(fail);
    }

    function fromHash() {
        const id = decodeURIComponent(location.hash.slice(1));
        if (id && diagram && diagram.kinds[id]) select(id, diagram.kinds[id]);
    }

    async function listWorkflows() {
        const listed = await ask('si.artifact.list', { kind: 'WF' });
        const list = document.getElementById('workflow-list');
        for (const row of listed.artifacts) {
            const item = document.createElement('li');
            item.innerHTML = '<a href="?wf=' + encodeURIComponent(row.artifact) + '"><code>'
                + escapeHtml(row.artifact) + '</code></a>';
            list.appendChild(item);
        }
        document.getElementById('picker').hidden = false;
    }

    async function load() {
        wfFqdn = new URLSearchParams(location.search).get('wf');
        if (!wfFqdn) return listWorkflows();

        const [shown, refs] = await Promise.all([
            ask('si.behavior_logic.show', { wf: wfFqdn }),
            ask('si.artifact.refs', { artifact: wfFqdn }),
        ]);
        graph = shown.graph;
        for (const dep of refs.deps || []) fqdns[codeOf(dep.fqdn)] = dep.fqdn;
        const ti = (refs.refs || []).find((r) => r.edge_kind === 'TI_INVOKES_WF');
        if (ti) fqdns[codeOf(ti.fqdn)] = ti.fqdn;

        document.getElementById('map-title').textContent = wfFqdn;
        document.getElementById('map').hidden = false;
        document.getElementById('kinds').hidden = false;
        diagram = window.WorkflowDiagram.draw(document.getElementById('wf-diagram'), graph,
            { entrance: ti ? codeOf(ti.fqdn) : null, onSelect: select });
        detail.hidden = false;
        detail.innerHTML = '<p class="map-sub">Click a box above. '
            + (ti ? 'Start with <b>TI</b>, the entrance, and walk right.' : 'Start at the left and walk right.') + '</p>';
        const summary = await ask('si.snapshot.summary', {});
        document.getElementById('footer').textContent = 'Reading snapshot ' + summary.snapshot_id;
        fromHash();
    }

    window.addEventListener('hashchange', fromHash);
    load().catch(fail);
})();
