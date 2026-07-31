#!/usr/bin/env python3
"""
Inspector testbed — the API contract, all twelve operations, and the validator's own checks.

Self-contained: every case builds a fixture snapshot in a temp directory, so the testbed proves
behaviour against a snapshot it fully controls rather than against whatever the workspace last
assembled. The fixture is deliberately awkward where the real snapshot is: an artifact whose FQDN
namespace is not its snapshot directory, and an artifact published in two domains at once.

Run: PYTHONPATH=. python3 scripts/testbed/test_inspector.py
"""

import json
import sys
import tempfile
from pathlib import Path

from inspector.api import operation_kind, operations, query
from inspector.registry import CATEGORIES, OPERATIONS, SNAPSHOT_QUERY, SNAPSHOT_READ

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  {detail}")


def _write(root: Path, relative: str, payload) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


# ── fixture ──────────────────────────────────────────────────────
#
# One composition, two domains. `shared::CS_STORE_V0` is published under BOTH domain trees and
# belongs to neither namespace — the shape that breaks any resolver deriving a path from an FQDN.

_CS = {
    "fqdn_id": "shared::CS_STORE_V0", "artifact_type": "CS",
    "frontmatter": {"core": {}},
}
_WF = {
    "fqdn_id": "d::WF_X_V0", "artifact_type": "WF", "namespace": "d",
    "frontmatter": {"subdomain": "sub", "core": {
        "summary": "does a thing", "start_node": "CC_A_V0",
        "nodes": {"CC_A_V0": {"type": "CC"}},
    }},
}
_CC = {"fqdn_id": "d::CC_A_V0", "artifact_type": "CC", "frontmatter": {"core": {}}}
_STRUCTURE = {
    "fqdn_id": "d::STRUCTURE_STORAGE_V0", "artifact_type": "STRUCTURE",
    "frontmatter": {"core": {"domain": "d", "entity_stores": {
        "ACTOR": {"path": "d/actors.json", "description": "actors"},
    }}},
}
_RB = {
    "fqdn_id": "d::RB_X_V0", "artifact_type": "RB",
    "frontmatter": {"core": {"bindings": {
        "shared::CS_STORE_V0": {"policy": {"path": "{{module_data_root}}/d/actors.json"}},
    }}},
}
_GRAPH = {
    "wf_id": "WF_X_V0", "entry": "IN_X_V0",
    "nodes": [{"id": "CC_A_V0", "type": "CC"}],
    "edges": [], "execution_paths": [["CC_A_V0"]],
}


def _fixture(root: Path) -> None:
    paths = {
        "d::WF_X_V0": ("canonical/d/workflows/d__WF_X_V0.json", _WF),
        "d::CC_A_V0": ("canonical/d/capability_contracts/d__CC_A_V0.json", _CC),
        "d::STRUCTURE_STORAGE_V0": ("canonical/d/structures/d__STRUCTURE_STORAGE_V0.json", _STRUCTURE),
        "d::RB_X_V0": ("canonical/d/runtime_bindings/d__RB_X_V0.json", _RB),
        # published under `e`, namespaced `shared` — index is the only way to find it
        "shared::CS_STORE_V0": ("canonical/e/capability_side_effects/shared__CS_STORE_V0.json", _CS),
    }
    for rel, payload in paths.values():
        _write(root, rel, payload)
    # the same artifact republished under the other domain, byte-identical
    _write(root, "canonical/d/capability_side_effects/shared__CS_STORE_V0.json", _CS)

    _write(root, "manifest.json", {
        "manifest_version": "v0", "snapshot_id": "abc123",
        "domains": [{"domain": "d", "compiler_version": "3", "graph_address_hash": "h1"},
                    {"domain": "e", "compiler_version": "3", "graph_address_hash": "h2"}],
    })
    # Addresses are stated ONLY where the vocabulary carries the identity — the index and the
    # vocabulary are two views of one fact, and a fixture that lets them disagree is testing
    # against a snapshot the assembler could not have produced.
    addresses = {"d::WF_X_V0": {"d": "0x0001"}}
    _write(root, "artifact_index/index.json", {
        "schema_version": "v0", "artifact_count": len(paths),
        "artifacts": {
            fqdn: {
                "domain": fqdn.split("::")[0], "kind": doc["artifact_type"],
                "owner_subdomain": None, "canonical_path": rel,
                "evidence_paths": {}, "addresses": addresses.get(fqdn, {}),
            }
            for fqdn, (rel, doc) in paths.items()
        },
    })
    _write(root, "kind_index/index.json", {
        "schema_version": "v0",
        "workflows": {"d::WF_X_V0": {
            "fqdn": "d::WF_X_V0", "namespace": "d", "subdomain": "sub",
            "summary": "does a thing", "start_node": "CC_A_V0", "nodes": {"CC_A_V0": {}},
        }},
    })
    _write(root, "store_index/index.json", {
        "schema_version": "v0", "store_count": 1,
        "stores": {"d::ACTOR": {"store": "ACTOR", "domain": "d", "declarations": [
            {"path": "d/actors.json", "description": "actors",
             "declared_by": "d::STRUCTURE_STORAGE_V0", "bindings": []},
        ]}},
    })
    _write(root, "vocabulary/d/reverse.json", {"d::WF_X_V0": "0x0001", "edge_kind::NODE_NEXT": "0x4000"})
    _write(root, "vocabulary/d/forward.json", {"0x0001": "d::WF_X_V0", "0x4000": "edge_kind::NODE_NEXT"})
    _write(root, "evidence/d/evidence.json", {
        "nodes": [{"fqdn": "d::WF_X_V0", "kind": "WF"}, {"fqdn": "d::CC_A_V0", "kind": "CC"},
                  {"fqdn": "shared::CS_STORE_V0", "kind": "CS"}],
        "edges": [
            {"kind": "WF_CONTAINS_NODE", "source_fqdn": "d::WF_X_V0", "target_fqdn": "d::CC_A_V0"},
            {"kind": "CC_BINDS_CS", "source_fqdn": "d::CC_A_V0", "target_fqdn": "shared::CS_STORE_V0"},
        ],
    })
    _write(root, "behavior_logic/d/WF_X_V0/WF_X_V0.graph.json", _GRAPH)
    _write(root, "conformance/composition.json", {
        "status": "PASSED", "snapshot_id": "abc123", "rules_evaluated": 2,
        "artifacts_examined": 5, "findings": [{"invariant": "i::INV_A_V0", "status": "PASSED"}],
    })


class Fixture:
    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        _fixture(root)
        return root

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()


# ── API contract ─────────────────────────────────────────────────

def test_api_contract() -> None:
    with Fixture() as root:
        try:
            query("si.not.an.operation", {}, root)
            check("api_unregistered_raises", False, "no raise")
        except KeyError:
            check("api_unregistered_raises", True)

        status, payload = query("si.artifact.show", {}, root)
        check("api_missing_required_is_not_found", status == "NOT_FOUND")
        check("api_missing_required_names_param", "artifact" in payload["reason"])

        status, _ = query("si.artifact.list", {}, root)
        check("api_optional_params_omitted_ok", status == "SUCCESS")

        check("api_operation_kind_read", operation_kind("si.artifact.show") == SNAPSHOT_READ)
        check("api_operation_kind_query", operation_kind("si.topology.impact") == SNAPSHOT_QUERY)


def test_catalog() -> None:
    catalog = operations()
    check("catalog_covers_registry", len(catalog) == len(OPERATIONS))
    check("catalog_identities_match", {c["operation"] for c in catalog} == set(OPERATIONS))
    check("catalog_kinds_valid", all(c["kind"] in (SNAPSHOT_READ, SNAPSHOT_QUERY) for c in catalog))
    check("catalog_categories_declared", {c["category"] for c in catalog} <= set(CATEGORIES))
    check("catalog_grouped", [c["category"] for c in catalog] ==
          sorted([c["category"] for c in catalog], key=CATEGORIES.index))
    check("catalog_required_subset_of_params",
          all(set(c["required"]) <= set(c["params"]) for c in catalog))
    check("catalog_every_op_summarized", all(c["summary"] and c["label"] for c in catalog))


# ── reads ────────────────────────────────────────────────────────

def test_artifact_show() -> None:
    with Fixture() as root:
        status, payload = query("si.artifact.show", {"artifact": "d::WF_X_V0"}, root)
        check("show_success", status == "SUCCESS")
        check("show_returns_canonical", payload["canonical"]["fqdn_id"] == "d::WF_X_V0")
        check("show_carries_kind", payload["kind"] == "WF")

        # the load-bearing case: namespace ≠ snapshot directory
        status, payload = query("si.artifact.show", {"artifact": "shared::CS_STORE_V0"}, root)
        check("show_resolves_foreign_namespace", status == "SUCCESS", str(payload))
        check("show_foreign_via_index",
              payload["canonical_path"].startswith("canonical/e/"), str(payload.get("canonical_path")))

        status, _ = query("si.artifact.show", {"artifact": "d::ABSENT_V0"}, root)
        check("show_absent_not_found", status == "NOT_FOUND")
        status, _ = query("si.artifact.show", {"artifact": "no-colons"}, root)
        check("show_malformed_fqdn_not_found", status == "NOT_FOUND")


def test_artifact_list() -> None:
    with Fixture() as root:
        _, all_of_them = query("si.artifact.list", {}, root)
        check("list_all", all_of_them["artifact_count"] == 5)

        _, filtered = query("si.artifact.list", {"kind": "WF"}, root)
        check("list_filter_kind", filtered["artifact_count"] == 1)

        _, by_domain = query("si.artifact.list", {"domain": "shared"}, root)
        check("list_filter_domain", by_domain["artifact_count"] == 1)

        status, payload = query("si.artifact.list", {"kind": "NOPE"}, root)
        check("list_unknown_kind_not_found", status == "NOT_FOUND")
        check("list_unknown_kind_reports_known", "WF" in payload["known_kinds"])


def test_artifact_indexed() -> None:
    with Fixture() as root:
        status, payload = query("si.artifact.indexed", {"artifact": "d::WF_X_V0"}, root)
        check("indexed_true", status == "SUCCESS" and payload["indexed"] is True)
        # membership is an answer, not a failure — absent must still be SUCCESS
        status, payload = query("si.artifact.indexed", {"artifact": "d::ABSENT_V0"}, root)
        check("indexed_false_is_success", status == "SUCCESS" and payload["indexed"] is False)


def test_vocab() -> None:
    with Fixture() as root:
        status, payload = query("si.vocab.search", {"term": "wf_x"}, root)
        check("vocab_search_case_insensitive", status == "SUCCESS" and payload["match_count"] == 1)
        check("vocab_search_marks_indexed", payload["matches"][0]["indexed"] is True)

        _, payload = query("si.vocab.search", {"term": "edge_kind"}, root)
        check("vocab_search_non_artifact_symbol",
              payload["matches"][0]["indexed"] is False and payload["match_count"] == 1)

        status, payload = query("si.vocab.resolve", {"artifact": "d::WF_X_V0"}, root)
        check("vocab_resolve_identity", status == "SUCCESS" and payload["addresses"] == {"d": "0x0001"})

        status, payload = query("si.vocab.resolve", {"address": "0x0001", "domain": "d"}, root)
        check("vocab_resolve_address", status == "SUCCESS" and payload["identity"] == "d::WF_X_V0")

        # an address without its domain is unanswerable — each domain owns its own address space
        status, _ = query("si.vocab.resolve", {"address": "0x0001"}, root)
        check("vocab_resolve_address_needs_domain", status == "NOT_FOUND")

        status, _ = query("si.vocab.resolve", {}, root)
        check("vocab_resolve_needs_input", status == "NOT_FOUND")


def test_behavior_logic() -> None:
    with Fixture() as root:
        status, payload = query("si.behavior_logic.list", {}, root)
        check("bl_list", status == "SUCCESS" and payload["workflow_count"] == 1)
        check("bl_list_entry", payload["workflows"][0]["entry"] == "IN_X_V0")
        check("bl_list_png_absent", payload["workflows"][0]["projection_path"] is None)

        status, payload = query("si.behavior_logic.show", {"wf": "d::WF_X_V0"}, root)
        check("bl_show", status == "SUCCESS" and payload["graph"]["wf_id"] == "WF_X_V0")

        status, _ = query("si.behavior_logic.show", {"wf": "d::WF_ABSENT_V0"}, root)
        check("bl_show_absent_not_found", status == "NOT_FOUND")


def test_snapshot_reads() -> None:
    with Fixture() as root:
        status, payload = query("si.snapshot.summary", {}, root)
        check("summary_identity", status == "SUCCESS" and payload["snapshot_id"] == "abc123")
        check("summary_counts_from_index", payload["artifact_count"] == 5)
        check("summary_by_kind", payload["artifacts_by_kind"]["WF"] == 1)
        check("summary_stores", payload["store_count"] == 1)

        status, payload = query("si.snapshot.topology", {}, root)
        check("topology_success", status == "SUCCESS")
        check("topology_declared_subdomain", "sub" in payload["topology"]["d"])
        check("topology_wf", payload["topology"]["d"]["sub"][0]["wf"] == "d::WF_X_V0")


# ── queries ──────────────────────────────────────────────────────

def test_refs_and_impact() -> None:
    with Fixture() as root:
        status, payload = query("si.artifact.refs", {"artifact": "d::CC_A_V0"}, root)
        check("refs_success", status == "SUCCESS")
        check("refs_consumers_are_incoming",
              [r["fqdn"] for r in payload["refs"]] == ["d::WF_X_V0"])
        check("refs_deps_are_outgoing",
              [r["fqdn"] for r in payload["deps"]] == ["shared::CS_STORE_V0"])
        check("refs_traversable", payload["traversable"] is True)

        # direct vs transitive must actually differ — a walk that ignores `transitive` looks fine
        _, direct = query("si.artifact.refs", {"artifact": "shared::CS_STORE_V0"}, root)
        _, deep = query("si.artifact.refs",
                        {"artifact": "shared::CS_STORE_V0", "transitive": True}, root)
        check("refs_direct_one_hop", direct["ref_count"] == 1)
        check("refs_transitive_closes", deep["ref_count"] == 2)
        check("refs_transitive_records_depth", max(r["depth"] for r in deep["refs"]) == 2)

        status, payload = query("si.topology.impact", {"artifact": "shared::CS_STORE_V0"}, root)
        check("impact_success", status == "SUCCESS")
        check("impact_counts_closure", payload["impacted_count"] == 2)
        check("impact_grouped_by_kind", set(payload["impact"]) == {"CC", "WF"})
        check("impact_namespaces", payload["impacted_namespaces"] == ["d"])

        status, _ = query("si.topology.impact", {"artifact": "d::ABSENT_V0"}, root)
        check("impact_absent_not_found", status == "NOT_FOUND")


def test_validate_green() -> None:
    with Fixture() as root:
        status, payload = query("si.snapshot.validate", {}, root)
        check("validate_success", status == "SUCCESS")
        check("validate_clean_fixture_valid", payload["valid"] is True, str(payload["failed_checks"]))
        check("validate_every_check_reports_examined",
              all("examined" in c for c in payload["checks"]))
        # the anti-vacuity property: a green check that inspected nothing is not evidence
        substantive = [c for c in payload["checks"] if c["check"] != "manifest_identity"]
        check("validate_no_vacuous_pass", all(c["examined"] > 0 for c in substantive),
              str([c["check"] for c in substantive if not c["examined"]]))


def test_validate_detects() -> None:
    def failed(root: Path, strict: bool = False) -> list[str]:
        return query("si.snapshot.validate", {"strict": strict}, root)[1]["failed_checks"]

    with Fixture() as root:
        (root / "canonical/d/workflows/d__WF_X_V0.json").unlink()
        check("validate_catches_missing_canonical",
              "index_locators_resolve" in failed(root))

    with Fixture() as root:
        _write(root, "canonical/d/events/d__EV_GHOST_V0.json",
               {"fqdn_id": "d::EV_GHOST_V0", "artifact_type": "EV"})
        check("validate_catches_unindexed_artifact",
              "canonical_artifacts_indexed" in failed(root))

    with Fixture() as root:
        _write(root, "vocabulary/d/reverse.json", {"d::WF_X_V0": "0xBEEF"})
        check("validate_catches_address_drift",
              "addresses_agree_with_vocabulary" in failed(root))

    with Fixture() as root:
        evidence = json.loads((root / "evidence/d/evidence.json").read_text())
        evidence["edges"].append(
            {"kind": "NODE_NEXT", "source_fqdn": "d::CC_A_V0", "target_fqdn": "d::CC_GONE_V0"})
        _write(root, "evidence/d/evidence.json", evidence)
        check("validate_catches_dangling_edge", "graph_endpoints_indexed" in failed(root))

    with Fixture() as root:
        _write(root, "conformance/composition.json",
               {"status": "PASSED", "snapshot_id": "abc123", "rules_evaluated": 0, "findings": []})
        check("validate_catches_vacuous_conformance",
              "composition_conformance_recorded" in failed(root))

    with Fixture() as root:
        _write(root, "conformance/composition.json",
               {"status": "PASSED", "snapshot_id": "OLD", "rules_evaluated": 2, "findings": []})
        check("validate_catches_stale_conformance",
              "composition_conformance_recorded" in failed(root))

    with Fixture() as root:
        (root / "conformance/composition.json").unlink()
        check("validate_catches_absent_conformance",
              "composition_conformance_recorded" in failed(root))

    # advisories: reported always, but only fail the snapshot under strict
    with Fixture() as root:
        _write(root, "store_index/index.json",
               {"schema_version": "v0", "store_count": 0, "stores": {}})
        _, payload = query("si.snapshot.validate", {}, root)
        check("validate_advisory_reported",
              "bound_paths_declared_as_stores" in payload["advisory_checks"])
        check("validate_advisory_not_failing", payload["valid"] is True)
        check("validate_advisory_fails_under_strict",
              "bound_paths_declared_as_stores" in failed(root, strict=True))

    with Fixture() as root:
        divergent = dict(_CS, layer_code="OTHER")
        _write(root, "canonical/d/capability_side_effects/shared__CS_STORE_V0.json", divergent)
        _, payload = query("si.snapshot.validate", {}, root)
        advisory = next(c for c in payload["checks"] if c["check"] == "republished_copies_agree")
        check("validate_catches_divergent_copies", advisory["violation_count"] == 1)
        check("validate_names_divergent_fields",
              advisory["violations"][0]["divergent_fields"] == ["layer_code"])


def test_stores() -> None:
    with Fixture() as root:
        status, payload = query("si.store.list", {}, root)
        check("store_list", status == "SUCCESS" and payload["store_count"] == 1)
        check("store_list_owner",
              payload["stores"][0]["declared_by"] == ["d::STRUCTURE_STORAGE_V0"])

        status, payload = query("si.store.show", {"store": "ACTOR"}, root)
        check("store_show_by_bare_name", status == "SUCCESS" and payload["key"] == "d::ACTOR")
        status, payload = query("si.store.show", {"store": "d::ACTOR"}, root)
        check("store_show_by_key", status == "SUCCESS")

        status, _ = query("si.store.show", {"store": "GHOST"}, root)
        check("store_show_absent_not_found", status == "NOT_FOUND")

        status, payload = query("si.store.consumers", {"store": "ACTOR"}, root)
        check("store_consumers_empty_is_success",
              status == "SUCCESS" and payload["workflows"] == [])

        status, payload = query("si.store.list", {"domain": "nope"}, root)
        check("store_list_unknown_domain_not_found", status == "NOT_FOUND")


# ── CLI (a client of the API, never a second engine) ─────────────

def _cli(argv: list[str], root: Path) -> tuple[int, str]:
    import contextlib
    import io

    from inspector.cli import main as cli_main

    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cli_main(["--snapshot", str(root), *argv])
    return code, out.getvalue()


def test_cli() -> None:
    with Fixture() as root:
        code, out = _cli(["operations"], root)
        check("cli_catalog_exit0", code == 0)
        check("cli_catalog_lists_every_operation",
              all(op.identity.split(".", 1)[1].split(".")[0] in out for op in OPERATIONS.values()))

        code, out = _cli(["artifact", "show", "d::WF_X_V0"], root)
        check("cli_show_exit0", code == 0)
        check("cli_show_names_operation", "si.artifact.show" in out and "SUCCESS" in out)

        code, out = _cli(["--json", "artifact", "list", "--kind", "WF"], root)
        check("cli_json_is_payload_only", json.loads(out)["artifact_count"] == 1)

        code, out = _cli(["artifact", "list", "--kind", "WF", "--json"], root)
        check("cli_json_after_verb", code == 0 and json.loads(out)["artifact_count"] == 1)

        code, _ = _cli(["artifact", "refs", "d::CC_A_V0", "--transitive"], root)
        check("cli_flag_param", code == 0)

        # NOT_FOUND is exit 1 — a script can branch on the answer without parsing output
        code, _ = _cli(["artifact", "show", "d::ABSENT_V0"], root)
        check("cli_not_found_exit1", code == 1)

        code, _ = _cli(["snapshot", "validate"], root)
        check("cli_validate_clean_exit0", code == 0)

        # the CI gate: strict must fail the COMMAND, not merely report inside a success
        _write(root, "store_index/index.json",
               {"schema_version": "v0", "store_count": 0, "stores": {}})
        code, _ = _cli(["snapshot", "validate"], root)
        check("cli_validate_advisory_exit0", code == 0)
        code, _ = _cli(["snapshot", "validate", "--strict"], root)
        check("cli_validate_strict_exit1", code == 1)

    code, out = _cli(["artifact", "list"], Path("/nonexistent-snapshot"))
    check("cli_bad_snapshot_exit2", code == 2)


def test_cli_is_generated_from_catalog() -> None:
    """Every registered operation is reachable, and nothing else is.

    The CLI must not carry commands the API cannot answer: that is how a client becomes a second
    inspection engine with answers of its own.
    """
    from inspector.cli import _build_parser

    _, routes = _build_parser()
    check("cli_covers_every_operation",
          {op.identity for op in routes.values()} == set(OPERATIONS))
    check("cli_adds_no_commands", len(routes) == len(OPERATIONS))


def main() -> None:
    for test in (
        test_api_contract,
        test_catalog,
        test_artifact_show,
        test_artifact_list,
        test_artifact_indexed,
        test_vocab,
        test_behavior_logic,
        test_snapshot_reads,
        test_stores,
        test_refs_and_impact,
        test_validate_green,
        test_validate_detects,
        test_cli,
        test_cli_is_generated_from_catalog,
    ):
        print(f"\n{test.__name__}")
        test()
    print(f"\nPASSED: {PASS}/{PASS + FAIL}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
