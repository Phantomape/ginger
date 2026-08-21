from copy import deepcopy

import pytest

from quant.test_v2_contracts import (
    _evidence,
    _seal_evidence,
    _seal_mapping,
    _seal_source,
    _source,
)
from quant.test_v2_universe_ledger import _append, _bound_graph, _manifest, _reseal_manifest
from quant.v2_contracts import canonical_hash
from quant.v2_universe_coverage import (
    V2UniverseCoverageError,
    normalize_external_universe_coverage_snapshot,
    validate_external_universe_coverage_against_inputs,
)
from quant.v2_universe_ledger import (
    V2UniverseLedgerError,
    read_v2_universe_membership,
    validate_external_universe_coverage_against_manifest,
)


def _assert_code(code, function, error=V2UniverseCoverageError):
    with pytest.raises(error) as caught:
        function()
    assert caught.value.code == code


def _row(row_id, row_hash, *, disposition, evidence=None, mapping=None):
    return {
        "schema_version": 1,
        "record_type": "v2_external_universe_coverage_row",
        "source_row_id": row_id,
        "source_row_sha256": row_hash,
        "disposition": disposition,
        "reason_code": f"synthetic_{disposition}",
        "reason": f"Synthetic {disposition} row for coverage contract tests.",
        "security_mapping": mapping,
        "mapping_evidence_id": None if evidence is None else evidence["evidence_id"],
        "mapping_evidence_semantic_hash": (
            None if evidence is None else evidence["semantic_hash"]
        ),
        "mapping_evidence_record_hash": None if evidence is None else evidence["record_hash"],
    }


def _seal_snapshot(row):
    row = deepcopy(row)
    row["rows"] = sorted(row["rows"], key=lambda item: item["source_row_id"])
    row["source_reported_row_count"] = len(row["rows"])
    row["disposition_counts"] = {
        disposition: sum(item["disposition"] == disposition for item in row["rows"])
        for disposition in ("excluded", "mapped", "unmapped")
    }
    row["row_snapshot_sha256"] = canonical_hash(
        [
            {
                "source_row_id": item["source_row_id"],
                "source_row_sha256": item["source_row_sha256"],
            }
            for item in row["rows"]
        ]
    )
    row["coverage_status"] = (
        "verified_known_empty" if not row["rows"] else "verified_complete"
    )
    row.pop("semantic_hash", None)
    row.pop("record_hash", None)
    semantic = deepcopy(row)
    semantic.pop("recorded_at")
    row["semantic_hash"] = canonical_hash(semantic)
    record = deepcopy(row)
    row["record_hash"] = canonical_hash(record)
    return row


def _coverage_source_and_evidence(snapshot):
    decision_fields = [
        "coverage_scope_id",
        "coverage_scope_sha256",
        "coverage_scope_version",
        "enumeration_complete",
        "source_reported_row_count",
        "source_rows",
    ]
    source = _seal_source(
        _source(
            source_contract_id="source-v2-external-coverage-test-v1",
            source_name="synthetic_external_coverage",
            raw_identity_fields=["artifact_id", "revision_id"],
            decision_content_fields=decision_fields,
            published_at_field=None,
            published_at_rule="not separately published",
            security_mapping_policy="not_applicable",
            normalizer_id="v2-external-coverage-test-normalizer",
        )
    )
    source_rows = [
        {
            "source_row_id": item["source_row_id"],
            "source_row_sha256": item["source_row_sha256"],
        }
        for item in snapshot["rows"]
    ]
    evidence = _evidence(
        source=source,
        evidence_id="evidence-v2-external-coverage-test-r1",
        raw_identity={"artifact_id": "synthetic-coverage", "revision_id": "r1"},
        decision_content={
            "coverage_scope_id": snapshot["coverage_scope_id"],
            "coverage_scope_sha256": snapshot["coverage_scope_sha256"],
            "coverage_scope_version": snapshot["coverage_scope_version"],
            "enumeration_complete": True,
            "source_reported_row_count": len(source_rows),
            "source_rows": source_rows,
        },
        published_at=None,
        security_scope="not_applicable",
        security_mapping_kind="not_applicable",
        security_mapping=None,
    )
    return source, evidence


def _bind_coverage_evidence(snapshot):
    source, evidence = _coverage_source_and_evidence(snapshot)
    bound = deepcopy(snapshot)
    bound.update(
        coverage_source_contract_id=source["source_contract_id"],
        coverage_source_contract_hash=source["source_contract_hash"],
        coverage_evidence_id=evidence["evidence_id"],
        coverage_evidence_semantic_hash=evidence["semantic_hash"],
        coverage_evidence_record_hash=evidence["record_hash"],
    )
    return _seal_snapshot(bound), source, evidence


def _fixture(*, include_unmapped=True, include_excluded=True, empty=False):
    graph, bundle, clock, events = _bound_graph()
    manifest = _manifest(events, clock, graph=graph, bundle=bundle)
    evidence_by_security = {
        item["security_mapping"]["security_id"]: item for item in graph["evidence"]
    }
    rows = []
    if not empty:
        for membership in manifest["memberships"]:
            evidence = evidence_by_security[membership["security_id"]]
            rows.append(
                _row(
                    f"source-row-{membership['security_id']}",
                    canonical_hash({"source_row_id": membership["security_id"]}),
                    disposition="mapped",
                    evidence=evidence,
                    mapping=evidence["security_mapping"],
                )
            )
        if include_unmapped:
            rows.append(
                _row(
                    "source-row-unmapped",
                    canonical_hash({"source_row_id": "unmapped"}),
                    disposition="unmapped",
                )
            )
        if include_excluded:
            rows.append(
                _row(
                    "source-row-excluded",
                    canonical_hash({"source_row_id": "excluded"}),
                    disposition="excluded",
                )
            )
    snapshot = _seal_snapshot(
        {
            "schema_version": 1,
            "record_type": "v2_external_universe_coverage_snapshot",
            "coverage_snapshot_id": "coverage-snapshot-20260820-1",
            "universe_id": manifest["universe_id"],
            "universe_definition_id": manifest["universe_definition_id"],
            "universe_definition_version": manifest["universe_definition_version"],
            "universe_definition_sha256": manifest["universe_definition_sha256"],
            "universe_manifest_id": manifest["manifest_id"],
            "universe_manifest_hash": manifest["manifest_hash"],
            "coverage_scope_id": "synthetic-complete-source-scope",
            "coverage_scope_version": "1",
            "coverage_scope_sha256": canonical_hash(
                {"scope": "synthetic-complete-source-scope", "version": "1"}
            ),
            "coverage_source_contract_id": "placeholder",
            "coverage_source_contract_hash": "0" * 64,
            "coverage_evidence_id": "placeholder",
            "coverage_evidence_semantic_hash": "0" * 64,
            "coverage_evidence_record_hash": "0" * 64,
            "membership_as_of": manifest["membership_as_of"],
            "data_cutoff": manifest["data_cutoff"],
            "frozen_at": "2026-08-20T14:23:00Z",
            "recorded_at": "2026-08-20T14:24:00Z",
            "enumeration_complete": True,
            "source_reported_row_count": 0,
            "rows": rows,
            "disposition_counts": {},
            "row_snapshot_sha256": "0" * 64,
            "coverage_status": "verified_complete",
            "pit_tier": "research_pit",
            "external_universe_coverage_status": "unverified",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "parity_status": "contract_only_unwired",
            "known_future_leakage": False,
            "outcome_blind": True,
            "results_accessed": False,
            "authority": "research_only",
            "trade_enabled": False,
        }
    )
    snapshot, source, coverage_evidence = _bind_coverage_evidence(snapshot)
    return graph, bundle, clock, events, manifest, snapshot, source, coverage_evidence


def _validate_inputs(snapshot, source, evidence, graph):
    return validate_external_universe_coverage_against_inputs(
        snapshot,
        coverage_evidence=evidence,
        coverage_source_contract=source,
        mapping_evidence_records=graph["evidence"],
        mapping_source_contracts=[graph["source"]],
    )


def _validate_manifest(snapshot, manifest, events, graph, source, evidence):
    return validate_external_universe_coverage_against_manifest(
        snapshot,
        manifest,
        events,
        coverage_evidence=evidence,
        coverage_source_contract=source,
        mapping_evidence_records=graph["evidence"],
        mapping_source_contracts=[graph["source"]],
    )


def test_coverage_round_trip_input_binding_manifest_binding_and_reader_ceiling(tmp_path):
    graph, bundle, clock, events, manifest, snapshot, source, evidence = _fixture()
    normalized = normalize_external_universe_coverage_snapshot(snapshot)
    assert normalized == snapshot
    assert _validate_inputs(snapshot, source, evidence, graph)["input_binding_sha256"]
    binding = _validate_manifest(snapshot, manifest, events, graph, source, evidence)
    assert binding["active_mapping_count"] == 2
    assert binding["external_universe_coverage_status"] == "unverified"

    path = tmp_path / "universe.jsonl"
    _append(path, events, manifest, graph=graph, bundle=bundle, clock=clock)
    reader = read_v2_universe_membership(
        path,
        manifest_id=manifest["manifest_id"],
        as_of=manifest["membership_as_of"],
    )
    assert reader["external_universe_coverage_status"] == "unverified"
    assert reader["paper_live_eligible"] is False
    assert reader["trade_enabled"] is False


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda row: row.update(enumeration_complete=False), "coverage_enumeration_incomplete"),
        (lambda row: row.update(source_reported_row_count=99), "coverage_row_count_mismatch"),
        (lambda row: row.update(trade_enabled=True), "coverage_boundary_violation"),
        (lambda row: row.update(pit_tier="canonical_pit"), "coverage_boundary_violation"),
    ],
)
def test_snapshot_count_and_default_off_boundaries_fail_closed(mutate, code):
    *_, snapshot, _, _ = _fixture()
    damaged = deepcopy(snapshot)
    mutate(damaged)
    damaged = _seal_snapshot(damaged) if code == "coverage_boundary_violation" else damaged
    _assert_code(code, lambda: normalize_external_universe_coverage_snapshot(damaged))


def test_rows_must_be_sorted_and_have_unique_ids_and_hashes():
    *_, snapshot, _, _ = _fixture()
    unsorted = deepcopy(snapshot)
    unsorted["rows"] = list(reversed(unsorted["rows"]))
    _assert_code("coverage_rows_not_sorted", lambda: normalize_external_universe_coverage_snapshot(unsorted))

    duplicate_id = deepcopy(snapshot)
    duplicate_id["rows"][1]["source_row_id"] = duplicate_id["rows"][0]["source_row_id"]
    duplicate_id["rows"] = sorted(duplicate_id["rows"], key=lambda item: item["source_row_id"])
    _assert_code("duplicate_source_row_id", lambda: normalize_external_universe_coverage_snapshot(duplicate_id))

    duplicate_hash = deepcopy(snapshot)
    duplicate_hash["rows"][1]["source_row_sha256"] = duplicate_hash["rows"][0]["source_row_sha256"]
    _assert_code("duplicate_source_row_hash", lambda: normalize_external_universe_coverage_snapshot(duplicate_hash))

    mapping_fork = deepcopy(snapshot)
    mapped = next(item for item in mapping_fork["rows"] if item["disposition"] == "mapped")
    excluded = next(item for item in mapping_fork["rows"] if item["disposition"] == "excluded")
    forked_mapping = deepcopy(mapped["security_mapping"])
    forked_mapping["listing_id"] = "listing-fork-xnas"
    excluded.update(
        security_mapping=_seal_mapping(forked_mapping),
        mapping_evidence_id=mapped["mapping_evidence_id"],
        mapping_evidence_semantic_hash=mapped["mapping_evidence_semantic_hash"],
        mapping_evidence_record_hash=mapped["mapping_evidence_record_hash"],
    )
    _assert_code(
        "security_mapping_identity_conflict",
        lambda: normalize_external_universe_coverage_snapshot(mapping_fork),
    )


def test_disposition_mapping_bundles_are_mutually_exclusive():
    *_, snapshot, _, _ = _fixture()
    mapped = next(item for item in snapshot["rows"] if item["disposition"] == "mapped")

    missing = deepcopy(snapshot)
    target = next(item for item in missing["rows"] if item["disposition"] == "mapped")
    target["security_mapping"] = None
    target["mapping_evidence_id"] = None
    target["mapping_evidence_semantic_hash"] = None
    target["mapping_evidence_record_hash"] = None
    _assert_code("mapped_row_requires_mapping", lambda: normalize_external_universe_coverage_snapshot(missing))

    forged = deepcopy(snapshot)
    target = next(item for item in forged["rows"] if item["disposition"] == "unmapped")
    for field in (
        "security_mapping",
        "mapping_evidence_id",
        "mapping_evidence_semantic_hash",
        "mapping_evidence_record_hash",
    ):
        target[field] = mapped[field]
    _assert_code("unmapped_row_forbids_mapping", lambda: normalize_external_universe_coverage_snapshot(forged))


@pytest.mark.parametrize("field", ["source_reported_row_count", "source_rows", "coverage_scope_sha256"])
def test_coverage_evidence_must_bind_complete_population(field):
    graph, _, _, _, _, snapshot, source, evidence = _fixture()
    damaged = deepcopy(evidence)
    if field == "source_reported_row_count":
        damaged["decision_content"][field] += 1
    elif field == "source_rows":
        damaged["decision_content"][field] = damaged["decision_content"][field][:-1]
    else:
        damaged["decision_content"][field] = "f" * 64
    damaged = _seal_evidence(damaged)
    rebound = deepcopy(snapshot)
    rebound.update(
        coverage_evidence_semantic_hash=damaged["semantic_hash"],
        coverage_evidence_record_hash=damaged["record_hash"],
    )
    rebound = _seal_snapshot(rebound)
    _assert_code(
        "coverage_evidence_population_mismatch",
        lambda: _validate_inputs(rebound, source, damaged, graph),
    )


def test_mapping_evidence_hash_and_effective_interval_fail_closed():
    graph, _, _, _, _, snapshot, source, evidence = _fixture()
    wrong_hash = deepcopy(snapshot)
    row = next(item for item in wrong_hash["rows"] if item["disposition"] == "mapped")
    row["mapping_evidence_record_hash"] = "f" * 64
    wrong_hash = _seal_snapshot(wrong_hash)
    _assert_code("mapping_evidence_binding_mismatch", lambda: _validate_inputs(wrong_hash, source, evidence, graph))

    expired_graph = deepcopy(graph)
    target_evidence = expired_graph["evidence"][0]
    mapping = deepcopy(target_evidence["security_mapping"])
    mapping["effective_to"] = "2026-08-20T14:10:00Z"
    mapping = _seal_mapping(mapping)
    target_evidence["security_mapping"] = mapping
    target_evidence = _seal_evidence(target_evidence)
    expired_graph["evidence"][0] = target_evidence
    expired = deepcopy(snapshot)
    target_row = next(
        item
        for item in expired["rows"]
        if item["security_mapping"] is not None
        and item["security_mapping"]["security_id"] == mapping["security_id"]
    )
    target_row.update(
        security_mapping=mapping,
        mapping_evidence_semantic_hash=target_evidence["semantic_hash"],
        mapping_evidence_record_hash=target_evidence["record_hash"],
    )
    expired = _seal_snapshot(expired)
    _assert_code("mapping_interval_miss", lambda: _validate_inputs(expired, source, evidence, expired_graph))

    late_graph = deepcopy(graph)
    late_evidence = late_graph["evidence"][0]
    late_evidence.update(
        observed_at="2026-08-20T14:21:00Z",
        known_at="2026-08-20T14:21:00Z",
        recorded_at="2026-08-20T14:22:00Z",
    )
    late_evidence = _seal_evidence(late_evidence)
    late_graph["evidence"][0] = late_evidence
    late = deepcopy(snapshot)
    late_row = next(
        item
        for item in late["rows"]
        if item["mapping_evidence_id"] == late_evidence["evidence_id"]
    )
    late_row.update(
        mapping_evidence_semantic_hash=late_evidence["semantic_hash"],
        mapping_evidence_record_hash=late_evidence["record_hash"],
    )
    late = _seal_snapshot(late)
    _assert_code(
        "mapping_after_cutoff",
        lambda: _validate_inputs(late, source, evidence, late_graph),
    )


def test_cross_check_rejects_missing_mapping_listing_fork_and_manifest_fork():
    graph, _, _, events, manifest, snapshot, source, evidence = _fixture()
    missing = deepcopy(snapshot)
    missing["rows"] = [
        item for item in missing["rows"] if item["source_row_id"] != "source-row-sec-aaa"
    ]
    missing = _seal_snapshot(missing)
    missing, missing_source, missing_evidence = _bind_coverage_evidence(missing)
    _assert_code(
        "coverage_active_mapping_set_mismatch",
        lambda: _validate_manifest(
            missing, manifest, events, graph, missing_source, missing_evidence
        ),
        V2UniverseLedgerError,
    )

    fork_graph = deepcopy(graph)
    fork_evidence = fork_graph["evidence"][0]
    fork_mapping = deepcopy(fork_evidence["security_mapping"])
    fork_mapping["listing_id"] = "listing-fork-xnas"
    fork_mapping = _seal_mapping(fork_mapping)
    fork_evidence["security_mapping"] = fork_mapping
    fork_evidence = _seal_evidence(fork_evidence)
    fork_graph["evidence"][0] = fork_evidence
    forked = deepcopy(snapshot)
    target = next(
        item
        for item in forked["rows"]
        if item["security_mapping"] is not None
        and item["security_mapping"]["security_id"] == fork_mapping["security_id"]
    )
    target.update(
        security_mapping=fork_mapping,
        mapping_evidence_semantic_hash=fork_evidence["semantic_hash"],
        mapping_evidence_record_hash=fork_evidence["record_hash"],
    )
    forked = _seal_snapshot(forked)
    _assert_code(
        "coverage_active_mapping_set_mismatch",
        lambda: _validate_manifest(
            forked, manifest, events, fork_graph, source, evidence
        ),
        V2UniverseLedgerError,
    )

    manifest_fork = deepcopy(manifest)
    manifest_fork["manifest_id"] = "different-manifest"
    manifest_fork = _reseal_manifest(manifest_fork)
    _assert_code(
        "coverage_manifest_binding_mismatch",
        lambda: _validate_manifest(
            snapshot, manifest_fork, events, graph, source, evidence
        ),
        V2UniverseLedgerError,
    )


def test_manifest_cross_check_cannot_bypass_input_evidence_validation():
    graph, _, _, events, manifest, snapshot, source, evidence = _fixture()
    fabricated = deepcopy(snapshot)
    fabricated["coverage_evidence_record_hash"] = "f" * 64
    fabricated = _seal_snapshot(fabricated)
    _assert_code(
        "coverage_evidence_binding_mismatch",
        lambda: _validate_manifest(
            fabricated, manifest, events, graph, source, evidence
        ),
        V2UniverseLedgerError,
    )


def test_evidence_backed_known_empty_requires_empty_active_manifest():
    graph, _, _, events, manifest, snapshot, source, evidence = _fixture(empty=True)
    assert _validate_inputs(snapshot, source, evidence, graph)["input_binding_sha256"]
    _assert_code(
        "coverage_active_mapping_set_mismatch",
        lambda: _validate_manifest(
            snapshot, manifest, events, graph, source, evidence
        ),
        V2UniverseLedgerError,
    )

    empty_manifest = _manifest([], _bound_graph()[2], suffix="coverage-empty")
    empty_snapshot = deepcopy(snapshot)
    empty_snapshot.update(
        universe_manifest_id=empty_manifest["manifest_id"],
        universe_manifest_hash=empty_manifest["manifest_hash"],
        membership_as_of=empty_manifest["membership_as_of"],
        data_cutoff=empty_manifest["data_cutoff"],
    )
    empty_snapshot = _seal_snapshot(empty_snapshot)
    binding = _validate_manifest(
        empty_snapshot, empty_manifest, [], graph, source, evidence
    )
    assert binding["active_mapping_count"] == 0
