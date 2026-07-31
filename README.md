# snapshot_inspector

**Read-only inspection over assembled PGC snapshots.** A first-class toolchain component,
symmetric with the compiler, assembler, and runtime — each owns one phase of the snapshot
lifecycle:

```
protocol_compiler    source      → compiled projections
snapshot_assembler   projections → assembled snapshot
protocol_runtime     snapshot    → execution
snapshot_inspector   snapshot    → inspection      (this repo)
```

It reads the **assembled snapshot** (the final product) and answers inspection queries over it.
It never mutates and never executes.

## Consumers

Inspection is consumer-neutral. `inspector.api.query(...)` serves:

- the **transport** `SNAPSHOT_READ` / `SNAPSHOT_QUERY` handlers (the Inspection Surface),
- the **`si` CLI**,
- **CI gates** (`validate` / `violations`),
- **change-management** dossiers (impact / refs / deps).

## API

```python
from inspector.api import query

status, payload = query(
    "si.artifact.show",
    {"artifact": "workload::WF_COLLATZ_CONJECTURE_V0"},
    snapshot_root="/path/to/snapshot",
)
# status ∈ {"SUCCESS", "NOT_FOUND"}
```

Callers pass an **Operation Identity**; the inspector resolves it internally (never an RPC of
projection functions). See `CLAUDE.md` for the architectural rules.

`operations(snapshot_root)` publishes the catalog — every operation with its handler kind,
category, parameters, summary and declared implementation. **It is read from the snapshot's
`inspection::` TI artifacts**, so a client's menu is what that snapshot offers, not what the code
privately believes. There is no second list anywhere.

## Operations

| Operation | Kind | Params | |
|---|---|---|---|
| `si.snapshot.summary` | READ | — | identity, domains, counts by kind |
| `si.snapshot.topology` | READ | — | domain → subdomain → workflow map |
| `si.snapshot.validate` | QUERY | `strict?` | integrity + closure; every check reports `examined` |
| `si.artifact.list` | READ | `kind?` `domain?` | the artifact catalog |
| `si.artifact.show` | READ | `artifact` | the published canonical artifact |
| `si.artifact.indexed` | READ | `artifact` | index membership (absence is SUCCESS) |
| `si.artifact.refs` | QUERY | `artifact` `transitive?` | consumers and dependencies |
| `si.topology.impact` | QUERY | `artifact` | transitive consumer closure |
| `si.store.list` | READ | `domain?` | declared stores, owners, paths |
| `si.store.show` | READ | `store` | one store's declarations and bindings |
| `si.store.consumers` | READ | `store` | workflows and CCs reaching a store |
| `si.vocab.search` | READ | `term` | matching vocabulary identities |
| `si.vocab.resolve` | READ | `artifact` \| `address`+`domain` | identity ↔ per-domain address |
| `si.behavior_logic.list` | READ | — | workflows carrying a published graph |
| `si.behavior_logic.show` | READ | `wf` | one workflow's execution graph |
| `si.catalog` | READ | — | every operation this inspector answers |

A missing **required** parameter returns `NOT_FOUND` — a well-formed question the snapshot cannot
answer as posed. An **unregistered operation raises**: no snapshot could ever answer it.

## Query classes

| Class | Meaning | Phase |
|---|---|---|
| `SNAPSHOT_READ` | project **published** snapshot material | 2a |
| `SNAPSHOT_QUERY` | **derive** a result by traversing/evaluating snapshot state | 2b |

## CLI

```bash
export PGC_SNAPSHOT_ROOT=../snapshot          # or pass --snapshot PATH

si operations                                  # the catalog
si snapshot summary
si artifact show workload::WF_COLLATZ_CONJECTURE_V0
si artifact refs capability_side_effects::CS_MUTABLE_JSON_V0 --transitive
si store consumers LICENSE_REGISTRY
si snapshot validate --strict                  # CI gate: exit 1 if invalid
si artifact list --kind RB --json
```

Every command is **generated from the catalog** — registering an operation is the only way to add
one, so the CLI can never answer something the API cannot. Snapshot resolution: `--snapshot`, then
`$PGC_SNAPSHOT_ROOT`, then `./snapshot`. Exit codes: `0` SUCCESS, `1` NOT_FOUND (or an invalid
snapshot under `--strict`), `2` usage or snapshot error. Stdlib argparse — nothing to install.

## Inspection Surface (browser)

```bash
client/serve.sh          # :8001 — needs an assembled snapshot
```

One of two out-of-box reference implementations. Collatz demonstrates that a governed workflow
**executes**; this demonstrates what a governed snapshot **contains**.

The surface opens on a launcher listing every operation, grouped by category — fetched via
`si.catalog`, so the menu is exactly what the boundary can answer. Choosing an entry opens an
independent window: concurrent (several of the same operation with different parameters is the
point), movable, click-to-raise, individually closable. Nothing is ever disabled or queued behind
another window.

Every window's content arrives from one `POST /si` carrying an Operation Identity. The client
selects, fetches, formats, filters and navigates; it derives **no** PGC relationship. Clicking an
FQDN opens a new governed request for it — navigation, not a closure the browser worked out.

## The `inspection::` tool domain

This repo also hosts the domain that declares the boundary: `registry/` (build config) and
`transport/` (32 TI/TE artifacts), compiled by `protocol_compiler/compile_domain.sh .` and
composed into the snapshot like any other domain. A **tool domain** declares capabilities *about*
a snapshot rather than within one; it consumes the assembled snapshot as the runtime does, which
makes it a peer of the runtime, not part of the normative platform.

**The contracts are the authority.** Each TI declares its operation's identity, kind, input
contract, presentation and — as a capability transform does — the `{module, callable}` that
answers it. `inspector.registry` holds implementations and no metadata; the operation set comes
from the snapshot.

`scripts/author_transport_contracts.py` is the authoring aid that writes the `.md` artifacts from
one complete declaration per operation. Nothing consults it at run time: delete it and the
inspector keeps working from the compiled contracts. Re-run it, then recompile the domain, after
changing any declaration.

## Run (standalone)

```bash
PYTHONPATH=. python3 -m inspector operations               # CLI without installing
PYTHONPATH=. python3 -c "from inspector.api import query; \
  print(query('si.artifact.show', {'artifact':'workload::WF_COLLATZ_CONJECTURE_V0'}, '../snapshot'))"

PYTHONPATH=. python3 scripts/testbed/test_inspector.py     # behaviour contract
```
