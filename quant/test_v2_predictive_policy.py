from collections.abc import Mapping
from copy import deepcopy

import pytest

from quant.test_v2_engine0_baseline import (
    _inputs,
    _refresh_dynamic_market_universe,
    _refresh_pool_graph,
)
from quant.test_v2_research_contracts import _seal_claim, _seal_hypothesis
from quant.v2_contracts import (
    canonical_hash,
    research_claim_snapshot_hash,
    research_evidence_snapshot_hash,
    validate_decision_record_against_candidate_pool,
)
from quant.v2_predictive_policy import (
    PREDICTIVE_POLICY,
    V2PredictivePolicyError,
    build_daily_research_only_predictive_policy,
    build_replay_research_only_predictive_policy,
    build_research_only_predictive_policy,
    get_predictive_policy_snapshot,
    get_predictive_ranking_rule_snapshot,
    predictive_referenced_claim_record_snapshot_hash,
    validate_predictive_policy_snapshot,
)


def _predictive_inputs(**kwargs):
    return _inputs(
        treatment_policy=get_predictive_policy_snapshot(),
        ranking_rule=get_predictive_ranking_rule_snapshot(),
        **kwargs,
    )


def _build(inputs, **overrides):
    timestamps = {
        "decision_id": "decision-claim-support-20260821-v1",
        "decided_at": "2026-08-21T13:21:00Z",
        "recorded_at": "2026-08-21T13:25:00Z",
    }
    timestamps.update(overrides)
    return build_research_only_predictive_policy(**inputs, **timestamps)


def _validate(inputs, snapshot, **overrides):
    timestamps = {
        "decision_id": "decision-claim-support-20260821-v1",
        "decided_at": "2026-08-21T13:21:00Z",
        "recorded_at": "2026-08-21T13:25:00Z",
    }
    timestamps.update(overrides)
    return validate_predictive_policy_snapshot(
        snapshot,
        **inputs,
        expected_snapshot_hash=overrides.get(
            "expected_snapshot_hash", snapshot["predictive_policy_snapshot_hash"]
        ),
        expected_referenced_claim_record_snapshot_hash=overrides.get(
            "expected_referenced_claim_record_snapshot_hash",
            predictive_referenced_claim_record_snapshot_hash(
                inputs["research_claims"], inputs["hypothesis_candidate"]
            ),
        ),
        decision_id=timestamps["decision_id"],
        decided_at=timestamps["decided_at"],
        recorded_at=timestamps["recorded_at"],
    )


def _assert_code(code, func):
    with pytest.raises(V2PredictivePolicyError) as caught:
        func()
    assert caught.value.code == code
    return caught.value


def _assert_self_hash(row, field):
    payload = deepcopy(row)
    supplied = payload.pop(field)
    assert supplied == canonical_hash(payload)


def test_golden_predictive_policy_builds_complete_rank_only_decision():
    inputs = _predictive_inputs()
    result = _build(inputs)
    decision = result["decision_record"]

    validate_decision_record_against_candidate_pool(
        decision, inputs["candidate_pool"], inputs["hypothesis_candidate"]
    )
    assert result["predictive_feature_contract_established"] is True
    assert result["predictive_ranking_policy_established"] is True
    assert result["predictive_efficacy_status"] == "unvalidated_contract_only"
    assert result["entry_selection_enabled"] is False
    assert result["signal_policy_status"] == (
        "disabled_pending_frozen_experiment"
    )
    assert result["shared_policy_parity_status"] == (
        "daily_replay_alias_verified_research_only"
    )
    assert result["dynamic_market_universe_snapshot_hash"] == inputs[
        "expected_dynamic_market_universe_snapshot_hash"
    ]
    assert result["external_universe_coverage_status"] == "unverified"
    assert result["pit_tier"] == "research_pit"
    assert result["result_ceiling"] == "observed_only"
    assert result["paper_live_eligible"] is False
    assert result["promotion_eligible"] is False
    assert result["runtime_parity_status"] == "unwired"
    assert result["production_parity_status"] == "unwired"
    assert result["order_intent_count"] == 0
    assert result["trade_enabled"] is False
    assert decision["policy_arm"] == "treatment"
    assert decision["policy_snapshot"] == dict(PREDICTIVE_POLICY)
    assert [item["rank"] for item in decision["items"]] == [1, 2]
    assert {item["signal_action"] for item in decision["items"]} == {
        "not_selected"
    }
    assert all(item["side"] is None for item in decision["items"])
    assert all(item["risk_status"] is None for item in decision["items"])

    assert len(result["feature_rows"]) == len(inputs["candidate_pool"]["entries"])
    assert [row["claim_support_score_bps"] for row in result["feature_rows"]] == [
        8000,
        8000,
    ]
    assert result["feature_snapshot_sha256"] == canonical_hash(
        result["feature_rows"]
    )
    assert result["ranked_candidate_snapshot_sha256"] == canonical_hash(
        result["ranked_candidates"]
    )
    assert result["signal_decision_snapshot_sha256"] == canonical_hash(
        result["signal_decisions"]
    )
    for row in result["feature_rows"]:
        _assert_self_hash(row, "feature_row_sha256")
    for row in result["ranked_candidates"]:
        _assert_self_hash(row, "ranked_candidate_sha256")
    for row in result["signal_decisions"]:
        _assert_self_hash(row, "signal_decision_sha256")
    _assert_self_hash(result, "predictive_policy_snapshot_hash")


def test_daily_and_replay_are_true_aliases_and_deterministic():
    assert build_daily_research_only_predictive_policy is (
        build_research_only_predictive_policy
    )
    assert build_replay_research_only_predictive_policy is (
        build_research_only_predictive_policy
    )
    inputs = _predictive_inputs()
    assert _build(deepcopy(inputs)) == _build(deepcopy(inputs))


def test_validator_reconstructs_exact_plain_snapshot():
    inputs = _predictive_inputs()
    snapshot = _build(inputs)
    original_context = deepcopy(snapshot["decision_context"])

    class CallerContext(Mapping):
        def __len__(self):
            return len(original_context)

        def __getitem__(self, key):
            return original_context[key]

        def __iter__(self):
            return iter(original_context)

        def __deepcopy__(self, memo):
            return self

    caller_snapshot = deepcopy(snapshot)
    caller_snapshot["decision_context"] = CallerContext()

    validated = _validate(inputs, caller_snapshot)

    assert validated == snapshot
    assert type(validated) is dict
    assert type(validated["decision_context"]) is dict
    assert validated["decision_context"] == original_context


def test_referenced_claim_record_hash_ignores_valid_unreferenced_superset():
    inputs = _predictive_inputs()
    unreferenced_claim = deepcopy(inputs["research_claims"][0])
    unreferenced_claim["claim_id"] = "claim-unreferenced-superset-v1"
    unreferenced_claim = _seal_claim(unreferenced_claim)

    expected = predictive_referenced_claim_record_snapshot_hash(
        inputs["research_claims"], inputs["hypothesis_candidate"]
    )
    observed = predictive_referenced_claim_record_snapshot_hash(
        [*inputs["research_claims"], unreferenced_claim],
        inputs["hypothesis_candidate"],
    )

    assert observed == expected


def test_validator_rejects_wrong_separately_frozen_snapshot_hash():
    inputs = _predictive_inputs()
    snapshot = _build(inputs)

    _assert_code(
        "predictive_policy_expected_snapshot_hash_mismatch",
        lambda: _validate(inputs, snapshot, expected_snapshot_hash="0" * 64),
    )


def test_validator_rejects_comparison_overriding_hash_subclasses():
    inputs = _predictive_inputs()
    snapshot = _build(inputs)

    class EqualHash(str):
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

    _assert_code(
        "predictive_policy_claim_record_snapshot_mismatch",
        lambda: _validate(
            inputs,
            snapshot,
            expected_referenced_claim_record_snapshot_hash=EqualHash("f" * 64),
        ),
    )
    _assert_code(
        "predictive_policy_expected_snapshot_hash_mismatch",
        lambda: _validate(
            inputs,
            snapshot,
            expected_snapshot_hash=EqualHash("0" * 64),
        ),
    )
    subclass_snapshot = deepcopy(snapshot)
    subclass_snapshot["predictive_policy_snapshot_hash"] = EqualHash(
        snapshot["predictive_policy_snapshot_hash"]
    )
    _assert_code(
        "predictive_policy_expected_snapshot_hash_mismatch",
        lambda: _validate(
            inputs,
            subclass_snapshot,
            expected_snapshot_hash=snapshot["predictive_policy_snapshot_hash"],
        ),
    )


def test_validator_rejects_invalid_self_hash():
    inputs = _predictive_inputs()
    snapshot = _build(inputs)
    snapshot["trade_enabled"] = True

    _assert_code(
        "predictive_policy_snapshot_hash_mismatch",
        lambda: _validate(inputs, snapshot),
    )


def test_validator_rejects_extra_outcome_surface():
    inputs = _predictive_inputs()
    snapshot = _build(inputs)
    snapshot["settled_outcomes"] = []

    _assert_code(
        "predictive_policy_snapshot_shape_invalid",
        lambda: _validate(inputs, snapshot),
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: row["feature_rows"][0].update(
            claim_support_score_bps=9999
        ),
        lambda row: row["ranked_candidates"][0].update(rank=2),
        lambda row: row["signal_decisions"][0].update(
            signal_action="selected"
        ),
        lambda row: row["decision_context"].update(trade_enabled=True),
        lambda row: row["decision_record"]["items"][0].update(
            side="long"
        ),
    ],
)
def test_validator_rejects_fully_resealed_nested_substitution(mutate):
    inputs = _predictive_inputs()
    snapshot = _build(inputs)
    mutate(snapshot)
    snapshot.pop("predictive_policy_snapshot_hash")
    snapshot["predictive_policy_snapshot_hash"] = canonical_hash(snapshot)

    _assert_code(
        "predictive_policy_expected_snapshot_hash_mismatch",
        lambda: _validate(
            inputs,
            snapshot,
            expected_snapshot_hash=_build(inputs)[
                "predictive_policy_snapshot_hash"
            ],
        ),
    )


def test_validator_rejects_record_only_variant_of_irrelevant_referenced_claim():
    inputs = _predictive_inputs()
    irrelevant_claim = deepcopy(inputs["research_claims"][0])
    irrelevant_claim.update(
        claim_id="claim-outside-candidate-surface-v1",
        affected_object_ids=["sec-outside-candidate-surface"],
    )
    irrelevant_claim = _seal_claim(irrelevant_claim)
    inputs["research_claims"] = [inputs["research_claims"][0], irrelevant_claim]
    hypothesis = deepcopy(inputs["hypothesis_candidate"])
    hypothesis["research_claim_ids"] = [
        claim["claim_id"] for claim in inputs["research_claims"]
    ]
    hypothesis["claim_snapshot_sha256"] = research_claim_snapshot_hash(
        inputs["research_claims"]
    )
    inputs["hypothesis_candidate"] = _seal_hypothesis(hypothesis)
    inputs["candidate_pool"]["hypothesis_candidate_hash"] = inputs[
        "hypothesis_candidate"
    ]["semantic_hash"]
    _refresh_pool_graph(inputs, inputs["universe_events"])
    _refresh_dynamic_market_universe(inputs)
    snapshot = _build(inputs)
    expected_claim_records = predictive_referenced_claim_record_snapshot_hash(
        inputs["research_claims"], inputs["hypothesis_candidate"]
    )

    changed_inputs = deepcopy(inputs)
    changed_claim = deepcopy(changed_inputs["research_claims"][1])
    changed_claim["recorded_at"] = "2026-08-20T14:05:30Z"
    changed_inputs["research_claims"][1] = _seal_claim(changed_claim)
    assert _build(changed_inputs) == snapshot

    _assert_code(
        "predictive_policy_claim_record_snapshot_mismatch",
        lambda: _validate(
            changed_inputs,
            snapshot,
            expected_referenced_claim_record_snapshot_hash=(
                expected_claim_records
            ),
        ),
    )
    _assert_code(
        "predictive_policy_claim_record_snapshot_mismatch",
        lambda: _validate(
            changed_inputs,
            snapshot,
            expected_referenced_claim_record_snapshot_hash=None,
        ),
    )


def test_validator_reconstructs_before_hostile_snapshot_callback():
    inputs = _predictive_inputs()
    snapshot = _build(inputs)

    class MutatingSnapshot(Mapping):
        def __len__(self):
            return len(snapshot)

        def __getitem__(self, key):
            return snapshot[key]

        def __iter__(self):
            inputs["research_claims"].clear()
            return iter(snapshot)

    validated = _validate(inputs, MutatingSnapshot())

    assert validated == snapshot
    assert inputs["research_claims"] == []


def test_policy_snapshot_returns_fresh_copy():
    first = get_predictive_policy_snapshot()
    first["policy_id"] = "mutated"
    assert get_predictive_policy_snapshot() == dict(PREDICTIVE_POLICY)


def test_inactive_candidate_is_preserved_without_rank_or_signal():
    inputs = _predictive_inputs(admission_statuses=["admitted", "parked"])
    result = _build(inputs)

    assert len(result["feature_rows"]) == 2
    inactive_rank = next(
        row
        for row in result["ranked_candidates"]
        if row["admission_status"] == "parked"
    )
    inactive_signal = next(
        row
        for row in result["signal_decisions"]
        if row["candidate_entry_id"] == inactive_rank["candidate_entry_id"]
    )
    inactive_item = next(
        row
        for row in result["decision_record"]["items"]
        if row["candidate_entry_id"] == inactive_rank["candidate_entry_id"]
    )
    assert inactive_rank["rank"] is None
    assert inactive_signal["signal_action"] is None
    assert inactive_item["rank"] is None
    assert inactive_item["signal_action"] is None
    assert inactive_item["side"] is None


def test_missing_claim_support_ranks_after_available_feature():
    inputs = _predictive_inputs()
    claim = deepcopy(inputs["research_claims"][0])
    claim["affected_object_ids"] = ["sec-aaa"]
    claim = _seal_claim(claim)
    inputs["research_claims"] = [claim]

    hypothesis = deepcopy(inputs["hypothesis_candidate"])
    hypothesis["claim_snapshot_sha256"] = research_claim_snapshot_hash([claim])
    inputs["hypothesis_candidate"] = _seal_hypothesis(hypothesis)
    inputs["candidate_pool"]["hypothesis_candidate_hash"] = inputs[
        "hypothesis_candidate"
    ]["semantic_hash"]
    _refresh_pool_graph(inputs, inputs["universe_events"])
    _refresh_dynamic_market_universe(inputs)

    result = _build(inputs)
    features = {
        row["security_id"]: row for row in result["feature_rows"]
    }
    ranks = {
        row["security_id"]: row["rank"]
        for row in result["ranked_candidates"]
    }
    assert features["sec-aaa"]["claim_support_score_bps"] == 8000
    assert features["sec-bbb"]["claim_support_score_bps"] is None
    assert ranks == {"sec-aaa": 1, "sec-bbb": 2}


def test_available_features_rank_by_claim_support_score_descending():
    inputs = _predictive_inputs()
    evidence_by_security = {
        row["security_mapping"]["security_id"]: row
        for row in inputs["decision_evidence_records"]
    }
    claims = []
    for security_id, confidence_bps in (("sec-aaa", 6000), ("sec-bbb", 9000)):
        evidence = evidence_by_security[security_id]
        claim = deepcopy(inputs["research_claims"][0])
        claim.update(
            claim_id=f"claim-{security_id}-support-v1",
            evidence_record_ids=[evidence["evidence_id"]],
            evidence_snapshot_sha256=research_evidence_snapshot_hash([evidence]),
            affected_object_ids=[security_id],
            confidence_bps=confidence_bps,
        )
        claims.append(_seal_claim(claim))
    inputs["research_claims"] = claims

    hypothesis = deepcopy(inputs["hypothesis_candidate"])
    hypothesis["research_claim_ids"] = [row["claim_id"] for row in claims]
    hypothesis["claim_snapshot_sha256"] = research_claim_snapshot_hash(claims)
    inputs["hypothesis_candidate"] = _seal_hypothesis(hypothesis)
    inputs["candidate_pool"]["hypothesis_candidate_hash"] = inputs[
        "hypothesis_candidate"
    ]["semantic_hash"]
    _refresh_pool_graph(inputs, inputs["universe_events"])
    _refresh_dynamic_market_universe(inputs)

    result = _build(inputs)
    ranks = {
        row["security_id"]: row["rank"]
        for row in result["ranked_candidates"]
    }
    scores = {
        row["security_id"]: row["claim_support_score_bps"]
        for row in result["feature_rows"]
    }
    assert scores == {"sec-aaa": 6000, "sec-bbb": 9000}
    assert ranks == {"sec-aaa": 2, "sec-bbb": 1}


def test_affected_security_without_shared_evidence_has_no_claim_support():
    inputs = _predictive_inputs()
    aaa_evidence = next(
        row
        for row in inputs["decision_evidence_records"]
        if row["security_mapping"]["security_id"] == "sec-aaa"
    )
    claim = deepcopy(inputs["research_claims"][0])
    claim.update(
        evidence_record_ids=[aaa_evidence["evidence_id"]],
        evidence_snapshot_sha256=research_evidence_snapshot_hash(
            [aaa_evidence]
        ),
    )
    claim = _seal_claim(claim)
    inputs["research_claims"] = [claim]

    hypothesis = deepcopy(inputs["hypothesis_candidate"])
    hypothesis["claim_snapshot_sha256"] = research_claim_snapshot_hash(
        [claim]
    )
    inputs["hypothesis_candidate"] = _seal_hypothesis(hypothesis)
    inputs["candidate_pool"]["hypothesis_candidate_hash"] = inputs[
        "hypothesis_candidate"
    ]["semantic_hash"]
    _refresh_pool_graph(inputs, inputs["universe_events"])
    _refresh_dynamic_market_universe(inputs)

    result = _build(inputs)
    features = {
        row["security_id"]: row for row in result["feature_rows"]
    }
    assert features["sec-aaa"]["claim_support_score_bps"] == 8000
    assert features["sec-bbb"]["claim_support_score_bps"] is None
    assert features["sec-bbb"]["feature_status"] == "unavailable"


def test_unfrozen_treatment_policy_is_rejected():
    inputs = _inputs()
    _assert_code(
        "predictive_policy_treatment_mismatch",
        lambda: _build(inputs),
    )


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        (
            {"decided_at": "2026-08-21T12:59:59Z"},
            "predictive_policy_decision_chronology_invalid",
        ),
        (
            {"recorded_at": "2026-08-21T13:30:00Z"},
            "predictive_policy_decision_chronology_invalid",
        ),
        (
            {"decided_at": "2026-08-21T13:21:00"},
            "predictive_policy_instant_invalid",
        ),
    ],
)
def test_decision_chronology_fails_closed(overrides, code):
    inputs = _predictive_inputs()
    _assert_code(code, lambda: _build(inputs, **overrides))


def test_resealed_dynamic_snapshot_cannot_replace_separately_frozen_identity():
    inputs = _predictive_inputs()
    snapshot = deepcopy(inputs["dynamic_market_universe_snapshot"])
    snapshot["market_universe_scope"] = "self_resealed_substitute"
    snapshot.pop("dynamic_market_universe_snapshot_hash")
    snapshot["dynamic_market_universe_snapshot_hash"] = canonical_hash(snapshot)
    inputs["dynamic_market_universe_snapshot"] = snapshot

    error = _assert_code(
        "predictive_policy_dynamic_market_universe_dependency_error",
        lambda: _build(inputs),
    )
    assert "dynamic_market_universe_expected_hash_mismatch" in error.detail


def test_fully_resealed_baseline_policy_substitution_is_rejected():
    inputs = _predictive_inputs()
    hypothesis = deepcopy(inputs["hypothesis_candidate"])
    hypothesis["baseline_policy"]["parameters_sha256"] = "1" * 64
    inputs["hypothesis_candidate"] = _seal_hypothesis(hypothesis)
    inputs["candidate_pool"]["hypothesis_candidate_hash"] = inputs[
        "hypothesis_candidate"
    ]["semantic_hash"]
    _refresh_pool_graph(inputs, inputs["universe_events"])
    _refresh_dynamic_market_universe(inputs)

    _assert_code(
        "predictive_policy_engine0_baseline_mismatch",
        lambda: _build(inputs),
    )


def test_fully_resealed_candidate_pool_ranking_rule_substitution_is_rejected():
    inputs = _predictive_inputs()
    inputs["candidate_pool"]["ranking_rule_sha256"] = "1" * 64
    _refresh_pool_graph(inputs, inputs["universe_events"])
    _refresh_dynamic_market_universe(inputs)

    _assert_code(
        "predictive_policy_pool_ranking_rule_mismatch",
        lambda: _build(inputs),
    )


def test_candidate_pool_crosswire_is_rejected_by_dynamic_boundary():
    inputs = _predictive_inputs()
    pool = deepcopy(inputs["candidate_pool"])
    pool["candidate_pool_id"] = "crosswired-pool"
    inputs["candidate_pool"] = pool

    error = _assert_code(
        "predictive_policy_research_input_dependency_error",
        lambda: _build(inputs),
    )
    assert "semantic_hash_mismatch" in error.detail
