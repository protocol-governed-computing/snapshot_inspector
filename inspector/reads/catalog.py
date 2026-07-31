"""si.catalog — the inspection vocabulary itself: every operation this inspector answers.

A client needs to know what can be asked before it can ask anything. Publishing the catalog as an
operation means the menu a surface renders is DERIVED from the registry that answers it — a client
that hardcoded the list would hold a second copy of the registry, and the two would part company
the first time an operation was added or renamed.

It is a READ: the registry is published material, not a derivation over snapshot state. Note that
it is the one operation whose answer does not depend on the snapshot — the vocabulary is a property
of the inspector, not of what it is pointed at.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def catalog(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    from inspector.api import operations

    published = operations()
    return "SUCCESS", {
        "operation_count": len(published),
        "categories": sorted({op["category"] for op in published},
                             key=[op["category"] for op in published].index),
        "operations": published,
    }
