"""si.artifact.indexed — is this FQDN carried by the composition's artifact index?

The primary consumer's `is_indexed` predicate. Membership is ALWAYS a SUCCESS answer, including
when the artifact is absent: "no, it is not indexed" is the result being asked for, not a failed
lookup. Returning NOT_FOUND here would force every caller to treat its own question as an error.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def artifact_indexed(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fqdn = str(params.get("artifact", ""))
    entry = snapshot.entry(fqdn)
    return "SUCCESS", {
        "artifact": fqdn,
        "indexed": entry is not None,
        "kind": entry.get("kind") if entry else None,
        "domain": entry.get("domain") if entry else None,
    }
