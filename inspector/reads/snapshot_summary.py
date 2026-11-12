"""si.snapshot.summary — what this composition IS, at a glance.

Identity (`snapshot_id`), the composed domains with their compiler versions and declared reuse
visibility, and published counts by artifact kind. Every figure is read from the manifest and the
assembler's indexes; none is recounted here. Two components counting the same population
independently is how they come to disagree.

`reuse_visibility` is a declaration, not a figure — it is read from the domain's own build manifest
through the artifact index, the same way store declarations are read. It answers whether a domain's
artifacts may be offered as reuse candidates at all, which a change request's analysis phase must
know and must never infer: guessing relevance from structure is reserved to the author, never the
platform.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from inspector.snapshot import Snapshot


def _reuse_visibility(snapshot: Snapshot) -> dict[str, str]:
    """domain → declared reuse visibility, from each domain's own build manifest.

    A build manifest is the STRUCTURE that declares a `structure_scope`; every other STRUCTURE
    describes storage or discovery and declares no scope. The scope names the domain, so the
    mapping is read from the declaration rather than assembled from a path or a naming convention.
    """
    declared: dict[str, str] = {}
    for fqdn, entry in snapshot.entries().items():
        if entry.get("kind") != "STRUCTURE":
            continue
        artifact = snapshot.canonical(fqdn)
        frontmatter = (artifact or {}).get("frontmatter") or {}
        scope = frontmatter.get("structure_scope")
        if scope:
            declared[scope] = frontmatter.get("reuse_visibility")
    return declared


def snapshot_summary(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    manifest = snapshot.manifest()
    index = snapshot.artifact_index()
    entries = index["artifacts"]
    visibility = _reuse_visibility(snapshot)

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
                "reuse_visibility": visibility.get(d.get("domain")),
            }
            for d in manifest.get("domains", [])
        ],
        # Scope-keyed, not domain-keyed: substrate layers declare a visibility but are not
        # composed domains, so `domains[]` cannot carry the whole answer.
        "reuse_visibility": dict(sorted(visibility.items())),
        "artifact_count": index.get("artifact_count", len(entries)),
        "artifacts_by_kind": dict(sorted(by_kind.items())),
        "artifacts_by_namespace": dict(sorted(by_domain.items())),
        "store_count": snapshot.store_index().get("store_count", 0),
        "workflow_count": len(snapshot.kind_index().get("workflows", {})),
        "behavior_logic_count": len(snapshot.behavior_logic_workflows()),
    }
