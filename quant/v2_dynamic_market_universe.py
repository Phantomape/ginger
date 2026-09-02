"""Research-only dynamic PIT market-universe snapshot for Ginger V2.

The snapshot is a post-CandidatePool reconciliation boundary: it binds one
separately frozen market-decision clock to the complete CandidatePool
``UniverseEvent`` population at that clock's assignment cutoff.  It preserves
every current membership state and stops before predictive features, ranking,
signals, sizing, outcomes, or orders.  It does not generate CandidatePool.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any, Mapping, Sequence

from .v2_contracts import (
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
    validate_candidate_pool,
    validate_candidate_pool_against_inputs,
    validate_hypothesis_candidate,
    validate_record_against_session_clock,
)
from .v2_market_decision_clock import (
    V2MarketDecisionClockError,
    validate_market_decision_clock_snapshot,
)
from .v2_universe_ledger import (
    V2UniverseLedgerError,
    validate_universe_event_population,
)


SCHEMA_VERSION = 1
DYNAMIC_MARKET_UNIVERSE_RECORD_TYPE = "v2_dynamic_market_universe_snapshot"
DYNAMIC_MARKET_UNIVERSE_CONTRACT = (
    "v2_research_only_dynamic_pit_market_universe_v1"
)

FROZEN_RESEARCH_INPUT_IDENTITY_FIELDS = frozenset(
    {
        "candidate_pool_id",
        "candidate_pool_semantic_hash",
        "candidate_pool_record_hash",
        "candidate_pool_input_snapshot_sha256",
        "hypothesis_candidate_id",
        "hypothesis_candidate_semantic_hash",
        "hypothesis_candidate_record_hash",
    }
)

_SNAPSHOT_FIELDS = {
    "schema_version",
    "record_type",
    "dynamic_market_universe_contract",
    "source_frame",
    "consumer_stage",
    "input_identity",
    "input_identity_sha256",
    "membership_lineage",
    "membership_lineage_sha256",
    "state_counts",
    "market_universe_scope",
    "dynamic_market_universe_status",
    "candidate_surface_status",
    "market_decision_clock_status",
    "engine0_policy_invoked",
    "engine0_baseline_established",
    "external_universe_coverage_status",
    "pit_tier",
    "result_ceiling",
    "paper_live_eligible",
    "promotion_eligible",
    "parity_status",
    "runtime_parity_status",
    "production_parity_status",
    "outcome_blind",
    "results_accessed",
    "authority",
    "trade_enabled",
    "dynamic_market_universe_snapshot_hash",
}
_UNIVERSE_STATES = (
    "discovered",
    "research_eligible",
    "candidate_eligible",
    "quarantine",
    "retired",
)


class V2DynamicMarketUniverseError(RuntimeError):
    """Dynamic market-universe construction failed with a stable code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


def _fail(code: str, message: str) -> None:
    raise V2DynamicMarketUniverseError(code, message)


def _instant(value: Any, *, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str):
        _fail("dynamic_market_universe_instant_invalid", f"{field} must include a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("dynamic_market_universe_instant_invalid", f"{field} must include a timezone")
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


def _validate_research_boundary(
    record: CandidatePool | HypothesisCandidate, *, label: str
) -> None:
    if (
        record.pit_tier != "research_pit"
        or record.result_ceiling != "observed_only"
        or record.known_future_leakage is not False
        or record.outcome_blind is not True
        or record.results_accessed is not False
        or record.authority != "research_only"
        or record.trade_enabled is not False
    ):
        _fail(
            "dynamic_market_universe_research_boundary_mismatch",
            f"{label} must be research_pit, observed-only, outcome-blind, and default-off",
        )


def _validated_dependencies(
    market_clock_snapshot: Mapping[str, Any],
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
    expected_research_input_identity: Mapping[str, Any],
) -> tuple[
    dict[str, Any],
    CandidatePool,
    HypothesisCandidate,
    tuple[UniverseEvent, ...],
    list[dict[str, Any]],
]:
    expected_research_input_identity = _freeze_record(
        expected_research_input_identity
    )
    market_clock_snapshot = _freeze_record(market_clock_snapshot)
    candidate_pool = _freeze_record(candidate_pool)
    hypothesis_candidate = _freeze_record(hypothesis_candidate)
    research_claims = _freeze_sequence(research_claims)
    decision_evidence_records = _freeze_sequence(decision_evidence_records)
    decision_source_contracts = _freeze_sequence(decision_source_contracts)
    universe_events = _freeze_sequence(universe_events)
    session_clock = _freeze_record(session_clock)
    calendar_sessions = _freeze_sequence(calendar_sessions)
    calendar_evidence = _freeze_record(calendar_evidence)
    calendar_source_contract = _freeze_record(calendar_source_contract)
    try:
        market_clock = validate_market_decision_clock_snapshot(
            market_clock_snapshot,
            session_clock,
            calendar_sessions,
            calendar_evidence,
            calendar_source_contract,
            expected_snapshot_hash=expected_market_clock_snapshot_hash,
        )
    except V2MarketDecisionClockError as exc:
        raise V2DynamicMarketUniverseError(
            "dynamic_market_universe_market_clock_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc
    try:
        pool = validate_candidate_pool(candidate_pool)
        hypothesis = validate_hypothesis_candidate(hypothesis_candidate)
    except V2ContractValidationError as exc:
        raise V2DynamicMarketUniverseError(
            "dynamic_market_universe_research_input_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc

    if (
        not isinstance(expected_research_input_identity, Mapping)
        or set(expected_research_input_identity)
        != FROZEN_RESEARCH_INPUT_IDENTITY_FIELDS
    ):
        _fail(
            "dynamic_market_universe_frozen_research_identity_invalid",
            "expected research input identity has an unexpected field surface",
        )
    expected_identity = dict(expected_research_input_identity)
    observed_identity = {
        "candidate_pool_id": pool.candidate_pool_id,
        "candidate_pool_semantic_hash": pool.semantic_hash,
        "candidate_pool_record_hash": pool.record_hash,
        "candidate_pool_input_snapshot_sha256": pool.input_snapshot_sha256,
        "hypothesis_candidate_id": hypothesis.candidate_id,
        "hypothesis_candidate_semantic_hash": hypothesis.semantic_hash,
        "hypothesis_candidate_record_hash": hypothesis.record_hash,
    }
    if expected_identity != observed_identity:
        _fail(
            "dynamic_market_universe_frozen_research_identity_mismatch",
            "candidate-pool or hypothesis identity differs from the separately frozen input",
        )

    _validate_research_boundary(pool, label="candidate pool")
    _validate_research_boundary(hypothesis, label="hypothesis candidate")
    if (
        pool.hypothesis_candidate_id != hypothesis.candidate_id
        or pool.hypothesis_candidate_hash != hypothesis.semantic_hash
    ):
        _fail(
            "dynamic_market_universe_pool_hypothesis_binding_mismatch",
            "candidate pool must bind the supplied hypothesis id and semantic hash",
        )

    clock_identity = market_clock["input_identity"]
    if (
        pool.universe_id != clock_identity["universe_id"]
        or pool.run_id != clock_identity["run_id"]
        or pool.session_clock_id != clock_identity["session_clock_id"]
        or pool.session_clock_hash != clock_identity["session_clock_semantic_hash"]
        or pool.session_clock_record_hash != clock_identity["session_clock_record_hash"]
        or pool.run_date != clock_identity["run_date"]
        or pool.calendar_session_id != clock_identity["calendar_session_id"]
        or pool.data_cutoff != clock_identity["assignment_cutoff"]
    ):
        _fail(
            "dynamic_market_universe_market_pool_identity_mismatch",
            "pool universe, run, clock, session, date, and cutoff must match the market clock",
        )
    _, hypothesis_recorded_dt = _instant(
        hypothesis.recorded_at, field="hypothesis_candidate.recorded_at"
    )
    _, assignment_cutoff_dt = _instant(
        clock_identity["assignment_cutoff"], field="market_clock.assignment_cutoff"
    )
    if hypothesis_recorded_dt > assignment_cutoff_dt:
        _fail(
            "dynamic_market_universe_hypothesis_after_cutoff",
            "hypothesis must be recorded no later than the market-clock assignment cutoff",
        )

    try:
        validate_record_against_session_clock(
            pool,
            session_clock,
            calendar_sessions,
            calendar_evidence,
            calendar_source_contract,
        )
        pool = validate_candidate_pool_against_inputs(
            pool,
            hypothesis,
            research_claims,
            decision_evidence_records,
            decision_source_contracts,
            universe_events,
        )
    except V2ContractValidationError as exc:
        raise V2DynamicMarketUniverseError(
            "dynamic_market_universe_research_graph_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc
    try:
        ordered_events, projected_memberships = validate_universe_event_population(
            universe_events,
            universe_id=pool.universe_id,
            data_cutoff=pool.data_cutoff,
            frozen_at=pool.frozen_at,
            membership_as_of=clock_identity["assignment_cutoff"],
        )
    except V2UniverseLedgerError as exc:
        raise V2DynamicMarketUniverseError(
            "dynamic_market_universe_population_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc
    if projected_memberships != market_clock["memberships"]:
        _fail(
            "dynamic_market_universe_membership_lineage_mismatch",
            "market-clock memberships must exactly equal the supplied UniverseEvent projection",
        )
    return market_clock, pool, hypothesis, ordered_events, projected_memberships


def _snapshot_payload(
    market_clock: Mapping[str, Any],
    pool: CandidatePool,
    hypothesis: HypothesisCandidate,
    ordered_events: Sequence[UniverseEvent],
    projected_memberships: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    exact_event_rows = [
        {
            "event_id": event.event_id,
            "semantic_hash": event.semantic_hash,
            "record_hash": event.event_hash,
        }
        for event in sorted(ordered_events, key=lambda item: item.event_id)
    ]
    exact_event_snapshot_sha256 = canonical_hash(exact_event_rows)
    exact_membership_snapshot_sha256 = canonical_hash(projected_memberships)

    lineage_rows: list[dict[str, Any]] = []
    for market_row, projected_row in zip(
        market_clock["memberships"], projected_memberships, strict=True
    ):
        row = {
            **deepcopy(market_row),
            "market_clock_membership_row_sha256": canonical_hash(market_row),
            "universe_event_projection_row_sha256": canonical_hash(projected_row),
        }
        row["lineage_row_sha256"] = canonical_hash(row)
        lineage_rows.append(row)
    membership_lineage = {
        "lineage_type": "v2_dynamic_market_universe_membership_lineage",
        "lineage_version": "1",
        "universe_id": pool.universe_id,
        "membership_as_of": market_clock["input_identity"]["assignment_cutoff"],
        "market_decision_clock_snapshot_hash": market_clock[
            "market_decision_clock_snapshot_hash"
        ],
        "market_clock_membership_snapshot_sha256": market_clock["input_identity"]
        ["membership_snapshot_sha256"],
        "market_clock_exact_membership_snapshot_sha256": exact_membership_snapshot_sha256,
        "candidate_pool_id": pool.candidate_pool_id,
        "candidate_pool_universe_event_snapshot_sha256": (
            pool.universe_event_snapshot_sha256
        ),
        "universe_event_record_snapshot_sha256": exact_event_snapshot_sha256,
        "membership_count": len(lineage_rows),
        "row_snapshot_sha256": canonical_hash(lineage_rows),
        "rows": lineage_rows,
    }
    membership_lineage["membership_lineage_sha256"] = canonical_hash(
        membership_lineage
    )

    clock_identity = market_clock["input_identity"]
    input_identity = {
        "market_decision_clock_snapshot_hash": market_clock[
            "market_decision_clock_snapshot_hash"
        ],
        "market_decision_clock_input_identity_sha256": market_clock[
            "input_identity_sha256"
        ],
        "candidate_pool_id": pool.candidate_pool_id,
        "candidate_pool_semantic_hash": pool.semantic_hash,
        "candidate_pool_record_hash": pool.record_hash,
        "candidate_pool_input_snapshot_sha256": pool.input_snapshot_sha256,
        "candidate_pool_frozen_at": pool.frozen_at,
        "candidate_pool_recorded_at": pool.recorded_at,
        "hypothesis_candidate_id": hypothesis.candidate_id,
        "hypothesis_candidate_semantic_hash": hypothesis.semantic_hash,
        "hypothesis_candidate_record_hash": hypothesis.record_hash,
        "universe_id": pool.universe_id,
        "run_id": pool.run_id,
        "session_clock_id": pool.session_clock_id,
        "session_clock_semantic_hash": pool.session_clock_hash,
        "session_clock_record_hash": pool.session_clock_record_hash,
        "run_date": pool.run_date,
        "calendar_session_id": pool.calendar_session_id,
        "assignment_cutoff": pool.data_cutoff,
        "universe_event_count": len(ordered_events),
        "universe_event_semantic_snapshot_sha256": (
            pool.universe_event_snapshot_sha256
        ),
        "universe_event_record_snapshot_sha256": exact_event_snapshot_sha256,
        "candidate_entry_count": len(pool.entries),
        "membership_count": len(projected_memberships),
        "membership_semantic_snapshot_sha256": clock_identity[
            "membership_snapshot_sha256"
        ],
        "membership_exact_snapshot_sha256": exact_membership_snapshot_sha256,
    }
    state_counts = {
        state: sum(1 for row in projected_memberships if row["state"] == state)
        for state in _UNIVERSE_STATES
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": DYNAMIC_MARKET_UNIVERSE_RECORD_TYPE,
        "dynamic_market_universe_contract": DYNAMIC_MARKET_UNIVERSE_CONTRACT,
        "source_frame": market_clock["source_frame"],
        "consumer_stage": (
            "post_candidate_pool_pre_predictive_policy_dynamic_market_universe"
        ),
        "input_identity": input_identity,
        "input_identity_sha256": canonical_hash(input_identity),
        "membership_lineage": membership_lineage,
        "membership_lineage_sha256": membership_lineage[
            "membership_lineage_sha256"
        ],
        "state_counts": state_counts,
        "market_universe_scope": (
            "source_bound_post_candidate_pool_reconciliation"
        ),
        "dynamic_market_universe_status": "verified_exact_rows_research_only",
        "candidate_surface_status": "candidate_eligible_exactly_matches_candidate_pool",
        "market_decision_clock_status": "bound_research_only",
        "engine0_policy_invoked": False,
        "engine0_baseline_established": False,
        "external_universe_coverage_status": "unverified",
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "promotion_eligible": False,
        "parity_status": "contract_only_unwired",
        "runtime_parity_status": "unwired",
        "production_parity_status": "unwired",
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }


def validate_dynamic_market_universe_snapshot(
    value: Mapping[str, Any],
    market_clock_snapshot: Mapping[str, Any],
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
    expected_snapshot_hash: str,
    expected_market_clock_snapshot_hash: str,
    expected_research_input_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a dynamic universe snapshot against separately frozen inputs."""

    expected_research_input_identity = _freeze_record(
        expected_research_input_identity
    )
    if not isinstance(value, Mapping) or set(value) != _SNAPSHOT_FIELDS:
        _fail(
            "dynamic_market_universe_snapshot_shape_invalid",
            "dynamic market-universe snapshot has an unexpected field surface",
        )
    snapshot = deepcopy(dict(value))
    supplied_hash = snapshot.get("dynamic_market_universe_snapshot_hash")
    if (
        not isinstance(expected_snapshot_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_snapshot_hash) is None
        or supplied_hash != expected_snapshot_hash
    ):
        _fail(
            "dynamic_market_universe_expected_hash_mismatch",
            "dynamic market-universe snapshot does not match the separately frozen identity",
        )
    payload = deepcopy(snapshot)
    payload.pop("dynamic_market_universe_snapshot_hash", None)
    try:
        observed_hash = canonical_hash(payload)
    except V2ContractValidationError as exc:
        raise V2DynamicMarketUniverseError(
            "dynamic_market_universe_snapshot_hash_invalid",
            f"{exc.code}: {exc.detail}",
        ) from exc
    if supplied_hash != observed_hash:
        _fail(
            "dynamic_market_universe_snapshot_hash_mismatch",
            "dynamic market-universe snapshot hash is invalid",
        )

    dependencies = _validated_dependencies(
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
        expected_market_clock_snapshot_hash=expected_market_clock_snapshot_hash,
        expected_research_input_identity=expected_research_input_identity,
    )
    expected_payload = _snapshot_payload(*dependencies)
    if observed_hash != canonical_hash(expected_payload):
        _fail(
            "dynamic_market_universe_snapshot_dependency_mismatch",
            "dynamic market-universe snapshot differs from its validated dependencies",
        )
    expected_payload["dynamic_market_universe_snapshot_hash"] = observed_hash
    return expected_payload


def build_research_only_dynamic_market_universe_snapshot(
    market_clock_snapshot: Mapping[str, Any],
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
    expected_research_input_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one post-pool, source-bounded dynamic PIT reconciliation snapshot."""

    dependencies = _validated_dependencies(
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
        expected_market_clock_snapshot_hash=expected_market_clock_snapshot_hash,
        expected_research_input_identity=expected_research_input_identity,
    )
    snapshot = _snapshot_payload(*dependencies)
    snapshot["dynamic_market_universe_snapshot_hash"] = canonical_hash(snapshot)
    return snapshot


# Daily and replay cannot fork membership projection or candidate-surface logic.
build_daily_research_only_dynamic_market_universe_snapshot = (
    build_research_only_dynamic_market_universe_snapshot
)
build_replay_research_only_dynamic_market_universe_snapshot = (
    build_research_only_dynamic_market_universe_snapshot
)


__all__ = [
    "DYNAMIC_MARKET_UNIVERSE_CONTRACT",
    "DYNAMIC_MARKET_UNIVERSE_RECORD_TYPE",
    "FROZEN_RESEARCH_INPUT_IDENTITY_FIELDS",
    "SCHEMA_VERSION",
    "V2DynamicMarketUniverseError",
    "validate_dynamic_market_universe_snapshot",
    "build_research_only_dynamic_market_universe_snapshot",
    "build_daily_research_only_dynamic_market_universe_snapshot",
    "build_replay_research_only_dynamic_market_universe_snapshot",
]
