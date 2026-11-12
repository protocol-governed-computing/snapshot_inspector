"""si.vocab.resolve — resolve an identity to its per-domain semantic addresses, or an address back.

Each domain carries its OWN address space, so a shared artifact legitimately holds a different
address in each domain that sees it (`capability_side_effects::CS_MUTABLE_JSON_V0` is 0x0000 in
`workload`, 0x0001 in `platform`, 0x002C in `ai_governance`). Resolution is therefore always
per-domain; a single global address for an identity does not exist and must never be invented.

Accepts either direction — `artifact` (an identity) or `address` (with `domain`, since an address
means nothing outside its own space). Both are lookups in published tables: no derivation.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def vocab_resolve(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    identity = str(params.get("artifact", "")).strip()
    address = str(params.get("address", "")).strip()

    if identity:
        addresses = {
            domain: table
            for domain in snapshot.vocabulary_domains()
            if (table := snapshot.vocabulary(domain)["reverse"].get(identity)) is not None
        }
        if not addresses:
            return "NOT_FOUND", {"artifact": identity, "reason": "not present in any vocabulary"}
        entry = snapshot.entry(identity)
        return "SUCCESS", {
            "identity": identity,
            "addresses": dict(sorted(addresses.items())),
            "indexed": entry is not None,
            "kind": entry.get("kind") if entry else None,
        }

    if address:
        domain = str(params.get("domain", "")).strip()
        if not domain:
            return "NOT_FOUND", {
                "address": address,
                "reason": "an address resolves only within a domain's address space; "
                          "pass domain",
            }
        if domain not in snapshot.vocabulary_domains():
            return "NOT_FOUND", {
                "domain": domain,
                "reason": "no vocabulary for this domain",
                "known_domains": snapshot.vocabulary_domains(),
            }
        identity = snapshot.vocabulary(domain)["forward"].get(address)
        if identity is None:
            return "NOT_FOUND", {
                "address": address, "domain": domain,
                "reason": "no identity at this address in this domain",
            }
        entry = snapshot.entry(identity)
        return "SUCCESS", {
            "identity": identity,
            "addresses": {domain: address},
            "indexed": entry is not None,
            "kind": entry.get("kind") if entry else None,
        }

    return "NOT_FOUND", {"reason": "one of artifact (identity) or address is required"}
