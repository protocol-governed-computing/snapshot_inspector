"""snapshot_inspector — read-only inspection over assembled PGC snapshots.

A first-class toolchain component, symmetric with the compiler / assembler / runtime — each
owns one phase of the snapshot lifecycle:

    protocol_compiler    source      → compiled projections
    snapshot_assembler   projections → assembled snapshot
    protocol_runtime     snapshot    → execution
    snapshot_inspector   snapshot    → inspection      (this repo)

CONSUMER-NEUTRAL: the transport SNAPSHOT_READ/SNAPSHOT_QUERY handlers are one consumer; a `si`
CLI, CI gates (validate/violations), and change-management dossiers are others. The API makes
no web/transport assumptions.

Inspection never mutates and never executes. Phase 2a projects PUBLISHED snapshot material;
Phase 2b derives governed queries (refs/deps/impact/validation) over it.
"""
