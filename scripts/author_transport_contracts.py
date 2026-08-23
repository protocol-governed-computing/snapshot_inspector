#!/usr/bin/env python3
"""
Author the `inspection::` TI/TE boundary contracts for the `si.` operation family.

This script is an **authoring aid**, not a runtime authority. It writes the `.md` artifacts; the
compiler seals them into the snapshot; and `inspector.catalog` reads the compiled contracts as the
single source of what operations exist. Nothing consults this file at run time — delete it and the
inspector keeps working from the artifacts, which is the point.

Each operation is declared ONCE here, completely: kind, presentation, parameters and their types,
the implementation that answers it, and the fields it exposes. The TI and TE are projections of
that declaration.

The implementation is named by referencing the function object itself, so the `{module, callable}`
written into the artifact cannot be a typo — and `inspector.registry` must import that same
function or resolution fails hard at read time.

The exposed field list is declared, never derived from a live answer: a TE states what the boundary
EXPOSES, and a contract read off the implementation could never disagree with it.

Re-run after changing any declaration below:

    PYTHONPATH=. python3 scripts/author_transport_contracts.py
    protocol_compiler/compile_domain.sh <workspace>/snapshot_inspector

`--check` reports whether the contracts on disk still agree with these declarations and writes
nothing, exiting 1 if any differ. It exists because a generated artifact can be edited by hand and
nothing notices: `TI_SI_STORE_LIST_V0`'s catalog summary was improved in the artifact and not in the
declaration here, and the drift surfaced only when someone happened to regenerate — by which point
the better wording had been silently overwritten. A generator with no agreement check is a generator
whose output is only as current as the last person who remembered to run it.

An unrecognised argument stops the run rather than falling through, because the default action
writes and a flag whose whole meaning is "do nothing yet" must never be the thing that overwrites.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from inspector.queries.artifact_refs import artifact_refs
from inspector.queries.snapshot_validate import snapshot_validate
from inspector.queries.topology_impact import topology_impact
from inspector.reads.artifact_indexed import artifact_indexed
from inspector.reads.artifact_list import artifact_list
from inspector.reads.artifact_show import artifact_show
from inspector.reads.behavior_logic_list import behavior_logic_list
from inspector.reads.rule_set_list import rule_set_list
from inspector.reads.behavior_logic_show import behavior_logic_show
from inspector.reads.capability_surface import capability_surface
from inspector.reads.catalog import catalog
from inspector.reads.snapshot_summary import snapshot_summary
from inspector.reads.snapshot_topology import snapshot_topology
from inspector.reads.store_reads import store_consumers, store_list, store_show
from inspector.reads.vocab_resolve import vocab_resolve
from inspector.reads.vocab_search import vocab_search
from inspector.kinds import SNAPSHOT_QUERY, SNAPSHOT_READ
from inspector.registry import IMPLEMENTATIONS, implementation_ref

TRANSPORT_DIR = Path(__file__).resolve().parent.parent / "transport"

STRING = "string"
BOOLEAN = "boolean"


@dataclass(frozen=True)
class Spec:
    kind: str
    category: str
    label: str
    summary: str
    handler: object                              # the function; its module/name go in the artifact
    exposes: list[str]                           # fields that cross the boundary on SUCCESS
    params: dict[str, tuple[str, bool]] = field(default_factory=dict)   # name → (type, required)


SPECS: dict[str, Spec] = {
    # ── SNAPSHOT ──────────────────────────────────────────────────
    "si.catalog": Spec(
        SNAPSHOT_READ, "SNAPSHOT", "Catalog",
        "Every inspection operation this snapshot inspector answers.",
        catalog, ["operation_count", "categories", "operations"]),
    "si.snapshot.summary": Spec(
        SNAPSHOT_READ, "SNAPSHOT", "Summary",
        "Composition identity, domains, and published counts by kind.",
        snapshot_summary,
        # `reuse_visibility` is what P3 bounds a reuse search by — a domain declaring whether it may
        # be drawn on at all. It had been added to the TE by hand and was therefore dropped the
        # first time this script regenerated the contracts: a generated artifact edited in place is
        # a change waiting to be reverted, so the declaration lives here.
        ["snapshot_id", "manifest_version", "domains", "reuse_visibility", "artifact_count",
         "artifacts_by_kind", "artifacts_by_namespace", "store_count", "workflow_count",
         "behavior_logic_count"]),
    "si.snapshot.topology": Spec(
        SNAPSHOT_READ, "SNAPSHOT", "Topology",
        "Domain → subdomain → workflow map of the composition.",
        snapshot_topology, ["snapshot_id", "domains", "workflow_count", "topology"]),
    "si.snapshot.validate": Spec(
        SNAPSHOT_QUERY, "SNAPSHOT", "Validate",
        "Integrity and closure of the assembled snapshot; every check reports what it examined.",
        snapshot_validate,
        ["snapshot_id", "strict", "valid", "check_count", "failed_checks", "advisory_checks",
         "checks"],
        {"strict": (BOOLEAN, False)}),

    # ── ARTIFACTS ─────────────────────────────────────────────────
    "si.artifact.list": Spec(
        SNAPSHOT_READ, "ARTIFACTS", "List",
        "The artifact catalog, optionally narrowed by kind or namespace.",
        artifact_list, ["filter", "artifact_count", "artifacts"],
        {"kind": (STRING, False), "domain": (STRING, False)}),
    "si.artifact.show": Spec(
        SNAPSHOT_READ, "ARTIFACTS", "Show",
        "The published canonical artifact for an FQDN, as authored.",
        artifact_show,
        ["artifact", "kind", "domain", "owner_subdomain", "canonical_path", "addresses",
         "canonical"],
        {"artifact": (STRING, True)}),
    "si.artifact.indexed": Spec(
        SNAPSHOT_READ, "ARTIFACTS", "Indexed",
        "Whether an FQDN is carried by this composition's artifact index.",
        artifact_indexed, ["artifact", "indexed", "kind", "domain"],
        {"artifact": (STRING, True)}),
    "si.artifact.refs": Spec(
        SNAPSHOT_QUERY, "ARTIFACTS", "References",
        "Consumers (incoming edges) and dependencies (outgoing edges), direct or transitive.",
        artifact_refs,
        ["artifact", "kind", "transitive", "traversable", "ref_count", "dep_count", "refs",
         "deps"],
        {"artifact": (STRING, True), "transitive": (BOOLEAN, False)}),
    "si.topology.impact": Spec(
        SNAPSHOT_QUERY, "ARTIFACTS", "Impact",
        "Transitive consumer closure — what a change to this artifact reaches.",
        topology_impact,
        ["artifact", "kind", "traversable", "impacted_count", "impacted_namespaces", "impact"],
        {"artifact": (STRING, True)}),

    # ── STORES ────────────────────────────────────────────────────
    "si.store.list": Spec(
        SNAPSHOT_READ, "STORES", "List",
        "Every declared store with its owning STRUCTURE, path, and the bindings that reach it.",
        store_list, ["filter", "store_count", "stores"],
        {"domain": (STRING, False)}),
    "si.store.show": Spec(
        SNAPSHOT_READ, "STORES", "Show",
        "One store's declarations and their full binding surface.",
        store_show, ["key", "store", "domain", "declarations"],
        {"store": (STRING, True)}),
    "si.store.consumers": Spec(
        SNAPSHOT_READ, "STORES", "Consumers",
        "Which workflows and capability contracts reach a store, and through which binding.",
        store_consumers, ["key", "store", "domain", "workflows", "consumer_ccs", "bindings"],
        {"store": (STRING, True)}),

    # ── CAPABILITIES ──────────────────────────────────────────────
    "si.capability.surface": Spec(
        SNAPSHOT_READ, "STORES", "Capability surface",
        "Each capability side effect's operations and the fields they declare they yield.",
        capability_surface, ["filter", "capability_count", "capabilities"],
        {"capability": (STRING, False)}),

    # ── VOCABULARY ────────────────────────────────────────────────
    "si.vocab.search": Spec(
        SNAPSHOT_READ, "VOCABULARY", "Search",
        "Semantic-vocabulary identities matching a term, with their per-domain addresses.",
        vocab_search, ["term", "match_count", "matches"],
        {"term": (STRING, True)}),
    "si.vocab.resolve": Spec(
        SNAPSHOT_READ, "VOCABULARY", "Resolve",
        "Identity → per-domain addresses, or an address within one domain → identity.",
        vocab_resolve, ["identity", "addresses", "indexed", "kind"],
        {"artifact": (STRING, False), "address": (STRING, False), "domain": (STRING, False)}),

    # ── BEHAVIOR ──────────────────────────────────────────────────
    "si.rule_set.list": Spec(
        SNAPSHOT_READ, "ARTIFACTS", "Rule sets",
        "Every artifact carrying a sealed rule set, and the rule identifiers it declares.",
        rule_set_list, ["artifact", "carrier_count", "carriers"],
        {"artifact": (STRING, False)}),
    "si.behavior_logic.list": Spec(
        SNAPSHOT_READ, "BEHAVIOR", "Workflows",
        "Every workflow carrying a published behavior-logic graph.",
        behavior_logic_list, ["workflow_count", "workflows"]),
    "si.behavior_logic.show": Spec(
        SNAPSHOT_READ, "BEHAVIOR", "Logic Graph",
        "One workflow's compiled execution graph and its rendered projection.",
        behavior_logic_show, ["wf", "domain", "graph", "graph_path", "projection_path"],
        {"wf": (STRING, True)}),
}


def artifact_code(operation: str, side: str) -> str:
    """`si.artifact.show` → `TI_SI_ARTIFACT_SHOW_V0`."""
    return f"{side}_" + operation.replace(".", "_").upper() + "_V0"


def ti_markdown(operation: str, spec: Spec) -> str:
    if spec.params:
        contract_lines = []
        for param, (param_type, required) in spec.params.items():
            contract_lines.append(f"  {param}:")
            contract_lines.append(f"    type: {param_type}")
            contract_lines.append(f"    required: {'true' if required else 'false'}")
        input_contract = "\n".join(contract_lines)
    else:
        input_contract = "  {}"

    template = "\n".join(
        f'    {param}: "${{input.{param}}}"' for param in spec.params
    ) or "    {}"

    module, callable_name = implementation_ref(spec.handler).split(":")

    return f"""# {artifact_code(operation, 'TI')}

**Kind:** Transport Ingress Contract (Transport Standard V0 §6)
**Operation Identity:** `{operation}`

Declares `{operation}` in full: what it admits, how it is presented, and which implementation
answers it. This artifact is the **authority** — `inspector.catalog` reads the operation set from
the compiled contracts, and `inspector.registry` holds implementations and no metadata. Adding,
renaming or re-pointing an operation is an authoring act here, sealed into the snapshot and
attested; it cannot happen silently in code.

`handler.kind: {spec.kind}` selects the inspector's static entry point rather than the runtime's.
The engine routes by KIND and stops there — the inspector resolves the declared implementation
internally. No resolver or adapter code interprets the operation string; one that did would be a
hidden RPC router.

`handler.implementation` is the same binding a capability transform declares: the artifact names
`{{module, callable}}` and the inspector resolves it against a closed, statically imported
registry. An implementation the registry does not import cannot be named here.

Each `si.` operation carries its own TI/TE pair. The family shares one HTTP route, but sharing a
route is a protocol convenience; sharing a governed identity would leave the boundary unable to
admit one operation and refuse another.

## Machine

```yaml
fqdn: inspection::{artifact_code(operation, 'TI')}
artifact_kind: TRANSPORT_INGRESS
version: v0
governed_by: transport::CONSTITUTION_TRANSPORT_INGRESS_V0
authority: pgc.platform
concern: inspection
operation: {operation}

# Input contract — declared and enforced at the boundary before the handler is reached.
# A parameter declared `type: boolean` is what a client renders as a switch; `flags` is derived
# from the contract, never stated twice.
input_contract:
{input_contract}

# Presentation — the published catalog a client builds its menu from.
catalog:
  category: {spec.category}
  label: {spec.label}
  summary: {spec.summary}

# Context requirements — inert in V0 (AC reserved).
context_requirements: []

handler:
  kind: {spec.kind}
  operation: {operation}
  implementation:
    module: {module}
    callable: {callable_name}
  payload_template:
{template}
```
"""


def te_markdown(operation: str, spec: Spec) -> str:
    width = max(len(f) for f in spec.exposes)
    output_contract = "\n".join(
        f"- {{ field: {f.ljust(width)}, from: surface.{f} }}" for f in spec.exposes
    )
    nature = (
        "This operation DERIVES its result by traversing snapshot state (`SNAPSHOT_QUERY`)."
        if spec.kind == SNAPSHOT_QUERY else
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
governed_by: transport::CONSTITUTION_TRANSPORT_EGRESS_V0
authority: pgc.platform
concern: inspection
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


def rendered() -> dict[Path, str]:
    """Every contract this declaration produces, as path → text. Written by both callers."""
    out: dict[Path, str] = {}
    for operation, spec in sorted(SPECS.items()):
        for side, render in (("TI", ti_markdown), ("TE", te_markdown)):
            out[TRANSPORT_DIR / f"{artifact_code(operation, side)}.md"] = render(operation, spec)
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in argv
    unknown = [a for a in argv if a != "--check"]
    if unknown:
        print(__doc__.strip())
        print(f"\nunrecognised argument(s): {' '.join(unknown)}", file=sys.stderr)
        return 2

    # Every declared implementation must be one the registry imports — the artifact may only name
    # code that can actually be resolved when the contract is read back.
    unregistered = sorted(
        operation for operation, spec in SPECS.items()
        if implementation_ref(spec.handler) not in IMPLEMENTATIONS
    )
    if unregistered:
        print(f"implementation not registered in inspector.registry: {unregistered}",
              file=sys.stderr)
        return 1

    unused = sorted(set(IMPLEMENTATIONS) - {implementation_ref(s.handler) for s in SPECS.values()})
    if unused:
        print(f"registered implementation named by no operation: {unused}", file=sys.stderr)
        return 1

    contracts = rendered()

    if check_only:
        on_disk = {p for p in TRANSPORT_DIR.glob("T[IE]_*.md")}
        # Three ways to disagree, and they are named apart because they are fixed differently: a
        # contract edited by hand, one for an operation no longer declared, and one never written.
        drifted = sorted(p.name for p, text in contracts.items()
                         if not p.is_file() or p.read_text(encoding="utf-8") != text)
        orphaned = sorted(p.name for p in on_disk - set(contracts))
        for name in drifted:
            print(f"  DRIFTED  {name}")
        for name in orphaned:
            print(f"  ORPHANED {name}  — declared by no operation")
        if drifted or orphaned:
            print(f"\n{len(drifted) + len(orphaned)} contract(s) do not agree with the "
                  f"declaration that produces them.")
            return 1
        print(f"  OK       {len(contracts)} contract(s) for {len(SPECS)} operations agree")
        return 0

    TRANSPORT_DIR.mkdir(parents=True, exist_ok=True)
    for existing in TRANSPORT_DIR.glob("T[IE]_*.md"):
        existing.unlink()   # a removed operation must lose its contracts, not leave them orphaned

    for path, text in contracts.items():
        path.write_text(text, encoding="utf-8")
    print(f"authored {len(contracts)} boundary contracts for {len(SPECS)} operations "
          f"→ {TRANSPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
