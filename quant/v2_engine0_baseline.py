"""Research-only Engine-0 cash/no-signal baseline for Ginger V2.

The builder consumes an already-bound market decision clock, a separately
frozen dynamic market-universe snapshot, and a complete CandidatePool.
Engine-0 has no caller-configurable strategy knobs: admitted rows receive only
deterministic administrative ranks, every signal remains ``not_selected``, and
no order intent can be produced.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .v2_contracts import (
    CLOCK_BOUND_SCHEMA_VERSION,
    CalendarSession,
    CandidatePool,
    EvidenceRecord,
    HypothesisCandidate,
    ResearchClaim,
    SessionClock,
    SourceContract,
    UniverseEvent,
    V2ContractValidationError,
    canonical_hash,
    decision_input_snapshot_hash,
    validate_candidate_pool,
    validate_decision_record_against_candidate_pool,
    validate_hypothesis_candidate,
    validate_record_against_session_clock,
)
from .v2_dynamic_market_universe import (
    FROZEN_RESEARCH_INPUT_IDENTITY_FIELDS,
    V2DynamicMarketUniverseError,
    validate_dynamic_market_universe_snapshot,
)


SCHEMA_VERSION = 3
ENGINE0_BASELINE_RECORD_TYPE = "v2_engine0_cash_baseline_snapshot"
ENGINE0_BASELINE_CONTRACT = "v2_research_only_engine0_cash_no_signal_v3"

_ENGINE0_RULE = {
    "rule_id": "v2-engine0-cash-no-signal-rule",
    "rule_version": "1",
    "decision_engine_id": "v2-engine0-cash-no-signal",
    "decision_engine_version": "1",
    "admitted_ranking": "candidate_entry_id_ascending_administrative_only",
    "admitted_signal_action": "not_selected",
    "inactive_entry_handling": "all_decision_fields_null",
    "side": None,
    "risk_status": None,
    "approved_quantity_micros": None,
    "approved_notional_minor": None,
    "currency": None,
    "cash_comparator_role": "cash",
    "cash_comparator_reference_id": "cash",
    "execution_rule": {
        "rule_id": "v2-engine0-no-order",
        "rule_version": "engine0-no-order-v1",
        "order_intent_policy": "forbidden",
    },
    "cost_rule": {
        "rule_id": "v2-engine0-no-order-cost",
        "rule_version": "engine0-no-order-cost-v1",
        "cost_basis": "no_order_no_cost",
    },
    "comparison_rule": {
        "rule_id": "v2-engine0-cash-comparator",
        "rule_version": "engine0-cash-comparator-v1",
        "comparator_role": "cash",
        "reference_id": "cash",
    },
    "order_intent_count": 0,
}
ENGINE0_BASELINE_RULE_SHA256 = canonical_hash(_ENGINE0_RULE)

ENGINE0_BASELINE_POLICY = MappingProxyType(
    {
        "policy_id": "v2-engine0-cash-no-signal-baseline",
        "entry_policy_version": "engine0-no-entry-v1",
        "ranking_policy_version": "engine0-administrative-rank-v1",
        "sizing_policy_version": "engine0-no-size-v1",
        "exit_policy_version": "engine0-cash-only-v1",
        "cost_policy_version": "engine0-no-order-cost-v1",
        "parameters_sha256": ENGINE0_BASELINE_RULE_SHA256,
    }
)


class V2Engine0BaselineError(RuntimeError):
    """Engine-0 construction failed with a stable machine code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


def _fail(code: str, message: str) -> None:
    raise V2Engine0BaselineError(code, message)


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("engine0_identifier_invalid", f"{field} must be non-empty text")
    return value


def _instant(value: Any, *, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str):
        _fail("engine0_instant_invalid", f"{field} must include a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("engine0_instant_invalid", f"{field} must include a timezone")
    utc = parsed.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z"), utc


def _freeze_record(value: Any) -> Any:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    return deepcopy(value)


def _freeze_sequence(value: Any) -> Any:
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, Mapping)
    ):
        return tuple(deepcopy(item) for item in value)
    return deepcopy(value)


def get_engine0_baseline_policy_snapshot() -> dict[str, Any]:
    """Return a fresh mutable copy of the immutable Engine-0 policy."""

    return dict(ENGINE0_BASELINE_POLICY)


def _validate_dependencies(
    market_clock_snapshot: Mapping[str, Any],
    dynamic_market_universe_snapshot: Mapping[str, Any],
    candidate_pool: Mapping[str, Any] | CandidatePool,
    hypothesis_candidate: Mapping[str, Any] | HypothesisCandidate,
    research_claims: Sequence[Mapping[str, Any] | ResearchClaim],
    decision_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    decision_source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    universe_events: Sequence[Mapping[str, Any] | UniverseEvent],
    session_clock: Mapping[str, Any] | SessionClock,
    calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    calendar_source_contract: Mapping[str, Any] | SourceContract,
    *,
    expected_market_clock_snapshot_hash: str,
    expected_dynamic_market_universe_snapshot_hash: str,
    expected_research_input_identity: Mapping[str, Any],
) -> tuple[
    dict[str, Any],
    CandidatePool,
    HypothesisCandidate,
    dict[str, Any],
]:
    try:
        pool = validate_candidate_pool(candidate_pool)
        hypothesis = validate_hypothesis_candidate(hypothesis_candidate)
    except V2ContractValidationError as exc:
        raise V2Engine0BaselineError(
            "engine0_research_input_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc

    if canonical_hash(hypothesis.baseline_policy) != canonical_hash(
        ENGINE0_BASELINE_POLICY
    ):
        _fail(
            "engine0_baseline_policy_mismatch",
            "hypothesis baseline policy must exactly equal the hardcoded Engine-0 policy",
        )
    cash = next(item for item in pool.comparators if item.role == "cash")
    if cash.reference_id != "cash" or cash.availability_status != "available":
        _fail(
            "engine0_cash_comparator_unavailable",
            "Engine-0 requires the available cash comparator with reference_id cash",
        )
    try:
        dynamic_market_universe = validate_dynamic_market_universe_snapshot(
            dynamic_market_universe_snapshot,
            market_clock_snapshot,
            candidate_pool,
            hypothesis_candidate,
            research_claims,
            decision_evidence_records,
            decision_source_contracts,
            universe_events,
            session_clock,
            calendar_sessions,
            calendar_evidence,
            calendar_source_contract,
            expected_snapshot_hash=(
                expected_dynamic_market_universe_snapshot_hash
            ),
            expected_market_clock_snapshot_hash=(
                expected_market_clock_snapshot_hash
            ),
            expected_research_input_identity=expected_research_input_identity,
        )
    except V2DynamicMarketUniverseError as exc:
        code = {
            "dynamic_market_universe_market_clock_dependency_error": (
                "engine0_market_clock_dependency_error"
            ),
            "dynamic_market_universe_research_input_dependency_error": (
                "engine0_research_input_dependency_error"
            ),
            "dynamic_market_universe_frozen_research_identity_invalid": (
                "engine0_frozen_research_identity_invalid"
            ),
            "dynamic_market_universe_frozen_research_identity_mismatch": (
                "engine0_frozen_research_identity_mismatch"
            ),
            "dynamic_market_universe_research_boundary_mismatch": (
                "engine0_research_boundary_mismatch"
            ),
            "dynamic_market_universe_pool_hypothesis_binding_mismatch": (
                "engine0_pool_hypothesis_binding_mismatch"
            ),
            "dynamic_market_universe_market_pool_identity_mismatch": (
                "engine0_market_pool_identity_mismatch"
            ),
            "dynamic_market_universe_hypothesis_after_cutoff": (
                "engine0_hypothesis_after_cutoff"
            ),
            "dynamic_market_universe_research_graph_dependency_error": (
                "engine0_research_graph_dependency_error"
            ),
            "dynamic_market_universe_population_dependency_error": (
                "engine0_membership_lineage_dependency_error"
            ),
            "dynamic_market_universe_membership_lineage_mismatch": (
                "engine0_membership_lineage_mismatch"
            ),
        }.get(exc.code, "engine0_dynamic_market_universe_dependency_error")
        raise V2Engine0BaselineError(
            code,
            f"{exc.code}: {exc.detail}",
        ) from exc
    market_clock = deepcopy(dict(market_clock_snapshot))
    return market_clock, pool, hypothesis, dynamic_market_universe


def build_research_only_engine0_cash_baseline(
    market_clock_snapshot: Mapping[str, Any],
    dynamic_market_universe_snapshot: Mapping[str, Any],
    candidate_pool: Mapping[str, Any] | CandidatePool,
    hypothesis_candidate: Mapping[str, Any] | HypothesisCandidate,
    research_claims: Sequence[Mapping[str, Any] | ResearchClaim],
    decision_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    decision_source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    universe_events: Sequence[Mapping[str, Any] | UniverseEvent],
    session_clock: Mapping[str, Any] | SessionClock,
    calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    calendar_source_contract: Mapping[str, Any] | SourceContract,
    *,
    expected_market_clock_snapshot_hash: str,
    expected_dynamic_market_universe_snapshot_hash: str,
    expected_research_input_identity: Mapping[str, Any],
    decision_id: str,
    decided_at: str,
    recorded_at: str,
) -> dict[str, Any]:
    """Build one complete research-only cash/no-signal Engine-0 decision."""

    expected_research_input_identity = _freeze_record(
        expected_research_input_identity
    )
    market_clock_snapshot = _freeze_record(market_clock_snapshot)
    candidate_pool = _freeze_record(candidate_pool)
    hypothesis_candidate = _freeze_record(hypothesis_candidate)
    dynamic_market_universe_snapshot = _freeze_record(
        dynamic_market_universe_snapshot
    )
    research_claims = _freeze_sequence(research_claims)
    decision_evidence_records = _freeze_sequence(decision_evidence_records)
    decision_source_contracts = _freeze_sequence(decision_source_contracts)
    universe_events = _freeze_sequence(universe_events)
    session_clock = _freeze_record(session_clock)
    calendar_sessions = _freeze_sequence(calendar_sessions)
    calendar_evidence = _freeze_record(calendar_evidence)
    calendar_source_contract = _freeze_record(calendar_source_contract)
    market_clock, pool, hypothesis, dynamic_market_universe = _validate_dependencies(
        market_clock_snapshot,
        dynamic_market_universe_snapshot,
        candidate_pool,
        hypothesis_candidate,
        research_claims,
        decision_evidence_records,
        decision_source_contracts,
        universe_events,
        session_clock,
        calendar_sessions,
        calendar_evidence,
        calendar_source_contract,
        expected_market_clock_snapshot_hash=expected_market_clock_snapshot_hash,
        expected_dynamic_market_universe_snapshot_hash=(
            expected_dynamic_market_universe_snapshot_hash
        ),
        expected_research_input_identity=expected_research_input_identity,
    )
    decision_id = _text(decision_id, field="decision_id")
    decided_at, decided_dt = _instant(decided_at, field="decided_at")
    recorded_at, recorded_dt = _instant(recorded_at, field="recorded_at")
    _, pool_recorded_dt = _instant(pool.recorded_at, field="candidate_pool.recorded_at")
    _, session_open_dt = _instant(
        market_clock["input_identity"]["session_open_at"],
        field="market_clock.session_open_at",
    )
    if not (
        pool_recorded_dt <= decided_dt <= recorded_dt < session_open_dt
    ):
        _fail(
            "engine0_decision_chronology_invalid",
            "must satisfy pool recorded_at <= decided_at <= recorded_at < session open",
        )

    cash = next(item for item in pool.comparators if item.role == "cash")

    feature_rows = [
        {
            "candidate_entry_id": item.candidate_entry_id,
            "security_id": item.security_id,
            "listing_id": item.listing_id,
            "security_mapping_sha256": item.security_mapping_sha256,
            "decision_input_sha256": item.decision_input_sha256,
            "admission_status": item.admission_status,
        }
        for item in pool.entries
    ]
    feature_snapshot_sha256 = canonical_hash(feature_rows)
    rule = deepcopy(_ENGINE0_RULE)
    rule_sha256 = canonical_hash(rule)
    policy = get_engine0_baseline_policy_snapshot()
    policy_sha256 = canonical_hash(policy)

    membership_lineage = deepcopy(dynamic_market_universe["membership_lineage"])
    validated_research_input_identity = {
        field: dynamic_market_universe["input_identity"][field]
        for field in sorted(FROZEN_RESEARCH_INPUT_IDENTITY_FIELDS)
    }

    decision_context_id = f"{decision_id}:engine0-research-context-v3"
    decision_context = {
        "context_type": "v2_engine0_decision_context",
        "context_version": "3",
        "decision_context_id": decision_context_id,
        "market_decision_clock_snapshot_hash": market_clock[
            "market_decision_clock_snapshot_hash"
        ],
        "expected_market_clock_snapshot_hash": expected_market_clock_snapshot_hash,
        "dynamic_market_universe_snapshot_hash": dynamic_market_universe[
            "dynamic_market_universe_snapshot_hash"
        ],
        "expected_dynamic_market_universe_snapshot_hash": (
            expected_dynamic_market_universe_snapshot_hash
        ),
        "dynamic_market_universe_status": dynamic_market_universe[
            "dynamic_market_universe_status"
        ],
        "candidate_pool_id": pool.candidate_pool_id,
        "candidate_pool_semantic_hash": pool.semantic_hash,
        "candidate_pool_record_hash": pool.record_hash,
        "hypothesis_candidate_id": hypothesis.candidate_id,
        "hypothesis_candidate_semantic_hash": hypothesis.semantic_hash,
        "hypothesis_candidate_record_hash": hypothesis.record_hash,
        "expected_research_input_identity": deepcopy(
            validated_research_input_identity
        ),
        "membership_lineage_sha256": membership_lineage[
            "membership_lineage_sha256"
        ],
        "membership_lineage_row_snapshot_sha256": membership_lineage[
            "row_snapshot_sha256"
        ],
        "membership_lineage_row_count": membership_lineage["membership_count"],
        "feature_snapshot_sha256": feature_snapshot_sha256,
        "feature_row_count": len(feature_rows),
        "cash_comparator": cash.to_dict(),
        "engine0_rule_sha256": rule_sha256,
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    decision_context_sha256 = canonical_hash(decision_context)

    admitted_rank = 0
    items: list[dict[str, Any]] = []
    for entry in pool.entries:
        if entry.admission_status == "admitted":
            admitted_rank += 1
            rank: int | None = admitted_rank
            signal_action: str | None = "not_selected"
            reason_code = "engine0_cash_baseline_not_selected"
            reason = "Engine-0 holds cash and selects no admitted candidate."
        else:
            rank = None
            signal_action = None
            reason_code = "engine0_inactive_pool_entry"
            reason = "Engine-0 preserves this inactive candidate-pool row without a decision."
        items.append(
            {
                "decision_item_id": f"{decision_id}:{entry.candidate_entry_id}",
                "candidate_entry_id": entry.candidate_entry_id,
                "security_id": entry.security_id,
                "listing_id": entry.listing_id,
                "security_mapping_sha256": entry.security_mapping_sha256,
                "rank": rank,
                "signal_action": signal_action,
                "side": None,
                "risk_status": None,
                "approved_quantity_micros": None,
                "approved_notional_minor": None,
                "currency": None,
                "reason_code": reason_code,
                "reason": reason,
            }
        )

    execution_rule = rule["execution_rule"]
    cost_rule = rule["cost_rule"]
    comparison_rule = rule["comparison_rule"]
    decision = {
        "schema_version": CLOCK_BOUND_SCHEMA_VERSION,
        "record_type": "v2_decision_record",
        "decision_id": decision_id,
        "candidate_pool_id": pool.candidate_pool_id,
        "candidate_pool_hash": pool.semantic_hash,
        "candidate_pool_record_hash": pool.record_hash,
        "policy_arm": "baseline",
        "policy_snapshot": policy,
        "decision_engine_id": rule["decision_engine_id"],
        "decision_engine_version": rule["decision_engine_version"],
        "decision_engine_sha256": rule_sha256,
        "decision_context_id": decision_context_id,
        "decision_context_sha256": decision_context_sha256,
        "execution_rule_id": execution_rule["rule_id"],
        "execution_rule_version": execution_rule["rule_version"],
        "execution_rule_sha256": canonical_hash(execution_rule),
        "cost_rule_id": cost_rule["rule_id"],
        "cost_rule_version": cost_rule["rule_version"],
        "cost_rule_sha256": canonical_hash(cost_rule),
        "comparison_rule_id": comparison_rule["rule_id"],
        "comparison_rule_version": comparison_rule["rule_version"],
        "comparison_rule_sha256": canonical_hash(comparison_rule),
        "items": items,
        "expected_item_count": len(items),
        "decision_complete": True,
        "run_id": pool.run_id,
        "session_clock_id": pool.session_clock_id,
        "session_clock_hash": pool.session_clock_hash,
        "session_clock_record_hash": pool.session_clock_record_hash,
        "run_date": pool.run_date,
        "calendar_session_id": pool.calendar_session_id,
        "data_cutoff": pool.data_cutoff,
        "expected_horizon": hypothesis.expected_horizon,
        "decided_at": decided_at,
        "recorded_at": recorded_at,
        "input_snapshot_sha256": "",
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "known_future_leakage": False,
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    decision["input_snapshot_sha256"] = decision_input_snapshot_hash(
        candidate_pool=pool,
        policy_arm=decision["policy_arm"],
        policy_snapshot=decision["policy_snapshot"],
        decision_engine_id=decision["decision_engine_id"],
        decision_engine_version=decision["decision_engine_version"],
        decision_engine_sha256=decision["decision_engine_sha256"],
        decision_context_id=decision["decision_context_id"],
        decision_context_sha256=decision["decision_context_sha256"],
        execution_rule_id=decision["execution_rule_id"],
        execution_rule_version=decision["execution_rule_version"],
        execution_rule_sha256=decision["execution_rule_sha256"],
        cost_rule_id=decision["cost_rule_id"],
        cost_rule_version=decision["cost_rule_version"],
        cost_rule_sha256=decision["cost_rule_sha256"],
        comparison_rule_id=decision["comparison_rule_id"],
        comparison_rule_version=decision["comparison_rule_version"],
        comparison_rule_sha256=decision["comparison_rule_sha256"],
        items=decision["items"],
        run_id=decision["run_id"],
        session_clock_id=decision["session_clock_id"],
        session_clock_hash=decision["session_clock_hash"],
        session_clock_record_hash=decision["session_clock_record_hash"],
        run_date=decision["run_date"],
        calendar_session_id=decision["calendar_session_id"],
        data_cutoff=decision["data_cutoff"],
        expected_horizon=decision["expected_horizon"],
    )
    semantic_payload = deepcopy(decision)
    semantic_payload.pop("recorded_at")
    decision["semantic_hash"] = canonical_hash(semantic_payload)
    decision["record_hash"] = canonical_hash(decision)

    try:
        validated_decision = validate_decision_record_against_candidate_pool(
            decision, pool, hypothesis
        )
        validate_record_against_session_clock(
            validated_decision,
            session_clock,
            calendar_sessions,
            calendar_evidence,
            calendar_source_contract,
        )
    except V2ContractValidationError as exc:
        raise V2Engine0BaselineError(
            "engine0_decision_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc
    decision = validated_decision.to_dict()

    envelope = {
        "schema_version": SCHEMA_VERSION,
        "record_type": ENGINE0_BASELINE_RECORD_TYPE,
        "engine0_baseline_contract": ENGINE0_BASELINE_CONTRACT,
        "source_frame": market_clock["source_frame"],
        "consumer_stage": "research_only_engine0_cash_baseline",
        "market_decision_clock_snapshot_hash": market_clock[
            "market_decision_clock_snapshot_hash"
        ],
        "dynamic_market_universe_snapshot_hash": dynamic_market_universe[
            "dynamic_market_universe_snapshot_hash"
        ],
        "dynamic_market_universe_status": dynamic_market_universe[
            "dynamic_market_universe_status"
        ],
        "market_universe_scope": dynamic_market_universe[
            "market_universe_scope"
        ],
        "candidate_pool_identity": {
            "candidate_pool_id": pool.candidate_pool_id,
            "semantic_hash": pool.semantic_hash,
            "record_hash": pool.record_hash,
        },
        "hypothesis_candidate_identity": {
            "candidate_id": hypothesis.candidate_id,
            "semantic_hash": hypothesis.semantic_hash,
            "record_hash": hypothesis.record_hash,
        },
        "policy_snapshot": policy,
        "policy_snapshot_sha256": policy_sha256,
        "baseline_rule": rule,
        "baseline_rule_sha256": rule_sha256,
        "feature_rows": feature_rows,
        "feature_snapshot_sha256": feature_snapshot_sha256,
        "decision_context": decision_context,
        "decision_context_sha256": decision_context_sha256,
        "membership_lineage": membership_lineage,
        "membership_lineage_sha256": membership_lineage[
            "membership_lineage_sha256"
        ],
        "decision_record": decision,
        "decision_identity": {
            "decision_id": decision["decision_id"],
            "input_snapshot_sha256": decision["input_snapshot_sha256"],
            "semantic_hash": decision["semantic_hash"],
            "record_hash": decision["record_hash"],
        },
        "engine0_policy_invoked": True,
        "engine0_baseline_established": True,
        "engine0_baseline_scope": "validated_candidate_pool",
        "membership_lineage_status": "verified_exact_rows",
        "external_universe_coverage_status": "unverified",
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "promotion_eligible": False,
        "parity_status": "contract_only_unwired",
        "runtime_parity_status": "unwired",
        "production_parity_status": "unwired",
        "order_intent_count": 0,
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    envelope["engine0_baseline_snapshot_hash"] = canonical_hash(envelope)
    return envelope


# Daily and replay cannot fork Engine-0 policy, ranking, or decision logic.
build_daily_research_only_engine0_cash_baseline = (
    build_research_only_engine0_cash_baseline
)
build_replay_research_only_engine0_cash_baseline = (
    build_research_only_engine0_cash_baseline
)


__all__ = [
    "ENGINE0_BASELINE_CONTRACT",
    "ENGINE0_BASELINE_POLICY",
    "ENGINE0_BASELINE_RECORD_TYPE",
    "ENGINE0_BASELINE_RULE_SHA256",
    "SCHEMA_VERSION",
    "V2Engine0BaselineError",
    "get_engine0_baseline_policy_snapshot",
    "build_research_only_engine0_cash_baseline",
    "build_daily_research_only_engine0_cash_baseline",
    "build_replay_research_only_engine0_cash_baseline",
]
