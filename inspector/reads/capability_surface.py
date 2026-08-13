"""si.capability.surface — what each capability declares it accepts and yields.

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
                    # Whether the operation changes what it addresses. Published because a consumer
                    # holding a reach to read-only cannot do it otherwise: the name is inference and
                    # `idempotent` answers a different question — a last-write-wins write is
                    # idempotent. Absent rather than defaulted where a capability has not declared
                    # it, so an unstated effect is visibly unstated.
                    "effect": spec.get("effect"),
                    "input": list(spec.get("input") or []),
                    "output": list(spec.get("output") or []),
                    "result_status_values": list(spec.get("result_status_values") or []),
                }
                for op, spec in sorted(operations.items())
            },
        }

    # A capability transform is a capability. The surface published side effects only, which left
    # every consumer unable to ask what a transform accepts — and a design compiler that cannot ask
    # cannot hold a composition step to the transform it names. Published under its own key so the
    # side-effect surface, and the egress contract that enumerates it, are unchanged.
    transforms: dict[str, Any] = {}
    for fqdn, entry in sorted(entries.items()):
        if entry.get("kind") != "CT":
            continue
        core = ((snapshot.canonical(fqdn) or {}).get("frontmatter") or {}).get("core") or {}
        transforms[fqdn] = {
            "transform": fqdn,
            "inputs": {
                name: {"type": spec.get("type"), "required": bool(spec.get("required"))}
                for name, spec in sorted((core.get("inputs") or {}).items())
            },
            "outputs": sorted((core.get("outputs") or {})),
        }

    # A capability contract is a capability, and the same gap one level up. A design that reuses a
    # contract from another subdomain declares no interface for it — the contract already exists, so
    # there is nothing to restate — which left every consumer unable to ask what that contract
    # requires. A workflow consequently handed a reused contract nothing, three times in one change,
    # and each time the omission surfaced only when the act ran and the contract received nulls.
    #
    # Published under its own key, for the reason transforms are: the side-effect surface and the
    # egress contract that enumerates it stay as they are.
    contracts: dict[str, Any] = {}
    for fqdn, entry in sorted(entries.items()):
        if entry.get("kind") != "CC":
            continue
        core = ((snapshot.canonical(fqdn) or {}).get("frontmatter") or {}).get("core") or {}
        contracts[fqdn] = {
            "contract": fqdn,
            "inputs": {
                name: {"type": spec.get("type"), "required": bool(spec.get("required"))}
                for name, spec in sorted((core.get("inputs") or {}).items())
            },
            "outputs": sorted((core.get("outputs") or {})),
            # The pipeline as authored, not a judgement about it. A consumer asking whether a
            # contract writes reads each step's operation and looks its effect up on the capability
            # surface; summarising that here would be deriving a relationship, which is the other
            # query class's authority and not this one's.
            "steps": [
                {
                    "step": step.get("step"),
                    "side_effect": step.get("side_effect"),
                    "transform": step.get("transform"),
                    "op": step.get("op"),
                    "store": step.get("store"),
                }
                for step in (core.get("pipeline") or [])
                if isinstance(step, dict)
            ],
        }

    if capability is not None:
        if capability in contracts:
            return "SUCCESS", {
                "filter": {"capability": capability},
                "capability_count": 0,
                "capabilities": [],
                "transform_count": 0,
                "transforms": [],
                "contract_count": 1,
                "contracts": [contracts[capability]],
            }
        if capability in transforms:
            return "SUCCESS", {
                "filter": {"capability": capability},
                "capability_count": 0,
                "capabilities": [],
                "transform_count": 1,
                "transforms": [transforms[capability]],
                "contract_count": 0,
                "contracts": [],
            }
        if capability not in surfaces:
            return "NOT_FOUND", {
                "reason": f"no capability {capability!r} in this composition",
                "known_capabilities": sorted(surfaces) + sorted(transforms) + sorted(contracts),
            }
        surfaces = {capability: surfaces[capability]}

    return "SUCCESS", {
        "filter": {"capability": capability},
        "capability_count": len(surfaces),
        "capabilities": list(surfaces.values()),
        "transform_count": len(transforms),
        "transforms": list(transforms.values()),
        "contract_count": len(contracts),
        "contracts": list(contracts.values()),
    }
