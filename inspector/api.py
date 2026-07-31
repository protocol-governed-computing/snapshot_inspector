"""inspector.api — the single programmatic entry point for snapshot inspection.

    query(operation, params, snapshot_root) -> (status, payload)

`status` ∈ {"SUCCESS", "NOT_FOUND"}; raises on internal error. This mirrors
`runtime.api.run_workflow`'s `(status, surface)` so any boundary (e.g. the transport
SNAPSHOT_READ handler) can treat execution and inspection uniformly.

Dispatch is INTERNAL (`registry.py`: Operation Identity → read projection). Callers pass an
Operation Identity and never select a projection function directly — the same governed-identity
discipline the transport boundary uses.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from inspector.registry import PROJECTIONS
from inspector.snapshot import Snapshot


def query(operation: str, params: dict[str, Any], snapshot_root: str | Path) -> tuple[str, dict[str, Any]]:
    """Answer an inspection Operation Identity over the assembled snapshot at `snapshot_root`."""
    projection = PROJECTIONS.get(operation)
    if projection is None:
        raise KeyError(f"no inspection projection registered for operation {operation!r}")
    snapshot = Snapshot(Path(snapshot_root))
    return projection(snapshot, params or {})
