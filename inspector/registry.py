"""Internal dispatch: Operation Identity → read projection.

The inspector's OWN routing table (compiled/registered). Transport never sees this — it passes
an Operation Identity to `inspector.api.query`, which resolves it here. This keeps the transport
adapter free of any operation-dispatch logic (it is not an RPC router).
"""
from inspector.reads.artifact_show import artifact_show

PROJECTIONS = {
    "si.artifact.show": artifact_show,
    # Phase 2a — registered as each projection is built:
    #   si.snapshot.summary   si.snapshot.topology
    #   si.artifact.list
    #   si.vocab.search       si.vocab.resolve
    #   si.behavior_logic.list  si.behavior_logic.show
}
