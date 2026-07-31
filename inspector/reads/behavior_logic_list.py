"""si.behavior_logic.list — every workflow with a published behavior-logic graph.

Enumerates what is on disk under `behavior_logic/`, and marks whether each rendered projection is
present. A workflow can be composed without carrying a graph; the catalog says which, so the
surface can present the difference instead of failing on selection.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def behavior_logic_list(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    published = snapshot.behavior_logic_workflows()
    workflows = []
    for domain, code in published:
        logic = snapshot.behavior_logic(domain, code)
        graph = logic["graph"] if logic else {}
        workflows.append({
            "wf_code": code,
            "domain": domain,
            "entry": graph.get("entry", ""),
            "node_count": len(graph.get("nodes", [])),
            "path_count": len(graph.get("execution_paths", [])),
            "graph_path": logic["graph_path"] if logic else None,
            "projection_path": logic["projection_path"] if logic else None,
        })
    return "SUCCESS", {"workflow_count": len(workflows), "workflows": workflows}
