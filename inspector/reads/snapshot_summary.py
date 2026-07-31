"""si.snapshot.summary — what this composition IS, at a glance.

Identity (`snapshot_id`), the composed domains with their compiler versions, and published
counts by artifact kind. Every figure is read from the manifest and the assembler's indexes; none
is recounted here. Two components counting the same population independently is how they come to
disagree.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from inspector.snapshot import Snapshot


def snapshot_summary(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    manifest = snapshot.manifest()
    index = snapshot.artifact_index()
    entries = index["artifacts"]

    by_kind = Counter(e.get("kind") for e in entries.values())
    by_domain = Counter(e.get("domain") for e in entries.values())

    return "SUCCESS", {
        "snapshot_id": manifest.get("snapshot_id"),
        "manifest_version": manifest.get("manifest_version"),
        "domains": [
            {
                "domain": d.get("domain"),
                "compiler_version": d.get("compiler_version"),
                "graph_address_hash": d.get("graph_address_hash"),
            }
            for d in manifest.get("domains", [])
        ],
        "artifact_count": index.get("artifact_count", len(entries)),
        "artifacts_by_kind": dict(sorted(by_kind.items())),
        "artifacts_by_namespace": dict(sorted(by_domain.items())),
        "store_count": snapshot.store_index().get("store_count", 0),
        "workflow_count": len(snapshot.kind_index().get("workflows", {})),
        "behavior_logic_count": len(snapshot.behavior_logic_workflows()),
    }
