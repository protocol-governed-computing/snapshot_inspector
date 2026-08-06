"""Implementation registry — the code an operation's declared binding resolves to.

This table declares NOTHING about the operation set. It does not say which operations exist, what
they accept, what kind they are, or how they are grouped: all of that is declared by the
`inspection::` TI artifacts in the snapshot and read by `inspector.catalog`. Here there is only
the obedient half — the functions a declared `handler.implementation` can name.

    TI artifact:   handler.implementation: {module: inspector.reads.artifact_show,
                                            callable: artifact_show}
    this registry: resolves that pair to the function object

That is the same relationship a capability transform has with its code: the artifact names
`{module, callable}` and the runtime resolves it. Re-pointing an operation is therefore an
authoring act on an artifact — visible in the snapshot, attested, and diffable — never an edit
here.

**Static, closed, explicitly enumerated.** Every implementation is imported at module load and
indexed by its own `__module__` / `__name__`, so a declared reference resolves by lookup. No
`importlib`, no filesystem discovery, no dynamic import: an implementation this file does not
import cannot be named by any artifact, and a reference to one fails hard rather than resolving
by accident. It mirrors the compiler's closed `HANDLER_REGISTRY`.

Why the dispatch table stays here rather than being resolved from the snapshot by import: the
inspector must be able to answer over a snapshot it cannot fully parse. `si.snapshot.validate`
exists to diagnose exactly that snapshot, and a dispatcher that had to import modules named by
possibly-broken artifacts would fail precisely when it is most needed. The declaration is the
authority; the resolution is deliberately kept incapable of surprises.
"""
from __future__ import annotations

from typing import Any, Callable

from inspector.kinds import SNAPSHOT_QUERY, SNAPSHOT_READ  # noqa: F401 — re-exported

from inspector.queries.artifact_refs import artifact_refs
from inspector.queries.snapshot_validate import snapshot_validate
from inspector.queries.topology_impact import topology_impact
from inspector.reads.artifact_indexed import artifact_indexed
from inspector.reads.artifact_list import artifact_list
from inspector.reads.capability_surface import capability_surface
from inspector.reads.artifact_show import artifact_show
from inspector.reads.behavior_logic_list import behavior_logic_list
from inspector.reads.behavior_logic_show import behavior_logic_show
from inspector.reads.catalog import catalog
from inspector.reads.snapshot_summary import snapshot_summary
from inspector.reads.snapshot_topology import snapshot_topology
from inspector.reads.store_reads import store_consumers, store_list, store_show
from inspector.reads.vocab_resolve import vocab_resolve
from inspector.reads.vocab_search import vocab_search

Projection = Callable[..., tuple[str, dict[str, Any]]]

# Every projection this inspector can run. Order and grouping mean nothing here — those are
# declared by the artifacts.
_PROJECTIONS: tuple[Projection, ...] = (
    catalog,
    snapshot_summary,
    snapshot_topology,
    snapshot_validate,
    artifact_list,
    capability_surface,
    artifact_show,
    artifact_indexed,
    artifact_refs,
    topology_impact,
    store_list,
    store_show,
    store_consumers,
    vocab_search,
    vocab_resolve,
    behavior_logic_list,
    behavior_logic_show,
)


def implementation_ref(fn: Projection) -> str:
    """The reference an artifact uses to name this implementation: `<module>:<callable>`."""
    return f"{fn.__module__}:{fn.__name__}"


# Declared reference → function. Derived from the functions themselves, so the key can never
# drift from what it names.
IMPLEMENTATIONS: dict[str, Projection] = {implementation_ref(fn): fn for fn in _PROJECTIONS}


def resolve_implementation(module: str, callable_name: str) -> Projection:
    """Resolve a TI's declared `handler.implementation` to its function. Fails hard if unknown."""
    ref = f"{module}:{callable_name}"
    fn = IMPLEMENTATIONS.get(ref)
    if fn is None:
        raise KeyError(
            f"declared implementation {ref!r} is not registered in inspector.registry — "
            "an implementation the registry does not import cannot be named by an artifact"
        )
    return fn
