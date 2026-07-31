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
        return "NOT_FOUND", {"artifact": fqdn, "reason": "expected a <domain>::<CODE> FQDN"}
    domain, code = fqdn.split("::", 1)
    artifact = snapshot.canonical_artifact(domain, code)
    if artifact is None:
        return "NOT_FOUND", {"artifact": fqdn, "reason": "not present in snapshot"}
    return "SUCCESS", {"artifact": fqdn, "canonical": artifact}
