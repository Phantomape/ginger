"""Research-only external-universe coverage contracts for Ginger V2.

This module belongs only to the promotion-construction lane.  It proves that
one declared external source population was fully dispositioned and can be
reconciled with a committed V2 universe manifest.  It is not a CandidatePool
or scout-admission guard and grants no market-wide, paper, or live eligibility.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, Sequence

try:  # Support package imports and direct ``quant/`` execution.
    from .v2_contracts import (
        EvidenceRecord,
        SecurityMappingSnapshot,
        SourceContract,
        V2ContractValidationError,
        canonical_hash,
        validate_evidence_against_source,
        validate_evidence_record,
        validate_source_contract,
    )
except ImportError:  # pragma: no cover - direct script fallback.
    from v2_contracts import (  # type: ignore
        EvidenceRecord,
        SecurityMappingSnapshot,
        SourceContract,
        V2ContractValidationError,
        canonical_hash,
        validate_evidence_against_source,
        validate_evidence_record,
        validate_source_contract,
    )


SCHEMA_VERSION = 1
ROW_RECORD_TYPE = "v2_external_universe_coverage_row"
SNAPSHOT_RECORD_TYPE = "v2_external_universe_coverage_snapshot"
DISPOSITIONS = frozenset({"mapped", "unmapped", "excluded"})
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_PIT_RANK = {"not_pit": 0, "research_pit": 1, "canonical_pit": 2}


class V2UniverseCoverageError(RuntimeError):
    """Coverage validation failed with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


def _fail(code: str, message: str) -> None:
    raise V2UniverseCoverageError(code, message)


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
        raise V2UniverseCoverageError(
            "timezone_aware_instant_required", f"{field} is not a valid ISO instant"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("timezone_aware_instant_required", f"{field} must include an offset")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _integer(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("nonnegative_integer_required", f"{field} must be a nonnegative integer")
    return value


def _contract_call(function, *args):
    try:
        return function(*args)
    except V2ContractValidationError as exc:
        raise V2UniverseCoverageError(exc.code, f"{exc.path}: {exc.detail}") from exc


def _plain_mapping(value: Mapping[str, Any], *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("object_required", f"{field} must be an object")
    return deepcopy(dict(value))


@dataclass(frozen=True, slots=True)
class ExternalUniverseCoverageRow:
    schema_version: int
    record_type: str
    source_row_id: str
    source_row_sha256: str
    disposition: str
    reason_code: str
    reason: str
    security_mapping: SecurityMappingSnapshot | None
    mapping_evidence_id: str | None
    mapping_evidence_semantic_hash: str | None
    mapping_evidence_record_hash: str | None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExternalUniverseCoverageRow":
        raw = _plain_mapping(value, field="coverage row")
        expected = set(cls.__dataclass_fields__)
        if set(raw) != expected:
            _fail("invalid_coverage_row_shape", "coverage row must have the exact v1 fields")
        if raw["schema_version"] != SCHEMA_VERSION:
            _fail("unsupported_schema_version", "coverage row schema_version must be 1")
        if raw["record_type"] != ROW_RECORD_TYPE:
            _fail("invalid_record_type", f"coverage row record_type must be {ROW_RECORD_TYPE!r}")
        disposition = raw["disposition"]
        if disposition not in DISPOSITIONS:
            _fail("invalid_coverage_disposition", "disposition must be mapped, unmapped, or excluded")
        mapping = (
            None
            if raw["security_mapping"] is None
            else _contract_call(SecurityMappingSnapshot.from_dict, raw["security_mapping"])
        )
        evidence_id = _optional_text(raw["mapping_evidence_id"], field="mapping_evidence_id")
        semantic_hash = raw["mapping_evidence_semantic_hash"]
        record_hash = raw["mapping_evidence_record_hash"]
        if semantic_hash is not None:
            semantic_hash = _sha256(semantic_hash, field="mapping_evidence_semantic_hash")
        if record_hash is not None:
            record_hash = _sha256(record_hash, field="mapping_evidence_record_hash")
        has_mapping_bundle = all(
            item is not None for item in (mapping, evidence_id, semantic_hash, record_hash)
        )
        has_partial_bundle = any(
            item is not None for item in (mapping, evidence_id, semantic_hash, record_hash)
        ) and not has_mapping_bundle
        if has_partial_bundle:
            _fail("incomplete_mapping_binding", "mapping and all evidence identities must appear together")
        if disposition == "mapped" and not has_mapping_bundle:
            _fail("mapped_row_requires_mapping", "mapped rows require effective mapping evidence")
        if disposition == "unmapped" and has_mapping_bundle:
            _fail("unmapped_row_forbids_mapping", "unmapped rows cannot carry a mapping")
        return cls(
            schema_version=SCHEMA_VERSION,
            record_type=ROW_RECORD_TYPE,
            source_row_id=_text(raw["source_row_id"], field="source_row_id"),
            source_row_sha256=_sha256(raw["source_row_sha256"], field="source_row_sha256"),
            disposition=disposition,
            reason_code=_text(raw["reason_code"], field="reason_code"),
            reason=_text(raw["reason"], field="reason"),
            security_mapping=mapping,
            mapping_evidence_id=evidence_id,
            mapping_evidence_semantic_hash=semantic_hash,
            mapping_evidence_record_hash=record_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "source_row_id": self.source_row_id,
            "source_row_sha256": self.source_row_sha256,
            "disposition": self.disposition,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "security_mapping": (
                None if self.security_mapping is None else self.security_mapping.to_dict()
            ),
            "mapping_evidence_id": self.mapping_evidence_id,
            "mapping_evidence_semantic_hash": self.mapping_evidence_semantic_hash,
            "mapping_evidence_record_hash": self.mapping_evidence_record_hash,
        }


@dataclass(frozen=True, slots=True)
class ExternalUniverseCoverageSnapshot:
    schema_version: int
    record_type: str
    coverage_snapshot_id: str
    universe_id: str
    universe_definition_id: str
    universe_definition_version: str
    universe_definition_sha256: str
    universe_manifest_id: str
    universe_manifest_hash: str
    coverage_scope_id: str
    coverage_scope_version: str
    coverage_scope_sha256: str
    coverage_source_contract_id: str
    coverage_source_contract_hash: str
    coverage_evidence_id: str
    coverage_evidence_semantic_hash: str
    coverage_evidence_record_hash: str
    membership_as_of: str
    data_cutoff: str
    frozen_at: str
    recorded_at: str
    enumeration_complete: bool
    source_reported_row_count: int
    rows: tuple[ExternalUniverseCoverageRow, ...]
    disposition_counts: Mapping[str, int]
    row_snapshot_sha256: str
    coverage_status: str
    pit_tier: str
    external_universe_coverage_status: str
    result_ceiling: str
    paper_live_eligible: bool
    parity_status: str
    known_future_leakage: bool
    outcome_blind: bool
    results_accessed: bool
    authority: str
    trade_enabled: bool
    semantic_hash: str
    record_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExternalUniverseCoverageSnapshot":
        raw = _plain_mapping(value, field="coverage snapshot")
        expected = set(cls.__dataclass_fields__)
        if set(raw) != expected:
            _fail("invalid_coverage_snapshot_shape", "coverage snapshot must have the exact v1 fields")
        if raw["schema_version"] != SCHEMA_VERSION:
            _fail("unsupported_schema_version", "coverage snapshot schema_version must be 1")
        if raw["record_type"] != SNAPSHOT_RECORD_TYPE:
            _fail("invalid_record_type", f"record_type must be {SNAPSHOT_RECORD_TYPE!r}")
        rows_raw = raw["rows"]
        if not isinstance(rows_raw, list):
            _fail("coverage_rows_required", "rows must be a JSON array")
        rows = tuple(ExternalUniverseCoverageRow.from_dict(item) for item in rows_raw)
        row_ids = [item.source_row_id for item in rows]
        row_hashes = [item.source_row_sha256 for item in rows]
        if row_ids != sorted(row_ids):
            _fail("coverage_rows_not_sorted", "coverage rows must be sorted by source_row_id")
        if len(row_ids) != len(set(row_ids)):
            _fail("duplicate_source_row_id", "source_row_id values must be unique")
        if len(row_hashes) != len(set(row_hashes)):
            _fail("duplicate_source_row_hash", "source_row_sha256 values must be unique")
        mapping_hashes: dict[str, str] = {}
        for item in rows:
            if item.security_mapping is None:
                continue
            mapping_id = item.security_mapping.mapping_id
            mapping_hash = item.security_mapping.mapping_sha256
            if mapping_id in mapping_hashes and mapping_hashes[mapping_id] != mapping_hash:
                _fail(
                    "security_mapping_identity_conflict",
                    "one mapping_id cannot resolve to multiple mapping snapshots",
                )
            mapping_hashes[mapping_id] = mapping_hash
        reported_count = _integer(raw["source_reported_row_count"], field="source_reported_row_count")
        if reported_count != len(rows):
            _fail("coverage_row_count_mismatch", "reported row count must equal retained rows")
        if raw["enumeration_complete"] is not True:
            _fail("coverage_enumeration_incomplete", "coverage enumeration must be complete")
        counts_raw = _plain_mapping(raw["disposition_counts"], field="disposition_counts")
        if set(counts_raw) != DISPOSITIONS:
            _fail("invalid_disposition_counts", "disposition_counts must name all three dispositions")
        counts = {key: _integer(counts_raw[key], field=f"disposition_counts.{key}") for key in sorted(DISPOSITIONS)}
        actual_counts = {key: sum(item.disposition == key for item in rows) for key in sorted(DISPOSITIONS)}
        if counts != actual_counts or sum(counts.values()) != reported_count:
            _fail("coverage_disposition_count_mismatch", "disposition counts must conserve the source population")
        expected_row_snapshot = canonical_hash(
            [
                {"source_row_id": item.source_row_id, "source_row_sha256": item.source_row_sha256}
                for item in rows
            ]
        )
        row_snapshot = _sha256(raw["row_snapshot_sha256"], field="row_snapshot_sha256")
        if row_snapshot != expected_row_snapshot:
            _fail("coverage_row_snapshot_mismatch", "row snapshot hash is incorrect")
        expected_status = "verified_known_empty" if reported_count == 0 else "verified_complete"
        if raw["coverage_status"] != expected_status:
            _fail("invalid_coverage_status", f"coverage_status must be {expected_status!r}")
        membership_as_of, membership_dt = _instant(raw["membership_as_of"], field="membership_as_of")
        data_cutoff, cutoff_dt = _instant(raw["data_cutoff"], field="data_cutoff")
        frozen_at, frozen_dt = _instant(raw["frozen_at"], field="frozen_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], field="recorded_at")
        if not (membership_dt <= cutoff_dt <= frozen_dt <= recorded_dt):
            _fail(
                "invalid_coverage_chronology",
                "must satisfy membership_as_of <= data_cutoff <= frozen_at <= recorded_at",
            )
        fixed_values = {
            "pit_tier": "research_pit",
            "external_universe_coverage_status": "unverified",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "parity_status": "contract_only_unwired",
            "known_future_leakage": False,
            "outcome_blind": True,
            "results_accessed": False,
            "authority": "research_only",
            "trade_enabled": False,
        }
        for field, expected_value in fixed_values.items():
            if raw[field] != expected_value:
                _fail("coverage_boundary_violation", f"{field} must equal {expected_value!r}")
        obj = cls(
            schema_version=SCHEMA_VERSION,
            record_type=SNAPSHOT_RECORD_TYPE,
            coverage_snapshot_id=_text(raw["coverage_snapshot_id"], field="coverage_snapshot_id"),
            universe_id=_text(raw["universe_id"], field="universe_id"),
            universe_definition_id=_text(raw["universe_definition_id"], field="universe_definition_id"),
            universe_definition_version=_text(raw["universe_definition_version"], field="universe_definition_version"),
            universe_definition_sha256=_sha256(raw["universe_definition_sha256"], field="universe_definition_sha256"),
            universe_manifest_id=_text(raw["universe_manifest_id"], field="universe_manifest_id"),
            universe_manifest_hash=_sha256(raw["universe_manifest_hash"], field="universe_manifest_hash"),
            coverage_scope_id=_text(raw["coverage_scope_id"], field="coverage_scope_id"),
            coverage_scope_version=_text(raw["coverage_scope_version"], field="coverage_scope_version"),
            coverage_scope_sha256=_sha256(raw["coverage_scope_sha256"], field="coverage_scope_sha256"),
            coverage_source_contract_id=_text(raw["coverage_source_contract_id"], field="coverage_source_contract_id"),
            coverage_source_contract_hash=_sha256(raw["coverage_source_contract_hash"], field="coverage_source_contract_hash"),
            coverage_evidence_id=_text(raw["coverage_evidence_id"], field="coverage_evidence_id"),
            coverage_evidence_semantic_hash=_sha256(raw["coverage_evidence_semantic_hash"], field="coverage_evidence_semantic_hash"),
            coverage_evidence_record_hash=_sha256(raw["coverage_evidence_record_hash"], field="coverage_evidence_record_hash"),
            membership_as_of=membership_as_of,
            data_cutoff=data_cutoff,
            frozen_at=frozen_at,
            recorded_at=recorded_at,
            enumeration_complete=True,
            source_reported_row_count=reported_count,
            rows=rows,
            disposition_counts=MappingProxyType(dict(counts)),
            row_snapshot_sha256=row_snapshot,
            coverage_status=expected_status,
            pit_tier="research_pit",
            external_universe_coverage_status="unverified",
            result_ceiling="observed_only",
            paper_live_eligible=False,
            parity_status="contract_only_unwired",
            known_future_leakage=False,
            outcome_blind=True,
            results_accessed=False,
            authority="research_only",
            trade_enabled=False,
            semantic_hash=_sha256(raw["semantic_hash"], field="semantic_hash"),
            record_hash=_sha256(raw["record_hash"], field="record_hash"),
        )
        semantic_payload = obj.to_dict()
        semantic_payload.pop("semantic_hash")
        semantic_payload.pop("record_hash")
        semantic_payload.pop("recorded_at")
        if obj.semantic_hash != canonical_hash(semantic_payload):
            _fail("semantic_hash_mismatch", "coverage snapshot semantic_hash is incorrect")
        record_payload = obj.to_dict()
        record_payload.pop("record_hash")
        if obj.record_hash != canonical_hash(record_payload):
            _fail("record_hash_mismatch", "coverage snapshot record_hash is incorrect")
        return obj

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "coverage_snapshot_id": self.coverage_snapshot_id,
            "universe_id": self.universe_id,
            "universe_definition_id": self.universe_definition_id,
            "universe_definition_version": self.universe_definition_version,
            "universe_definition_sha256": self.universe_definition_sha256,
            "universe_manifest_id": self.universe_manifest_id,
            "universe_manifest_hash": self.universe_manifest_hash,
            "coverage_scope_id": self.coverage_scope_id,
            "coverage_scope_version": self.coverage_scope_version,
            "coverage_scope_sha256": self.coverage_scope_sha256,
            "coverage_source_contract_id": self.coverage_source_contract_id,
            "coverage_source_contract_hash": self.coverage_source_contract_hash,
            "coverage_evidence_id": self.coverage_evidence_id,
            "coverage_evidence_semantic_hash": self.coverage_evidence_semantic_hash,
            "coverage_evidence_record_hash": self.coverage_evidence_record_hash,
            "membership_as_of": self.membership_as_of,
            "data_cutoff": self.data_cutoff,
            "frozen_at": self.frozen_at,
            "recorded_at": self.recorded_at,
            "enumeration_complete": self.enumeration_complete,
            "source_reported_row_count": self.source_reported_row_count,
            "rows": [item.to_dict() for item in self.rows],
            "disposition_counts": dict(self.disposition_counts),
            "row_snapshot_sha256": self.row_snapshot_sha256,
            "coverage_status": self.coverage_status,
            "pit_tier": self.pit_tier,
            "external_universe_coverage_status": self.external_universe_coverage_status,
            "result_ceiling": self.result_ceiling,
            "paper_live_eligible": self.paper_live_eligible,
            "parity_status": self.parity_status,
            "known_future_leakage": self.known_future_leakage,
            "outcome_blind": self.outcome_blind,
            "results_accessed": self.results_accessed,
            "authority": self.authority,
            "trade_enabled": self.trade_enabled,
            "semantic_hash": self.semantic_hash,
            "record_hash": self.record_hash,
        }


def validate_external_universe_coverage_snapshot(
    value: Mapping[str, Any] | ExternalUniverseCoverageSnapshot,
) -> ExternalUniverseCoverageSnapshot:
    return ExternalUniverseCoverageSnapshot.from_dict(
        value.to_dict() if isinstance(value, ExternalUniverseCoverageSnapshot) else value
    )


def normalize_external_universe_coverage_snapshot(
    value: Mapping[str, Any] | ExternalUniverseCoverageSnapshot,
) -> dict[str, Any]:
    return validate_external_universe_coverage_snapshot(value).to_dict()


def _unique_contracts(
    values: Sequence[Mapping[str, Any] | SourceContract],
) -> dict[str, SourceContract]:
    result: dict[str, SourceContract] = {}
    for raw in values:
        contract = _contract_call(validate_source_contract, raw)
        prior = result.get(contract.source_contract_id)
        if prior is not None and prior.source_contract_hash != contract.source_contract_hash:
            _fail("source_contract_id_conflict", "one source contract id has multiple hashes")
        result[contract.source_contract_id] = contract
    return result


def _unique_evidence(
    values: Sequence[Mapping[str, Any] | EvidenceRecord],
) -> dict[str, EvidenceRecord]:
    result: dict[str, EvidenceRecord] = {}
    for raw in values:
        evidence = _contract_call(validate_evidence_record, raw)
        prior = result.get(evidence.evidence_id)
        if prior is not None and (
            prior.semantic_hash != evidence.semantic_hash
            or prior.record_hash != evidence.record_hash
        ):
            _fail("evidence_id_conflict", "one evidence id has multiple records")
        result[evidence.evidence_id] = evidence
    return result


def validate_external_universe_coverage_against_inputs(
    snapshot: Mapping[str, Any] | ExternalUniverseCoverageSnapshot,
    *,
    coverage_evidence: Mapping[str, Any] | EvidenceRecord,
    coverage_source_contract: Mapping[str, Any] | SourceContract,
    mapping_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord] = (),
    mapping_source_contracts: Sequence[Mapping[str, Any] | SourceContract] = (),
) -> dict[str, Any]:
    """Bind one complete source enumeration to exact source and mapping evidence."""

    record = validate_external_universe_coverage_snapshot(snapshot)
    source = _contract_call(validate_source_contract, coverage_source_contract)
    evidence = _contract_call(validate_evidence_against_source, coverage_evidence, source)
    if (
        record.coverage_source_contract_id != source.source_contract_id
        or record.coverage_source_contract_hash != source.source_contract_hash
    ):
        _fail("coverage_source_binding_mismatch", "snapshot does not bind the coverage source")
    if (
        record.coverage_evidence_id != evidence.evidence_id
        or record.coverage_evidence_semantic_hash != evidence.semantic_hash
        or record.coverage_evidence_record_hash != evidence.record_hash
    ):
        _fail("coverage_evidence_binding_mismatch", "snapshot does not bind exact coverage evidence")
    if evidence.security_scope != "not_applicable" or evidence.security_mapping is not None:
        _fail("coverage_evidence_scope_mismatch", "coverage evidence must describe the whole source artifact")
    if _PIT_RANK[evidence.pit_tier] < _PIT_RANK[record.pit_tier]:
        _fail("coverage_pit_tier_exceeded", "coverage snapshot exceeds its evidence PIT tier")
    _, evidence_known_dt = _instant(evidence.known_at, field="coverage_evidence.known_at")
    _, evidence_recorded_dt = _instant(evidence.recorded_at, field="coverage_evidence.recorded_at")
    _, cutoff_dt = _instant(record.data_cutoff, field="data_cutoff")
    _, frozen_dt = _instant(record.frozen_at, field="frozen_at")
    if evidence_known_dt > cutoff_dt or evidence_recorded_dt > frozen_dt:
        _fail("coverage_evidence_after_freeze", "coverage evidence must be known and recorded before freeze")
    required_content = {
        "coverage_scope_id": record.coverage_scope_id,
        "coverage_scope_version": record.coverage_scope_version,
        "coverage_scope_sha256": record.coverage_scope_sha256,
        "enumeration_complete": True,
        "source_reported_row_count": record.source_reported_row_count,
        "source_rows": [
            {"source_row_id": item.source_row_id, "source_row_sha256": item.source_row_sha256}
            for item in record.rows
        ],
    }
    for field, expected in required_content.items():
        if field not in evidence.decision_content or canonical_hash(
            evidence.decision_content[field]
        ) != canonical_hash(expected):
            _fail("coverage_evidence_population_mismatch", f"coverage evidence field {field!r} does not match")

    sources = _unique_contracts(mapping_source_contracts)
    mapping_evidence = _unique_evidence(mapping_evidence_records)
    used_evidence_ids: set[str] = set()
    for row in record.rows:
        if row.security_mapping is None:
            continue
        evidence_id = row.mapping_evidence_id
        if evidence_id is None:  # pragma: no cover - individual row validator prevents this.
            _fail("mapped_row_requires_mapping", "mapping evidence is missing")
        item = mapping_evidence.get(evidence_id)
        if item is None:
            _fail("unresolved_mapping_evidence", f"mapping evidence {evidence_id!r} was not supplied")
        item_source = sources.get(item.source_contract_id)
        if item_source is None:
            _fail("unresolved_mapping_source", f"mapping source {item.source_contract_id!r} was not supplied")
        _contract_call(validate_evidence_against_source, item, item_source)
        if (
            item.semantic_hash != row.mapping_evidence_semantic_hash
            or item.record_hash != row.mapping_evidence_record_hash
            or item.security_mapping is None
            or item.security_mapping.to_dict() != row.security_mapping.to_dict()
        ):
            _fail("mapping_evidence_binding_mismatch", f"row {row.source_row_id!r} changed mapping evidence")
        if _PIT_RANK[item.pit_tier] < _PIT_RANK[record.pit_tier]:
            _fail("mapping_pit_tier_exceeded", "coverage snapshot exceeds mapping evidence PIT tier")
        _, mapping_known_dt = _instant(row.security_mapping.known_at, field="mapping.known_at")
        _, item_known_dt = _instant(item.known_at, field="mapping_evidence.known_at")
        _, item_recorded_dt = _instant(item.recorded_at, field="mapping_evidence.recorded_at")
        if mapping_known_dt > cutoff_dt or item_known_dt > cutoff_dt:
            _fail("mapping_after_cutoff", "mapping and its evidence must be known by data_cutoff")
        if item_recorded_dt > frozen_dt:
            _fail("mapping_after_freeze", "mapping evidence must be recorded before freeze")
        if not row.security_mapping.covers(record.membership_as_of):
            _fail("mapping_interval_miss", "mapping must cover membership_as_of")
        used_evidence_ids.add(evidence_id)

    binding = {
        "coverage_snapshot_id": record.coverage_snapshot_id,
        "coverage_snapshot_record_hash": record.record_hash,
        "coverage_evidence_record_hash": evidence.record_hash,
        "mapping_evidence_record_hashes": [
            mapping_evidence[item].record_hash for item in sorted(used_evidence_ids)
        ],
    }
    return {**binding, "input_binding_sha256": canonical_hash(binding)}


__all__ = [
    "ExternalUniverseCoverageRow",
    "ExternalUniverseCoverageSnapshot",
    "V2UniverseCoverageError",
    "normalize_external_universe_coverage_snapshot",
    "validate_external_universe_coverage_against_inputs",
    "validate_external_universe_coverage_snapshot",
]
