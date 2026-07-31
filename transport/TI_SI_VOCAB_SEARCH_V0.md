# TI_SI_VOCAB_SEARCH_V0

**Kind:** Transport Ingress Contract (Transport Standard V0 §6)
**Operation Identity:** `si.vocab.search`

Declares `si.vocab.search` in full: what it admits, how it is presented, and which implementation
answers it. This artifact is the **authority** — `inspector.catalog` reads the operation set from
the compiled contracts, and `inspector.registry` holds implementations and no metadata. Adding,
renaming or re-pointing an operation is an authoring act here, sealed into the snapshot and
attested; it cannot happen silently in code.

`handler.kind: SNAPSHOT_READ` selects the inspector's static entry point rather than the runtime's.
The engine routes by KIND and stops there — the inspector resolves the declared implementation
internally. No resolver or adapter code interprets the operation string; one that did would be a
hidden RPC router.

`handler.implementation` is the same binding a capability transform declares: the artifact names
`{module, callable}` and the inspector resolves it against a closed, statically imported
registry. An implementation the registry does not import cannot be named here.

Each `si.` operation carries its own TI/TE pair. The family shares one HTTP route, but sharing a
route is a protocol convenience; sharing a governed identity would leave the boundary unable to
admit one operation and refuse another.

## Machine

```yaml
fqdn: inspection::TI_SI_VOCAB_SEARCH_V0
artifact_kind: TRANSPORT_INGRESS
version: v0
governed_by: fb.transport::CONSTITUTION_TRANSPORT_INGRESS_V0
operation: si.vocab.search

# Input contract — declared and enforced at the boundary before the handler is reached.
# A parameter declared `type: boolean` is what a client renders as a switch; `flags` is derived
# from the contract, never stated twice.
input_contract:
  term:
    type: string
    required: true

# Presentation — the published catalog a client builds its menu from.
catalog:
  category: VOCABULARY
  label: Search
  summary: Semantic-vocabulary identities matching a term, with their per-domain addresses.

# Context requirements — inert in V0 (AC reserved).
context_requirements: []

handler:
  kind: SNAPSHOT_READ
  operation: si.vocab.search
  implementation:
    module: inspector.reads.vocab_search
    callable: vocab_search
  payload_template:
    term: "${input.term}"
```
