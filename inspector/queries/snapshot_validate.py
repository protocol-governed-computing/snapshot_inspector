"""si.snapshot.validate — integrity and closure of the assembled snapshot.

This is NOT a second governance engine. It re-evaluates no invariant and re-derives no assertion:
the compiler proved each domain, the assembler proved the composition, and both left evidence
behind. What this checks is that the assembled artefact is INTERNALLY CONSISTENT — that its
indexes, canonical tree, vocabulary, semantic graph and behavior logic still describe the same
composition — plus whatever verdict the composition-conformance phase already recorded.

**Every check reports `examined`.** A check that inspected nothing and therefore violated nothing
is not a pass, and a validator that cannot tell the two apart reports green while looking at an
empty set. That defect has bitten this codebase repeatedly; here the count is part of the result,
so vacuity is visible without re-running anything.

`strict` promotes ADVISORY findings to failures. An advisory is a real inconsistency that no rule
currently forbids — today: a runtime binding writing to a path that no storage STRUCTURE declares.
CI gates run strict; exploratory inspection does not.
"""
from __future__ import annotations

import json
from typing import Any

from inspector.graph import SemanticGraph
from inspector.snapshot import Snapshot


def _check(name: str, examined: int, violations: list[Any], advisory: bool = False) -> dict[str, Any]:
    return {
        "check": name,
        "examined": examined,
        "violation_count": len(violations),
        "violations": violations[:50],
        "truncated": len(violations) > 50,
        "advisory": advisory,
        "passed": not violations,
    }


def snapshot_validate(snapshot: Snapshot, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    strict = bool(params.get("strict", False))
    entries = snapshot.entries()
    checks: list[dict[str, Any]] = []

    # 1. Identity — the composition names itself.
    manifest = snapshot.manifest()
    checks.append(_check(
        "manifest_identity",
        1,
        [] if manifest.get("snapshot_id") else ["manifest declares no snapshot_id"],
    ))

    # 2. Every index locator resolves to a file on disk.
    missing = [
        {"artifact": fqdn, "canonical_path": entry["canonical_path"]}
        for fqdn, entry in entries.items()
        if not snapshot.has(entry["canonical_path"])
    ]
    checks.append(_check("index_locators_resolve", len(entries), missing))

    # 3. Every canonical artifact on disk is indexed — the index is complete, not merely correct.
    #    4. …and where one FQDN is published in several domain trees (a shared artifact is copied
    #    into each domain that sees it), the copies agree. The index records ONE path per FQDN, so
    #    divergent copies would be invisible to every consumer that resolves through it.
    unindexed = []
    published: dict[str, list[tuple[str, str]]] = {}
    canonical_root = snapshot.root / "canonical"
    on_disk = 0
    if canonical_root.is_dir():
        for path in sorted(canonical_root.rglob("*.json")):
            if path.name == "metadata.json":
                continue
            raw = path.read_text(encoding="utf-8")
            fqdn = json.loads(raw).get("fqdn_id")
            if not fqdn:
                continue
            on_disk += 1
            rel = path.relative_to(snapshot.root).as_posix()
            published.setdefault(fqdn, []).append((rel, raw))
            if fqdn not in entries:
                unindexed.append({"artifact": fqdn, "canonical_path": rel})
    checks.append(_check("canonical_artifacts_indexed", on_disk, unindexed))

    duplicated = {f: copies for f, copies in published.items() if len(copies) > 1}
    divergent = []
    for fqdn, copies in sorted(duplicated.items()):
        if len({content for _, content in copies}) == 1:
            continue
        parsed = [(rel, json.loads(content)) for rel, content in copies]
        fields = sorted({
            key
            for key in {k for _, doc in parsed for k in doc}
            if len({json.dumps(doc.get(key), sort_keys=True) for _, doc in parsed}) > 1
        })
        divergent.append({
            "artifact": fqdn,
            "divergent_fields": fields,
            "paths": [rel for rel, _ in parsed],
            # The copy every consumer actually resolves to, chosen by the index. Which one that
            # is decides what `si.artifact.show` returns for this FQDN.
            "indexed_copy": (entries.get(fqdn) or {}).get("canonical_path"),
        })
    checks.append(_check("republished_copies_agree", len(duplicated), divergent, advisory=True))

    # 4. Indexed addresses agree with the vocabulary tables they were read from.
    address_mismatches = []
    examined_addresses = 0
    vocabularies = {d: snapshot.vocabulary(d)["reverse"] for d in snapshot.vocabulary_domains()}
    for fqdn, entry in entries.items():
        for domain, address in entry.get("addresses", {}).items():
            examined_addresses += 1
            published = vocabularies.get(domain, {}).get(fqdn)
            if published != address:
                address_mismatches.append({
                    "artifact": fqdn, "domain": domain,
                    "index": address, "vocabulary": published,
                })
    checks.append(_check("addresses_agree_with_vocabulary", examined_addresses, address_mismatches))

    # 5. Every semantic-graph endpoint is a composed artifact — no dangling reference.
    graph = SemanticGraph(snapshot)
    dangling = sorted({
        endpoint
        for edge in graph.edges
        for endpoint in (edge.source, edge.target)
        if endpoint not in entries
    })
    checks.append(_check("graph_endpoints_indexed", len(graph.edges), dangling))

    # 6. Every published behavior-logic graph belongs to a composed workflow.
    published_logic = snapshot.behavior_logic_workflows()
    orphan_logic = [
        f"{domain}/{code}"
        for domain, code in published_logic
        if not any(fqdn.split("::", 1)[1] == code for fqdn in entries)
    ]
    checks.append(_check("behavior_logic_workflows_composed", len(published_logic), orphan_logic))

    # 7. ADVISORY — every bound data path is a store some STRUCTURE declares.
    #    A governed write to an undeclared store is invisible to the storage-ownership model: no
    #    artifact claims the file, so nothing governs its lifecycle. No rule forbids it today.
    declared_paths = {
        declaration["path"]
        for store in snapshot.store_index()["stores"].values()
        for declaration in store["declarations"]
    }
    bound, undeclared = 0, []
    for fqdn, entry in entries.items():
        if entry.get("kind") != "RB":
            continue
        canonical = snapshot.canonical(fqdn) or {}
        bindings = canonical.get("frontmatter", {}).get("core", {}).get("bindings", {})
        for cs_fqdn, binding in bindings.items():
            path = (binding.get("policy") or {}).get("path")
            if not path:
                continue
            bound += 1
            stripped = path.replace("{{module_data_root}}/", "", 1)
            if stripped not in declared_paths:
                undeclared.append({"rb": fqdn, "cs": cs_fqdn, "path": stripped})
    checks.append(_check("bound_paths_declared_as_stores", bound, undeclared, advisory=True))

    # 8. The inspection boundary agrees with the code that serves it. The contracts are the
    #    authority for what exists, so an implementation no contract names is unreachable code —
    #    it cannot be invoked through any boundary, and its presence means the registry and the
    #    snapshot have drifted apart.
    from inspector.catalog import load_catalog
    from inspector.registry import IMPLEMENTATIONS

    declared = {op.implementation for op in load_catalog(snapshot).values()}
    unreachable = sorted(set(IMPLEMENTATIONS) - declared)
    checks.append(_check(
        "inspection_implementations_declared",
        len(IMPLEMENTATIONS),
        [{"implementation": ref, "reason": "no inspection contract names it"} for ref in unreachable],
    ))

    # 9. The composition-conformance verdict, as the assembler recorded it. Read, never re-run.
    #    A recorded PASSED is only worth reading if it covered something and belongs to THIS
    #    composition: evidence carrying an older snapshot_id is a verdict about a different
    #    snapshot, and a verdict over zero rules is the vacuity the phase exists to prevent.
    conformance = snapshot.conformance()
    if conformance is None:
        checks.append(_check(
            "composition_conformance_recorded", 0,
            ["no composition conformance evidence in snapshot"],
        ))
    else:
        rules_evaluated = conformance.get("rules_evaluated", 0)
        findings = conformance.get("findings", [])
        violations: list[Any] = []
        if conformance.get("status") not in ("PASSED", "PASS"):
            violations.append({"recorded_status": conformance.get("status")})
        if conformance.get("snapshot_id") != manifest.get("snapshot_id"):
            violations.append({
                "reason": "conformance evidence is for a different composition",
                "evidence_snapshot_id": conformance.get("snapshot_id"),
                "manifest_snapshot_id": manifest.get("snapshot_id"),
            })
        if not rules_evaluated:
            violations.append({"reason": "verdict recorded over zero rules"})
        violations += [
            {"invariant": f.get("invariant"), "status": f.get("status"), "examined": f.get("examined")}
            for f in findings
            if f.get("status") not in ("PASSED", "PASS")
        ]
        checks.append(_check(
            "composition_conformance_recorded", rules_evaluated, violations,
        ))

    failed = [c for c in checks if not c["passed"] and (strict or not c["advisory"])]
    advisories = [c for c in checks if not c["passed"] and c["advisory"]]

    return "SUCCESS", {
        "snapshot_id": snapshot.snapshot_id(),
        "strict": strict,
        "valid": not failed,
        "check_count": len(checks),
        "failed_checks": [c["check"] for c in failed],
        "advisory_checks": [c["check"] for c in advisories],
        "checks": checks,
    }
