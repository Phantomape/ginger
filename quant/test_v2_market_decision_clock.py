from __future__ import annotations

from copy import deepcopy

import pytest

import quant.v2_market_decision_clock as market_clock_module
import quant.v2_universe_observation as universe_observation_module
from quant.test_v2_sec_8k_universe import _published_runtime_fixture
from quant.test_v2_session_clock_contracts import (
    _calendar_bundle,
    _clock,
    _seal_clock,
)
from quant.v2_contracts import canonical_hash
from quant.v2_market_decision_clock import (
    V2MarketDecisionClockError,
    observe_sec_8k_daily_market_decision_clock,
    observe_sec_8k_market_decision_clock,
    observe_sec_8k_replay_market_decision_clock,
    validate_market_decision_clock_snapshot,
)
from quant.v2_sec_8k_runtime_adapter import (
    LEDGER_BACKEND_LEGACY_JSONL_V1,
    LEDGER_BACKEND_SEGMENTED_HOT_V1,
)
from quant.v2_universe_observation import V2UniverseObservationError


def _inputs(tmp_path, **clock_overrides):
    source_dir, ledger_path, envelope_path, manifest_id, as_of = (
        _published_runtime_fixture(tmp_path)
    )
    calendar = _calendar_bundle()
    clock_values = {
        "calendar_session_id": "XNYS-2026-08-21",
        "assignment_cutoff": as_of,
        "frozen_at": "2026-08-21T12:40:00Z",
        "recorded_at": "2026-08-21T12:50:00Z",
    }
    clock_values.update(clock_overrides)
    return {
        "source_dir": source_dir,
        "envelope_path": envelope_path,
        "backend": LEDGER_BACKEND_LEGACY_JSONL_V1,
        "storage_location": ledger_path,
        "manifest_id": manifest_id,
        "as_of": as_of,
        "session_clock": _clock(calendar, **clock_values),
        "calendar_sessions": calendar["sessions"],
        "calendar_evidence": calendar["evidence"],
        "calendar_source_contract": calendar["source"],
    }


def _assert_code(code, func):
    with pytest.raises(V2MarketDecisionClockError) as caught:
        func()
    assert caught.value.code == code
    return caught.value


def _reseal_observation(observation):
    observation["input_identity_sha256"] = canonical_hash(
        observation["input_identity"]
    )
    payload = deepcopy(observation)
    payload.pop("observation_snapshot_hash")
    observation["observation_snapshot_hash"] = canonical_hash(payload)
    return observation


def _reseal_market_clock(snapshot):
    payload = deepcopy(snapshot)
    payload.pop("market_decision_clock_snapshot_hash", None)
    snapshot["market_decision_clock_snapshot_hash"] = canonical_hash(payload)
    return snapshot


def _validate_snapshot(snapshot, inputs, *, expected_snapshot_hash=None):
    return validate_market_decision_clock_snapshot(
        snapshot,
        inputs["session_clock"],
        inputs["calendar_sessions"],
        inputs["calendar_evidence"],
        inputs["calendar_source_contract"],
        expected_snapshot_hash=(
            snapshot["market_decision_clock_snapshot_hash"]
            if expected_snapshot_hash is None
            else expected_snapshot_hash
        ),
    )


def test_market_clock_uses_one_adapter_call_and_true_daily_replay_aliases(
    tmp_path, monkeypatch
):
    inputs = _inputs(tmp_path)
    real_adapter = universe_observation_module.read_sec_8k_runtime_universe
    calls = []

    def counted_adapter(*args, **kwargs):
        calls.append((args, kwargs))
        return real_adapter(*args, **kwargs)

    monkeypatch.setattr(
        universe_observation_module,
        "read_sec_8k_runtime_universe",
        counted_adapter,
    )
    snapshot = observe_sec_8k_market_decision_clock(**inputs)

    assert len(calls) == 1
    assert observe_sec_8k_daily_market_decision_clock is (
        observe_sec_8k_market_decision_clock
    )
    assert observe_sec_8k_replay_market_decision_clock is (
        observe_sec_8k_market_decision_clock
    )
    assert snapshot["input_identity"]["manifest_id"] == inputs["manifest_id"]
    assert snapshot["input_identity"]["observation_as_of"] == inputs["as_of"]
    assert snapshot["input_identity"]["assignment_cutoff"] == inputs["as_of"]
    assert snapshot["input_identity"]["membership_count"] == 1
    assert snapshot["schema_version"] == 2
    assert snapshot["market_decision_clock_contract"] == (
        "v2_research_only_market_decision_clock_v2"
    )
    assert len(snapshot["memberships"]) == 1
    assert snapshot["input_identity"]["membership_snapshot_sha256"] == (
        canonical_hash(
            [
                {
                    key: value
                    for key, value in row.items()
                    if key != "latest_event_hash"
                }
                for row in snapshot["memberships"]
            ]
        )
    )
    assert snapshot["input_identity_sha256"] == canonical_hash(
        snapshot["input_identity"]
    )
    payload = deepcopy(snapshot)
    supplied_hash = payload.pop("market_decision_clock_snapshot_hash")
    assert supplied_hash == canonical_hash(payload)
    assert snapshot["external_universe_coverage_status"] == "unverified"
    assert snapshot["observation_scope"] == (
        "source_bound_universe_membership_only"
    )
    assert snapshot["pit_tier"] == "research_pit"
    assert snapshot["authority"] == "research_only"
    assert snapshot["engine0_policy_invoked"] is False
    assert snapshot["engine0_baseline_established"] is False
    assert snapshot["market_decision_clock_status"] == "bound_research_only"
    assert snapshot["result_ceiling"] == "observed_only"
    assert snapshot["paper_live_eligible"] is False
    assert snapshot["parity_status"] == "contract_only_unwired"
    assert snapshot["outcome_blind"] is True
    assert snapshot["results_accessed"] is False
    assert snapshot["trade_enabled"] is False
    forbidden = {"candidate", "signal", "decision", "order", "outcome"}
    assert forbidden.isdisjoint(snapshot)
    assert forbidden.isdisjoint(snapshot["input_identity"])
    assert set(snapshot) == {
        "schema_version",
        "record_type",
        "market_decision_clock_contract",
        "source_frame",
        "consumer_stage",
        "input_identity",
        "input_identity_sha256",
        "memberships",
        "external_universe_coverage_status",
        "observation_scope",
        "pit_tier",
        "authority",
        "process_wall_clock_fallback_used",
        "engine0_policy_invoked",
        "engine0_baseline_established",
        "market_decision_clock_status",
        "result_ceiling",
        "paper_live_eligible",
        "parity_status",
        "outcome_blind",
        "results_accessed",
        "trade_enabled",
        "market_decision_clock_snapshot_hash",
    }
    assert set(snapshot["input_identity"]) == {
        "observation_snapshot_hash",
        "observation_input_identity_sha256",
        "runtime_adapter_snapshot_hash",
        "runtime_input_identity_sha256",
        "ledger_backend",
        "segmented_hot_state_identity_sha256",
        "manifest_id",
        "manifest_hash",
        "universe_id",
        "universe_definition_id",
        "universe_definition_version",
        "universe_definition_sha256",
        "membership_count",
        "membership_snapshot_sha256",
        "shared_reader_snapshot_hash",
        "observation_as_of",
        "session_clock_id",
        "session_clock_semantic_hash",
        "session_clock_record_hash",
        "run_id",
        "run_date",
        "calendar_id",
        "calendar_version",
        "calendar_timezone",
        "calendar_snapshot_sha256",
        "calendar_evidence_id",
        "calendar_evidence_record_hash",
        "calendar_session_id",
        "session_open_at",
        "session_close_at",
        "assignment_cutoff",
        "clock_frozen_at",
        "clock_recorded_at",
    }


def test_market_clock_accepts_offset_equivalent_cutoff_and_normalizes_output(
    tmp_path,
):
    inputs = _inputs(tmp_path)
    inputs["session_clock"]["assignment_cutoff"] = (
        "2026-08-21T05:30:00-07:00"
    )
    inputs["as_of"] = "2026-08-21T05:30:00-07:00"

    snapshot = observe_sec_8k_market_decision_clock(**inputs)

    assert snapshot["input_identity"]["observation_as_of"] == (
        "2026-08-21T12:30:00Z"
    )
    assert snapshot["input_identity"]["assignment_cutoff"] == (
        "2026-08-21T12:30:00Z"
    )


def test_market_clock_consumer_validator_rejects_resealed_boundary_escalation(
    tmp_path,
):
    inputs = _inputs(tmp_path)
    snapshot = observe_sec_8k_market_decision_clock(**inputs)
    snapshot["trade_enabled"] = True
    snapshot = _reseal_market_clock(snapshot)

    _assert_code(
        "market_clock_snapshot_boundary_mismatch",
        lambda: _validate_snapshot(snapshot, inputs),
    )


def test_market_clock_consumer_validator_rejects_inner_identity_tamper(tmp_path):
    inputs = _inputs(tmp_path)
    snapshot = observe_sec_8k_market_decision_clock(**inputs)
    snapshot["input_identity"]["universe_id"] = "crosswired-universe"
    snapshot = _reseal_market_clock(snapshot)

    _assert_code(
        "market_clock_snapshot_identity_mismatch",
        lambda: _validate_snapshot(snapshot, inputs),
    )


def test_market_clock_consumer_validator_rejects_fully_resealed_identity_substitution(
    tmp_path,
):
    inputs = _inputs(tmp_path)
    snapshot = observe_sec_8k_market_decision_clock(**inputs)
    expected_snapshot_hash = snapshot["market_decision_clock_snapshot_hash"]
    snapshot["input_identity"]["universe_id"] = "crosswired-universe"
    snapshot["input_identity_sha256"] = canonical_hash(snapshot["input_identity"])
    snapshot = _reseal_market_clock(snapshot)

    _assert_code(
        "market_clock_snapshot_expected_hash_mismatch",
        lambda: _validate_snapshot(
            snapshot,
            inputs,
            expected_snapshot_hash=expected_snapshot_hash,
        ),
    )


def test_market_clock_consumer_validator_rejects_boolean_schema_version(tmp_path):
    inputs = _inputs(tmp_path)
    snapshot = observe_sec_8k_market_decision_clock(**inputs)
    snapshot["schema_version"] = True
    snapshot = _reseal_market_clock(snapshot)

    _assert_code(
        "market_clock_snapshot_contract_mismatch",
        lambda: _validate_snapshot(snapshot, inputs),
    )


def test_market_clock_consumer_validator_rejects_clock_record_substitution(tmp_path):
    inputs = _inputs(tmp_path)
    snapshot = observe_sec_8k_market_decision_clock(**inputs)
    substituted_clock = deepcopy(inputs["session_clock"])
    substituted_clock["recorded_at"] = "2026-08-21T12:51:00Z"
    substituted_clock = _seal_clock(substituted_clock)
    inputs["session_clock"] = substituted_clock

    _assert_code(
        "market_clock_snapshot_clock_identity_mismatch",
        lambda: _validate_snapshot(snapshot, inputs),
    )


def test_market_clock_consumer_rejects_fully_resealed_exact_row_tamper(tmp_path):
    inputs = _inputs(tmp_path)
    snapshot = observe_sec_8k_market_decision_clock(**inputs)
    expected_snapshot_hash = snapshot["market_decision_clock_snapshot_hash"]
    snapshot["memberships"][0]["latest_event_hash"] = "f" * 64
    snapshot = _reseal_market_clock(snapshot)

    _assert_code(
        "market_clock_snapshot_expected_hash_mismatch",
        lambda: _validate_snapshot(
            snapshot,
            inputs,
            expected_snapshot_hash=expected_snapshot_hash,
        ),
    )


def test_market_clock_consumer_rejects_resealed_membership_count_drift(tmp_path):
    inputs = _inputs(tmp_path)
    snapshot = observe_sec_8k_market_decision_clock(**inputs)
    snapshot["memberships"] = []
    snapshot = _reseal_market_clock(snapshot)

    _assert_code(
        "market_clock_snapshot_membership_identity_mismatch",
        lambda: _validate_snapshot(snapshot, inputs),
    )


def test_market_clock_consumer_rejects_fully_resealed_membership_hash_drift(
    tmp_path,
):
    inputs = _inputs(tmp_path)
    snapshot = observe_sec_8k_market_decision_clock(**inputs)
    snapshot["input_identity"]["membership_snapshot_sha256"] = "f" * 64
    snapshot["input_identity_sha256"] = canonical_hash(snapshot["input_identity"])
    snapshot = _reseal_market_clock(snapshot)

    _assert_code(
        "market_clock_snapshot_membership_identity_mismatch",
        lambda: _validate_snapshot(snapshot, inputs),
    )


def test_market_clock_consumer_rejects_fully_resealed_future_membership(tmp_path):
    inputs = _inputs(tmp_path)
    snapshot = observe_sec_8k_market_decision_clock(**inputs)
    snapshot["memberships"][0]["effective_at"] = "2026-08-21T12:30:01Z"
    semantic_rows = [
        {key: value for key, value in row.items() if key != "latest_event_hash"}
        for row in snapshot["memberships"]
    ]
    snapshot["input_identity"]["membership_snapshot_sha256"] = canonical_hash(
        semantic_rows
    )
    snapshot["input_identity_sha256"] = canonical_hash(snapshot["input_identity"])
    snapshot = _reseal_market_clock(snapshot)

    _assert_code(
        "market_clock_snapshot_membership_after_cutoff",
        lambda: _validate_snapshot(snapshot, inputs),
    )


def test_market_clock_rejects_observation_as_of_cutoff_mismatch(tmp_path):
    inputs = _inputs(
        tmp_path,
        assignment_cutoff="2026-08-21T12:29:59Z",
    )
    _assert_code(
        "market_clock_as_of_cutoff_mismatch",
        lambda: observe_sec_8k_market_decision_clock(**inputs),
    )


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        (
            {
                "frozen_at": "2026-08-21T13:30:00Z",
                "recorded_at": "2026-08-21T13:30:01Z",
            },
            "market_clock_frozen_at_not_preopen",
        ),
        (
            {"recorded_at": "2026-08-21T13:30:00Z"},
            "market_clock_recorded_at_not_preopen",
        ),
    ],
)
def test_market_clock_requires_freeze_and_record_strictly_before_open(
    tmp_path, overrides, code
):
    inputs = _inputs(tmp_path, **overrides)
    _assert_code(code, lambda: observe_sec_8k_market_decision_clock(**inputs))


@pytest.mark.parametrize(
    ("field", "value", "underlying_code"),
    [
        (
            "process_wall_clock_fallback_used",
            True,
            "process_wall_clock_fallback_forbidden",
        ),
        ("pit_tier", "canonical_pit", "calendar_pit_tier_mismatch"),
        ("authority", "trading", "research_authority_required"),
        ("trade_enabled", True, "trade_enabled_forbidden"),
    ],
)
def test_market_clock_wraps_clock_pit_authority_and_default_off_drift(
    tmp_path, field, value, underlying_code
):
    inputs = _inputs(tmp_path)
    changed = deepcopy(inputs["session_clock"])
    changed[field] = value
    inputs["session_clock"] = _seal_clock(changed)

    error = _assert_code(
        "market_clock_session_clock_dependency_error",
        lambda: observe_sec_8k_market_decision_clock(**inputs),
    )
    assert error.detail.startswith(f"{underlying_code}:")


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            "identity_crosswire",
            "market_clock_observation_identity_mismatch",
        ),
        (
            "boundary_escalation",
            "market_clock_observation_boundary_mismatch",
        ),
    ],
)
def test_market_clock_rejects_resealed_observation_identity_and_boundary_drift(
    tmp_path, monkeypatch, mutation, code
):
    inputs = _inputs(tmp_path)
    observation = universe_observation_module.observe_sec_8k_universe(
        inputs["source_dir"],
        inputs["envelope_path"],
        backend=inputs["backend"],
        storage_location=inputs["storage_location"],
        manifest_id=inputs["manifest_id"],
        as_of=inputs["as_of"],
    )
    if mutation == "identity_crosswire":
        observation["input_identity"]["membership_snapshot_sha256"] = "f" * 64
    else:
        observation["boundary"]["result_ceiling"] = "gate_eligible"
    observation = _reseal_observation(observation)
    monkeypatch.setattr(
        market_clock_module,
        "observe_sec_8k_universe",
        lambda *args, **kwargs: observation,
    )

    _assert_code(code, lambda: observe_sec_8k_market_decision_clock(**inputs))


def test_market_clock_rejects_fully_resealed_future_effective_membership(
    tmp_path, monkeypatch
):
    inputs = _inputs(tmp_path)
    observation = universe_observation_module.observe_sec_8k_universe(
        inputs["source_dir"],
        inputs["envelope_path"],
        backend=inputs["backend"],
        storage_location=inputs["storage_location"],
        manifest_id=inputs["manifest_id"],
        as_of=inputs["as_of"],
    )
    observation["memberships"][0]["effective_at"] = "2026-08-21T12:30:01Z"
    semantic_rows = [
        {key: value for key, value in row.items() if key != "latest_event_hash"}
        for row in observation["memberships"]
    ]
    membership_hash = canonical_hash(semantic_rows)
    observation["membership_snapshot_sha256"] = membership_hash
    observation["input_identity"]["membership_snapshot_sha256"] = membership_hash
    observation = _reseal_observation(observation)
    monkeypatch.setattr(
        market_clock_module,
        "observe_sec_8k_universe",
        lambda *args, **kwargs: observation,
    )

    _assert_code(
        "market_clock_observation_effective_after_as_of",
        lambda: observe_sec_8k_market_decision_clock(**inputs),
    )


def test_market_clock_rejects_resealed_adapter_contract_drift(tmp_path, monkeypatch):
    inputs = _inputs(tmp_path)
    observation = universe_observation_module.observe_sec_8k_universe(
        inputs["source_dir"],
        inputs["envelope_path"],
        backend=inputs["backend"],
        storage_location=inputs["storage_location"],
        manifest_id=inputs["manifest_id"],
        as_of=inputs["as_of"],
    )
    observation["input_identity"]["runtime_adapter_contract"] = (
        "forged_runtime_adapter_contract"
    )
    observation = _reseal_observation(observation)
    monkeypatch.setattr(
        market_clock_module,
        "observe_sec_8k_universe",
        lambda *args, **kwargs: observation,
    )

    _assert_code(
        "market_clock_observation_identity_mismatch",
        lambda: observe_sec_8k_market_decision_clock(**inputs),
    )


@pytest.mark.parametrize("backend", [LEDGER_BACKEND_LEGACY_JSONL_V1, LEDGER_BACKEND_SEGMENTED_HOT_V1])
def test_market_clock_rejects_backend_hot_state_identity_crosswire(
    tmp_path, monkeypatch, backend
):
    inputs = _inputs(tmp_path)
    observation = universe_observation_module.observe_sec_8k_universe(
        inputs["source_dir"],
        inputs["envelope_path"],
        backend=inputs["backend"],
        storage_location=inputs["storage_location"],
        manifest_id=inputs["manifest_id"],
        as_of=inputs["as_of"],
    )
    if backend == LEDGER_BACKEND_LEGACY_JSONL_V1:
        observation["input_identity"][
            "segmented_hot_state_identity_sha256"
        ] = "a" * 64
    else:
        inputs["backend"] = LEDGER_BACKEND_SEGMENTED_HOT_V1
        observation["ledger_backend"] = LEDGER_BACKEND_SEGMENTED_HOT_V1
        observation["input_identity"]["ledger_backend"] = (
            LEDGER_BACKEND_SEGMENTED_HOT_V1
        )
    observation = _reseal_observation(observation)
    monkeypatch.setattr(
        market_clock_module,
        "observe_sec_8k_universe",
        lambda *args, **kwargs: observation,
    )

    _assert_code(
        "market_clock_observation_identity_mismatch",
        lambda: observe_sec_8k_market_decision_clock(**inputs),
    )


def test_market_clock_wraps_observation_dependency_error(tmp_path, monkeypatch):
    inputs = _inputs(tmp_path)

    def fail_observation(*args, **kwargs):
        raise V2UniverseObservationError("synthetic_observation_failure", "boom")

    monkeypatch.setattr(
        market_clock_module,
        "observe_sec_8k_universe",
        fail_observation,
    )
    error = _assert_code(
        "market_clock_observation_dependency_error",
        lambda: observe_sec_8k_market_decision_clock(**inputs),
    )
    assert error.detail == "synthetic_observation_failure: boom"
