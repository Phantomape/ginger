"""Shared research-only predictive feature and ranking policy for Ginger V2.

This module is a sibling consumer of the dynamic market-universe snapshot used
by Engine-0.  It derives one outcome-blind claim-support feature for every
CandidatePool row, applies one deterministic ranking rule, and emits a complete
treatment DecisionRecord.  Entry remains disabled: every admitted candidate is
``not_selected`` and no OrderIntent can be produced.

The feature and rank are a reproducible contract surface, not evidence that the
feature predicts returns.  Daily and replay are true aliases of the same pure
builder; scheduler, runtime, production, canonical, paper, and live parity stay
unwired.
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
    research_claim_snapshot_hash,
    validate_candidate_pool,
    validate_decision_record_against_candidate_pool,
    validate_hypothesis_candidate,
    validate_record_against_session_clock,
    validate_research_claim,
    validate_session_clock,
)
from .v2_dynamic_market_universe import (
    FROZEN_RESEARCH_INPUT_IDENTITY_FIELDS,
    V2DynamicMarketUniverseError,
    validate_dynamic_market_universe_snapshot,
)
from .v2_engine0_baseline import ENGINE0_BASELINE_POLICY


SCHEMA_VERSION = 1
PREDICTIVE_POLICY_RECORD_TYPE = "v2_predictive_policy_snapshot"
PREDICTIVE_POLICY_CONTRACT = (
    "v2_research_only_claim_support_feature_rank_policy_v1"
)

_PREDICTIVE_RULE = {
    "rule_id": "v2-research-claim-support-rank-only",
    "rule_version": "1",
    "decision_engine_id": "v2-research-claim-support-ranker",
    "decision_engine_version": "1",
    "feature_rule": {
        "rule_id": "v2-research-claim-support-feature",
        "rule_version": "claim-support-v1",
        "candidate_match": "claim_affected_security_id",
        "evidence_match": "nonempty_claim_candidate_evidence_intersection",
        "value": "max_relevant_claim_confidence_bps",
        "missing_value": None,
    },
    "ranking_rule": {
        "rule_id": "v2-research-claim-support-ranking",
        "rule_version": "claim-support-desc-v1",
        "order": (
            "feature_available_first",
            "claim_support_score_bps_descending",
            "candidate_entry_id_ascending",
        ),
        "inactive_entry_handling": "rank_null",
    },
    "entry_rule": {
        "rule_id": "v2-research-claim-support-no-entry",
        "rule_version": "claim-support-no-entry-v1",
        "admitted_signal_action": "not_selected",
        "inactive_signal_action": None,
        "side": None,
        "risk_status": None,
        "approved_quantity_micros": None,
        "approved_notional_minor": None,
        "currency": None,
    },
    "execution_rule": {
        "rule_id": "v2-research-claim-support-no-order",
        "rule_version": "claim-support-no-order-v1",
        "order_intent_policy": "forbidden",
    },
    "cost_rule": {
        "rule_id": "v2-research-claim-support-no-order-cost",
        "rule_version": "claim-support-no-order-cost-v1",
        "cost_basis": "no_order_no_cost",
    },
    "comparison_rule": {
        "rule_id": "v2-research-claim-support-cash-comparator",
        "rule_version": "claim-support-cash-comparator-v1",
        "comparator_role": "cash",
        "reference_id": "cash",
    },
    "order_intent_count": 0,
}
PREDICTIVE_POLICY_RULE_SHA256 = canonical_hash(_PREDICTIVE_RULE)
PREDICTIVE_FEATURE_RULE_SHA256 = canonical_hash(_PREDICTIVE_RULE["feature_rule"])
PREDICTIVE_RANKING_RULE_SHA256 = canonical_hash(_PREDICTIVE_RULE["ranking_rule"])

PREDICTIVE_POLICY = MappingProxyType(
    {
        "policy_id": "v2-research-claim-support-rank-only",
        "entry_policy_version": "claim-support-no-entry-v1",
        "ranking_policy_version": "claim-support-desc-v1",
        "sizing_policy_version": "claim-support-no-size-v1",
        "exit_policy_version": "claim-support-no-position-v1",
        "cost_policy_version": "claim-support-no-order-cost-v1",
        "parameters_sha256": PREDICTIVE_POLICY_RULE_SHA256,
    }
)


class V2PredictivePolicyError(RuntimeError):
    """Predictive feature/policy construction failed with a stable code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


def _fail(code: str, message: str) -> None:
    raise V2PredictivePolicyError(code, message)


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("predictive_policy_identifier_invalid", f"{field} must be non-empty text")
    return value


def _instant(value: Any, *, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str):
        _fail("predictive_policy_instant_invalid", f"{field} must include a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("predictive_policy_instant_invalid", f"{field} must include a timezone")
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


def get_predictive_policy_snapshot() -> dict[str, Any]:
    """Return a fresh mutable copy of the fixed rank-only treatment policy."""

    return dict(PREDICTIVE_POLICY)


def get_predictive_ranking_rule_snapshot() -> dict[str, Any]:
    """Return the exact ranking rule that CandidatePool must pre-freeze."""

    return deepcopy(_PREDICTIVE_RULE["ranking_rule"])


def _validated_dependencies(
    market_clock_snapshot: Mapping[str, Any],
    dynamic_market_universe_snapshot: Mapping[str, Any],
    candidate_pool: CandidatePool,
    hypothesis_candidate: HypothesisCandidate,
    research_claims: Sequence[ResearchClaim],
    decision_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    decision_source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    universe_events: Sequence[Mapping[str, Any] | UniverseEvent],
    session_clock: SessionClock,
    calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    calendar_source_contract: Mapping[str, Any] | SourceContract,
    *,
    expected_market_clock_snapshot_hash: str,
    expected_dynamic_market_universe_snapshot_hash: str,
    expected_research_input_identity: Mapping[str, Any],
    baseline_policy_snapshot: Mapping[str, Any],
    predictive_policy_snapshot: Mapping[str, Any],
    ranking_rule_snapshot: Mapping[str, Any],
    ranking_rule_sha256: str,
) -> tuple[
    dict[str, Any],
    CandidatePool,
    HypothesisCandidate,
    tuple[ResearchClaim, ...],
    SessionClock,
]:
    try:
        dynamic_market_universe = validate_dynamic_market_universe_snapshot(
            dynamic_market_universe_snapshot,
            market_clock_snapshot,
            candidate_pool.to_dict(),
            hypothesis_candidate.to_dict(),
            [claim.to_dict() for claim in research_claims],
            decision_evidence_records,
            decision_source_contracts,
            universe_events,
            session_clock.to_dict(),
            calendar_sessions,
            calendar_evidence,
            calendar_source_contract,
            expected_snapshot_hash=expected_dynamic_market_universe_snapshot_hash,
            expected_market_clock_snapshot_hash=expected_market_clock_snapshot_hash,
            expected_research_input_identity=expected_research_input_identity,
        )
    except V2DynamicMarketUniverseError as exc:
        raise V2PredictivePolicyError(
            "predictive_policy_dynamic_market_universe_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc

    observed_research_identity = {
        "candidate_pool_id": candidate_pool.candidate_pool_id,
        "candidate_pool_semantic_hash": candidate_pool.semantic_hash,
        "candidate_pool_record_hash": candidate_pool.record_hash,
        "candidate_pool_input_snapshot_sha256": candidate_pool.input_snapshot_sha256,
        "hypothesis_candidate_id": hypothesis_candidate.candidate_id,
        "hypothesis_candidate_semantic_hash": hypothesis_candidate.semantic_hash,
        "hypothesis_candidate_record_hash": hypothesis_candidate.record_hash,
    }
    dynamic_research_identity = {
        field: dynamic_market_universe["input_identity"][field]
        for field in sorted(FROZEN_RESEARCH_INPUT_IDENTITY_FIELDS)
    }
    if observed_research_identity != dynamic_research_identity:
        _fail(
            "predictive_policy_reconstructed_identity_mismatch",
            "reconstructed pool or hypothesis differs from the validated dynamic boundary",
        )
    if canonical_hash(hypothesis_candidate.baseline_policy) != canonical_hash(
        baseline_policy_snapshot
    ):
        _fail(
            "predictive_policy_engine0_baseline_mismatch",
            "hypothesis baseline policy must exactly equal Engine-0",
        )
    if canonical_hash(hypothesis_candidate.treatment_policy) != canonical_hash(
        predictive_policy_snapshot
    ):
        _fail(
            "predictive_policy_treatment_mismatch",
            "hypothesis treatment policy must exactly equal the shared policy",
        )
    if (
        candidate_pool.ranking_rule_id != ranking_rule_snapshot["rule_id"]
        or candidate_pool.ranking_rule_version
        != ranking_rule_snapshot["rule_version"]
        or candidate_pool.ranking_rule_sha256 != ranking_rule_sha256
    ):
        _fail(
            "predictive_policy_pool_ranking_rule_mismatch",
            "CandidatePool must pre-freeze the exact shared ranking rule identity",
        )

    claims_by_id: dict[str, ResearchClaim] = {}
    for claim in research_claims:
        if claim.claim_id in claims_by_id:
            _fail(
                "predictive_policy_duplicate_claim_id",
                f"duplicate claim id {claim.claim_id}",
            )
        claims_by_id[claim.claim_id] = claim
    missing_claim_ids = [
        claim_id
        for claim_id in hypothesis_candidate.research_claim_ids
        if claim_id not in claims_by_id
    ]
    if missing_claim_ids:
        _fail(
            "predictive_policy_unresolved_claim_id",
            f"unresolved claim ids: {', '.join(missing_claim_ids)}",
        )
    referenced_claims = tuple(
        claims_by_id[claim_id] for claim_id in hypothesis_candidate.research_claim_ids
    )
    if (
        research_claim_snapshot_hash(referenced_claims)
        != hypothesis_candidate.claim_snapshot_sha256
    ):
        _fail(
            "predictive_policy_claim_snapshot_mismatch",
            "reconstructed claims differ from the hypothesis claim snapshot",
        )
    return (
        dynamic_market_universe,
        candidate_pool,
        hypothesis_candidate,
        referenced_claims,
        session_clock,
    )


def _build_feature_rows(
    *,
    decision_id: str,
    pool: CandidatePool,
    claims: Sequence[ResearchClaim],
    feature_rule_sha256: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in pool.entries:
        entry_evidence_ids = set(entry.evidence_record_ids)
        relevant = sorted(
            (
                claim
                for claim in claims
                if entry.security_id in claim.affected_object_ids
                and entry_evidence_ids.intersection(claim.evidence_record_ids)
            ),
            key=lambda claim: claim.claim_id,
        )
        claim_identities = [
            {
                "claim_id": claim.claim_id,
                "semantic_hash": claim.semantic_hash,
                "record_hash": claim.record_hash,
                "confidence_bps": claim.confidence_bps,
                "recorded_at": claim.recorded_at,
            }
            for claim in relevant
        ]
        feature_input = {
            "candidate_entry_id": entry.candidate_entry_id,
            "security_id": entry.security_id,
            "listing_id": entry.listing_id,
            "security_mapping_sha256": entry.security_mapping_sha256,
            "decision_input_sha256": entry.decision_input_sha256,
            "feature_rule_sha256": feature_rule_sha256,
            "claim_identities": claim_identities,
        }
        row = {
            "feature_row_id": (
                f"{decision_id}:{entry.candidate_entry_id}:claim-support-v1"
            ),
            "candidate_entry_id": entry.candidate_entry_id,
            "security_id": entry.security_id,
            "listing_id": entry.listing_id,
            "security_mapping_sha256": entry.security_mapping_sha256,
            "decision_input_sha256": entry.decision_input_sha256,
            "admission_status": entry.admission_status,
            "feature_name": "max_relevant_claim_confidence_bps",
            "feature_status": "available" if relevant else "unavailable",
            "claim_support_score_bps": (
                max(claim.confidence_bps for claim in relevant)
                if relevant
                else None
            ),
            "feature_available_at": (
                max(claim.recorded_at for claim in relevant) if relevant else None
            ),
            "contributing_claims": claim_identities,
            "feature_input_sha256": canonical_hash(feature_input),
        }
        row["feature_row_sha256"] = canonical_hash(row)
        rows.append(row)
    return rows


def _build_ranked_candidates(
    *,
    decision_id: str,
    pool: CandidatePool,
    feature_rows: Sequence[Mapping[str, Any]],
    ranking_rule_sha256: str,
) -> list[dict[str, Any]]:
    features = {row["candidate_entry_id"]: row for row in feature_rows}
    admitted = [
        entry for entry in pool.entries if entry.admission_status == "admitted"
    ]
    ordered = sorted(
        admitted,
        key=lambda entry: (
            features[entry.candidate_entry_id]["claim_support_score_bps"] is None,
            -(
                features[entry.candidate_entry_id]["claim_support_score_bps"]
                or 0
            ),
            entry.candidate_entry_id,
        ),
    )
    rank_by_entry_id = {
        entry.candidate_entry_id: rank
        for rank, entry in enumerate(ordered, start=1)
    }
    rows: list[dict[str, Any]] = []
    for entry in pool.entries:
        feature = features[entry.candidate_entry_id]
        row = {
            "ranked_candidate_id": (
                f"{decision_id}:{entry.candidate_entry_id}:rank-v1"
            ),
            "candidate_entry_id": entry.candidate_entry_id,
            "security_id": entry.security_id,
            "listing_id": entry.listing_id,
            "security_mapping_sha256": entry.security_mapping_sha256,
            "admission_status": entry.admission_status,
            "feature_row_sha256": feature["feature_row_sha256"],
            "claim_support_score_bps": feature["claim_support_score_bps"],
            "rank": rank_by_entry_id.get(entry.candidate_entry_id),
            "ranking_status": (
                "ranked" if entry.admission_status == "admitted" else "inactive"
            ),
            "ranking_rule_sha256": ranking_rule_sha256,
        }
        row["ranked_candidate_sha256"] = canonical_hash(row)
        rows.append(row)
    return rows


def _build_signal_decisions(
    *,
    decision_id: str,
    pool: CandidatePool,
    ranked_candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ranked = {row["candidate_entry_id"]: row for row in ranked_candidates}
    rows: list[dict[str, Any]] = []
    for entry in pool.entries:
        rank = ranked[entry.candidate_entry_id]
        admitted = entry.admission_status == "admitted"
        row = {
            "signal_decision_id": (
                f"{decision_id}:{entry.candidate_entry_id}:signal-v1"
            ),
            "candidate_entry_id": entry.candidate_entry_id,
            "security_id": entry.security_id,
            "listing_id": entry.listing_id,
            "security_mapping_sha256": entry.security_mapping_sha256,
            "ranked_candidate_sha256": rank["ranked_candidate_sha256"],
            "rank": rank["rank"],
            "signal_action": "not_selected" if admitted else None,
            "selection_status": (
                "disabled_contract_only" if admitted else "inactive"
            ),
            "reason_code": (
                "predictive_policy_entry_disabled"
                if admitted
                else "predictive_policy_inactive_pool_entry"
            ),
            "reason": (
                "The shared feature/ranking contract is established, but entry "
                "selection remains disabled until an experiment freezes a "
                "directional policy."
                if admitted
                else "The inactive CandidatePool row is preserved without a signal."
            ),
        }
        row["signal_decision_sha256"] = canonical_hash(row)
        rows.append(row)
    return rows


def build_research_only_predictive_policy(
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
    """Build one complete claim-support feature/rank treatment decision."""

    # Freeze every executable rule and policy before touching caller-controlled
    # objects.  Dependency validators may invoke custom Mapping/Sequence methods;
    # no such callback may change the rule that is later emitted or executed.
    rule = deepcopy(_PREDICTIVE_RULE)
    rule_sha256 = canonical_hash(rule)
    expected_rule_sha256 = PREDICTIVE_POLICY_RULE_SHA256
    feature_rule_sha256 = canonical_hash(rule["feature_rule"])
    ranking_rule = deepcopy(rule["ranking_rule"])
    ranking_rule_sha256 = canonical_hash(ranking_rule)
    policy = dict(PREDICTIVE_POLICY)
    policy_sha256 = canonical_hash(policy)
    baseline_policy = dict(ENGINE0_BASELINE_POLICY)
    baseline_policy_sha256 = canonical_hash(baseline_policy)
    if (
        rule_sha256 != expected_rule_sha256
        or feature_rule_sha256 != PREDICTIVE_FEATURE_RULE_SHA256
        or ranking_rule_sha256 != PREDICTIVE_RANKING_RULE_SHA256
    ):
        _fail(
            "predictive_policy_rule_identity_mismatch",
            "runtime predictive rule differs from its frozen identity",
        )
    if policy["parameters_sha256"] != rule_sha256:
        _fail(
            "predictive_policy_snapshot_identity_mismatch",
            "runtime policy differs from its frozen rule identity",
        )

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

    # Materialize every dependency reused after the dynamic boundary exactly
    # once.  From this point forward the builder consumes only immutable
    # dataclasses, never caller-owned Mapping objects.
    try:
        validated_pool = validate_candidate_pool(candidate_pool)
        validated_hypothesis = validate_hypothesis_candidate(
            hypothesis_candidate
        )
        validated_claims = tuple(
            validate_research_claim(item) for item in research_claims
        )
        validated_clock = validate_session_clock(session_clock)
    except V2ContractValidationError as exc:
        raise V2PredictivePolicyError(
            "predictive_policy_research_input_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc

    dynamic_market_universe, pool, hypothesis, claims, validated_clock = (
        _validated_dependencies(
            market_clock_snapshot,
            dynamic_market_universe_snapshot,
            validated_pool,
            validated_hypothesis,
            validated_claims,
            decision_evidence_records,
            decision_source_contracts,
            universe_events,
            validated_clock,
            calendar_sessions,
            calendar_evidence,
            calendar_source_contract,
            expected_market_clock_snapshot_hash=expected_market_clock_snapshot_hash,
            expected_dynamic_market_universe_snapshot_hash=(
                expected_dynamic_market_universe_snapshot_hash
            ),
            expected_research_input_identity=expected_research_input_identity,
            baseline_policy_snapshot=baseline_policy,
            predictive_policy_snapshot=policy,
            ranking_rule_snapshot=ranking_rule,
            ranking_rule_sha256=ranking_rule_sha256,
        )
    )

    decision_id = _text(decision_id, field="decision_id")
    decided_at, decided_dt = _instant(decided_at, field="decided_at")
    recorded_at, recorded_dt = _instant(recorded_at, field="recorded_at")
    _, pool_recorded_dt = _instant(
        pool.recorded_at, field="candidate_pool.recorded_at"
    )
    _, session_open_dt = _instant(
        validated_clock.session_open_at,
        field="session_clock.session_open_at",
    )
    if not (pool_recorded_dt <= decided_dt <= recorded_dt < session_open_dt):
        _fail(
            "predictive_policy_decision_chronology_invalid",
            "must satisfy pool recorded_at <= decided_at <= recorded_at < session open",
        )

    feature_rows = _build_feature_rows(
        decision_id=decision_id,
        pool=pool,
        claims=claims,
        feature_rule_sha256=feature_rule_sha256,
    )
    feature_snapshot_sha256 = canonical_hash(feature_rows)
    ranked_candidates = _build_ranked_candidates(
        decision_id=decision_id,
        pool=pool,
        feature_rows=feature_rows,
        ranking_rule_sha256=ranking_rule_sha256,
    )
    ranked_candidate_snapshot_sha256 = canonical_hash(ranked_candidates)
    signal_decisions = _build_signal_decisions(
        decision_id=decision_id,
        pool=pool,
        ranked_candidates=ranked_candidates,
    )
    signal_decision_snapshot_sha256 = canonical_hash(signal_decisions)
    validated_research_input_identity = {
        field: dynamic_market_universe["input_identity"][field]
        for field in sorted(FROZEN_RESEARCH_INPUT_IDENTITY_FIELDS)
    }
    decision_context_id = f"{decision_id}:research-predictive-context-v1"
    decision_context = {
        "context_type": "v2_predictive_policy_decision_context",
        "context_version": "1",
        "decision_context_id": decision_context_id,
        "market_decision_clock_snapshot_hash": dynamic_market_universe[
            "input_identity"
        ]["market_decision_clock_snapshot_hash"],
        "expected_market_clock_snapshot_hash": expected_market_clock_snapshot_hash,
        "dynamic_market_universe_snapshot_hash": dynamic_market_universe[
            "dynamic_market_universe_snapshot_hash"
        ],
        "expected_dynamic_market_universe_snapshot_hash": (
            expected_dynamic_market_universe_snapshot_hash
        ),
        "candidate_pool_id": pool.candidate_pool_id,
        "candidate_pool_semantic_hash": pool.semantic_hash,
        "candidate_pool_record_hash": pool.record_hash,
        "hypothesis_candidate_id": hypothesis.candidate_id,
        "hypothesis_candidate_semantic_hash": hypothesis.semantic_hash,
        "hypothesis_candidate_record_hash": hypothesis.record_hash,
        "expected_research_input_identity": deepcopy(
            validated_research_input_identity
        ),
        "membership_lineage_sha256": dynamic_market_universe[
            "membership_lineage_sha256"
        ],
        "feature_snapshot_sha256": feature_snapshot_sha256,
        "feature_row_count": len(feature_rows),
        "ranked_candidate_snapshot_sha256": ranked_candidate_snapshot_sha256,
        "ranked_candidate_count": len(ranked_candidates),
        "signal_decision_snapshot_sha256": signal_decision_snapshot_sha256,
        "signal_decision_count": len(signal_decisions),
        "predictive_policy_sha256": policy_sha256,
        "predictive_rule_sha256": rule_sha256,
        "entry_selection_enabled": False,
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    decision_context_sha256 = canonical_hash(decision_context)

    signals = {row["candidate_entry_id"]: row for row in signal_decisions}
    items = []
    for entry in pool.entries:
        signal = signals[entry.candidate_entry_id]
        items.append(
            {
                "decision_item_id": f"{decision_id}:{entry.candidate_entry_id}",
                "candidate_entry_id": entry.candidate_entry_id,
                "security_id": entry.security_id,
                "listing_id": entry.listing_id,
                "security_mapping_sha256": entry.security_mapping_sha256,
                "rank": signal["rank"],
                "signal_action": signal["signal_action"],
                "side": None,
                "risk_status": None,
                "approved_quantity_micros": None,
                "approved_notional_minor": None,
                "currency": None,
                "reason_code": signal["reason_code"],
                "reason": signal["reason"],
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
        "policy_arm": "treatment",
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
            validated_clock,
            calendar_sessions,
            calendar_evidence,
            calendar_source_contract,
        )
    except V2ContractValidationError as exc:
        raise V2PredictivePolicyError(
            "predictive_policy_decision_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc
    decision = validated_decision.to_dict()

    envelope = {
        "schema_version": SCHEMA_VERSION,
        "record_type": PREDICTIVE_POLICY_RECORD_TYPE,
        "predictive_policy_contract": PREDICTIVE_POLICY_CONTRACT,
        "source_frame": dynamic_market_universe["source_frame"],
        "consumer_stage": "research_only_shared_predictive_feature_policy",
        "market_decision_clock_snapshot_hash": dynamic_market_universe[
            "input_identity"
        ]["market_decision_clock_snapshot_hash"],
        "dynamic_market_universe_snapshot_hash": dynamic_market_universe[
            "dynamic_market_universe_snapshot_hash"
        ],
        "dynamic_market_universe_status": dynamic_market_universe[
            "dynamic_market_universe_status"
        ],
        "market_universe_scope": dynamic_market_universe["market_universe_scope"],
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
        "baseline_policy_snapshot": baseline_policy,
        "baseline_policy_snapshot_sha256": baseline_policy_sha256,
        "predictive_policy_snapshot": policy,
        "predictive_policy_snapshot_sha256": policy_sha256,
        "predictive_rule": rule,
        "predictive_rule_sha256": rule_sha256,
        "feature_rows": feature_rows,
        "feature_snapshot_sha256": feature_snapshot_sha256,
        "ranked_candidates": ranked_candidates,
        "ranked_candidate_snapshot_sha256": ranked_candidate_snapshot_sha256,
        "signal_decisions": signal_decisions,
        "signal_decision_snapshot_sha256": signal_decision_snapshot_sha256,
        "decision_context": decision_context,
        "decision_context_sha256": decision_context_sha256,
        "decision_record": decision,
        "decision_identity": {
            "decision_id": decision["decision_id"],
            "input_snapshot_sha256": decision["input_snapshot_sha256"],
            "semantic_hash": decision["semantic_hash"],
            "record_hash": decision["record_hash"],
        },
        "predictive_feature_contract_established": True,
        "predictive_ranking_policy_established": True,
        "predictive_efficacy_status": "unvalidated_contract_only",
        "entry_selection_enabled": False,
        "signal_policy_status": "disabled_pending_frozen_experiment",
        "membership_lineage_status": "verified_exact_rows",
        "external_universe_coverage_status": "unverified",
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "promotion_eligible": False,
        "parity_status": "contract_only_unwired",
        "shared_policy_parity_status": (
            "daily_replay_alias_verified_research_only"
        ),
        "runtime_parity_status": "unwired",
        "production_parity_status": "unwired",
        "order_intent_count": 0,
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    envelope["predictive_policy_snapshot_hash"] = canonical_hash(envelope)
    return envelope


# Daily and replay cannot fork feature, ranking, or treatment-decision logic.
build_daily_research_only_predictive_policy = build_research_only_predictive_policy
build_replay_research_only_predictive_policy = build_research_only_predictive_policy


__all__ = [
    "PREDICTIVE_POLICY",
    "PREDICTIVE_POLICY_CONTRACT",
    "PREDICTIVE_FEATURE_RULE_SHA256",
    "PREDICTIVE_POLICY_RECORD_TYPE",
    "PREDICTIVE_POLICY_RULE_SHA256",
    "PREDICTIVE_RANKING_RULE_SHA256",
    "SCHEMA_VERSION",
    "V2PredictivePolicyError",
    "get_predictive_policy_snapshot",
    "get_predictive_ranking_rule_snapshot",
    "build_research_only_predictive_policy",
    "build_daily_research_only_predictive_policy",
    "build_replay_research_only_predictive_policy",
]
