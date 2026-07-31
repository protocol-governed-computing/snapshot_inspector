#!/usr/bin/env python3
"""
Author the `inspection::` TI/TE boundary contracts for the `si.` operation family.

Fifteen sibling operations need fifteen TI/TE pairs — each a distinct governed identity, because
sharing one contract across a family would make the boundary unable to admit one operation and
refuse another (Plan §3 rule 2). Hand-authoring thirty near-identical artifacts would guarantee
drift between the contracts and the API they describe, so they are GENERATED from the registry
that is already the single declaration of each operation: its kind, its params, and which of them
are required.

The exposed field list per operation is the one thing the registry does not carry, so it is
declared here — deliberately, and not by inspecting a live answer. A TE's `output_contract` states
what the boundary EXPOSES; deriving it from whatever a handler happened to return would mean the
contract could never disagree with the implementation, which is the entire point of having one.

Re-run after adding an operation:  PYTHONPATH=. python3 scripts/author_transport_contracts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from inspector.registry import OPERATIONS, SNAPSHOT_QUERY

TRANSPORT_DIR = Path(__file__).resolve().parent.parent / "transport"

# What each operation exposes across the boundary on SUCCESS. Declared, not derived.
EXPOSED: dict[str, list[str]] = {
    "si.catalog": ["operation_count", "categories", "operations"],
    "si.snapshot.summary": [
        "snapshot_id", "manifest_version", "domains", "artifact_count",
        "artifacts_by_kind", "artifacts_by_namespace", "store_count",
        "workflow_count", "behavior_logic_count",
    ],
    "si.snapshot.topology": ["snapshot_id", "domains", "workflow_count", "topology"],
    "si.snapshot.validate": [
        "snapshot_id", "strict", "valid", "check_count", "failed_checks",
        "advisory_checks", "checks",
    ],
    "si.artifact.list": ["filter", "artifact_count", "artifacts"],
    "si.artifact.show": [
        "artifact", "kind", "domain", "owner_subdomain", "canonical_path",
        "addresses", "canonical",
    ],
    "si.artifact.indexed": ["artifact", "indexed", "kind", "domain"],
    "si.artifact.refs": [
        "artifact", "kind", "transitive", "traversable", "ref_count", "dep_count",
        "refs", "deps",
    ],
    "si.topology.impact": [
        "artifact", "kind", "traversable", "impacted_count", "impacted_namespaces", "impact",
    ],
    "si.store.list": ["filter", "store_count", "stores"],
    "si.store.show": ["key", "store", "domain", "declarations"],
    "si.store.consumers": ["key", "store", "domain", "workflows", "consumer_ccs", "bindings"],
    "si.vocab.search": ["term", "match_count", "matches"],
    "si.vocab.resolve": ["identity", "addresses", "indexed", "kind"],
    "si.behavior_logic.list": ["workflow_count", "workflows"],
    "si.behavior_logic.show": ["wf", "domain", "graph", "graph_path", "projection_path"],
}

# Declared parameter types. A param absent here is a string.
PARAM_TYPES = {"transitive": "boolean", "strict": "boolean"}


def artifact_code(operation: str, side: str) -> str:
    """`si.artifact.show` → `TI_SI_ARTIFACT_SHOW_V0`."""
    return f"{side}_" + operation.replace(".", "_").upper() + "_V0"


def ti_markdown(operation, op) -> str:
    contract_lines = []
    for param in op.params:
        contract_lines.append(f"  {param}:")
        contract_lines.append(f"    type: {PARAM_TYPES.get(param, 'string')}")
        contract_lines.append(f"    required: {'true' if param in op.required else 'false'}")
    input_contract = "\n".join(contract_lines) if contract_lines else "  {}"

    template = "\n".join(
        f'    {param}: "${{input.{param}}}"' for param in op.params
    ) or "    {}"

    return f"""# {artifact_code(operation, 'TI')}

**Kind:** Transport Ingress Contract (Transport Standard V0 §6)
**Operation Identity:** `{operation}`

Declares the admission semantics for `{operation}`: its input contract, the handler it binds to,
and how the canonical input maps onto that handler.

`handler.kind: {op.kind}` selects the inspector's static entry point rather than the runtime's.
The engine routes by KIND and stops there — the inspector resolves `handler.operation` through
its own internal registry. No resolver or adapter code interprets the operation string; one that
did would be a hidden RPC router.

Each `si.` operation carries its own TI/TE pair. The family shares one HTTP route, but sharing a
route is a protocol convenience; sharing a governed identity would leave the boundary unable to
admit one operation and refuse another.

## Machine

```yaml
fqdn: inspection::{artifact_code(operation, 'TI')}
artifact_kind: TRANSPORT_INGRESS
version: v0
governed_by: fb.transport::CONSTITUTION_TRANSPORT_INGRESS_V0
operation: {operation}

# Input contract — declared and enforced at the boundary before the handler is reached.
input_contract:
{input_contract}

# Context requirements — inert in V0 (AC reserved).
context_requirements: []

handler:
  kind: {op.kind}
  operation: {operation}
  payload_template:
{template}
```
"""


def te_markdown(operation, op) -> str:
    fields = EXPOSED[operation]
    width = max(len(f) for f in fields)
    output_contract = "\n".join(
        f"- {{ field: {f.ljust(width)}, from: surface.{f} }}" for f in fields
    )
    derived = op.kind == SNAPSHOT_QUERY
    nature = (
        "This operation DERIVES its result by traversing snapshot state (`SNAPSHOT_QUERY`)."
        if derived else
        "This operation projects PUBLISHED snapshot material (`SNAPSHOT_READ`)."
    )

    return f"""# {artifact_code(operation, 'TE')}

**Kind:** Transport Egress Contract (Transport Standard V0 §7)
**Operation Identity:** `{operation}`

Classifies an inspection result into a protocol-neutral Result Class and declares the output
projection. It carries **no** protocol semantics — no HTTP status, no exit code
(`RESULT_CLASS_PROTOCOL_INDEPENDENCE`); the adapter alone projects a Result Class onto a wire
representation (`RESPONSE_PROJECTION_EXTERNAL`).

{nature}

The inspector's `NOT_FOUND` is a *governed answer*, not a boundary failure: the request was
admitted and answered, and the subject it named does not exist. It is neither `VIOLATION`
(nothing was violated) nor `OPERATION_NOT_FOUND` (the identity resolved perfectly well).

`output_contract` enumerates every field that crosses the boundary. The enumeration IS the
contract — an inspection payload is never passed through wholesale, because a boundary exposing
whatever a handler happened to return would declare nothing.

Inspection executes nothing and so produces no trace: `evidence_policy: none`. Declaring
`reference_only` here would promise evidence that cannot exist.

## Machine

```yaml
fqdn: inspection::{artifact_code(operation, 'TE')}
artifact_kind: TRANSPORT_EGRESS
version: v0
governed_by: fb.transport::CONSTITUTION_TRANSPORT_EGRESS_V0
operation: {operation}

result_classification:
  SUCCESS:   SUCCESS
  NOT_FOUND: NOT_FOUND
default_result_class: EXECUTION_FAILURE

output_contract:
{output_contract}

evidence_policy: none
```
"""


def main() -> int:
    missing = sorted(set(OPERATIONS) - set(EXPOSED))
    if missing:
        print(f"no exposed-field declaration for: {missing}", file=sys.stderr)
        return 1
    extra = sorted(set(EXPOSED) - set(OPERATIONS))
    if extra:
        print(f"exposed-field declaration for unregistered operation: {extra}", file=sys.stderr)
        return 1

    TRANSPORT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for operation, op in sorted(OPERATIONS.items()):
        for side, render in (("TI", ti_markdown), ("TE", te_markdown)):
            path = TRANSPORT_DIR / f"{artifact_code(operation, side)}.md"
            path.write_text(render(operation, op), encoding="utf-8")
            written += 1
    print(f"authored {written} boundary contracts for {len(OPERATIONS)} operations → {TRANSPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
