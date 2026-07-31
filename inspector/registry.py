"""Internal dispatch: Operation Identity → projection.

The inspector's OWN routing table. Transport never sees it — the boundary passes an Operation
Identity to `inspector.api.query`, which resolves it here. That is what keeps the transport
adapter from becoming an RPC router: it selects a HANDLER KIND (`SNAPSHOT_READ` /
`SNAPSHOT_QUERY`) and nothing else. Branching on an operation string in the adapter is forbidden.

Each entry declares its handler kind alongside its callable, so the kind is a property of the
operation itself rather than a fact the transport has to remember about it:

    SNAPSHOT_READ   project PUBLISHED snapshot material — no traversal, no evaluation
    SNAPSHOT_QUERY  DERIVE a result by traversing or evaluating snapshot state

The table is also the CATALOG. `inspector.api.operations()` publishes it, so a client's menu of
what can be asked is generated from what can actually be answered — a hand-maintained second list
would drift the moment an operation is added or renamed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from inspector.queries.artifact_refs import artifact_refs
from inspector.queries.snapshot_validate import snapshot_validate
from inspector.queries.topology_impact import topology_impact
from inspector.reads.artifact_indexed import artifact_indexed
from inspector.reads.artifact_list import artifact_list
from inspector.reads.artifact_show import artifact_show
from inspector.reads.behavior_logic_list import behavior_logic_list
from inspector.reads.behavior_logic_show import behavior_logic_show
from inspector.reads.catalog import catalog
from inspector.reads.snapshot_summary import snapshot_summary
from inspector.reads.snapshot_topology import snapshot_topology
from inspector.reads.store_reads import store_consumers, store_list, store_show
from inspector.reads.vocab_resolve import vocab_resolve
from inspector.reads.vocab_search import vocab_search

SNAPSHOT_READ = "SNAPSHOT_READ"
SNAPSHOT_QUERY = "SNAPSHOT_QUERY"

CATEGORIES = ("SNAPSHOT", "ARTIFACTS", "STORES", "VOCABULARY", "BEHAVIOR")


@dataclass(frozen=True)
class Operation:
    identity: str
    kind: str                   # SNAPSHOT_READ | SNAPSHOT_QUERY
    category: str               # catalog grouping, one of CATEGORIES
    label: str                  # short human name for a menu entry
    params: tuple[str, ...]     # accepted parameter names
    required: tuple[str, ...]   # those without which the operation cannot answer
    flags: tuple[str, ...]      # of `params`, the boolean ones — a client renders these as switches
    summary: str
    handler: Callable[..., tuple[str, dict[str, Any]]]


def _op(identity, kind, category, label, params, required, summary, handler,
        flags=()) -> Operation:
    return Operation(
        identity, kind, category, label,
        tuple(params), tuple(required), tuple(flags), summary, handler,
    )


OPERATIONS: dict[str, Operation] = {
    op.identity: op for op in (
        # ── SNAPSHOT ──────────────────────────────────────────────
        _op("si.catalog", SNAPSHOT_READ, "SNAPSHOT", "Catalog",
            (), (),
            "Every inspection operation this snapshot inspector answers.",
            catalog),
        _op("si.snapshot.summary", SNAPSHOT_READ, "SNAPSHOT", "Summary",
            (), (),
            "Composition identity, domains, and published counts by kind.",
            snapshot_summary),
        _op("si.snapshot.topology", SNAPSHOT_READ, "SNAPSHOT", "Topology",
            (), (),
            "Domain → subdomain → workflow map of the composition.",
            snapshot_topology),
        _op("si.snapshot.validate", SNAPSHOT_QUERY, "SNAPSHOT", "Validate",
            ("strict",), (),
            "Integrity and closure of the assembled snapshot; every check reports what it examined.",
            snapshot_validate, flags=("strict",)),

        # ── ARTIFACTS ─────────────────────────────────────────────
        _op("si.artifact.list", SNAPSHOT_READ, "ARTIFACTS", "List",
            ("kind", "domain"), (),
            "The artifact catalog, optionally narrowed by kind or namespace.",
            artifact_list),
        _op("si.artifact.show", SNAPSHOT_READ, "ARTIFACTS", "Show",
            ("artifact",), ("artifact",),
            "The published canonical artifact for an FQDN, as authored.",
            artifact_show),
        _op("si.artifact.indexed", SNAPSHOT_READ, "ARTIFACTS", "Indexed",
            ("artifact",), ("artifact",),
            "Whether an FQDN is carried by this composition's artifact index.",
            artifact_indexed),
        _op("si.artifact.refs", SNAPSHOT_QUERY, "ARTIFACTS", "References",
            ("artifact", "transitive"), ("artifact",),
            "Consumers (incoming edges) and dependencies (outgoing edges), direct or transitive.",
            artifact_refs, flags=("transitive",)),
        _op("si.topology.impact", SNAPSHOT_QUERY, "ARTIFACTS", "Impact",
            ("artifact",), ("artifact",),
            "Transitive consumer closure — what a change to this artifact reaches.",
            topology_impact),

        # ── STORES ────────────────────────────────────────────────
        _op("si.store.list", SNAPSHOT_READ, "STORES", "List",
            ("domain",), (),
            "Every declared store with its owning STRUCTURE, path and binding count.",
            store_list),
        _op("si.store.show", SNAPSHOT_READ, "STORES", "Show",
            ("store",), ("store",),
            "One store's declarations and their full binding surface.",
            store_show),
        _op("si.store.consumers", SNAPSHOT_READ, "STORES", "Consumers",
            ("store",), ("store",),
            "Which workflows and capability contracts reach a store, and through which binding.",
            store_consumers),

        # ── VOCABULARY ────────────────────────────────────────────
        _op("si.vocab.search", SNAPSHOT_READ, "VOCABULARY", "Search",
            ("term",), ("term",),
            "Semantic-vocabulary identities matching a term, with their per-domain addresses.",
            vocab_search),
        _op("si.vocab.resolve", SNAPSHOT_READ, "VOCABULARY", "Resolve",
            ("artifact", "address", "domain"), (),
            "Identity → per-domain addresses, or an address within one domain → identity.",
            vocab_resolve),

        # ── BEHAVIOR ──────────────────────────────────────────────
        _op("si.behavior_logic.list", SNAPSHOT_READ, "BEHAVIOR", "Workflows",
            (), (),
            "Every workflow carrying a published behavior-logic graph.",
            behavior_logic_list),
        _op("si.behavior_logic.show", SNAPSHOT_READ, "BEHAVIOR", "Logic Graph",
            ("wf",), ("wf",),
            "One workflow's compiled execution graph and its rendered projection.",
            behavior_logic_show),
    )
}
