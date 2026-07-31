# `si` — CLI Reference

Read-only inspection of an assembled PGC snapshot. Every command is generated from the operations
the **snapshot declares**, so this list is exactly what the snapshot in front of you offers —
nothing more, nothing less. Point `si` at a different snapshot and the available commands may
differ.

## Running it

```bash
cd snapshot_inspector
export PGC_SNAPSHOT_ROOT=../snapshot          # or pass --snapshot PATH per call
PYTHONPATH=. python3 -m inspector <group> <verb> [args]
```

Installed (`pip install -e .`), the same thing is just `si <group> <verb>`. Every example below
drops the `PYTHONPATH=. python3 -m inspector` prefix for readability.

**Snapshot resolution**, in order: `--snapshot PATH` → `$PGC_SNAPSHOT_ROOT` → `./snapshot`. The
only requirement is a `manifest.json` in that directory.

**Global flags**, valid before or after the verb:

| Flag | |
|---|---|
| `--snapshot PATH` | which snapshot to read |
| `--json` | emit the raw payload instead of the rendered view |

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | SUCCESS |
| `1` | NOT_FOUND — or a snapshot that failed `validate --strict` |
| `2` | usage error, or the snapshot could not be opened |

## The catalog

```bash
si operations              # the catalog, rendered as a menu
si catalog --json          # the same thing as a governed operation, with declared implementations
```

## Snapshot

```bash
si snapshot summary        # identity, domains, counts by kind
si snapshot topology       # domain → subdomain → workflow map
si snapshot validate       # integrity + closure; every check reports what it examined
si snapshot validate --strict     # advisories become failures — the CI gate form
```

`validate` reports **advisory** checks separately from failures. An advisory is a real
inconsistency that no rule currently forbids; it is always reported, but only `--strict` makes it
fail the command.

## Artifacts

```bash
si artifact list                                   # the whole catalog
si artifact list --kind WF                         # by kind
si artifact list --domain ai_governance            # by namespace
si artifact list --kind RB --json

si artifact show workload::WF_COLLATZ_CONJECTURE_V0
si artifact indexed workload::WF_COLLATZ_CONJECTURE_V0     # membership; absence is still exit 0

si artifact refs workload::CC_STORE_RESULTS_V0             # direct consumers + dependencies
si artifact refs capability_side_effects::CS_MUTABLE_JSON_V0 --transitive

si topology impact capability_side_effects::CS_MUTABLE_JSON_V0
```

`refs` reports **both** directions: `refs` are incoming edges (who consumes this), `deps` are
outgoing (what this depends on). `impact` is the transitive consumer closure — what a change to
this artifact would reach.

An FQDN is `<namespace>::<CODE>`. The namespace is not the snapshot directory:
`capability_side_effects::CS_MUTABLE_JSON_V0` is published under `canonical/workload/`. Always
address artifacts by FQDN and let the index resolve the path.

## Stores

```bash
si store list                          # every declared store, its owner and path
si store list --domain ai_governance
si store show LICENSE_REGISTRY         # bare name works when unambiguous
si store show ai_governance::LICENSE_REGISTRY
si store consumers LICENSE_REGISTRY    # which workflows and CCs reach it, through which binding
```

A store may carry several declarations — one name declared by more than one storage STRUCTURE, at
the same path (shared) or different paths (per-subdomain). All are reported; none is elected
canonical.

## Vocabulary

```bash
si vocab search collatz                                    # substring, case-insensitive
si vocab resolve --artifact workload::WF_COLLATZ_CONJECTURE_V0
si vocab resolve --address 0x0000 --domain workload        # an address needs its domain
```

Each domain owns its own address space, so one identity legitimately holds a different address per
domain. There is no global address, and `resolve` will not invent one.

## Behaviour logic

```bash
si behavior_logic list                                     # workflows carrying a published graph
si behavior_logic show workload::WF_COLLATZ_CONJECTURE_V0
```

`show` returns the compiled execution graph and the relative path of the rendered PNG. The image
is a binary asset — fetch it from the snapshot directly rather than through an operation.

## Recipes

Fail a build on an invalid snapshot:

```bash
si --snapshot ./snapshot snapshot validate --strict || exit 1
```

What breaks if I change this artifact:

```bash
si topology impact <FQDN> --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["impacted_count"])'
```

Which checks are merely advisory right now:

```bash
si snapshot validate --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["advisory_checks"])'
```

Every workflow in one namespace:

```bash
si artifact list --kind WF --domain ai_governance
```

Confirm a check is not vacuous — `examined` is reported per check precisely so a green result over
an empty set is visible:

```bash
si snapshot validate --json | grep -E '"check"|"examined"'
```

## Same operations over HTTP

The CLI and the browser surface are two clients of one API. Through the transport boundary the
identical operation is:

```bash
curl -s -X POST http://127.0.0.1:8001/si \
  -H 'Content-Type: application/json' \
  -d '{"operation":"si.artifact.show","params":{"artifact":"workload::WF_COLLATZ_CONJECTURE_V0"}}'
```

The response is a Canonical Transport Response — `{request_id, outcome, result_class, result,
evidence, errors}` — where the CLI prints the payload. The `result_class` there is the governed
class (`SUCCESS`, `NOT_FOUND`, `VIOLATION`, `OPERATION_NOT_FOUND`, `EXECUTION_FAILURE`); the CLI's
exit code is the same information projected onto a shell convention.

## Adding an operation

The CLI grows on its own. Four steps, no CLI edit and no engine change:

1. write the projection in `inspector/reads/` or `inspector/queries/`
2. add it to `_PROJECTIONS` in `inspector/registry.py` so an artifact may name it
3. declare the operation in `scripts/author_transport_contracts.py` — kind, presentation,
   parameters, implementation, exposed fields — then re-run that script
4. recompile the domain — `protocol_compiler/compile_domain.sh <workspace>/snapshot_inspector`

The command, its help text, and the surface's menu entry all follow from the compiled contract.
Step 4 is not optional: until the artifact is in the snapshot, the operation does not exist.
