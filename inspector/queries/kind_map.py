"""si.kind.map — the composition read one level up: every artifact kind, and how kinds refer to kinds.

An instance view answers "what does this artifact touch". This answers the question a reader needs
first: what kinds exist, what each one declares, and which kinds a kind can reach. It is derived
from the same federated semantic graph as `si.artifact.refs`, aggregated by the kind of each end.

**An edge counts distinct artifact pairs, not edges.** One workflow names one contract as a node, as
a routing target and by full name; a count of edges would report three links where there is one.
`edge_kinds` keeps the typed edges that make up each pair, so the kind of relation stays readable.

**Only what the snapshot publishes.** Kinds and counts come from the artifact index, field shapes
from each artifact's parsed declaration, and the schema each kind is described by from the
platform's own `structure::STRUCTURE_SCHEMA_DISPATCH_V0`. A kind's semantic category, provenance
and runtime disposition come from the sealed Governance Ontology, `artifact::VOCAB_GOVERNANCE_ONTOLOGY_V0`.
A snapshot that carries either declaration reports what it says; one that carries neither reports
`schema_dispatch_declared` or `ontology_declared` as false rather than inventing an answer.

**A domain narrows the map to one composed domain.** `domain` names a domain the manifest composes,
such as `platform` or `blockchain`, not a namespace. An artifact is in that domain when the index
gives it an address there, so a platform capability a domain reaches is part of the domain's map.
An edge counts when both its artifacts are in the domain. Without `domain`, the map is the whole
snapshot. A domain the manifest does not compose is NOT_FOUND, so a typo cannot pass for an empty
domain.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from inspector.graph import SemanticGraph
from inspector.snapshot import Snapshot

SCHEMA_DISPATCH = "structure::STRUCTURE_SCHEMA_DISPATCH_V0"
ONTOLOGY = "artifact::VOCAB_GOVERNANCE_ONTOLOGY_V0"


def _fields(frontmatter: dict[str, Any]) -> list[str]:
    """The keys an artifact declares: top level, and one level into `core`."""
    names = [str(key) for key in frontmatter]
    core = frontmatter.get("core")
    if isinstance(core, dict):
        names.extend(f"core.{key}" for key in core)
    return names


def _ontology(frontmatter: dict[str, Any]) -> dict[str, dict[str, str]]:
    """artifact kind → {category, provenance, runtime_disposition}, as the vocabulary groups state it."""
    def groups(prefix: str) -> dict[str, list[str]]:
        return {name[len(prefix):]: list((group or {}).get("entries") or [])
                for name, group in frontmatter.items()
                if name.startswith(prefix) and isinstance(group, dict)}

    disposition = {category: name for name, categories in groups("runtime_disposition_").items()
                   for category in categories}
    out: dict[str, dict[str, str]] = {}
    for category, kinds in groups("category_").items():
        for kind in kinds:
            out.setdefault(kind, {})["category"] = category
            out[kind]["runtime_disposition"] = disposition.get(category)
    for provenance, kinds in groups("provenance_").items():
        for kind in kinds:
            out.setdefault(kind, {})["provenance"] = provenance
    return out


def kind_map(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    domain = params.get("domain")
    domains = snapshot.domains()
    if domain is not None and domain not in domains:
        return "NOT_FOUND", {
            "reason": f"this snapshot composes no domain {domain!r}",
            "known_domains": domains,
        }
    entries = {fqdn: entry for fqdn, entry in snapshot.entries().items()
               if domain is None or domain in (entry.get("addresses") or {})}
    graph = SemanticGraph(snapshot)

    def kind_of(fqdn: str) -> str:
        entry = entries.get(fqdn)
        return str(entry.get("kind")) if entry else graph.node_kind(fqdn)

    counts: Counter[str] = Counter()
    namespaces: dict[str, Counter[str]] = defaultdict(Counter)
    fields: dict[str, Counter[str]] = defaultdict(Counter)
    artifact_kinds: dict[str, Counter[str]] = defaultdict(Counter)
    example: dict[str, str] = {}
    for fqdn in sorted(entries):
        kind = kind_of(fqdn)
        counts[kind] += 1
        namespaces[kind][fqdn.split("::")[0]] += 1
        example.setdefault(kind, fqdn)
        frontmatter = (snapshot.canonical(fqdn) or {}).get("frontmatter") or {}
        if isinstance(frontmatter, dict):
            fields[kind].update(set(_fields(frontmatter)))
            if frontmatter.get("artifact_kind"):
                artifact_kinds[kind][str(frontmatter["artifact_kind"])] += 1

    dispatch = (snapshot.canonical(SCHEMA_DISPATCH) or {}).get("frontmatter") or {}
    dispatch_core = dispatch.get("core") or {}
    described_by = dispatch_core.get("schema_dispatch") or {}
    pending = dispatch_core.get("description_pending") or {}

    ontology_fm = (snapshot.canonical(ONTOLOGY) or {}).get("frontmatter") or {}
    ontology = _ontology(ontology_fm)

    kinds = []
    for kind, count in counts.most_common():
        declared_kind = artifact_kinds[kind].most_common(1)[0][0] if artifact_kinds[kind] else None
        kinds.append({
            "kind": kind,
            "artifact_kind": declared_kind,
            "count": count,
            "namespaces": dict(namespaces[kind].most_common()),
            "example": example[kind],
            "schema": described_by.get(declared_kind) if declared_kind else None,
            "schema_pending": pending.get(declared_kind) if declared_kind else None,
            "category": ontology.get(declared_kind, {}).get("category"),
            "provenance": ontology.get(declared_kind, {}).get("provenance"),
            "runtime_disposition": ontology.get(declared_kind, {}).get("runtime_disposition"),
            "fields": [{"name": name, "share": round(n / count, 3)}
                       for name, n in fields[kind].most_common()],
        })

    pairs: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    typed: dict[tuple[str, str], dict[str, set[tuple[str, str]]]] = defaultdict(lambda: defaultdict(set))
    for edge in graph.edges:
        if domain is not None and not (edge.source in entries and edge.target in entries):
            continue
        key = (kind_of(edge.source), kind_of(edge.target))
        pair = (edge.source, edge.target)
        pairs[key].add(pair)
        typed[key][edge.kind].add(pair)

    edges = [
        {
            "from": source_kind,
            "to": target_kind,
            "pairs": len(linked),
            "sources": len({source for source, _ in linked}),
            "edge_kinds": {name: len(p) for name, p in
                           sorted(typed[(source_kind, target_kind)].items(), key=lambda kv: -len(kv[1]))},
        }
        for (source_kind, target_kind), linked in sorted(pairs.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]

    return "SUCCESS", {
        "snapshot_id": snapshot.snapshot_id(),
        "filter": {"domain": domain},
        "domains": domains,
        "artifact_count": sum(counts.values()),
        "kind_count": len(kinds),
        "edge_count": len(edges),
        "schema_dispatch_declared": bool(dispatch),
        "ontology_declared": bool(ontology_fm),
        "categories": list((ontology_fm.get("semantic_categories") or {}).get("entries") or []),
        "kinds": kinds,
        "edges": edges,
    }
