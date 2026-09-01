from copy import deepcopy

import pytest

from quant.test_v2_research_contracts import (
    _graph,
    _seal_hypothesis,
    _seal_pool,
)
from quant.test_v2_session_clock_contracts import (
    _calendar_bundle,
    _clock,
    _seal_clock,
)
from quant.v2_contracts import (
    candidate_entry_input_snapshot_hash,
    candidate_pool_input_snapshot_hash,
    canonical_hash,
    universe_event_snapshot_hash,
    validate_decision_record_against_candidate_pool,
)
from quant.v2_engine0_baseline import (
    ENGINE0_BASELINE_POLICY,
    V2Engine0BaselineError,
    build_daily_research_only_engine0_cash_baseline,
    build_replay_research_only_engine0_cash_baseline,
    build_research_only_engine0_cash_baseline,
    get_engine0_baseline_policy_snapshot,
)
from quant.v2_sec_8k_runtime_adapter import LEDGER_BACKEND_LEGACY_JSONL_V1


def _hash(label):
    return canonical_hash({"identity": label})


def _market_clock_snapshot(clock, pool):
    identity = {
        "observation_snapshot_hash": _hash("observation"),
        "observation_input_identity_sha256": _hash("observation-input"),
        "runtime_adapter_snapshot_hash": _hash("adapter"),
        "runtime_input_identity_sha256": _hash("adapter-input"),
        "ledger_backend": LEDGER_BACKEND_LEGACY_JSONL_V1,
        "segmented_hot_state_identity_sha256": None,
        "manifest_id": "manifest-engine0-fixture",
        "manifest_hash": _hash("manifest"),
        "universe_id": pool["universe_id"],
        "universe_definition_id": "universe-definition-engine0",
        "universe_definition_version": "1",
        "universe_definition_sha256": _hash("universe-definition"),
        "membership_count": len(pool["entries"]),
        "membership_snapshot_sha256": _hash("memberships"),
        "shared_reader_snapshot_hash": _hash("shared-reader"),
        "observation_as_of": clock["assignment_cutoff"],
        "session_clock_id": clock["session_clock_id"],
        "session_clock_semantic_hash": clock["semantic_hash"],
        "session_clock_record_hash": clock["record_hash"],
        "run_id": clock["run_id"],
        "run_date": clock["run_date"],
        "calendar_id": clock["calendar_id"],
        "calendar_version": clock["calendar_version"],
        "calendar_timezone": clock["calendar_timezone"],
        "calendar_snapshot_sha256": clock["calendar_snapshot_sha256"],
        "calendar_evidence_id": clock["calendar_evidence_id"],
        "calendar_evidence_record_hash": clock["calendar_evidence_record_hash"],
        "calendar_session_id": clock["calendar_session_id"],
        "session_open_at": clock["session_open_at"],
        "session_close_at": clock["session_close_at"],
        "assignment_cutoff": clock["assignment_cutoff"],
        "clock_frozen_at": clock["frozen_at"],
        "clock_recorded_at": clock["recorded_at"],
    }
    snapshot = {
        "schema_version": 1,
        "record_type": "v2_market_decision_clock_snapshot",
        "market_decision_clock_contract": "v2_research_only_market_decision_clock_v1",
        "source_frame": "sec_edgar_8k",
        "consumer_stage": "pre_engine0_market_decision_clock",
        "input_identity": identity,
        "input_identity_sha256": canonical_hash(identity),
        "external_universe_coverage_status": "unverified",
        "observation_scope": "source_bound_universe_membership_only",
        "pit_tier": "research_pit",
        "authority": "research_only",
        "process_wall_clock_fallback_used": False,
        "engine0_policy_invoked": False,
        "engine0_baseline_established": False,
        "market_decision_clock_status": "bound_research_only",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "parity_status": "contract_only_unwired",
        "outcome_blind": True,
        "results_accessed": False,
        "trade_enabled": False,
    }
    snapshot["market_decision_clock_snapshot_hash"] = canonical_hash(snapshot)
    return snapshot


def _reseal_market_clock(snapshot):
    snapshot = deepcopy(snapshot)
    snapshot["input_identity_sha256"] = canonical_hash(snapshot["input_identity"])
    snapshot.pop("market_decision_clock_snapshot_hash", None)
    snapshot["market_decision_clock_snapshot_hash"] = canonical_hash(snapshot)
    return snapshot


def _inputs(*, two_candidates=True, admission_statuses=None):
    calendar = _calendar_bundle()
    clock = _clock(calendar, calendar_session_id="XNYS-2026-08-21")
    graph = _graph(two_candidates=two_candidates)
    hypothesis = deepcopy(graph["hypothesis"])
    hypothesis["baseline_policy"] = get_engine0_baseline_policy_snapshot()
    hypothesis = _seal_hypothesis(hypothesis)

    evidence_by_id = {item["evidence_id"]: item for item in graph["evidence"]}
    events_by_id = {item["event_id"]: item for item in graph["events"]}
    entries = deepcopy(graph["pool"]["entries"])
    for entry in entries:
        entry["decision_input_sha256"] = candidate_entry_input_snapshot_hash(
            hypothesis_candidate=hypothesis,
            universe_event=events_by_id[entry["universe_event_id"]],
            evidence_records=[
                evidence_by_id[evidence_id]
                for evidence_id in entry["evidence_record_ids"]
            ],
            generator_rule_sha256=graph["pool"]["generator_rule_sha256"],
        )
    if admission_statuses is not None:
        for entry, status in zip(entries, admission_statuses, strict=True):
            entry["admission_status"] = status
            entry["reason_code"] = f"fixture_{status}"
            entry["reason"] = f"Fixture preserves the {status} pool state."
    universe_events = graph["events"]

    pool = deepcopy(graph["pool"])
    pool.update(
        hypothesis_candidate_id=hypothesis["candidate_id"],
        hypothesis_candidate_hash=hypothesis["semantic_hash"],
        entries=entries,
        expected_candidate_count=len(entries),
        universe_event_ids=[item["event_id"] for item in universe_events],
        universe_event_snapshot_sha256=universe_event_snapshot_hash(
            universe_events
        ),
        run_id=clock["run_id"],
        session_clock_id=clock["session_clock_id"],
        session_clock_hash=clock["semantic_hash"],
        session_clock_record_hash=clock["record_hash"],
        run_date=clock["run_date"],
        calendar_session_id=clock["calendar_session_id"],
        data_cutoff=clock["assignment_cutoff"],
        frozen_at="2026-08-21T12:55:00Z",
        recorded_at="2026-08-21T13:00:00Z",
    )
    pool["input_snapshot_sha256"] = candidate_pool_input_snapshot_hash(
        hypothesis_candidate=hypothesis,
        evidence_records=graph["evidence"],
        universe_events=universe_events,
        entries=pool["entries"],
        comparators=pool["comparators"],
        generator_rule_sha256=pool["generator_rule_sha256"],
        ranking_rule_sha256=pool["ranking_rule_sha256"],
        universe_id=pool["universe_id"],
        session_clock_id=pool["session_clock_id"],
        session_clock_hash=pool["session_clock_hash"],
        session_clock_record_hash=pool["session_clock_record_hash"],
        run_date=pool["run_date"],
        calendar_session_id=pool["calendar_session_id"],
        data_cutoff=pool["data_cutoff"],
    )
    pool = _seal_pool(pool)
    market_clock_snapshot = _market_clock_snapshot(clock, pool)
    expected_research_input_identity = {
        "candidate_pool_id": pool["candidate_pool_id"],
        "candidate_pool_semantic_hash": pool["semantic_hash"],
        "candidate_pool_record_hash": pool["record_hash"],
        "candidate_pool_input_snapshot_sha256": pool["input_snapshot_sha256"],
        "hypothesis_candidate_id": hypothesis["candidate_id"],
        "hypothesis_candidate_semantic_hash": hypothesis["semantic_hash"],
        "hypothesis_candidate_record_hash": hypothesis["record_hash"],
    }
    return {
        "market_clock_snapshot": market_clock_snapshot,
        "expected_market_clock_snapshot_hash": market_clock_snapshot[
            "market_decision_clock_snapshot_hash"
        ],
        "candidate_pool": pool,
        "hypothesis_candidate": hypothesis,
        "research_claims": [graph["claim"]],
        "decision_evidence_records": graph["evidence"],
        "decision_source_contracts": [graph["source"]],
        "universe_events": universe_events,
        "expected_research_input_identity": expected_research_input_identity,
        "session_clock": clock,
        "calendar_sessions": calendar["sessions"],
        "calendar_evidence": calendar["evidence"],
        "calendar_source_contract": calendar["source"],
    }


def _build(inputs, **overrides):
    timestamps = {
        "decision_id": "decision-engine0-20260821-v1",
        "decided_at": "2026-08-21T13:10:00Z",
        "recorded_at": "2026-08-21T13:20:00Z",
    }
    timestamps.update(overrides)
    return build_research_only_engine0_cash_baseline(**inputs, **timestamps)


def _assert_code(code, func):
    with pytest.raises(V2Engine0BaselineError) as caught:
        func()
    assert caught.value.code == code


def _refresh_expected_research_identity(inputs):
    pool = inputs["candidate_pool"]
    hypothesis = inputs["hypothesis_candidate"]
    inputs["expected_research_input_identity"] = {
        "candidate_pool_id": pool["candidate_pool_id"],
        "candidate_pool_semantic_hash": pool["semantic_hash"],
        "candidate_pool_record_hash": pool["record_hash"],
        "candidate_pool_input_snapshot_sha256": pool["input_snapshot_sha256"],
        "hypothesis_candidate_id": hypothesis["candidate_id"],
        "hypothesis_candidate_semantic_hash": hypothesis["semantic_hash"],
        "hypothesis_candidate_record_hash": hypothesis["record_hash"],
    }


def test_golden_engine0_builds_complete_cash_only_decision():
    inputs = _inputs()
    result = _build(inputs)
    decision = result["decision_record"]

    validate_decision_record_against_candidate_pool(
        decision, inputs["candidate_pool"], inputs["hypothesis_candidate"]
    )
    assert result["engine0_policy_invoked"] is True
    assert result["engine0_baseline_established"] is True
    assert result["engine0_baseline_scope"] == "validated_candidate_pool"
    assert result["membership_lineage_status"] == "unverified_hash_only"
    assert result["external_universe_coverage_status"] == "unverified"
    assert result["runtime_parity_status"] == "unwired"
    assert result["production_parity_status"] == "unwired"
    assert result["paper_live_eligible"] is False
    assert result["promotion_eligible"] is False
    assert result["order_intent_count"] == 0
    assert decision["policy_arm"] == "baseline"
    assert [item["rank"] for item in decision["items"]] == [1, 2]
    assert {item["signal_action"] for item in decision["items"]} == {"not_selected"}
    for item in decision["items"]:
        assert all(
            item[field] is None
            for field in (
                "side",
                "risk_status",
                "approved_quantity_micros",
                "approved_notional_minor",
                "currency",
            )
        )
    assert result["feature_snapshot_sha256"] == canonical_hash(
        result["feature_rows"]
    )
    assert result["decision_context_sha256"] == canonical_hash(
        result["decision_context"]
    )
    payload = deepcopy(result)
    supplied_hash = payload.pop("engine0_baseline_snapshot_hash")
    assert supplied_hash == canonical_hash(payload)


def test_policy_helper_is_fresh_and_daily_replay_are_true_aliases():
    first = get_engine0_baseline_policy_snapshot()
    second = get_engine0_baseline_policy_snapshot()
    first["policy_id"] = "mutated"

    assert second == dict(ENGINE0_BASELINE_POLICY)
    assert build_daily_research_only_engine0_cash_baseline is (
        build_research_only_engine0_cash_baseline
    )
    assert build_replay_research_only_engine0_cash_baseline is (
        build_research_only_engine0_cash_baseline
    )
    inputs = _inputs()
    assert _build(inputs) == _build(deepcopy(inputs))


def test_inactive_rows_preserve_the_no_decision_boundary():
    mixed = _build(_inputs(admission_statuses=["admitted", "rejected"]))
    admitted, rejected = mixed["decision_record"]["items"]
    assert (admitted["rank"], admitted["signal_action"]) == (1, "not_selected")
    assert all(
        rejected[field] is None
        for field in (
            "rank",
            "signal_action",
            "side",
            "risk_status",
            "approved_quantity_micros",
            "approved_notional_minor",
            "currency",
        )
    )


def test_market_clock_hash_boundary_and_record_substitution_fail_closed():
    inputs = _inputs()
    damaged = deepcopy(inputs)
    damaged["market_clock_snapshot"]["market_decision_clock_snapshot_hash"] = "0" * 64
    _assert_code("engine0_market_clock_dependency_error", lambda: _build(damaged))

    escalated = deepcopy(inputs)
    escalated["market_clock_snapshot"]["trade_enabled"] = True
    escalated["market_clock_snapshot"] = _reseal_market_clock(
        escalated["market_clock_snapshot"]
    )
    _assert_code("engine0_market_clock_dependency_error", lambda: _build(escalated))

    resealed_substitute = deepcopy(inputs)
    resealed_substitute["market_clock_snapshot"]["input_identity"].update(
        universe_id="fully-resealed-universe",
        manifest_id="fully-resealed-manifest",
        manifest_hash=_hash("fully-resealed-manifest"),
    )
    resealed_substitute["market_clock_snapshot"] = _reseal_market_clock(
        resealed_substitute["market_clock_snapshot"]
    )
    _assert_code(
        "engine0_market_clock_dependency_error",
        lambda: _build(resealed_substitute),
    )

    substituted = deepcopy(inputs)
    clock = deepcopy(substituted["session_clock"])
    clock["recorded_at"] = "2026-08-21T12:51:00Z"
    substituted["session_clock"] = _seal_clock(clock)
    _assert_code("engine0_market_clock_dependency_error", lambda: _build(substituted))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("universe_id", "cross-wired-universe"),
        ("calendar_session_id", "XNYS-2026-08-20"),
        ("data_cutoff", "2026-08-21T12:31:00Z"),
        ("session_clock_hash", "f" * 64),
    ],
)
def test_pool_universe_session_cutoff_and_clock_crosswire_fail_closed(field, value):
    inputs = _inputs()
    pool = deepcopy(inputs["candidate_pool"])
    pool[field] = value
    inputs["candidate_pool"] = _seal_pool(pool)
    _refresh_expected_research_identity(inputs)
    _assert_code("engine0_market_pool_identity_mismatch", lambda: _build(inputs))


def test_pool_decision_chronology_policy_and_cash_fail_closed():
    late_pool = _inputs()
    pool = deepcopy(late_pool["candidate_pool"])
    pool["recorded_at"] = "2026-08-21T13:15:00Z"
    late_pool["candidate_pool"] = _seal_pool(pool)
    _refresh_expected_research_identity(late_pool)
    _assert_code(
        "engine0_decision_chronology_invalid", lambda: _build(late_pool)
    )

    _assert_code(
        "engine0_decision_chronology_invalid",
        lambda: _build(
            _inputs(),
            decided_at="2026-08-21T13:31:00Z",
            recorded_at="2026-08-21T13:32:00Z",
        ),
    )

    crosswired = _inputs()
    hypothesis = deepcopy(crosswired["hypothesis_candidate"])
    hypothesis["baseline_policy"]["parameters_sha256"] = "1" * 64
    hypothesis = _seal_hypothesis(hypothesis)
    pool = deepcopy(crosswired["candidate_pool"])
    pool["hypothesis_candidate_hash"] = hypothesis["semantic_hash"]
    crosswired["hypothesis_candidate"] = hypothesis
    crosswired["candidate_pool"] = _seal_pool(pool)
    _refresh_expected_research_identity(crosswired)
    _assert_code("engine0_baseline_policy_mismatch", lambda: _build(crosswired))

    unavailable = _inputs()
    pool = deepcopy(unavailable["candidate_pool"])
    cash = next(item for item in pool["comparators"] if item["role"] == "cash")
    cash["availability_status"] = "unavailable"
    unavailable["candidate_pool"] = _seal_pool(pool)
    _refresh_expected_research_identity(unavailable)
    _assert_code("engine0_cash_comparator_unavailable", lambda: _build(unavailable))


def test_frozen_pool_anchor_and_hypothesis_cutoff_fail_closed():
    truncated = _inputs()
    pool = deepcopy(truncated["candidate_pool"])
    pool["entries"] = pool["entries"][:1]
    pool["expected_candidate_count"] = 1
    truncated["candidate_pool"] = _seal_pool(pool)
    _assert_code(
        "engine0_frozen_research_identity_mismatch",
        lambda: _build(truncated),
    )

    late_hypothesis = _inputs()
    hypothesis = deepcopy(late_hypothesis["hypothesis_candidate"])
    hypothesis.update(
        created_at="2026-08-21T12:31:00Z",
        frozen_at="2026-08-21T12:32:00Z",
        recorded_at="2026-08-21T12:33:00Z",
    )
    hypothesis = _seal_hypothesis(hypothesis)
    pool = deepcopy(late_hypothesis["candidate_pool"])
    pool["hypothesis_candidate_hash"] = hypothesis["semantic_hash"]
    late_hypothesis["hypothesis_candidate"] = hypothesis
    late_hypothesis["candidate_pool"] = _seal_pool(pool)
    _refresh_expected_research_identity(late_hypothesis)
    _assert_code(
        "engine0_hypothesis_after_cutoff",
        lambda: _build(late_hypothesis),
    )


def test_resealed_truncated_pool_still_requires_the_complete_research_graph():
    truncated = _inputs()
    pool = deepcopy(truncated["candidate_pool"])
    pool["entries"] = pool["entries"][:1]
    pool["expected_candidate_count"] = 1
    truncated["candidate_pool"] = _seal_pool(pool)
    _refresh_expected_research_identity(truncated)

    _assert_code(
        "engine0_research_graph_dependency_error",
        lambda: _build(truncated),
    )
