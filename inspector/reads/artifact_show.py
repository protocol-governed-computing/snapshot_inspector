"""si.artifact.show — project the published canonical artifact for an FQDN.

Returns what the snapshot DECLARES about the artifact (its canonical form: identity, governance,
declared references/dependencies as authored). It does NOT compute consumer closures or impact —
derived relationships are Phase 2b (SNAPSHOT_QUERY).
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def artifact_show(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fqdn = str(params.get("artifact", ""))
    if "::" not in fqdn:
        return "NOT_FOUND", {"artifact": fqdn, "reason": "expected a <namespace>::<CODE> FQDN"}
    canonical = snapshot.canonical(fqdn)
    if canonical is None:
        return "NOT_FOUND", {"artifact": fqdn, "reason": "not present in snapshot"}
    entry = snapshot.entry(fqdn) or {}
    return "SUCCESS", {
        "artifact": fqdn,
        "kind": entry.get("kind"),
        "domain": entry.get("domain"),
        "owner_subdomain": entry.get("owner_subdomain"),
        "canonical_path": entry.get("canonical_path"),
        "addresses": entry.get("addresses", {}),
        "canonical": canonical,
    }
