"""si.catalog — the inspection vocabulary itself: every operation this snapshot declares.

A client needs to know what can be asked before it can ask anything. The catalog is read from the
snapshot's compiled `inspection::` TI artifacts, so a surface's menu and a CLI's commands are
generated from the same contracts that admit the requests. There is no second list anywhere.

It is a READ: the contracts are published snapshot material, not a derivation over snapshot state.
Unlike every other operation it describes the snapshot's *boundary* rather than its contents —
which is exactly why it can be answered before anything else is known.
"""
from __future__ import annotations

from typing import Any

from inspector.kinds import CATEGORIES
from inspector.snapshot import Snapshot


def catalog(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    from inspector.catalog import load_catalog

    operations = load_catalog(snapshot)
    published = [
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
        for op in operations.values()
    ]
    present = {op["category"] for op in published}
    return "SUCCESS", {
        "operation_count": len(published),
        "categories": [c for c in CATEGORIES if c in present],
        "operations": published,
    }
