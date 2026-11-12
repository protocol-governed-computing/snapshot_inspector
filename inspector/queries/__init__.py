"""Derived queries (Phase 2b) — each DERIVES a result by traversing or evaluating snapshot state.

Signature: `(snapshot: Snapshot, params: dict) -> (status, payload)`, identical to a read, so the
boundary treats both uniformly. The difference is not the signature but the authority: a read
re-emits what the snapshot published, a query computes a relationship that is not published
anywhere. That computation belongs HERE and nowhere downstream — the moment a client derives a
reference closure of its own, there are two inspection engines and they will disagree.
"""
