"""Strict, research-only foundation contracts for Ginger V2.

The records in this module describe source authority, point-in-time evidence,
replayable universe state transitions, evidence-backed research claims,
outcome-blind hypotheses, frozen security candidate pools, deterministic
research decisions, non-submitted order intents, and immutable measurement
records.  They deliberately perform no file I/O and have no runtime or
order-routing integration.  Every public validator is fail-closed, every
instant requires an explicit timezone, and trading is always disabled.
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
_CLAIM_KINDS = frozenset({"fact", "interpretation", "counterevidence"})
_PRODUCER_KINDS = frozenset({"human", "ai_skill", "deterministic"})
_RESEARCH_AUTHORITY = "research_only"
_NOVELTY_AXES = frozenset(
    {
        "independent_source",
        "different_decision_surface",
        "settled_forward_reopen",
        "unused_unsaturated_field",
        "none",
    }
)
_DECISION_SURFACES = frozenset(
    {"entry", "exit", "ranking", "candidate_pool", "notional_scalar", "allocator", "observer"}
)
_RESULT_CEILING_BY_PIT = {
    "not_pit": "invalid",
    "research_pit": "observed_only",
    "canonical_pit": "gate_eligible",
}
_CANDIDATE_ADMISSION_STATES = frozenset({"admitted", "parked", "rejected"})
_COMPARATOR_ROLES = frozenset({"cash", "spy", "qqq", "v1"})
_COMPARATOR_AVAILABILITY = frozenset({"available", "unavailable"})
_REQUIRED_COMPARATOR_ROLES = frozenset({"cash", "spy", "qqq", "v1"})
_DECISION_POLICY_ARMS = frozenset({"baseline", "treatment"})
_SIGNAL_ACTIONS = frozenset({"selected", "not_selected"})
_RISK_STATUSES = frozenset({"approved", "rejected"})
_ORDER_SIDES = frozenset({"buy", "sell", "sell_short", "buy_to_cover"})
_ORDER_TYPES = frozenset({"market", "limit", "stop", "stop_limit"})
_TIME_IN_FORCE_VALUES = frozenset({"day", "gtc", "ioc", "fok"})
_OUTCOME_STATUSES = frozenset({"settled", "unavailable"})
_REPLACEMENT_STATUSES = frozenset({"computed", "unavailable"})
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


def _string_tuple(
    value: Any, *, path: str, allow_empty: bool = False
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list of strings")
    values = [_text(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if not values and not allow_empty:
        _fail("nonempty_list_required", path, "must contain at least one value")
    if len(values) != len(set(values)):
        _fail("duplicate_list_value", path, "must not contain duplicate values")
    return tuple(sorted(values))


def _ordered_string_tuple(value: Any, *, path: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list of strings")
    values = tuple(
        _text(item, path=f"{path}[{index}]") for index, item in enumerate(value)
    )
    if not values:
        _fail("nonempty_list_required", path, "must contain at least one value")
    if len(values) != len(set(values)):
        _fail("duplicate_list_value", path, "must not contain duplicate values")
    return values


def _bounded_integer(value: Any, *, minimum: int, maximum: int, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail("integer_required", path, "must be an integer")
    if value < minimum or value > maximum:
        _fail("integer_out_of_range", path, f"must be between {minimum} and {maximum}")
    return value


def _optional_integer(
    value: Any,
    *,
    path: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        _fail("integer_required", path, "must be an integer or null")
    if minimum is not None and value < minimum:
        _fail("integer_out_of_range", path, f"must be at least {minimum}")
    if maximum is not None and value > maximum:
        _fail("integer_out_of_range", path, f"must be at most {maximum}")
    return value


def _optional_currency(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    result = _text(value, path=path).upper()
    if re.fullmatch(r"[A-Z]{3}", result) is None:
        _fail("invalid_currency", path, "must be a three-letter uppercase currency")
    return result


def _require_true(value: Any, *, path: str, code: str) -> bool:
    result = _boolean(value, path=path)
    if not result:
        _fail(code, path, "must be true")
    return True


def _require_false(value: Any, *, path: str, code: str) -> bool:
    result = _boolean(value, path=path)
    if result:
        _fail(code, path, "must be false")
    return False


def _research_authority(value: Any, *, path: str) -> str:
    result = _text(value, path=path)
    if result != _RESEARCH_AUTHORITY:
        _fail(
            "research_authority_required",
            path,
            f"must equal {_RESEARCH_AUTHORITY}",
        )
    return result


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


def _hypothesis_mechanism(value: Any, *, path: str) -> Mapping[str, Any]:
    raw = _mapping(value, path=path)
    _check_fields(
        raw,
        required={
            "economic_mechanism",
            "causal_chain",
            "decision_surface",
            "why_not_arbitraged",
        },
        path=path,
    )
    return MappingProxyType(
        {
            "economic_mechanism": _text(
                raw["economic_mechanism"], path=f"{path}.economic_mechanism"
            ),
            "causal_chain": _ordered_string_tuple(
                raw["causal_chain"], path=f"{path}.causal_chain"
            ),
            "decision_surface": _enum(
                raw["decision_surface"],
                allowed=_DECISION_SURFACES,
                path=f"{path}.decision_surface",
            ),
            "why_not_arbitraged": _text(
                raw["why_not_arbitraged"], path=f"{path}.why_not_arbitraged"
            ),
        }
    )


def _policy_snapshot(value: Any, *, path: str) -> Mapping[str, Any]:
    raw = _mapping(value, path=path)
    fields = {
        "policy_id",
        "entry_policy_version",
        "ranking_policy_version",
        "sizing_policy_version",
        "exit_policy_version",
        "cost_policy_version",
        "parameters_sha256",
    }
    _check_fields(raw, required=fields, path=path)
    return MappingProxyType(
        {
            "policy_id": _text(raw["policy_id"], path=f"{path}.policy_id"),
            "entry_policy_version": _text(
                raw["entry_policy_version"], path=f"{path}.entry_policy_version"
            ),
            "ranking_policy_version": _text(
                raw["ranking_policy_version"], path=f"{path}.ranking_policy_version"
            ),
            "sizing_policy_version": _text(
                raw["sizing_policy_version"], path=f"{path}.sizing_policy_version"
            ),
            "exit_policy_version": _text(
                raw["exit_policy_version"], path=f"{path}.exit_policy_version"
            ),
            "cost_policy_version": _text(
                raw["cost_policy_version"], path=f"{path}.cost_policy_version"
            ),
            "parameters_sha256": _sha256(
                raw["parameters_sha256"], path=f"{path}.parameters_sha256"
            ),
        }
    )


def _execution_constraints(value: Any, *, path: str) -> Mapping[str, Any]:
    raw = _mapping(value, path=path)
    fields = {
        "liquidity_rule",
        "capacity_rule",
        "timing_rule",
        "overlap_rule",
        "concentration_rule",
    }
    _check_fields(raw, required=fields, path=path)
    return MappingProxyType(
        {field: _text(raw[field], path=f"{path}.{field}") for field in sorted(fields)}
    )


@dataclass(frozen=True, slots=True)
class ResearchClaim:
    schema_version: int
    record_type: str
    claim_id: str
    claim_kind: str
    claim_text: str
    producer_kind: str
    producer_id: str
    producer_version: str
    producer_sha256: str
    evidence_record_ids: tuple[str, ...]
    evidence_snapshot_sha256: str
    affected_object_ids: tuple[str, ...]
    as_of: str
    created_at: str
    known_at: str
    recorded_at: str
    pit_tier: str
    known_future_leakage: bool
    confidence_bps: int
    confidence_basis: str
    falsifier: str
    next_step: str
    outcome_blind: bool
    authority: str
    trade_enabled: bool
    semantic_hash: str
    record_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResearchClaim":
        raw = _mapping(value, path="$")
        _check_fields(raw, required=set(cls.__dataclass_fields__), path="$")
        as_of, as_of_dt = _instant(raw["as_of"], path="$.as_of")
        created_at, created_dt = _instant(raw["created_at"], path="$.created_at")
        known_at, known_dt = _instant(raw["known_at"], path="$.known_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], path="$.recorded_at")
        if not (as_of_dt <= created_dt <= known_dt <= recorded_dt):
            _fail(
                "invalid_claim_chronology",
                "$.as_of",
                "must satisfy as_of <= created_at <= known_at <= recorded_at",
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
                raw["record_type"], expected="v2_research_claim", path="$.record_type"
            ),
            claim_id=_text(raw["claim_id"], path="$.claim_id"),
            claim_kind=_enum(raw["claim_kind"], allowed=_CLAIM_KINDS, path="$.claim_kind"),
            claim_text=_text(raw["claim_text"], path="$.claim_text"),
            producer_kind=_enum(
                raw["producer_kind"], allowed=_PRODUCER_KINDS, path="$.producer_kind"
            ),
            producer_id=_text(raw["producer_id"], path="$.producer_id"),
            producer_version=_text(raw["producer_version"], path="$.producer_version"),
            producer_sha256=_sha256(raw["producer_sha256"], path="$.producer_sha256"),
            evidence_record_ids=_string_tuple(
                raw["evidence_record_ids"], path="$.evidence_record_ids"
            ),
            evidence_snapshot_sha256=_sha256(
                raw["evidence_snapshot_sha256"], path="$.evidence_snapshot_sha256"
            ),
            affected_object_ids=_string_tuple(
                raw["affected_object_ids"], path="$.affected_object_ids"
            ),
            as_of=as_of,
            created_at=created_at,
            known_at=known_at,
            recorded_at=recorded_at,
            pit_tier=pit_tier,
            known_future_leakage=leakage,
            confidence_bps=_bounded_integer(
                raw["confidence_bps"], minimum=0, maximum=10_000, path="$.confidence_bps"
            ),
            confidence_basis=_text(raw["confidence_basis"], path="$.confidence_basis"),
            falsifier=_text(raw["falsifier"], path="$.falsifier"),
            next_step=_text(raw["next_step"], path="$.next_step"),
            outcome_blind=_require_true(
                raw["outcome_blind"], path="$.outcome_blind", code="outcome_blind_required"
            ),
            authority=_research_authority(raw["authority"], path="$.authority"),
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
        return {field: _plain(getattr(self, field)) for field in self.__dataclass_fields__}

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class HypothesisCandidate:
    schema_version: int
    record_type: str
    candidate_id: str
    hypothesis: str
    mechanism: Mapping[str, Any]
    research_claim_ids: tuple[str, ...]
    claim_snapshot_sha256: str
    novelty_axis: str
    novelty_basis: str
    prior_fingerprint_snapshot_sha256: str
    baseline_policy: Mapping[str, Any]
    treatment_policy: Mapping[str, Any]
    expected_horizon: str
    replacement_comparator_ids: tuple[str, ...]
    success_criteria: tuple[str, ...]
    failure_conditions: tuple[str, ...]
    falsifier: str
    kill_switches: tuple[str, ...]
    promotion_conditions: tuple[str, ...]
    execution_constraints: Mapping[str, Any]
    pit_tier: str
    result_ceiling: str
    known_future_leakage: bool
    data_cutoff: str
    created_at: str
    frozen_at: str
    recorded_at: str
    outcome_blind: bool
    results_accessed: bool
    authority: str
    trade_enabled: bool
    semantic_hash: str
    record_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HypothesisCandidate":
        raw = _mapping(value, path="$")
        _check_fields(raw, required=set(cls.__dataclass_fields__), path="$")
        data_cutoff, cutoff_dt = _instant(raw["data_cutoff"], path="$.data_cutoff")
        created_at, created_dt = _instant(raw["created_at"], path="$.created_at")
        frozen_at, frozen_dt = _instant(raw["frozen_at"], path="$.frozen_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], path="$.recorded_at")
        if not (cutoff_dt <= created_dt <= frozen_dt <= recorded_dt):
            _fail(
                "invalid_hypothesis_chronology",
                "$.data_cutoff",
                "must satisfy data_cutoff <= created_at <= frozen_at <= recorded_at",
            )
        baseline = _policy_snapshot(raw["baseline_policy"], path="$.baseline_policy")
        treatment = _policy_snapshot(raw["treatment_policy"], path="$.treatment_policy")
        if canonical_hash(baseline) == canonical_hash(treatment):
            _fail(
                "identical_baseline_treatment",
                "$.treatment_policy",
                "treatment policy must differ from baseline policy",
            )
        comparator_ids = _string_tuple(
            raw["replacement_comparator_ids"], path="$.replacement_comparator_ids"
        )
        required_comparators = {"cash", "SPY", "QQQ", "V1"}
        if set(comparator_ids) != required_comparators:
            _fail(
                "required_comparator_missing",
                "$.replacement_comparator_ids",
                "must contain exactly cash, SPY, QQQ, and V1",
            )
        pit_tier = _enum(raw["pit_tier"], allowed=PIT_TIERS, path="$.pit_tier")
        leakage = _boolean(raw["known_future_leakage"], path="$.known_future_leakage")
        if pit_tier != "not_pit" and leakage:
            _fail(
                "future_leakage_requires_not_pit",
                "$.known_future_leakage",
                "known future leakage is only valid with not_pit",
            )
        result_ceiling = _text(raw["result_ceiling"], path="$.result_ceiling")
        expected_ceiling = _RESULT_CEILING_BY_PIT[pit_tier]
        if result_ceiling != expected_ceiling:
            _fail(
                "result_ceiling_mismatch",
                "$.result_ceiling",
                f"must equal {expected_ceiling} for {pit_tier}",
            )
        obj = cls(
            schema_version=_schema_version(raw["schema_version"], path="$.schema_version"),
            record_type=_record_type(
                raw["record_type"],
                expected="v2_hypothesis_candidate",
                path="$.record_type",
            ),
            candidate_id=_text(raw["candidate_id"], path="$.candidate_id"),
            hypothesis=_text(raw["hypothesis"], path="$.hypothesis"),
            mechanism=_hypothesis_mechanism(raw["mechanism"], path="$.mechanism"),
            research_claim_ids=_string_tuple(
                raw["research_claim_ids"], path="$.research_claim_ids"
            ),
            claim_snapshot_sha256=_sha256(
                raw["claim_snapshot_sha256"], path="$.claim_snapshot_sha256"
            ),
            novelty_axis=_enum(
                raw["novelty_axis"], allowed=_NOVELTY_AXES, path="$.novelty_axis"
            ),
            novelty_basis=_text(raw["novelty_basis"], path="$.novelty_basis"),
            prior_fingerprint_snapshot_sha256=_sha256(
                raw["prior_fingerprint_snapshot_sha256"],
                path="$.prior_fingerprint_snapshot_sha256",
            ),
            baseline_policy=baseline,
            treatment_policy=treatment,
            expected_horizon=_text(raw["expected_horizon"], path="$.expected_horizon"),
            replacement_comparator_ids=comparator_ids,
            success_criteria=_ordered_string_tuple(
                raw["success_criteria"], path="$.success_criteria"
            ),
            failure_conditions=_ordered_string_tuple(
                raw["failure_conditions"], path="$.failure_conditions"
            ),
            falsifier=_text(raw["falsifier"], path="$.falsifier"),
            kill_switches=_ordered_string_tuple(raw["kill_switches"], path="$.kill_switches"),
            promotion_conditions=_ordered_string_tuple(
                raw["promotion_conditions"], path="$.promotion_conditions"
            ),
            execution_constraints=_execution_constraints(
                raw["execution_constraints"], path="$.execution_constraints"
            ),
            pit_tier=pit_tier,
            result_ceiling=result_ceiling,
            known_future_leakage=leakage,
            data_cutoff=data_cutoff,
            created_at=created_at,
            frozen_at=frozen_at,
            recorded_at=recorded_at,
            outcome_blind=_require_true(
                raw["outcome_blind"], path="$.outcome_blind", code="outcome_blind_required"
            ),
            results_accessed=_require_false(
                raw["results_accessed"],
                path="$.results_accessed",
                code="results_accessed_forbidden",
            ),
            authority=_research_authority(raw["authority"], path="$.authority"),
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
        return {field: _plain(getattr(self, field)) for field in self.__dataclass_fields__}

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class CandidatePoolEntry:
    candidate_entry_id: str
    security_id: str
    listing_id: str
    universe_event_id: str
    security_mapping_sha256: str
    evidence_record_ids: tuple[str, ...]
    decision_input_sha256: str
    admission_status: str
    reason_code: str
    reason: str

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, path: str = "$.entries[]"
    ) -> "CandidatePoolEntry":
        raw = _mapping(value, path=path)
        _check_fields(raw, required=set(cls.__dataclass_fields__), path=path)
        return cls(
            candidate_entry_id=_text(
                raw["candidate_entry_id"], path=f"{path}.candidate_entry_id"
            ),
            security_id=_text(raw["security_id"], path=f"{path}.security_id"),
            listing_id=_text(raw["listing_id"], path=f"{path}.listing_id"),
            universe_event_id=_text(
                raw["universe_event_id"], path=f"{path}.universe_event_id"
            ),
            security_mapping_sha256=_sha256(
                raw["security_mapping_sha256"],
                path=f"{path}.security_mapping_sha256",
            ),
            evidence_record_ids=_string_tuple(
                raw["evidence_record_ids"], path=f"{path}.evidence_record_ids"
            ),
            decision_input_sha256=_sha256(
                raw["decision_input_sha256"], path=f"{path}.decision_input_sha256"
            ),
            admission_status=_enum(
                raw["admission_status"],
                allowed=_CANDIDATE_ADMISSION_STATES,
                path=f"{path}.admission_status",
            ),
            reason_code=_text(raw["reason_code"], path=f"{path}.reason_code"),
            reason=_text(raw["reason"], path=f"{path}.reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {field: _plain(getattr(self, field)) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class CandidatePoolComparator:
    role: str
    reference_id: str
    reference_snapshot_sha256: str
    availability_status: str
    reason_code: str
    reason: str
    comparison_only: bool

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, path: str = "$.comparators[]"
    ) -> "CandidatePoolComparator":
        raw = _mapping(value, path=path)
        _check_fields(raw, required=set(cls.__dataclass_fields__), path=path)
        return cls(
            role=_enum(raw["role"], allowed=_COMPARATOR_ROLES, path=f"{path}.role"),
            reference_id=_text(raw["reference_id"], path=f"{path}.reference_id"),
            reference_snapshot_sha256=_sha256(
                raw["reference_snapshot_sha256"],
                path=f"{path}.reference_snapshot_sha256",
            ),
            availability_status=_enum(
                raw["availability_status"],
                allowed=_COMPARATOR_AVAILABILITY,
                path=f"{path}.availability_status",
            ),
            reason_code=_text(raw["reason_code"], path=f"{path}.reason_code"),
            reason=_text(raw["reason"], path=f"{path}.reason"),
            comparison_only=_require_true(
                raw["comparison_only"],
                path=f"{path}.comparison_only",
                code="comparison_only_required",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {field: _plain(getattr(self, field)) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class CandidatePool:
    schema_version: int
    record_type: str
    candidate_pool_id: str
    hypothesis_candidate_id: str
    hypothesis_candidate_hash: str
    universe_id: str
    universe_event_ids: tuple[str, ...]
    universe_event_snapshot_sha256: str
    evidence_record_ids: tuple[str, ...]
    evidence_snapshot_sha256: str
    entries: tuple[CandidatePoolEntry, ...]
    comparators: tuple[CandidatePoolComparator, ...]
    generator_rule_id: str
    generator_rule_version: str
    generator_rule_sha256: str
    ranking_rule_id: str
    ranking_rule_version: str
    ranking_rule_sha256: str
    run_id: str
    run_date: str
    calendar_session_id: str
    data_cutoff: str
    frozen_at: str
    recorded_at: str
    expected_candidate_count: int
    candidate_pool_complete: bool
    universe_snapshot_complete: bool
    input_snapshot_sha256: str
    pit_tier: str
    result_ceiling: str
    known_future_leakage: bool
    outcome_blind: bool
    results_accessed: bool
    authority: str
    trade_enabled: bool
    semantic_hash: str
    record_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CandidatePool":
        raw = _mapping(value, path="$")
        _check_fields(raw, required=set(cls.__dataclass_fields__), path="$")
        entries_raw = raw["entries"]
        if not isinstance(entries_raw, Sequence) or isinstance(
            entries_raw, (str, bytes, bytearray)
        ):
            _fail("list_required", "$.entries", "must be a list")
        entries = tuple(
            CandidatePoolEntry.from_dict(item, path=f"$.entries[{index}]")
            for index, item in enumerate(entries_raw)
        )
        entry_ids = [item.candidate_entry_id for item in entries]
        if len(entry_ids) != len(set(entry_ids)):
            _fail("duplicate_candidate_entry_id", "$.entries", "entry ids must be unique")
        securities = [(item.security_id, item.listing_id) for item in entries]
        if len(securities) != len(set(securities)):
            _fail(
                "duplicate_candidate_security",
                "$.entries",
                "security/listing pairs must be unique",
            )
        expected_count = _bounded_integer(
            raw["expected_candidate_count"],
            minimum=0,
            maximum=10_000_000,
            path="$.expected_candidate_count",
        )
        if expected_count != len(entries):
            _fail(
                "candidate_count_mismatch",
                "$.expected_candidate_count",
                "must equal the number of frozen entries",
            )
        comparators_raw = raw["comparators"]
        if not isinstance(comparators_raw, Sequence) or isinstance(
            comparators_raw, (str, bytes, bytearray)
        ):
            _fail("list_required", "$.comparators", "must be a list")
        comparators = tuple(
            CandidatePoolComparator.from_dict(item, path=f"$.comparators[{index}]")
            for index, item in enumerate(comparators_raw)
        )
        roles = [item.role for item in comparators]
        if len(roles) != len(set(roles)) or set(roles) != _REQUIRED_COMPARATOR_ROLES:
            _fail(
                "comparator_panel_incomplete",
                "$.comparators",
                "must contain exactly one cash, SPY, QQQ, and V1 comparator",
            )
        data_cutoff, cutoff_dt = _instant(raw["data_cutoff"], path="$.data_cutoff")
        frozen_at, frozen_dt = _instant(raw["frozen_at"], path="$.frozen_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], path="$.recorded_at")
        if not (cutoff_dt <= frozen_dt <= recorded_dt):
            _fail(
                "invalid_candidate_pool_chronology",
                "$.data_cutoff",
                "must satisfy data_cutoff <= frozen_at <= recorded_at",
            )
        pit_tier = _enum(raw["pit_tier"], allowed=PIT_TIERS, path="$.pit_tier")
        leakage = _boolean(raw["known_future_leakage"], path="$.known_future_leakage")
        if pit_tier != "not_pit" and leakage:
            _fail(
                "future_leakage_requires_not_pit",
                "$.known_future_leakage",
                "known future leakage is only valid with not_pit",
            )
        result_ceiling = _text(raw["result_ceiling"], path="$.result_ceiling")
        expected_ceiling = _RESULT_CEILING_BY_PIT[pit_tier]
        if result_ceiling != expected_ceiling:
            _fail(
                "result_ceiling_mismatch",
                "$.result_ceiling",
                f"must equal {expected_ceiling} for {pit_tier}",
            )
        obj = cls(
            schema_version=_schema_version(raw["schema_version"], path="$.schema_version"),
            record_type=_record_type(
                raw["record_type"], expected="v2_candidate_pool", path="$.record_type"
            ),
            candidate_pool_id=_text(raw["candidate_pool_id"], path="$.candidate_pool_id"),
            hypothesis_candidate_id=_text(
                raw["hypothesis_candidate_id"], path="$.hypothesis_candidate_id"
            ),
            hypothesis_candidate_hash=_sha256(
                raw["hypothesis_candidate_hash"], path="$.hypothesis_candidate_hash"
            ),
            universe_id=_text(raw["universe_id"], path="$.universe_id"),
            universe_event_ids=_string_tuple(
                raw["universe_event_ids"], path="$.universe_event_ids"
            ),
            universe_event_snapshot_sha256=_sha256(
                raw["universe_event_snapshot_sha256"],
                path="$.universe_event_snapshot_sha256",
            ),
            evidence_record_ids=_string_tuple(
                raw["evidence_record_ids"], path="$.evidence_record_ids"
            ),
            evidence_snapshot_sha256=_sha256(
                raw["evidence_snapshot_sha256"], path="$.evidence_snapshot_sha256"
            ),
            entries=tuple(sorted(entries, key=lambda item: item.candidate_entry_id)),
            comparators=tuple(sorted(comparators, key=lambda item: item.role)),
            generator_rule_id=_text(raw["generator_rule_id"], path="$.generator_rule_id"),
            generator_rule_version=_text(
                raw["generator_rule_version"], path="$.generator_rule_version"
            ),
            generator_rule_sha256=_sha256(
                raw["generator_rule_sha256"], path="$.generator_rule_sha256"
            ),
            ranking_rule_id=_text(raw["ranking_rule_id"], path="$.ranking_rule_id"),
            ranking_rule_version=_text(
                raw["ranking_rule_version"], path="$.ranking_rule_version"
            ),
            ranking_rule_sha256=_sha256(
                raw["ranking_rule_sha256"], path="$.ranking_rule_sha256"
            ),
            run_id=_text(raw["run_id"], path="$.run_id"),
            run_date=_calendar_date(raw["run_date"], path="$.run_date"),
            calendar_session_id=_text(
                raw["calendar_session_id"], path="$.calendar_session_id"
            ),
            data_cutoff=data_cutoff,
            frozen_at=frozen_at,
            recorded_at=recorded_at,
            expected_candidate_count=expected_count,
            candidate_pool_complete=_require_true(
                raw["candidate_pool_complete"],
                path="$.candidate_pool_complete",
                code="candidate_pool_incomplete",
            ),
            universe_snapshot_complete=_require_true(
                raw["universe_snapshot_complete"],
                path="$.universe_snapshot_complete",
                code="universe_snapshot_incomplete",
            ),
            input_snapshot_sha256=_sha256(
                raw["input_snapshot_sha256"], path="$.input_snapshot_sha256"
            ),
            pit_tier=pit_tier,
            result_ceiling=result_ceiling,
            known_future_leakage=leakage,
            outcome_blind=_require_true(
                raw["outcome_blind"], path="$.outcome_blind", code="outcome_blind_required"
            ),
            results_accessed=_require_false(
                raw["results_accessed"],
                path="$.results_accessed",
                code="results_accessed_forbidden",
            ),
            authority=_research_authority(raw["authority"], path="$.authority"),
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
            if field in {"entries", "comparators"}:
                result[field] = [item.to_dict() for item in value]
            else:
                result[field] = _plain(value)
        return result

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class DecisionItem:
    decision_item_id: str
    candidate_entry_id: str
    security_id: str
    listing_id: str
    security_mapping_sha256: str
    rank: int | None
    signal_action: str | None
    side: str | None
    risk_status: str | None
    approved_quantity_micros: int | None
    approved_notional_minor: int | None
    currency: str | None
    reason_code: str
    reason: str

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, path: str = "$.items[]"
    ) -> "DecisionItem":
        raw = _mapping(value, path=path)
        _check_fields(raw, required=set(cls.__dataclass_fields__), path=path)
        rank = _optional_integer(raw["rank"], path=f"{path}.rank", minimum=1)
        action = (
            None
            if raw["signal_action"] is None
            else _enum(
                raw["signal_action"],
                allowed=_SIGNAL_ACTIONS,
                path=f"{path}.signal_action",
            )
        )
        side = (
            None
            if raw["side"] is None
            else _enum(raw["side"], allowed=_ORDER_SIDES, path=f"{path}.side")
        )
        risk = (
            None
            if raw["risk_status"] is None
            else _enum(
                raw["risk_status"],
                allowed=_RISK_STATUSES,
                path=f"{path}.risk_status",
            )
        )
        quantity = _optional_integer(
            raw["approved_quantity_micros"],
            path=f"{path}.approved_quantity_micros",
            minimum=1,
        )
        notional = _optional_integer(
            raw["approved_notional_minor"],
            path=f"{path}.approved_notional_minor",
            minimum=1,
        )
        currency = _optional_currency(raw["currency"], path=f"{path}.currency")
        if action == "selected":
            if side is None:
                _fail(
                    "selected_side_required",
                    f"{path}.side",
                    "selected items must freeze an order side",
                )
            if risk is None:
                _fail(
                    "risk_status_required",
                    f"{path}.risk_status",
                    "selected items require an explicit approved or rejected risk result",
                )
            if risk == "approved":
                if (quantity is None) == (notional is None):
                    _fail(
                        "approved_size_xor_required",
                        path,
                        "approved selected items require exactly one of quantity or notional",
                    )
                if currency is None:
                    _fail(
                        "approved_currency_required",
                        f"{path}.currency",
                        "approved selected items require a currency",
                    )
            elif quantity is not None or notional is not None or currency is not None:
                _fail(
                    "rejected_size_forbidden",
                    path,
                    "risk-rejected items cannot carry approved size or currency",
                )
        elif (
            side is not None
            or risk is not None
            or quantity is not None
            or notional is not None
            or currency is not None
        ):
            _fail(
                "inactive_decision_fields_forbidden",
                path,
                "unselected or inactive items cannot carry risk or approved size",
            )
        return cls(
            decision_item_id=_text(
                raw["decision_item_id"], path=f"{path}.decision_item_id"
            ),
            candidate_entry_id=_text(
                raw["candidate_entry_id"], path=f"{path}.candidate_entry_id"
            ),
            security_id=_text(raw["security_id"], path=f"{path}.security_id"),
            listing_id=_text(raw["listing_id"], path=f"{path}.listing_id"),
            security_mapping_sha256=_sha256(
                raw["security_mapping_sha256"],
                path=f"{path}.security_mapping_sha256",
            ),
            rank=rank,
            signal_action=action,
            side=side,
            risk_status=risk,
            approved_quantity_micros=quantity,
            approved_notional_minor=notional,
            currency=currency,
            reason_code=_text(raw["reason_code"], path=f"{path}.reason_code"),
            reason=_text(raw["reason"], path=f"{path}.reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {field: _plain(getattr(self, field)) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    schema_version: int
    record_type: str
    decision_id: str
    candidate_pool_id: str
    candidate_pool_hash: str
    candidate_pool_record_hash: str
    policy_arm: str
    policy_snapshot: Mapping[str, Any]
    decision_engine_id: str
    decision_engine_version: str
    decision_engine_sha256: str
    decision_context_id: str
    decision_context_sha256: str
    execution_rule_id: str
    execution_rule_version: str
    execution_rule_sha256: str
    cost_rule_id: str
    cost_rule_version: str
    cost_rule_sha256: str
    comparison_rule_id: str
    comparison_rule_version: str
    comparison_rule_sha256: str
    items: tuple[DecisionItem, ...]
    expected_item_count: int
    decision_complete: bool
    run_id: str
    run_date: str
    calendar_session_id: str
    data_cutoff: str
    expected_horizon: str
    decided_at: str
    recorded_at: str
    input_snapshot_sha256: str
    pit_tier: str
    result_ceiling: str
    known_future_leakage: bool
    outcome_blind: bool
    results_accessed: bool
    authority: str
    trade_enabled: bool
    semantic_hash: str
    record_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DecisionRecord":
        raw = _mapping(value, path="$")
        _check_fields(raw, required=set(cls.__dataclass_fields__), path="$")
        items_raw = raw["items"]
        if not isinstance(items_raw, Sequence) or isinstance(
            items_raw, (str, bytes, bytearray)
        ):
            _fail("list_required", "$.items", "must be a list")
        items = tuple(
            DecisionItem.from_dict(item, path=f"$.items[{index}]")
            for index, item in enumerate(items_raw)
        )
        for values, code, detail in (
            (
                [item.decision_item_id for item in items],
                "duplicate_decision_item_id",
                "decision item ids must be unique",
            ),
            (
                [item.candidate_entry_id for item in items],
                "duplicate_candidate_entry_id",
                "candidate entry ids must be unique",
            ),
            (
                [(item.security_id, item.listing_id) for item in items],
                "duplicate_decision_security",
                "security/listing pairs must be unique",
            ),
        ):
            if len(values) != len(set(values)):
                _fail(code, "$.items", detail)
        ranks = sorted(item.rank for item in items if item.rank is not None)
        if ranks != list(range(1, len(ranks) + 1)):
            _fail(
                "noncontiguous_decision_ranks",
                "$.items",
                "non-null ranks must be unique and contiguous from one",
            )
        expected_count = _bounded_integer(
            raw["expected_item_count"],
            minimum=0,
            maximum=10_000_000,
            path="$.expected_item_count",
        )
        if expected_count != len(items):
            _fail(
                "decision_item_count_mismatch",
                "$.expected_item_count",
                "must equal the number of frozen decision items",
            )
        data_cutoff, cutoff_dt = _instant(raw["data_cutoff"], path="$.data_cutoff")
        decided_at, decided_dt = _instant(raw["decided_at"], path="$.decided_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], path="$.recorded_at")
        if not (cutoff_dt <= decided_dt <= recorded_dt):
            _fail(
                "invalid_decision_chronology",
                "$.data_cutoff",
                "must satisfy data_cutoff <= decided_at <= recorded_at",
            )
        pit_tier = _enum(raw["pit_tier"], allowed=PIT_TIERS, path="$.pit_tier")
        if pit_tier == "canonical_pit":
            _fail(
                "decision_context_contract_incomplete",
                "$.pit_tier",
                "decisions cannot be canonical until portfolio, cash, and position context PIT contracts exist",
            )
        leakage = _boolean(raw["known_future_leakage"], path="$.known_future_leakage")
        if pit_tier != "not_pit" and leakage:
            _fail(
                "future_leakage_requires_not_pit",
                "$.known_future_leakage",
                "known future leakage is only valid with not_pit",
            )
        result_ceiling = _text(raw["result_ceiling"], path="$.result_ceiling")
        expected_ceiling = _RESULT_CEILING_BY_PIT[pit_tier]
        if result_ceiling != expected_ceiling:
            _fail(
                "result_ceiling_mismatch",
                "$.result_ceiling",
                f"must equal {expected_ceiling} for {pit_tier}",
            )
        obj = cls(
            schema_version=_schema_version(raw["schema_version"], path="$.schema_version"),
            record_type=_record_type(
                raw["record_type"], expected="v2_decision_record", path="$.record_type"
            ),
            decision_id=_text(raw["decision_id"], path="$.decision_id"),
            candidate_pool_id=_text(
                raw["candidate_pool_id"], path="$.candidate_pool_id"
            ),
            candidate_pool_hash=_sha256(
                raw["candidate_pool_hash"], path="$.candidate_pool_hash"
            ),
            candidate_pool_record_hash=_sha256(
                raw["candidate_pool_record_hash"],
                path="$.candidate_pool_record_hash",
            ),
            policy_arm=_enum(
                raw["policy_arm"], allowed=_DECISION_POLICY_ARMS, path="$.policy_arm"
            ),
            policy_snapshot=_policy_snapshot(
                raw["policy_snapshot"], path="$.policy_snapshot"
            ),
            decision_engine_id=_text(
                raw["decision_engine_id"], path="$.decision_engine_id"
            ),
            decision_engine_version=_text(
                raw["decision_engine_version"], path="$.decision_engine_version"
            ),
            decision_engine_sha256=_sha256(
                raw["decision_engine_sha256"], path="$.decision_engine_sha256"
            ),
            decision_context_id=_text(
                raw["decision_context_id"], path="$.decision_context_id"
            ),
            decision_context_sha256=_sha256(
                raw["decision_context_sha256"], path="$.decision_context_sha256"
            ),
            execution_rule_id=_text(
                raw["execution_rule_id"], path="$.execution_rule_id"
            ),
            execution_rule_version=_text(
                raw["execution_rule_version"], path="$.execution_rule_version"
            ),
            execution_rule_sha256=_sha256(
                raw["execution_rule_sha256"], path="$.execution_rule_sha256"
            ),
            cost_rule_id=_text(raw["cost_rule_id"], path="$.cost_rule_id"),
            cost_rule_version=_text(
                raw["cost_rule_version"], path="$.cost_rule_version"
            ),
            cost_rule_sha256=_sha256(
                raw["cost_rule_sha256"], path="$.cost_rule_sha256"
            ),
            comparison_rule_id=_text(
                raw["comparison_rule_id"], path="$.comparison_rule_id"
            ),
            comparison_rule_version=_text(
                raw["comparison_rule_version"], path="$.comparison_rule_version"
            ),
            comparison_rule_sha256=_sha256(
                raw["comparison_rule_sha256"], path="$.comparison_rule_sha256"
            ),
            items=tuple(sorted(items, key=lambda item: item.candidate_entry_id)),
            expected_item_count=expected_count,
            decision_complete=_require_true(
                raw["decision_complete"],
                path="$.decision_complete",
                code="decision_incomplete",
            ),
            run_id=_text(raw["run_id"], path="$.run_id"),
            run_date=_calendar_date(raw["run_date"], path="$.run_date"),
            calendar_session_id=_text(
                raw["calendar_session_id"], path="$.calendar_session_id"
            ),
            data_cutoff=data_cutoff,
            expected_horizon=_text(
                raw["expected_horizon"], path="$.expected_horizon"
            ),
            decided_at=decided_at,
            recorded_at=recorded_at,
            input_snapshot_sha256=_sha256(
                raw["input_snapshot_sha256"], path="$.input_snapshot_sha256"
            ),
            pit_tier=pit_tier,
            result_ceiling=result_ceiling,
            known_future_leakage=leakage,
            outcome_blind=_require_true(
                raw["outcome_blind"],
                path="$.outcome_blind",
                code="outcome_blind_required",
            ),
            results_accessed=_require_false(
                raw["results_accessed"],
                path="$.results_accessed",
                code="results_accessed_forbidden",
            ),
            authority=_research_authority(raw["authority"], path="$.authority"),
            trade_enabled=_require_default_off(raw["trade_enabled"], path="$.trade_enabled"),
            semantic_hash=_sha256(raw["semantic_hash"], path="$.semantic_hash"),
            record_hash=_sha256(raw["record_hash"], path="$.record_hash"),
        )
        if obj.cost_rule_version != obj.policy_snapshot["cost_policy_version"]:
            _fail(
                "cost_rule_version_mismatch",
                "$.cost_rule_version",
                "must equal policy_snapshot.cost_policy_version",
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
            result[field] = (
                [item.to_dict() for item in value]
                if field == "items"
                else _plain(value)
            )
        return result

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class OrderIntent:
    schema_version: int
    record_type: str
    order_intent_id: str
    decision_id: str
    decision_hash: str
    decision_record_hash: str
    decision_item_id: str
    candidate_entry_id: str
    security_id: str
    listing_id: str
    security_mapping_sha256: str
    side: str
    quantity_micros: int | None
    notional_minor: int | None
    currency: str
    order_type: str
    limit_price_minor: int | None
    stop_price_minor: int | None
    time_in_force: str
    not_before: str
    expires_at: str
    calendar_session_id: str
    execution_rule_id: str
    execution_rule_version: str
    execution_rule_sha256: str
    created_at: str
    recorded_at: str
    input_snapshot_sha256: str
    submitted: bool
    authority: str
    trade_enabled: bool
    semantic_hash: str
    record_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OrderIntent":
        raw = _mapping(value, path="$")
        _check_fields(raw, required=set(cls.__dataclass_fields__), path="$")
        quantity = _optional_integer(
            raw["quantity_micros"], path="$.quantity_micros", minimum=1
        )
        notional = _optional_integer(
            raw["notional_minor"], path="$.notional_minor", minimum=1
        )
        if (quantity is None) == (notional is None):
            _fail(
                "order_size_xor_required",
                "$.quantity_micros",
                "exactly one of quantity or notional must be provided",
            )
        order_type = _enum(
            raw["order_type"], allowed=_ORDER_TYPES, path="$.order_type"
        )
        limit_price = _optional_integer(
            raw["limit_price_minor"], path="$.limit_price_minor", minimum=1
        )
        stop_price = _optional_integer(
            raw["stop_price_minor"], path="$.stop_price_minor", minimum=1
        )
        expected_price_fields = {
            "market": (False, False),
            "limit": (True, False),
            "stop": (False, True),
            "stop_limit": (True, True),
        }[order_type]
        actual_price_fields = (limit_price is not None, stop_price is not None)
        if actual_price_fields != expected_price_fields:
            _fail(
                "order_price_fields_mismatch",
                "$.order_type",
                "limit and stop prices must exactly match the order type",
            )
        created_at, created_dt = _instant(raw["created_at"], path="$.created_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], path="$.recorded_at")
        not_before, not_before_dt = _instant(raw["not_before"], path="$.not_before")
        expires_at, expires_dt = _instant(raw["expires_at"], path="$.expires_at")
        if not (created_dt <= recorded_dt <= not_before_dt < expires_dt):
            _fail(
                "invalid_order_intent_chronology",
                "$.created_at",
                "must satisfy created_at <= recorded_at <= not_before < expires_at",
            )
        obj = cls(
            schema_version=_schema_version(raw["schema_version"], path="$.schema_version"),
            record_type=_record_type(
                raw["record_type"], expected="v2_order_intent", path="$.record_type"
            ),
            order_intent_id=_text(raw["order_intent_id"], path="$.order_intent_id"),
            decision_id=_text(raw["decision_id"], path="$.decision_id"),
            decision_hash=_sha256(raw["decision_hash"], path="$.decision_hash"),
            decision_record_hash=_sha256(
                raw["decision_record_hash"], path="$.decision_record_hash"
            ),
            decision_item_id=_text(
                raw["decision_item_id"], path="$.decision_item_id"
            ),
            candidate_entry_id=_text(
                raw["candidate_entry_id"], path="$.candidate_entry_id"
            ),
            security_id=_text(raw["security_id"], path="$.security_id"),
            listing_id=_text(raw["listing_id"], path="$.listing_id"),
            security_mapping_sha256=_sha256(
                raw["security_mapping_sha256"], path="$.security_mapping_sha256"
            ),
            side=_enum(raw["side"], allowed=_ORDER_SIDES, path="$.side"),
            quantity_micros=quantity,
            notional_minor=notional,
            currency=_optional_currency(raw["currency"], path="$.currency") or "",
            order_type=order_type,
            limit_price_minor=limit_price,
            stop_price_minor=stop_price,
            time_in_force=_enum(
                raw["time_in_force"],
                allowed=_TIME_IN_FORCE_VALUES,
                path="$.time_in_force",
            ),
            not_before=not_before,
            expires_at=expires_at,
            calendar_session_id=_text(
                raw["calendar_session_id"], path="$.calendar_session_id"
            ),
            execution_rule_id=_text(
                raw["execution_rule_id"], path="$.execution_rule_id"
            ),
            execution_rule_version=_text(
                raw["execution_rule_version"], path="$.execution_rule_version"
            ),
            execution_rule_sha256=_sha256(
                raw["execution_rule_sha256"], path="$.execution_rule_sha256"
            ),
            created_at=created_at,
            recorded_at=recorded_at,
            input_snapshot_sha256=_sha256(
                raw["input_snapshot_sha256"], path="$.input_snapshot_sha256"
            ),
            submitted=_require_false(
                raw["submitted"], path="$.submitted", code="submitted_order_forbidden"
            ),
            authority=_research_authority(raw["authority"], path="$.authority"),
            trade_enabled=_require_default_off(raw["trade_enabled"], path="$.trade_enabled"),
            semantic_hash=_sha256(raw["semantic_hash"], path="$.semantic_hash"),
            record_hash=_sha256(raw["record_hash"], path="$.record_hash"),
        )
        if not obj.currency:
            _fail("currency_required", "$.currency", "must be a three-letter currency")
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
        return {field: _plain(getattr(self, field)) for field in self.__dataclass_fields__}

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())


def _revision_identity(
    *,
    revision_number: Any,
    previous_id: Any,
    previous_hash: Any,
    path: str,
) -> tuple[int, str | None, str | None]:
    revision = _bounded_integer(
        revision_number,
        minimum=1,
        maximum=1_000_000_000,
        path=f"{path}.revision_number",
    )
    prior_id = _optional_text(previous_id, path=f"{path}.previous_id")
    prior_hash = _optional_sha256(previous_hash, path=f"{path}.previous_hash")
    if revision == 1 and (prior_id is not None or prior_hash is not None):
        _fail(
            "initial_revision_previous_forbidden",
            path,
            "the first revision cannot reference a previous record",
        )
    if revision > 1 and (prior_id is None or prior_hash is None):
        _fail(
            "previous_revision_required",
            path,
            "later revisions require both previous id and previous record hash",
        )
    return revision, prior_id, prior_hash


@dataclass(frozen=True, slots=True)
class SettledOutcome:
    schema_version: int
    record_type: str
    outcome_id: str
    stable_key: str
    revision_number: int
    previous_outcome_id: str | None
    previous_outcome_record_hash: str | None
    decision_id: str
    decision_hash: str
    decision_record_hash: str
    order_intent_id: str
    order_intent_hash: str
    order_intent_record_hash: str
    candidate_pool_id: str
    candidate_pool_hash: str
    candidate_pool_record_hash: str
    fill_snapshot_id: str
    fill_snapshot_sha256: str
    position_snapshot_id: str
    position_snapshot_sha256: str
    settlement_evidence_record_ids: tuple[str, ...]
    settlement_evidence_snapshot_sha256: str
    horizon: str
    entry_session_id: str
    entry_at: str
    exit_session_id: str
    exit_at: str
    settled_at: str
    recorded_at: str
    status: str
    reason_code: str
    reason: str
    basis_notional_minor: int | None
    currency: str | None
    gross_pnl_minor: int | None
    cost_minor: int | None
    net_pnl_minor: int | None
    cost_rule_id: str
    cost_rule_version: str
    cost_rule_sha256: str
    comparison_rule_id: str
    comparison_rule_version: str
    comparison_rule_sha256: str
    input_snapshot_sha256: str
    pit_tier: str
    result_ceiling: str
    known_future_leakage: bool
    measurement_only: bool
    trade_enabled: bool
    semantic_hash: str
    record_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SettledOutcome":
        raw = _mapping(value, path="$")
        _check_fields(raw, required=set(cls.__dataclass_fields__), path="$")
        revision, previous_id, previous_hash = _revision_identity(
            revision_number=raw["revision_number"],
            previous_id=raw["previous_outcome_id"],
            previous_hash=raw["previous_outcome_record_hash"],
            path="$",
        )
        evidence_ids = _string_tuple(
            raw["settlement_evidence_record_ids"],
            path="$.settlement_evidence_record_ids",
            allow_empty=True,
        )
        entry_at, entry_dt = _instant(raw["entry_at"], path="$.entry_at")
        exit_at, exit_dt = _instant(raw["exit_at"], path="$.exit_at")
        settled_at, settled_dt = _instant(raw["settled_at"], path="$.settled_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], path="$.recorded_at")
        if not (entry_dt <= exit_dt <= settled_dt <= recorded_dt):
            _fail(
                "invalid_outcome_chronology",
                "$.entry_at",
                "must satisfy entry_at <= exit_at <= settled_at <= recorded_at",
            )
        status = _enum(raw["status"], allowed=_OUTCOME_STATUSES, path="$.status")
        basis_notional = _optional_integer(
            raw["basis_notional_minor"],
            path="$.basis_notional_minor",
            minimum=1,
        )
        currency = _optional_currency(raw["currency"], path="$.currency")
        gross = _optional_integer(raw["gross_pnl_minor"], path="$.gross_pnl_minor")
        cost = _optional_integer(raw["cost_minor"], path="$.cost_minor", minimum=0)
        net = _optional_integer(raw["net_pnl_minor"], path="$.net_pnl_minor")
        measurement_values = (basis_notional, currency, gross, cost, net)
        if status == "settled":
            if not evidence_ids:
                _fail(
                    "settled_evidence_required",
                    "$.settlement_evidence_record_ids",
                    "settled outcomes require settlement evidence",
                )
            if any(item is None for item in measurement_values):
                _fail(
                    "settled_values_required",
                    "$.status",
                    "settled outcomes require basis notional, currency, gross, cost, and net",
                )
            assert gross is not None and cost is not None and net is not None
            if net != gross - cost:
                _fail(
                    "net_pnl_mismatch",
                    "$.net_pnl_minor",
                    "must equal gross_pnl_minor - cost_minor",
                )
        elif any(item is not None for item in measurement_values):
            _fail(
                "unavailable_values_forbidden",
                "$.status",
                "unavailable outcomes must keep all measurement values null",
            )
        pit_tier = _enum(raw["pit_tier"], allowed=PIT_TIERS, path="$.pit_tier")
        if pit_tier == "canonical_pit":
            _fail(
                "execution_snapshot_contract_incomplete",
                "$.pit_tier",
                "settled outcomes cannot be canonical until Fill/Reject and PositionState PIT contracts exist",
            )
        leakage = _boolean(raw["known_future_leakage"], path="$.known_future_leakage")
        if pit_tier != "not_pit" and leakage:
            _fail(
                "future_leakage_requires_not_pit",
                "$.known_future_leakage",
                "known future leakage is only valid with not_pit",
            )
        result_ceiling = _text(raw["result_ceiling"], path="$.result_ceiling")
        expected_ceiling = _RESULT_CEILING_BY_PIT[pit_tier]
        if result_ceiling != expected_ceiling:
            _fail(
                "result_ceiling_mismatch",
                "$.result_ceiling",
                f"must equal {expected_ceiling} for {pit_tier}",
            )
        obj = cls(
            schema_version=_schema_version(raw["schema_version"], path="$.schema_version"),
            record_type=_record_type(
                raw["record_type"], expected="v2_settled_outcome", path="$.record_type"
            ),
            outcome_id=_text(raw["outcome_id"], path="$.outcome_id"),
            stable_key=_sha256(raw["stable_key"], path="$.stable_key"),
            revision_number=revision,
            previous_outcome_id=previous_id,
            previous_outcome_record_hash=previous_hash,
            decision_id=_text(raw["decision_id"], path="$.decision_id"),
            decision_hash=_sha256(raw["decision_hash"], path="$.decision_hash"),
            decision_record_hash=_sha256(
                raw["decision_record_hash"], path="$.decision_record_hash"
            ),
            order_intent_id=_text(raw["order_intent_id"], path="$.order_intent_id"),
            order_intent_hash=_sha256(
                raw["order_intent_hash"], path="$.order_intent_hash"
            ),
            order_intent_record_hash=_sha256(
                raw["order_intent_record_hash"],
                path="$.order_intent_record_hash",
            ),
            candidate_pool_id=_text(
                raw["candidate_pool_id"], path="$.candidate_pool_id"
            ),
            candidate_pool_hash=_sha256(
                raw["candidate_pool_hash"], path="$.candidate_pool_hash"
            ),
            candidate_pool_record_hash=_sha256(
                raw["candidate_pool_record_hash"],
                path="$.candidate_pool_record_hash",
            ),
            fill_snapshot_id=_text(
                raw["fill_snapshot_id"], path="$.fill_snapshot_id"
            ),
            fill_snapshot_sha256=_sha256(
                raw["fill_snapshot_sha256"], path="$.fill_snapshot_sha256"
            ),
            position_snapshot_id=_text(
                raw["position_snapshot_id"], path="$.position_snapshot_id"
            ),
            position_snapshot_sha256=_sha256(
                raw["position_snapshot_sha256"], path="$.position_snapshot_sha256"
            ),
            settlement_evidence_record_ids=evidence_ids,
            settlement_evidence_snapshot_sha256=_sha256(
                raw["settlement_evidence_snapshot_sha256"],
                path="$.settlement_evidence_snapshot_sha256",
            ),
            horizon=_text(raw["horizon"], path="$.horizon"),
            entry_session_id=_text(
                raw["entry_session_id"], path="$.entry_session_id"
            ),
            entry_at=entry_at,
            exit_session_id=_text(raw["exit_session_id"], path="$.exit_session_id"),
            exit_at=exit_at,
            settled_at=settled_at,
            recorded_at=recorded_at,
            status=status,
            reason_code=_text(raw["reason_code"], path="$.reason_code"),
            reason=_text(raw["reason"], path="$.reason"),
            basis_notional_minor=basis_notional,
            currency=currency,
            gross_pnl_minor=gross,
            cost_minor=cost,
            net_pnl_minor=net,
            cost_rule_id=_text(raw["cost_rule_id"], path="$.cost_rule_id"),
            cost_rule_version=_text(
                raw["cost_rule_version"], path="$.cost_rule_version"
            ),
            cost_rule_sha256=_sha256(
                raw["cost_rule_sha256"], path="$.cost_rule_sha256"
            ),
            comparison_rule_id=_text(
                raw["comparison_rule_id"], path="$.comparison_rule_id"
            ),
            comparison_rule_version=_text(
                raw["comparison_rule_version"], path="$.comparison_rule_version"
            ),
            comparison_rule_sha256=_sha256(
                raw["comparison_rule_sha256"], path="$.comparison_rule_sha256"
            ),
            input_snapshot_sha256=_sha256(
                raw["input_snapshot_sha256"], path="$.input_snapshot_sha256"
            ),
            pit_tier=pit_tier,
            result_ceiling=result_ceiling,
            known_future_leakage=leakage,
            measurement_only=_require_true(
                raw["measurement_only"],
                path="$.measurement_only",
                code="measurement_only_required",
            ),
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
        return {field: _plain(getattr(self, field)) for field in self.__dataclass_fields__}

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class ReplacementValue:
    schema_version: int
    record_type: str
    replacement_value_id: str
    stable_key: str
    revision_number: int
    previous_replacement_value_id: str | None
    previous_replacement_value_record_hash: str | None
    settled_outcome_id: str
    settled_outcome_hash: str
    settled_outcome_record_hash: str
    candidate_pool_id: str
    candidate_pool_hash: str
    candidate_pool_record_hash: str
    comparator_role: str
    comparator_reference_id: str
    comparator_reference_snapshot_sha256: str
    comparator_evidence_record_ids: tuple[str, ...]
    comparator_evidence_snapshot_sha256: str
    comparison_rule_id: str
    comparison_rule_version: str
    comparison_rule_sha256: str
    status: str
    reason_code: str
    reason: str
    basis_notional_minor: int | None
    currency: str | None
    strategy_value_minor: int | None
    comparator_value_minor: int | None
    replacement_value_minor: int | None
    settled_at: str
    recorded_at: str
    input_snapshot_sha256: str
    pit_tier: str
    result_ceiling: str
    known_future_leakage: bool
    measurement_only: bool
    trade_enabled: bool
    semantic_hash: str
    record_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReplacementValue":
        raw = _mapping(value, path="$")
        _check_fields(raw, required=set(cls.__dataclass_fields__), path="$")
        revision, previous_id, previous_hash = _revision_identity(
            revision_number=raw["revision_number"],
            previous_id=raw["previous_replacement_value_id"],
            previous_hash=raw["previous_replacement_value_record_hash"],
            path="$",
        )
        evidence_ids = _string_tuple(
            raw["comparator_evidence_record_ids"],
            path="$.comparator_evidence_record_ids",
            allow_empty=True,
        )
        settled_at, settled_dt = _instant(raw["settled_at"], path="$.settled_at")
        recorded_at, recorded_dt = _instant(raw["recorded_at"], path="$.recorded_at")
        if settled_dt > recorded_dt:
            _fail(
                "invalid_replacement_chronology",
                "$.settled_at",
                "settled_at must not follow recorded_at",
            )
        status = _enum(
            raw["status"], allowed=_REPLACEMENT_STATUSES, path="$.status"
        )
        basis_notional = _optional_integer(
            raw["basis_notional_minor"],
            path="$.basis_notional_minor",
            minimum=1,
        )
        currency = _optional_currency(raw["currency"], path="$.currency")
        strategy = _optional_integer(
            raw["strategy_value_minor"], path="$.strategy_value_minor"
        )
        comparator = _optional_integer(
            raw["comparator_value_minor"], path="$.comparator_value_minor"
        )
        replacement = _optional_integer(
            raw["replacement_value_minor"], path="$.replacement_value_minor"
        )
        measurement_values = (
            basis_notional,
            currency,
            strategy,
            comparator,
            replacement,
        )
        if status == "computed":
            if not evidence_ids:
                _fail(
                    "computed_evidence_required",
                    "$.comparator_evidence_record_ids",
                    "computed replacement rows require comparator evidence",
                )
            if any(item is None for item in measurement_values):
                _fail(
                    "computed_values_required",
                    "$.status",
                    "computed replacement rows require all measurement values",
                )
            assert strategy is not None and comparator is not None and replacement is not None
            if replacement != strategy - comparator:
                _fail(
                    "replacement_value_mismatch",
                    "$.replacement_value_minor",
                    "must equal strategy_value_minor - comparator_value_minor",
                )
        elif any(item is not None for item in measurement_values):
            _fail(
                "unavailable_values_forbidden",
                "$.status",
                "unavailable replacement rows must keep measurement values null",
            )
        pit_tier = _enum(raw["pit_tier"], allowed=PIT_TIERS, path="$.pit_tier")
        leakage = _boolean(raw["known_future_leakage"], path="$.known_future_leakage")
        if pit_tier != "not_pit" and leakage:
            _fail(
                "future_leakage_requires_not_pit",
                "$.known_future_leakage",
                "known future leakage is only valid with not_pit",
            )
        result_ceiling = _text(raw["result_ceiling"], path="$.result_ceiling")
        expected_ceiling = _RESULT_CEILING_BY_PIT[pit_tier]
        if result_ceiling != expected_ceiling:
            _fail(
                "result_ceiling_mismatch",
                "$.result_ceiling",
                f"must equal {expected_ceiling} for {pit_tier}",
            )
        obj = cls(
            schema_version=_schema_version(raw["schema_version"], path="$.schema_version"),
            record_type=_record_type(
                raw["record_type"], expected="v2_replacement_value", path="$.record_type"
            ),
            replacement_value_id=_text(
                raw["replacement_value_id"], path="$.replacement_value_id"
            ),
            stable_key=_sha256(raw["stable_key"], path="$.stable_key"),
            revision_number=revision,
            previous_replacement_value_id=previous_id,
            previous_replacement_value_record_hash=previous_hash,
            settled_outcome_id=_text(
                raw["settled_outcome_id"], path="$.settled_outcome_id"
            ),
            settled_outcome_hash=_sha256(
                raw["settled_outcome_hash"], path="$.settled_outcome_hash"
            ),
            settled_outcome_record_hash=_sha256(
                raw["settled_outcome_record_hash"],
                path="$.settled_outcome_record_hash",
            ),
            candidate_pool_id=_text(
                raw["candidate_pool_id"], path="$.candidate_pool_id"
            ),
            candidate_pool_hash=_sha256(
                raw["candidate_pool_hash"], path="$.candidate_pool_hash"
            ),
            candidate_pool_record_hash=_sha256(
                raw["candidate_pool_record_hash"],
                path="$.candidate_pool_record_hash",
            ),
            comparator_role=_enum(
                raw["comparator_role"],
                allowed=_COMPARATOR_ROLES,
                path="$.comparator_role",
            ),
            comparator_reference_id=_text(
                raw["comparator_reference_id"], path="$.comparator_reference_id"
            ),
            comparator_reference_snapshot_sha256=_sha256(
                raw["comparator_reference_snapshot_sha256"],
                path="$.comparator_reference_snapshot_sha256",
            ),
            comparator_evidence_record_ids=evidence_ids,
            comparator_evidence_snapshot_sha256=_sha256(
                raw["comparator_evidence_snapshot_sha256"],
                path="$.comparator_evidence_snapshot_sha256",
            ),
            comparison_rule_id=_text(
                raw["comparison_rule_id"], path="$.comparison_rule_id"
            ),
            comparison_rule_version=_text(
                raw["comparison_rule_version"], path="$.comparison_rule_version"
            ),
            comparison_rule_sha256=_sha256(
                raw["comparison_rule_sha256"], path="$.comparison_rule_sha256"
            ),
            status=status,
            reason_code=_text(raw["reason_code"], path="$.reason_code"),
            reason=_text(raw["reason"], path="$.reason"),
            basis_notional_minor=basis_notional,
            currency=currency,
            strategy_value_minor=strategy,
            comparator_value_minor=comparator,
            replacement_value_minor=replacement,
            settled_at=settled_at,
            recorded_at=recorded_at,
            input_snapshot_sha256=_sha256(
                raw["input_snapshot_sha256"], path="$.input_snapshot_sha256"
            ),
            pit_tier=pit_tier,
            result_ceiling=result_ceiling,
            known_future_leakage=leakage,
            measurement_only=_require_true(
                raw["measurement_only"],
                path="$.measurement_only",
                code="measurement_only_required",
            ),
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
        return {field: _plain(getattr(self, field)) for field in self.__dataclass_fields__}

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
    if contract.known_future_leakage and not record.known_future_leakage:
        _fail(
            "future_leakage_not_propagated",
            "$.known_future_leakage",
            "evidence must propagate leakage from its source contract",
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


def validate_research_claim(
    value: Mapping[str, Any] | ResearchClaim,
) -> ResearchClaim:
    return ResearchClaim.from_dict(
        value.to_dict() if isinstance(value, ResearchClaim) else value
    )


def normalize_research_claim(
    value: Mapping[str, Any] | ResearchClaim,
) -> dict[str, Any]:
    return validate_research_claim(value).to_dict()


def validate_hypothesis_candidate(
    value: Mapping[str, Any] | HypothesisCandidate,
) -> HypothesisCandidate:
    return HypothesisCandidate.from_dict(
        value.to_dict() if isinstance(value, HypothesisCandidate) else value
    )


def normalize_hypothesis_candidate(
    value: Mapping[str, Any] | HypothesisCandidate,
) -> dict[str, Any]:
    return validate_hypothesis_candidate(value).to_dict()


def validate_candidate_pool(
    value: Mapping[str, Any] | CandidatePool,
) -> CandidatePool:
    return CandidatePool.from_dict(
        value.to_dict() if isinstance(value, CandidatePool) else value
    )


def normalize_candidate_pool(
    value: Mapping[str, Any] | CandidatePool,
) -> dict[str, Any]:
    return validate_candidate_pool(value).to_dict()


def validate_decision_record(
    value: Mapping[str, Any] | DecisionRecord,
) -> DecisionRecord:
    return DecisionRecord.from_dict(
        value.to_dict() if isinstance(value, DecisionRecord) else value
    )


def normalize_decision_record(
    value: Mapping[str, Any] | DecisionRecord,
) -> dict[str, Any]:
    return validate_decision_record(value).to_dict()


def validate_order_intent(
    value: Mapping[str, Any] | OrderIntent,
) -> OrderIntent:
    return OrderIntent.from_dict(
        value.to_dict() if isinstance(value, OrderIntent) else value
    )


def normalize_order_intent(
    value: Mapping[str, Any] | OrderIntent,
) -> dict[str, Any]:
    return validate_order_intent(value).to_dict()


def validate_settled_outcome(
    value: Mapping[str, Any] | SettledOutcome,
) -> SettledOutcome:
    return SettledOutcome.from_dict(
        value.to_dict() if isinstance(value, SettledOutcome) else value
    )


def normalize_settled_outcome(
    value: Mapping[str, Any] | SettledOutcome,
) -> dict[str, Any]:
    return validate_settled_outcome(value).to_dict()


def validate_replacement_value(
    value: Mapping[str, Any] | ReplacementValue,
) -> ReplacementValue:
    return ReplacementValue.from_dict(
        value.to_dict() if isinstance(value, ReplacementValue) else value
    )


def normalize_replacement_value(
    value: Mapping[str, Any] | ReplacementValue,
) -> dict[str, Any]:
    return validate_replacement_value(value).to_dict()


def _evidence_snapshot_hash(
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    *,
    path: str,
    allow_empty: bool,
) -> str:
    records = [validate_evidence_record(record) for record in evidence_records]
    ids = [record.evidence_id for record in records]
    if not records and not allow_empty:
        _fail(
            "nonempty_list_required",
            path,
            "must contain at least one evidence record",
        )
    if len(ids) != len(set(ids)):
        _fail("duplicate_evidence_id", path, "evidence ids must be unique")
    return canonical_hash(
        [
            {"evidence_id": record.evidence_id, "semantic_hash": record.semantic_hash}
            for record in sorted(records, key=lambda item: item.evidence_id)
        ]
    )


def research_evidence_snapshot_hash(
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
) -> str:
    return _evidence_snapshot_hash(
        evidence_records, path="$.evidence_records", allow_empty=False
    )


def research_claim_snapshot_hash(
    claims: Sequence[Mapping[str, Any] | ResearchClaim],
) -> str:
    records = [validate_research_claim(claim) for claim in claims]
    ids = [record.claim_id for record in records]
    if not records:
        _fail(
            "nonempty_list_required",
            "$.research_claims",
            "must contain at least one research claim",
        )
    if len(ids) != len(set(ids)):
        _fail("duplicate_claim_id", "$.research_claims", "claim ids must be unique")
    return canonical_hash(
        [
            {"claim_id": record.claim_id, "semantic_hash": record.semantic_hash}
            for record in sorted(records, key=lambda item: item.claim_id)
        ]
    )


def universe_event_snapshot_hash(
    events: Sequence[Mapping[str, Any] | UniverseEvent],
) -> str:
    records = [validate_universe_event(event) for event in events]
    ids = [record.event_id for record in records]
    if not records:
        _fail(
            "nonempty_list_required",
            "$.universe_events",
            "must contain at least one universe event",
        )
    if len(ids) != len(set(ids)):
        _fail("duplicate_universe_event_id", "$.universe_events", "event ids must be unique")
    return canonical_hash(
        [
            {"event_id": record.event_id, "semantic_hash": record.semantic_hash}
            for record in sorted(records, key=lambda item: item.event_id)
        ]
    )


def candidate_entry_input_snapshot_hash(
    *,
    hypothesis_candidate: Mapping[str, Any] | HypothesisCandidate,
    universe_event: Mapping[str, Any] | UniverseEvent,
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    generator_rule_sha256: str,
) -> str:
    hypothesis = validate_hypothesis_candidate(hypothesis_candidate)
    event = validate_universe_event(universe_event)
    evidence = [validate_evidence_record(item) for item in evidence_records]
    evidence_ids = [item.evidence_id for item in evidence]
    if not evidence:
        _fail(
            "nonempty_list_required",
            "$.evidence_records",
            "candidate entry requires evidence",
        )
    if len(evidence_ids) != len(set(evidence_ids)):
        _fail("duplicate_evidence_id", "$.evidence_records", "evidence ids must be unique")
    return canonical_hash(
        {
            "hypothesis_candidate": {
                "candidate_id": hypothesis.candidate_id,
                "semantic_hash": hypothesis.semantic_hash,
            },
            "universe_event": {
                "event_id": event.event_id,
                "semantic_hash": event.semantic_hash,
            },
            "evidence_records": [
                {"evidence_id": item.evidence_id, "semantic_hash": item.semantic_hash}
                for item in sorted(evidence, key=lambda item: item.evidence_id)
            ],
            "generator_rule_sha256": _sha256(
                generator_rule_sha256, path="$.generator_rule_sha256"
            ),
        }
    )


def candidate_pool_input_snapshot_hash(
    *,
    hypothesis_candidate: Mapping[str, Any] | HypothesisCandidate,
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    universe_events: Sequence[Mapping[str, Any] | UniverseEvent],
    entries: Sequence[Mapping[str, Any] | CandidatePoolEntry],
    comparators: Sequence[Mapping[str, Any] | CandidatePoolComparator],
    generator_rule_sha256: str,
    ranking_rule_sha256: str,
    universe_id: str,
    run_date: str,
    calendar_session_id: str,
    data_cutoff: str,
) -> str:
    hypothesis = validate_hypothesis_candidate(hypothesis_candidate)
    evidence = [validate_evidence_record(item) for item in evidence_records]
    events = [validate_universe_event(item) for item in universe_events]
    normalized_entries = [
        CandidatePoolEntry.from_dict(
            item.to_dict() if isinstance(item, CandidatePoolEntry) else item,
            path="$.entries[]",
        )
        for item in entries
    ]
    normalized_comparators = [
        CandidatePoolComparator.from_dict(
            item.to_dict() if isinstance(item, CandidatePoolComparator) else item,
            path="$.comparators[]",
        )
        for item in comparators
    ]
    return canonical_hash(
        {
            "hypothesis_candidate": {
                "candidate_id": hypothesis.candidate_id,
                "semantic_hash": hypothesis.semantic_hash,
            },
            "evidence_snapshot_sha256": research_evidence_snapshot_hash(evidence),
            "universe_event_snapshot_sha256": universe_event_snapshot_hash(events),
            "entries": [
                item.to_dict()
                for item in sorted(
                    normalized_entries, key=lambda entry: entry.candidate_entry_id
                )
            ],
            "comparators": [
                item.to_dict()
                for item in sorted(normalized_comparators, key=lambda comparator: comparator.role)
            ],
            "generator_rule_sha256": _sha256(
                generator_rule_sha256, path="$.generator_rule_sha256"
            ),
            "ranking_rule_sha256": _sha256(
                ranking_rule_sha256, path="$.ranking_rule_sha256"
            ),
            "universe_id": _text(universe_id, path="$.universe_id"),
            "run_date": _calendar_date(run_date, path="$.run_date"),
            "calendar_session_id": _text(
                calendar_session_id, path="$.calendar_session_id"
            ),
            "data_cutoff": _instant(data_cutoff, path="$.data_cutoff")[0],
        }
    )


def decision_input_snapshot_hash(
    *,
    candidate_pool: Mapping[str, Any] | CandidatePool,
    policy_arm: str,
    policy_snapshot: Mapping[str, Any],
    decision_engine_id: str,
    decision_engine_version: str,
    decision_engine_sha256: str,
    decision_context_id: str,
    decision_context_sha256: str,
    execution_rule_id: str,
    execution_rule_version: str,
    execution_rule_sha256: str,
    cost_rule_id: str,
    cost_rule_version: str,
    cost_rule_sha256: str,
    comparison_rule_id: str,
    comparison_rule_version: str,
    comparison_rule_sha256: str,
    items: Sequence[Mapping[str, Any] | DecisionItem],
    run_id: str,
    run_date: str,
    calendar_session_id: str,
    data_cutoff: str,
    expected_horizon: str,
) -> str:
    pool = validate_candidate_pool(candidate_pool)
    normalized_items = [
        DecisionItem.from_dict(
            item.to_dict() if isinstance(item, DecisionItem) else item,
            path="$.items[]",
        )
        for item in items
    ]
    item_ids = [item.decision_item_id for item in normalized_items]
    if len(item_ids) != len(set(item_ids)):
        _fail("duplicate_decision_item_id", "$.items", "decision item ids must be unique")
    return canonical_hash(
        {
            "candidate_pool": {
                "candidate_pool_id": pool.candidate_pool_id,
                "semantic_hash": pool.semantic_hash,
                "record_hash": pool.record_hash,
            },
            "policy_arm": _enum(
                policy_arm, allowed=_DECISION_POLICY_ARMS, path="$.policy_arm"
            ),
            "policy_snapshot": _plain(
                _policy_snapshot(policy_snapshot, path="$.policy_snapshot")
            ),
            "decision_engine": {
                "id": _text(decision_engine_id, path="$.decision_engine_id"),
                "version": _text(
                    decision_engine_version, path="$.decision_engine_version"
                ),
                "sha256": _sha256(
                    decision_engine_sha256, path="$.decision_engine_sha256"
                ),
            },
            "decision_context": {
                "id": _text(decision_context_id, path="$.decision_context_id"),
                "sha256": _sha256(
                    decision_context_sha256, path="$.decision_context_sha256"
                ),
            },
            "execution_rule": {
                "id": _text(execution_rule_id, path="$.execution_rule_id"),
                "version": _text(
                    execution_rule_version, path="$.execution_rule_version"
                ),
                "sha256": _sha256(
                    execution_rule_sha256, path="$.execution_rule_sha256"
                ),
            },
            "cost_rule": {
                "id": _text(cost_rule_id, path="$.cost_rule_id"),
                "version": _text(cost_rule_version, path="$.cost_rule_version"),
                "sha256": _sha256(cost_rule_sha256, path="$.cost_rule_sha256"),
            },
            "comparison_rule": {
                "id": _text(comparison_rule_id, path="$.comparison_rule_id"),
                "version": _text(
                    comparison_rule_version, path="$.comparison_rule_version"
                ),
                "sha256": _sha256(
                    comparison_rule_sha256, path="$.comparison_rule_sha256"
                ),
            },
            "items": [
                item.to_dict()
                for item in sorted(
                    normalized_items, key=lambda item: item.candidate_entry_id
                )
            ],
            "run_id": _text(run_id, path="$.run_id"),
            "run_date": _calendar_date(run_date, path="$.run_date"),
            "calendar_session_id": _text(
                calendar_session_id, path="$.calendar_session_id"
            ),
            "data_cutoff": _instant(data_cutoff, path="$.data_cutoff")[0],
            "expected_horizon": _text(
                expected_horizon, path="$.expected_horizon"
            ),
        }
    )


def order_intent_input_snapshot_hash(
    *,
    decision_record: Mapping[str, Any] | DecisionRecord,
    decision_item_id: str,
    side: str,
    quantity_micros: int | None,
    notional_minor: int | None,
    currency: str,
    order_type: str,
    limit_price_minor: int | None,
    stop_price_minor: int | None,
    time_in_force: str,
    not_before: str,
    expires_at: str,
    calendar_session_id: str,
    execution_rule_id: str,
    execution_rule_version: str,
    execution_rule_sha256: str,
    created_at: str,
) -> str:
    decision = validate_decision_record(decision_record)
    quantity = _optional_integer(
        quantity_micros, path="$.quantity_micros", minimum=1
    )
    notional = _optional_integer(
        notional_minor, path="$.notional_minor", minimum=1
    )
    if (quantity is None) == (notional is None):
        _fail(
            "order_size_xor_required",
            "$.quantity_micros",
            "exactly one of quantity or notional is required",
        )
    normalized_order_type = _enum(
        order_type, allowed=_ORDER_TYPES, path="$.order_type"
    )
    limit_price = _optional_integer(
        limit_price_minor, path="$.limit_price_minor", minimum=1
    )
    stop_price = _optional_integer(
        stop_price_minor, path="$.stop_price_minor", minimum=1
    )
    required_prices = {
        "market": (False, False),
        "limit": (True, False),
        "stop": (False, True),
        "stop_limit": (True, True),
    }[normalized_order_type]
    if (limit_price is not None, stop_price is not None) != required_prices:
        _fail(
            "order_price_fields_mismatch",
            "$.order_type",
            "limit and stop prices must exactly match the order type",
        )
    return canonical_hash(
        {
            "decision": {
                "decision_id": decision.decision_id,
                "semantic_hash": decision.semantic_hash,
                "record_hash": decision.record_hash,
            },
            "decision_item_id": _text(decision_item_id, path="$.decision_item_id"),
            "side": _enum(side, allowed=_ORDER_SIDES, path="$.side"),
            "quantity_micros": quantity,
            "notional_minor": notional,
            "currency": _optional_currency(currency, path="$.currency"),
            "order_type": normalized_order_type,
            "limit_price_minor": limit_price,
            "stop_price_minor": stop_price,
            "time_in_force": _enum(
                time_in_force,
                allowed=_TIME_IN_FORCE_VALUES,
                path="$.time_in_force",
            ),
            "not_before": _instant(not_before, path="$.not_before")[0],
            "expires_at": _instant(expires_at, path="$.expires_at")[0],
            "calendar_session_id": _text(
                calendar_session_id, path="$.calendar_session_id"
            ),
            "execution_rule": {
                "id": _text(execution_rule_id, path="$.execution_rule_id"),
                "version": _text(
                    execution_rule_version, path="$.execution_rule_version"
                ),
                "sha256": _sha256(
                    execution_rule_sha256, path="$.execution_rule_sha256"
                ),
            },
            "created_at": _instant(created_at, path="$.created_at")[0],
        }
    )


def settlement_evidence_snapshot_hash(
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
) -> str:
    records = [validate_evidence_record(record) for record in evidence_records]
    ids = [record.evidence_id for record in records]
    if len(ids) != len(set(ids)):
        _fail(
            "duplicate_evidence_id",
            "$.settlement_evidence_records",
            "evidence ids must be unique",
        )
    return canonical_hash(
        [
            {
                "evidence_id": record.evidence_id,
                "semantic_hash": record.semantic_hash,
                "record_hash": record.record_hash,
            }
            for record in sorted(records, key=lambda item: item.evidence_id)
        ]
    )


def settled_outcome_stable_key(*, order_intent_id: str, horizon: str) -> str:
    return canonical_hash(
        {
            "order_intent_id": _text(
                order_intent_id, path="$.order_intent_id"
            ),
            "horizon": _text(horizon, path="$.horizon"),
        }
    )


def settled_outcome_input_snapshot_hash(
    *,
    decision_record: Mapping[str, Any] | DecisionRecord,
    order_intent: Mapping[str, Any] | OrderIntent,
    settlement_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    fill_snapshot_id: str,
    fill_snapshot_sha256: str,
    position_snapshot_id: str,
    position_snapshot_sha256: str,
    horizon: str,
    entry_session_id: str,
    entry_at: str,
    exit_session_id: str,
    exit_at: str,
    cost_rule_id: str,
    cost_rule_version: str,
    cost_rule_sha256: str,
    comparison_rule_id: str,
    comparison_rule_version: str,
    comparison_rule_sha256: str,
) -> str:
    decision = validate_decision_record(decision_record)
    intent = validate_order_intent(order_intent)
    evidence = [validate_evidence_record(item) for item in settlement_evidence_records]
    return canonical_hash(
        {
            "decision": {
                "decision_id": decision.decision_id,
                "semantic_hash": decision.semantic_hash,
                "record_hash": decision.record_hash,
            },
            "order_intent": {
                "order_intent_id": intent.order_intent_id,
                "semantic_hash": intent.semantic_hash,
                "record_hash": intent.record_hash,
            },
            "candidate_pool": {
                "candidate_pool_id": decision.candidate_pool_id,
                "semantic_hash": decision.candidate_pool_hash,
                "record_hash": decision.candidate_pool_record_hash,
            },
            "fill_snapshot": {
                "id": _text(fill_snapshot_id, path="$.fill_snapshot_id"),
                "sha256": _sha256(
                    fill_snapshot_sha256, path="$.fill_snapshot_sha256"
                ),
            },
            "position_snapshot": {
                "id": _text(position_snapshot_id, path="$.position_snapshot_id"),
                "sha256": _sha256(
                    position_snapshot_sha256, path="$.position_snapshot_sha256"
                ),
            },
            "settlement_evidence_snapshot_sha256": settlement_evidence_snapshot_hash(
                evidence
            ),
            "horizon": _text(horizon, path="$.horizon"),
            "entry_session_id": _text(
                entry_session_id, path="$.entry_session_id"
            ),
            "entry_at": _instant(entry_at, path="$.entry_at")[0],
            "exit_session_id": _text(exit_session_id, path="$.exit_session_id"),
            "exit_at": _instant(exit_at, path="$.exit_at")[0],
            "cost_rule": {
                "id": _text(cost_rule_id, path="$.cost_rule_id"),
                "version": _text(cost_rule_version, path="$.cost_rule_version"),
                "sha256": _sha256(cost_rule_sha256, path="$.cost_rule_sha256"),
            },
            "comparison_rule": {
                "id": _text(comparison_rule_id, path="$.comparison_rule_id"),
                "version": _text(
                    comparison_rule_version, path="$.comparison_rule_version"
                ),
                "sha256": _sha256(
                    comparison_rule_sha256, path="$.comparison_rule_sha256"
                ),
            },
        }
    )


def replacement_value_stable_key(
    *, settled_outcome_stable_key: str, comparator_role: str
) -> str:
    return canonical_hash(
        {
            "settled_outcome_stable_key": _sha256(
                settled_outcome_stable_key, path="$.settled_outcome_stable_key"
            ),
            "comparator_role": _enum(
                comparator_role,
                allowed=_COMPARATOR_ROLES,
                path="$.comparator_role",
            ),
        }
    )


def replacement_value_input_snapshot_hash(
    *,
    settled_outcome: Mapping[str, Any] | SettledOutcome,
    candidate_pool: Mapping[str, Any] | CandidatePool,
    comparator: Mapping[str, Any] | CandidatePoolComparator,
    comparator_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    comparison_rule_id: str,
    comparison_rule_version: str,
    comparison_rule_sha256: str,
) -> str:
    outcome = validate_settled_outcome(settled_outcome)
    pool = validate_candidate_pool(candidate_pool)
    comparator_record = CandidatePoolComparator.from_dict(
        comparator.to_dict() if isinstance(comparator, CandidatePoolComparator) else comparator,
        path="$.comparator",
    )
    evidence = [validate_evidence_record(item) for item in comparator_evidence_records]
    return canonical_hash(
        {
            "settled_outcome": {
                "outcome_id": outcome.outcome_id,
                "semantic_hash": outcome.semantic_hash,
                "record_hash": outcome.record_hash,
            },
            "candidate_pool": {
                "candidate_pool_id": pool.candidate_pool_id,
                "semantic_hash": pool.semantic_hash,
                "record_hash": pool.record_hash,
            },
            "comparator": comparator_record.to_dict(),
            "comparator_evidence_snapshot_sha256": settlement_evidence_snapshot_hash(
                evidence
            ),
            "comparison_rule": {
                "id": _text(comparison_rule_id, path="$.comparison_rule_id"),
                "version": _text(
                    comparison_rule_version, path="$.comparison_rule_version"
                ),
                "sha256": _sha256(
                    comparison_rule_sha256, path="$.comparison_rule_sha256"
                ),
            },
        }
    )


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
    if any(item.known_future_leakage for item in referenced) and not record.known_future_leakage:
        _fail(
            "future_leakage_not_propagated",
            "$.known_future_leakage",
            "universe event must propagate leakage from referenced evidence",
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


def _validated_source_registry(
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
) -> dict[str, SourceContract]:
    by_id: dict[str, SourceContract] = {}
    for item in source_contracts:
        source = validate_source_contract(item)
        if source.source_contract_id in by_id:
            _fail(
                "duplicate_source_contract_id",
                "$.source_contracts",
                f"duplicate source contract id {source.source_contract_id}",
            )
        by_id[source.source_contract_id] = source
    return by_id


def _validated_evidence_registry(
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
) -> tuple[dict[str, EvidenceRecord], dict[str, SourceContract]]:
    sources = _validated_source_registry(source_contracts)
    by_id: dict[str, EvidenceRecord] = {}
    for item in evidence_records:
        evidence = validate_evidence_record(item)
        if evidence.evidence_id in by_id:
            _fail(
                "duplicate_evidence_id",
                "$.evidence_records",
                f"duplicate evidence id {evidence.evidence_id}",
            )
        source = sources.get(evidence.source_contract_id)
        if source is None:
            _fail(
                "unresolved_source_contract_id",
                "$.source_contracts",
                f"no source contract for {evidence.source_contract_id}",
            )
        by_id[evidence.evidence_id] = validate_evidence_against_source(
            evidence, source
        )
    return by_id, sources


def validate_research_claim_against_evidence(
    claim: Mapping[str, Any] | ResearchClaim,
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
) -> ResearchClaim:
    record = validate_research_claim(claim)
    evidence_by_id, _ = _validated_evidence_registry(
        evidence_records, source_contracts
    )
    missing = [item for item in record.evidence_record_ids if item not in evidence_by_id]
    if missing:
        _fail(
            "unresolved_evidence_id",
            "$.evidence_record_ids",
            f"unresolved ids: {', '.join(missing)}",
        )
    referenced = [evidence_by_id[item] for item in record.evidence_record_ids]
    expected_snapshot = research_evidence_snapshot_hash(referenced)
    if record.evidence_snapshot_sha256 != expected_snapshot:
        _fail(
            "evidence_snapshot_hash_mismatch",
            "$.evidence_snapshot_sha256",
            f"expected {expected_snapshot}, got {record.evidence_snapshot_sha256}",
        )
    weakest = min(referenced, key=lambda item: _PIT_RANK[item.pit_tier]).pit_tier
    if _PIT_RANK[record.pit_tier] > _PIT_RANK[weakest]:
        _fail(
            "pit_tier_exceeds_evidence",
            "$.pit_tier",
            "research claim tier exceeds its weakest evidence record",
        )
    if any(item.known_future_leakage for item in referenced) and not record.known_future_leakage:
        _fail(
            "future_leakage_not_propagated",
            "$.known_future_leakage",
            "claim must propagate leakage from referenced evidence",
        )
    _, claim_as_of_dt = _instant(record.as_of, path="$.as_of")
    _, claim_created_dt = _instant(record.created_at, path="$.created_at")
    for item in referenced:
        _, evidence_known_dt = _instant(item.known_at, path="$.evidence.known_at")
        if evidence_known_dt > claim_as_of_dt:
            _fail(
                "claim_cutoff_before_evidence",
                "$.as_of",
                "claim cutoff cannot precede referenced evidence known_at",
            )
        _, evidence_recorded_dt = _instant(
            item.recorded_at, path="$.evidence.recorded_at"
        )
        if evidence_recorded_dt > claim_created_dt:
            _fail(
                "evidence_recorded_after_claim_creation",
                "$.evidence.recorded_at",
                "referenced evidence must be recorded before the claim is created",
            )
    return record


def validate_hypothesis_candidate_against_claims(
    candidate: Mapping[str, Any] | HypothesisCandidate,
    research_claims: Sequence[Mapping[str, Any] | ResearchClaim],
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
) -> HypothesisCandidate:
    record = validate_hypothesis_candidate(candidate)
    claims_by_id: dict[str, ResearchClaim] = {}
    for item in research_claims:
        claim = validate_research_claim(item)
        if claim.claim_id in claims_by_id:
            _fail(
                "duplicate_claim_id",
                "$.research_claims",
                f"duplicate claim id {claim.claim_id}",
            )
        claims_by_id[claim.claim_id] = claim
    missing = [item for item in record.research_claim_ids if item not in claims_by_id]
    if missing:
        _fail(
            "unresolved_claim_id",
            "$.research_claim_ids",
            f"unresolved ids: {', '.join(missing)}",
        )
    referenced = [
        validate_research_claim_against_evidence(
            claims_by_id[item], evidence_records, source_contracts
        )
        for item in record.research_claim_ids
    ]
    expected_snapshot = research_claim_snapshot_hash(referenced)
    if record.claim_snapshot_sha256 != expected_snapshot:
        _fail(
            "claim_snapshot_hash_mismatch",
            "$.claim_snapshot_sha256",
            f"expected {expected_snapshot}, got {record.claim_snapshot_sha256}",
        )
    weakest = min(referenced, key=lambda item: _PIT_RANK[item.pit_tier]).pit_tier
    if _PIT_RANK[record.pit_tier] > _PIT_RANK[weakest]:
        _fail(
            "pit_tier_exceeds_claim",
            "$.pit_tier",
            "hypothesis tier exceeds its weakest research claim",
        )
    if any(item.known_future_leakage for item in referenced) and not record.known_future_leakage:
        _fail(
            "future_leakage_not_propagated",
            "$.known_future_leakage",
            "hypothesis must propagate leakage from referenced claims",
        )
    _, cutoff_dt = _instant(record.data_cutoff, path="$.data_cutoff")
    _, created_dt = _instant(record.created_at, path="$.created_at")
    for item in referenced:
        _, claim_known_dt = _instant(item.known_at, path="$.claim.known_at")
        if claim_known_dt > cutoff_dt:
            _fail(
                "hypothesis_cutoff_before_claim",
                "$.data_cutoff",
                "hypothesis cutoff cannot precede claim known_at",
            )
        _, claim_recorded_dt = _instant(item.recorded_at, path="$.claim.recorded_at")
        if claim_recorded_dt > created_dt:
            _fail(
                "claim_recorded_after_hypothesis_creation",
                "$.claim.recorded_at",
                "referenced claims must be recorded before the hypothesis is created",
            )
    return record


def _validate_universe_event_chains(
    events: Sequence[UniverseEvent],
) -> dict[str, UniverseEvent]:
    by_security: dict[str, list[UniverseEvent]] = {}
    for event in events:
        by_security.setdefault(event.security_mapping.security_id, []).append(event)
    latest: dict[str, UniverseEvent] = {}
    for security_id, chain in by_security.items():
        ordered = sorted(
            chain,
            key=lambda item: (
                _instant(item.effective_at, path="$.universe_event.effective_at")[1],
                item.event_id,
            ),
        )
        first = ordered[0]
        if first.event_type != "discovery":
            _fail(
                "incomplete_universe_event_chain",
                "$.universe_event_ids",
                f"{security_id} snapshot does not start with discovery",
            )
        previous = first
        for current in ordered[1:]:
            _, previous_effective_dt = _instant(
                previous.effective_at, path="$.universe_event.effective_at"
            )
            _, current_effective_dt = _instant(
                current.effective_at, path="$.universe_event.effective_at"
            )
            _, current_decided_dt = _instant(
                current.decided_at, path="$.universe_event.decided_at"
            )
            if current_effective_dt <= previous_effective_dt:
                _fail(
                    "nonmonotonic_universe_event_chain",
                    "$.universe_event_ids",
                    f"{security_id} event effective_at values must increase",
                )
            if current_decided_dt < previous_effective_dt:
                _fail(
                    "universe_transition_before_prior_effective",
                    "$.universe_event_ids",
                    f"{security_id} cannot transition before its prior state is effective",
                )
            if (
                current.previous_event_id != previous.event_id
                or current.previous_event_hash != previous.event_hash
                or current.from_state != previous.to_state
            ):
                _fail(
                    "broken_universe_event_chain",
                    "$.universe_event_ids",
                    f"{security_id} event does not bind the immediately prior state",
                )
            previous = current
        latest[security_id] = previous
    return latest


def validate_candidate_pool_against_inputs(
    pool: Mapping[str, Any] | CandidatePool,
    hypothesis_candidate: Mapping[str, Any] | HypothesisCandidate,
    research_claims: Sequence[Mapping[str, Any] | ResearchClaim],
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    universe_events: Sequence[Mapping[str, Any] | UniverseEvent],
) -> CandidatePool:
    record = validate_candidate_pool(pool)
    hypothesis = validate_hypothesis_candidate_against_claims(
        hypothesis_candidate, research_claims, evidence_records, source_contracts
    )
    if record.hypothesis_candidate_id != hypothesis.candidate_id:
        _fail(
            "hypothesis_candidate_id_mismatch",
            "$.hypothesis_candidate_id",
            "does not match the supplied hypothesis candidate",
        )
    if record.hypothesis_candidate_hash != hypothesis.semantic_hash:
        _fail(
            "hypothesis_candidate_hash_mismatch",
            "$.hypothesis_candidate_hash",
            "does not bind the supplied hypothesis semantic hash",
        )
    comparator_identity = {"cash": "cash", "spy": "SPY", "qqq": "QQQ", "v1": "V1"}
    for comparator in record.comparators:
        if comparator.reference_id != comparator_identity[comparator.role]:
            _fail(
                "comparator_identity_mismatch",
                "$.comparators",
                "cash, SPY, QQQ, and V1 roles must bind their frozen hypothesis identities",
            )
    evidence_by_id, _ = _validated_evidence_registry(
        evidence_records, source_contracts
    )
    if set(evidence_by_id) != set(record.evidence_record_ids):
        _fail(
            "evidence_snapshot_membership_mismatch",
            "$.evidence_record_ids",
            "supplied evidence must exactly match the frozen pool snapshot",
        )
    referenced_evidence = [evidence_by_id[item] for item in record.evidence_record_ids]
    expected_evidence_snapshot = research_evidence_snapshot_hash(referenced_evidence)
    if record.evidence_snapshot_sha256 != expected_evidence_snapshot:
        _fail(
            "evidence_snapshot_hash_mismatch",
            "$.evidence_snapshot_sha256",
            f"expected {expected_evidence_snapshot}, got {record.evidence_snapshot_sha256}",
        )
    events: list[UniverseEvent] = []
    event_ids: set[str] = set()
    for item in universe_events:
        event = validate_universe_event_against_evidence(
            item, evidence_records, source_contracts
        )
        if event.event_id in event_ids:
            _fail(
                "duplicate_universe_event_id",
                "$.universe_events",
                f"duplicate universe event id {event.event_id}",
            )
        event_ids.add(event.event_id)
        events.append(event)
    if event_ids != set(record.universe_event_ids):
        _fail(
            "universe_snapshot_membership_mismatch",
            "$.universe_event_ids",
            "supplied events must exactly match the frozen universe snapshot",
        )
    expected_event_snapshot = universe_event_snapshot_hash(events)
    if record.universe_event_snapshot_sha256 != expected_event_snapshot:
        _fail(
            "universe_event_snapshot_hash_mismatch",
            "$.universe_event_snapshot_sha256",
            f"expected {expected_event_snapshot}, got {record.universe_event_snapshot_sha256}",
        )
    _, pool_cutoff_dt = _instant(record.data_cutoff, path="$.data_cutoff")
    _, pool_frozen_dt = _instant(record.frozen_at, path="$.frozen_at")
    for event in events:
        if event.universe_id != record.universe_id:
            _fail(
                "universe_id_mismatch",
                "$.universe_id",
                "all frozen universe events must belong to the pool universe",
            )
        _, event_known_dt = _instant(event.known_at, path="$.universe_event.known_at")
        _, event_effective_dt = _instant(
            event.effective_at, path="$.universe_event.effective_at"
        )
        _, event_recorded_dt = _instant(
            event.recorded_at, path="$.universe_event.recorded_at"
        )
        if event_known_dt > pool_cutoff_dt or event_effective_dt > pool_cutoff_dt:
            _fail(
                "universe_event_after_pool_cutoff",
                "$.data_cutoff",
                "universe events must be known and effective by the pool cutoff",
            )
        if event_recorded_dt > pool_frozen_dt:
            _fail(
                "universe_event_recorded_after_pool_freeze",
                "$.universe_event.recorded_at",
                "universe events must be recorded before the pool freezes",
            )
    latest_by_security = _validate_universe_event_chains(events)
    eligible = {
        (
            event.security_mapping.security_id,
            event.security_mapping.listing_id,
        ): event
        for event in latest_by_security.values()
        if event.to_state == "candidate_eligible"
    }
    entry_keys = {(entry.security_id, entry.listing_id) for entry in record.entries}
    if entry_keys != set(eligible):
        _fail(
            "candidate_surface_incomplete",
            "$.entries",
            "entries must exactly cover securities whose latest universe state is "
            "candidate_eligible",
        )
    event_by_id = {event.event_id: event for event in events}
    required_evidence_ids: set[str] = set()
    claims_by_id = {
        item.claim_id: item
        for item in (validate_research_claim(claim) for claim in research_claims)
    }
    for claim_id in hypothesis.research_claim_ids:
        required_evidence_ids.update(claims_by_id[claim_id].evidence_record_ids)
    for event in events:
        required_evidence_ids.update(event.evidence_record_ids)
    for entry in record.entries:
        required_evidence_ids.update(entry.evidence_record_ids)
        latest_event = eligible[(entry.security_id, entry.listing_id)]
        if entry.universe_event_id != latest_event.event_id:
            _fail(
                "candidate_not_bound_to_latest_universe_event",
                "$.entries",
                "candidate entry must bind the latest eligible universe event",
            )
        if entry.security_mapping_sha256 != latest_event.security_mapping.mapping_sha256:
            _fail(
                "candidate_mapping_hash_mismatch",
                "$.entries",
                "candidate entry must bind the latest universe security mapping",
            )
        entry_evidence: list[EvidenceRecord] = []
        for evidence_id in entry.evidence_record_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                _fail(
                    "unresolved_evidence_id",
                    "$.entries",
                    f"candidate entry references missing evidence {evidence_id}",
                )
            entry_evidence.append(evidence)
            if evidence.security_scope == "instrument":
                mapping = evidence.security_mapping
                if mapping is None:
                    _fail(
                        "candidate_evidence_security_unbound",
                        "$.entries",
                        "instrument evidence must carry an effective security mapping",
                    )
                if (
                    mapping.security_id != entry.security_id
                    or mapping.listing_id != entry.listing_id
                ):
                    _fail(
                        "candidate_evidence_security_mismatch",
                        "$.entries",
                        "instrument evidence must match the candidate security and listing",
                    )
        expected_entry_input = candidate_entry_input_snapshot_hash(
            hypothesis_candidate=hypothesis,
            universe_event=event_by_id[entry.universe_event_id],
            evidence_records=entry_evidence,
            generator_rule_sha256=record.generator_rule_sha256,
        )
        if entry.decision_input_sha256 != expected_entry_input:
            _fail(
                "candidate_entry_input_hash_mismatch",
                "$.entries",
                f"entry {entry.candidate_entry_id} does not bind its decision inputs",
            )
    if required_evidence_ids != set(record.evidence_record_ids):
        _fail(
            "candidate_evidence_surface_incomplete",
            "$.evidence_record_ids",
            "pool evidence must exactly cover universe and candidate entry inputs",
        )
    _, hypothesis_recorded_dt = _instant(
        hypothesis.recorded_at, path="$.hypothesis.recorded_at"
    )
    if hypothesis_recorded_dt > pool_frozen_dt:
        _fail(
            "hypothesis_recorded_after_pool_freeze",
            "$.hypothesis.recorded_at",
            "hypothesis must be recorded before the candidate pool freezes",
        )
    _, hypothesis_cutoff_dt = _instant(
        hypothesis.data_cutoff, path="$.hypothesis.data_cutoff"
    )
    if hypothesis_cutoff_dt > pool_cutoff_dt:
        _fail(
            "pool_cutoff_before_hypothesis",
            "$.data_cutoff",
            "pool cutoff cannot precede the hypothesis data cutoff",
        )
    for evidence in referenced_evidence:
        _, evidence_known_dt = _instant(evidence.known_at, path="$.evidence.known_at")
        _, evidence_recorded_dt = _instant(
            evidence.recorded_at, path="$.evidence.recorded_at"
        )
        if evidence_known_dt > pool_cutoff_dt:
            _fail(
                "pool_cutoff_before_evidence",
                "$.data_cutoff",
                "pool cutoff cannot precede evidence known_at",
            )
        if evidence_recorded_dt > pool_frozen_dt:
            _fail(
                "evidence_recorded_after_pool_freeze",
                "$.evidence.recorded_at",
                "pool evidence must be recorded before the pool freezes",
            )
    pit_inputs = [hypothesis.pit_tier]
    pit_inputs.extend(item.pit_tier for item in referenced_evidence)
    pit_inputs.extend(item.pit_tier for item in events)
    weakest = min(pit_inputs, key=lambda item: _PIT_RANK[item])
    if _PIT_RANK[record.pit_tier] > _PIT_RANK[weakest]:
        _fail(
            "pit_tier_exceeds_pool_inputs",
            "$.pit_tier",
            "candidate pool tier exceeds its weakest frozen input",
        )
    leakage = hypothesis.known_future_leakage or any(
        item.known_future_leakage for item in [*referenced_evidence, *events]
    )
    if leakage and not record.known_future_leakage:
        _fail(
            "future_leakage_not_propagated",
            "$.known_future_leakage",
            "candidate pool must propagate leakage from every input",
        )
    expected_input_snapshot = candidate_pool_input_snapshot_hash(
        hypothesis_candidate=hypothesis,
        evidence_records=referenced_evidence,
        universe_events=events,
        entries=record.entries,
        comparators=record.comparators,
        generator_rule_sha256=record.generator_rule_sha256,
        ranking_rule_sha256=record.ranking_rule_sha256,
        universe_id=record.universe_id,
        run_date=record.run_date,
        calendar_session_id=record.calendar_session_id,
        data_cutoff=record.data_cutoff,
    )
    if record.input_snapshot_sha256 != expected_input_snapshot:
        _fail(
            "input_snapshot_hash_mismatch",
            "$.input_snapshot_sha256",
            f"expected {expected_input_snapshot}, got {record.input_snapshot_sha256}",
        )
    return record


def validate_decision_record_against_candidate_pool(
    decision: Mapping[str, Any] | DecisionRecord,
    candidate_pool: Mapping[str, Any] | CandidatePool,
    hypothesis_candidate: Mapping[str, Any] | HypothesisCandidate,
) -> DecisionRecord:
    record = validate_decision_record(decision)
    pool = validate_candidate_pool(candidate_pool)
    hypothesis = validate_hypothesis_candidate(hypothesis_candidate)
    if (
        pool.hypothesis_candidate_id != hypothesis.candidate_id
        or pool.hypothesis_candidate_hash != hypothesis.semantic_hash
    ):
        _fail(
            "pool_hypothesis_binding_mismatch",
            "$.candidate_pool_id",
            "the supplied pool does not bind the supplied hypothesis",
        )
    if record.candidate_pool_id != pool.candidate_pool_id:
        _fail(
            "candidate_pool_id_mismatch",
            "$.candidate_pool_id",
            "does not match the supplied candidate pool",
        )
    if record.candidate_pool_hash != pool.semantic_hash:
        _fail(
            "candidate_pool_hash_mismatch",
            "$.candidate_pool_hash",
            "does not bind the supplied candidate pool semantic hash",
        )
    if record.candidate_pool_record_hash != pool.record_hash:
        _fail(
            "candidate_pool_record_hash_mismatch",
            "$.candidate_pool_record_hash",
            "does not bind the exact supplied candidate pool record",
        )
    if record.expected_horizon != hypothesis.expected_horizon:
        _fail(
            "decision_horizon_mismatch",
            "$.expected_horizon",
            "must equal the frozen hypothesis expected horizon",
        )
    expected_policy = (
        hypothesis.baseline_policy
        if record.policy_arm == "baseline"
        else hypothesis.treatment_policy
    )
    if canonical_hash(record.policy_snapshot) != canonical_hash(expected_policy):
        _fail(
            "decision_policy_snapshot_mismatch",
            "$.policy_snapshot",
            "must exactly match the frozen hypothesis policy arm",
        )
    if (
        record.run_id != pool.run_id
        or record.run_date != pool.run_date
        or record.calendar_session_id != pool.calendar_session_id
        or record.data_cutoff != pool.data_cutoff
    ):
        _fail(
            "decision_clock_identity_mismatch",
            "$.run_id",
            "run, session, and cutoff must exactly match the candidate pool",
        )
    _, pool_recorded_dt = _instant(pool.recorded_at, path="$.pool.recorded_at")
    _, decided_dt = _instant(record.decided_at, path="$.decided_at")
    if pool_recorded_dt > decided_dt:
        _fail(
            "decision_before_pool_recorded",
            "$.decided_at",
            "the complete candidate pool must be recorded before the decision",
        )
    pool_entries = {item.candidate_entry_id: item for item in pool.entries}
    decision_items = {item.candidate_entry_id: item for item in record.items}
    if set(decision_items) != set(pool_entries):
        _fail(
            "decision_surface_incomplete",
            "$.items",
            "decision items must exactly cover every candidate pool entry",
        )
    for entry_id, item in decision_items.items():
        entry = pool_entries[entry_id]
        if (
            item.security_id != entry.security_id
            or item.listing_id != entry.listing_id
            or item.security_mapping_sha256 != entry.security_mapping_sha256
        ):
            _fail(
                "decision_item_identity_mismatch",
                "$.items",
                f"decision item {item.decision_item_id} does not bind its pool entry",
            )
        if entry.admission_status == "admitted":
            if item.rank is None or item.signal_action is None:
                _fail(
                    "admitted_decision_required",
                    "$.items",
                    "admitted entries require rank and selected/not-selected action",
                )
        elif any(
            value is not None
            for value in (
                item.rank,
                item.signal_action,
                item.side,
                item.risk_status,
                item.approved_quantity_micros,
                item.approved_notional_minor,
                item.currency,
            )
        ):
            _fail(
                "inactive_pool_entry_decision_forbidden",
                "$.items",
                "parked and rejected pool entries cannot carry rank, action, risk, or size",
            )
    expected_decision_tier = (
        "research_pit" if pool.pit_tier == "canonical_pit" else pool.pit_tier
    )
    if (
        record.pit_tier != expected_decision_tier
        or record.result_ceiling
        != _RESULT_CEILING_BY_PIT[expected_decision_tier]
        or record.known_future_leakage != pool.known_future_leakage
    ):
        _fail(
            "decision_evidence_identity_mismatch",
            "$.pit_tier",
            "decision must propagate pool leakage and obey the research-only context ceiling",
        )
    expected_snapshot = decision_input_snapshot_hash(
        candidate_pool=pool,
        policy_arm=record.policy_arm,
        policy_snapshot=record.policy_snapshot,
        decision_engine_id=record.decision_engine_id,
        decision_engine_version=record.decision_engine_version,
        decision_engine_sha256=record.decision_engine_sha256,
        decision_context_id=record.decision_context_id,
        decision_context_sha256=record.decision_context_sha256,
        execution_rule_id=record.execution_rule_id,
        execution_rule_version=record.execution_rule_version,
        execution_rule_sha256=record.execution_rule_sha256,
        cost_rule_id=record.cost_rule_id,
        cost_rule_version=record.cost_rule_version,
        cost_rule_sha256=record.cost_rule_sha256,
        comparison_rule_id=record.comparison_rule_id,
        comparison_rule_version=record.comparison_rule_version,
        comparison_rule_sha256=record.comparison_rule_sha256,
        items=record.items,
        run_id=record.run_id,
        run_date=record.run_date,
        calendar_session_id=record.calendar_session_id,
        data_cutoff=record.data_cutoff,
        expected_horizon=record.expected_horizon,
    )
    if record.input_snapshot_sha256 != expected_snapshot:
        _fail(
            "input_snapshot_hash_mismatch",
            "$.input_snapshot_sha256",
            f"expected {expected_snapshot}, got {record.input_snapshot_sha256}",
        )
    return record


def validate_order_intent_against_decision(
    order_intent: Mapping[str, Any] | OrderIntent,
    decision_record: Mapping[str, Any] | DecisionRecord,
) -> OrderIntent:
    intent = validate_order_intent(order_intent)
    decision = validate_decision_record(decision_record)
    if intent.decision_id != decision.decision_id:
        _fail(
            "decision_id_mismatch",
            "$.decision_id",
            "does not match the supplied decision",
        )
    if intent.decision_hash != decision.semantic_hash:
        _fail(
            "decision_hash_mismatch",
            "$.decision_hash",
            "does not bind the supplied decision semantic hash",
        )
    if intent.decision_record_hash != decision.record_hash:
        _fail(
            "decision_record_hash_mismatch",
            "$.decision_record_hash",
            "does not bind the exact supplied decision record",
        )
    by_item_id = {item.decision_item_id: item for item in decision.items}
    item = by_item_id.get(intent.decision_item_id)
    if item is None:
        _fail(
            "unresolved_decision_item_id",
            "$.decision_item_id",
            "does not identify a supplied decision item",
        )
    if item.signal_action != "selected" or item.risk_status != "approved":
        _fail(
            "order_intent_not_approved",
            "$.decision_item_id",
            "only selected and risk-approved decision items may create an intent",
        )
    if (
        intent.candidate_entry_id != item.candidate_entry_id
        or intent.security_id != item.security_id
        or intent.listing_id != item.listing_id
        or intent.security_mapping_sha256 != item.security_mapping_sha256
    ):
        _fail(
            "order_intent_identity_mismatch",
            "$.candidate_entry_id",
            "intent security identity must exactly match the approved decision item",
        )
    if (
        intent.quantity_micros != item.approved_quantity_micros
        or intent.notional_minor != item.approved_notional_minor
        or intent.currency != item.currency
    ):
        _fail(
            "order_intent_size_mismatch",
            "$.quantity_micros",
            "intent size and currency must exactly match risk approval",
        )
    if intent.side != item.side:
        _fail(
            "order_intent_side_mismatch",
            "$.side",
            "intent side must exactly match the frozen decision item side",
        )
    if (
        intent.execution_rule_id != decision.execution_rule_id
        or intent.execution_rule_version != decision.execution_rule_version
        or intent.execution_rule_sha256 != decision.execution_rule_sha256
    ):
        _fail(
            "execution_rule_mismatch",
            "$.execution_rule_id",
            "intent execution rule must exactly match the frozen decision rule",
        )
    _, decision_recorded_dt = _instant(
        decision.recorded_at, path="$.decision.recorded_at"
    )
    _, intent_created_dt = _instant(intent.created_at, path="$.created_at")
    if decision_recorded_dt > intent_created_dt:
        _fail(
            "intent_created_before_decision_recorded",
            "$.created_at",
            "the decision must be recorded before an intent is created",
        )
    expected_snapshot = order_intent_input_snapshot_hash(
        decision_record=decision,
        decision_item_id=intent.decision_item_id,
        side=intent.side,
        quantity_micros=intent.quantity_micros,
        notional_minor=intent.notional_minor,
        currency=intent.currency,
        order_type=intent.order_type,
        limit_price_minor=intent.limit_price_minor,
        stop_price_minor=intent.stop_price_minor,
        time_in_force=intent.time_in_force,
        not_before=intent.not_before,
        expires_at=intent.expires_at,
        calendar_session_id=intent.calendar_session_id,
        execution_rule_id=intent.execution_rule_id,
        execution_rule_version=intent.execution_rule_version,
        execution_rule_sha256=intent.execution_rule_sha256,
        created_at=intent.created_at,
    )
    if intent.input_snapshot_sha256 != expected_snapshot:
        _fail(
            "input_snapshot_hash_mismatch",
            "$.input_snapshot_sha256",
            f"expected {expected_snapshot}, got {intent.input_snapshot_sha256}",
        )
    return intent


def validate_settled_outcome_against_inputs(
    settled_outcome: Mapping[str, Any] | SettledOutcome,
    decision_record: Mapping[str, Any] | DecisionRecord,
    order_intent: Mapping[str, Any] | OrderIntent,
    settlement_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    *,
    previous_outcome: Mapping[str, Any] | SettledOutcome | None = None,
) -> SettledOutcome:
    outcome = validate_settled_outcome(settled_outcome)
    decision = validate_decision_record(decision_record)
    intent = validate_order_intent_against_decision(order_intent, decision)
    if (
        outcome.decision_id != decision.decision_id
        or outcome.decision_hash != decision.semantic_hash
        or outcome.decision_record_hash != decision.record_hash
    ):
        _fail(
            "outcome_decision_binding_mismatch",
            "$.decision_id",
            "outcome must bind the exact supplied decision record",
        )
    if (
        outcome.order_intent_id != intent.order_intent_id
        or outcome.order_intent_hash != intent.semantic_hash
        or outcome.order_intent_record_hash != intent.record_hash
    ):
        _fail(
            "outcome_intent_binding_mismatch",
            "$.order_intent_id",
            "outcome must bind the exact supplied intent record",
        )
    if (
        outcome.candidate_pool_id != decision.candidate_pool_id
        or outcome.candidate_pool_hash != decision.candidate_pool_hash
        or outcome.candidate_pool_record_hash
        != decision.candidate_pool_record_hash
    ):
        _fail(
            "outcome_pool_binding_mismatch",
            "$.candidate_pool_id",
            "outcome must bind the decision's exact candidate pool record",
        )
    if outcome.horizon != decision.expected_horizon:
        _fail(
            "outcome_horizon_mismatch",
            "$.horizon",
            "outcome horizon must equal the frozen decision horizon",
        )
    expected_key = settled_outcome_stable_key(
        order_intent_id=intent.order_intent_id, horizon=outcome.horizon
    )
    if outcome.stable_key != expected_key:
        _fail(
            "outcome_stable_key_mismatch",
            "$.stable_key",
            f"expected {expected_key}, got {outcome.stable_key}",
        )
    evidence_by_id, _ = _validated_evidence_registry(
        settlement_evidence_records, source_contracts
    )
    if set(evidence_by_id) != set(outcome.settlement_evidence_record_ids):
        _fail(
            "settlement_evidence_membership_mismatch",
            "$.settlement_evidence_record_ids",
            "supplied evidence must exactly match the frozen settlement snapshot",
        )
    evidence = [
        evidence_by_id[item] for item in outcome.settlement_evidence_record_ids
    ]
    expected_evidence_snapshot = settlement_evidence_snapshot_hash(evidence)
    if outcome.settlement_evidence_snapshot_sha256 != expected_evidence_snapshot:
        _fail(
            "settlement_evidence_snapshot_mismatch",
            "$.settlement_evidence_snapshot_sha256",
            f"expected {expected_evidence_snapshot}, got "
            f"{outcome.settlement_evidence_snapshot_sha256}",
        )
    _, entry_dt = _instant(outcome.entry_at, path="$.entry_at")
    _, settled_dt = _instant(outcome.settled_at, path="$.settled_at")
    _, not_before_dt = _instant(intent.not_before, path="$.intent.not_before")
    _, expires_dt = _instant(intent.expires_at, path="$.intent.expires_at")
    if not (not_before_dt <= entry_dt < expires_dt):
        _fail(
            "entry_outside_intent_window",
            "$.entry_at",
            "entry must fall inside the frozen intent window",
        )
    if outcome.entry_session_id != intent.calendar_session_id:
        _fail(
            "entry_session_mismatch",
            "$.entry_session_id",
            "must equal the intent calendar session",
        )
    for item in evidence:
        if item.security_scope == "instrument":
            mapping = item.security_mapping
            if mapping is None or (
                mapping.security_id != intent.security_id
                or mapping.listing_id != intent.listing_id
            ):
                _fail(
                    "settlement_evidence_security_mismatch",
                    "$.settlement_evidence_record_ids",
                    "instrument settlement evidence must match the intent security and listing",
                )
        _, evidence_known_dt = _instant(item.known_at, path="$.evidence.known_at")
        _, evidence_recorded_dt = _instant(
            item.recorded_at, path="$.evidence.recorded_at"
        )
        if evidence_known_dt > settled_dt or evidence_recorded_dt > settled_dt:
            _fail(
                "settlement_evidence_after_settlement",
                "$.settled_at",
                "settlement evidence must be known and recorded by settled_at",
            )
    if (
        outcome.status == "settled"
        and intent.notional_minor is not None
        and outcome.basis_notional_minor != intent.notional_minor
    ):
        _fail(
            "outcome_basis_notional_mismatch",
            "$.basis_notional_minor",
            "must equal the frozen intent notional when that notional is available",
        )
    if outcome.status == "settled" and outcome.currency != intent.currency:
        _fail(
            "outcome_currency_mismatch",
            "$.currency",
            "settled outcome currency must equal the frozen intent currency",
        )
    if (
        outcome.cost_rule_id != decision.cost_rule_id
        or outcome.cost_rule_version != decision.cost_rule_version
        or outcome.cost_rule_sha256 != decision.cost_rule_sha256
    ):
        _fail(
            "cost_rule_mismatch",
            "$.cost_rule_id",
            "outcome cost rule must exactly match the frozen decision rule",
        )
    if (
        outcome.comparison_rule_id != decision.comparison_rule_id
        or outcome.comparison_rule_version != decision.comparison_rule_version
        or outcome.comparison_rule_sha256 != decision.comparison_rule_sha256
    ):
        _fail(
            "comparison_rule_mismatch",
            "$.comparison_rule_id",
            "outcome comparison rule must exactly match the frozen decision rule",
        )
    weakest = min(
        [decision.pit_tier, *(item.pit_tier for item in evidence)],
        key=lambda item: _PIT_RANK[item],
    )
    if weakest == "canonical_pit":
        weakest = "research_pit"
    leakage = decision.known_future_leakage or any(
        item.known_future_leakage for item in evidence
    )
    if (
        outcome.pit_tier != weakest
        or outcome.result_ceiling != _RESULT_CEILING_BY_PIT[weakest]
        or outcome.known_future_leakage != leakage
    ):
        _fail(
            "outcome_evidence_identity_mismatch",
            "$.pit_tier",
            "outcome must exactly propagate weakest PIT, ceiling, and leakage",
        )
    expected_snapshot = settled_outcome_input_snapshot_hash(
        decision_record=decision,
        order_intent=intent,
        settlement_evidence_records=evidence,
        fill_snapshot_id=outcome.fill_snapshot_id,
        fill_snapshot_sha256=outcome.fill_snapshot_sha256,
        position_snapshot_id=outcome.position_snapshot_id,
        position_snapshot_sha256=outcome.position_snapshot_sha256,
        horizon=outcome.horizon,
        entry_session_id=outcome.entry_session_id,
        entry_at=outcome.entry_at,
        exit_session_id=outcome.exit_session_id,
        exit_at=outcome.exit_at,
        cost_rule_id=outcome.cost_rule_id,
        cost_rule_version=outcome.cost_rule_version,
        cost_rule_sha256=outcome.cost_rule_sha256,
        comparison_rule_id=outcome.comparison_rule_id,
        comparison_rule_version=outcome.comparison_rule_version,
        comparison_rule_sha256=outcome.comparison_rule_sha256,
    )
    if outcome.input_snapshot_sha256 != expected_snapshot:
        _fail(
            "input_snapshot_hash_mismatch",
            "$.input_snapshot_sha256",
            f"expected {expected_snapshot}, got {outcome.input_snapshot_sha256}",
        )
    if outcome.revision_number == 1:
        if previous_outcome is not None:
            _fail(
                "unexpected_previous_outcome",
                "$.previous_outcome_id",
                "the first revision cannot be validated against a previous outcome",
            )
    else:
        if previous_outcome is None:
            _fail(
                "previous_outcome_required",
                "$.previous_outcome_id",
                "later revisions require the referenced previous outcome",
            )
        previous = validate_settled_outcome(previous_outcome)
        if previous.status == "settled" and outcome.status != "settled":
            _fail(
                "settled_outcome_revision_regression",
                "$.status",
                "a settled outcome revision cannot regress to unavailable",
            )
        if (
            outcome.previous_outcome_id != previous.outcome_id
            or outcome.previous_outcome_record_hash != previous.record_hash
            or outcome.outcome_id == previous.outcome_id
            or outcome.stable_key != previous.stable_key
            or outcome.revision_number != previous.revision_number + 1
            or outcome.decision_id != previous.decision_id
            or outcome.decision_hash != previous.decision_hash
            or outcome.decision_record_hash != previous.decision_record_hash
            or outcome.order_intent_id != previous.order_intent_id
            or outcome.order_intent_hash != previous.order_intent_hash
            or outcome.order_intent_record_hash
            != previous.order_intent_record_hash
            or outcome.candidate_pool_id != previous.candidate_pool_id
            or outcome.candidate_pool_hash != previous.candidate_pool_hash
            or outcome.candidate_pool_record_hash
            != previous.candidate_pool_record_hash
            or outcome.horizon != previous.horizon
            or outcome.cost_rule_id != previous.cost_rule_id
            or outcome.cost_rule_version != previous.cost_rule_version
            or outcome.cost_rule_sha256 != previous.cost_rule_sha256
            or outcome.comparison_rule_id != previous.comparison_rule_id
            or outcome.comparison_rule_version
            != previous.comparison_rule_version
            or outcome.comparison_rule_sha256
            != previous.comparison_rule_sha256
        ):
            _fail(
                "previous_outcome_binding_mismatch",
                "$.previous_outcome_id",
                "revision must bind the immediately prior record in the same outcome chain",
            )
        _, previous_recorded_dt = _instant(
            previous.recorded_at, path="$.previous_outcome.recorded_at"
        )
        _, outcome_recorded_dt = _instant(outcome.recorded_at, path="$.recorded_at")
        if previous_recorded_dt > outcome_recorded_dt:
            _fail(
                "nonmonotonic_outcome_revision",
                "$.recorded_at",
                "a revision cannot be recorded before its predecessor",
            )
    return outcome


def validate_replacement_value_against_inputs(
    replacement_value: Mapping[str, Any] | ReplacementValue,
    settled_outcome: Mapping[str, Any] | SettledOutcome,
    candidate_pool: Mapping[str, Any] | CandidatePool,
    comparator_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    *,
    previous_replacement_value: Mapping[str, Any] | ReplacementValue | None = None,
) -> ReplacementValue:
    replacement = validate_replacement_value(replacement_value)
    outcome = validate_settled_outcome(settled_outcome)
    pool = validate_candidate_pool(candidate_pool)
    if (
        pool.candidate_pool_id != outcome.candidate_pool_id
        or pool.semantic_hash != outcome.candidate_pool_hash
        or pool.record_hash != outcome.candidate_pool_record_hash
    ):
        _fail(
            "outcome_pool_binding_mismatch",
            "$.candidate_pool_id",
            "the supplied pool must be the exact pool bound by the outcome",
        )
    if (
        replacement.settled_outcome_id != outcome.outcome_id
        or replacement.settled_outcome_hash != outcome.semantic_hash
        or replacement.settled_outcome_record_hash != outcome.record_hash
    ):
        _fail(
            "replacement_outcome_binding_mismatch",
            "$.settled_outcome_id",
            "replacement row must bind the exact supplied outcome record",
        )
    if (
        replacement.candidate_pool_id != pool.candidate_pool_id
        or replacement.candidate_pool_hash != pool.semantic_hash
        or replacement.candidate_pool_record_hash != pool.record_hash
    ):
        _fail(
            "replacement_pool_binding_mismatch",
            "$.candidate_pool_id",
            "replacement row must bind the supplied candidate pool",
        )
    comparators = {item.role: item for item in pool.comparators}
    comparator = comparators[replacement.comparator_role]
    if (
        replacement.comparator_reference_id != comparator.reference_id
        or replacement.comparator_reference_snapshot_sha256
        != comparator.reference_snapshot_sha256
    ):
        _fail(
            "replacement_comparator_binding_mismatch",
            "$.comparator_reference_id",
            "replacement row must bind the frozen pool comparator identity",
        )
    if (
        replacement.comparison_rule_id != outcome.comparison_rule_id
        or replacement.comparison_rule_version != outcome.comparison_rule_version
        or replacement.comparison_rule_sha256 != outcome.comparison_rule_sha256
    ):
        _fail(
            "comparison_rule_mismatch",
            "$.comparison_rule_id",
            "replacement comparison rule must match the frozen outcome rule",
        )
    expected_key = replacement_value_stable_key(
        settled_outcome_stable_key=outcome.stable_key,
        comparator_role=replacement.comparator_role,
    )
    if replacement.stable_key != expected_key:
        _fail(
            "replacement_stable_key_mismatch",
            "$.stable_key",
            f"expected {expected_key}, got {replacement.stable_key}",
        )
    if replacement.revision_number != outcome.revision_number:
        _fail(
            "replacement_revision_mismatch",
            "$.revision_number",
            "replacement revision must equal the bound outcome revision",
        )
    evidence_by_id, _ = _validated_evidence_registry(
        comparator_evidence_records, source_contracts
    )
    missing = [
        item
        for item in replacement.comparator_evidence_record_ids
        if item not in evidence_by_id
    ]
    if missing:
        _fail(
            "unresolved_comparator_evidence_id",
            "$.comparator_evidence_record_ids",
            f"unresolved ids: {', '.join(missing)}",
        )
    evidence = [
        evidence_by_id[item] for item in replacement.comparator_evidence_record_ids
    ]
    expected_evidence_snapshot = settlement_evidence_snapshot_hash(evidence)
    if replacement.comparator_evidence_snapshot_sha256 != expected_evidence_snapshot:
        _fail(
            "comparator_evidence_snapshot_mismatch",
            "$.comparator_evidence_snapshot_sha256",
            f"expected {expected_evidence_snapshot}, got "
            f"{replacement.comparator_evidence_snapshot_sha256}",
        )
    _, outcome_recorded_dt = _instant(
        outcome.recorded_at, path="$.outcome.recorded_at"
    )
    _, replacement_settled_dt = _instant(
        replacement.settled_at, path="$.settled_at"
    )
    if outcome_recorded_dt > replacement_settled_dt:
        _fail(
            "replacement_before_outcome_recorded",
            "$.settled_at",
            "the outcome must be recorded before replacement measurement settles",
        )
    comparator_instrument_matched = False
    for item in evidence:
        if not {
            "comparator_reference_id",
            "comparator_reference_snapshot_sha256",
        }.issubset(item.decision_content):
            _fail(
                "comparator_evidence_reference_binding_required",
                "$.comparator_evidence_record_ids",
                "comparator evidence must declare its frozen reference id and snapshot",
            )
        evidence_reference_id = _text(
            item.decision_content["comparator_reference_id"],
            path="$.evidence.decision_content.comparator_reference_id",
        )
        evidence_reference_snapshot = _sha256(
            item.decision_content["comparator_reference_snapshot_sha256"],
            path="$.evidence.decision_content.comparator_reference_snapshot_sha256",
        )
        if (
            evidence_reference_id != comparator.reference_id
            or evidence_reference_snapshot != comparator.reference_snapshot_sha256
        ):
            _fail(
                "comparator_evidence_reference_mismatch",
                "$.comparator_evidence_record_ids",
                "comparator evidence must exactly bind the pool reference identity",
            )
        if replacement.comparator_role in {"cash", "v1"}:
            if item.security_scope == "instrument":
                _fail(
                    "comparator_instrument_evidence_forbidden",
                    "$.comparator_evidence_record_ids",
                    "cash and V1 comparators cannot use instrument-scope evidence",
                )
        elif item.security_scope == "instrument":
            mapping = item.security_mapping
            if mapping is None or (
                mapping.symbol != comparator.reference_id
                or mapping.mapping_sha256
                != comparator.reference_snapshot_sha256
            ):
                _fail(
                    "comparator_evidence_security_mismatch",
                    "$.comparator_evidence_record_ids",
                    "SPY and QQQ instrument evidence must match the frozen symbol and mapping snapshot",
                )
            comparator_instrument_matched = True
        _, evidence_known_dt = _instant(item.known_at, path="$.evidence.known_at")
        _, evidence_recorded_dt = _instant(
            item.recorded_at, path="$.evidence.recorded_at"
        )
        if (
            evidence_known_dt > replacement_settled_dt
            or evidence_recorded_dt > replacement_settled_dt
        ):
            _fail(
                "comparator_evidence_after_settlement",
                "$.settled_at",
                "comparator evidence must be known and recorded by settled_at",
            )
    if (
        replacement.status == "computed"
        and replacement.comparator_role in {"spy", "qqq"}
        and not comparator_instrument_matched
    ):
        _fail(
            "comparator_instrument_evidence_required",
            "$.comparator_evidence_record_ids",
            "computed SPY and QQQ rows require matching instrument evidence",
        )
    if replacement.status == "computed":
        if outcome.status != "settled" or comparator.availability_status != "available":
            _fail(
                "replacement_computation_unavailable",
                "$.status",
                "computed replacement requires settled strategy and available comparator",
            )
        if (
            replacement.strategy_value_minor != outcome.net_pnl_minor
            or replacement.basis_notional_minor != outcome.basis_notional_minor
            or replacement.currency != outcome.currency
        ):
            _fail(
                "strategy_measurement_mismatch",
                "$.strategy_value_minor",
                "strategy value, basis notional, and currency must match the settled outcome",
            )
    elif outcome.status == "unavailable" or comparator.availability_status == "unavailable":
        pass
    weakest = min(
        [outcome.pit_tier, *(item.pit_tier for item in evidence)],
        key=lambda item: _PIT_RANK[item],
    )
    leakage = outcome.known_future_leakage or any(
        item.known_future_leakage for item in evidence
    )
    if (
        replacement.pit_tier != weakest
        or replacement.result_ceiling != _RESULT_CEILING_BY_PIT[weakest]
        or replacement.known_future_leakage != leakage
    ):
        _fail(
            "replacement_evidence_identity_mismatch",
            "$.pit_tier",
            "replacement must exactly propagate weakest PIT, ceiling, and leakage",
        )
    expected_snapshot = replacement_value_input_snapshot_hash(
        settled_outcome=outcome,
        candidate_pool=pool,
        comparator=comparator,
        comparator_evidence_records=evidence,
        comparison_rule_id=replacement.comparison_rule_id,
        comparison_rule_version=replacement.comparison_rule_version,
        comparison_rule_sha256=replacement.comparison_rule_sha256,
    )
    if replacement.input_snapshot_sha256 != expected_snapshot:
        _fail(
            "input_snapshot_hash_mismatch",
            "$.input_snapshot_sha256",
            f"expected {expected_snapshot}, got {replacement.input_snapshot_sha256}",
        )
    if replacement.revision_number == 1:
        if previous_replacement_value is not None:
            _fail(
                "unexpected_previous_replacement_value",
                "$.previous_replacement_value_id",
                "the first revision cannot have a supplied predecessor",
            )
    else:
        if previous_replacement_value is None:
            _fail(
                "previous_replacement_value_required",
                "$.previous_replacement_value_id",
                "later revisions require the referenced previous replacement row",
            )
        previous = validate_replacement_value(previous_replacement_value)
        if previous.status == "computed" and replacement.status != "computed":
            _fail(
                "computed_replacement_revision_regression",
                "$.status",
                "a computed replacement revision cannot regress to unavailable",
            )
        if (
            replacement.previous_replacement_value_id
            != previous.replacement_value_id
            or replacement.previous_replacement_value_record_hash != previous.record_hash
            or replacement.replacement_value_id == previous.replacement_value_id
            or replacement.stable_key != previous.stable_key
            or replacement.revision_number != previous.revision_number + 1
            or replacement.comparator_role != previous.comparator_role
            or replacement.candidate_pool_id != previous.candidate_pool_id
            or replacement.candidate_pool_hash != previous.candidate_pool_hash
            or replacement.candidate_pool_record_hash
            != previous.candidate_pool_record_hash
            or replacement.comparator_reference_id
            != previous.comparator_reference_id
            or replacement.comparator_reference_snapshot_sha256
            != previous.comparator_reference_snapshot_sha256
            or replacement.comparison_rule_id != previous.comparison_rule_id
            or replacement.comparison_rule_version
            != previous.comparison_rule_version
            or replacement.comparison_rule_sha256
            != previous.comparison_rule_sha256
        ):
            _fail(
                "previous_replacement_binding_mismatch",
                "$.previous_replacement_value_id",
                "revision must bind the immediately prior row for the same comparator",
            )
        _, previous_recorded_dt = _instant(
            previous.recorded_at, path="$.previous_replacement.recorded_at"
        )
        _, replacement_recorded_dt = _instant(
            replacement.recorded_at, path="$.recorded_at"
        )
        if previous_recorded_dt > replacement_recorded_dt:
            _fail(
                "nonmonotonic_replacement_revision",
                "$.recorded_at",
                "a replacement revision cannot be recorded before its predecessor",
            )
    return replacement


def validate_replacement_value_panel(
    replacement_values: Sequence[Mapping[str, Any] | ReplacementValue],
    settled_outcome: Mapping[str, Any] | SettledOutcome,
    candidate_pool: Mapping[str, Any] | CandidatePool,
    comparator_evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    *,
    previous_replacement_values: Sequence[
        Mapping[str, Any] | ReplacementValue
    ] = (),
) -> tuple[ReplacementValue, ...]:
    rows = [validate_replacement_value(item) for item in replacement_values]
    roles = [item.comparator_role for item in rows]
    if len(roles) != len(set(roles)) or set(roles) != _REQUIRED_COMPARATOR_ROLES:
        _fail(
            "replacement_panel_incomplete",
            "$.replacement_values",
            "must contain exactly one cash, SPY, QQQ, and V1 row",
        )
    ids = [item.replacement_value_id for item in rows]
    if len(ids) != len(set(ids)):
        _fail(
            "duplicate_replacement_value_id",
            "$.replacement_values",
            "replacement value ids must be unique",
        )
    evidence_by_id, _ = _validated_evidence_registry(
        comparator_evidence_records, source_contracts
    )
    referenced_ids = {
        evidence_id
        for row in rows
        for evidence_id in row.comparator_evidence_record_ids
    }
    if referenced_ids != set(evidence_by_id):
        _fail(
            "comparator_evidence_panel_mismatch",
            "$.comparator_evidence_records",
            "supplied evidence must exactly cover the four replacement rows",
        )
    previous_rows = [
        validate_replacement_value(item) for item in previous_replacement_values
    ]
    previous_by_key = {item.stable_key: item for item in previous_rows}
    if len(previous_by_key) != len(previous_rows):
        _fail(
            "duplicate_previous_replacement_key",
            "$.previous_replacement_values",
            "previous replacement stable keys must be unique",
        )
    outcome = validate_settled_outcome(settled_outcome)
    if outcome.revision_number == 1 and previous_rows:
        _fail(
            "unexpected_previous_replacement_panel",
            "$.previous_replacement_values",
            "the first outcome revision cannot have a previous panel",
        )
    if outcome.revision_number > 1:
        previous_roles = [item.comparator_role for item in previous_rows]
        if (
            len(previous_roles) != len(set(previous_roles))
            or set(previous_roles) != _REQUIRED_COMPARATOR_ROLES
        ):
            _fail(
                "previous_replacement_panel_incomplete",
                "$.previous_replacement_values",
                "later outcome revisions require the complete previous comparator panel",
            )
    validated = [
        validate_replacement_value_against_inputs(
            row,
            outcome,
            candidate_pool,
            comparator_evidence_records,
            source_contracts,
            previous_replacement_value=previous_by_key.get(row.stable_key),
        )
        for row in rows
    ]
    return tuple(sorted(validated, key=lambda item: item.comparator_role))


__all__ = [
    "SCHEMA_VERSION",
    "PIT_TIERS",
    "V2ContractValidationError",
    "SecurityMappingSnapshot",
    "SourceContract",
    "EvidenceRecord",
    "UniverseEvent",
    "ResearchClaim",
    "HypothesisCandidate",
    "CandidatePoolEntry",
    "CandidatePoolComparator",
    "CandidatePool",
    "DecisionItem",
    "DecisionRecord",
    "OrderIntent",
    "SettledOutcome",
    "ReplacementValue",
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
    "validate_research_claim",
    "normalize_research_claim",
    "research_evidence_snapshot_hash",
    "validate_research_claim_against_evidence",
    "validate_hypothesis_candidate",
    "normalize_hypothesis_candidate",
    "research_claim_snapshot_hash",
    "validate_hypothesis_candidate_against_claims",
    "validate_candidate_pool",
    "normalize_candidate_pool",
    "universe_event_snapshot_hash",
    "candidate_entry_input_snapshot_hash",
    "candidate_pool_input_snapshot_hash",
    "validate_candidate_pool_against_inputs",
    "validate_decision_record",
    "normalize_decision_record",
    "decision_input_snapshot_hash",
    "validate_decision_record_against_candidate_pool",
    "validate_order_intent",
    "normalize_order_intent",
    "order_intent_input_snapshot_hash",
    "validate_order_intent_against_decision",
    "validate_settled_outcome",
    "normalize_settled_outcome",
    "settlement_evidence_snapshot_hash",
    "settled_outcome_stable_key",
    "settled_outcome_input_snapshot_hash",
    "validate_settled_outcome_against_inputs",
    "validate_replacement_value",
    "normalize_replacement_value",
    "replacement_value_stable_key",
    "replacement_value_input_snapshot_hash",
    "validate_replacement_value_against_inputs",
    "validate_replacement_value_panel",
]
