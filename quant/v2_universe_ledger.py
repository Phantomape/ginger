"""Atomic, research-only dynamic-universe ledger for Ginger V2.

The ledger is one mixed JSONL stream.  Every transaction writes zero or more
``UniverseEvent`` rows followed by exactly one membership manifest commit
marker.  Readers reject missing manifests, orphan event tails, damaged history,
and implicit wall-clock selection.  Daily and replay consumers are aliases of
the same explicit-manifest resolver.

This first M2 storage slice proves only that the committed ledger population is
complete and replayable.  It deliberately marks external universe coverage as
unverified, so it cannot be used as a complete CandidatePool or Gate input.
The writer nevertheless requires the M1 source, evidence, and calendar inputs
and validates every proposed event and both manifest clocks before committing.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

try:  # Support package imports and direct ``quant/`` execution.
    from .data_paths import atomic_write_text
    from .v2_contracts import (
        CalendarSession,
        EvidenceRecord,
        PIT_TIERS,
        SessionClock,
        SourceContract,
        UniverseEvent,
        V2ContractValidationError,
        canonical_hash,
        canonical_json,
        validate_evidence_against_source,
        validate_evidence_record,
        validate_session_clock_against_calendar,
        validate_session_clock,
        validate_source_contract,
        validate_universe_event,
        validate_universe_event_against_evidence,
        validate_universe_event_against_session_clocks,
    )
    from .v2_universe_coverage import (
        ExternalUniverseCoverageSnapshot,
        V2UniverseCoverageError,
        validate_external_universe_coverage_against_inputs,
        validate_external_universe_coverage_snapshot,
    )
except ImportError:  # pragma: no cover - direct script fallback.
    from data_paths import atomic_write_text  # type: ignore
    from v2_contracts import (  # type: ignore
        CalendarSession,
        EvidenceRecord,
        PIT_TIERS,
        SessionClock,
        SourceContract,
        UniverseEvent,
        V2ContractValidationError,
        canonical_hash,
        canonical_json,
        validate_evidence_against_source,
        validate_evidence_record,
        validate_session_clock_against_calendar,
        validate_session_clock,
        validate_source_contract,
        validate_universe_event,
        validate_universe_event_against_evidence,
        validate_universe_event_against_session_clocks,
    )
    from v2_universe_coverage import (  # type: ignore
        ExternalUniverseCoverageSnapshot,
        V2UniverseCoverageError,
        validate_external_universe_coverage_against_inputs,
        validate_external_universe_coverage_snapshot,
    )


SCHEMA_VERSION = 1
MANIFEST_RECORD_TYPE = "v2_universe_membership_manifest"
SNAPSHOT_RECORD_TYPE = "v2_universe_membership_snapshot"
SHARED_READER_CONTRACT = "v2_shared_daily_replay_universe_reader_v1"
DEFAULT_LEDGER_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "v2"
    / "universe"
    / "universe_ledger.jsonl"
)

_LOCK_TIMEOUT_SECONDS = 10.0
_LOCK_POLL_SECONDS = 0.02
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_PIT_RANK = {"not_pit": 0, "research_pit": 1, "canonical_pit": 2}

_MEMBERSHIP_FIELDS = frozenset(
    {
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
)

_EVIDENCE_REGISTRY_FIELDS = frozenset(
    {"source_contract_id", "semantic_hash", "record_hash"}
)

_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "record_type",
        "manifest_id",
        "universe_id",
        "event_batch_id",
        "universe_definition_id",
        "universe_definition_version",
        "universe_definition_sha256",
        "source_contract_registry",
        "evidence_record_registry",
        "run_id",
        "session_clock_id",
        "session_clock_hash",
        "session_clock_record_hash",
        "session_clock_calendar_evidence_id",
        "session_clock_calendar_evidence_record_hash",
        "session_clock_pit_tier",
        "effective_session_clock_id",
        "effective_session_clock_hash",
        "effective_session_clock_record_hash",
        "effective_session_clock_calendar_evidence_id",
        "effective_session_clock_calendar_evidence_record_hash",
        "effective_session_clock_pit_tier",
        "run_date",
        "calendar_session_id",
        "effective_session_id",
        "ledger_population_start",
        "membership_as_of",
        "data_cutoff",
        "frozen_at",
        "recorded_at",
        "previous_manifest_id",
        "previous_manifest_hash",
        "batch_event_ids",
        "universe_event_ids",
        "universe_event_semantic_snapshot_sha256",
        "universe_event_record_snapshot_sha256",
        "memberships",
        "membership_snapshot_sha256",
        "ledger_population_complete",
        "external_universe_coverage_status",
        "pit_tier",
        "result_ceiling",
        "paper_live_eligible",
        "parity_status",
        "known_future_leakage",
        "outcome_blind",
        "results_accessed",
        "authority",
        "trade_enabled",
        "semantic_hash",
        "manifest_hash",
    }
)


class V2UniverseLedgerError(RuntimeError):
    """Base error with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


class V2UniverseLedgerValidationError(V2UniverseLedgerError):
    """A row, population, manifest, or read request failed closed."""


class V2UniverseLedgerConflictError(V2UniverseLedgerError):
    """An immutable identity already exists with different semantics."""


class V2UniverseLedgerLockError(V2UniverseLedgerError):
    """The writer could not acquire its advisory lock."""


def _fail(code: str, message: str) -> None:
    raise V2UniverseLedgerValidationError(code, message)


def _contract_call(function, *args, **kwargs):
    """Expose one stable ledger validation error surface at public boundaries."""

    try:
        return function(*args, **kwargs)
    except V2ContractValidationError as exc:
        raise V2UniverseLedgerValidationError(
            exc.code, f"{exc.path}: {exc.detail}"
        ) from exc


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("nonempty_text_required", f"{field} must be trimmed non-empty text")
    return value


def _optional_text(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field=field)


def _sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        _fail("sha256_required", f"{field} must be lowercase SHA-256 hex")
    return value


def _instant(value: Any, *, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.strip():
        _fail("timezone_aware_instant_required", f"{field} must be an ISO instant")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise V2UniverseLedgerValidationError(
            "timezone_aware_instant_required", f"{field} is not a valid ISO instant"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("timezone_aware_instant_required", f"{field} must include an offset")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _calendar_date(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        _fail("calendar_date_required", f"{field} must be YYYY-MM-DD")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise V2UniverseLedgerValidationError(
            "calendar_date_required", f"{field} must be YYYY-MM-DD"
        ) from exc
    if parsed != value:
        _fail("calendar_date_required", f"{field} must be canonical YYYY-MM-DD")
    return value


def _string_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        _fail("list_required", f"{field} must be a JSON array")
    rows = [_text(item, field=f"{field}[]") for item in value]
    if rows != sorted(rows) or len(rows) != len(set(rows)):
        _fail("sorted_unique_list_required", f"{field} must be sorted and unique")
    return rows


def _json_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise V2UniverseLedgerValidationError(
            "json_object_required", "record must contain only finite JSON values"
        ) from exc


def _event_semantic_snapshot(events: Sequence[UniverseEvent]) -> str:
    return canonical_hash(
        [
            {"event_id": event.event_id, "semantic_hash": event.semantic_hash}
            for event in sorted(events, key=lambda item: item.event_id)
        ]
    )


def _event_record_snapshot(events: Sequence[UniverseEvent]) -> str:
    return canonical_hash(
        [
            {"event_id": event.event_id, "event_hash": event.event_hash}
            for event in sorted(events, key=lambda item: item.event_id)
        ]
    )


def _event_input_snapshot_from_registry(
    event: UniverseEvent,
    evidence_registry: Mapping[str, Mapping[str, str]],
) -> str:
    bindings = []
    for evidence_id in event.evidence_record_ids:
        binding = evidence_registry.get(evidence_id)
        if binding is None:
            _fail(
                "unresolved_evidence_id",
                f"event {event.event_id!r} evidence is absent from the manifest registry",
            )
        bindings.append(
            {
                "evidence_id": evidence_id,
                "semantic_hash": binding["semantic_hash"],
                "record_hash": binding["record_hash"],
            }
        )
    return canonical_hash(
        {
            "evidence_records": sorted(
                bindings, key=lambda item: item["evidence_id"]
            ),
            "rule_sha256": event.rule_sha256,
            "security_mapping_sha256": event.security_mapping.mapping_sha256,
            "session_clock": {
                "id": event.session_clock_id,
                "semantic_hash": event.session_clock_hash,
                "record_hash": event.session_clock_record_hash,
            },
            "effective_session_clock": {
                "id": event.effective_session_clock_id,
                "semantic_hash": event.effective_session_clock_hash,
                "record_hash": event.effective_session_clock_record_hash,
            },
        }
    )


def _membership_rows(latest: Mapping[str, UniverseEvent]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    listing_ids: set[str] = set()
    for security_id in sorted(latest):
        event = latest[security_id]
        mapping = event.security_mapping
        if mapping.listing_id in listing_ids:
            _fail(
                "duplicate_latest_listing",
                f"latest membership repeats listing_id {mapping.listing_id!r}",
            )
        listing_ids.add(mapping.listing_id)
        rows.append(
            {
                "mapping_id": mapping.mapping_id,
                "security_id": mapping.security_id,
                "listing_id": mapping.listing_id,
                "symbol": mapping.symbol,
                "mic": mapping.mic,
                "mapping_sha256": mapping.mapping_sha256,
                "state": event.to_state,
                "latest_event_id": event.event_id,
                "latest_event_semantic_hash": event.semantic_hash,
                "latest_event_hash": event.event_hash,
                "effective_at": event.effective_at,
            }
        )
    return rows


def _validate_membership_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("list_required", "memberships must be a JSON array")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or set(item) != _MEMBERSHIP_FIELDS:
            _fail(
                "invalid_membership_shape",
                f"memberships[{index}] must have the exact membership schema",
            )
        row = _json_copy(item)
        for field in (
            "mapping_id",
            "security_id",
            "listing_id",
            "symbol",
            "mic",
            "state",
            "latest_event_id",
        ):
            _text(row[field], field=f"memberships[{index}].{field}")
        for field in (
            "mapping_sha256",
            "latest_event_semantic_hash",
            "latest_event_hash",
        ):
            _sha256(row[field], field=f"memberships[{index}].{field}")
        row["effective_at"] = _instant(
            row["effective_at"], field=f"memberships[{index}].effective_at"
        )[0]
        rows.append(row)
    expected = sorted(rows, key=lambda row: (row["security_id"], row["listing_id"]))
    if rows != expected:
        _fail("noncanonical_membership_order", "memberships must be identity-sorted")
    if len({row["security_id"] for row in rows}) != len(rows):
        _fail("duplicate_membership_security", "memberships repeat a security_id")
    return rows


def _membership_semantic_rows(
    memberships: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Drop the exact event record hash while preserving membership semantics."""

    return [
        {
            key: deepcopy(value)
            for key, value in row.items()
            if key != "latest_event_hash"
        }
        for row in memberships
    ]


def _validate_source_contract_registry(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        _fail("registry_object_required", "source_contract_registry must be an object")
    result: dict[str, str] = {}
    for source_id, contract_hash in value.items():
        identifier = _text(source_id, field="source_contract_registry key")
        result[identifier] = _sha256(
            contract_hash, field=f"source_contract_registry.{identifier}"
        )
    return dict(sorted(result.items()))


def _validate_evidence_record_registry(
    value: Any, *, source_registry: Mapping[str, str]
) -> dict[str, dict[str, str]]:
    if not isinstance(value, Mapping):
        _fail("registry_object_required", "evidence_record_registry must be an object")
    result: dict[str, dict[str, str]] = {}
    for evidence_id, raw_binding in value.items():
        identifier = _text(evidence_id, field="evidence_record_registry key")
        if (
            not isinstance(raw_binding, Mapping)
            or set(raw_binding) != _EVIDENCE_REGISTRY_FIELDS
        ):
            _fail(
                "invalid_evidence_registry_binding",
                f"evidence_record_registry.{identifier} has an invalid shape",
            )
        binding = _json_copy(raw_binding)
        source_id = _text(
            binding["source_contract_id"],
            field=f"evidence_record_registry.{identifier}.source_contract_id",
        )
        if source_id not in source_registry:
            _fail(
                "unresolved_source_contract_id",
                f"registry evidence {identifier!r} has no source contract binding",
            )
        for field in ("semantic_hash", "record_hash"):
            _sha256(
                binding[field],
                field=f"evidence_record_registry.{identifier}.{field}",
            )
        result[identifier] = binding
    return dict(sorted(result.items()))


def _input_registry_bindings(
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    sources_by_id: dict[str, SourceContract] = {}
    for raw in source_contracts:
        source = _contract_call(validate_source_contract, raw)
        previous = sources_by_id.get(source.source_contract_id)
        if (
            previous is not None
            and previous.source_contract_hash != source.source_contract_hash
        ):
            _fail(
                "source_contract_id_conflict",
                "one source_contract_id cannot resolve to multiple contracts",
            )
        sources_by_id[source.source_contract_id] = source

    evidence_by_id: dict[str, EvidenceRecord] = {}
    for raw in evidence_records:
        evidence = _contract_call(validate_evidence_record, raw)
        source = sources_by_id.get(evidence.source_contract_id)
        if source is None:
            _fail(
                "unresolved_source_contract_id",
                f"no source contract for {evidence.source_contract_id!r}",
            )
        _contract_call(validate_evidence_against_source, evidence, source)
        previous = evidence_by_id.get(evidence.evidence_id)
        if previous is not None and (
            previous.semantic_hash != evidence.semantic_hash
            or previous.record_hash != evidence.record_hash
        ):
            _fail(
                "evidence_id_conflict",
                "one evidence_id cannot resolve to multiple evidence records",
            )
        evidence_by_id[evidence.evidence_id] = evidence

    source_registry = {
        source_id: source.source_contract_hash
        for source_id, source in sorted(sources_by_id.items())
    }
    evidence_registry = {
        evidence_id: {
            "source_contract_id": evidence.source_contract_id,
            "semantic_hash": evidence.semantic_hash,
            "record_hash": evidence.record_hash,
        }
        for evidence_id, evidence in sorted(evidence_by_id.items())
    }
    return source_registry, evidence_registry


def validate_universe_event_population(
    events: Iterable[Mapping[str, Any] | UniverseEvent],
    *,
    universe_id: str,
    data_cutoff: str | None = None,
    frozen_at: str | None = None,
    membership_as_of: str | None = None,
) -> tuple[tuple[UniverseEvent, ...], list[dict[str, Any]]]:
    """Validate one committed population and derive effective membership heads."""

    if isinstance(events, (str, bytes, bytearray, Mapping)):
        _fail("event_sequence_required", "events must be an iterable of objects")
    expected_universe = _text(universe_id, field="universe_id")
    records = tuple(_contract_call(validate_universe_event, event) for event in events)
    ids = [event.event_id for event in records]
    if len(ids) != len(set(ids)):
        _fail("duplicate_universe_event_id", "event_id values must be unique")
    if any(event.universe_id != expected_universe for event in records):
        _fail("mixed_universe_population", "all events must match universe_id")

    cutoff_dt = None
    frozen_dt = None
    membership_dt = None
    if data_cutoff is not None:
        _, cutoff_dt = _instant(data_cutoff, field="data_cutoff")
    if frozen_at is not None:
        _, frozen_dt = _instant(frozen_at, field="frozen_at")
    if membership_as_of is not None:
        _, membership_dt = _instant(membership_as_of, field="membership_as_of")
    elif cutoff_dt is not None:
        membership_dt = cutoff_dt
    if frozen_dt is not None and cutoff_dt is not None and frozen_dt < cutoff_dt:
        _fail("invalid_manifest_chronology", "frozen_at cannot precede data_cutoff")
    if membership_dt is not None and cutoff_dt is not None and membership_dt > cutoff_dt:
        _fail(
            "membership_after_data_cutoff",
            "membership_as_of cannot exceed data_cutoff",
        )

    by_security: dict[str, list[UniverseEvent]] = {}
    rules: dict[tuple[str, str], str] = {}
    mappings: dict[str, str] = {}
    for event in records:
        rule_key = (event.rule_id, event.rule_version)
        if rule_key in rules and rules[rule_key] != event.rule_sha256:
            _fail(
                "universe_rule_identity_conflict",
                "one rule id/version cannot resolve to multiple rule hashes",
            )
        rules[rule_key] = event.rule_sha256
        mapping = event.security_mapping
        if (
            mapping.mapping_id in mappings
            and mappings[mapping.mapping_id] != mapping.mapping_sha256
        ):
            _fail(
                "security_mapping_identity_conflict",
                "one mapping_id cannot resolve to multiple mapping hashes",
            )
        mappings[mapping.mapping_id] = mapping.mapping_sha256
        if cutoff_dt is not None:
            _, known_dt = _instant(event.known_at, field="event.known_at")
            _, decided_dt = _instant(event.decided_at, field="event.decided_at")
            if known_dt > cutoff_dt or decided_dt > cutoff_dt:
                _fail(
                    "universe_event_after_cutoff",
                    f"event {event.event_id!r} is not known and decided by data_cutoff",
                )
        if frozen_dt is not None:
            _, event_recorded_dt = _instant(
                event.recorded_at, field="event.recorded_at"
            )
            if event_recorded_dt > frozen_dt:
                _fail(
                    "universe_event_recorded_after_freeze",
                    f"event {event.event_id!r} was recorded after frozen_at",
                )
        by_security.setdefault(event.security_mapping.security_id, []).append(event)

    latest: dict[str, UniverseEvent] = {}
    for security_id, chain in by_security.items():
        ordered = sorted(
            chain,
            key=lambda item: (
                _instant(item.effective_at, field="event.effective_at")[1],
                item.event_id,
            ),
        )
        first = ordered[0]
        if first.event_type != "discovery":
            _fail(
                "incomplete_universe_event_chain",
                f"{security_id!r} does not start with discovery",
            )
        previous = first
        for current in ordered[1:]:
            previous_effective = _instant(
                previous.effective_at, field="event.effective_at"
            )[1]
            current_effective = _instant(
                current.effective_at, field="event.effective_at"
            )[1]
            current_decided = _instant(
                current.decided_at, field="event.decided_at"
            )[1]
            if current_effective <= previous_effective:
                _fail(
                    "nonmonotonic_universe_event_chain",
                    f"{security_id!r} effective_at values must increase",
                )
            if current_decided < previous_effective:
                _fail(
                    "universe_transition_before_prior_effective",
                    f"{security_id!r} transitions before its prior state is effective",
                )
            if (
                current.previous_event_id != previous.event_id
                or current.previous_event_hash != previous.event_hash
                or current.from_state != previous.to_state
            ):
                _fail(
                    "broken_universe_event_chain",
                    f"{security_id!r} does not bind the immediately prior event",
                )
            previous = current
        effective = [
            event
            for event in ordered
            if membership_dt is None
            or _instant(event.effective_at, field="event.effective_at")[1]
            <= membership_dt
        ]
        if effective:
            latest[security_id] = effective[-1]

    ordered_records = tuple(
        sorted(
            records,
            key=lambda item: (
                _instant(item.effective_at, field="event.effective_at")[1],
                item.event_id,
            ),
        )
    )
    return ordered_records, _membership_rows(latest)


def _manifest_semantic_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        key: deepcopy(value)
        for key, value in row.items()
        if key
        not in {
            "recorded_at",
            "semantic_hash",
            "manifest_hash",
            "universe_event_record_snapshot_sha256",
        }
    }
    payload["memberships"] = _membership_semantic_rows(row["memberships"])
    return payload


def _manifest_record_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in row.items() if key != "manifest_hash"}


def _validate_manifest_shape(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _MANIFEST_FIELDS:
        _fail("invalid_manifest_shape", "manifest must have the exact v1 schema")
    row = _json_copy(value)
    if type(row["schema_version"]) is not int or row["schema_version"] != SCHEMA_VERSION:
        _fail("unsupported_schema_version", "manifest schema_version must be 1")
    if row["record_type"] != MANIFEST_RECORD_TYPE:
        _fail("invalid_record_type", f"record_type must be {MANIFEST_RECORD_TYPE!r}")
    for field in (
        "manifest_id",
        "universe_id",
        "event_batch_id",
        "universe_definition_id",
        "universe_definition_version",
        "run_id",
        "session_clock_id",
        "session_clock_calendar_evidence_id",
        "effective_session_clock_id",
        "effective_session_clock_calendar_evidence_id",
        "calendar_session_id",
        "effective_session_id",
        "authority",
        "external_universe_coverage_status",
        "result_ceiling",
        "parity_status",
    ):
        _text(row[field], field=field)
    for field in (
        "universe_definition_sha256",
        "session_clock_hash",
        "session_clock_record_hash",
        "session_clock_calendar_evidence_record_hash",
        "effective_session_clock_hash",
        "effective_session_clock_record_hash",
        "effective_session_clock_calendar_evidence_record_hash",
        "universe_event_semantic_snapshot_sha256",
        "universe_event_record_snapshot_sha256",
        "membership_snapshot_sha256",
        "semantic_hash",
        "manifest_hash",
    ):
        _sha256(row[field], field=field)
    for field in (
        "session_clock_pit_tier",
        "effective_session_clock_pit_tier",
        "pit_tier",
    ):
        if row[field] not in PIT_TIERS:
            _fail("invalid_pit_tier", f"{field} must be a supported PIT tier")
    row["source_contract_registry"] = _validate_source_contract_registry(
        row["source_contract_registry"]
    )
    row["evidence_record_registry"] = _validate_evidence_record_registry(
        row["evidence_record_registry"],
        source_registry=row["source_contract_registry"],
    )
    for evidence_id_field, evidence_hash_field in (
        (
            "session_clock_calendar_evidence_id",
            "session_clock_calendar_evidence_record_hash",
        ),
        (
            "effective_session_clock_calendar_evidence_id",
            "effective_session_clock_calendar_evidence_record_hash",
        ),
    ):
        evidence_binding = row["evidence_record_registry"].get(row[evidence_id_field])
        if evidence_binding is None:
            _fail(
                "missing_clock_calendar_evidence",
                f"{evidence_id_field} must resolve in evidence_record_registry",
            )
        if evidence_binding["record_hash"] != row[evidence_hash_field]:
            _fail(
                "clock_calendar_evidence_record_hash_mismatch",
                f"{evidence_hash_field} must match the registered evidence record",
            )
    _calendar_date(row["run_date"], field="run_date")
    row["ledger_population_start"], population_start_dt = _instant(
        row["ledger_population_start"], field="ledger_population_start"
    )
    row["membership_as_of"], membership_dt = _instant(
        row["membership_as_of"], field="membership_as_of"
    )
    row["data_cutoff"], cutoff_dt = _instant(
        row["data_cutoff"], field="data_cutoff"
    )
    row["frozen_at"], frozen_dt = _instant(row["frozen_at"], field="frozen_at")
    row["recorded_at"], recorded_dt = _instant(
        row["recorded_at"], field="recorded_at"
    )
    if not population_start_dt <= membership_dt <= cutoff_dt <= frozen_dt <= recorded_dt:
        _fail(
            "invalid_manifest_chronology",
            "must satisfy ledger_population_start <= membership_as_of <= "
            "data_cutoff <= frozen_at <= recorded_at",
        )
    previous_id = _optional_text(row["previous_manifest_id"], field="previous_manifest_id")
    previous_hash = row["previous_manifest_hash"]
    if previous_hash is not None:
        _sha256(previous_hash, field="previous_manifest_hash")
    if (previous_id is None) != (previous_hash is None):
        _fail(
            "incomplete_previous_manifest_binding",
            "previous manifest id and hash must both be null or both be present",
        )
    _string_list(row["batch_event_ids"], field="batch_event_ids")
    _string_list(row["universe_event_ids"], field="universe_event_ids")
    memberships = _validate_membership_rows(row["memberships"])
    if row["membership_snapshot_sha256"] != canonical_hash(
        _membership_semantic_rows(memberships)
    ):
        _fail("membership_snapshot_hash_mismatch", "membership hash is incorrect")
    for field in (
        "ledger_population_complete",
        "paper_live_eligible",
        "known_future_leakage",
        "outcome_blind",
        "results_accessed",
        "trade_enabled",
    ):
        if type(row[field]) is not bool:
            _fail("boolean_required", f"{field} must be boolean")
    if row["ledger_population_complete"] is not True:
        _fail(
            "complete_ledger_population_required",
            "ledger_population_complete must be true",
        )
    if row["external_universe_coverage_status"] != "unverified":
        _fail(
            "external_universe_coverage_unverified",
            "this storage slice must not claim external universe completeness",
        )
    if row["known_future_leakage"] is not False:
        _fail("future_leakage_forbidden", "research ledger cannot contain known leakage")
    if row["outcome_blind"] is not True or row["results_accessed"] is not False:
        _fail("outcome_blind_required", "manifest must remain outcome blind")
    if row["authority"] != "research_only":
        _fail("research_authority_required", "authority must be research_only")
    if row["trade_enabled"] is not False:
        _fail("trade_enabled_forbidden", "trade_enabled must remain false")
    if row["paper_live_eligible"] is not False:
        _fail("paper_live_eligible_forbidden", "paper/live eligibility must remain false")
    if row["result_ceiling"] != "observed_only":
        _fail("observed_only_required", "result_ceiling must remain observed_only")
    if row["parity_status"] != "contract_only_unwired":
        _fail(
            "unwired_parity_required",
            "parity_status must remain contract_only_unwired",
        )
    if row["pit_tier"] != "research_pit":
        _fail(
            "research_pit_ceiling_required",
            "unanchored ledger manifests are capped at research_pit",
        )
    expected_semantic = canonical_hash(_manifest_semantic_payload(row))
    if row["semantic_hash"] != expected_semantic:
        _fail("semantic_hash_mismatch", "manifest semantic_hash is incorrect")
    expected_record = canonical_hash(_manifest_record_payload(row))
    if row["manifest_hash"] != expected_record:
        _fail("manifest_hash_mismatch", "manifest_hash is incorrect")
    return row


def _validate_manifest_event_bindings(
    row: Mapping[str, Any],
    events: Sequence[Mapping[str, Any] | UniverseEvent],
    previous_manifest: Mapping[str, Any] | None,
) -> tuple[tuple[UniverseEvent, ...], list[dict[str, Any]]]:
    records, memberships = validate_universe_event_population(
        events,
        universe_id=row["universe_id"],
        data_cutoff=row["data_cutoff"],
        frozen_at=row["frozen_at"],
        membership_as_of=row["membership_as_of"],
    )
    event_ids = sorted(event.event_id for event in records)
    for event in records:
        if event.input_snapshot_sha256 != _event_input_snapshot_from_registry(
            event, row["evidence_record_registry"]
        ):
            _fail(
                "event_input_registry_mismatch",
                "event input snapshot does not match manifest evidence bindings",
            )
    if row["universe_event_ids"] != event_ids:
        _fail(
            "manifest_event_population_mismatch",
            "universe_event_ids must cover the complete committed population",
        )
    if row["universe_event_semantic_snapshot_sha256"] != _event_semantic_snapshot(records):
        _fail(
            "event_semantic_snapshot_mismatch",
            "semantic event snapshot does not match the population",
        )
    if row["universe_event_record_snapshot_sha256"] != _event_record_snapshot(records):
        _fail(
            "event_record_snapshot_mismatch",
            "physical event snapshot does not match the population",
        )
    if row["memberships"] != memberships:
        _fail(
            "manifest_membership_mismatch",
            "memberships must exactly equal the derived latest chain heads",
        )

    previous_ids: set[str] = set()
    if previous_manifest is None:
        if row["previous_manifest_id"] is not None:
            _fail("unexpected_previous_manifest", "first manifest must not name a predecessor")
    else:
        prior = _validate_manifest_shape(previous_manifest)
        if (
            row["previous_manifest_id"] != prior["manifest_id"]
            or row["previous_manifest_hash"] != prior["manifest_hash"]
        ):
            _fail(
                "broken_manifest_chain",
                "manifest must bind the immediately prior manifest record",
            )
        for field in (
            "universe_id",
            "universe_definition_id",
            "universe_definition_version",
            "universe_definition_sha256",
            "ledger_population_start",
        ):
            if row[field] != prior[field]:
                _fail(
                    "manifest_identity_drift",
                    f"{field} cannot change inside one ledger chain",
                )
        for field in ("source_contract_registry", "evidence_record_registry"):
            current_registry = row[field]
            for stable_id, binding in prior[field].items():
                if current_registry.get(stable_id) != binding:
                    _fail(
                        "input_registry_history_conflict",
                        f"{field} cannot remove or redefine {stable_id!r}",
                    )
        previous_ids = set(prior["universe_event_ids"])
        if not previous_ids.issubset(event_ids):
            _fail("event_history_removed", "a later manifest cannot remove events")
        prior_cutoff = _instant(prior["data_cutoff"], field="previous.data_cutoff")[1]
        cutoff = _instant(row["data_cutoff"], field="data_cutoff")[1]
        prior_recorded = _instant(prior["recorded_at"], field="previous.recorded_at")[1]
        frozen = _instant(row["frozen_at"], field="frozen_at")[1]
        recorded = _instant(row["recorded_at"], field="recorded_at")[1]
        prior_membership = _instant(
            prior["membership_as_of"], field="previous.membership_as_of"
        )[1]
        membership = _instant(row["membership_as_of"], field="membership_as_of")[1]
        if (
            cutoff < prior_cutoff
            or membership < prior_membership
            or frozen < prior_recorded
            or recorded < prior_recorded
        ):
            _fail("nonmonotonic_manifest_chain", "manifest clocks cannot move backward")
        if row["event_batch_id"] == prior["event_batch_id"]:
            _fail(
                "duplicate_event_batch_id",
                "successor manifests must use a fresh event_batch_id",
            )

    expected_batch_ids = sorted(set(event_ids) - previous_ids)
    if row["batch_event_ids"] != expected_batch_ids:
        _fail(
            "manifest_batch_membership_mismatch",
            "batch_event_ids must be the exact newly committed event set",
        )
    by_id = {event.event_id: event for event in records}
    if any(
        by_id[event_id].event_batch_id != row["event_batch_id"]
        for event_id in expected_batch_ids
    ):
        _fail(
            "event_batch_id_mismatch",
            "newly committed events must match the manifest event_batch_id",
        )
    for event_id in expected_batch_ids:
        event = by_id[event_id]
        if (
            event.run_id != row["run_id"]
            or event.session_clock_id != row["session_clock_id"]
            or event.session_clock_hash != row["session_clock_hash"]
            or event.session_clock_record_hash != row["session_clock_record_hash"]
            or event.run_date != row["run_date"]
            or event.calendar_session_id != row["calendar_session_id"]
            or event.effective_session_clock_id
            != row["effective_session_clock_id"]
            or event.effective_session_clock_hash
            != row["effective_session_clock_hash"]
            or event.effective_session_clock_record_hash
            != row["effective_session_clock_record_hash"]
            or event.effective_session_id != row["effective_session_id"]
        ):
            _fail(
                "manifest_event_clock_binding_mismatch",
                "new events must bind the manifest's exact run and effective clocks",
            )
    if previous_manifest is not None:
        prior = _validate_manifest_shape(previous_manifest)
        prior_cutoff = _instant(
            prior["data_cutoff"], field="previous.data_cutoff"
        )[1]
        prior_membership = _instant(
            prior["membership_as_of"], field="previous.membership_as_of"
        )[1]
        for event_id in expected_batch_ids:
            event = by_id[event_id]
            decided = _instant(event.decided_at, field="event.decided_at")[1]
            effective = _instant(event.effective_at, field="event.effective_at")[1]
            if decided <= prior_cutoff or effective <= prior_membership:
                _fail(
                    "retroactive_universe_event",
                    "new events must be decided after the prior data cutoff and "
                    "effective after the prior membership projection",
                )

    weakest = min(
        [row["session_clock_pit_tier"], row["effective_session_clock_pit_tier"]]
        + [event.pit_tier for event in records],
        key=lambda item: _PIT_RANK[item],
    )
    if weakest == "not_pit":
        _fail(
            "research_pit_inputs_required",
            "ledger inputs must all satisfy at least research_pit",
        )
    return records, memberships


def validate_universe_membership_manifest(
    manifest: Mapping[str, Any],
    *,
    events: Sequence[Mapping[str, Any] | UniverseEvent],
    run_clock: Mapping[str, Any] | SessionClock,
    effective_clock: Mapping[str, Any] | SessionClock,
    previous_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one manifest against its full event population and clocks."""

    row = _validate_manifest_shape(manifest)
    run = _contract_call(validate_session_clock, run_clock)
    effective = _contract_call(validate_session_clock, effective_clock)
    _validate_clock_identity_pair(run, effective)
    if (
        row["run_id"] != run.run_id
        or row["session_clock_id"] != run.session_clock_id
        or row["session_clock_hash"] != run.semantic_hash
        or row["session_clock_record_hash"] != run.record_hash
        or row["session_clock_calendar_evidence_id"]
        != run.calendar_evidence_id
        or row["session_clock_calendar_evidence_record_hash"]
        != run.calendar_evidence_record_hash
        or row["session_clock_pit_tier"] != run.pit_tier
        or row["run_date"] != run.run_date
        or row["calendar_session_id"] != run.calendar_session_id
    ):
        _fail("manifest_run_clock_mismatch", "manifest does not bind the supplied run clock")
    if (
        row["effective_session_clock_id"] != effective.session_clock_id
        or row["effective_session_clock_hash"] != effective.semantic_hash
        or row["effective_session_clock_record_hash"] != effective.record_hash
        or row["effective_session_clock_calendar_evidence_id"]
        != effective.calendar_evidence_id
        or row["effective_session_clock_calendar_evidence_record_hash"]
        != effective.calendar_evidence_record_hash
        or row["effective_session_clock_pit_tier"] != effective.pit_tier
        or row["effective_session_id"] != effective.calendar_session_id
    ):
        _fail(
            "manifest_effective_clock_mismatch",
            "manifest does not bind the supplied effective clock",
        )
    run_open = _instant(run.session_open_at, field="run_clock.session_open_at")[1]
    effective_open = _instant(
        effective.session_open_at, field="effective_clock.session_open_at"
    )[1]
    if effective_open < run_open:
        _fail("effective_clock_precedes_run", "effective clock cannot precede run clock")
    cutoff = _instant(row["data_cutoff"], field="data_cutoff")[1]
    frozen = _instant(row["frozen_at"], field="frozen_at")[1]
    for clock, label in ((run, "run"), (effective, "effective")):
        clock_recorded = _instant(clock.recorded_at, field=f"{label}_clock.recorded_at")[1]
        if clock_recorded > cutoff:
            _fail(
                "session_clock_recorded_after_cutoff",
                f"{label} clock must be recorded by data_cutoff",
            )
    run_zone = ZoneInfo(run.calendar_timezone)
    if cutoff.astimezone(run_zone).date().isoformat() != run.run_date:
        _fail("run_clock_use_date_mismatch", "data_cutoff must fall on run_clock run_date")
    if frozen.astimezone(run_zone).date().isoformat() != run.run_date:
        _fail("run_clock_use_date_mismatch", "frozen_at must fall on run_clock run_date")
    weakest = min(
        [run.pit_tier, effective.pit_tier]
        + [
            _contract_call(validate_universe_event, event).pit_tier
            for event in events
        ],
        key=lambda item: _PIT_RANK[item],
    )
    if weakest == "not_pit":
        _fail(
            "research_pit_inputs_required",
            "manifest inputs must all satisfy at least research_pit",
        )
    _validate_manifest_event_bindings(row, events, previous_manifest)
    return row


def build_universe_membership_manifest(
    events: Sequence[Mapping[str, Any] | UniverseEvent],
    *,
    manifest_id: str,
    universe_id: str,
    event_batch_id: str,
    universe_definition_id: str,
    universe_definition_version: str,
    universe_definition_sha256: str,
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    run_clock: Mapping[str, Any] | SessionClock,
    effective_clock: Mapping[str, Any] | SessionClock,
    ledger_population_start: str,
    membership_as_of: str,
    data_cutoff: str,
    frozen_at: str,
    recorded_at: str,
    previous_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic manifest; every clock and timestamp is explicit."""

    run = _contract_call(validate_session_clock, run_clock)
    effective = _contract_call(validate_session_clock, effective_clock)
    records, memberships = validate_universe_event_population(
        events,
        universe_id=universe_id,
        data_cutoff=data_cutoff,
        frozen_at=frozen_at,
        membership_as_of=membership_as_of,
    )
    previous = None if previous_manifest is None else _validate_manifest_shape(previous_manifest)
    current_sources, current_evidence = _input_registry_bindings(
        source_contracts, evidence_records
    )
    source_registry = (
        {} if previous is None else deepcopy(previous["source_contract_registry"])
    )
    evidence_registry = (
        {} if previous is None else deepcopy(previous["evidence_record_registry"])
    )
    for stable_id, binding in current_sources.items():
        if stable_id in source_registry and source_registry[stable_id] != binding:
            _fail(
                "source_contract_id_conflict",
                "source contract identity conflicts with prior manifest history",
            )
        source_registry[stable_id] = binding
    for stable_id, binding in current_evidence.items():
        if stable_id in evidence_registry and evidence_registry[stable_id] != binding:
            _fail(
                "evidence_id_conflict",
                "evidence identity conflicts with prior manifest history",
            )
        evidence_registry[stable_id] = binding
    source_registry = dict(sorted(source_registry.items()))
    evidence_registry = dict(sorted(evidence_registry.items()))
    previous_ids = set(previous["universe_event_ids"]) if previous else set()
    event_ids = sorted(event.event_id for event in records)
    weakest = min(
        [run.pit_tier, effective.pit_tier] + [event.pit_tier for event in records],
        key=lambda item: _PIT_RANK[item],
    )
    if weakest == "not_pit":
        _fail(
            "research_pit_inputs_required",
            "ledger inputs must all satisfy at least research_pit",
        )
    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": MANIFEST_RECORD_TYPE,
        "manifest_id": _text(manifest_id, field="manifest_id"),
        "universe_id": _text(universe_id, field="universe_id"),
        "event_batch_id": _text(event_batch_id, field="event_batch_id"),
        "universe_definition_id": _text(
            universe_definition_id, field="universe_definition_id"
        ),
        "universe_definition_version": _text(
            universe_definition_version, field="universe_definition_version"
        ),
        "universe_definition_sha256": _sha256(
            universe_definition_sha256, field="universe_definition_sha256"
        ),
        "source_contract_registry": source_registry,
        "evidence_record_registry": evidence_registry,
        "run_id": run.run_id,
        "session_clock_id": run.session_clock_id,
        "session_clock_hash": run.semantic_hash,
        "session_clock_record_hash": run.record_hash,
        "session_clock_calendar_evidence_id": run.calendar_evidence_id,
        "session_clock_calendar_evidence_record_hash": (
            run.calendar_evidence_record_hash
        ),
        "session_clock_pit_tier": run.pit_tier,
        "effective_session_clock_id": effective.session_clock_id,
        "effective_session_clock_hash": effective.semantic_hash,
        "effective_session_clock_record_hash": effective.record_hash,
        "effective_session_clock_calendar_evidence_id": (
            effective.calendar_evidence_id
        ),
        "effective_session_clock_calendar_evidence_record_hash": (
            effective.calendar_evidence_record_hash
        ),
        "effective_session_clock_pit_tier": effective.pit_tier,
        "run_date": run.run_date,
        "calendar_session_id": run.calendar_session_id,
        "effective_session_id": effective.calendar_session_id,
        "ledger_population_start": _instant(
            ledger_population_start, field="ledger_population_start"
        )[0],
        "membership_as_of": _instant(membership_as_of, field="membership_as_of")[0],
        "data_cutoff": _instant(data_cutoff, field="data_cutoff")[0],
        "frozen_at": _instant(frozen_at, field="frozen_at")[0],
        "recorded_at": _instant(recorded_at, field="recorded_at")[0],
        "previous_manifest_id": None if previous is None else previous["manifest_id"],
        "previous_manifest_hash": None if previous is None else previous["manifest_hash"],
        "batch_event_ids": sorted(set(event_ids) - previous_ids),
        "universe_event_ids": event_ids,
        "universe_event_semantic_snapshot_sha256": _event_semantic_snapshot(records),
        "universe_event_record_snapshot_sha256": _event_record_snapshot(records),
        "memberships": memberships,
        "membership_snapshot_sha256": canonical_hash(
            _membership_semantic_rows(memberships)
        ),
        "ledger_population_complete": True,
        "external_universe_coverage_status": "unverified",
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "parity_status": "contract_only_unwired",
        "known_future_leakage": False,
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    row["semantic_hash"] = canonical_hash(_manifest_semantic_payload(row))
    row["manifest_hash"] = canonical_hash(_manifest_record_payload(row))
    return validate_universe_membership_manifest(
        row,
        events=records,
        run_clock=run,
        effective_clock=effective,
        previous_manifest=previous,
    )


def _load_ledger_text(
    text: str, *, source: str, allow_empty: bool
) -> dict[str, list[dict[str, Any]]]:
    if not text:
        if allow_empty:
            return {"events": [], "manifests": []}
        _fail("universe_ledger_empty", f"{source} has no committed manifest")
    raw_rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            _fail("blank_jsonl_row", f"blank row at {source}:{line_number}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise V2UniverseLedgerValidationError(
                "invalid_jsonl", f"invalid JSON at {source}:{line_number}: {exc.msg}"
            ) from exc
        if not isinstance(row, dict):
            _fail("json_object_required", f"row {line_number} must be an object")
        raw_rows.append(row)

    events: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    uncommitted_ids: list[str] = []
    event_semantic_by_id: dict[str, str] = {}
    seen_manifest_ids: set[str] = set()
    seen_event_batch_ids: set[str] = set()
    clock_bindings: dict[str, tuple[str, str, str, str]] = {}
    for row in raw_rows:
        record_type = row.get("record_type")
        if record_type == "v2_universe_event":
            event = _contract_call(validate_universe_event, row)
            previous_semantic = event_semantic_by_id.get(event.event_id)
            if previous_semantic is not None:
                if previous_semantic != event.semantic_hash:
                    _fail(
                        "immutable_key_conflict",
                        f"event_id {event.event_id!r} already has different semantics",
                    )
                _fail(
                    "duplicate_physical_universe_event",
                    "a committed ledger cannot store a duplicate event row",
                )
            events.append(event.to_dict())
            event_semantic_by_id[event.event_id] = event.semantic_hash
            uncommitted_ids.append(event.event_id)
            continue
        if record_type != MANIFEST_RECORD_TYPE:
            _fail("unsupported_ledger_record_type", f"unsupported record_type {record_type!r}")
        manifest = _validate_manifest_shape(row)
        if manifest["manifest_id"] in seen_manifest_ids:
            _fail("duplicate_physical_manifest", "manifest_id appears more than once")
        if manifest["event_batch_id"] in seen_event_batch_ids:
            _fail(
                "duplicate_event_batch_id",
                "event_batch_id must be unique across committed manifests",
            )
        try:
            _extend_clock_binding_registry(manifest, clock_bindings)
        except V2UniverseLedgerConflictError as exc:
            raise V2UniverseLedgerValidationError(
                "damaged_session_clock_registry", exc.detail
            ) from exc
        previous = manifests[-1] if manifests else None
        _validate_manifest_event_bindings(manifest, events, previous)
        if manifest["batch_event_ids"] != sorted(uncommitted_ids):
            _fail(
                "orphan_or_cross_batch_events",
                "physical event rows since the prior manifest must equal batch_event_ids",
            )
        manifests.append(manifest)
        seen_manifest_ids.add(manifest["manifest_id"])
        seen_event_batch_ids.add(manifest["event_batch_id"])
        uncommitted_ids = []
    if uncommitted_ids or not manifests or raw_rows[-1].get("record_type") != MANIFEST_RECORD_TYPE:
        _fail("uncommitted_universe_event_tail", "ledger must end with a manifest commit marker")
    return {"events": events, "manifests": manifests}


def load_v2_universe_ledger(
    path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, list[dict[str, Any]]]:
    """Strictly load the complete committed ledger; missing is not empty."""

    ledger_path = Path(path)
    if not ledger_path.exists():
        _fail("universe_ledger_missing", f"ledger does not exist: {ledger_path}")
    try:
        text = ledger_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise V2UniverseLedgerError(
            "universe_ledger_read_failed", f"cannot read {ledger_path}: {exc}"
        ) from exc
    return _load_ledger_text(text, source=str(ledger_path), allow_empty=False)


@contextmanager
def _exclusive_ledger_lock(lock_path: Path, *, timeout_seconds: float):
    """Cross-platform OS advisory lock; process exit releases the lock."""

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    locked = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        deadline = time.monotonic() + timeout_seconds
        while not locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - CI may exercise POSIX.
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except (OSError, BlockingIOError) as exc:
                if time.monotonic() >= deadline:
                    raise V2UniverseLedgerLockError(
                        "universe_ledger_lock_timeout",
                        f"timed out waiting for {lock_path}",
                    ) from exc
                time.sleep(_LOCK_POLL_SECONDS)
        yield
    finally:
        if locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def _validate_writer_identity_registry(
    *,
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    run_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    run_calendar_source_contract: Mapping[str, Any] | SourceContract,
    effective_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    effective_calendar_source_contract: Mapping[str, Any] | SourceContract,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Reject stable-ID aliases across event and calendar input registries."""

    all_sources = [
        *source_contracts,
        run_calendar_source_contract,
        effective_calendar_source_contract,
    ]
    all_evidence = [
        *evidence_records,
        run_calendar_evidence,
        effective_calendar_evidence,
    ]
    return _input_registry_bindings(all_sources, all_evidence)


def _validate_clock_identity_pair(run: SessionClock, effective: SessionClock) -> None:
    if run.session_clock_id == effective.session_clock_id and (
        run.semantic_hash != effective.semantic_hash
        or run.record_hash != effective.record_hash
    ):
        _fail(
            "session_clock_id_conflict",
            "one session_clock_id cannot resolve to multiple clock records",
        )


def _validate_manifest_input_registry(
    manifest: Mapping[str, Any],
    previous_manifest: Mapping[str, Any] | None,
    current_sources: Mapping[str, str],
    current_evidence: Mapping[str, Mapping[str, str]],
) -> None:
    expected_sources = (
        {}
        if previous_manifest is None
        else deepcopy(previous_manifest["source_contract_registry"])
    )
    expected_evidence = (
        {}
        if previous_manifest is None
        else deepcopy(previous_manifest["evidence_record_registry"])
    )
    for stable_id, binding in current_sources.items():
        if stable_id in expected_sources and expected_sources[stable_id] != binding:
            raise V2UniverseLedgerConflictError(
                "source_contract_id_conflict",
                "source contract identity conflicts with committed history",
            )
        expected_sources[stable_id] = binding
    for stable_id, binding in current_evidence.items():
        if stable_id in expected_evidence and expected_evidence[stable_id] != binding:
            raise V2UniverseLedgerConflictError(
                "evidence_id_conflict",
                "evidence identity conflicts with committed history",
            )
        expected_evidence[stable_id] = dict(binding)
    if (
        manifest["source_contract_registry"]
        != dict(sorted(expected_sources.items()))
        or manifest["evidence_record_registry"]
        != dict(sorted(expected_evidence.items()))
    ):
        _fail(
            "manifest_input_registry_mismatch",
            "manifest registry must exactly equal prior history plus supplied inputs",
        )


def _extend_clock_binding_registry(
    manifest: Mapping[str, Any],
    registry: dict[str, tuple[str, str, str, str]],
) -> None:
    bindings = (
        (
            manifest["session_clock_id"],
            (
                manifest["session_clock_hash"],
                manifest["session_clock_record_hash"],
                manifest["session_clock_calendar_evidence_id"],
                manifest["session_clock_calendar_evidence_record_hash"],
            ),
        ),
        (
            manifest["effective_session_clock_id"],
            (
                manifest["effective_session_clock_hash"],
                manifest["effective_session_clock_record_hash"],
                manifest["effective_session_clock_calendar_evidence_id"],
                manifest["effective_session_clock_calendar_evidence_record_hash"],
            ),
        ),
    )
    for clock_id, binding in bindings:
        if clock_id in registry and registry[clock_id] != binding:
            raise V2UniverseLedgerConflictError(
                "session_clock_id_conflict",
                "session_clock_id is already bound to another clock record",
            )
        registry[clock_id] = binding


def _validate_clock_bindings_against_history(
    manifest: Mapping[str, Any],
    existing_manifests: Sequence[Mapping[str, Any]],
) -> None:
    registry: dict[str, tuple[str, str, str, str]] = {}
    for item in existing_manifests:
        try:
            _extend_clock_binding_registry(item, registry)
        except V2UniverseLedgerConflictError:
            _fail(
                "damaged_session_clock_registry",
                "stored manifests disagree on one session_clock_id",
            )
    _extend_clock_binding_registry(manifest, registry)


def _validated_lock_timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise V2UniverseLedgerLockError(
            "invalid_lock_timeout", "lock_timeout_seconds must be finite and non-negative"
        ) from exc
    if not math.isfinite(timeout) or timeout < 0:
        raise V2UniverseLedgerLockError(
            "invalid_lock_timeout", "lock_timeout_seconds must be finite and non-negative"
        )
    return timeout


def _prepare_v2_universe_batch_append(
    events: Iterable[Mapping[str, Any] | UniverseEvent],
    manifest: Mapping[str, Any],
    *,
    run_clock: Mapping[str, Any] | SessionClock,
    effective_clock: Mapping[str, Any] | SessionClock,
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    run_calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    run_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    run_calendar_source_contract: Mapping[str, Any] | SourceContract,
    effective_calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    effective_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    effective_calendar_source_contract: Mapping[str, Any] | SourceContract,
) -> dict[str, Any]:
    """Validate and materialize one request before any writer I/O."""

    if isinstance(events, (str, bytes, bytearray, Mapping)):
        _fail("event_sequence_required", "events must be an iterable of objects")
    proposed = [_contract_call(validate_universe_event, event) for event in events]
    proposed_manifest = _validate_manifest_shape(manifest)
    current_sources, current_evidence = _validate_writer_identity_registry(
        evidence_records=evidence_records,
        source_contracts=source_contracts,
        run_calendar_evidence=run_calendar_evidence,
        run_calendar_source_contract=run_calendar_source_contract,
        effective_calendar_evidence=effective_calendar_evidence,
        effective_calendar_source_contract=effective_calendar_source_contract,
    )
    verified_run = _contract_call(
        validate_session_clock_against_calendar,
        run_clock,
        run_calendar_sessions,
        run_calendar_evidence,
        run_calendar_source_contract,
    )
    verified_effective = _contract_call(
        validate_session_clock_against_calendar,
        effective_clock,
        effective_calendar_sessions,
        effective_calendar_evidence,
        effective_calendar_source_contract,
    )
    _validate_clock_identity_pair(verified_run, verified_effective)
    for event in proposed:
        _contract_call(
            validate_universe_event_against_evidence,
            event,
            evidence_records,
            source_contracts,
        )
        _contract_call(
            validate_universe_event_against_session_clocks,
            event,
            run_clock=verified_run,
            run_calendar_sessions=run_calendar_sessions,
            run_calendar_evidence=run_calendar_evidence,
            run_calendar_source_contract=run_calendar_source_contract,
            effective_clock=verified_effective,
            effective_calendar_sessions=effective_calendar_sessions,
            effective_calendar_evidence=effective_calendar_evidence,
            effective_calendar_source_contract=effective_calendar_source_contract,
        )

    return {
        "proposed": proposed,
        "manifest": proposed_manifest,
        "current_sources": current_sources,
        "current_evidence": current_evidence,
        "verified_run": verified_run,
        "verified_effective": verified_effective,
    }


def _classify_v2_universe_batch_append(
    loaded: Mapping[str, Sequence[Mapping[str, Any]]],
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify a prepared request against one locked, strict logical view."""

    proposed = prepared["proposed"]
    proposed_manifest = prepared["manifest"]
    current_sources = prepared["current_sources"]
    current_evidence = prepared["current_evidence"]
    verified_run = prepared["verified_run"]
    verified_effective = prepared["verified_effective"]

    existing_events = [
        _contract_call(validate_universe_event, event) for event in loaded["events"]
    ]
    existing_manifests = list(loaded["manifests"])
    _validate_clock_bindings_against_history(proposed_manifest, existing_manifests)

    same_manifest = next(
        (
            item
            for item in existing_manifests
            if item["manifest_id"] == proposed_manifest["manifest_id"]
        ),
        None,
    )
    if same_manifest is None:
        registry_previous = existing_manifests[-1] if existing_manifests else None
    else:
        same_index = existing_manifests.index(same_manifest)
        registry_previous = (
            existing_manifests[same_index - 1] if same_index > 0 else None
        )
    _validate_manifest_input_registry(
        proposed_manifest,
        registry_previous,
        current_sources,
        current_evidence,
    )
    new_events: list[UniverseEvent] = []
    combined = list(existing_events)
    event_semantic_by_id = {
        event.event_id: event.semantic_hash for event in existing_events
    }
    for event in sorted(proposed, key=lambda item: (item.effective_at, item.event_id)):
        previous_semantic = event_semantic_by_id.get(event.event_id)
        if previous_semantic is not None:
            if previous_semantic != event.semantic_hash:
                raise V2UniverseLedgerConflictError(
                    "universe_event_id_conflict",
                    f"event_id {event.event_id!r} already has different semantics",
                )
            continue
        event_semantic_by_id[event.event_id] = event.semantic_hash
        combined.append(event)
        new_events.append(event)
    if same_manifest is not None:
        if same_manifest["semantic_hash"] == proposed_manifest["semantic_hash"] and not new_events:
            same_index = existing_manifests.index(same_manifest)
            same_previous = (
                existing_manifests[same_index - 1] if same_index > 0 else None
            )
            same_event_ids = set(same_manifest["universe_event_ids"])
            same_events = [
                event for event in existing_events if event.event_id in same_event_ids
            ]
            validate_universe_membership_manifest(
                same_manifest,
                events=same_events,
                run_clock=verified_run,
                effective_clock=verified_effective,
                previous_manifest=same_previous,
            )
            return {
                "status": "duplicate",
                "new_events": [],
                "manifest": deepcopy(same_manifest),
                "events": [event.to_dict() for event in existing_events],
                "manifests": [deepcopy(item) for item in existing_manifests],
            }
        raise V2UniverseLedgerConflictError(
            "manifest_id_conflict",
            f"manifest_id {proposed_manifest['manifest_id']!r} changed semantics",
        )
    if proposed_manifest["event_batch_id"] in {
        item["event_batch_id"] for item in existing_manifests
    }:
        raise V2UniverseLedgerConflictError(
            "event_batch_id_conflict",
            "event_batch_id is already committed by another manifest",
        )
    previous = existing_manifests[-1] if existing_manifests else None
    validated_manifest = validate_universe_membership_manifest(
        proposed_manifest,
        events=combined,
        run_clock=verified_run,
        effective_clock=verified_effective,
        previous_manifest=previous,
    )
    if validated_manifest["batch_event_ids"] != sorted(
        event.event_id for event in new_events
    ):
        _fail(
            "manifest_batch_membership_mismatch",
            "manifest batch_event_ids must equal the rows newly written",
        )
    return {
        "status": "append",
        "new_events": [event.to_dict() for event in new_events],
        "manifest": validated_manifest,
        "events": [event.to_dict() for event in combined],
        "manifests": [
            *[deepcopy(item) for item in existing_manifests],
            deepcopy(validated_manifest),
        ],
    }


def append_v2_universe_batch(
    path: str | Path,
    events: Iterable[Mapping[str, Any] | UniverseEvent],
    manifest: Mapping[str, Any],
    *,
    run_clock: Mapping[str, Any] | SessionClock,
    effective_clock: Mapping[str, Any] | SessionClock,
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    run_calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    run_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    run_calendar_source_contract: Mapping[str, Any] | SourceContract,
    effective_calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    effective_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    effective_calendar_source_contract: Mapping[str, Any] | SourceContract,
    lock_timeout_seconds: float = _LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Atomically commit after mandatory M1 evidence and clock validation."""

    prepared = _prepare_v2_universe_batch_append(
        events,
        manifest,
        run_clock=run_clock,
        effective_clock=effective_clock,
        evidence_records=evidence_records,
        source_contracts=source_contracts,
        run_calendar_sessions=run_calendar_sessions,
        run_calendar_evidence=run_calendar_evidence,
        run_calendar_source_contract=run_calendar_source_contract,
        effective_calendar_sessions=effective_calendar_sessions,
        effective_calendar_evidence=effective_calendar_evidence,
        effective_calendar_source_contract=effective_calendar_source_contract,
    )
    timeout = _validated_lock_timeout(lock_timeout_seconds)

    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(f"{ledger_path}.lock")
    with _exclusive_ledger_lock(lock_path, timeout_seconds=timeout):
        try:
            exists = ledger_path.exists()
            existing_text = ledger_path.read_text(encoding="utf-8-sig") if exists else ""
        except (OSError, UnicodeError) as exc:
            raise V2UniverseLedgerError(
                "universe_ledger_read_failed", f"cannot read {ledger_path}: {exc}"
            ) from exc
        loaded = _load_ledger_text(
            existing_text,
            source=str(ledger_path),
            allow_empty=not exists,
        )
        plan = _classify_v2_universe_batch_append(loaded, prepared)
        if plan["status"] == "duplicate":
            committed_manifest = plan["manifest"]
            return {
                "status": "duplicate",
                "rows_written": 0,
                "event_rows_written": 0,
                "manifest_id": committed_manifest["manifest_id"],
                "manifest_hash": committed_manifest["manifest_hash"],
                "event_count": len(plan["events"]),
                "manifest_count": len(plan["manifests"]),
                "path": str(ledger_path),
            }

        prefix = existing_text
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        suffix = "".join(canonical_json(event) + "\n" for event in plan["new_events"])
        suffix += canonical_json(plan["manifest"]) + "\n"
        atomic_write_text(prefix + suffix, ledger_path)
        return {
            "status": "appended",
            "rows_written": len(plan["new_events"]) + 1,
            "event_rows_written": len(plan["new_events"]),
            "manifest_id": plan["manifest"]["manifest_id"],
            "manifest_hash": plan["manifest"]["manifest_hash"],
            "event_count": len(plan["events"]),
            "manifest_count": len(plan["manifests"]),
            "path": str(ledger_path),
        }


def read_v2_universe_membership(
    path: str | Path,
    *,
    manifest_id: str,
    as_of: str,
    universe_id: str | None = None,
) -> dict[str, Any]:
    """Resolve one explicit manifest through the sole daily/replay code path."""

    loaded = load_v2_universe_ledger(path)
    requested_id = _text(manifest_id, field="manifest_id")
    manifest = next(
        (item for item in loaded["manifests"] if item["manifest_id"] == requested_id),
        None,
    )
    if manifest is None:
        _fail("unknown_manifest_id", f"manifest_id {requested_id!r} is not committed")
    if universe_id is not None and manifest["universe_id"] != universe_id:
        _fail("universe_id_mismatch", "requested universe_id does not match manifest")
    as_of_text, as_of_dt = _instant(as_of, field="as_of")
    population_start_dt = _instant(
        manifest["ledger_population_start"], field="ledger_population_start"
    )[1]
    membership_dt = _instant(
        manifest["membership_as_of"], field="membership_as_of"
    )[1]
    if as_of_dt < population_start_dt:
        _fail(
            "as_of_before_ledger_population",
            "membership is unknown before ledger_population_start",
        )
    if as_of_dt > membership_dt:
        _fail(
            "as_of_after_membership_projection",
            "as_of cannot exceed manifest membership_as_of",
        )

    manifest_ids = set(manifest["universe_event_ids"])
    selected = []
    for raw in loaded["events"]:
        event = _contract_call(validate_universe_event, raw)
        effective_dt = _instant(event.effective_at, field="event.effective_at")[1]
        if event.event_id in manifest_ids and effective_dt <= as_of_dt:
            selected.append(event)
    _, memberships = validate_universe_event_population(
        selected,
        universe_id=manifest["universe_id"],
        data_cutoff=manifest["data_cutoff"],
        membership_as_of=as_of_text,
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": SNAPSHOT_RECORD_TYPE,
        "reader_contract": SHARED_READER_CONTRACT,
        "manifest_id": manifest["manifest_id"],
        "manifest_hash": manifest["manifest_hash"],
        "universe_id": manifest["universe_id"],
        "universe_definition_id": manifest["universe_definition_id"],
        "universe_definition_version": manifest["universe_definition_version"],
        "universe_definition_sha256": manifest["universe_definition_sha256"],
        "as_of": as_of_text,
        "ledger_population_start": manifest["ledger_population_start"],
        "membership_as_of": manifest["membership_as_of"],
        "data_cutoff": manifest["data_cutoff"],
        "pit_tier": manifest["pit_tier"],
        "result_ceiling": manifest["result_ceiling"],
        "paper_live_eligible": manifest["paper_live_eligible"],
        "parity_status": manifest["parity_status"],
        "memberships": memberships,
        "membership_snapshot_sha256": canonical_hash(
            _membership_semantic_rows(memberships)
        ),
        "ledger_population_complete": True,
        "external_universe_coverage_status": "unverified",
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    result["snapshot_hash"] = canonical_hash(result)
    return result


def validate_external_universe_coverage_against_manifest(
    coverage_snapshot: Mapping[str, Any] | ExternalUniverseCoverageSnapshot,
    manifest: Mapping[str, Any],
    events: Iterable[Mapping[str, Any] | UniverseEvent],
    *,
    coverage_evidence: Mapping[str, Any] | EvidenceRecord,
    coverage_source_contract: Mapping[str, Any] | SourceContract,
    mapping_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord] = (),
    mapping_source_contracts: Sequence[Mapping[str, Any] | SourceContract] = (),
) -> dict[str, Any]:
    """Reconcile promotion-only coverage with one immutable ledger commit.

    This is deliberately a read-only cross-check.  It does not upgrade the
    manifest's unverified external-market status or participate in scout
    admission, CandidatePool construction, persistence, or runtime reads.
    """

    try:
        coverage = validate_external_universe_coverage_snapshot(coverage_snapshot)
        input_binding = validate_external_universe_coverage_against_inputs(
            coverage,
            coverage_evidence=coverage_evidence,
            coverage_source_contract=coverage_source_contract,
            mapping_evidence_records=mapping_evidence_records,
            mapping_source_contracts=mapping_source_contracts,
        )
    except V2UniverseCoverageError as exc:
        raise V2UniverseLedgerValidationError(exc.code, exc.detail) from exc
    committed = _validate_manifest_shape(manifest)
    if (
        coverage.universe_manifest_id != committed["manifest_id"]
        or coverage.universe_manifest_hash != committed["manifest_hash"]
    ):
        _fail("coverage_manifest_binding_mismatch", "coverage does not bind this manifest")
    for field in (
        "universe_id",
        "universe_definition_id",
        "universe_definition_version",
        "universe_definition_sha256",
        "membership_as_of",
        "data_cutoff",
    ):
        if getattr(coverage, field) != committed[field]:
            _fail(
                "coverage_manifest_identity_mismatch",
                f"coverage {field} does not match the committed manifest",
            )
    _, coverage_frozen_dt = _instant(coverage.frozen_at, field="coverage.frozen_at")
    _, manifest_recorded_dt = _instant(committed["recorded_at"], field="manifest.recorded_at")
    if coverage_frozen_dt < manifest_recorded_dt:
        _fail(
            "coverage_frozen_before_manifest",
            "coverage cannot bind a manifest that was not yet recorded",
        )

    event_records, memberships = validate_universe_event_population(
        events,
        universe_id=committed["universe_id"],
        data_cutoff=committed["data_cutoff"],
        frozen_at=committed["frozen_at"],
        membership_as_of=committed["membership_as_of"],
    )
    if sorted(item.event_id for item in event_records) != committed["universe_event_ids"]:
        _fail(
            "coverage_manifest_event_population_mismatch",
            "supplied events do not equal the manifest event population",
        )
    if memberships != committed["memberships"]:
        _fail(
            "coverage_manifest_membership_mismatch",
            "manifest memberships do not match the supplied event population",
        )

    coverage_mappings = {
        (
            row.security_mapping.security_id,
            row.security_mapping.listing_id,
            row.security_mapping.mapping_sha256,
        )
        for row in coverage.rows
        if row.disposition == "mapped" and row.security_mapping is not None
    }
    active_manifest_mappings = {
        (row["security_id"], row["listing_id"], row["mapping_sha256"])
        for row in memberships
        if row["state"] != "retired"
    }
    if coverage_mappings != active_manifest_mappings:
        _fail(
            "coverage_active_mapping_set_mismatch",
            "mapped coverage rows must exactly equal active manifest mappings",
        )
    if coverage.coverage_status == "verified_known_empty" and active_manifest_mappings:
        _fail(
            "known_empty_active_membership_mismatch",
            "known-empty coverage requires an empty active manifest membership",
        )
    binding = {
        "coverage_snapshot_id": coverage.coverage_snapshot_id,
        "coverage_snapshot_record_hash": coverage.record_hash,
        "coverage_input_binding_sha256": input_binding["input_binding_sha256"],
        "universe_manifest_id": committed["manifest_id"],
        "universe_manifest_hash": committed["manifest_hash"],
        "active_mapping_count": len(active_manifest_mappings),
        "external_universe_coverage_status": "unverified",
        "paper_live_eligible": False,
        "trade_enabled": False,
    }
    binding["coverage_manifest_binding_sha256"] = canonical_hash(binding)
    return binding


# These are true aliases: adapters cannot fork membership logic by consumer.
read_v2_daily_universe = read_v2_universe_membership
read_v2_replay_universe = read_v2_universe_membership


__all__ = [
    "SCHEMA_VERSION",
    "MANIFEST_RECORD_TYPE",
    "SNAPSHOT_RECORD_TYPE",
    "SHARED_READER_CONTRACT",
    "DEFAULT_LEDGER_PATH",
    "V2UniverseLedgerError",
    "V2UniverseLedgerValidationError",
    "V2UniverseLedgerConflictError",
    "V2UniverseLedgerLockError",
    "validate_universe_event_population",
    "build_universe_membership_manifest",
    "validate_universe_membership_manifest",
    "load_v2_universe_ledger",
    "append_v2_universe_batch",
    "read_v2_universe_membership",
    "read_v2_daily_universe",
    "read_v2_replay_universe",
    "validate_external_universe_coverage_against_manifest",
]
