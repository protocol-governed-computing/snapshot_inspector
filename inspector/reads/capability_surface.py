"""si.capability.surface — what each capability side effect's operations declare they yield.

A composition can only be checked against a capability's *declared* surface if that surface is
published. It was not, and a design consequently bound a step's output named `authorized` to a field
called `exists`: the operation it invoked never yields anything named `authorized`, and nothing in
the pipeline could say so. An unauthorized caller wrote to the catalog for as long as that held.

Projects the CS artifacts' own `core.operations` declarations. Derives nothing — the operation
names, their inputs, their outputs and their result statuses are read as authored, because a surface
inferred from behaviour could never contradict the behaviour it was inferred from.

One call returns every capability. A capability contract is a fixed pipeline with no iteration, so a
rule that had to ask per capability could not be expressed at all.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def capability_surface(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    entries = snapshot.entries()
    capability = params.get("capability")

    surfaces: dict[str, Any] = {}
    for fqdn, entry in sorted(entries.items()):
        if entry.get("kind") != "CS":
            continue
        canonical = snapshot.canonical(fqdn) or {}
        core = (canonical.get("frontmatter") or {}).get("core") or {}
        operations = core.get("operations") or {}
        surfaces[fqdn] = {
            "capability": fqdn,
            "category": core.get("category"),
            "operations": {
                op: {
                    "input": list(spec.get("input") or []),
                    "output": list(spec.get("output") or []),
                    "result_status_values": list(spec.get("result_status_values") or []),
                }
                for op, spec in sorted(operations.items())
            },
        }

    if capability is not None:
        if capability not in surfaces:
            return "NOT_FOUND", {
                "reason": f"no capability side effect {capability!r} in this composition",
                "known_capabilities": sorted(surfaces),
            }
        surfaces = {capability: surfaces[capability]}

    return "SUCCESS", {
        "filter": {"capability": capability},
        "capability_count": len(surfaces),
        "capabilities": list(surfaces.values()),
    }
