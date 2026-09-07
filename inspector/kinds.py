"""Inspection vocabulary — handler kinds and catalog categories.

A leaf module that imports nothing, so the registry, the catalog reader, and the projections can
all name these without importing each other. They are the fixed words of the inspection surface:

    SNAPSHOT_READ   project PUBLISHED snapshot material — no traversal, no evaluation
    SNAPSHOT_QUERY  DERIVE a result by traversing or evaluating snapshot state

The handler kinds are also transport handler kinds: the boundary routes by them, and the pair is
part of the Transport Standard rather than of this repo. `CATEGORIES` is presentation order for a
catalog — the only thing here that is purely this surface's own.
"""

SNAPSHOT_READ = "SNAPSHOT_READ"
SNAPSHOT_QUERY = "SNAPSHOT_QUERY"

INSPECTION_KINDS = (SNAPSHOT_READ, SNAPSHOT_QUERY)

CATEGORIES = ("SNAPSHOT", "ARTIFACTS", "STORES", "VOCABULARY", "BEHAVIOR")
