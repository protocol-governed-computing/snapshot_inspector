"""inspector.api — the single programmatic entry point for snapshot inspection.

    query(operation, params, snapshot_root) -> (status, payload)
    operations()                            -> the published catalog of what can be asked

`status` ∈ {"SUCCESS", "NOT_FOUND"}; raises on internal error. This mirrors
`runtime.api.run_workflow`'s `(status, surface)` so any boundary (e.g. the transport
SNAPSHOT_READ handler) can treat execution and inspection uniformly.

Dispatch is INTERNAL (`registry.py`: Operation Identity → projection). Callers pass an Operation
Identity and never select a projection function directly — the same governed-identity discipline
the transport boundary uses.

A missing REQUIRED parameter is NOT_FOUND, not a raise: the caller asked a well-formed question
the snapshot cannot answer as posed. An UNREGISTERED operation raises, because no snapshot could
ever answer it — that is a caller defect, not a result.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from inspector.registry import OPERATIONS
from inspector.snapshot import Snapshot


def query(
    operation: str,
    params: dict[str, Any],
    snapshot_root: str | Path,
) -> tuple[str, dict[str, Any]]:
    """Answer an inspection Operation Identity over the assembled snapshot at `snapshot_root`."""
    op = OPERATIONS.get(operation)
    if op is None:
        raise KeyError(f"no inspection projection registered for operation {operation!r}")

    params = params or {}
    missing = [p for p in op.required if params.get(p) in (None, "")]
    if missing:
        return "NOT_FOUND", {
            "operation": operation,
            "reason": f"missing required parameter(s): {', '.join(missing)}",
            "params": list(op.params),
        }

    snapshot = Snapshot(Path(snapshot_root))
    return op.handler(snapshot, params)


def operation_kind(operation: str) -> str:
    """The handler kind (`SNAPSHOT_READ` / `SNAPSHOT_QUERY`) a boundary routes this operation by."""
    op = OPERATIONS.get(operation)
    if op is None:
        raise KeyError(f"no inspection projection registered for operation {operation!r}")
    return op.kind


def operations() -> list[dict[str, Any]]:
    """The inspection catalog — every operation, grouped-ready, in category then identity order.

    Published so a client's menu is DERIVED from what can actually be answered. The catalog is the
    registry; there is no second list to keep in step with it.
    """
    from inspector.registry import CATEGORIES

    order = {category: position for position, category in enumerate(CATEGORIES)}
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
        }
        for op in sorted(
            OPERATIONS.values(),
            key=lambda o: (order.get(o.category, len(order)), o.identity),
        )
    ]
