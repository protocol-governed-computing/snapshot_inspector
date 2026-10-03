"""si.execution.explain — explain one run: the path it took, what chose each route, what it touched.

Joins two inputs and keeps them apart in the answer:

- **recorded** — what the run's trace states: the nodes it visited, each node's outcome, every
  route and the outcome that selected it, the steps and atoms each node ran, the events it emitted,
  and the value of every non-deterministic atom (a captured input).
- **joined** — what this inspector adds from the sealed snapshot by node id or FQDN: each node's
  declared type and capability, whether each route is a declared edge, and each artifact's kind.
  The trace does not record these. They sit under a `snapshot` key, or in `artifacts`, so a client
  can draw them differently from what was recorded.

The trace must name the snapshot being read (`inspector.trace`). A trace produced under another
snapshot is refused, not explained: its numeric addresses mean something only inside the snapshot
that produced them, and an explanation against the wrong one would be confidently wrong.

**Why each node decided as it did** is reported only as far as the trace records it:

- an admission gate records every check it evaluated, held or not, so the answer names the check
  that refused;
- a capability records the outcome it returned and the names of its results, not its reasons, and
  the answer says so rather than supplying one;
- a run the declarations could not answer for (an unrouted outcome, a gate with no contract) ends
  in an ERROR record, reported as that, not as a refusal by a rule.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot
from inspector.trace import TraceRefused, read_trace

# The trace's own word for an atom declared not deterministic. Its recorded `outcome` is a
# captured input: replay substitutes it rather than running the atom again.
_NONDETERMINISTIC = "ct_impure"


def _code(fqdn: str | None) -> str | None:
    return fqdn.split("::", 1)[1] if fqdn and "::" in fqdn else fqdn


class _Visit:
    def __init__(self, node: str) -> None:
        self.node = node
        self.fqdn: str | None = None
        self.result: str | None = None
        self.steps: list[dict[str, Any]] = []
        self.atoms: list[dict[str, Any]] = []
        self.events: list[str] = []
        self.route: dict[str, Any] | None = None
        self.admission: bool = False
        self.checks: list[dict[str, Any]] | None = None
        self.errors: list[dict[str, Any]] = []


def _visits(events: list[dict[str, Any]]) -> list[_Visit]:
    """The run as an ordered list of node visits, built from recorded events alone."""
    visits: list[_Visit] = []
    current: _Visit | None = None

    def enter(node: str) -> _Visit:
        visit = _Visit(node)
        visits.append(visit)
        return visit

    for event in events:
        kind = event.get("event_type")
        detail = event.get("detail") or {}
        if kind == "CC_START":
            if current is None or current.node != detail.get("node"):
                current = enter(detail.get("node"))
            current.fqdn = detail.get("cc_fqdn")
        elif kind == "CC_STEP":
            if current is None:
                current = enter(_code(detail.get("step_fqdn")))
                current.fqdn = detail.get("step_fqdn")
            current.steps.append({"step": detail.get("step_fqdn"), "op": event.get("step_op")})
            if event.get("step_op") == "ADMIT":
                current.admission = True
                current.checks = detail.get("checks")
        elif kind == "CT_STEP" and current is not None:
            atom = {"atom": detail.get("step_fqdn"), "path": detail.get("path"),
                    "purity": detail.get("purity")}
            if detail.get("purity") == _NONDETERMINISTIC:
                atom["captured"] = True
                atom["replayed"] = bool(detail.get("replayed"))
                atom["_value"] = detail.get("outcome")
            current.atoms.append(atom)
        elif kind == "CC_COMPLETE" and current is not None:
            current.result = event.get("result_status")
        elif kind == "EVENT" and current is not None:
            current.events.append(detail.get("ev_fqdn"))
        elif kind == "ERROR":
            if current is None:
                current = enter(None)
            current.errors.append(dict(detail))
        elif kind == "WF_ROUTE":
            source = detail.get("from_node")
            if current is None or current.node != source:
                current = enter(source)
            current.route = {"to": detail.get("to_node"), "outcome": event.get("result_status"),
                             "terminal": bool(detail.get("terminal"))}
            if detail.get("to_node") is not None:
                current = enter(detail.get("to_node"))
    return visits


def _determination(visit: _Visit) -> dict[str, Any] | None:
    """Why this node decided as it did, as far as the trace records it — and no further."""
    if visit.admission:
        if visit.checks is None:
            return {"basis": "not recorded", "note": "the trace records the admission outcome, "
                    "not its checks; it predates the runtime recording them"}
        return {"basis": "recorded admission checks", "checks": visit.checks,
                "failed": [c for c in visit.checks if not c.get("held")]}
    if visit.result is not None:
        return {"basis": "capability outcome", "outcome": visit.result,
                "note": "the trace records the outcome the capability returned and its result "
                        "names, not its reasons"}
    return None


def _ending(visits: list[_Visit], status: str | None) -> dict[str, Any]:
    """How the run ended: at a declared ending, where the declarations had no answer, or not at all."""
    errors = [e for v in visits for e in v.errors]
    last = next((v for v in reversed(visits) if v.route is not None), None)
    if last is not None and last.route["terminal"] and last.route["to"] is not None and not errors:
        return {"kind": "declared_ending", "ending": last.route["to"], "status": status,
                "decided_at": last.node, "outcome": last.route["outcome"]}
    if errors:
        at = next(v for v in visits if v.errors)
        return {"kind": "no_declared_answer", "status": status, "at": at.node,
                "errors": errors,
                "note": "the declarations did not answer for this run; no rule refused it"}
    return {"kind": "incomplete", "status": status,
            "note": "the trace records no ending; the run may still be in progress or was cut off"}


def execution_explain(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    reference = str(params.get("trace", ""))
    try:
        trace = read_trace(snapshot.trace_root, reference)
    except TraceRefused as exc:
        return "NOT_FOUND", {"trace": reference, "reason": str(exc)}

    here = snapshot.snapshot_id()
    if trace.snapshot_id != here:
        return "NOT_FOUND", {
            "trace": reference,
            "reason": (f"the trace was produced under snapshot {trace.snapshot_id}; this inspector "
                       f"reads snapshot {here}. Read it against the snapshot it names."),
        }

    events = trace.events
    start = next((e for e in events if e.get("event_type") == "WF_START"), None)
    if start is None:
        return "NOT_FOUND", {"trace": reference, "reason": "the trace records no workflow start"}
    wf = (start.get("detail") or {}).get("wf_fqdn")
    wf_code = _code(wf)

    if snapshot.entry(wf) is None:
        return "NOT_FOUND", {"trace": reference, "wf": wf,
                             "reason": "the workflow the trace ran is not indexed in this snapshot"}
    domain = next((d for d, code in snapshot.behavior_logic_workflows() if code == wf_code), None)
    logic = snapshot.behavior_logic(domain, wf_code) if domain else None
    if logic is None:
        return "NOT_FOUND", {"trace": reference, "wf": wf,
                             "reason": "no behavior logic published for the workflow the trace ran"}
    graph = logic["graph"]
    nodes = {n.get("id"): n for n in graph.get("nodes", [])}
    edges = {(e.get("from"), e.get("to"), e.get("condition")) for e in graph.get("edges", [])}

    complete = next((e for e in events if e.get("event_type") == "WF_COMPLETE"), None)
    trace_id = next((e.get("trace_id") for e in events if e.get("trace_id")), None)
    actor = (start.get("detail") or {}).get("actor")

    named: set[str] = {wf} | ({actor} if actor else set())
    visits_out: list[dict[str, Any]] = []
    captured: list[dict[str, Any]] = []
    undeclared: list[dict[str, Any]] = []
    visits = _visits(events)
    for visit in visits:
        values = [atom.pop("_value", None) for atom in visit.atoms]
        declared = nodes.get(visit.node)
        joined = ({"declared": False} if declared is None else {
            "declared": True,
            "type": declared.get("type"),
            "capability": declared.get("capability"),
            "capability_type": declared.get("capability_type"),
        })
        route = None
        if visit.route is not None:
            is_edge = (visit.node, visit.route["to"], visit.route["outcome"]) in edges
            route = {**visit.route, "snapshot": {"declared_edge": is_edge}}
            if not is_edge:
                undeclared.append({"from": visit.node, **visit.route})
        visits_out.append({
            "node": visit.node,
            "fqdn": visit.fqdn,
            "result": visit.result,
            "steps": visit.steps,
            "atoms": visit.atoms,
            "events": visit.events,
            "determination": _determination(visit),
            "errors": visit.errors,
            "route": route,
            "snapshot": joined,
        })
        named.update(s["step"] for s in visit.steps if s["step"])
        named.update(a["atom"] for a in visit.atoms if a["atom"])
        named.update(e for e in visit.events if e)
        if declared and declared.get("capability"):
            named.add(declared["capability"])
        if visit.fqdn:
            named.add(visit.fqdn)
        for atom, value in zip(visit.atoms, values):
            if atom.get("captured"):
                # A captured input never selects a route itself; the node's recorded outcome does.
                captured.append({
                    "node": visit.node,
                    "atom": atom["atom"],
                    "path": atom["path"],
                    "replayed": atom["replayed"],
                    "value": value,
                    "routed_by": None if route is None else {
                        "node": visit.node, "outcome": route["outcome"], "to": route["to"]},
                })

    artifacts = []
    for fqdn in sorted(f for f in named if f):
        entry = snapshot.entry(fqdn)
        artifacts.append({"fqdn": fqdn, "indexed": entry is not None,
                          "kind": entry.get("kind") if entry else None})

    return "SUCCESS", {
        "trace": reference,
        "trace_id": trace_id,
        "snapshot_id": here,
        "tie": {"snapshot_id": trace.snapshot_id, "standing": "claimed",
                "basis": "the trace's own trace_classification record; the trace is unsealed"},
        "wf": wf,
        "domain": domain,
        "status": complete.get("result_status") if complete else None,
        "ending": _ending(visits, complete.get("result_status") if complete else None),
        "visits": visits_out,
        "captured_inputs": captured,
        "undeclared_routes": undeclared,
        "artifacts": artifacts,
    }

