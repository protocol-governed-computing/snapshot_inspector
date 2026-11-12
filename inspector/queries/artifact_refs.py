"""si.artifact.refs — who references this artifact, and what it references.

Derived by walking the federated semantic graph: `refs` are incoming edges (consumers), `deps` are
outgoing edges (dependencies). `transitive` extends both to their full closure, with each result
carrying the `depth` at which it was reached and the `edge_kind` that reached it.

An artifact that is indexed but carries no evidence node is not traversable, and that is reported
explicitly (`traversable: false`) rather than as an empty result — "no consumers" and "cannot be
walked" are different facts, and collapsing them is how a vacuous answer passes for a real one.
"""
from __future__ import annotations

from typing import Any

from inspector.graph import SemanticGraph
from inspector.snapshot import Snapshot


def artifact_refs(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fqdn = str(params.get("artifact", ""))
    if "::" not in fqdn:
        return "NOT_FOUND", {"artifact": fqdn, "reason": "expected a <namespace>::<CODE> FQDN"}
    if snapshot.entry(fqdn) is None:
        return "NOT_FOUND", {"artifact": fqdn, "reason": "not present in snapshot"}

    transitive = bool(params.get("transitive", False))
    graph = SemanticGraph(snapshot)
    refs = graph.refs(fqdn, transitive=transitive)
    deps = graph.deps(fqdn, transitive=transitive)

    return "SUCCESS", {
        "artifact": fqdn,
        "kind": graph.node_kind(fqdn),
        "transitive": transitive,
        "traversable": graph.known(fqdn),
        "ref_count": len(refs),
        "dep_count": len(deps),
        "refs": refs,
        "deps": deps,
    }
