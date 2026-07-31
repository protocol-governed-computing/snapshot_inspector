"""si.artifact.list — the composition's artifact catalog, optionally narrowed.

Projects the assembler's artifact index. Filters (`kind`, `domain`) SELECT over published entries;
they never derive anything. An empty result for a well-formed filter is SUCCESS with zero
artifacts — "nothing matched" is an answer, not a missing artifact. NOT_FOUND is reserved for a
filter value the composition does not contain at all, so a typo'd kind cannot masquerade as an
empty catalog.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def artifact_list(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    entries = snapshot.entries()
    kind = params.get("kind")
    domain = params.get("domain")

    known_kinds = {e.get("kind") for e in entries.values()}
    known_domains = {e.get("domain") for e in entries.values()}
    if kind is not None and kind not in known_kinds:
        return "NOT_FOUND", {
            "reason": f"no artifact of kind {kind!r} in this composition",
            "known_kinds": sorted(k for k in known_kinds if k),
        }
    if domain is not None and domain not in known_domains:
        return "NOT_FOUND", {
            "reason": f"no artifact in namespace {domain!r} in this composition",
            "known_domains": sorted(d for d in known_domains if d),
        }

    selected = {
        fqdn: entry
        for fqdn, entry in sorted(entries.items())
        if (kind is None or entry.get("kind") == kind)
        and (domain is None or entry.get("domain") == domain)
    }
    return "SUCCESS", {
        "filter": {"kind": kind, "domain": domain},
        "artifact_count": len(selected),
        "artifacts": [
            {
                "artifact": fqdn,
                "kind": entry.get("kind"),
                "domain": entry.get("domain"),
                "owner_subdomain": entry.get("owner_subdomain"),
                "canonical_path": entry.get("canonical_path"),
            }
            for fqdn, entry in selected.items()
        ],
    }
