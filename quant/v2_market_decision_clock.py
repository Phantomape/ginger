"""Research-only market-clock binding for the SEC 8-K universe observation.

This boundary attaches one explicit, evidence-backed :class:`SessionClock` to
one validated universe observation.  It deliberately stops before Engine-0:
no candidate, signal, decision, outcome, or order is produced here.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .v2_contracts import (
    CalendarSession,
    EvidenceRecord,
    SessionClock,
    SourceContract,
    V2ContractValidationError,
    canonical_hash,
    validate_session_clock_against_calendar,
)
from .v2_sec_8k_runtime_adapter import (
    ADAPTER_CONTRACT,
    LEDGER_BACKEND_LEGACY_JSONL_V1,
    LEDGER_BACKEND_SEGMENTED_HOT_V1,
    V2SEC8KRuntimeAdapterError,
)
from .v2_universe_observation import (
    OBSERVATION_CONTRACT,
    OBSERVATION_RECORD_TYPE,
    SCHEMA_VERSION as OBSERVATION_SCHEMA_VERSION,
    V2UniverseObservationError,
    observe_sec_8k_universe,
)


SCHEMA_VERSION = 1
MARKET_DECISION_CLOCK_RECORD_TYPE = "v2_market_decision_clock_snapshot"
MARKET_DECISION_CLOCK_CONTRACT = "v2_research_only_market_decision_clock_v1"

_RESEARCH_ONLY_OBSERVATION_BOUNDARY = {
    "external_universe_coverage_status": "unverified",
    "pit_tier": "research_pit",
    "result_ceiling": "observed_only",
    "paper_live_eligible": False,
    "parity_status": "contract_only_unwired",
    "authority": "research_only",
    "trade_enabled": False,
}
_OBSERVATION_FIELDS = {
    "schema_version",
    "record_type",
    "observation_contract",
    "consumer_stage",
    "source_frame",
    "ledger_backend",
    "input_identity",
    "input_identity_sha256",
    "membership_count",
    "memberships",
    "membership_snapshot_sha256",
    "observation_parity_status",
    "observation_scope",
    "engine0_policy_invoked",
    "engine0_baseline_established",
    "market_decision_clock_status",
    "boundary",
    "outcome_blind",
    "results_accessed",
    "authority",
    "trade_enabled",
    "observation_snapshot_hash",
}
_OBSERVATION_INPUT_IDENTITY_FIELDS = {
    "runtime_adapter_contract",
    "runtime_adapter_snapshot_hash",
    "runtime_input_identity_sha256",
    "manifest_id",
    "manifest_hash",
    "universe_id",
    "universe_definition_id",
    "universe_definition_version",
    "universe_definition_sha256",
    "as_of",
    "membership_snapshot_sha256",
    "shared_reader_snapshot_hash",
    "ledger_backend",
    "segmented_hot_state_identity_sha256",
}
_MEMBERSHIP_FIELDS = {
    "mapping_id",
    "security_id",
    "listing_id",
    "symbol",
    "mic",
    "mapping_sha256",
    "state",
    "latest_event_id",
    "latest_event_semantic_hash",
    "latest_event_hash",
    "effective_at",
}
_MEMBERSHIP_HASH_FIELDS = {
    "mapping_sha256",
    "latest_event_semantic_hash",
    "latest_event_hash",
}
_UNIVERSE_STATES = {
    "discovered",
    "research_eligible",
    "candidate_eligible",
    "quarantine",
    "retired",
}
_MARKET_CLOCK_FIELDS = {
    "schema_version",
    "record_type",
    "market_decision_clock_contract",
    "source_frame",
    "consumer_stage",
    "input_identity",
    "input_identity_sha256",
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
_MARKET_CLOCK_INPUT_IDENTITY_FIELDS = {
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
_MARKET_CLOCK_IDENTITY_HASH_FIELDS = {
    "observation_snapshot_hash",
    "observation_input_identity_sha256",
    "runtime_adapter_snapshot_hash",
    "runtime_input_identity_sha256",
    "manifest_hash",
    "universe_definition_sha256",
    "membership_snapshot_sha256",
    "shared_reader_snapshot_hash",
    "session_clock_semantic_hash",
    "session_clock_record_hash",
    "calendar_snapshot_sha256",
    "calendar_evidence_record_hash",
}
_MARKET_CLOCK_IDENTITY_INSTANT_FIELDS = {
    "observation_as_of",
    "session_open_at",
    "session_close_at",
    "assignment_cutoff",
    "clock_frozen_at",
    "clock_recorded_at",
}


class V2MarketDecisionClockError(RuntimeError):
    """Market-clock binding failed with a stable machine code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


def _fail(code: str, message: str) -> None:
    raise V2MarketDecisionClockError(code, message)


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("market_clock_observation_shape_invalid", f"{field} must be an object")
    return value


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail(
            "market_clock_observation_shape_invalid",
            f"{field} must be non-empty text",
        )
    return value


def _sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail(
            "market_clock_observation_shape_invalid",
            f"{field} must be a lowercase SHA-256",
        )
    return value


def _instant(value: Any, *, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str):
        _fail("market_clock_instant_invalid", f"{field} must include a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("market_clock_instant_invalid", f"{field} must include a timezone")
    utc = parsed.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z"), utc


def _validate_observation(
    value: Any,
    *,
    backend: str,
    manifest_id: str,
    as_of: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any], datetime]:
    observation = _mapping(value, field="observation")
    if set(observation) != _OBSERVATION_FIELDS:
        _fail(
            "market_clock_observation_shape_invalid",
            "observation has an unexpected field surface",
        )
    payload = deepcopy(dict(observation))
    supplied_snapshot_hash = payload.pop("observation_snapshot_hash", None)
    if supplied_snapshot_hash != canonical_hash(payload):
        _fail(
            "market_clock_observation_hash_mismatch",
            "observation snapshot hash is invalid",
        )
    if (
        observation.get("schema_version") != OBSERVATION_SCHEMA_VERSION
        or observation.get("record_type") != OBSERVATION_RECORD_TYPE
        or observation.get("observation_contract") != OBSERVATION_CONTRACT
        or observation.get("consumer_stage")
        != "pre_engine0_universe_observation"
        or observation.get("source_frame") != "sec_edgar_8k"
        or observation.get("observation_parity_status")
        != "daily_replay_alias_verified_research_only"
        or observation.get("observation_scope")
        != "source_bound_universe_membership_only"
        or observation.get("market_decision_clock_status") != "unwired"
    ):
        _fail(
            "market_clock_observation_contract_mismatch",
            "unexpected pre-Engine-0 observation contract",
        )
    boundary = _mapping(observation.get("boundary"), field="observation.boundary")
    if dict(boundary) != _RESEARCH_ONLY_OBSERVATION_BOUNDARY or (
        observation.get("engine0_policy_invoked") is not False
        or observation.get("engine0_baseline_established") is not False
        or observation.get("outcome_blind") is not True
        or observation.get("results_accessed") is not False
        or observation.get("authority") != "research_only"
        or observation.get("trade_enabled") is not False
    ):
        _fail(
            "market_clock_observation_boundary_mismatch",
            "observation is not research-only and default-off",
        )

    identity = _mapping(
        observation.get("input_identity"), field="observation.input_identity"
    )
    if set(identity) != _OBSERVATION_INPUT_IDENTITY_FIELDS:
        _fail(
            "market_clock_observation_shape_invalid",
            "observation input identity has an unexpected field surface",
        )
    if observation.get("input_identity_sha256") != canonical_hash(identity):
        _fail(
            "market_clock_observation_identity_hash_mismatch",
            "observation input identity hash is invalid",
        )
    for field in (
        "runtime_adapter_snapshot_hash",
        "runtime_input_identity_sha256",
        "manifest_hash",
        "universe_definition_sha256",
        "membership_snapshot_sha256",
        "shared_reader_snapshot_hash",
    ):
        _sha256(identity.get(field), field=f"observation.input_identity.{field}")
    for field in (
        "runtime_adapter_contract",
        "manifest_id",
        "universe_id",
        "universe_definition_id",
        "universe_definition_version",
        "ledger_backend",
    ):
        _text(identity.get(field), field=f"observation.input_identity.{field}")
    hot_state_hash = identity.get("segmented_hot_state_identity_sha256")
    if hot_state_hash is not None:
        _sha256(
            hot_state_hash,
            field="observation.input_identity.segmented_hot_state_identity_sha256",
        )
    if (
        identity.get("runtime_adapter_contract") != ADAPTER_CONTRACT
        or identity.get("manifest_id") != manifest_id
        or identity.get("ledger_backend") != backend
        or observation.get("ledger_backend") != backend
        or observation.get("membership_snapshot_sha256")
        != identity.get("membership_snapshot_sha256")
    ):
        _fail(
            "market_clock_observation_identity_mismatch",
            "observation contradicts the explicit manifest, backend, or membership identity",
        )
    if (
        backend == LEDGER_BACKEND_LEGACY_JSONL_V1
        and hot_state_hash is not None
    ) or (
        backend == LEDGER_BACKEND_SEGMENTED_HOT_V1
        and hot_state_hash is None
    ):
        _fail(
            "market_clock_observation_identity_mismatch",
            "observation backend contradicts its segmented hot-state identity",
        )
    _, observed_as_of_dt = _instant(
        identity.get("as_of"), field="observation.input_identity.as_of"
    )
    _, requested_as_of_dt = _instant(as_of, field="as_of")
    if observed_as_of_dt != requested_as_of_dt:
        _fail(
            "market_clock_observation_identity_mismatch",
            "observation as_of contradicts the explicit adapter input",
        )

    rows = observation.get("memberships")
    count = observation.get("membership_count")
    if (
        not isinstance(rows, list)
        or not isinstance(count, int)
        or isinstance(count, bool)
        or count != len(rows)
    ):
        _fail(
            "market_clock_observation_identity_mismatch",
            "observation membership count is invalid",
        )
    normalized_rows: list[dict[str, str]] = []
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row, field=f"observation.memberships[{index}]")
        if set(row) != _MEMBERSHIP_FIELDS:
            _fail(
                "market_clock_observation_shape_invalid",
                f"observation.memberships[{index}] has an unexpected field surface",
            )
        normalized: dict[str, str] = {}
        for field in _MEMBERSHIP_FIELDS:
            item = _text(row.get(field), field=f"observation.memberships[{index}].{field}")
            if field in _MEMBERSHIP_HASH_FIELDS:
                _sha256(item, field=f"observation.memberships[{index}].{field}")
            if field == "state" and item not in _UNIVERSE_STATES:
                _fail(
                    "market_clock_observation_shape_invalid",
                    f"observation.memberships[{index}].state is unsupported",
                )
            if field == "effective_at":
                normalized_item, effective_at_dt = _instant(
                    item, field=f"observation.memberships[{index}].effective_at"
                )
                if item != normalized_item:
                    _fail(
                        "market_clock_observation_shape_invalid",
                        f"observation.memberships[{index}].effective_at must be UTC-normalized",
                    )
                if effective_at_dt > observed_as_of_dt:
                    _fail(
                        "market_clock_observation_effective_after_as_of",
                        f"observation.memberships[{index}].effective_at must not exceed observation as_of",
                    )
            normalized[field] = item
        normalized_rows.append(normalized)
    if normalized_rows != sorted(
        normalized_rows, key=lambda row: (row["security_id"], row["listing_id"])
    ):
        _fail(
            "market_clock_observation_identity_mismatch",
            "observation memberships are not identity-sorted",
        )
    if (
        len({row["security_id"] for row in normalized_rows}) != len(normalized_rows)
        or len({row["listing_id"] for row in normalized_rows})
        != len(normalized_rows)
    ):
        _fail(
            "market_clock_observation_identity_mismatch",
            "observation memberships repeat a security or listing identity",
        )
    semantic_rows = [
        {key: item for key, item in row.items() if key != "latest_event_hash"}
        for row in normalized_rows
    ]
    if canonical_hash(semantic_rows) != identity.get("membership_snapshot_sha256"):
        _fail(
            "market_clock_observation_identity_mismatch",
            "observation membership semantic identity is invalid",
        )
    return observation, identity, observed_as_of_dt


def validate_market_decision_clock_snapshot(
    value: Mapping[str, Any],
    session_clock: Mapping[str, Any] | SessionClock,
    calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    calendar_source_contract: Mapping[str, Any] | SourceContract,
    *,
    expected_snapshot_hash: str,
) -> dict[str, Any]:
    """Validate a market-clock envelope against a separately frozen hash."""

    if not isinstance(value, Mapping) or set(value) != _MARKET_CLOCK_FIELDS:
        _fail(
            "market_clock_snapshot_shape_invalid",
            "market-clock snapshot has an unexpected field surface",
        )
    snapshot = deepcopy(dict(value))
    payload = deepcopy(snapshot)
    supplied_snapshot_hash = payload.pop(
        "market_decision_clock_snapshot_hash", None
    )
    if (
        not isinstance(expected_snapshot_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_snapshot_hash) is None
        or supplied_snapshot_hash != expected_snapshot_hash
    ):
        _fail(
            "market_clock_snapshot_expected_hash_mismatch",
            "market-clock snapshot does not match the separately frozen identity",
        )
    if supplied_snapshot_hash != canonical_hash(payload):
        _fail(
            "market_clock_snapshot_hash_mismatch",
            "market-clock snapshot hash is invalid",
        )
    if (
        type(snapshot.get("schema_version")) is not int
        or snapshot.get("schema_version") != SCHEMA_VERSION
        or snapshot.get("record_type") != MARKET_DECISION_CLOCK_RECORD_TYPE
        or snapshot.get("market_decision_clock_contract")
        != MARKET_DECISION_CLOCK_CONTRACT
        or snapshot.get("source_frame") != "sec_edgar_8k"
        or snapshot.get("consumer_stage")
        != "pre_engine0_market_decision_clock"
        or snapshot.get("market_decision_clock_status")
        != "bound_research_only"
        or snapshot.get("observation_scope")
        != "source_bound_universe_membership_only"
    ):
        _fail(
            "market_clock_snapshot_contract_mismatch",
            "unexpected market-clock snapshot contract",
        )
    if (
        snapshot.get("external_universe_coverage_status") != "unverified"
        or snapshot.get("pit_tier") != "research_pit"
        or snapshot.get("authority") != "research_only"
        or snapshot.get("process_wall_clock_fallback_used") is not False
        or snapshot.get("engine0_policy_invoked") is not False
        or snapshot.get("engine0_baseline_established") is not False
        or snapshot.get("result_ceiling") != "observed_only"
        or snapshot.get("paper_live_eligible") is not False
        or snapshot.get("parity_status") != "contract_only_unwired"
        or snapshot.get("outcome_blind") is not True
        or snapshot.get("results_accessed") is not False
        or snapshot.get("trade_enabled") is not False
    ):
        _fail(
            "market_clock_snapshot_boundary_mismatch",
            "market-clock snapshot is not research-only and default-off",
        )

    identity = snapshot.get("input_identity")
    if (
        not isinstance(identity, Mapping)
        or set(identity) != _MARKET_CLOCK_INPUT_IDENTITY_FIELDS
        or snapshot.get("input_identity_sha256") != canonical_hash(identity)
    ):
        _fail(
            "market_clock_snapshot_identity_mismatch",
            "market-clock input identity is invalid",
        )
    for field in _MARKET_CLOCK_IDENTITY_HASH_FIELDS:
        item = identity.get(field)
        if not isinstance(item, str) or re.fullmatch(r"[0-9a-f]{64}", item) is None:
            _fail(
                "market_clock_snapshot_identity_mismatch",
                f"market-clock identity {field} is not a lowercase SHA-256",
            )
    hot_state_hash = identity.get("segmented_hot_state_identity_sha256")
    if hot_state_hash is not None and (
        not isinstance(hot_state_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", hot_state_hash) is None
    ):
        _fail(
            "market_clock_snapshot_identity_mismatch",
            "segmented hot-state identity is invalid",
        )
    membership_count = identity.get("membership_count")
    if (
        not isinstance(membership_count, int)
        or isinstance(membership_count, bool)
        or membership_count < 0
    ):
        _fail(
            "market_clock_snapshot_identity_mismatch",
            "membership_count must be a non-negative integer",
        )
    text_fields = _MARKET_CLOCK_INPUT_IDENTITY_FIELDS - (
        _MARKET_CLOCK_IDENTITY_HASH_FIELDS
        | _MARKET_CLOCK_IDENTITY_INSTANT_FIELDS
        | {"membership_count", "segmented_hot_state_identity_sha256"}
    )
    for field in text_fields:
        item = identity.get(field)
        if not isinstance(item, str) or not item.strip() or item != item.strip():
            _fail(
                "market_clock_snapshot_identity_mismatch",
                f"market-clock identity {field} must be non-empty text",
            )

    instants: dict[str, datetime] = {}
    for field in _MARKET_CLOCK_IDENTITY_INSTANT_FIELDS:
        normalized, parsed = _instant(identity.get(field), field=f"input_identity.{field}")
        if identity.get(field) != normalized:
            _fail(
                "market_clock_snapshot_identity_mismatch",
                f"market-clock identity {field} must be UTC-normalized",
            )
        instants[field] = parsed
    if (
        instants["observation_as_of"] != instants["assignment_cutoff"]
        or not (
            instants["assignment_cutoff"]
            <= instants["clock_frozen_at"]
            <= instants["clock_recorded_at"]
            < instants["session_open_at"]
            < instants["session_close_at"]
        )
    ):
        _fail(
            "market_clock_snapshot_chronology_invalid",
            "market-clock identity chronology is invalid",
        )
    backend = identity.get("ledger_backend")
    if (
        backend not in {
            LEDGER_BACKEND_LEGACY_JSONL_V1,
            LEDGER_BACKEND_SEGMENTED_HOT_V1,
        }
        or (
            backend == LEDGER_BACKEND_LEGACY_JSONL_V1
            and hot_state_hash is not None
        )
        or (
            backend == LEDGER_BACKEND_SEGMENTED_HOT_V1
            and hot_state_hash is None
        )
    ):
        _fail(
            "market_clock_snapshot_identity_mismatch",
            "ledger backend contradicts its hot-state identity",
        )

    try:
        clock = validate_session_clock_against_calendar(
            session_clock,
            calendar_sessions,
            calendar_evidence,
            calendar_source_contract,
        )
    except V2ContractValidationError as exc:
        raise V2MarketDecisionClockError(
            "market_clock_session_clock_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc
    expected_clock_identity = {
        "session_clock_id": clock.session_clock_id,
        "session_clock_semantic_hash": clock.semantic_hash,
        "session_clock_record_hash": clock.record_hash,
        "run_id": clock.run_id,
        "run_date": clock.run_date,
        "calendar_id": clock.calendar_id,
        "calendar_version": clock.calendar_version,
        "calendar_timezone": clock.calendar_timezone,
        "calendar_snapshot_sha256": clock.calendar_snapshot_sha256,
        "calendar_evidence_id": clock.calendar_evidence_id,
        "calendar_evidence_record_hash": clock.calendar_evidence_record_hash,
        "calendar_session_id": clock.calendar_session_id,
        "session_open_at": clock.session_open_at,
        "session_close_at": clock.session_close_at,
        "assignment_cutoff": clock.assignment_cutoff,
        "clock_frozen_at": clock.frozen_at,
        "clock_recorded_at": clock.recorded_at,
    }
    if any(
        identity.get(field) != expected
        for field, expected in expected_clock_identity.items()
    ):
        _fail(
            "market_clock_snapshot_clock_identity_mismatch",
            "market-clock envelope does not bind the supplied session clock",
        )
    if (
        clock.pit_tier != "research_pit"
        or clock.authority != "research_only"
        or clock.trade_enabled is not False
        or clock.process_wall_clock_fallback_used is not False
    ):
        _fail(
            "market_clock_snapshot_boundary_mismatch",
            "supplied session clock exceeds the research-only boundary",
        )
    return snapshot


def observe_sec_8k_market_decision_clock(
    source_dir: str | Path,
    envelope_path: str | Path,
    *,
    backend: str,
    storage_location: str | Path,
    manifest_id: str,
    as_of: str,
    session_clock: Mapping[str, Any] | SessionClock,
    calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    calendar_source_contract: Mapping[str, Any] | SourceContract,
) -> dict[str, Any]:
    """Bind one explicit research-only session clock to one SEC observation."""

    try:
        clock = validate_session_clock_against_calendar(
            session_clock,
            calendar_sessions,
            calendar_evidence,
            calendar_source_contract,
        )
    except V2ContractValidationError as exc:
        raise V2MarketDecisionClockError(
            "market_clock_session_clock_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc
    if (
        clock.pit_tier != "research_pit"
        or clock.authority != "research_only"
        or clock.trade_enabled is not False
        or clock.process_wall_clock_fallback_used is not False
    ):
        _fail(
            "market_clock_clock_boundary_mismatch",
            "session clock must match the research-only/default-off observation boundary",
        )
    _, session_open_dt = _instant(clock.session_open_at, field="clock.session_open_at")
    _, frozen_dt = _instant(clock.frozen_at, field="clock.frozen_at")
    _, recorded_dt = _instant(clock.recorded_at, field="clock.recorded_at")
    if frozen_dt >= session_open_dt:
        _fail(
            "market_clock_frozen_at_not_preopen",
            "session clock must be frozen strictly before session_open_at",
        )
    if recorded_dt >= session_open_dt:
        _fail(
            "market_clock_recorded_at_not_preopen",
            "session clock must be recorded strictly before session_open_at",
        )

    try:
        observed_value = observe_sec_8k_universe(
            source_dir,
            envelope_path,
            backend=backend,
            storage_location=storage_location,
            manifest_id=manifest_id,
            as_of=as_of,
        )
    except (V2UniverseObservationError, V2SEC8KRuntimeAdapterError) as exc:
        raise V2MarketDecisionClockError(
            "market_clock_observation_dependency_error",
            f"{exc.code}: {exc.detail}",
        ) from exc
    observation, observation_identity, observed_as_of_dt = _validate_observation(
        observed_value,
        backend=backend,
        manifest_id=manifest_id,
        as_of=as_of,
    )
    _, assignment_cutoff_dt = _instant(
        clock.assignment_cutoff, field="clock.assignment_cutoff"
    )
    if observed_as_of_dt != assignment_cutoff_dt:
        _fail(
            "market_clock_as_of_cutoff_mismatch",
            "observation as_of must be the same UTC instant as assignment_cutoff",
        )

    input_identity = {
        "observation_snapshot_hash": observation["observation_snapshot_hash"],
        "observation_input_identity_sha256": observation["input_identity_sha256"],
        "runtime_adapter_snapshot_hash": observation_identity[
            "runtime_adapter_snapshot_hash"
        ],
        "runtime_input_identity_sha256": observation_identity[
            "runtime_input_identity_sha256"
        ],
        "ledger_backend": observation_identity["ledger_backend"],
        "segmented_hot_state_identity_sha256": observation_identity[
            "segmented_hot_state_identity_sha256"
        ],
        "manifest_id": observation_identity["manifest_id"],
        "manifest_hash": observation_identity["manifest_hash"],
        "universe_id": observation_identity["universe_id"],
        "universe_definition_id": observation_identity["universe_definition_id"],
        "universe_definition_version": observation_identity[
            "universe_definition_version"
        ],
        "universe_definition_sha256": observation_identity[
            "universe_definition_sha256"
        ],
        "membership_count": observation["membership_count"],
        "membership_snapshot_sha256": observation_identity[
            "membership_snapshot_sha256"
        ],
        "shared_reader_snapshot_hash": observation_identity[
            "shared_reader_snapshot_hash"
        ],
        "observation_as_of": observation_identity["as_of"],
        "session_clock_id": clock.session_clock_id,
        "session_clock_semantic_hash": clock.semantic_hash,
        "session_clock_record_hash": clock.record_hash,
        "run_id": clock.run_id,
        "run_date": clock.run_date,
        "calendar_id": clock.calendar_id,
        "calendar_version": clock.calendar_version,
        "calendar_timezone": clock.calendar_timezone,
        "calendar_snapshot_sha256": clock.calendar_snapshot_sha256,
        "calendar_evidence_id": clock.calendar_evidence_id,
        "calendar_evidence_record_hash": clock.calendar_evidence_record_hash,
        "calendar_session_id": clock.calendar_session_id,
        "session_open_at": clock.session_open_at,
        "session_close_at": clock.session_close_at,
        "assignment_cutoff": clock.assignment_cutoff,
        "clock_frozen_at": clock.frozen_at,
        "clock_recorded_at": clock.recorded_at,
    }
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "record_type": MARKET_DECISION_CLOCK_RECORD_TYPE,
        "market_decision_clock_contract": MARKET_DECISION_CLOCK_CONTRACT,
        "source_frame": "sec_edgar_8k",
        "consumer_stage": "pre_engine0_market_decision_clock",
        "input_identity": input_identity,
        "input_identity_sha256": canonical_hash(input_identity),
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
    return validate_market_decision_clock_snapshot(
        snapshot,
        session_clock,
        calendar_sessions,
        calendar_evidence,
        calendar_source_contract,
        expected_snapshot_hash=snapshot["market_decision_clock_snapshot_hash"],
    )


# Daily and replay cannot fork clock assignment or observation logic.
observe_sec_8k_daily_market_decision_clock = observe_sec_8k_market_decision_clock
observe_sec_8k_replay_market_decision_clock = observe_sec_8k_market_decision_clock


__all__ = [
    "MARKET_DECISION_CLOCK_CONTRACT",
    "MARKET_DECISION_CLOCK_RECORD_TYPE",
    "SCHEMA_VERSION",
    "V2MarketDecisionClockError",
    "validate_market_decision_clock_snapshot",
    "observe_sec_8k_market_decision_clock",
    "observe_sec_8k_daily_market_decision_clock",
    "observe_sec_8k_replay_market_decision_clock",
]
