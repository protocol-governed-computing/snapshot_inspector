"""si.vocab.search — find semantic-vocabulary identities matching a term.

Searches every domain's published `reverse.json` (identity → address). Matching is a
case-insensitive substring test over the identity string: a SELECTION over published symbols, not
semantic resolution. The vocabulary carries more than artifacts — `edge_kind::*` and other symbol
categories share the address space — so results carry an `indexed` flag saying whether the symbol
is also a composed artifact.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def vocab_search(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    term = str(params.get("term", "")).strip()
    if not term:
        return "NOT_FOUND", {"term": term, "reason": "a search term is required"}
    needle = term.lower()

    hits: dict[str, dict[str, str]] = {}
    for domain in snapshot.vocabulary_domains():
        for identity, address in snapshot.vocabulary(domain)["reverse"].items():
            if needle in identity.lower():
                hits.setdefault(identity, {})[domain] = address

    entries = snapshot.entries()
    return "SUCCESS", {
        "term": term,
        "match_count": len(hits),
        "matches": [
            {
                "identity": identity,
                "addresses": dict(sorted(addresses.items())),
                "indexed": identity in entries,
                "kind": entries[identity]["kind"] if identity in entries else None,
            }
            for identity, addresses in sorted(hits.items())
        ],
    }
