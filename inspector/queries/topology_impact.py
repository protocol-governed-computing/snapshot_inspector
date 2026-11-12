"""si.topology.impact — what a change to this artifact reaches.

The transitive CONSUMER closure, grouped by artifact kind then namespace: everything that would
have to be re-examined if this artifact changed. Direction matters and is not symmetric — impact
walks edges backwards (into the artifact), because a consumer depends on what it references, not
the reverse.

Grouping is presentational; membership is not. The closure is computed once, in the graph, and
the same walk backs `si.artifact.refs` with `transitive: true`. Two implementations of one
relationship would eventually disagree about the blast radius of a change, which is the one
question this operation exists to answer.
"""
from __future__ import annotations

from typing import Any

from inspector.graph import SemanticGraph
from inspector.snapshot import Snapshot


def topology_impact(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fqdn = str(params.get("artifact", ""))
    if "::" not in fqdn:
        return "NOT_FOUND", {"artifact": fqdn, "reason": "expected a <namespace>::<CODE> FQDN"}
    if snapshot.entry(fqdn) is None:
        return "NOT_FOUND", {"artifact": fqdn, "reason": "not present in snapshot"}

    graph = SemanticGraph(snapshot)
    grouped = graph.impact(fqdn)
    reached = sorted({f for by_ns in grouped.values() for fqdns in by_ns.values() for f in fqdns})

    return "SUCCESS", {
        "artifact": fqdn,
        "kind": graph.node_kind(fqdn),
        "traversable": graph.known(fqdn),
        "impacted_count": len(reached),
        "impacted_namespaces": sorted({f.split("::", 1)[0] for f in reached}),
        "impact": grouped,
    }
