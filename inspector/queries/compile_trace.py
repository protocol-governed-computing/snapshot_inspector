"""si.compile.trace — how the compiler came to produce one artifact, from each domain's compile trace.

A build records what each stage did as events (`evidence/<domain>/evidence_graph.json`): the stage,
the operation, the artifact it concerned, and CAUSALITY edges from each event to the events it
caused. This answers, per domain whose build concerned the artifact:

- `events`     — the events about the artifact, in order;
- `upstream`   — every event that led to them, root first;
- `downstream` — every event they led to;
- `written`    — where the build wrote the artifact.

This is the compile trace, not the semantic graph: it says what the build did, not what the artifact
refers to (`si.artifact.refs` answers that). An artifact no build's trace concerns is NOT_FOUND.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from inspector.snapshot import Snapshot


def _event(e: dict[str, Any]) -> dict[str, Any]:
    return {key: e.get(key) for key in ("event_id", "stage", "family", "operation", "subject_fqdn", "detail")}


def _reach(start: set[int], step: dict[int, set[int]]) -> set[int]:
    seen: set[int] = set()
    frontier = list(start)
    while frontier:
        for nxt in step.get(frontier.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    return seen - start


def compile_trace(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    artifact = str(params.get("artifact", ""))
    domain = params.get("domain")
    domains = snapshot.domains()
    if domain is not None and domain not in domains:
        return "NOT_FOUND", {"reason": f"this snapshot composes no domain {domain!r}", "known_domains": domains}

    answers = []
    for d in [domain] if domain else domains:
        trace = snapshot.compile_trace(d)
        if trace is None:
            continue
        events = {e["event_id"]: e for e in trace.get("events", [])}
        own = {i for i, e in events.items() if e.get("subject_fqdn") == artifact}
        if not own:
            continue
        causes: dict[int, set[int]] = defaultdict(set)
        effects: dict[int, set[int]] = defaultdict(set)
        for edge in trace.get("edges", []):
            if edge.get("kind") == "CAUSALITY":
                causes[edge["target_event_id"]].add(edge["source_event_id"])
                effects[edge["source_event_id"]].add(edge["target_event_id"])
        answers.append({
            "domain": d,
            "events": [_event(events[i]) for i in sorted(own)],
            "upstream": [_event(events[i]) for i in sorted(_reach(own, causes)) if i in events],
            "downstream": [_event(events[i]) for i in sorted(_reach(own, effects)) if i in events],
            "written": sorted({str(events[i]["detail"]["output_path"]) for i in own
                               if events[i].get("operation") == "artifact_written"
                               and "output_path" in (events[i].get("detail") or {})}),
        })

    if not answers:
        return "NOT_FOUND", {"artifact": artifact, "reason": "no build's compile trace concerns this artifact"}
    return "SUCCESS", {"artifact": artifact, "domain_count": len(answers), "domains": answers}
