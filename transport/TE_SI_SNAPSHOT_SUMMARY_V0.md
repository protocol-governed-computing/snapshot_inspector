# TE_SI_SNAPSHOT_SUMMARY_V0

**Kind:** Transport Egress Contract (Transport Standard V0 §7)
**Operation Identity:** `si.snapshot.summary`

Classifies an inspection result into a protocol-neutral Result Class and declares the output
projection. It carries **no** protocol semantics — no HTTP status, no exit code
(`RESULT_CLASS_PROTOCOL_INDEPENDENCE`); the adapter alone projects a Result Class onto a wire
representation (`RESPONSE_PROJECTION_EXTERNAL`).

This operation projects PUBLISHED snapshot material (`SNAPSHOT_READ`).

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
fqdn: inspection::TE_SI_SNAPSHOT_SUMMARY_V0
artifact_kind: TRANSPORT_EGRESS
version: v0
governed_by: fb.transport::CONSTITUTION_TRANSPORT_EGRESS_V0
operation: si.snapshot.summary

result_classification:
  SUCCESS:   SUCCESS
  NOT_FOUND: NOT_FOUND
default_result_class: EXECUTION_FAILURE

output_contract:
- { field: snapshot_id           , from: surface.snapshot_id }
- { field: manifest_version      , from: surface.manifest_version }
- { field: domains               , from: surface.domains }
- { field: artifact_count        , from: surface.artifact_count }
- { field: artifacts_by_kind     , from: surface.artifacts_by_kind }
- { field: artifacts_by_namespace, from: surface.artifacts_by_namespace }
- { field: store_count           , from: surface.store_count }
- { field: workflow_count        , from: surface.workflow_count }
- { field: behavior_logic_count  , from: surface.behavior_logic_count }

evidence_policy: none
```
