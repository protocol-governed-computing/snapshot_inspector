"""The operation catalog, read from the snapshot's own `inspection::` TI artifacts.

**The protocol declares which operations exist; the code only obeys.** An operation's identity,
handler kind, accepted parameters and their types, which are required, how it is presented, and
which implementation answers it are all declared by a compiled TI artifact. Nothing in Python
enumerates the operation set — `inspector.registry` holds implementations and no metadata at all.

Adding, removing, renaming or re-pointing an operation is therefore an authoring act on an
artifact that is compiled, sealed into the snapshot and attested. It is visible in a snapshot
diff, and it cannot happen silently in code.

    TI frontmatter                          Operation field
    ─────────────────────────────────────   ───────────────
    operation                               identity
    handler.kind                            kind
    handler.implementation {module,callable} implementation → registry lookup
    input_contract {name: {type, required}} params / required / flags
    catalog {category, label, summary}      presentation

`flags` is derived, not declared twice: a parameter is a flag exactly when its declared type is
boolean. A client renders those as switches.

Read once per `Snapshot` instance. If the snapshot carries no inspection contracts this raises —
an inspector pointed at a snapshot that declares no operations has nothing to offer, and saying so
is more useful than answering from a private list the snapshot does not know about.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inspector.kinds import CATEGORIES, INSPECTION_KINDS as _INSPECTION_KINDS
from inspector.registry import Projection, resolve_implementation
from inspector.snapshot import Snapshot, SnapshotError


@dataclass(frozen=True)
class Operation:
    identity: str
    kind: str                   # SNAPSHOT_READ | SNAPSHOT_QUERY
    category: str               # catalog grouping
    label: str                  # short human name for a menu entry
    params: tuple[str, ...]     # accepted parameter names
    required: tuple[str, ...]   # those without which the operation cannot answer
    flags: tuple[str, ...]      # of `params`, the ones declared boolean
    summary: str
    implementation: str         # "<module>:<callable>", as the artifact declares it
    handler: Projection         # what that reference resolves to


def _operation_from_ti(frontmatter: dict[str, Any], source: str) -> Operation:
    identity = frontmatter.get("operation")
    handler = frontmatter.get("handler") or {}
    kind = handler.get("kind")
    if not identity:
        raise SnapshotError(f"inspection TI declares no operation identity: {source}")
    if kind not in _INSPECTION_KINDS:
        raise SnapshotError(
            f"inspection TI {identity!r} declares handler kind {kind!r}; expected one of "
            f"{list(_INSPECTION_KINDS)} ({source})"
        )

    declared_impl = handler.get("implementation") or {}
    module = declared_impl.get("module")
    callable_name = declared_impl.get("callable")
    if not module or not callable_name:
        raise SnapshotError(
            f"inspection TI {identity!r} declares no handler.implementation {{module, callable}} "
            f"({source}) — an operation whose implementation is not declared is bound by code, "
            "not by protocol"
        )

    contract = frontmatter.get("input_contract") or {}
    params = tuple(contract)
    required = tuple(p for p in params if (contract[p] or {}).get("required") is True)
    flags = tuple(p for p in params if (contract[p] or {}).get("type") == "boolean")

    presentation = frontmatter.get("catalog") or {}
    category = presentation.get("category") or "SNAPSHOT"
    if category not in CATEGORIES:
        raise SnapshotError(
            f"inspection TI {identity!r} declares category {category!r}, which is not a known "
            f"catalog category {list(CATEGORIES)} ({source})"
        )

    return Operation(
        identity=identity,
        kind=kind,
        category=category,
        label=presentation.get("label") or identity,
        params=params,
        required=required,
        flags=flags,
        summary=presentation.get("summary") or "",
        implementation=f"{module}:{callable_name}",
        handler=resolve_implementation(module, callable_name),
    )


def load_catalog(snapshot: Snapshot) -> dict[str, Operation]:
    """Every inspection operation the snapshot declares, keyed by Operation Identity."""
    cached = snapshot.cached("__catalog__")
    if cached is not None:
        return cached

    operations: dict[str, Operation] = {}
    for fqdn, entry in snapshot.entries().items():
        if entry.get("kind") != "TI":
            continue
        canonical = snapshot.canonical(fqdn) or {}
        frontmatter = canonical.get("frontmatter") or {}
        handler = frontmatter.get("handler") or {}
        if handler.get("kind") not in _INSPECTION_KINDS:
            continue  # an execution TI belongs to a workload, not to this catalog
        operation = _operation_from_ti(frontmatter, fqdn)
        if operation.identity in operations:
            raise SnapshotError(
                f"two inspection TIs declare operation {operation.identity!r} — an Operation "
                "Identity must resolve to exactly one contract"
            )
        operations[operation.identity] = operation

    if not operations:
        raise SnapshotError(
            f"snapshot at {snapshot.root} declares no inspection operations "
            "(no TI artifact with a SNAPSHOT_READ/SNAPSHOT_QUERY handler kind) — "
            "compile and assemble the inspection domain before inspecting"
        )

    ordered = dict(sorted(
        operations.items(),
        key=lambda kv: (CATEGORIES.index(kv[1].category), kv[0]),
    ))
    snapshot.cache("__catalog__", ordered)
    return ordered
