"""si.store.list / si.store.show / si.store.consumers — storage ownership and its binding surface.

All three project the assembler's `store_index/index.json`, which already carries the join
(storage STRUCTURE → declared path → RB → CS → workflows → consumer CCs). Nothing is re-joined
here: the assembler computed it over the composition, and a second implementation of the same
join would eventually disagree about who owns a file.

A store is keyed `<domain>::<STORE_NAME>` and may carry SEVERAL declarations — one name can be
declared by more than one storage STRUCTURE, at the same path (a shared store) or at different
paths (per-subdomain stores sharing a name). Declarations are reported as the protocol states
them; none is elected the canonical one.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def _resolve(snapshot: Snapshot, name: str) -> tuple[str, dict[str, Any]] | None:
    """Find a store by full key, or by bare name when that is unambiguous."""
    stores = snapshot.store_index()["stores"]
    if name in stores:
        return name, stores[name]
    matches = [(key, store) for key, store in stores.items() if store["store"] == name]
    return matches[0] if len(matches) == 1 else None


def store_list(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    stores = snapshot.store_index()["stores"]
    domain = params.get("domain")
    known = {store["domain"] for store in stores.values()}
    if domain is not None and domain not in known:
        return "NOT_FOUND", {
            "reason": f"no store declared in domain {domain!r}",
            "known_domains": sorted(known),
        }
    selected = {k: s for k, s in stores.items() if domain is None or s["domain"] == domain}
    return "SUCCESS", {
        "filter": {"domain": domain},
        "store_count": len(selected),
        "stores": [
            {
                "key": key,
                "store": store["store"],
                "domain": store["domain"],
                "declaration_count": len(store["declarations"]),
                "paths": sorted({d["path"] for d in store["declarations"]}),
                "declared_by": sorted({d["declared_by"] for d in store["declarations"]}),
                "binding_count": sum(len(d["bindings"]) for d in store["declarations"]),
            }
            for key, store in sorted(selected.items())
        ],
    }


def store_show(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    name = str(params.get("store", ""))
    resolved = _resolve(snapshot, name)
    if resolved is None:
        return "NOT_FOUND", {
            "store": name,
            "reason": "no such store, or the bare name is declared in more than one domain",
            "known_stores": sorted(snapshot.store_index()["stores"]),
        }
    key, store = resolved
    return "SUCCESS", {"key": key, **store}


def store_consumers(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Which workflows and capability contracts reach this store, through which binding.

    A store with zero consumers is a SUCCESS answer, not an absence: a declared store that nothing
    writes is a real and reportable state — and one worth seeing.
    """
    name = str(params.get("store", ""))
    resolved = _resolve(snapshot, name)
    if resolved is None:
        return "NOT_FOUND", {
            "store": name,
            "reason": "no such store, or the bare name is declared in more than one domain",
            "known_stores": sorted(snapshot.store_index()["stores"]),
        }
    key, store = resolved

    workflows: set[str] = set()
    consumer_ccs: set[str] = set()
    bindings = []
    for declaration in store["declarations"]:
        for binding in declaration["bindings"]:
            workflows.update(binding["workflows"])
            consumer_ccs.update(binding["consumer_ccs"])
            bindings.append({**binding, "path": declaration["path"]})

    return "SUCCESS", {
        "key": key,
        "store": store["store"],
        "domain": store["domain"],
        "workflows": sorted(workflows),
        "consumer_ccs": sorted(consumer_ccs),
        "bindings": bindings,
    }
