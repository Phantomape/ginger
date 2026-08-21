from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from threading import Event
from time import perf_counter
import tracemalloc

import pytest

import quant.v2_universe_ledger_segments as segments_module
from quant.test_v2_contracts import _seal_event
from quant.test_v2_session_clock_contracts import _clock
from quant.test_v2_universe_ledger import (
    _append,
    _bound_graph,
    _manifest,
    _reseal_manifest,
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
    COMPACT_HEAD_STORAGE_CONTRACT,
    STORAGE_CONTRACT,
    append_segmented_v2_universe_batch,
    audit_segmented_v2_universe_ledger_orphans,
    bootstrap_segmented_v2_universe_ledger,
    build_segmented_ledger_contract,
    load_segmented_v2_universe_state,
    load_segmented_v2_universe_ledger,
    rotate_segmented_v2_universe_checkpoint,
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


def _append_segmented(
    root,
    events,
    manifest,
    fixture,
    *,
    evidence_records=None,
    run_clock=None,
    effective_clock=None,
):
    if run_clock is None:
        run_clock = (
            fixture["clock"]
            if manifest["session_clock_id"]
            == fixture["clock"]["session_clock_id"]
            else fixture["future_clock"]
        )
    if effective_clock is None:
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


def _write_three_manifest_segmented(root, fixture):
    _bootstrap_segmented(root, fixture)
    for events, manifest in fixture["transactions"]:
        _append_segmented(root, events, manifest, fixture)
    assert load_segmented_v2_universe_ledger(root) == fixture["full"]


def _cold_scale_history(fixture):
    manifests = list(fixture["full"]["manifests"])
    for suffix, membership_as_of, frozen_at, recorded_at in (
        (
            "4-cold-scale",
            "2026-08-21T14:03:00Z",
            "2026-08-21T14:04:00Z",
            "2026-08-21T14:05:00Z",
        ),
        (
            "5-cold-scale",
            "2026-08-21T14:06:00Z",
            "2026-08-21T14:07:00Z",
            "2026-08-21T14:08:00Z",
        ),
    ):
        manifests.append(
            _manifest(
                fixture["full"]["events"],
                fixture["future_clock"],
                previous=manifests[-1],
                suffix=suffix,
                graph=fixture["graph"],
                bundle=fixture["bundle"],
                membership_as_of=membership_as_of,
                data_cutoff=membership_as_of,
                frozen_at=frozen_at,
                recorded_at=recorded_at,
            )
        )
    return {
        "events": fixture["full"]["events"],
        "manifests": manifests,
    }, [
        *fixture["transactions"],
        ([], manifests[-2]),
        ([], manifests[-1]),
    ]


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

    assert contract["head"]["storage_contract"] == STORAGE_CONTRACT
    assert contract["checkpoint"]["storage_contract"] == STORAGE_CONTRACT
    assert all(
        segment["storage_contract"] == STORAGE_CONTRACT
        for segment in contract["segments"]
    )
    legacy_state = load_segmented_v2_universe_state(root)
    assert legacy_state["storage_contract"] == STORAGE_CONTRACT
    assert legacy_state["legacy_full_reader_compatible"] is True
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

    rotate_segmented_v2_universe_checkpoint(root)
    assert load_segmented_v2_universe_ledger(root) == legacy
    compact_state = load_segmented_v2_universe_state(root)
    assert compact_state["head_manifest"] == manifest
    assert compact_state["event_count"] == 111
    assert compact_state["manifest_count"] == 1


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


def test_immutable_collision_rejects_symlink_before_reading_target(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "collision-symlink"
    _bootstrap_segmented(root, fixture)
    old_head = (root / "HEAD.json").read_bytes()
    planned = build_segmented_ledger_contract(
        fixture["full"], checkpoint_manifest_count=1
    )["segments"][0]
    collision_path = segmented_record_path(
        root, "segment", planned["segment_hash"]
    )
    collision_path.parent.mkdir(parents=True, exist_ok=True)
    external = tmp_path / "external-collision-target.json"
    external.write_bytes(b"external bytes must not be read or changed\n")
    try:
        collision_path.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"file symlinks unavailable: {exc}")
    real_read_bytes = Path.read_bytes

    def reject_collision_read(path):
        if path == collision_path:
            raise AssertionError("immutable collision followed a symlink")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_collision_read)
    events, manifest = fixture["transactions"][0]

    _assert_code(
        "segmented_segment_collision",
        lambda: _append_segmented(root, events, manifest, fixture),
    )
    assert external.read_bytes() == b"external bytes must not be read or changed\n"
    assert (root / "HEAD.json").read_bytes() == old_head


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


def test_rotation_compacts_three_manifest_history_without_logical_drift(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotated"
    _write_three_manifest_segmented(root, fixture)
    before = load_segmented_v2_universe_ledger(root)
    old_head = json.loads((root / "HEAD.json").read_bytes())
    old_files = {
        segmented_record_path(root, "checkpoint", old_head["checkpoint_hash"])
        .relative_to(root)
        .as_posix(),
        *(
            item.relative_to(root).as_posix()
            for item in (root / "segments").glob("*.json")
        ),
    }

    rotated = rotate_segmented_v2_universe_checkpoint(root)

    assert rotated["status"] == "rotated"
    assert rotated["old_checkpoint_hash"] == old_head["checkpoint_hash"]
    assert rotated["event_count"] == len(before["events"])
    assert rotated["manifest_count"] == len(before["manifests"])
    assert load_segmented_v2_universe_ledger(root) == before == fixture["full"]
    new_head = json.loads((root / "HEAD.json").read_bytes())
    assert new_head["head_hash"] == rotated["head_hash"]
    assert new_head["checkpoint_hash"] == rotated["new_checkpoint_hash"]
    assert new_head["tail_segment_hash"] is None
    assert old_head["storage_contract"] == STORAGE_CONTRACT
    assert new_head["storage_contract"] == COMPACT_HEAD_STORAGE_CONTRACT
    compact_path = segmented_record_path(
        root, "checkpoint", rotated["new_checkpoint_hash"]
    )
    compact = json.loads(compact_path.read_bytes())
    assert compact["storage_contract"] == STORAGE_CONTRACT
    assert compact["head_manifest"] == before["manifests"][-1]
    assert "manifests" not in compact

    audit = audit_segmented_v2_universe_ledger_orphans(root)
    assert audit["orphan_count"] == 0
    assert audit["orphan_files"] == []
    assert audit["superseded_count"] == len(old_files)
    assert set(audit["superseded_files"]) == old_files
    assert all((root / relative).is_file() for relative in old_files)


@pytest.mark.parametrize("compact", (False, True))
def test_head_storage_marker_must_match_checkpoint_format(tmp_path, compact):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / f"marker-mismatch-{compact}"
    _write_three_manifest_segmented(root, fixture)
    if compact:
        rotate_segmented_v2_universe_checkpoint(root)

    head = json.loads((root / "HEAD.json").read_bytes())
    head["storage_contract"] = (
        STORAGE_CONTRACT if compact else COMPACT_HEAD_STORAGE_CONTRACT
    )
    _write_json(root / "HEAD.json", _reseal(head, "head_hash"))

    _assert_code(
        "segmented_head_storage_contract_mismatch",
        lambda: load_segmented_v2_universe_state(root),
    )


def test_unknown_head_storage_marker_fails_before_checkpoint_load(tmp_path, monkeypatch):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "unknown-head-marker"
    _write_three_manifest_segmented(root, fixture)
    head = json.loads((root / "HEAD.json").read_bytes())
    head["storage_contract"] = "v2_universe_checkpoint_segment_sidecar_future"
    _write_json(root / "HEAD.json", _reseal(head, "head_hash"))

    real_read_json = segments_module._read_json

    def reject_checkpoint_load(path, *, role):
        if role == "checkpoint":
            raise AssertionError("unknown HEAD capability opened a checkpoint")
        return real_read_json(path, role=role)

    monkeypatch.setattr(segments_module, "_read_json", reject_checkpoint_load)
    _assert_code(
        "segmented_storage_contract_invalid",
        lambda: load_segmented_v2_universe_state(root),
    )


def test_audit_reports_symlink_entries_as_invalid_without_following_them(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "audit-symlink"
    bootstrapped = _bootstrap_segmented(root, fixture)
    checkpoint_path = segmented_record_path(
        root, "checkpoint", bootstrapped["checkpoint_hash"]
    )
    link_path = checkpoint_path.with_name("unreferenced-link.json")
    external_segments = tmp_path / "external-segments"
    external_segments.mkdir()
    segment_directory_link = root / "segments"
    try:
        link_path.symlink_to(checkpoint_path.name)
        segment_directory_link.symlink_to(
            external_segments, target_is_directory=True
        )
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    real_is_symlink = Path.is_symlink

    def junction_like_is_symlink(path):
        if path == segment_directory_link:
            return False
        return real_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", junction_like_is_symlink)

    audit = audit_segmented_v2_universe_ledger_orphans(root)

    assert audit["invalid_files"] == [
        "checkpoints/unreferenced-link.json",
        "segments",
    ]
    assert audit["invalid_count"] == 2
    assert audit["orphan_count"] == 0
    assert audit["superseded_count"] == 0


def test_audit_reports_non_directory_storage_entry_as_invalid(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "audit-storage-file"
    _bootstrap_segmented(root, fixture)
    (root / "segments").write_bytes(b"not a directory\n")

    audit = audit_segmented_v2_universe_ledger_orphans(root)

    assert audit["invalid_files"] == ["segments"]
    assert audit["invalid_count"] == 1


def test_rotation_rejects_storage_directory_link_without_external_write(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-directory-link"
    _write_three_manifest_segmented(root, fixture)
    old_head = (root / "HEAD.json").read_bytes()
    checkpoint_directory = root / "checkpoints"
    external_directory = tmp_path / "outside-checkpoints"
    checkpoint_directory.rename(external_directory)
    try:
        checkpoint_directory.symlink_to(
            external_directory, target_is_directory=True
        )
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")
    external_files = sorted(external_directory.glob("*.json"))

    _assert_code(
        "segmented_storage_directory_invalid",
        lambda: rotate_segmented_v2_universe_checkpoint(root),
    )

    assert sorted(external_directory.glob("*.json")) == external_files
    assert (root / "HEAD.json").read_bytes() == old_head


def test_rotation_rejects_lock_symlink_without_touching_external_target(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-lock-link"
    _write_three_manifest_segmented(root, fixture)
    old_head = (root / "HEAD.json").read_bytes()
    lock_path = root / "HEAD.json.lock"
    lock_path.unlink()
    external_lock = tmp_path / "external-lock-target"
    external_lock.write_bytes(b"")
    try:
        lock_path.symlink_to(external_lock)
    except OSError as exc:
        pytest.skip(f"file symlinks unavailable: {exc}")

    _assert_code(
        "segmented_lock_path_invalid",
        lambda: rotate_segmented_v2_universe_checkpoint(root),
    )

    assert external_lock.read_bytes() == b""
    assert (root / "HEAD.json").read_bytes() == old_head


def test_append_after_rotation_restarts_segment_sequence_and_keeps_logical_count(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotated-append"
    _write_three_manifest_segmented(root, fixture)
    rotated = rotate_segmented_v2_universe_checkpoint(root)
    fourth_manifest = _manifest(
        fixture["full"]["events"],
        fixture["future_clock"],
        previous=fixture["full"]["manifests"][-1],
        suffix="4",
        graph=fixture["graph"],
        bundle=fixture["bundle"],
        membership_as_of="2026-08-21T14:03:00Z",
        data_cutoff="2026-08-21T14:03:00Z",
        frozen_at="2026-08-21T14:04:00Z",
        recorded_at="2026-08-21T14:05:00Z",
    )

    def reject_archive_load(*_args, **_kwargs):
        raise AssertionError("fresh append traversed archived generations")

    monkeypatch.setattr(
        segments_module, "_load_reachable_store", reject_archive_load
    )

    appended = _append_segmented(root, [], fourth_manifest, fixture)

    assert appended["status"] == "appended"
    assert appended["manifest_count"] == 4
    segment = json.loads(
        segmented_record_path(root, "segment", appended["segment_hash"]).read_bytes()
    )
    assert segment["checkpoint_hash"] == rotated["new_checkpoint_hash"]
    assert segment["sequence"] == 1
    assert segment["storage_contract"] == STORAGE_CONTRACT
    assert segment["previous_segment_hash"] is None
    assert segment["before_manifest_count"] == 3
    assert segment["after_manifest_count"] == 4
    state = load_segmented_v2_universe_state(root)
    assert state["manifest_count"] == 4
    assert state["current_generation_manifest_count"] == 2
    assert state["head_manifest"] == fourth_manifest
    assert state["storage_contract"] == COMPACT_HEAD_STORAGE_CONTRACT
    assert state["legacy_full_reader_compatible"] is False


def test_pending_future_event_activates_through_zero_event_append_after_rotation(
    tmp_path,
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotated-pending"
    _bootstrap_segmented(root, fixture)
    scheduled_events, scheduled_manifest = fixture["transactions"][0]
    _append_segmented(
        root, scheduled_events, scheduled_manifest, fixture
    )
    pending = load_segmented_v2_universe_ledger(root)

    rotate_segmented_v2_universe_checkpoint(root)
    activated_events, activated_manifest = fixture["transactions"][1]
    appended = _append_segmented(
        root, activated_events, activated_manifest, fixture
    )

    assert activated_events == []
    assert appended["status"] == "appended"
    assert load_segmented_v2_universe_ledger(root) == fixture["full"]
    assert pending["manifests"][-1]["membership_snapshot_sha256"] != (
        activated_manifest["membership_snapshot_sha256"]
    )


def test_historical_retry_recognizes_events_committed_in_compact_tail(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotated-tail-event-retry"
    _bootstrap_segmented(root, fixture)
    rotate_segmented_v2_universe_checkpoint(root)
    previous = max(
        (
            item
            for item in fixture["first"]["events"]
            if item["security_mapping"]["security_id"] == "sec-bbb"
        ),
        key=lambda item: item["effective_at"],
    )
    bbb_evidence = next(
        item
        for item in fixture["graph"]["evidence"]
        if item["security_mapping"]["security_id"] == "sec-bbb"
    )
    tail_event = _transition_event(
        {**fixture["graph"], "evidence": [bbb_evidence]},
        fixture["clock"],
        previous,
        suffix="tail-retry",
    )
    tail_manifest = _manifest(
        [*fixture["first"]["events"], tail_event],
        fixture["clock"],
        previous=fixture["first"]["manifests"][0],
        suffix="tail-retry",
        graph=fixture["graph"],
        bundle=fixture["bundle"],
        membership_as_of="2026-08-20T14:26:00Z",
        data_cutoff="2026-08-20T14:26:00Z",
        frozen_at="2026-08-20T14:27:00Z",
        recorded_at="2026-08-20T14:28:00Z",
    )
    _append_segmented(root, [tail_event], tail_manifest, fixture)

    def reject_archive_load(*_args, **_kwargs):
        raise AssertionError("historical retry traversed archived generations")

    monkeypatch.setattr(
        segments_module, "_load_reachable_store", reject_archive_load
    )
    retried = _append_segmented(
        root,
        [tail_event],
        fixture["first"]["manifests"][0],
        fixture,
    )

    assert retried["status"] == "duplicate"
    changed_tail_event = deepcopy(tail_event)
    changed_tail_event["reason"] = "Changed semantics for the same tail event ID."
    changed_tail_event = _seal_event(changed_tail_event)
    _assert_code(
        "universe_event_id_conflict",
        lambda: _append_segmented(
            root,
            [changed_tail_event],
            fixture["first"]["manifests"][0],
            fixture,
        ),
    )

    unseen_event = deepcopy(tail_event)
    unseen_event["event_id"] = "sec-bbb-unseen-request-duplicate"
    unseen_event = _seal_event(unseen_event)
    changed_unseen_event = deepcopy(unseen_event)
    changed_unseen_event["reason"] = "Conflicting duplicate inside one request."
    changed_unseen_event = _seal_event(changed_unseen_event)
    _assert_code(
        "universe_event_id_conflict",
        lambda: _append_segmented(
            root,
            [unseen_event, changed_unseen_event],
            fixture["first"]["manifests"][0],
            fixture,
        ),
    )


def test_fresh_manifest_input_error_precedes_historical_batch_conflict(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotated-error-order"
    _write_three_manifest_segmented(root, fixture)
    rotate_segmented_v2_universe_checkpoint(root)
    proposed = _manifest(
        fixture["full"]["events"],
        fixture["future_clock"],
        previous=fixture["full"]["manifests"][-1],
        suffix="fresh-error-order",
        graph=fixture["graph"],
        bundle=fixture["bundle"],
        membership_as_of="2026-08-21T14:03:00Z",
        data_cutoff="2026-08-21T14:03:00Z",
        frozen_at="2026-08-21T14:04:00Z",
        recorded_at="2026-08-21T14:05:00Z",
    )
    proposed["event_batch_id"] = fixture["full"]["manifests"][0][
        "event_batch_id"
    ]
    proposed["source_contract_registry"]["uncommitted-source"] = "a" * 64
    proposed = _reseal_manifest(proposed)

    _assert_code(
        "manifest_input_registry_mismatch",
        lambda: _append_segmented(root, [], proposed, fixture),
    )


def test_rotation_preserves_valid_cross_batch_physical_event_order(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "cross-batch-event-order"
    _bootstrap_segmented(root, fixture)
    future_events, future_manifest = fixture["transactions"][0]
    _append_segmented(root, future_events, future_manifest, fixture)
    current = load_segmented_v2_universe_ledger(root)
    previous = max(
        (
            item
            for item in current["events"]
            if item["security_mapping"]["security_id"] == "sec-bbb"
        ),
        key=lambda item: item["effective_at"],
    )
    bbb_evidence = next(
        item
        for item in fixture["graph"]["evidence"]
        if item["security_mapping"]["security_id"] == "sec-bbb"
    )
    earlier_effective_event = _transition_event(
        {**fixture["graph"], "evidence": [bbb_evidence]},
        fixture["clock"],
        previous,
        suffix="cross-batch-order",
        decided_at="2026-08-20T14:27:00Z",
        recorded_at="2026-08-20T14:28:00Z",
        effective_at="2026-08-20T14:30:00Z",
    )
    reordered_manifest = _manifest(
        [*current["events"], earlier_effective_event],
        fixture["clock"],
        previous=future_manifest,
        suffix="cross-batch-order",
        graph=fixture["graph"],
        bundle=fixture["bundle"],
        membership_as_of="2026-08-20T14:31:00Z",
        data_cutoff="2026-08-20T14:31:00Z",
        frozen_at="2026-08-20T14:32:00Z",
        recorded_at="2026-08-20T14:33:00Z",
    )
    _append_segmented(
        root, [earlier_effective_event], reordered_manifest, fixture
    )
    before = load_segmented_v2_universe_ledger(root)
    assert before["events"][-2]["effective_at"] > before["events"][-1][
        "effective_at"
    ]

    assert rotate_segmented_v2_universe_checkpoint(root)["status"] == "rotated"
    assert load_segmented_v2_universe_ledger(root) == before


def test_rotation_and_append_share_one_serial_commit_order(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotate-append-concurrent"
    _bootstrap_segmented(root, fixture)
    scheduled_events, scheduled_manifest = fixture["transactions"][0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        rotate_future = pool.submit(
            rotate_segmented_v2_universe_checkpoint, root
        )
        append_future = pool.submit(
            _append_segmented,
            root,
            scheduled_events,
            scheduled_manifest,
            fixture,
        )
        rotated = rotate_future.result()
        appended = append_future.result()

    assert rotated["status"] == "rotated"
    assert appended["status"] == "appended"
    assert load_segmented_v2_universe_ledger(root) == {
        "events": fixture["full"]["events"],
        "manifests": fixture["full"]["manifests"][:2],
    }


def test_rotation_waits_for_one_snapshot_consistent_audit(tmp_path, monkeypatch):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "audit-rotation-concurrent"
    _write_three_manifest_segmented(root, fixture)
    audit_started = Event()
    release_audit = Event()
    real_hot_load = segments_module._load_hot_store

    def pause_hot_load(*args, **kwargs):
        loaded = real_hot_load(*args, **kwargs)
        audit_started.set()
        assert release_audit.wait(timeout=5)
        return loaded

    monkeypatch.setattr(segments_module, "_load_hot_store", pause_hot_load)
    with ThreadPoolExecutor(max_workers=2) as pool:
        audit_future = pool.submit(
            audit_segmented_v2_universe_ledger_orphans, root
        )
        assert audit_started.wait(timeout=5)
        rotation_future = pool.submit(
            rotate_segmented_v2_universe_checkpoint, root
        )
        assert not rotation_future.done()
        release_audit.set()
        audit = audit_future.result()
        rotated = rotation_future.result()

    assert audit["orphan_count"] == 0
    assert audit["superseded_count"] == 0
    assert audit["invalid_count"] == 0
    assert rotated["status"] == "rotated"
    assert load_segmented_v2_universe_ledger(root) == fixture["full"]


def test_cooperative_rotations_commit_once(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "concurrent-rotation"
    _write_three_manifest_segmented(root, fixture)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: rotate_segmented_v2_universe_checkpoint(root),
                range(2),
            )
        )

    assert sorted(item["status"] for item in results) == [
        "already_compact",
        "rotated",
    ]
    assert load_segmented_v2_universe_ledger(root) == fixture["full"]


def test_second_rotation_preserves_iterative_archival_history(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "second-rotation"
    _write_three_manifest_segmented(root, fixture)
    first_rotation = rotate_segmented_v2_universe_checkpoint(root)
    fourth_manifest = _manifest(
        fixture["full"]["events"],
        fixture["future_clock"],
        previous=fixture["full"]["manifests"][-1],
        suffix="4-second-rotation",
        graph=fixture["graph"],
        bundle=fixture["bundle"],
        membership_as_of="2026-08-21T14:03:00Z",
        data_cutoff="2026-08-21T14:03:00Z",
        frozen_at="2026-08-21T14:04:00Z",
        recorded_at="2026-08-21T14:05:00Z",
    )
    _append_segmented(root, [], fourth_manifest, fixture)
    expected = {
        "events": fixture["full"]["events"],
        "manifests": [*fixture["full"]["manifests"], fourth_manifest],
    }

    second_rotation = rotate_segmented_v2_universe_checkpoint(root)

    assert second_rotation["status"] == "rotated"
    assert second_rotation["new_checkpoint_hash"] != first_rotation[
        "new_checkpoint_hash"
    ]
    assert load_segmented_v2_universe_ledger(root) == expected
    state = load_segmented_v2_universe_state(root)
    assert state["manifest_count"] == 4
    assert state["current_generation_manifest_count"] == 1
    assert state["storage_contract"] == COMPACT_HEAD_STORAGE_CONTRACT
    audit = audit_segmented_v2_universe_ledger_orphans(root)
    assert audit["orphan_count"] == 0
    assert audit["superseded_count"] == 5


def test_rotation_head_failure_leaves_reusable_checkpoint_orphan(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-head-failure"
    _write_three_manifest_segmented(root, fixture)
    old_head = (root / "HEAD.json").read_bytes()
    real_replace = segments_module._replace_with_retry

    def fail_replace(_source, _target):
        raise OSError("simulated rotation HEAD replace failure")

    monkeypatch.setattr(segments_module, "_replace_with_retry", fail_replace)
    _assert_code(
        "segmented_head_write_failed",
        lambda: rotate_segmented_v2_universe_checkpoint(root),
    )
    assert json.loads((root / "HEAD.json").read_bytes())[
        "storage_contract"
    ] == STORAGE_CONTRACT
    assert (root / "HEAD.json").read_bytes() == old_head
    failed_audit = audit_segmented_v2_universe_ledger_orphans(root)
    assert failed_audit["orphan_count"] == 1
    assert failed_audit["superseded_count"] == 0

    monkeypatch.setattr(segments_module, "_replace_with_retry", real_replace)
    retry = rotate_segmented_v2_universe_checkpoint(root)
    assert retry["status"] == "rotated"
    assert retry["checkpoint_reused"] is True
    assert audit_segmented_v2_universe_ledger_orphans(root)["orphan_count"] == 0
    assert load_segmented_v2_universe_ledger(root) == fixture["full"]


def test_stale_rotation_orphan_is_not_adopted_after_an_append(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "stale-rotation-orphan"
    _bootstrap_segmented(root, fixture)
    real_replace = segments_module._replace_with_retry

    def fail_replace(_source, _target):
        raise OSError("simulated stale rotation orphan")

    monkeypatch.setattr(segments_module, "_replace_with_retry", fail_replace)
    _assert_code(
        "segmented_head_write_failed",
        lambda: rotate_segmented_v2_universe_checkpoint(root),
    )
    stale_orphan = audit_segmented_v2_universe_ledger_orphans(root)[
        "orphan_files"
    ]
    assert len(stale_orphan) == 1

    monkeypatch.setattr(segments_module, "_replace_with_retry", real_replace)
    events, manifest = fixture["transactions"][0]
    _append_segmented(root, events, manifest, fixture)
    rotated = rotate_segmented_v2_universe_checkpoint(root)

    assert rotated["status"] == "rotated"
    assert rotated["new_checkpoint_hash"] not in stale_orphan[0]
    audit = audit_segmented_v2_universe_ledger_orphans(root)
    assert audit["orphan_files"] == stale_orphan
    assert load_segmented_v2_universe_ledger(root) == {
        "events": fixture["full"]["events"],
        "manifests": fixture["full"]["manifests"][:2],
    }


def test_rotation_retry_after_committed_head_is_already_compact(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-post-head-error"
    _write_three_manifest_segmented(root, fixture)
    real_replace = segments_module._replace_with_retry

    def commit_then_raise(source, target):
        real_replace(source, target)
        raise OSError("simulated rotation error after commit point")

    monkeypatch.setattr(segments_module, "_replace_with_retry", commit_then_raise)
    _assert_code(
        "segmented_head_write_failed",
        lambda: rotate_segmented_v2_universe_checkpoint(root),
    )
    committed_head = (root / "HEAD.json").read_bytes()
    assert json.loads(committed_head)[
        "storage_contract"
    ] == COMPACT_HEAD_STORAGE_CONTRACT
    assert load_segmented_v2_universe_ledger(root) == fixture["full"]

    monkeypatch.setattr(segments_module, "_replace_with_retry", real_replace)
    retry = rotate_segmented_v2_universe_checkpoint(root)
    assert retry["status"] == "already_compact"
    assert (root / "HEAD.json").read_bytes() == committed_head


def test_compact_checkpoint_collision_never_overwrites_or_moves_head(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-collision"
    _write_three_manifest_segmented(root, fixture)
    old_head = (root / "HEAD.json").read_bytes()
    real_publish = segments_module._publish_immutable_record
    collision = {}

    def publish_collision(path, value, *, role):
        if value.get("record_type") == "v2_universe_ledger_compact_checkpoint":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"different immutable compact checkpoint bytes\n")
            collision["path"] = path
        return real_publish(path, value, role=role)

    monkeypatch.setattr(
        segments_module, "_publish_immutable_record", publish_collision
    )
    _assert_code(
        "segmented_checkpoint_collision",
        lambda: rotate_segmented_v2_universe_checkpoint(root),
    )
    assert collision["path"].read_bytes() == (
        b"different immutable compact checkpoint bytes\n"
    )
    assert (root / "HEAD.json").read_bytes() == old_head
    assert load_segmented_v2_universe_ledger(root) == fixture["full"]


def test_referenced_compact_checkpoint_damage_never_falls_back_to_archive(
    tmp_path,
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-damage"
    _write_three_manifest_segmented(root, fixture)
    rotated = rotate_segmented_v2_universe_checkpoint(root)
    compact_path = segmented_record_path(
        root, "checkpoint", rotated["new_checkpoint_hash"]
    )
    compact_path.write_bytes(b'{"schema_version":1')

    _assert_code(
        "segmented_checkpoint_invalid",
        lambda: load_segmented_v2_universe_state(root),
    )
    _assert_code(
        "segmented_checkpoint_invalid",
        lambda: load_segmented_v2_universe_ledger(root),
    )


def test_rotated_history_preserves_exact_retry_and_conflict_taxonomy(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-history"
    _write_three_manifest_segmented(root, fixture)
    rotate_segmented_v2_universe_checkpoint(root)
    historical_events, historical_manifest = fixture["transactions"][0]
    committed_head = (root / "HEAD.json").read_bytes()

    def reject_archive_load(*_args, **_kwargs):
        raise AssertionError("historical retry traversed archived generations")

    monkeypatch.setattr(
        segments_module, "_load_reachable_store", reject_archive_load
    )

    _assert_code(
        "manifest_run_clock_mismatch",
        lambda: _append_segmented(
            root,
            [],
            historical_manifest,
            fixture,
            run_clock=fixture["future_clock"],
            effective_clock=fixture["future_clock"],
        ),
    )

    missing_inherited_registry = deepcopy(historical_manifest)
    inherited_evidence_id = fixture["graph"]["evidence"][0]["evidence_id"]
    del missing_inherited_registry["evidence_record_registry"][
        inherited_evidence_id
    ]
    missing_inherited_registry = _reseal_manifest(
        missing_inherited_registry
    )
    _assert_code(
        "manifest_input_registry_mismatch",
        lambda: _append_segmented(
            root,
            [],
            missing_inherited_registry,
            fixture,
            evidence_records=[],
        ),
    )

    exact_retry = _append_segmented(
        root, historical_events, historical_manifest, fixture
    )
    assert exact_retry["status"] == "duplicate"
    assert (root / "HEAD.json").read_bytes() == committed_head

    compact_head_manifest = fixture["full"]["manifests"][-1]
    assert _append_segmented(
        root, [], compact_head_manifest, fixture
    )["status"] == "duplicate"
    noisy_head_retry = deepcopy(compact_head_manifest)
    noisy_head_retry["recorded_at"] = "2026-08-21T14:02:30Z"
    noisy_head_retry = _reseal_manifest(noisy_head_retry)
    assert _append_segmented(
        root, [], noisy_head_retry, fixture
    )["status"] == "duplicate"
    assert (root / "HEAD.json").read_bytes() == committed_head

    noisy_retry = deepcopy(historical_manifest)
    noisy_retry["recorded_at"] = "2026-08-20T14:26:30Z"
    noisy_retry = _reseal_manifest(noisy_retry)
    assert noisy_retry["semantic_hash"] == historical_manifest["semantic_hash"]
    assert noisy_retry["manifest_hash"] != historical_manifest["manifest_hash"]
    assert _append_segmented(
        root, historical_events, noisy_retry, fixture
    )["status"] == "duplicate"

    changed_manifest = deepcopy(historical_manifest)
    changed_manifest["frozen_at"] = "2026-08-20T14:25:30Z"
    changed_manifest = _reseal_manifest(changed_manifest)
    assert changed_manifest["semantic_hash"] != historical_manifest["semantic_hash"]
    _assert_code(
        "manifest_id_conflict",
        lambda: _append_segmented(
            root, historical_events, changed_manifest, fixture
        ),
    )
    assert (root / "HEAD.json").read_bytes() == committed_head


def test_exact_load_binds_compact_identity_index_to_archived_history(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-identity-lineage"
    _write_three_manifest_segmented(root, fixture)
    rotated = rotate_segmented_v2_universe_checkpoint(root)
    compact_path = segmented_record_path(
        root, "checkpoint", rotated["new_checkpoint_hash"]
    )
    compact = json.loads(compact_path.read_bytes())
    compact["identity_state"]["manifest_identities"][0]["manifest_id"] = (
        "tampered-archived-manifest-id"
    )
    compact["identity_state"]["manifest_identities"][0]["event_batch_id"] = (
        "tampered-archived-event-batch-id"
    )
    compact = _reseal(compact, "checkpoint_hash")
    _write_json(
        segmented_record_path(root, "checkpoint", compact["checkpoint_hash"]),
        compact,
    )
    head = json.loads((root / "HEAD.json").read_bytes())
    head["checkpoint_hash"] = compact["checkpoint_hash"]
    head = _reseal(head, "head_hash")
    _write_json(root / "HEAD.json", head)

    _assert_code(
        "segmented_compact_lineage_mismatch",
        lambda: load_segmented_v2_universe_ledger(root),
    )


def test_compact_identity_registry_shape_fails_with_stable_error(tmp_path):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-registry-shape"
    _write_three_manifest_segmented(root, fixture)
    rotated = rotate_segmented_v2_universe_checkpoint(root)
    compact_path = segmented_record_path(
        root, "checkpoint", rotated["new_checkpoint_hash"]
    )
    compact = json.loads(compact_path.read_bytes())
    compact["identity_state"]["source_contract_registry"] = None
    compact = _reseal(compact, "checkpoint_hash")
    _write_json(
        segmented_record_path(root, "checkpoint", compact["checkpoint_hash"]),
        compact,
    )
    head = json.loads((root / "HEAD.json").read_bytes())
    head["checkpoint_hash"] = compact["checkpoint_hash"]
    head = _reseal(head, "head_hash")
    _write_json(root / "HEAD.json", head)

    _assert_code(
        "segmented_compact_identity_state_invalid",
        lambda: load_segmented_v2_universe_state(root),
    )


@pytest.mark.parametrize(
    ("identity_field", "error_code"),
    (
        ("manifest_id", "duplicate_physical_manifest"),
        ("event_batch_id", "duplicate_event_batch_id"),
    ),
)
def test_hot_load_rejects_tail_identity_reused_from_compact_history(
    tmp_path, identity_field, error_code
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / f"rotation-tail-{identity_field}"
    _write_three_manifest_segmented(root, fixture)
    rotate_segmented_v2_universe_checkpoint(root)
    fourth_manifest = _manifest(
        fixture["full"]["events"],
        fixture["future_clock"],
        previous=fixture["full"]["manifests"][-1],
        suffix=f"4-tail-{identity_field}",
        graph=fixture["graph"],
        bundle=fixture["bundle"],
        membership_as_of="2026-08-21T14:03:00Z",
        data_cutoff="2026-08-21T14:03:00Z",
        frozen_at="2026-08-21T14:04:00Z",
        recorded_at="2026-08-21T14:05:00Z",
    )
    appended = _append_segmented(root, [], fourth_manifest, fixture)
    segment_path = segmented_record_path(root, "segment", appended["segment_hash"])
    segment = json.loads(segment_path.read_bytes())
    segment["manifest"][identity_field] = fixture["full"]["manifests"][0][
        identity_field
    ]
    segment["manifest"] = _reseal_manifest(segment["manifest"])
    segment["head_manifest_id"] = segment["manifest"]["manifest_id"]
    segment["head_manifest_hash"] = segment["manifest"]["manifest_hash"]
    segment = _reseal(segment, "segment_hash")
    _write_json(
        segmented_record_path(root, "segment", segment["segment_hash"]),
        segment,
    )
    head = json.loads((root / "HEAD.json").read_bytes())
    head["tail_segment_hash"] = segment["segment_hash"]
    head["head_manifest_id"] = segment["manifest"]["manifest_id"]
    head["head_manifest_hash"] = segment["manifest"]["manifest_hash"]
    head = _reseal(head, "head_hash")
    _write_json(root / "HEAD.json", head)

    _assert_code(error_code, lambda: load_segmented_v2_universe_state(root))


def test_compact_tail_retry_checks_clocks_against_archived_capsule(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-tail-clock-history"
    _write_three_manifest_segmented(root, fixture)
    rotate_segmented_v2_universe_checkpoint(root)
    fourth_manifest = _manifest(
        fixture["full"]["events"],
        fixture["future_clock"],
        previous=fixture["full"]["manifests"][-1],
        suffix="4-tail-clock-history",
        graph=fixture["graph"],
        bundle=fixture["bundle"],
        membership_as_of="2026-08-21T14:03:00Z",
        data_cutoff="2026-08-21T14:03:00Z",
        frozen_at="2026-08-21T14:04:00Z",
        recorded_at="2026-08-21T14:05:00Z",
    )
    _append_segmented(root, [], fourth_manifest, fixture)

    def reject_archive_load(*_args, **_kwargs):
        raise AssertionError("tail retry traversed archived generations")

    monkeypatch.setattr(
        segments_module, "_load_reachable_store", reject_archive_load
    )
    conflicting_clock_retry = deepcopy(fourth_manifest)
    conflicting_clock_retry["session_clock_id"] = fixture["clock"][
        "session_clock_id"
    ]
    conflicting_clock_retry = _reseal_manifest(conflicting_clock_retry)

    _assert_code(
        "session_clock_id_conflict",
        lambda: _append_segmented(
            root, [], conflicting_clock_retry, fixture
        ),
    )


def test_fast_state_load_does_not_reconstruct_archived_manifests(
    tmp_path, monkeypatch
):
    fixture = _segmented_writer_fixture(tmp_path)
    root = tmp_path / "rotation-fast-state"
    _write_three_manifest_segmented(root, fixture)
    rotated = rotate_segmented_v2_universe_checkpoint(root)

    real_load_generation = segments_module._load_generation

    def reject_archive_load(*args, **kwargs):
        if kwargs["head_target"] is None:
            raise AssertionError("fast state load traversed archived generation")
        return real_load_generation(*args, **kwargs)

    monkeypatch.setattr(segments_module, "_load_generation", reject_archive_load)
    state = load_segmented_v2_universe_state(root)
    assert state["events"] == fixture["full"]["events"]
    assert state["head_manifest"] == fixture["full"]["manifests"][-1]
    assert state["event_count"] == len(fixture["full"]["events"])
    assert state["manifest_count"] == len(fixture["full"]["manifests"])
    assert state["checkpoint_hash"] == rotated["new_checkpoint_hash"]
    assert state["tail_segment_hash"] is None
    assert state["current_generation_manifest_count"] == 1
    assert state["storage_contract"] == COMPACT_HEAD_STORAGE_CONTRACT
    assert state["legacy_full_reader_compatible"] is False
    assert state["authority"] == "research_only"
    assert state["trade_enabled"] is False


@pytest.mark.parametrize(
    ("lineage_depth", "rotation_manifest_counts"),
    (
        (1, (5,)),
        (2, (3, 5)),
        (4, (2, 3, 4, 5)),
    ),
    ids=("depth-1", "depth-2", "depth-4"),
)
def test_cold_scale_hot_and_exact_load_structural_bounds(
    tmp_path,
    monkeypatch,
    lineage_depth,
    rotation_manifest_counts,
):
    fixture = _segmented_writer_fixture(tmp_path)
    expected, transactions = _cold_scale_history(fixture)
    root = tmp_path / f"cold-scale-{lineage_depth}"
    _bootstrap_segmented(root, fixture)
    rotations = []
    for manifest_count, (events, manifest) in enumerate(
        transactions, start=2
    ):
        _append_segmented(root, events, manifest, fixture)
        if manifest_count in rotation_manifest_counts:
            rotations.append(rotate_segmented_v2_universe_checkpoint(root))

    assert len(rotations) == lineage_depth
    assert all(item["status"] == "rotated" for item in rotations)
    final_rotation = rotations[-1]
    head_path = root / "HEAD.json"
    checkpoint_paths = {
        item for item in (root / "checkpoints").glob("*.json")
    }
    segment_paths = {
        item for item in (root / "segments").glob("*.json")
    }
    current_checkpoint_path = segmented_record_path(
        root, "checkpoint", final_rotation["new_checkpoint_hash"]
    )
    assert len(checkpoint_paths) == lineage_depth + 1
    assert len(segment_paths) == len(transactions)
    assert current_checkpoint_path in checkpoint_paths
    path_sizes = {
        path: path.stat().st_size
        for path in {head_path, *checkpoint_paths, *segment_paths}
    }

    visits = []
    real_read_json = segments_module._read_json

    def measured_read_json(path, *, role):
        visits.append((Path(path), role))
        return real_read_json(path, role=role)

    monkeypatch.setattr(segments_module, "_read_json", measured_read_json)

    def measure(call):
        visits.clear()
        tracer_was_running = tracemalloc.is_tracing()
        if not tracer_was_running:
            tracemalloc.start()
        started_at = perf_counter()
        try:
            output = call()
        finally:
            elapsed_seconds = perf_counter() - started_at
            peak_bytes = None
            if not tracer_was_running:
                _, peak_bytes = tracemalloc.get_traced_memory()
                tracemalloc.stop()
        return output, list(visits), peak_bytes, elapsed_seconds

    hot, hot_visits, hot_peak_bytes, hot_elapsed_seconds = measure(
        lambda: load_segmented_v2_universe_state(root)
    )
    assert hot == {
        "events": expected["events"],
        "head_manifest": expected["manifests"][-1],
        "event_count": len(expected["events"]),
        "manifest_count": len(expected["manifests"]),
        "checkpoint_hash": final_rotation["new_checkpoint_hash"],
        "tail_segment_hash": None,
        "current_generation_manifest_count": 1,
        "storage_contract": COMPACT_HEAD_STORAGE_CONTRACT,
        "legacy_full_reader_compatible": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    expected_hot_visits = [
        (head_path, "head"),
        (current_checkpoint_path, "checkpoint"),
    ]
    assert Counter(hot_visits) == Counter(expected_hot_visits)

    exact, exact_visits, exact_peak_bytes, exact_elapsed_seconds = measure(
        lambda: load_segmented_v2_universe_ledger(root)
    )
    assert exact == expected
    assert exact["manifests"][-1]["trade_enabled"] is False
    expected_exact_visits = [
        (head_path, "head"),
        *((path, "checkpoint") for path in checkpoint_paths),
        *((path, "segment") for path in segment_paths),
    ]
    assert Counter(exact_visits) == Counter(expected_exact_visits)

    fixed_interpreter_allowance_bytes = 4 * 1024 * 1024
    linear_memory_multiplier = 32
    def summarize(output, measured_visits, peak_bytes, elapsed_seconds):
        read_bytes = sum(path_sizes[path] for path, _ in measured_visits)
        output_bytes = len((canonical_json(output) + "\n").encode("utf-8"))
        peak_limit_bytes = fixed_interpreter_allowance_bytes + (
            linear_memory_multiplier
            * (read_bytes + output_bytes)
        )
        if peak_bytes is not None:
            assert peak_bytes <= peak_limit_bytes
        return {
            "read_count": len(measured_visits),
            "roles": dict(
                sorted(
                    Counter(role for _, role in measured_visits).items()
                )
            ),
            "read_bytes": read_bytes,
            "output_bytes": output_bytes,
            "peak_bytes": peak_bytes,
            "peak_limit_bytes": peak_limit_bytes,
            # Diagnostic only; cadence and SLO remain intentionally unset.
            "elapsed_ms": round(elapsed_seconds * 1000, 3),
        }
    telemetry = {
        "lineage_depth": lineage_depth,
        "hot": summarize(
            hot, hot_visits, hot_peak_bytes, hot_elapsed_seconds
        ),
        "exact": summarize(
            exact, exact_visits, exact_peak_bytes, exact_elapsed_seconds
        ),
    }
    print(
        "V2_SEGMENT_SCALE "
        + json.dumps(telemetry, sort_keys=True, separators=(",", ":"))
    )
