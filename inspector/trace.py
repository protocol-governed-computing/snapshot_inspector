"""Read-only access to one execution trace — the inspector's second, narrower input.

The inspector reads the assembled snapshot. One query also reads a trace, because explaining a
run needs what the run recorded. A trace is not snapshot material: the runtime writes it under its
instance data root, outside the seal. So it arrives under its own rules:

- **Named, never discovered.** The caller names a trace by the reference the runtime returned for
  the run — its path relative to the trace root, e.g. `traces/<domain>/<WF>/<id>/<id>.jsonl`. The
  inspector never scans the root for traces.
- **Confined to the trace root.** A reference that is absolute, climbs out with `..`, or resolves
  outside the root is refused. The root is provisioned by whoever runs the inspector, the same way
  the snapshot root is.
- **Tied to a snapshot by its own first record.** The runtime opens every trace with a
  `trace_classification` record carrying the `snapshot_id` it executed under. A file without that
  record is refused: nothing ties it to any snapshot. The tie is *claimed*: the trace is unsealed,
  and the inspector reports the claim without vouching for it.

Refusals are `TraceRefused` with a reason. The query projects them as NOT_FOUND, never as an empty
explanation, and never echoes file content it refused.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

_CLASSIFICATION = "trace_classification"


class TraceRefused(ValueError):
    """The named trace cannot be read as a trace of any snapshot. `str(exc)` is the reason."""


@dataclass(frozen=True)
class Trace:
    reference: str                   # as the caller named it
    snapshot_id: str                 # claimed by the trace's first record
    classification: dict[str, Any]   # that first record
    events: list[dict[str, Any]]     # every record after it, in order


def read_trace(trace_root: Path | None, reference: str) -> Trace:
    if trace_root is None:
        raise TraceRefused("no trace root is provisioned for this inspector")
    ref = PurePosixPath(reference)
    if not reference or ref.is_absolute() or ".." in ref.parts or ref.suffix != ".jsonl":
        raise TraceRefused("a trace reference is a relative path to a .jsonl file under the trace root")

    root = Path(trace_root).resolve()
    path = (root / ref).resolve()
    if not path.is_relative_to(root):
        raise TraceRefused("the trace reference resolves outside the trace root")
    if not path.is_file():
        raise TraceRefused("no trace at this reference")

    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for number, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                raise TraceRefused(f"the trace is not well-formed JSONL (line {number})") from None
            if not isinstance(record, dict):
                raise TraceRefused(f"the trace is not well-formed JSONL (line {number})")
            records.append(record)

    head = records[0] if records else {}
    snapshot_id = head.get("snapshot_id")
    if head.get("event_type") != _CLASSIFICATION or not isinstance(snapshot_id, str) or not snapshot_id:
        raise TraceRefused(
            "the trace does not open with a trace_classification record naming its snapshot, "
            "so nothing ties it to any snapshot"
        )
    return Trace(reference=reference, snapshot_id=snapshot_id, classification=head,
                 events=records[1:])
