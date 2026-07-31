"""Semantic graph — the traversal substrate behind every SNAPSHOT_QUERY operation.

The graph is the union of every domain's `evidence/<domain>/evidence.json` (artifact-level nodes
+ typed edges), deduplicated: an artifact visible to three domain builds contributes one node and
its edges once. Operations here are STRUCTURAL only — neighbourhood, closure, grouping. No domain
knowledge and no PGC semantics live here; that is what keeps inspection from becoming a second
governance engine.

Edge direction, as the compiler materializes it:

    source --kind--> target    means "source depends on / contains / routes to target"

So the CONSUMERS of X are the sources of edges INTO X (`refs`), and X's DEPENDENCIES are the
targets of edges out of X (`deps`). Impact analysis is the transitive consumer closure.

Ported from `protocol_compiler/compiler/inspection/traversal.py`, which this repo supersedes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from inspector.snapshot import Snapshot


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str
    metadata_json: str  # canonical JSON — keeps Edge hashable, so dedup is by value

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json)


class SemanticGraph:
    """Federated, immutable artifact graph over every composed domain."""

    def __init__(self, snapshot: Snapshot) -> None:
        nodes: dict[str, str] = {}
        edges: set[Edge] = set()

        for domain in snapshot.evidence_domains():
            evidence = snapshot.evidence(domain)
            for node in evidence.get("nodes", []):
                nodes.setdefault(node["fqdn"], node["kind"])
            for edge in evidence.get("edges", []):
                edges.add(Edge(
                    source=edge["source_fqdn"],
                    target=edge["target_fqdn"],
                    kind=edge["kind"],
                    metadata_json=json.dumps(edge.get("metadata", {}), sort_keys=True),
                ))

        self.nodes = nodes
        self.edges = sorted(edges, key=lambda e: (e.source, e.target, e.kind, e.metadata_json))

        self._out: dict[str, list[Edge]] = {}
        self._in: dict[str, list[Edge]] = {}
        for edge in self.edges:
            self._out.setdefault(edge.source, []).append(edge)
            self._in.setdefault(edge.target, []).append(edge)

    # ── direct neighbourhood ─────────────────────────────────────

    def out_edges(self, fqdn: str) -> list[Edge]:
        return self._out.get(fqdn, [])

    def in_edges(self, fqdn: str) -> list[Edge]:
        return self._in.get(fqdn, [])

    def node_kind(self, fqdn: str) -> str:
        return self.nodes.get(fqdn, "UNKNOWN")

    def known(self, fqdn: str) -> bool:
        """True iff the graph carries this artifact as a node.

        An artifact can be indexed but carry no evidence node — it is then not traversable, which
        a caller must be able to distinguish from "traversable but unreferenced".
        """
        return fqdn in self.nodes

    # ── walks ────────────────────────────────────────────────────

    def refs(self, fqdn: str, transitive: bool = False) -> list[dict[str, Any]]:
        """Who references this artifact — incoming edges; its consumers."""
        return self._walk(fqdn, self._in, "source", transitive)

    def deps(self, fqdn: str, transitive: bool = False) -> list[dict[str, Any]]:
        """What this artifact depends on — outgoing edges."""
        return self._walk(fqdn, self._out, "target", transitive)

    def _walk(
        self,
        start: str,
        adjacency: dict[str, list[Edge]],
        neighbor_attr: str,
        transitive: bool,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        visited: set[str] = {start}
        frontier = [start]
        depth = 0
        while frontier:
            depth += 1
            next_frontier: list[str] = []
            for fqdn in frontier:
                for edge in adjacency.get(fqdn, []):
                    neighbor = getattr(edge, neighbor_attr)
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)
                    results.append({
                        "fqdn": neighbor,
                        "kind": self.node_kind(neighbor),
                        "edge_kind": edge.kind,
                        "depth": depth,
                    })
                    next_frontier.append(neighbor)
            if not transitive:
                break
            frontier = next_frontier
        results.sort(key=lambda r: (r["depth"], r["fqdn"]))
        return results

    def impact(self, fqdn: str) -> dict[str, dict[str, list[str]]]:
        """Transitive consumer closure, grouped by artifact kind then namespace."""
        grouped: dict[str, dict[str, list[str]]] = {}
        for record in self.refs(fqdn, transitive=True):
            namespace = record["fqdn"].split("::", 1)[0]
            grouped.setdefault(record["kind"], {}).setdefault(namespace, []).append(record["fqdn"])
        return {
            kind: {ns: sorted(set(fqdns)) for ns, fqdns in sorted(by_ns.items())}
            for kind, by_ns in sorted(grouped.items())
        }
