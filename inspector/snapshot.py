"""Read-only accessor over an assembled PGC snapshot (the assembler product).

Loads published material on demand; never writes. This is the ONE place the snapshot's on-disk
layout (manifest, canonical/, vocabulary/, artifact_index/, kind_index/, behavior_logic/) is encoded,
so read projections stay layout-agnostic.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Snapshot:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _read_json(self, rel: str) -> Any:
        return json.loads((self.root / rel).read_text(encoding="utf-8"))

    def manifest(self) -> dict[str, Any]:
        return self._read_json("manifest.json")

    def canonical_artifact(self, domain: str, code: str) -> dict[str, Any] | None:
        """Return the canonical JSON for <domain>::<code>, or None if absent.

        Globs the domain's kind subdirectories (workflows/, intents/, events/, …) so callers
        need not know which kind an artifact is.
        """
        hits = sorted((self.root / "canonical" / domain).glob(f"*/{domain}__{code}.json"))
        if not hits:
            return None
        return json.loads(hits[0].read_text(encoding="utf-8"))
