"""Strict, research-only foundation contracts for Ginger V2.

The records in this module describe source authority, point-in-time evidence,
and replayable universe state transitions.  They deliberately perform no file
I/O and have no runtime or order-routing integration.  Every public validator
is fail-closed, every instant requires an explicit timezone, and trading is
always disabled.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SCHEMA_VERSION = 1

PIT_TIERS = frozenset({"not_pit", "research_pit", "canonical_pit"})
_PIT_RANK = {"not_pit": 0, "research_pit": 1, "canonical_pit": 2}
_PASS_STATES = frozenset({"pass", "fail", "unknown"})
_SOURCE_KINDS = frozenset(
    {"official", "vendor", "broker", "internal_observer", "derived"}
)
_REVISION_POLICIES = frozenset(
    {"immutable", "append_only", "versioned", "mutable_current", "unknown"}
)
_MAPPING_POLICIES = frozenset(
    {"effective_dated", "current_only", "not_applicable", "unknown"}
)
_SECURITY_SCOPES = frozenset({"instrument", "not_applicable"})
_MAPPING_KINDS = frozenset(
    {"effective_dated", "current_only", "not_applicable"}
)
_UNIVERSE_EVENT_TYPES = frozenset({"discovery", "state_transition"})
_UNIVERSE_STATES = frozenset(
    {"discovered", "research_eligible", "candidate_eligible", "quarantine", "retired"}
)
_ALLOWED_TRANSITIONS = {
    "discovered": frozenset({"research_eligible", "quarantine", "retired"}),
    "research_eligible": frozenset(
        {"candidate_eligible", "quarantine", "retired"}
    ),
    "candidate_eligible": frozenset(
        {"research_eligible", "quarantine", "retired"}
    ),
    "quarantine": frozenset({"research_eligible", "retired"}),
    "retired": frozenset(),
}


class V2ContractValidationError(ValueError):
    """Fail-closed validation error with a stable machine-readable code."""

    def __init__(self, code: str, path: str, message: str):
        self.code = str(code)
        self.path = str(path)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.path}: {self.detail}")

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.detail}


def _fail(code: str, path: str, message: str) -> None:
    raise V2ContractValidationError(code, path, message)


def _plain(value: Any, *, path: str = "$") -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _plain(value.to_dict(), path=path)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _fail("string_key_required", path, "all object keys must be strings")
            result[key] = _plain(item, path=f"{path}.{key}")
        return result
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [
            _plain(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("invalid_json_value", path, "non-finite numbers are forbidden")
        return value
    _fail("invalid_json_value", path, f"unsupported JSON value {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return deterministic JSON, rejecting non-JSON and non-finite values."""

    return json.dumps(
        _plain(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_hash(value: Any) -> str:
    """Return the full SHA-256 digest of canonical JSON."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("mapping_required", path, "must be an object")
    for key in value:
        if not isinstance(key, str):
            _fail("string_key_required", path, "all object keys must be strings")
    return value


def _check_fields(
    value: Mapping[str, Any],
    *,
    required: Iterable[str],
    optional: Iterable[str] = (),
    path: str,
) -> None:
    required_set = frozenset(required)
    allowed = required_set | frozenset(optional)
    missing = sorted(required_set - set(value))
    if missing:
        _fail("missing_field", path, f"missing required fields: {', '.join(missing)}")
    unknown = sorted(set(value) - allowed)
    if unknown:
        _fail("unknown_field", path, f"unknown fields: {', '.join(unknown)}")


def _text(value: Any, *, path: str) -> str:
    if not isinstance(value, str):
        _fail("string_required", path, "must be a string")
    result = value.strip()
    if not result:
        _fail("empty_string", path, "must not be empty")
    return result


def _optional_text(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    return _text(value, path=path)


def _enum(value: Any, *, allowed: frozenset[str], path: str) -> str:
    result = _text(value, path=path).lower()
    if result not in allowed:
        _fail("invalid_enum", path, f"must be one of {', '.join(sorted(allowed))}")
    return result


def _boolean(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        _fail("boolean_required", path, "must be a boolean")
    return value


def _schema_version(value: Any, *, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail("integer_required", path, "must be an integer")
    if value != SCHEMA_VERSION:
        _fail("unsupported_schema_version", path, f"must equal {SCHEMA_VERSION}")
    return value


def _record_type(value: Any, *, expected: str, path: str) -> str:
    result = _text(value, path=path)
    if result != expected:
        _fail("invalid_record_type", path, f"must equal {expected}")
    return result


def _sha256(value: Any, *, path: str) -> str:
    result = _text(value, path=path).lower()
    if re.fullmatch(r"[0-9a-f]{64}", result) is None:
        _fail("invalid_sha256", path, "must be a lowercase 64-character SHA-256")
    return result


def _optional_sha256(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    return _sha256(value, path=path)


def _instant(value: Any, *, path: str) -> tuple[str, datetime]:
    if not isinstance(value, str):
        _fail("timestamp_string_required", path, "must be an ISO timestamp string")
    text = value.strip()
    if not text or re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        _fail("instant_required", path, "date-only values are forbidden")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise V2ContractValidationError(
            "invalid_timestamp", path, "must be a valid ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("timezone_required", path, "must include an explicit timezone")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _optional_instant(value: Any, *, path: str) -> tuple[str | None, datetime | None]:
    if value is None:
        return None, None
    return _instant(value, path=path)


def _calendar_date(value: Any, *, path: str) -> str:
    if not isinstance(value, str):
        _fail("date_string_required", path, "must be a YYYY-MM-DD string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise V2ContractValidationError(
            "invalid_date", path, "must be a valid YYYY-MM-DD date"
        ) from exc
    if parsed.isoformat() != value:
        _fail("invalid_date", path, "must use canonical YYYY-MM-DD form")
    return value


def _timezone_name(value: Any, *, path: str) -> str:
    result = _text(value, path=path)
    try:
        ZoneInfo(result)
    except ZoneInfoNotFoundError as exc:
        raise V2ContractValidationError(
            "invalid_timezone", path, "must be a valid IANA timezone name"
        ) from exc
    return result


def _string_tuple(value: Any, *, path: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list of strings")
    values = [_text(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if not values:
        _fail("nonempty_list_required", path, "must contain at least one value")
    if len(values) != len(set(values)):
        _fail("duplicate_list_value", path, "must not contain duplicate values")
    return tuple(sorted(values))


def _frozen_object(value: Any, *, path: str) -> Mapping[str, Any]:
    raw = _mapping(value, path=path)
    if not raw:
        _fail("nonempty_object_required", path, "must contain at least one field")
    frozen = _freeze_json(raw, path=path)
    assert isinstance(frozen, Mapping)
    return frozen


def _freeze_json(value: Any, *, path: str) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _fail("string_key_required", path, "all object keys must be strings")
            result[key] = _freeze_json(item, path=f"{path}.{key}")
        return MappingProxyType(result)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(
            _freeze_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    _fail("invalid_json_value", path, "must contain finite JSON values only")


def _require_default_off(value: Any, *, path: str) -> bool:
    enabled = _boolean(value, path=path)
    if enabled:
        _fail("trade_enabled_forbidden", path, "V2 contracts must remain default-off")
    return False


def _check_self_hash(
    value: Mapping[str, Any], *, hash_field: str, supplied: str, path: str
) -> None:
    payload = dict(_plain(value))
    payload.pop(hash_field, None)
    expected = canonical_hash(payload)
    if supplied != expected:
        _fail("hash_mismatch", path, f"expected {expected}, got {supplied}")


@dataclass(frozen=True, slots=True)
class SecurityMappingSnapshot:
    mapping_id: str
    security_id: str
    listing_id: str
    symbol: str
    mic: str
    effective_from: str
    effective_to: str | None
    known_at: str
    source_snapshot_sha256: str
    mapping_sha256: str

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, path: str = "$.security_mapping"
    ) -> "SecurityMappingSnapshot":
        raw = _mapping(value, path=path)
        _check_fields(
            raw,
            required={
                "mapping_id",
                "security_id",
                "listing_id",
                "symbol",
                "mic",
                "effective_from",
                "effective_to",
                "known_at",
                "source_snapshot_sha256",
                "mapping_sha256",
            },
            path=path,
        )
        effective_from, effective_from_dt = _instant(
            raw["effective_from"], path=f"{path}.effective_from"
        )
        effective_to, effective_to_dt = _optional_instant(
            raw["effective_to"], path=f"{path}.effective_to"
        )
        if effective_to_dt is not None and effective_to_dt <= effective_from_dt:
            _fail(
                "invalid_effective_interval",
                f"{path}.effective_to",
                "must be later than effective_from",
            )
        known_at, _ = _instant(raw["known_at"], path=f"{path}.known_at")
        obj = cls(
            mapping_id=_text(raw["mapping_id"], path=f"{path}.mapping_id"),
            security_id=_text(raw["security_id"], path=f"{path}.security_id"),
            listing_id=_text(raw["listing_id"], path=f"{path}.listing_id"),
            symbol=_text(raw["symbol"], path=f"{path}.symbol"),
            mic=_text(raw["mic"], path=f"{path}.mic"),
            effective_from=effective_from,
            effective_to=effective_to,
            known_at=known_at,
            source_snapshot_sha256=_sha256(
                raw["source_snapshot_sha256"], path=f"{path}.source_snapshot_sha256"
            ),
            mapping_sha256=_sha256(
                raw["mapping_sha256"], path=f"{path}.mapping_sha256"
            ),
        )
        _check_self_hash(
            obj.to_dict(),
            hash_field="mapping_sha256",
            supplied=obj.mapping_sha256,
            path=f"{path}.mapping_sha256",
        )
        return obj

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "security_id": self.security_id,
            "listing_id": self.listing_id,
            "symbol": self.symbol,
            "mic": self.mic,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "known_at": self.known_at,
            "source_snapshot_sha256": self.source_snapshot_sha256,
            "mapping_sha256": self.mapping_sha256,
        }

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def covers(self, instant: str) -> bool:
        _, target = _instant(instant, path="$.instant")
        _, start = _instant(self.effective_from, path="$.effective_from")
        _, end = _optional_instant(self.effective_to, path="$.effective_to")
        return target >= start and (end is None or target < end)


@dataclass(frozen=True, slots=True)
class SourceContract:
    schema_version: int
    record_type: str
    source_contract_id: str
    contract_version: str
    provider: str
    source_name: str
    source_kind: str
    source_locator: str
    raw_identity_fields: tuple[str, ...]
    decision_content_fields: tuple[str, ...]
    authorization_status: str
    authorization_reference: str
    authorization_evidence_sha256: str | None
    permitted_uses: tuple[str, ...]
    availability_status: str
    availability_reference: str
    source_timezone: str
    observed_at_rule: str
    published_at_rule: str
    published_at_field: str | None
    known_at_rule: str
    decision_calendar: str
    session_assignment_rule: str
    revision_policy: str
    revision_id_field: str
    security_mapping_policy: str
    normalizer_id: str
    normalizer_version: str
    adjustment_policy: str
    replay_daily_parity_status: str
    maximum_pit_tier: str
    known_future_leakage: bool
    effective_from: str
    effective_to: str | None
    created_at: str
    trade_enabled: bool
    source_contract_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceContract":
        path = "$"
        raw = _mapping(value, path=path)
        fields = set(cls.__dataclass_fields__)
        _check_fields(raw, required=fields, path=path)
        created_at, created_at_dt = _instant(raw["created_at"], path="$.created_at")
        effective_from, effective_from_dt = _instant(
            raw["effective_from"], path="$.effective_from"
        )
        effective_to, effective_to_dt = _optional_instant(
            raw["effective_to"], path="$.effective_to"
        )
        maximum_pit_tier = _enum(
            raw["maximum_pit_tier"], allowed=PIT_TIERS, path="$.maximum_pit_tier"
        )
        if maximum_pit_tier == "canonical_pit" and effective_from_dt < created_at_dt:
            _fail(
                "retroactive_contract_start",
                "$.effective_from",
                "canonical source contracts must not predate created_at",
            )
        if effective_to_dt is not None and effective_to_dt <= effective_from_dt:
            _fail(
                "invalid_effective_interval",
                "$.effective_to",
                "must be later than effective_from",
            )
        authorization_status = _enum(
            raw["authorization_status"],
            allowed=_PASS_STATES,
            path="$.authorization_status",
        )
        availability_status = _enum(
            raw["availability_status"],
            allowed=_PASS_STATES,
            path="$.availability_status",
        )
        revision_policy = _enum(
            raw["revision_policy"],
            allowed=_REVISION_POLICIES,
            path="$.revision_policy",
        )
        mapping_policy = _enum(
            raw["security_mapping_policy"],
            allowed=_MAPPING_POLICIES,
            path="$.security_mapping_policy",
        )
        parity_status = _enum(
            raw["replay_daily_parity_status"],
            allowed=_PASS_STATES,
            path="$.replay_daily_parity_status",
        )
        leakage = _boolean(raw["known_future_leakage"], path="$.known_future_leakage")
        authorization_hash = _optional_sha256(
            raw["authorization_evidence_sha256"],
            path="$.authorization_evidence_sha256",
        )
        permitted_uses = _string_tuple(raw["permitted_uses"], path="$.permitted_uses")
        raw_identity_fields = _string_tuple(
            raw["raw_identity_fields"], path="$.raw_identity_fields"
        )
        decision_content_fields = _string_tuple(
            raw["decision_content_fields"], path="$.decision_content_fields"
        )
        published_at_field = _optional_text(
            raw["published_at_field"], path="$.published_at_field"
        )
        revision_id_field = _text(
            raw["revision_id_field"], path="$.revision_id_field"
        )
        if (
            published_at_field is not None
            and published_at_field not in decision_content_fields
        ):
            _fail(
                "published_field_not_declared",
                "$.published_at_field",
                "must name a field in decision_content_fields",
            )
        if revision_id_field not in raw_identity_fields:
            _fail(
                "revision_field_not_declared",
                "$.revision_id_field",
                "must name a field in raw_identity_fields",
            )
        if maximum_pit_tier != "not_pit":
            if authorization_status != "pass" or authorization_hash is None:
                _fail(
                    "authorization_not_verified",
                    "$.authorization_status",
                    "research/canonical PIT requires hashed authorization evidence",
                )
            if availability_status != "pass":
                _fail(
                    "availability_not_verified",
                    "$.availability_status",
                    "research/canonical PIT requires verified availability",
                )
            if "research" not in permitted_uses:
                _fail(
                    "research_use_not_authorized",
                    "$.permitted_uses",
                    "research/canonical PIT requires the research use",
                )
            if leakage:
                _fail(
                    "future_leakage_requires_not_pit",
                    "$.known_future_leakage",
                    "known future leakage is only valid with not_pit",
                )
            if mapping_policy not in {"effective_dated", "not_applicable"}:
                _fail(
                    "current_mapping_requires_not_pit",
                    "$.security_mapping_policy",
                    "research/canonical PIT forbids current or unknown mappings",
                )
        if maximum_pit_tier == "canonical_pit":
            if revision_policy not in {"immutable", "append_only", "versioned"}:
                _fail(
                    "canonical_revision_policy_required",
                    "$.revision_policy",
                    "canonical PIT requires immutable, append-only, or versioned data",
                )
            if parity_status != "pass":
                _fail(
                    "canonical_parity_required",
                    "$.replay_daily_parity_status",
                    "canonical PIT requires replay/daily parity",
                )
        obj = cls(
            schema_version=_schema_version(raw["schema_version"], path="$.schema_version"),
            record_type=_record_type(
                raw["record_type"], expected="v2_source_contract", path="$.record_type"
            ),
            source_contract_id=_text(raw["source_contract_id"], path="$.source_contract_id"),
            contract_version=_text(raw["contract_version"], path="$.contract_version"),
            provider=_text(raw["provider"], path="$.provider"),
            source_name=_text(raw["source_name"], path="$.source_name"),
            source_kind=_enum(raw["source_kind"], allowed=_SOURCE_KINDS, path="$.source_kind"),
            source_locator=_text(raw["source_locator"], path="$.source_locator"),
            raw_identity_fields=raw_identity_fields,
            decision_content_fields=decision_content_fields,
            authorization_status=authorization_status,
            authorization_reference=_text(
                raw["authorization_reference"], path="$.authorization_reference"
            ),
            authorization_evidence_sha256=authorization_hash,
            permitted_uses=permitted_uses,
            availability_status=availability_status,
            availability_reference=_text(
                raw["availability_reference"], path="$.availability_reference"
            ),
            source_timezone=_timezone_name(raw["source_timezone"], path="$.source_timezone"),
            observed_at_rule=_text(raw["observed_at_rule"], path="$.observed_at_rule"),
            published_at_rule=_text(raw["published_at_rule"], path="$.published_at_rule"),
            published_at_field=published_at_field,
            known_at_rule=_text(raw["known_at_rule"], path="$.known_at_rule"),
            decision_calendar=_text(raw["decision_calendar"], path="$.decision_calendar"),
            session_assignment_rule=_text(
                raw["session_assignment_rule"], path="$.session_assignment_rule"
            ),
            revision_policy=revision_policy,
            revision_id_field=revision_id_field,
            security_mapping_policy=mapping_policy,
            normalizer_id=_text(raw["normalizer_id"], path="$.normalizer_id"),
            normalizer_version=_text(raw["normalizer_version"], path="$.normalizer_version"),
            adjustment_policy=_text(raw["adjustment_policy"], path="$.adjustment_policy"),
            replay_daily_parity_status=parity_status,
            maximum_pit_tier=maximum_pit_tier,
            known_future_leakage=leakage,
            effective_from=effective_from,
            effective_to=effective_to,
            created_at=created_at,
            trade_enabled=_require_default_off(raw["trade_enabled"], path="$.trade_enabled"),
            source_contract_hash=_sha256(
                raw["source_contract_hash"], path="$.source_contract_hash"
            ),
        )
        _check_self_hash(
            obj.to_dict(),
            hash_field="source_contract_hash",
            supplied=obj.source_contract_hash,
            path="$.source_contract_hash",
        )
        return obj

    def to_dict(self) -> dict[str, Any]:
        return {
            field: _plain(getattr(self, field))
            for field in self.__dataclass_fields__
        }

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    schema_version: int
    record_type: str
    evidence_id: str
    source_contract_id: str
    source_contract_hash: str
    raw_identity: Mapping[str, Any]
    raw_artifact_locator: str
    raw_artifact_sha256: str
    decision_content: Mapping[str, Any]
    decision_content_sha256: str
    normalizer_id: str
    normalizer_version: str
    source_timezone: str
    observed_at: str
    published_at: str | None
    known_at: str
    known_at_basis: str
    effective_from: str
    effective_to: str | None
    revision_id: str
    supersedes_evidence_id: str | None
    security_scope: str
    security_mapping_kind: str
    security_mapping: SecurityMappingSnapshot | None
    authorization_status: str
    authorization_evidence_sha256: str | None
    pit_tier: str
    known_future_leakage: bool
    recorded_at: str
    trade_enabled: bool
    semantic_hash: str
    record_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceRecord":
        path = "$"
        raw = _mapping(value, path=path)
        _check_fields(raw, required=set(cls.__dataclass_fields__), path=path)
        observed_at, observed_dt = _instant(raw["observed_at"], path="$.observed_at")
        published_at, published_dt = _optional_instant(
            raw["published_at"], path="$.published_at"
        )
        known_at, known_dt = _instant(raw["known_at"], path="$.known_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], path="$.recorded_at")
        effective_from, effective_from_dt = _instant(
            raw["effective_from"], path="$.effective_from"
        )
        effective_to, effective_to_dt = _optional_instant(
            raw["effective_to"], path="$.effective_to"
        )
        if observed_dt > known_dt or (published_dt is not None and published_dt > known_dt):
            _fail(
                "known_at_before_source_clock",
                "$.known_at",
                "must be at or after observed_at and published_at",
            )
        if known_dt > recorded_dt:
            _fail("recorded_before_known", "$.recorded_at", "must be at or after known_at")
        if effective_to_dt is not None and effective_to_dt <= effective_from_dt:
            _fail(
                "invalid_effective_interval",
                "$.effective_to",
                "must be later than effective_from",
            )
        decision_content = _frozen_object(raw["decision_content"], path="$.decision_content")
        decision_hash = _sha256(
            raw["decision_content_sha256"], path="$.decision_content_sha256"
        )
        expected_decision_hash = canonical_hash(decision_content)
        if decision_hash != expected_decision_hash:
            _fail(
                "decision_content_hash_mismatch",
                "$.decision_content_sha256",
                f"expected {expected_decision_hash}, got {decision_hash}",
            )
        pit_tier = _enum(raw["pit_tier"], allowed=PIT_TIERS, path="$.pit_tier")
        authorization_status = _enum(
            raw["authorization_status"],
            allowed=_PASS_STATES,
            path="$.authorization_status",
        )
        authorization_hash = _optional_sha256(
            raw["authorization_evidence_sha256"],
            path="$.authorization_evidence_sha256",
        )
        leakage = _boolean(raw["known_future_leakage"], path="$.known_future_leakage")
        security_scope = _enum(
            raw["security_scope"], allowed=_SECURITY_SCOPES, path="$.security_scope"
        )
        mapping_kind = _enum(
            raw["security_mapping_kind"],
            allowed=_MAPPING_KINDS,
            path="$.security_mapping_kind",
        )
        mapping_raw = raw["security_mapping"]
        mapping = (
            None
            if mapping_raw is None
            else SecurityMappingSnapshot.from_dict(mapping_raw, path="$.security_mapping")
        )
        if security_scope == "not_applicable":
            if mapping_kind != "not_applicable" or mapping is not None:
                _fail(
                    "mapping_scope_mismatch",
                    "$.security_mapping_kind",
                    "non-security evidence must explicitly use not_applicable",
                )
        else:
            if mapping_kind == "effective_dated" and mapping is None:
                _fail(
                    "security_mapping_required",
                    "$.security_mapping",
                    "effective-dated instrument evidence requires a mapping snapshot",
                )
            if mapping_kind == "not_applicable":
                _fail(
                    "mapping_scope_mismatch",
                    "$.security_mapping_kind",
                    "instrument evidence cannot use not_applicable",
                )
            if mapping_kind == "current_only" and mapping is not None:
                _fail(
                    "current_mapping_snapshot_forbidden",
                    "$.security_mapping",
                    "current-only mappings cannot masquerade as effective snapshots",
                )
        if mapping is not None:
            _, mapping_known_dt = _instant(mapping.known_at, path="$.security_mapping.known_at")
            if mapping_known_dt > known_dt:
                _fail(
                    "mapping_known_too_late",
                    "$.security_mapping.known_at",
                    "mapping must be known by evidence known_at",
                )
            if not mapping.covers(known_at):
                _fail(
                    "mapping_interval_miss",
                    "$.security_mapping",
                    "mapping effective interval must cover evidence known_at",
                )
        if pit_tier != "not_pit":
            if authorization_status != "pass" or authorization_hash is None:
                _fail(
                    "authorization_not_verified",
                    "$.authorization_status",
                    "research/canonical evidence requires hashed authorization evidence",
                )
            if leakage:
                _fail(
                    "future_leakage_requires_not_pit",
                    "$.known_future_leakage",
                    "known future leakage is only valid with not_pit",
                )
            if mapping_kind == "current_only":
                _fail(
                    "current_mapping_requires_not_pit",
                    "$.security_mapping_kind",
                    "current mappings cannot support PIT evidence",
                )
        obj = cls(
            schema_version=_schema_version(raw["schema_version"], path="$.schema_version"),
            record_type=_record_type(
                raw["record_type"], expected="v2_evidence_record", path="$.record_type"
            ),
            evidence_id=_text(raw["evidence_id"], path="$.evidence_id"),
            source_contract_id=_text(
                raw["source_contract_id"], path="$.source_contract_id"
            ),
            source_contract_hash=_sha256(
                raw["source_contract_hash"], path="$.source_contract_hash"
            ),
            raw_identity=_frozen_object(raw["raw_identity"], path="$.raw_identity"),
            raw_artifact_locator=_text(
                raw["raw_artifact_locator"], path="$.raw_artifact_locator"
            ),
            raw_artifact_sha256=_sha256(
                raw["raw_artifact_sha256"], path="$.raw_artifact_sha256"
            ),
            decision_content=decision_content,
            decision_content_sha256=decision_hash,
            normalizer_id=_text(raw["normalizer_id"], path="$.normalizer_id"),
            normalizer_version=_text(raw["normalizer_version"], path="$.normalizer_version"),
            source_timezone=_timezone_name(raw["source_timezone"], path="$.source_timezone"),
            observed_at=observed_at,
            published_at=published_at,
            known_at=known_at,
            known_at_basis=_text(raw["known_at_basis"], path="$.known_at_basis"),
            effective_from=effective_from,
            effective_to=effective_to,
            revision_id=_text(raw["revision_id"], path="$.revision_id"),
            supersedes_evidence_id=_optional_text(
                raw["supersedes_evidence_id"], path="$.supersedes_evidence_id"
            ),
            security_scope=security_scope,
            security_mapping_kind=mapping_kind,
            security_mapping=mapping,
            authorization_status=authorization_status,
            authorization_evidence_sha256=authorization_hash,
            pit_tier=pit_tier,
            known_future_leakage=leakage,
            recorded_at=recorded_at,
            trade_enabled=_require_default_off(raw["trade_enabled"], path="$.trade_enabled"),
            semantic_hash=_sha256(raw["semantic_hash"], path="$.semantic_hash"),
            record_hash=_sha256(raw["record_hash"], path="$.record_hash"),
        )
        semantic_payload = obj.to_dict()
        semantic_payload.pop("semantic_hash")
        semantic_payload.pop("record_hash")
        semantic_payload.pop("recorded_at")
        expected_semantic_hash = canonical_hash(semantic_payload)
        if obj.semantic_hash != expected_semantic_hash:
            _fail(
                "semantic_hash_mismatch",
                "$.semantic_hash",
                f"expected {expected_semantic_hash}, got {obj.semantic_hash}",
            )
        _check_self_hash(
            obj.to_dict(),
            hash_field="record_hash",
            supplied=obj.record_hash,
            path="$.record_hash",
        )
        return obj

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in self.__dataclass_fields__:
            value = getattr(self, field)
            if field == "security_mapping":
                result[field] = None if value is None else value.to_dict()
            else:
                result[field] = _plain(value)
        return result

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class UniverseEvent:
    schema_version: int
    record_type: str
    event_id: str
    event_batch_id: str
    universe_id: str
    event_type: str
    from_state: str | None
    to_state: str
    security_mapping: SecurityMappingSnapshot
    reason_code: str
    reason: str
    rule_id: str
    rule_version: str
    rule_sha256: str
    evidence_record_ids: tuple[str, ...]
    input_snapshot_sha256: str
    pit_tier: str
    known_future_leakage: bool
    run_id: str
    run_date: str
    calendar_session_id: str
    known_at: str
    decided_at: str
    recorded_at: str
    effective_at: str
    effective_session_id: str
    previous_event_id: str | None
    previous_event_hash: str | None
    trade_enabled: bool
    semantic_hash: str
    event_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "UniverseEvent":
        path = "$"
        raw = _mapping(value, path=path)
        _check_fields(raw, required=set(cls.__dataclass_fields__), path=path)
        event_type = _enum(
            raw["event_type"], allowed=_UNIVERSE_EVENT_TYPES, path="$.event_type"
        )
        from_state = (
            None
            if raw["from_state"] is None
            else _enum(raw["from_state"], allowed=_UNIVERSE_STATES, path="$.from_state")
        )
        to_state = _enum(raw["to_state"], allowed=_UNIVERSE_STATES, path="$.to_state")
        previous_event_id = _optional_text(
            raw["previous_event_id"], path="$.previous_event_id"
        )
        previous_event_hash = _optional_sha256(
            raw["previous_event_hash"], path="$.previous_event_hash"
        )
        if event_type == "discovery":
            if from_state is not None or to_state != "discovered":
                _fail(
                    "invalid_discovery_transition",
                    "$.to_state",
                    "discovery must transition from null to discovered",
                )
            if previous_event_id is not None or previous_event_hash is not None:
                _fail(
                    "discovery_previous_event_forbidden",
                    "$.previous_event_id",
                    "first discovery cannot reference a previous event",
                )
        else:
            if from_state is None:
                _fail(
                    "from_state_required",
                    "$.from_state",
                    "state_transition requires a prior state",
                )
            if previous_event_id is None or previous_event_hash is None:
                _fail(
                    "previous_event_required",
                    "$.previous_event_id",
                    "state_transition requires previous event id and hash",
                )
            if to_state not in _ALLOWED_TRANSITIONS[from_state]:
                _fail(
                    "invalid_universe_transition",
                    "$.to_state",
                    f"{from_state} cannot transition to {to_state}",
                )
        known_at, known_dt = _instant(raw["known_at"], path="$.known_at")
        decided_at, decided_dt = _instant(raw["decided_at"], path="$.decided_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], path="$.recorded_at")
        effective_at, effective_dt = _instant(raw["effective_at"], path="$.effective_at")
        if not (known_dt <= decided_dt <= recorded_dt <= effective_dt):
            _fail(
                "invalid_event_chronology",
                "$.known_at",
                "must satisfy known_at <= decided_at <= recorded_at <= effective_at",
            )
        mapping = SecurityMappingSnapshot.from_dict(
            raw["security_mapping"], path="$.security_mapping"
        )
        _, mapping_known_dt = _instant(mapping.known_at, path="$.security_mapping.known_at")
        if mapping_known_dt > known_dt:
            _fail(
                "mapping_known_too_late",
                "$.security_mapping.known_at",
                "mapping must be known by event known_at",
            )
        if not mapping.covers(effective_at):
            _fail(
                "mapping_interval_miss",
                "$.security_mapping",
                "mapping effective interval must cover effective_at",
            )
        pit_tier = _enum(raw["pit_tier"], allowed=PIT_TIERS, path="$.pit_tier")
        leakage = _boolean(raw["known_future_leakage"], path="$.known_future_leakage")
        if pit_tier != "not_pit" and leakage:
            _fail(
                "future_leakage_requires_not_pit",
                "$.known_future_leakage",
                "known future leakage is only valid with not_pit",
            )
        obj = cls(
            schema_version=_schema_version(raw["schema_version"], path="$.schema_version"),
            record_type=_record_type(
                raw["record_type"], expected="v2_universe_event", path="$.record_type"
            ),
            event_id=_text(raw["event_id"], path="$.event_id"),
            event_batch_id=_text(raw["event_batch_id"], path="$.event_batch_id"),
            universe_id=_text(raw["universe_id"], path="$.universe_id"),
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            security_mapping=mapping,
            reason_code=_text(raw["reason_code"], path="$.reason_code"),
            reason=_text(raw["reason"], path="$.reason"),
            rule_id=_text(raw["rule_id"], path="$.rule_id"),
            rule_version=_text(raw["rule_version"], path="$.rule_version"),
            rule_sha256=_sha256(raw["rule_sha256"], path="$.rule_sha256"),
            evidence_record_ids=_string_tuple(
                raw["evidence_record_ids"], path="$.evidence_record_ids"
            ),
            input_snapshot_sha256=_sha256(
                raw["input_snapshot_sha256"], path="$.input_snapshot_sha256"
            ),
            pit_tier=pit_tier,
            known_future_leakage=leakage,
            run_id=_text(raw["run_id"], path="$.run_id"),
            run_date=_calendar_date(raw["run_date"], path="$.run_date"),
            calendar_session_id=_text(
                raw["calendar_session_id"], path="$.calendar_session_id"
            ),
            known_at=known_at,
            decided_at=decided_at,
            recorded_at=recorded_at,
            effective_at=effective_at,
            effective_session_id=_text(
                raw["effective_session_id"], path="$.effective_session_id"
            ),
            previous_event_id=previous_event_id,
            previous_event_hash=previous_event_hash,
            trade_enabled=_require_default_off(raw["trade_enabled"], path="$.trade_enabled"),
            semantic_hash=_sha256(raw["semantic_hash"], path="$.semantic_hash"),
            event_hash=_sha256(raw["event_hash"], path="$.event_hash"),
        )
        semantic_payload = obj.to_dict()
        semantic_payload.pop("semantic_hash")
        semantic_payload.pop("event_hash")
        semantic_payload.pop("recorded_at")
        expected_semantic_hash = canonical_hash(semantic_payload)
        if obj.semantic_hash != expected_semantic_hash:
            _fail(
                "semantic_hash_mismatch",
                "$.semantic_hash",
                f"expected {expected_semantic_hash}, got {obj.semantic_hash}",
            )
        _check_self_hash(
            obj.to_dict(),
            hash_field="event_hash",
            supplied=obj.event_hash,
            path="$.event_hash",
        )
        return obj

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in self.__dataclass_fields__:
            value = getattr(self, field)
            if field == "security_mapping":
                result[field] = value.to_dict()
            else:
                result[field] = _plain(value)
        return result

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())


def validate_source_contract(value: Mapping[str, Any] | SourceContract) -> SourceContract:
    return SourceContract.from_dict(value.to_dict() if isinstance(value, SourceContract) else value)


def normalize_source_contract(value: Mapping[str, Any] | SourceContract) -> dict[str, Any]:
    return validate_source_contract(value).to_dict()


def validate_evidence_record(value: Mapping[str, Any] | EvidenceRecord) -> EvidenceRecord:
    return EvidenceRecord.from_dict(value.to_dict() if isinstance(value, EvidenceRecord) else value)


def normalize_evidence_record(value: Mapping[str, Any] | EvidenceRecord) -> dict[str, Any]:
    return validate_evidence_record(value).to_dict()


def validate_evidence_against_source(
    evidence: Mapping[str, Any] | EvidenceRecord,
    source_contract: Mapping[str, Any] | SourceContract,
) -> EvidenceRecord:
    record = validate_evidence_record(evidence)
    contract = validate_source_contract(source_contract)
    if record.source_contract_id != contract.source_contract_id:
        _fail(
            "source_contract_id_mismatch",
            "$.source_contract_id",
            "does not match the supplied source contract",
        )
    if record.source_contract_hash != contract.source_contract_hash:
        _fail(
            "source_contract_hash_mismatch",
            "$.source_contract_hash",
            "does not bind the supplied source contract",
        )
    if record.source_timezone != contract.source_timezone:
        _fail(
            "source_timezone_mismatch",
            "$.source_timezone",
            "does not match the supplied source contract",
        )
    if (record.normalizer_id, record.normalizer_version) != (
        contract.normalizer_id,
        contract.normalizer_version,
    ):
        _fail(
            "normalizer_mismatch",
            "$.normalizer_id",
            "does not match the supplied source contract",
        )
    if set(record.raw_identity) != set(contract.raw_identity_fields):
        _fail(
            "raw_identity_fields_mismatch",
            "$.raw_identity",
            "fields must exactly match source_contract.raw_identity_fields",
        )
    if set(record.decision_content) != set(contract.decision_content_fields):
        _fail(
            "decision_content_fields_mismatch",
            "$.decision_content",
            "fields must exactly match source_contract.decision_content_fields",
        )
    raw_revision = _text(
        record.raw_identity[contract.revision_id_field],
        path=f"$.raw_identity.{contract.revision_id_field}",
    )
    if raw_revision != record.revision_id:
        _fail(
            "revision_id_mismatch",
            "$.revision_id",
            "must equal the source-declared raw identity revision field",
        )
    if contract.published_at_field is None:
        if record.published_at is not None:
            _fail(
                "published_at_not_declared",
                "$.published_at",
                "must be null when the source contract declares no published field",
            )
    else:
        content_published_at, _ = _instant(
            record.decision_content[contract.published_at_field],
            path=f"$.decision_content.{contract.published_at_field}",
        )
        if record.published_at != content_published_at:
            _fail(
                "published_at_mismatch",
                "$.published_at",
                "must equal the source-declared decision content timestamp",
            )
    if (
        record.authorization_status != contract.authorization_status
        or record.authorization_evidence_sha256
        != contract.authorization_evidence_sha256
    ):
        _fail(
            "authorization_binding_mismatch",
            "$.authorization_status",
            "does not bind the source authorization snapshot",
        )
    _, known_dt = _instant(record.known_at, path="$.known_at")
    _, evidence_recorded_dt = _instant(record.recorded_at, path="$.recorded_at")
    _, contract_created_dt = _instant(contract.created_at, path="$.source.created_at")
    if evidence_recorded_dt < contract_created_dt:
        _fail(
            "evidence_recorded_before_contract",
            "$.recorded_at",
            "a record cannot bind a source contract before that contract exists",
        )
    _, contract_start = _instant(contract.effective_from, path="$.source.effective_from")
    _, contract_end = _optional_instant(
        contract.effective_to, path="$.source.effective_to"
    )
    if known_dt < contract_start or (contract_end is not None and known_dt >= contract_end):
        _fail(
            "source_contract_interval_miss",
            "$.known_at",
            "evidence known_at is outside the source contract interval",
        )
    if _PIT_RANK[record.pit_tier] > _PIT_RANK[contract.maximum_pit_tier]:
        _fail(
            "pit_tier_exceeds_source",
            "$.pit_tier",
            "evidence tier exceeds the source contract maximum",
        )
    expected_mapping_kind = {
        "effective_dated": "effective_dated",
        "current_only": "current_only",
        "not_applicable": "not_applicable",
        "unknown": "current_only",
    }[contract.security_mapping_policy]
    if record.security_mapping_kind != expected_mapping_kind:
        _fail(
            "mapping_policy_mismatch",
            "$.security_mapping_kind",
            "does not match the supplied source contract",
        )
    return record


def validate_universe_event(value: Mapping[str, Any] | UniverseEvent) -> UniverseEvent:
    return UniverseEvent.from_dict(value.to_dict() if isinstance(value, UniverseEvent) else value)


def normalize_universe_event(value: Mapping[str, Any] | UniverseEvent) -> dict[str, Any]:
    return validate_universe_event(value).to_dict()


def universe_input_snapshot_hash(
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    *,
    rule_sha256: str,
    security_mapping_sha256: str,
) -> str:
    records = [validate_evidence_record(record) for record in evidence_records]
    ids = [record.evidence_id for record in records]
    if len(ids) != len(set(ids)):
        _fail("duplicate_evidence_id", "$.evidence_records", "evidence ids must be unique")
    return canonical_hash(
        {
            "evidence_records": [
                {
                    "evidence_id": record.evidence_id,
                    "semantic_hash": record.semantic_hash,
                }
                for record in sorted(records, key=lambda item: item.evidence_id)
            ],
            "rule_sha256": _sha256(rule_sha256, path="$.rule_sha256"),
            "security_mapping_sha256": _sha256(
                security_mapping_sha256, path="$.security_mapping_sha256"
            ),
        }
    )


def validate_universe_event_against_evidence(
    event: Mapping[str, Any] | UniverseEvent,
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
) -> UniverseEvent:
    record = validate_universe_event(event)
    supplied = [validate_evidence_record(item) for item in evidence_records]
    by_id: dict[str, EvidenceRecord] = {}
    for item in supplied:
        if item.evidence_id in by_id:
            _fail(
                "duplicate_evidence_id",
                "$.evidence_records",
                f"duplicate evidence id {item.evidence_id}",
        )
        by_id[item.evidence_id] = item
    sources_by_id: dict[str, SourceContract] = {}
    for item in source_contracts:
        source = validate_source_contract(item)
        if source.source_contract_id in sources_by_id:
            _fail(
                "duplicate_source_contract_id",
                "$.source_contracts",
                f"duplicate source contract id {source.source_contract_id}",
            )
        sources_by_id[source.source_contract_id] = source
    missing = [item for item in record.evidence_record_ids if item not in by_id]
    if missing:
        _fail(
            "unresolved_evidence_id",
            "$.evidence_record_ids",
            f"unresolved ids: {', '.join(missing)}",
        )
    referenced: list[EvidenceRecord] = []
    for evidence_id in record.evidence_record_ids:
        evidence = by_id[evidence_id]
        source = sources_by_id.get(evidence.source_contract_id)
        if source is None:
            _fail(
                "unresolved_source_contract_id",
                "$.source_contracts",
                f"no source contract for {evidence.source_contract_id}",
            )
        referenced.append(validate_evidence_against_source(evidence, source))
    weakest = min(referenced, key=lambda item: _PIT_RANK[item.pit_tier]).pit_tier
    if _PIT_RANK[record.pit_tier] > _PIT_RANK[weakest]:
        _fail(
            "pit_tier_exceeds_evidence",
            "$.pit_tier",
            "universe event tier exceeds its weakest evidence record",
        )
    _, event_known_dt = _instant(record.known_at, path="$.known_at")
    _, event_decided_dt = _instant(record.decided_at, path="$.decided_at")
    for item in referenced:
        _, evidence_known_dt = _instant(item.known_at, path="$.evidence.known_at")
        if evidence_known_dt > event_known_dt:
            _fail(
                "event_known_before_evidence",
                "$.known_at",
                "event cannot be known before referenced evidence",
            )
        _, evidence_recorded_dt = _instant(
            item.recorded_at, path="$.evidence.recorded_at"
        )
        if evidence_recorded_dt > event_decided_dt:
            _fail(
                "evidence_recorded_after_decision",
                "$.evidence.recorded_at",
                "referenced evidence must be recorded before the universe decision",
            )
        if (
            item.security_mapping is not None
            and item.security_mapping.security_id != record.security_mapping.security_id
        ):
            _fail(
                "evidence_security_mismatch",
                "$.security_mapping.security_id",
                "instrument evidence refers to a different security",
            )
    expected_snapshot = universe_input_snapshot_hash(
        referenced,
        rule_sha256=record.rule_sha256,
        security_mapping_sha256=record.security_mapping.mapping_sha256,
    )
    if record.input_snapshot_sha256 != expected_snapshot:
        _fail(
            "input_snapshot_hash_mismatch",
            "$.input_snapshot_sha256",
            f"expected {expected_snapshot}, got {record.input_snapshot_sha256}",
        )
    return record


__all__ = [
    "SCHEMA_VERSION",
    "PIT_TIERS",
    "V2ContractValidationError",
    "SecurityMappingSnapshot",
    "SourceContract",
    "EvidenceRecord",
    "UniverseEvent",
    "canonical_json",
    "canonical_hash",
    "validate_source_contract",
    "normalize_source_contract",
    "validate_evidence_record",
    "normalize_evidence_record",
    "validate_evidence_against_source",
    "validate_universe_event",
    "normalize_universe_event",
    "universe_input_snapshot_hash",
    "validate_universe_event_against_evidence",
]
