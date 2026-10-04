"""si.behavior_logic.show — project one workflow's published execution graph.

Returns the compiled `<WF>.graph.json` (entry node, nodes with their CT/CS projections, edges with
their routing conditions, and the enumerated execution paths) exactly as published, plus the
relative path of the rendered PNG. The image itself is fetched directly as a binary asset (§3
rule 6) rather than inlined here.

The workflow is addressed by FQDN. Its behavior-logic directory is keyed by the SNAPSHOT DOMAIN,
which is not always the FQDN namespace, so the domain is resolved through the artifact index.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def behavior_logic_show(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fqdn = str(params.get("wf", "") or params.get("artifact", ""))
    if "::" not in fqdn:
        return "NOT_FOUND", {"wf": fqdn, "reason": "expected a <namespace>::<WF_CODE> FQDN"}
    code = fqdn.split("::", 1)[1]

    published = snapshot.behavior_logic_workflows()
    domain = next((d for d, wf in published if wf == code), None)
    if domain is None:
        return "NOT_FOUND", {
            "wf": fqdn,
            "reason": "no behavior logic published for this workflow",
            "published": [f"{d}/{wf}" for d, wf in published],
        }

    logic = snapshot.behavior_logic(domain, code)
    if logic is None:
        return "NOT_FOUND", {"wf": fqdn, "reason": "no behavior logic published for this workflow"}
    return "SUCCESS", {"wf": fqdn, "domain": domain, **logic}
