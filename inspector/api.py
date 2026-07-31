"""inspector.api — the single programmatic entry point for snapshot inspection.

    query(operation, params, snapshot_root)  -> (status, payload)
    operations(snapshot_root)                -> the published catalog
    operation_kind(operation, snapshot_root) -> the handler kind a boundary routes it by

`status` ∈ {"SUCCESS", "NOT_FOUND"}; raises on internal error. This mirrors
`runtime.api.run_workflow`'s `(status, surface)` so any boundary (e.g. the transport
SNAPSHOT_READ handler) can treat execution and inspection uniformly.

**The snapshot declares the operation set.** Every operation, its accepted parameters, its handler
kind and the implementation that answers it are read from the snapshot's compiled `inspection::` TI
artifacts (`inspector.catalog`); `inspector.registry` supplies implementations and declares no
metadata. So an inspector pointed at a snapshot answers exactly what that snapshot declares — two
snapshots may legitimately offer different operations, and neither is what the code privately
believes.

A missing REQUIRED parameter is NOT_FOUND, not a raise: the caller asked a well-formed question the
snapshot cannot answer as posed. An operation the snapshot does not declare raises, because no
amount of parameters would make it answerable here — that is a caller defect, not a result.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from inspector.catalog import load_catalog
from inspector.kinds import CATEGORIES
from inspector.snapshot import Snapshot


def _resolve(operation: str, snapshot: Snapshot):
    catalog = load_catalog(snapshot)
    op = catalog.get(operation)
    if op is None:
        raise KeyError(
            f"snapshot at {snapshot.root} declares no inspection operation {operation!r}"
        )
    return op


def query(
    operation: str,
    params: dict[str, Any],
    snapshot_root: str | Path,
) -> tuple[str, dict[str, Any]]:
    """Answer an inspection Operation Identity over the assembled snapshot at `snapshot_root`."""
    snapshot = Snapshot(Path(snapshot_root))
    op = _resolve(operation, snapshot)

    params = params or {}
    missing = [p for p in op.required if params.get(p) in (None, "")]
    if missing:
        return "NOT_FOUND", {
            "operation": operation,
            "reason": f"missing required parameter(s): {', '.join(missing)}",
            "params": list(op.params),
        }

    return op.handler(snapshot, params)


def operation_kind(operation: str, snapshot_root: str | Path) -> str:
    """The handler kind (`SNAPSHOT_READ` / `SNAPSHOT_QUERY`) a boundary routes this operation by."""
    return _resolve(operation, Snapshot(Path(snapshot_root))).kind


def operations(snapshot_root: str | Path) -> list[dict[str, Any]]:
    """The inspection catalog — every operation the snapshot declares, in category then identity order.

    Published so a client's menu is what the SNAPSHOT offers. There is no second list: the CLI's
    commands and the surface's launcher are both built from this, and this is built from the
    compiled contracts.
    """
    snapshot = Snapshot(Path(snapshot_root))
    return [
        {
            "operation": op.identity,
            "kind": op.kind,
            "category": op.category,
            "label": op.label,
            "params": list(op.params),
            "required": list(op.required),
            "flags": list(op.flags),
            "summary": op.summary,
            "implementation": op.implementation,
        }
        for op in load_catalog(snapshot).values()
    ]


def categories() -> tuple[str, ...]:
    """The catalog groupings, in presentation order."""
    return CATEGORIES
