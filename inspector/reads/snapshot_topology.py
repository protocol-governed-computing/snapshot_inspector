"""si.snapshot.topology — the domain → subdomain → workflow map of the composition.

Projects the assembler's kind index. Subdomain membership is the workflow's DECLARED `subdomain`
field, not an inference from naming: `workload::WF_COLLATZ_CONJECTURE_V0` belongs to subdomain
`collatz` because it says so. A workflow declaring no subdomain is reported under the empty key
rather than being assigned one.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def snapshot_topology(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    workflows = snapshot.kind_index().get("workflows", {})

    tree: dict[str, dict[str, list[dict[str, str]]]] = {}
    for fqdn, wf in sorted(workflows.items()):
        namespace = wf.get("namespace") or fqdn.split("::", 1)[0]
        subdomain = wf.get("subdomain") or ""
        tree.setdefault(namespace, {}).setdefault(subdomain, []).append({
            "wf": fqdn,
            "summary": wf.get("summary", ""),
            "start_node": wf.get("start_node", ""),
            "node_count": len(wf.get("nodes", {})),
        })

    return "SUCCESS", {
        "snapshot_id": snapshot.snapshot_id(),
        "domains": snapshot.domains(),
        "workflow_count": len(workflows),
        "topology": {
            namespace: dict(sorted(subdomains.items()))
            for namespace, subdomains in sorted(tree.items())
        },
    }
