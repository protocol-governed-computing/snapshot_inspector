# Architecture — `snapshot_inspector`

This document describes what this repository is, what it owns, and what it must never do. It is
written to be read before any code, and assumes no prior familiarity with Protocol-Governed
Computing.

For the big picture — what PGC is and how the repositories compose — see
**https://github.com/protocol-governed-computing**.

---

## 1. What this repo is

This is how you **ask a sealed snapshot what it contains**. A snapshot is the immutable artefact a
PGC system is built into and executes from; this repository reads it and answers questions about it.

The unusual thing about it is what it refuses to be:

> Inspection is a **domain**, not a tool. Every question you may ask is a governed operation the
> snapshot itself declares — and answering it never runs anything.

A conventional inspector is a bag of scripts that grow whatever query someone needed that week. Here,
`si.artifact.show` and `si.store.consumers` are identities of the same standing as any business
operation, declared in artefacts, compiled, and sealed. Two snapshots may legitimately offer
different questions, and an inspector answers exactly what the snapshot in front of it declares.

**What this repo is not.** It is not the runtime, not a debugger, and not a place where an
undeclared question can be answered. It never mutates, never executes, and holds no capability the
snapshot did not publish.

## 2. Where it sits

```
   protocol_compiler    source      → compiled projections
   snapshot_assembler   projections → assembled snapshot
   protocol_runtime     snapshot    → execution
   snapshot_inspector   snapshot    → inspection      ← YOU ARE HERE

                        ┌────────────────────┐
                        │  sealed snapshot   │  read-only
                        └─────────┬──────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  inspector.api.query(...)  │  the ONE entry point
                    └─────────────┬──────────────┘
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
        `si` CLI          transport boundary        CI gates
                          (browser surface)       (validate / violations)
```

It is a **peer** of the compiler, assembler and runtime — one of four components, each owning one
phase of a snapshot's life. It is not a utility hanging off one of them.

## 3. The central idea: the snapshot declares what may be asked

The distinction that explains every design choice in this repository:

```
   AN INSPECTION TOOL                    THIS INSPECTOR

   commands live in code                 operations live in ARTEFACTS
        │                                     │
        │  a new question =                   │  a new question =
        │  a new function + a new             │  an authored contract, compiled,
        │  CLI flag + a new client            │  sealed and attested
        ▼                                     ▼
   the tool decides what is                the snapshot decides what is
   knowable, and drifts from               knowable, and cannot drift —
   the thing it inspects                   it IS the thing being inspected
```

Each inspection contract declares its identity, its handler kind, what inputs it admits, how the
answer is presented, and the implementation that answers it. The code holds implementations and
**no metadata at all**. Adding, renaming, removing or re-pointing an operation is therefore an
authoring act on a governed artefact — never an edit to a Python table.

### The one deliberate exception

Implementations are statically imported and explicitly enumerated. A declared reference resolves by
lookup, never by dynamic import — and this is on purpose:

> `si.snapshot.validate` exists to diagnose a **broken** snapshot. A dispatcher that had to import
> modules named by possibly-broken artefacts would fail exactly when it is needed.

**The declaration is the authority; the resolution is incapable of surprises.**

## 4. Two classes of question

The split is load-bearing, not cosmetic:

| kind | what it does | examples |
|---|---|---|
| `SNAPSHOT_READ` | **projects published material** — retrieves what is already there, with no traversal and no evaluation | artefact list/show, vocabulary, behaviour logic, capability surface, store list |
| `SNAPSHOT_QUERY` | **derives an answer** by traversing and evaluating snapshot state | references and dependencies, topology impact, snapshot validation |

A read that quietly computed a relationship would be a query wearing a read's clothes — cheaper to
call, and carrying an authority it never declared. Seventeen operations ship in this release,
fourteen reads and three queries.

## 5. What it owns, and what it must never do

**It owns:**

- **one entry point** — `query(operation, params, snapshot_root) → (status, payload)`, reached by
  every consumer without exception;
- **governed identity dispatch** — the caller names an operation; it never selects a projection
  function;
- **the on-disk snapshot format** — one module encodes the layout, and it is the only place that
  knows it;
- **a semantic graph** over the snapshot's evidence, as the substrate derived queries traverse.

**It must never:**

- **mutate or execute.** There is no write path and no execution path here, and the runtime must
  never grow an inspection subsystem in return.
- **assume a consumer.** The API makes no web, transport or terminal assumptions. The CLI, the
  browser surface and CI gates are peers, none privileged.
- **let a client hold a capability.** A hand-written command accretes filters and joins the API does
  not have, and the client quietly becomes a second inspection engine with answers of its own.
- **depend on the tools that produced the snapshot.** No compiler, runtime, or domain import. The
  on-disk format is the input contract; the producers are irrelevant.

### The constraint this repo exists to enforce

Without it, every consumer that wanted to know something about a build would reach into compiler
internals and read whatever it found. That is a dependency on *how the snapshot was made* rather than
*what the snapshot is* — and it breaks the moment the compiler changes. This repository is the
single legitimate reader.

## 6. How one question is answered

```
   caller names an OPERATION IDENTITY        e.g.  si.store.consumers
        │
        ▼
   catalog     is it declared by THIS snapshot?
        │            no → NOT_FOUND
        ▼
   contract    admit the params it declares
        │
        ▼
   registry    declared implementation reference → an imported function
        │                                          (lookup, never dynamic import)
        ▼
   snapshot    read-only accessor — the one place the layout is known
        │            reads project;  queries traverse the semantic graph
        ▼
   (status, payload)      status ∈ { SUCCESS, NOT_FOUND };
                          an internal fault raises, and the boundary classifies it
```

The status pair deliberately mirrors the runtime's, so a boundary treats execution and inspection
uniformly and needs no special case for either.

### Two places where the wrong answer looks fine

Both are realization hazards worth stating plainly, because neither announces itself:

1. **An artefact's namespace is not its directory.** A path derived from an identity will often be
   wrong. Resolution goes through the artefact index, whose recorded path is authoritative.
2. **The evidence file has a lookalike sibling.** One is the semantic graph of typed, identity-keyed
   edges; the other is the compile trace and carries no artefact-level edges. Reading the wrong one
   yields an **empty result, not an error** — a confident, well-formed, entirely wrong answer.

The second hazard is not hypothetical: a store-consumer query in an earlier release answered
"nothing uses this" for fourteen of fifteen stores, and every part of the system reported healthy.
An inspection answer that is empty and confident is the characteristic failure of this component.

## 7. Layout

```
inspector/
    api.py        query(...) — the only entry point; also publishes the catalog
    kinds.py      handler kinds and catalog categories (imports nothing)
    catalog.py    reads the declared operation set from the snapshot
    registry.py   declared reference → function. Holds no operation metadata
    snapshot.py   read-only accessor; the one place the on-disk layout is encoded
    graph.py      the semantic graph over evidence — traversal substrate for queries
    reads/        projections of published material
    queries/      derived queries — same signature, different authority
    cli.py        the `si` CLI: a client of the API, generated from the catalog

transport/        the inspection:: contracts — what may be asked, declared
registry/         this repo's own build structure — it compiles as a domain like any other
client/           the browser surface: renders results, derives nothing
doc/              the `si` command reference
```

## 8. The browser surface — try it without learning anything first

The fastest way to understand this repository is to open it. Two commands, no prior knowledge, no
configuration to write:

```bash
cd snapshot_inspector
./client/serve.sh                     # serves on http://localhost:8001
```

Open **http://localhost:8001** and click through to **Protocol Inspection**. You get a launcher of
inspection operations; choosing one opens an independent window beside it, so several answers stay
on screen at once. Operations that need an input ask for it; operations that need nothing answer
immediately.

Nothing else is required. The launcher points at the snapshot already assembled in the workspace; to
inspect a different one, set `PGC_SNAPSHOT_ROOT` before starting.

### What to look at, in the order that teaches the most

| try | and notice |
|---|---|
| **Snapshot → summary** | what a sealed composition actually contains — domains, counts, an identity hash |
| **Artifacts → list**, then **show** one | an artefact is a compiled, addressable object, not a file you found |
| **Artifacts → refs** | this one *derives* the relationship rather than retrieving it — a query, not a read |
| **Topology → impact** | what changing one artefact would reach |
| **Behaviour logic → show** | a compiled workflow, rendered as a graph. This is the picture of what executes |
| **Snapshot → validate** | the snapshot checking itself, each criterion reported separately |

### The part worth pausing on

The menu itself is not written anywhere in the web client. The page's first action is to ask the
boundary `si.catalog` and build the launcher from the answer:

```
   browser              ONE route, every operation:
      │                 POST /si  { "operation": "si.<…>", "params": { … } }
      ▼
   transport boundary   the namespace `si.` is an admission constraint,
      │                 not a switch the adapter branches on
      ▼
   inspector.api.query  each identity resolves against its own governed contract
      │
      ▼
   { outcome · result_class · result · evidence · errors }
```

So the surface **cannot offer an operation the snapshot does not declare**, and cannot fail to offer
one it does. Point it at a different snapshot and the menu changes by itself. Open your browser's
network tab while clicking: every window's content is one `POST /si`, and the client renders what
comes back without deriving anything from it.

The server prints, at startup, the snapshot identity and every operation it booted — including the
business operations served by the very same adapter. The boundary is read once at startup, so
**restart it after rebuilding a snapshot**.

## 9. Rules this repo enforces

1. **Read-only.** No mutation, no execution, in any code path.
2. **The snapshot declares the operation set.** Code holds implementations and no metadata.
3. **One entry point.** Every consumer goes through `query`; none selects an implementation.
4. **Resolution never uses dynamic import**, so a broken snapshot can still be diagnosed.
5. **Reads project; queries derive.** A read that computes a relationship is a defect.
6. **Clients carry no capability.** CLI commands and browser views are generated from declared
   contracts; a hand-written one is a violation.
7. **Artefacts are located through the index**, never by deriving a path from an identity.
8. **No import of the compiler, the runtime, or any domain.** The on-disk format is the contract.

## 10. How to know it works

```bash
export PGC_SNAPSHOT_ROOT=../snapshot
PYTHONPATH=. python3 -m inspector catalog           # what THIS snapshot declares
PYTHONPATH=. python3 -m inspector snapshot validate # does it hold together?
```

A good result has a specific shape. The catalog reports the same seventeen operations as there are
contracts in `transport/` — because both come from the same declarations, not because someone kept
them in step. `validate` reports its checks individually, separating failures from advisories,
rather than collapsing to a single pass/fail. And the check that matters most for this
component: **an answer that is empty is empty because the snapshot is, not because the reader looked
in the wrong place.** Cross-check one empty answer against the artefact it concerns before believing
it.

## 11. Where the architecture is explained

This document describes *this repository*. The architecture it realizes is developed in the papers
indexed at **https://github.com/protocol-governed-computing**:

- **A Conceptual Model** — the snapshot as the immutable admissibility boundary, and the evidence
  model this repository reads.
- **Realizing the Normative Platform and Its Governed Transformation** — the condition that a
  governed platform must *answer* about itself, and what it takes to make that answer trustworthy.
- **An Architecture for Deterministic Declarative Execution** — the execution phase this repository
  is deliberately not part of.
