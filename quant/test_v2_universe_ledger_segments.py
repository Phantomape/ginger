from copy import deepcopy
import json
from pathlib import Path

import pytest

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
    load_v2_universe_ledger,
    read_v2_daily_universe,
    read_v2_replay_universe,
    read_v2_universe_membership,
)
from quant.v2_universe_ledger_segments import (
    V2UniverseSegmentError,
    audit_segmented_v2_universe_ledger_orphans,
    build_segmented_ledger_contract,
    load_segmented_v2_universe_ledger,
    segmented_record_path,
    validate_segmented_checkpoint,
    validate_segmented_head,
    validate_segmented_segment,
)


def _assert_code(code, call):
    with pytest.raises(V2UniverseSegmentError) as caught:
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
