from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path

import pytest

import quant.v2_universe_ledger_segments as segments_module
from quant.test_v2_contracts import _seal_event
from quant.test_v2_session_clock_contracts import _clock
from quant.test_v2_universe_ledger import (
    _append,
    _bound_graph,
    _manifest,
    _transition_event,
)
from quant.v2_contracts import canonical_hash, canonical_json
from quant.v2_universe_ledger import (
    V2UniverseLedgerError,
    load_v2_universe_ledger,
    read_v2_daily_universe,
    read_v2_replay_universe,
    read_v2_universe_membership,
)
from quant.v2_universe_ledger_segments import (
    append_segmented_v2_universe_batch,
    audit_segmented_v2_universe_ledger_orphans,
    bootstrap_segmented_v2_universe_ledger,
    build_segmented_ledger_contract,
    load_segmented_v2_universe_ledger,
    segmented_record_path,
    validate_segmented_checkpoint,
    validate_segmented_head,
    validate_segmented_segment,
)


def _assert_code(code, call):
    with pytest.raises(V2UniverseLedgerError) as caught:
        call()
    assert caught.value.code == code


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((canonical_json(value) + "\n").encode("utf-8"))


def _write_contract(root, contract):
    root.mkdir(parents=True, exist_ok=True)
    checkpoint = contract["checkpoint"]
    _write_json(
        segmented_record_path(root, "checkpoint", checkpoint["checkpoint_hash"]),
        checkpoint,
    )
    for segment in contract["segments"]:
        _write_json(
            segmented_record_path(root, "segment", segment["segment_hash"]),
            segment,
        )
    _write_json(root / "HEAD.json", contract["head"])


def _three_manifest_ledger(tmp_path):
    graph, bundle, clock, events = _bound_graph(quarantine_second=False)
    path = tmp_path / "legacy.jsonl"
    first = _manifest(events, clock)
    _append(path, events, first, graph=graph, bundle=bundle, clock=clock)

    previous = max(
        (
            event
            for event in events
            if event["security_mapping"]["security_id"] == "sec-aaa"
        ),
        key=lambda event: event["effective_at"],
    )
    future_clock = _clock(
        bundle,
        calendar_session_id="XNYS-2026-08-21",
        assignment_cutoff="2026-08-20T14:20:00Z",
        frozen_at="2026-08-20T14:21:00Z",
        recorded_at="2026-08-20T14:22:00Z",
    )
    transition = _transition_event(
        graph,
        clock,
        previous,
        effective_clock=future_clock,
        effective_at="2026-08-21T13:30:00Z",
    )
    all_events = events + [transition]
    scheduled = _manifest(
        all_events,
        clock,
        previous=first,
        suffix="2",
        effective_clock=future_clock,
        membership_as_of="2026-08-20T14:24:00Z",
        data_cutoff="2026-08-20T14:24:00Z",
        frozen_at="2026-08-20T14:25:00Z",
        recorded_at="2026-08-20T14:26:00Z",
    )
    _append(
        path,
        [transition],
        scheduled,
        graph=graph,
        bundle=bundle,
        clock=clock,
        effective_clock=future_clock,
    )
    activated = _manifest(
        all_events,
        future_clock,
        previous=scheduled,
        suffix="3",
        membership_as_of="2026-08-21T14:00:00Z",
        data_cutoff="2026-08-21T14:00:00Z",
        frozen_at="2026-08-21T14:01:00Z",
        recorded_at="2026-08-21T14:02:00Z",
    )
    _append(
        path,
        [],
        activated,
        graph=graph,
        bundle=bundle,
        clock=future_clock,
    )
    return path, transition


def _segmented_writer_fixture(tmp_path):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    full = load_v2_universe_ledger(legacy_path)
    graph, bundle, clock, _ = _bound_graph(quarantine_second=False)
    future_clock = _clock(
        bundle,
        calendar_session_id="XNYS-2026-08-21",
        assignment_cutoff="2026-08-20T14:20:00Z",
        frozen_at="2026-08-20T14:21:00Z",
        recorded_at="2026-08-20T14:22:00Z",
    )
    first_ids = set(full["manifests"][0]["universe_event_ids"])
    first = {
        "events": [item for item in full["events"] if item["event_id"] in first_ids],
        "manifests": full["manifests"][:1],
    }
    transactions = []
    for manifest in full["manifests"][1:]:
        batch_ids = set(manifest["batch_event_ids"])
        transactions.append(
            (
                [item for item in full["events"] if item["event_id"] in batch_ids],
                manifest,
            )
        )
    return {
        "full": full,
        "first": first,
        "transactions": transactions,
        "graph": graph,
        "bundle": bundle,
        "clock": clock,
        "future_clock": future_clock,
    }


def _append_segmented(root, events, manifest, fixture, *, evidence_records=None):
    run_clock = (
        fixture["clock"]
        if manifest["session_clock_id"] == fixture["clock"]["session_clock_id"]
        else fixture["future_clock"]
    )
    effective_clock = (
        fixture["clock"]
        if manifest["effective_session_clock_id"]
        == fixture["clock"]["session_clock_id"]
        else fixture["future_clock"]
    )
    return append_segmented_v2_universe_batch(
        root,
        events,
        manifest,
        run_clock=run_clock,
        effective_clock=effective_clock,
        evidence_records=(
            fixture["graph"]["evidence"]
            if evidence_records is None
            else evidence_records
        ),
        source_contracts=[fixture["graph"]["source"]],
        run_calendar_sessions=fixture["bundle"]["sessions"],
        run_calendar_evidence=fixture["bundle"]["evidence"],
        run_calendar_source_contract=fixture["bundle"]["source"],
        effective_calendar_sessions=fixture["bundle"]["sessions"],
        effective_calendar_evidence=fixture["bundle"]["evidence"],
        effective_calendar_source_contract=fixture["bundle"]["source"],
    )


def _bootstrap_segmented(root, fixture, *, evidence_records=None):
    return bootstrap_segmented_v2_universe_ledger(
        root,
        fixture["first"]["events"],
        fixture["first"]["manifests"][0],
        run_clock=fixture["clock"],
        effective_clock=fixture["clock"],
        evidence_records=(
            fixture["graph"]["evidence"]
            if evidence_records is None
            else evidence_records
        ),
        source_contracts=[fixture["graph"]["source"]],
        run_calendar_sessions=fixture["bundle"]["sessions"],
        run_calendar_evidence=fixture["bundle"]["evidence"],
        run_calendar_source_contract=fixture["bundle"]["source"],
        effective_calendar_sessions=fixture["bundle"]["sessions"],
        effective_calendar_evidence=fixture["bundle"]["evidence"],
        effective_calendar_source_contract=fixture["bundle"]["source"],
    )


def _reseal(row, hash_field):
    result = deepcopy(row)
    result[hash_field] = canonical_hash(
        {key: value for key, value in result.items() if key != hash_field}
    )
    return result


def test_segmented_load_round_trips_future_event_and_zero_event_activation(tmp_path):
    legacy_path, transition = _three_manifest_ledger(tmp_path)
    legacy = load_v2_universe_ledger(legacy_path)
    contract = build_segmented_ledger_contract(
        legacy, checkpoint_manifest_count=2
    )
    root = tmp_path / "segmented"
    _write_contract(root, contract)

    assert contract["head"]["tail_segment_hash"] == contract["segments"][0][
        "segment_hash"
    ]
    assert contract["segments"][0]["events"] == []
    assert transition["event_id"] in contract["checkpoint"]["identity_state"][
        "pending_future_event_ids"
    ]
    checkpoint_aaa = next(
        item
        for item in contract["checkpoint"]["identity_state"]["memberships"]
        if item["security_id"] == "sec-aaa"
    )
    final_aaa = next(
        item
        for item in legacy["manifests"][-1]["memberships"]
        if item["security_id"] == "sec-aaa"
    )
    assert checkpoint_aaa["state"] == "candidate_eligible"
    assert final_aaa["state"] == "quarantine"
    assert load_segmented_v2_universe_ledger(root) == legacy
    assert read_v2_daily_universe is read_v2_universe_membership
    assert read_v2_replay_universe is read_v2_universe_membership


@pytest.mark.parametrize("damage", ("missing", "tamper", "truncate"))
def test_referenced_segment_damage_fails_without_rollback(tmp_path, damage):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    contract = build_segmented_ledger_contract(
        load_v2_universe_ledger(legacy_path), checkpoint_manifest_count=2
    )
    root = tmp_path / "segmented"
    _write_contract(root, contract)
    segment = contract["segments"][0]
    path = segmented_record_path(root, "segment", segment["segment_hash"])

    if damage == "missing":
        path.unlink()
        code = "segmented_segment_missing"
    elif damage == "tamper":
        changed = deepcopy(segment)
        changed["sequence"] = 9
        _write_json(path, changed)
        code = "segmented_segment_hash_mismatch"
    else:
        path.write_text('{"schema_version":1', encoding="utf-8")
        code = "segmented_segment_invalid"

    _assert_code(code, lambda: load_segmented_v2_universe_ledger(root))


def test_builder_and_loader_conserve_every_physical_event_row(tmp_path):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    legacy = load_v2_universe_ledger(legacy_path)
    duplicate = deepcopy(legacy)
    duplicate["events"].append(deepcopy(legacy["events"][0]))
    _assert_code(
        "segmented_event_population_mismatch",
        lambda: build_segmented_ledger_contract(duplicate),
    )

    contract = build_segmented_ledger_contract(
        legacy, checkpoint_manifest_count=2
    )
    root = tmp_path / "reachable-extra-event"
    _write_contract(root, contract)
    segment = deepcopy(contract["segments"][0])
    segment["events"].append(deepcopy(contract["checkpoint"]["events"][0]))
    segment["after_event_count"] += 1
    segment = _reseal(segment, "segment_hash")
    _assert_code(
        "segmented_event_population_mismatch",
        lambda: validate_segmented_segment(segment),
    )
    _write_json(segmented_record_path(root, "segment", segment["segment_hash"]), segment)
    head = deepcopy(contract["head"])
    head["tail_segment_hash"] = segment["segment_hash"]
    head["event_count"] += 1
    head = _reseal(head, "head_hash")
    _write_json(root / "HEAD.json", head)
    _assert_code(
        "segmented_event_population_mismatch",
        lambda: load_segmented_v2_universe_ledger(root),
    )


@pytest.mark.parametrize(
    ("record_key", "validator", "field", "value", "hash_field", "code"),
    (
        (
            "head",
            validate_segmented_head,
            "schema_version",
            True,
            "head_hash",
            "segmented_record_version_invalid",
        ),
        (
            "checkpoint",
            validate_segmented_checkpoint,
            "trade_enabled",
            0,
            "checkpoint_hash",
            "segmented_boundary_escalation",
        ),
        (
            "segment",
            validate_segmented_segment,
            "paper_live_eligible",
            0,
            "segment_hash",
            "segmented_boundary_escalation",
        ),
    ),
)
def test_segmented_records_reject_boolean_integer_aliases(
    tmp_path, record_key, validator, field, value, hash_field, code
):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    contract = build_segmented_ledger_contract(
        load_v2_universe_ledger(legacy_path), checkpoint_manifest_count=2
    )
    record = (
        contract["segments"][0]
        if record_key == "segment"
        else contract[record_key]
    )
    changed = deepcopy(record)
    changed[field] = value
    changed = _reseal(changed, hash_field)
    _assert_code(code, lambda: validator(changed))


def test_segment_validator_binds_event_batch_universe_and_clocks(tmp_path):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    contract = build_segmented_ledger_contract(
        load_v2_universe_ledger(legacy_path), checkpoint_manifest_count=1
    )
    segment = deepcopy(contract["segments"][0])
    changed_event = deepcopy(segment["events"][0])
    changed_event["event_batch_id"] = "wrong-batch"
    segment["events"][0] = _seal_event(changed_event)
    segment = _reseal(segment, "segment_hash")
    _assert_code(
        "segmented_segment_event_binding_mismatch",
        lambda: validate_segmented_segment(segment),
    )


def test_checkpoint_state_and_head_boundary_tamper_fail_closed(tmp_path):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    legacy = load_v2_universe_ledger(legacy_path)

    checkpoint_contract = build_segmented_ledger_contract(legacy)
    checkpoint = deepcopy(checkpoint_contract["checkpoint"])
    checkpoint["identity_state"]["event_identities"] = []
    checkpoint = _reseal(checkpoint, "checkpoint_hash")
    _assert_code(
        "segmented_checkpoint_state_mismatch",
        lambda: validate_segmented_checkpoint(checkpoint),
    )
    head = deepcopy(checkpoint_contract["head"])
    head["checkpoint_hash"] = checkpoint["checkpoint_hash"]
    head = _reseal(head, "head_hash")
    root = tmp_path / "checkpoint-tamper"
    _write_json(
        segmented_record_path(root, "checkpoint", checkpoint["checkpoint_hash"]),
        checkpoint,
    )
    _write_json(root / "HEAD.json", head)
    _assert_code(
        "segmented_checkpoint_state_mismatch",
        lambda: load_segmented_v2_universe_ledger(root),
    )

    boundary_contract = build_segmented_ledger_contract(legacy)
    root = tmp_path / "head-escalation"
    _write_contract(root, boundary_contract)
    escalated = deepcopy(boundary_contract["head"])
    escalated["trade_enabled"] = True
    escalated = _reseal(escalated, "head_hash")
    _write_json(root / "HEAD.json", escalated)
    _assert_code(
        "segmented_boundary_escalation",
        lambda: load_segmented_v2_universe_ledger(root),
    )


def test_missing_or_truncated_head_and_checkpoint_never_fall_back(tmp_path):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    contract = build_segmented_ledger_contract(load_v2_universe_ledger(legacy_path))
    root = tmp_path / "segmented"
    _write_contract(root, contract)

    (root / "HEAD.json").unlink()
    _assert_code(
        "segmented_head_missing", lambda: load_segmented_v2_universe_ledger(root)
    )
    _write_json(root / "HEAD.json", contract["head"])
    checkpoint_path = segmented_record_path(
        root, "checkpoint", contract["checkpoint"]["checkpoint_hash"]
    )
    checkpoint_path.write_text('{"schema_version":1', encoding="utf-8")
    _assert_code(
        "segmented_checkpoint_invalid",
        lambda: load_segmented_v2_universe_ledger(root),
    )


def test_reordered_tail_chain_fails_and_unreferenced_orphan_is_invisible(tmp_path):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    legacy = load_v2_universe_ledger(legacy_path)
    contract = build_segmented_ledger_contract(
        legacy, checkpoint_manifest_count=1
    )
    root = tmp_path / "segmented"
    _write_contract(root, contract)

    orphan = deepcopy(contract["segments"][0])
    orphan["previous_segment_hash"] = "f" * 64
    orphan = _reseal(orphan, "segment_hash")
    validate_segmented_segment(orphan)
    orphan_hash = orphan["segment_hash"]
    orphan_path = segmented_record_path(root, "segment", orphan_hash)
    _write_json(orphan_path, orphan)
    assert load_segmented_v2_universe_ledger(root) == legacy
    audit = audit_segmented_v2_universe_ledger_orphans(root)
    assert audit["orphan_files"] == [f"segments/{orphan_hash}.json"]
    assert audit["trade_enabled"] is False

    tail = deepcopy(contract["segments"][-1])
    tail["previous_segment_hash"] = None
    tail = _reseal(tail, "segment_hash")
    _write_json(segmented_record_path(root, "segment", tail["segment_hash"]), tail)
    head = deepcopy(contract["head"])
    head["tail_segment_hash"] = tail["segment_hash"]
    head = _reseal(head, "head_hash")
    _write_json(root / "HEAD.json", head)
    _assert_code(
        "segmented_segment_chain_mismatch",
        lambda: load_segmented_v2_universe_ledger(root),
    )


def test_referenced_records_require_exact_canonical_bytes(tmp_path):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    contract = build_segmented_ledger_contract(
        load_v2_universe_ledger(legacy_path), checkpoint_manifest_count=2
    )
    root = tmp_path / "segmented"
    _write_contract(root, contract)
    segment = contract["segments"][0]
    path = segmented_record_path(root, "segment", segment["segment_hash"])
    path.write_text("  " + canonical_json(segment) + "\n", encoding="utf-8")
    _assert_code(
        "segmented_segment_noncanonical_bytes",
        lambda: load_segmented_v2_universe_ledger(root),
    )

    _write_contract(root, contract)
    (root / "HEAD.json").write_bytes(
        (canonical_json(contract["head"]) + "\r\n").encode("utf-8")
    )
    _assert_code(
        "segmented_head_noncanonical_bytes",
        lambda: load_segmented_v2_universe_ledger(root),
    )


def test_nonfinite_json_stays_inside_segment_error_surface(tmp_path):
    legacy_path, _ = _three_manifest_ledger(tmp_path)
    legacy = load_v2_universe_ledger(legacy_path)
    malformed_view = deepcopy(legacy)
    malformed_view["events"][0]["known_at"] = float("nan")
    _assert_code(
        "invalid_json_value",
        lambda: build_segmented_ledger_contract(malformed_view),
    )

    contract = build_segmented_ledger_contract(legacy)
    root = tmp_path / "segmented"
    _write_contract(root, contract)
    malformed_head = deepcopy(contract["head"])
    malformed_head["event_count"] = float("nan")
    (root / "HEAD.json").write_text(
        json.dumps(
            malformed_head,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _assert_code(
        "segmented_head_invalid",
        lambda: load_segmented_v2_universe_ledger(root),
    )


def test_checked_in_sec_ledger_identity_is_unchanged(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    legacy_path = (
        repo_root
        / "data"
        / "v2"
        / "universe"
        / "sec_edgar_8k"
        / "20260820"
        / "20260821T125627Z"
        / "universe_ledger.jsonl"
    )
    legacy = load_v2_universe_ledger(legacy_path)
    contract = build_segmented_ledger_contract(legacy)
    root = tmp_path / "sec-segmented"
    _write_contract(root, contract)

    reconstructed = load_segmented_v2_universe_ledger(root)
    manifest = reconstructed["manifests"][-1]
    assert reconstructed == legacy
    assert manifest["manifest_hash"] == (
        "852f1eae21701bd52d3fe3519f4b9d5fc6909fff0266f2d1c958ac39e4bb0fac"
    )
    assert manifest["universe_event_semantic_snapshot_sha256"] == (
        "437e640b39fdaf4da0db20ba91efbf434f8bc9906b40c52c973002073665ba6d"
    )
    assert manifest["universe_event_record_snapshot_sha256"] == (
        "427ebbbc70625fbaa648619619a49a02ce3c1c321305796d1c3978e4b99de466"
    )
    assert manifest["membership_snapshot_sha256"] == (
        "e8663c0049b74e19397a475026c3efdca193b5f2929e84ba78e2f75803c0dd38"
    )


def test_writer_bootstraps_appends_zero_event_segment_and_retries_exactly(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "writer"

    first = _bootstrap_segmented(root, fixture)
    retry_bootstrap = _bootstrap_segmented(root, fixture)
    assert first["status"] == "bootstrapped"
    assert retry_bootstrap["status"] == "duplicate"
    head_bytes = (root / "HEAD.json").read_bytes()
    assert head_bytes.endswith(b"\n")
    assert b"\r\n" not in head_bytes
    checkpoint_path = segmented_record_path(
        root, "checkpoint", first["checkpoint_hash"]
    )
    checkpoint_bytes = checkpoint_path.read_bytes()

    second_events, second_manifest = fixture["transactions"][0]
    second = _append_segmented(
        root, second_events, second_manifest, fixture
    )
    second_retry = _append_segmented(
        root, second_events, second_manifest, fixture
    )
    assert second["status"] == "appended"
    assert second["event_rows_written"] == 1
    assert second_retry["status"] == "duplicate"
    assert second_retry["segment_hash"] is None
    assert second_retry["head_hash"] == second["head_hash"]

    third_events, third_manifest = fixture["transactions"][1]
    third = _append_segmented(root, third_events, third_manifest, fixture)
    assert third["status"] == "appended"
    assert third["event_rows_written"] == 0
    assert checkpoint_path.read_bytes() == checkpoint_bytes
    assert len(list((root / "segments").glob("*.json"))) == 2
    assert load_segmented_v2_universe_ledger(root) == fixture["full"]


def test_append_requires_head_and_reuses_legacy_m1_guards(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    events, manifest = fixture["transactions"][0]
    rejected_bootstrap = tmp_path / "rejected-bootstrap"
    _assert_code(
        "unresolved_evidence_id",
        lambda: _bootstrap_segmented(
            rejected_bootstrap, fixture, evidence_records=[]
        ),
    )
    assert not (rejected_bootstrap / "HEAD.json").exists()
    assert not (rejected_bootstrap / "checkpoints").exists()

    _assert_code(
        "segmented_head_missing",
        lambda: _append_segmented(
            tmp_path / "missing-head", events, manifest, fixture
        ),
    )

    root = tmp_path / "guarded"
    _bootstrap_segmented(root, fixture)
    old_head = (root / "HEAD.json").read_bytes()
    _assert_code(
        "unresolved_evidence_id",
        lambda: _append_segmented(
            root, events, manifest, fixture, evidence_records=[]
        ),
    )
    assert (root / "HEAD.json").read_bytes() == old_head
    assert not (root / "segments").exists()


def test_immutable_segment_collision_never_overwrites_or_moves_head(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "collision"
    first = _bootstrap_segmented(root, fixture)
    old_head = (root / "HEAD.json").read_bytes()
    planned = build_segmented_ledger_contract(
        fixture["full"], checkpoint_manifest_count=1
    )["segments"][0]
    collision_path = segmented_record_path(root, "segment", planned["segment_hash"])
    collision_path.parent.mkdir(parents=True, exist_ok=True)
    collision_path.write_bytes(b"different immutable bytes\n")
    events, manifest = fixture["transactions"][0]

    _assert_code(
        "segmented_segment_collision",
        lambda: _append_segmented(root, events, manifest, fixture),
    )
    assert (root / "HEAD.json").read_bytes() == old_head
    assert collision_path.read_bytes() == b"different immutable bytes\n"
    assert load_segmented_v2_universe_ledger(root) == fixture["first"]
    assert first["checkpoint_hash"] == json.loads(old_head)["checkpoint_hash"]


def test_head_write_failure_leaves_orphan_and_exact_retry_adopts_only_it(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "head-failure"
    _bootstrap_segmented(root, fixture)
    old_head = (root / "HEAD.json").read_bytes()
    events, manifest = fixture["transactions"][0]
    real_replace = segments_module._replace_with_retry

    def fail_replace(_source, _target):
        raise OSError("simulated HEAD replace failure")

    monkeypatch.setattr(segments_module, "_replace_with_retry", fail_replace)
    _assert_code(
        "segmented_head_write_failed",
        lambda: _append_segmented(root, events, manifest, fixture),
    )
    assert (root / "HEAD.json").read_bytes() == old_head
    audit = audit_segmented_v2_universe_ledger_orphans(root)
    assert audit["orphan_count"] == 1

    monkeypatch.setattr(segments_module, "_replace_with_retry", real_replace)
    retry = _append_segmented(root, events, manifest, fixture)
    assert retry["status"] == "appended"
    assert retry["segment_reused"] is True
    assert audit_segmented_v2_universe_ledger_orphans(root)["orphan_count"] == 0


def test_bootstrap_head_failure_reuses_only_exact_checkpoint_orphan(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "bootstrap-head-failure"
    real_replace = segments_module._replace_with_retry

    def fail_replace(_source, _target):
        raise OSError("simulated failure")

    monkeypatch.setattr(segments_module, "_replace_with_retry", fail_replace)
    _assert_code("segmented_head_write_failed", lambda: _bootstrap_segmented(root, fixture))
    assert not (root / "HEAD.json").exists()
    assert len(list((root / "checkpoints").glob("*.json"))) == 1
    assert not (root / "segments").exists()

    monkeypatch.setattr(segments_module, "_replace_with_retry", real_replace)
    retry = _bootstrap_segmented(root, fixture)
    assert retry["status"] == "bootstrapped"
    assert retry["checkpoint_reused"] is True
    assert load_segmented_v2_universe_ledger(root) == fixture["first"]


def test_retry_after_head_committed_then_error_is_duplicate(tmp_path, monkeypatch):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "post-head-error"
    _bootstrap_segmented(root, fixture)
    events, manifest = fixture["transactions"][0]
    real_replace = segments_module._replace_with_retry

    def commit_then_raise(source, target):
        real_replace(source, target)
        raise OSError("simulated error after commit point")

    monkeypatch.setattr(segments_module, "_replace_with_retry", commit_then_raise)
    _assert_code(
        "segmented_head_write_failed",
        lambda: _append_segmented(root, events, manifest, fixture),
    )
    assert load_segmented_v2_universe_ledger(root)["manifests"] == fixture["full"][
        "manifests"
    ][:2]

    monkeypatch.setattr(segments_module, "_replace_with_retry", real_replace)
    retry = _append_segmented(root, events, manifest, fixture)
    assert retry["status"] == "duplicate"
    assert len(list((root / "segments").glob("*.json"))) == 1


def test_changed_head_fails_predecessor_identity_check(tmp_path, monkeypatch):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "stale-head"
    _bootstrap_segmented(root, fixture)
    old_head_row = json.loads((root / "HEAD.json").read_bytes())
    concurrent_head = deepcopy(old_head_row)
    concurrent_head["head_manifest_id"] = "simulated-concurrent-head"
    concurrent_head = _reseal(concurrent_head, "head_hash")
    concurrent_bytes = (canonical_json(concurrent_head) + "\n").encode("utf-8")
    real_publish = segments_module._publish_immutable_record

    def publish_then_change_head(path, value, *, role):
        reused = real_publish(path, value, role=role)
        if role == "segment":
            _write_json(root / "HEAD.json", concurrent_head)
        return reused

    monkeypatch.setattr(
        segments_module, "_publish_immutable_record", publish_then_change_head
    )
    events, manifest = fixture["transactions"][0]
    _assert_code(
        "segmented_stale_head",
        lambda: _append_segmented(root, events, manifest, fixture),
    )
    assert (root / "HEAD.json").read_bytes() == concurrent_bytes

    _write_json(root / "HEAD.json", old_head_row)
    assert audit_segmented_v2_universe_ledger_orphans(root)["orphan_count"] == 1


def test_missing_head_cannot_roll_back_a_store_with_segments(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "missing-committed-head"
    _bootstrap_segmented(root, fixture)
    events, manifest = fixture["transactions"][0]
    _append_segmented(root, events, manifest, fixture)
    immutable_before = {
        item.relative_to(root).as_posix(): item.read_bytes()
        for directory in (root / "checkpoints", root / "segments")
        for item in directory.glob("*.json")
    }
    (root / "HEAD.json").unlink()

    _assert_code(
        "segmented_bootstrap_orphan_conflict",
        lambda: _bootstrap_segmented(root, fixture),
    )
    assert not (root / "HEAD.json").exists()
    assert {
        item.relative_to(root).as_posix(): item.read_bytes()
        for directory in (root / "checkpoints", root / "segments")
        for item in directory.glob("*.json")
    } == immutable_before


def test_cooperative_same_batch_writers_serialize_to_append_and_duplicate(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "concurrent"
    _bootstrap_segmented(root, fixture)
    events, manifest = fixture["transactions"][0]

    def append_once(_):
        return _append_segmented(root, events, manifest, fixture)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(append_once, range(2)))
    assert sorted(item["status"] for item in results) == ["appended", "duplicate"]
    assert len(list((root / "segments").glob("*.json"))) == 1
    assert load_segmented_v2_universe_ledger(root)["manifests"] == fixture["full"][
        "manifests"
    ][:2]
