# TI_SI_TOPOLOGY_IMPACT_V0

**Kind:** Transport Ingress Contract (Transport Standard V0 §6)
**Operation Identity:** `si.topology.impact`

Declares the admission semantics for `si.topology.impact`: its input contract, the handler it binds to,
and how the canonical input maps onto that handler.

`handler.kind: SNAPSHOT_QUERY` selects the inspector's static entry point rather than the runtime's.
The engine routes by KIND and stops there — the inspector resolves `handler.operation` through
its own internal registry. No resolver or adapter code interprets the operation string; one that
did would be a hidden RPC router.

Each `si.` operation carries its own TI/TE pair. The family shares one HTTP route, but sharing a
route is a protocol convenience; sharing a governed identity would leave the boundary unable to
admit one operation and refuse another.

## Machine

```yaml
fqdn: inspection::TI_SI_TOPOLOGY_IMPACT_V0
artifact_kind: TRANSPORT_INGRESS
version: v0
governed_by: fb.transport::CONSTITUTION_TRANSPORT_INGRESS_V0
operation: si.topology.impact

# Input contract — declared and enforced at the boundary before the handler is reached.
input_contract:
  artifact:
    type: string
    required: true

# Context requirements — inert in V0 (AC reserved).
context_requirements: []

handler:
  kind: SNAPSHOT_QUERY
  operation: si.topology.impact
  payload_template:
    artifact: "${input.artifact}"
```
