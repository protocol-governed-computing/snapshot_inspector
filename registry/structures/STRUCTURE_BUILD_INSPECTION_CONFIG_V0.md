# STRUCTURE_BUILD_INSPECTION_CONFIG_V0

**Artifact Type**: STRUCTURE
**Version**: V0
**Governed By**: structure::CONSTITUTION_STRUCTURE_V0

---

## Purpose

Self-describing build manifest for the **inspection** domain (`inspection::`) — the governed
boundary surface of the Protocol Inspection Surface.

This is a **tool domain**: it declares capabilities *about* a snapshot rather than business
capabilities *within* one. It consumes the assembled snapshot exactly as the runtime does, which
makes it a peer of the runtime, not part of the normative platform. Its artifacts are applications
of the governance language, never extensions of it, so they live here rather than in
`software_governance`.

The domain declares **only boundary contracts** — TI/TE pairs for the `si.` operation family. It
has no workflow, no capability contract and no runtime binding, because inspection does not
execute: an `si.` operation resolves through `handler.kind: SNAPSHOT_READ` / `SNAPSHOT_QUERY` to
the inspector's static entry point, never through the runtime scheduler. A tool domain is
therefore the first PGC domain whose artifact set is boundary-only.

The namespace is `inspection::` rather than one derived from this repository. A namespace names
the capability family, not the directory that happens to hold it — and PGC already publishes
artifacts whose namespace differs from their snapshot location, so a location-derived namespace
would become inaccurate the moment the surface moved.

---

## Machine

```yaml
fqdn: inspection::STRUCTURE_BUILD_INSPECTION_CONFIG_V0
artifact_kind: STRUCTURE
version: V0
governed_by: structure::CONSTITUTION_STRUCTURE_V0
authority: pgc.platform
concern: inspection
structure_scope: inspection
reuse_visibility: platform_service
core:
  summary: Build-time STRUCTURE manifest (inspection tool-domain scope)
  description: 'Compiles the inspection domain''s own boundary artifacts (TI/TE), resolving
    governance references against the imported compiled platform surface. Emits only inspection
    artifacts. Self-describing: declares its own source layers and namespace rule additively.

    '
layer_definitions:
  INSPECTION:
    domain_subpath: registry
    registry_module: inspection.registry
    layer_category: workload
  INSPECTION_TRANSPORT:
    domain_subpath: transport
    registry_module: inspection.transport
    layer_category: workload
identity_rules:
- match: inspection.registry
  namespace: inspection
- match: inspection.transport
  namespace: inspection
artifact_discovery:
  search_layers:
  - INSPECTION
  - INSPECTION_TRANSPORT
  import_surface:
    domain: platform
  artifact_types:
  - STRUCTURE
  - TI
  - TE
output_configuration:
  artifacts:
    layer: PROTOCOL_BUILD_ROOT
    subpath: compiled/canonical
  vocabulary_projection_path:
    layer: GOVERNANCE
    subpath: compiled/vocabulary
  tokenized_projection_path:
    layer: GOVERNANCE
    subpath: compiled/tokenized
  evidence_projection_path:
    layer: GOVERNANCE
    subpath: compiled/evidence
  trust_attestation_path:
    layer: GOVERNANCE
    subpath: compiled/trust
  visualization_projection_path:
    layer: GOVERNANCE
    subpath: compiled/visualization
  layer_outputs:
    INSPECTION:
      layer: INSPECTION
      subpath: compiled/canonical
    INSPECTION_TRANSPORT:
      layer: INSPECTION
      subpath: compiled/canonical
  bootstrap_search_roots:
  - layer: GOVERNANCE
    subpath: structure/structures
build_phases:
- phase: discover
  description: Discover inspection artifacts via STRUCTURE
- phase: parse
  description: Parse artifacts into canonical machine form
- phase: normalize
  description: Resolve references (inspection + imported platform surface)
- phase: validate
  description: Validate artifacts using compiler schema rules
- phase: assert
  description: Evaluate cross-artifact invariants (boundary closure)
- phase: materialize
  description: Emit deterministic compiled artifacts (inspection scope only)
  target: compiled/artifacts/
```

## Version History

- **V0**: First PGC tool-domain build manifest. Compiles `inspection::` boundary contracts against
  the imported compiled platform surface; emits only inspection artifacts. Platform surface
  unchanged.
