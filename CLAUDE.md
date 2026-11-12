# Protocol Inspector (PGC) — Architectural Rules

## What this repo is

The **read-only inspection authority** over assembled PGC snapshots. A first-class toolchain
component, symmetric with the compiler / assembler / runtime — each owns one phase of the
snapshot lifecycle:

```
protocol_compiler    source      → compiled projections
snapshot_assembler   projections → assembled snapshot
protocol_runtime     snapshot    → execution
snapshot_inspector   snapshot    → inspection      (this repo)
```

Import package (repo root on PYTHONPATH): `inspector`. Programmatic entry point:
`inspector.api.query(operation, params, snapshot_root) -> (status, payload)`.

## Core doctrine

- **Read-only.** Inspection never mutates and never executes. It reads the assembled snapshot
  (the assembler product) and returns projections/queries over it.
- **One input beyond the snapshot: a named trace.** `si.execution.explain` reads one run's trace
  through `inspector/trace.py`, under a trace root the caller provisions (`query(..., trace_root=)`;
  the transport passes its data root, the CLI `--trace-root` or `$PGC_DATA_ROOT`). The trace is
  named by the reference the runtime returned, never discovered, and confined to the root. The
  query refuses a trace that does not name the snapshot being read. Recorded facts and facts joined
  from the snapshot stay apart in the answer. No other operation reads a trace.
- **Consumer-neutral.** The transport `SNAPSHOT_READ`/`SNAPSHOT_QUERY` handlers are one consumer;
  a `si` CLI, CI gates (`validate`/`violations`), and change-management dossiers are others. The
  API makes NO web/transport assumptions.
- **Not the runtime.** Execution lives in `protocol_runtime`. This repo must never grow an
  execution path, and the runtime must never grow an inspection subsystem.
- **Governed identity dispatch.** `inspector.api.query` takes an **Operation Identity** and
  resolves it through the internal `registry.py` table. Callers never select a projection
  function directly. Transport passes the identity through; it does not dispatch.

## Two query classes

- **SNAPSHOT_READ (Phase 2a)** — retrieve/project **published** snapshot material (summary,
  artifact show/list, vocab, behavior_logic). No traversal, no evaluation, no derived
  relationships.
- **SNAPSHOT_QUERY (Phase 2b)** — **derive** a result by traversing/evaluating snapshot state
  (refs/deps/lineage, topology impact/path, validate/violations).

The distinction is load-bearing: Phase 2a must not compute semantic relationships client- or
server-side that belong to Phase 2b.

## Layout

```
inspector/
  api.py        query(operation, params, snapshot_root) -> (status, payload)   ← only entry point
                operations(snapshot_root) -> the published catalog; operation_kind() -> handler kind
  kinds.py      handler kinds + catalog categories (leaf module, imports nothing)
  catalog.py    reads the operation set from the snapshot's inspection:: TI artifacts
  registry.py   declared implementation reference → function. Holds NO operation metadata
  snapshot.py   read-only accessor; the ONE place the on-disk snapshot layout is encoded
  trace.py      reads one named trace under the trace root; refuses an untied or escaping one
  graph.py      federated semantic graph over evidence/*/evidence.json — traversal substrate
  reads/        Phase-2a read projections; signature (snapshot, params) -> (status, payload)
  queries/      Phase-2b derived queries; same signature, different authority
  cli.py        the `si` CLI — a CLIENT of api.query, generated from the catalog
scripts/testbed/test_inspector.py    behaviour contract — PYTHONPATH=. python3 …
```

## The protocol declares the operation set

**Which operations exist is declared by artifacts, not by code.** Each `inspection::` TI declares
its identity, handler kind, input contract, presentation, and — like a capability transform —
the `{module, callable}` that answers it. `inspector.catalog` reads that from the snapshot;
`inspector.registry` holds implementations and no metadata at all.

So adding, renaming, removing or re-pointing an operation is an authoring act on an artifact that
is compiled, sealed and attested — never an edit to a Python table. Two snapshots may legitimately
offer different operations, and an inspector answers what the snapshot in front of it declares.

The one thing deliberately NOT resolved from the snapshot is the dispatch table: implementations
are statically imported and explicitly enumerated, so a declared reference resolves by lookup and
never by dynamic import. `si.snapshot.validate` exists to diagnose a broken snapshot, and a
dispatcher that had to import modules named by possibly-broken artifacts would fail exactly when
it is needed. **The declaration is the authority; the resolution is incapable of surprises.**

## Clients carry no capability of their own

The CLI holds no per-operation code: commands, arguments and help are generated from the
snapshot's declared contracts. **Authoring a TI artifact is the only way to add a command.** Hand-written
commands accrete filters and joins the API does not have, and the client becomes a second
inspection engine with answers of its own. The same rule binds the browser surface (§7 of the
plan): render results, never derive relationships.

## Locating artifacts

**Resolve through `artifact_index/index.json`, never by deriving a path from an FQDN.** An
artifact's namespace is not its snapshot directory: `capability_side_effects::CS_MUTABLE_JSON_V0`
is published under `canonical/workload/…`. The index's `canonical_path` is authoritative — the
assembler computes it, the inspector reads it.

## Reading evidence

`evidence/<domain>/evidence.json` is the SEMANTIC graph (typed, FQDN-keyed edges). Its sibling
`evidence_graph.json` is the COMPILE TRACE (`STAGE_SEQUENCE` / `CAUSALITY`, keyed by event id) and
carries no artifact-level edges. Reading the wrong one yields an empty result, not an error.

## Status contract

`query` returns `(status, payload)`:
- `status ∈ {"SUCCESS", "NOT_FOUND"}` (mirrors `runtime.api.run_workflow`'s `(status, surface)`
  so boundaries treat execution and inspection uniformly).
- Raises on internal error (unregistered operation, malformed snapshot). Boundaries project a
  raise as their failure class.

## Import rules

Absolute, fully-qualified from `inspector.*`. No imports of `compiler.*`, `runtime.*`,
`structure.*`, `pgs_*`, or any domain. The inspector depends only on the snapshot's on-disk
format (an input contract), never on the tools that produced it.

## Environment

Do NOT `pip install` — dependencies are managed externally. Stdlib-only.

## Workflow rules

Diagnose → plan → approval before multi-file changes. Present the file list first.

## One-line summary

Read-only, consumer-neutral inspection over the assembled snapshot; governed Operation-Identity
dispatch; `SNAPSHOT_READ` projects published material, `SNAPSHOT_QUERY` derives governed queries.
Inspection is not execution.
