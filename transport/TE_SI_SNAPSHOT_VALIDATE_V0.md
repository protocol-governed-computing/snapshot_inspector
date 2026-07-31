# TE_SI_SNAPSHOT_VALIDATE_V0

**Kind:** Transport Egress Contract (Transport Standard V0 §7)
**Operation Identity:** `si.snapshot.validate`

Classifies an inspection result into a protocol-neutral Result Class and declares the output
projection. It carries **no** protocol semantics — no HTTP status, no exit code
(`RESULT_CLASS_PROTOCOL_INDEPENDENCE`); the adapter alone projects a Result Class onto a wire
representation (`RESPONSE_PROJECTION_EXTERNAL`).

This operation DERIVES its result by traversing snapshot state (`SNAPSHOT_QUERY`).

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
fqdn: inspection::TE_SI_SNAPSHOT_VALIDATE_V0
artifact_kind: TRANSPORT_EGRESS
version: v0
governed_by: fb.transport::CONSTITUTION_TRANSPORT_EGRESS_V0
operation: si.snapshot.validate

result_classification:
  SUCCESS:   SUCCESS
  NOT_FOUND: NOT_FOUND
default_result_class: EXECUTION_FAILURE

output_contract:
- { field: snapshot_id    , from: surface.snapshot_id }
- { field: strict         , from: surface.strict }
- { field: valid          , from: surface.valid }
- { field: check_count    , from: surface.check_count }
- { field: failed_checks  , from: surface.failed_checks }
- { field: advisory_checks, from: surface.advisory_checks }
- { field: checks         , from: surface.checks }

evidence_policy: none
```
