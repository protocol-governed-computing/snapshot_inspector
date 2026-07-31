"""Read-only accessor over an assembled PGC snapshot (the assembler product).

Loads published material on demand; never writes. This is the ONE place the snapshot's on-disk
layout is encoded, so projections stay layout-agnostic:

    manifest.json                                  composition identity + provenance
    artifact_index/index.json                      FQDN → domain / kind / canonical_path / addresses
    kind_index/index.json                          by-kind cross-reference database
    store_index/index.json                         store → owner / declared path / binding surface
    canonical/<domain>/<kind>/*.json               the artifacts themselves
    vocabulary/<domain>/{forward,reverse}.json     address ↔ identity
    evidence/<domain>/evidence.json                the semantic graph (nodes + typed edges)
    behavior_logic/<domain>/<WF>/<WF>.graph.json   per-workflow execution graph (+ .projection.png)

**Artifacts are located through the artifact index, never by globbing a domain directory.** An
artifact's FQDN namespace is not its snapshot directory: `capability_side_effects::CS_MUTABLE_JSON_V0`
is published at `canonical/workload/capability_side_effects/…`. The index's `canonical_path` is the
authoritative locator — the assembler computes it, the inspector reads it. Deriving a path from a
namespace instead silently misses every `fb.*` and `capability_*` artifact (157 of 215 today).

Reads are memoized per instance: one `query()` builds one Snapshot, so a projection that consults
an index repeatedly still reads it once, and two queries never share stale state.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SnapshotError(RuntimeError):
    """The snapshot is absent or malformed — an internal error, never a NOT_FOUND result."""


class Snapshot:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        if not self.root.is_dir():
            raise SnapshotError(f"snapshot root is not a directory: {self.root}")
        self._cache: dict[str, Any] = {}

    # ── raw reads ────────────────────────────────────────────────

    def _read_json(self, rel: str) -> Any:
        if rel in self._cache:
            return self._cache[rel]
        path = self.root / rel
        if not path.is_file():
            raise SnapshotError(f"snapshot is missing {rel} (under {self.root})")
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SnapshotError(f"malformed JSON in {rel}: {exc}") from exc
        self._cache[rel] = content
        return content

    def has(self, rel: str) -> bool:
        return (self.root / rel).is_file()

    def cached(self, key: str) -> Any:
        """Whatever was memoized under `key` for this instance, or None."""
        return self._cache.get(key)

    def cache(self, key: str, value: Any) -> Any:
        """Memoize a derived read (e.g. the parsed operation catalog) for this instance."""
        self._cache[key] = value
        return value

    # ── composition ──────────────────────────────────────────────

    def manifest(self) -> dict[str, Any]:
        return self._read_json("manifest.json")

    def snapshot_id(self) -> str:
        return self.manifest().get("snapshot_id", "")

    def domains(self) -> list[str]:
        """Composed domains as the manifest declares them — the assembly unit, not the namespace."""
        return sorted(d["domain"] for d in self.manifest().get("domains", []))

    # ── indexes (built by the assembler over the composed snapshot) ──

    def artifact_index(self) -> dict[str, Any]:
        return self._read_json("artifact_index/index.json")

    def kind_index(self) -> dict[str, Any]:
        return self._read_json("kind_index/index.json")

    def store_index(self) -> dict[str, Any]:
        return self._read_json("store_index/index.json")

    def entries(self) -> dict[str, dict[str, Any]]:
        """FQDN → artifact index entry, for every artifact in the composition."""
        return self.artifact_index()["artifacts"]

    def entry(self, fqdn: str) -> dict[str, Any] | None:
        return self.entries().get(fqdn)

    # ── canonical artifacts ──────────────────────────────────────

    def canonical(self, fqdn: str) -> dict[str, Any] | None:
        """The published canonical artifact for an FQDN, located via the index. None if absent."""
        entry = self.entry(fqdn)
        if entry is None:
            return None
        rel = entry["canonical_path"]
        if not self.has(rel):
            raise SnapshotError(f"index names a canonical artifact that is not present: {rel}")
        return self._read_json(rel)

    def conformance(self) -> dict[str, Any] | None:
        """The composition-conformance verdict the assembler recorded, if the phase has run."""
        rel = "conformance/composition.json"
        return self._read_json(rel) if self.has(rel) else None

    # ── vocabulary ───────────────────────────────────────────────

    def vocabulary_domains(self) -> list[str]:
        root = self.root / "vocabulary"
        if not root.is_dir():
            return []
        return sorted(d.name for d in root.iterdir() if (d / "reverse.json").is_file())

    def vocabulary(self, domain: str) -> dict[str, dict[str, str]]:
        """{'forward': address → identity, 'reverse': identity → address} for one domain."""
        return {
            "forward": self._read_json(f"vocabulary/{domain}/forward.json"),
            "reverse": self._read_json(f"vocabulary/{domain}/reverse.json"),
        }

    # ── evidence (the semantic graph) ────────────────────────────

    def evidence_domains(self) -> list[str]:
        root = self.root / "evidence"
        if not root.is_dir():
            return []
        return sorted(d.name for d in root.iterdir() if (d / "evidence.json").is_file())

    def evidence(self, domain: str) -> dict[str, Any]:
        """One domain's SEMANTIC graph.

        `evidence.json`, never its sibling `evidence_graph.json` — that file is the compile trace
        (STAGE_SEQUENCE / CAUSALITY, keyed by event id) and carries no artifact-level edges.
        """
        return self._read_json(f"evidence/{domain}/evidence.json")

    # ── behavior logic ───────────────────────────────────────────

    def behavior_logic_workflows(self) -> list[tuple[str, str]]:
        """(domain, WF code) for every published behavior-logic graph."""
        root = self.root / "behavior_logic"
        if not root.is_dir():
            return []
        return sorted(
            (domain.name, wf.name)
            for domain in root.iterdir() if domain.is_dir()
            for wf in domain.iterdir()
            if wf.is_dir() and (wf / f"{wf.name}.graph.json").is_file()
        )

    def behavior_logic(self, domain: str, wf_code: str) -> dict[str, Any] | None:
        """One workflow's execution graph, plus the path of its rendered projection.

        The PNG is fetched directly (§3 rule 6: direct snapshot fetch is for binary assets only),
        so this returns its path rather than its bytes.
        """
        rel = f"behavior_logic/{domain}/{wf_code}/{wf_code}.graph.json"
        if not self.has(rel):
            return None
        png = f"behavior_logic/{domain}/{wf_code}/{wf_code}.projection.png"
        return {
            "graph": self._read_json(rel),
            "graph_path": rel,
            "projection_path": png if self.has(png) else None,
        }
