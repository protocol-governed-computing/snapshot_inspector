"""si.rule_set.list — every artifact that carries a sealed rule set, and the rules in it.

A rule set exists in two places by design: declared in the code that generates it, and sealed inside
the artifact the compiler built from that declaration. Only the second is governance — it is what the
snapshot carries, what a pin names, and what actually judged a document. Nothing published it, so a
caller wanting to know whether a rule is in force had to open the artifact and go looking.

Published as identifiers rather than whole rules. What a rule *is* — its check kind, its register,
its parameters — is already readable through `si.artifact.show`, and repeating it here would make a
second copy of the same declaration that could drift from the first. What this answers is the
question `si.artifact.show` answers only by being read in full: **which rules are in force, and where**.

The rule set is searched for rather than addressed by path. It is node input, and which node carries
it is the workflow's own business; a path would couple this projection to a topology that is free to
change. That is the same read `transformation/design/sealed.py` performs against one workflow at a
time, published for all of them at once — because an observation is gathered with no parameters, and
a caller that must name the artifact first cannot ask a general question.

**No phase vocabulary appears here.** Which workflow is "phase 7" is the transformation compiler's
naming and not a snapshot fact; publishing it would put one repo's vocabulary into another's surface.
The identity is published; the caller maps its own names onto it.
"""
from __future__ import annotations

from typing import Any

from inspector.snapshot import Snapshot


def _find_rule_set(obj: Any) -> list | None:
    """The `rule_set` an artifact carries, wherever its node structure puts it."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "rule_set" and isinstance(value, list):
                return value
            found = _find_rule_set(value)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_rule_set(value)
            if found is not None:
                return found
    return None


def rule_set_list(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    artifact = (params.get("artifact") or "").strip()

    carriers = []
    for fqdn in sorted(snapshot.entries()):
        if artifact and fqdn != artifact:
            continue
        canonical = snapshot.canonical(fqdn)
        if canonical is None:
            continue
        rules = _find_rule_set(canonical)
        if rules is None:
            continue
        # An identifier may be declared more than once in one set — a register rule derived per
        # register shares its id across every register it is derived for. Reported as declared,
        # deduplicated and sorted, because the question is whether a rule is in force and not how
        # many times it was written.
        ids = sorted({str(r.get("id")) for r in rules if isinstance(r, dict) and r.get("id")})
        carriers.append({
            "artifact": fqdn,
            "domain": fqdn.split("::")[0],
            "rule_count": len(rules),
            "rules": ids,
        })

    # A named artifact that carries no rule set is a governed answer, not an error: the caller asked
    # a well-formed question about an artifact that exists and holds no rules.
    if artifact and not carriers:
        return "NOT_FOUND", {
            "artifact": artifact,
            "reason": "no sealed rule set is carried by that artifact",
        }

    return "SUCCESS", {
        "artifact": artifact or None,
        "carrier_count": len(carriers),
        "carriers": carriers,
    }
