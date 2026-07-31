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

- the **transport** `SNAPSHOT_READ` / `SNAPSHOT_QUERY` handlers (the PI web surface),
- a future **`si` CLI**,
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

## Query classes

| Class | Meaning | Phase |
|---|---|---|
| `SNAPSHOT_READ` | project **published** snapshot material | 2a |
| `SNAPSHOT_QUERY` | **derive** a result by traversing/evaluating snapshot state | 2b |

## Run (standalone)

```bash
PYTHONPATH=. python3 -c "from inspector.api import query; \
  print(query('si.artifact.show', {'artifact':'workload::WF_COLLATZ_CONJECTURE_V0'}, '../snapshot'))"
```
