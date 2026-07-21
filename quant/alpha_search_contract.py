"""Outcome-blind contracts for alpha hypothesis discovery.

This module is deliberately research-only.  It normalises and validates the
inputs used *before* an experiment is reserved, but it never reads outcomes,
writes files, changes strategy behaviour, or enables trading.  Canonical hashes
are SHA-256 digests of deterministic JSON and are suitable for immutable
selection-panel identities.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
SCOPE_MANIFEST_VERSION = "alpha_search_scope_manifest_v1"

QUEUE_VALUES = frozenset({"exploration", "adjacent", "exploitation"})
QUEUE_ALIASES = {
    "explore": "exploration",
    "exploration": "exploration",
    "adjacent": "adjacent",
    "exploit": "exploitation",
    "exploitation": "exploitation",
}
EXPECTATION_PROXY_ALIASES = {
    "direct_implied": "direct_implied_probability",
    "direct_implied_probability": "direct_implied_probability",
    "explicit_consensus": "explicit_consensus",
    "price_revealed": "price_revealed",
    "positioning_constraint": "positioning_constraint",
    "unidentified": "unidentified",
}
CANDIDATE_KINDS = frozenset({"expectation_gap", "plain_event_lead"})
EVIDENCE_GRADES = frozenset(
    {"lead", "observer", "observed_only", "gate_candidate"}
)
PIT_STATUSES = frozenset(
    {
        "not_pit",
        "snapshot_only",
        "pit_forward_unsettled",
        "settled_forward_sufficient",
        "canonical_pit",
    }
)
SATURATION_STATUSES = frozenset(
    {"unknown", "open", "saturated", "frozen", "parked"}
)
SOURCE_CONTRACT_STATUSES = frozenset({"pass", "partial", "fail"})
PREFLIGHT_GATE_STATUSES = frozenset({"pass", "park", "reject"})
PREFLIGHT_DECISIONS = PREFLIGHT_GATE_STATUSES

_GRADE_RANK = {"lead": 0, "observer": 1, "observed_only": 2, "gate_candidate": 3}

_PRODUCTION_IMPACT_FIELDS = (
    "shared_policy_changed",
    "backtester_adapter_changed",
    "run_adapter_changed",
    "entry_rules_changed",
    "ranking_changed",
    "sizing_changed",
    "exit_rules_changed",
    "orders_changed",
    "replay_only",
    "trade_enabled",
    "daily_snapshot_exposed",
    "live_realism_evaluated",
    "live_ready",
    "parity_test_added",
)

_FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "actual_return",
        "actual_ev_delta",
        "actual_pnl_delta",
        "alpha_result",
        "after_metrics",
        "backtest_result",
        "before_metrics",
        "best_horizon",
        "candidate_return",
        "delta_metrics",
        "expected_value_score",
        "forward_return",
        "future_return",
        "gate_metric",
        "gate_result",
        "label_positive_cash",
        "label_positive_qqq",
        "label_positive_spy",
        "max_drawdown",
        "outcome",
        "outcome_label",
        "outcomes",
        "performance",
        "pnl",
        "profit",
        "profit_and_loss",
        "realised_outcome",
        "realised_pnl",
        "realised_return",
        "realized_outcome",
        "realized_pnl",
        "realized_return",
        "return",
        "returns",
        "settlement_return",
        "sharpe",
        "sharpe_daily",
        "sortino",
        "strategy_total_return_pct",
        "total_pnl",
        "total_return",
        "total_return_pct",
        "trade_result",
        "win_rate",
        "winning_horizon",
    }
)
_FORBIDDEN_OUTCOME_KEY_PARTS = (
    "backtest_result",
    "forward_return",
    "gate_result",
    "outcome_label",
    "realised_pnl",
    "realised_return",
    "realized_pnl",
    "realized_return",
    "total_pnl",
    "total_return",
)

_FORBIDDEN_OUTCOME_SUFFIXES = (
    "_return",
    "_returns",
    "_pnl",
    "_sharpe",
    "_sortino",
    "_drawdown",
    "_win_rate",
)


class FailureReason(str, Enum):
    """Closed preflight failure taxonomy; values are stable ledger codes."""

    NO_GROSS_EDGE = "no_gross_edge"
    ALREADY_PRICED = "already_priced"
    WRONG_TRANSMISSION_MAPPING = "wrong_transmission_mapping"
    NO_CANDIDATE_OVERLAP = "no_candidate_overlap"
    MARKET_EXPECTATION_UNIDENTIFIED = "market_expectation_unidentified"
    PIT_OR_SOURCE_FAILURE = "pit_or_source_failure"
    COST_AND_CARRY = "cost_and_carry"
    BORROW_OR_CAPACITY = "borrow_or_capacity"
    CORE_OPPORTUNITY_COST = "core_opportunity_cost"
    CONCENTRATION = "concentration"
    TAIL_RISK = "tail_risk"
    INSUFFICIENT_INDEPENDENT_ROWS = "insufficient_independent_rows"
    DUPLICATE_OR_FROZEN = "duplicate_or_frozen"
    INCOMPLETE_SELECTION_PANEL = "incomplete_selection_panel"
    OUTCOME_CONTAMINATION = "outcome_contamination"
    UNCLASSIFIED = "unclassified"


class ContractValidationError(ValueError):
    """Fail-closed validation error with a stable machine-readable code."""

    def __init__(self, code: str, path: str, message: str):
        self.code = str(code)
        self.path = str(path)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.path}: {self.detail}")

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.detail}


def _fail(code: str, path: str, message: str) -> None:
    raise ContractValidationError(code, path, message)


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
    if isinstance(value, tuple):
        return [_plain(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, list):
        return [_plain(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    return value


def canonical_json(value: Any) -> str:
    """Return deterministic JSON, rejecting non-JSON and non-finite values."""

    plain = _plain(value)
    try:
        return json.dumps(
            plain,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(
            "invalid_json_value", "$", f"value is not canonical JSON: {exc}"
        ) from exc


def canonical_hash(value: Any) -> str:
    """Return a full SHA-256 digest over :func:`canonical_json`."""

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


def _reject_outcomes(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = re.sub(r"[^a-z0-9]+", "_", str(raw_key).strip().lower()).strip("_")
            item_path = f"{path}.{raw_key}"
            forbidden_suffix = key.endswith(_FORBIDDEN_OUTCOME_SUFFIXES)
            forbidden_part = any(part in key for part in _FORBIDDEN_OUTCOME_KEY_PARTS)
            if key in _FORBIDDEN_OUTCOME_KEYS or forbidden_suffix or forbidden_part:
                _fail(
                    "forbidden_outcome_field",
                    item_path,
                    "realized outcomes and performance may not enter discovery contracts",
                )
            _reject_outcomes(item, path=item_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_outcomes(item, path=f"{path}[{index}]")


def _sha256_digest(value: Any, *, path: str) -> str:
    digest = _text(value, path=path, lower=True)
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        _fail("invalid_sha256", path, "must be a lowercase 64-character SHA-256 digest")
    return digest


def _hash_without_top_level(value: Any, *excluded: str) -> str:
    raw = dict(_mapping(_plain(value), path="$"))
    for key in excluded:
        raw.pop(key, None)
    return canonical_hash(raw)


def _semantic_hash(value: Any) -> str:
    """Compatibility hash used by the engine for self-referential documents."""

    return _hash_without_top_level(value, "panel_hash", "preflight_hash")


def _text(value: Any, *, path: str, lower: bool = False) -> str:
    if not isinstance(value, str):
        _fail("string_required", path, "must be a string")
    text = value.strip()
    if not text:
        _fail("empty_string", path, "must not be empty")
    return text.lower() if lower else text


def _boolean(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        _fail("boolean_required", path, "must be a boolean")
    return value


def _nonnegative_integer(value: Any, *, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail("nonnegative_integer_required", path, "must be an integer >= 0")
    return value


def _string_tuple(
    value: Any, *, path: str, required: bool = True, lower: bool = False
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list of strings")
    normalised = {
        _text(item, path=f"{path}[{index}]", lower=lower)
        for index, item in enumerate(value)
    }
    if required and not normalised:
        _fail("nonempty_list_required", path, "must contain at least one value")
    return tuple(sorted(normalised))


def _known_at(value: Any, *, path: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        return value.isoformat()
    elif isinstance(value, str):
        text = value.strip()
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            parsed_date = None
        if parsed_date is not None and parsed_date.isoformat() == text:
            return text
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractValidationError(
                "invalid_known_at", path, "must be an ISO date or timezone-aware datetime"
            ) from exc
    else:
        _fail("invalid_known_at", path, "must be an ISO date or timezone-aware datetime")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("invalid_known_at", path, "datetime must include a timezone")
    utc_value = parsed.astimezone(timezone.utc).isoformat()
    return utc_value.replace("+00:00", "Z")


def _frozen_json(value: Any, *, path: str) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("invalid_json_value", path, "numbers must be finite")
        return value
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        normalised: dict[str, Any] = {}
        raw_keys = list(value)
        for raw_key in raw_keys:
            if not isinstance(raw_key, str):
                _fail("string_key_required", path, "all object keys must be strings")
        for raw_key in sorted(raw_keys):
            key = raw_key.strip()
            if not key:
                _fail("empty_key", path, "object keys must not be empty")
            if key in normalised:
                _fail("duplicate_key", path, f"duplicate normalised key: {key}")
            normalised[key] = _frozen_json(value[raw_key], path=f"{path}.{key}")
        return MappingProxyType(normalised)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(
            _frozen_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    _fail("invalid_json_value", path, f"unsupported value type: {type(value).__name__}")


def research_only_production_impact() -> dict[str, bool]:
    """Return the canonical all-false production boundary."""

    return {field: False for field in _PRODUCTION_IMPACT_FIELDS}


def _production_impact(value: Any, *, path: str) -> Mapping[str, bool]:
    raw = _mapping(value, path=path)
    if not raw:
        _fail("production_impact_required", path, "must explicitly declare false flags")
    normalised = research_only_production_impact()
    for key, item in raw.items():
        clean_key = _text(key, path=f"{path}.<key>")
        if not isinstance(item, bool):
            _fail("boolean_required", f"{path}.{clean_key}", "must be a boolean")
        if item:
            _fail(
                "production_impact_not_false",
                f"{path}.{clean_key}",
                "alpha discovery contracts require every production flag to be false",
            )
        normalised[clean_key] = False
    return MappingProxyType(dict(sorted(normalised.items())))


def _expectation_proxy(value: Any, *, path: str) -> Mapping[str, str] | None:
    if value is None:
        return None
    raw = _mapping(value, path=path)
    _check_fields(raw, required={"type", "field", "source"}, path=path)
    return MappingProxyType(
        {
            "type": _normalise_expectation_proxy_type(
                raw["type"], path=f"{path}.type"
            ),
            "field": _text(raw["field"], path=f"{path}.field"),
            "source": _text(raw["source"], path=f"{path}.source"),
        }
    )


def _normalise_expectation_proxy_type(value: Any, *, path: str) -> str:
    proxy = _text(value, path=path, lower=True)
    return EXPECTATION_PROXY_ALIASES.get(proxy, proxy)


_FINGERPRINT_FIELDS = frozenset(
    {
        "data_source",
        "component_sources",
        "expectation_proxy",
        "economic_mechanism",
        "decision_surface",
        "payoff_shape",
        "horizon",
        "execution_dependency",
        "portfolio_role",
    }
)


def _fingerprint(value: Any, *, path: str) -> Mapping[str, Any]:
    raw = _mapping(value, path=path)
    _check_fields(raw, required=_FINGERPRINT_FIELDS, path=path)
    return MappingProxyType(
        {
            "data_source": _text(raw["data_source"], path=f"{path}.data_source"),
            "component_sources": _string_tuple(
                raw["component_sources"], path=f"{path}.component_sources"
            ),
            "expectation_proxy": _text(
                _normalise_expectation_proxy_type(
                    raw["expectation_proxy"], path=f"{path}.expectation_proxy"
                ),
                path=f"{path}.expectation_proxy",
            ),
            "economic_mechanism": _text(
                raw["economic_mechanism"], path=f"{path}.economic_mechanism"
            ),
            "decision_surface": _text(
                raw["decision_surface"], path=f"{path}.decision_surface"
            ),
            "payoff_shape": _text(raw["payoff_shape"], path=f"{path}.payoff_shape"),
            "horizon": _text(raw["horizon"], path=f"{path}.horizon"),
            "execution_dependency": _text(
                raw["execution_dependency"], path=f"{path}.execution_dependency"
            ),
            "portfolio_role": _text(
                raw["portfolio_role"], path=f"{path}.portfolio_role"
            ),
        }
    )


def _prediction(value: Any, *, path: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    raw = _mapping(value, path=path)
    _check_fields(
        raw,
        required={"success_probability", "main_failure_modes", "confidence_reason"},
        path=path,
    )
    probability = raw["success_probability"]
    if (
        not isinstance(probability, (int, float))
        or isinstance(probability, bool)
        or not math.isfinite(float(probability))
        or not 0.0 <= float(probability) <= 1.0
    ):
        _fail(
            "invalid_probability",
            f"{path}.success_probability",
            "must be a finite number between 0 and 1",
        )
    return MappingProxyType(
        {
            "success_probability": float(probability),
            "main_failure_modes": _string_tuple(
                raw["main_failure_modes"], path=f"{path}.main_failure_modes"
            ),
            "confidence_reason": _text(
                raw["confidence_reason"], path=f"{path}.confidence_reason"
            ),
        }
    )


def _source_readiness_references(
    value: Any, *, surface_ids: Sequence[str], path: str
) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list of snapshot hash references")
    by_surface: dict[str, Mapping[str, str]] = {}
    allowed_surfaces = set(surface_ids)
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        raw = _mapping(item, path=item_path)
        _check_fields(raw, required={"surface_id", "snapshot_hash"}, path=item_path)
        surface_id = _text(raw["surface_id"], path=f"{item_path}.surface_id")
        if surface_id not in allowed_surfaces:
            _fail(
                "unknown_surface_reference",
                f"{item_path}.surface_id",
                "must reference candidate.surface_ids",
            )
        if surface_id in by_surface:
            _fail(
                "duplicate_surface_reference",
                f"{item_path}.surface_id",
                f"duplicate readiness reference for {surface_id}",
            )
        by_surface[surface_id] = MappingProxyType(
            {
                "surface_id": surface_id,
                "snapshot_hash": _sha256_digest(
                    raw["snapshot_hash"], path=f"{item_path}.snapshot_hash"
                ),
            }
        )
    return tuple(by_surface[key] for key in sorted(by_surface))


def _clock(value: Any, *, path: str) -> tuple[str, datetime]:
    normalised = _known_at(value, path=path)
    if len(normalised) == 10:
        parsed = datetime.combine(
            date.fromisoformat(normalised), datetime_time.max, tzinfo=timezone.utc
        )
        normalised = parsed.isoformat().replace("+00:00", "Z")
    else:
        parsed = datetime.fromisoformat(normalised.replace("Z", "+00:00"))
    return normalised, parsed


def _scope_manifest(value: Any, *, path: str = "$.scope_manifest") -> Mapping[str, Any]:
    raw = _mapping(value, path=path)
    required = {
        "schema_version",
        "manifest_version",
        "scope_name",
        "preregistered_at",
        "data_cutoff",
        "freeze_at",
        "generator_version",
        "candidate_generation_config",
        "allowed_surface_ids",
        "surface_registry_hash",
        "prior_fingerprint_snapshot_hash",
        "prior_fingerprint_count",
        "selector_version",
        "score_version",
        "queue_budgets",
        "expected_candidate_count",
        "selection_limit",
        "batch_policy_bundle_id",
        "outcome_blind",
        "trade_enabled",
        "manifest_hash",
    }
    _check_fields(raw, required=required, path=path)
    _reject_outcomes(raw, path=path)
    if raw["schema_version"] != SCHEMA_VERSION or isinstance(raw["schema_version"], bool):
        _fail("schema_version_mismatch", f"{path}.schema_version", f"must equal {SCHEMA_VERSION}")
    if raw["manifest_version"] != SCOPE_MANIFEST_VERSION:
        _fail(
            "scope_manifest_version_mismatch",
            f"{path}.manifest_version",
            f"must equal {SCOPE_MANIFEST_VERSION}",
        )
    preregistered_at, preregistered_clock = _clock(
        raw["preregistered_at"], path=f"{path}.preregistered_at"
    )
    data_cutoff, cutoff_clock = _clock(raw["data_cutoff"], path=f"{path}.data_cutoff")
    freeze_at, freeze_clock = _clock(raw["freeze_at"], path=f"{path}.freeze_at")
    if not preregistered_clock <= cutoff_clock <= freeze_clock:
        _fail(
            "scope_manifest_clock_order",
            path,
            "require preregistered_at <= data_cutoff <= freeze_at",
        )
    generation_config = _mapping(
        raw["candidate_generation_config"], path=f"{path}.candidate_generation_config"
    )
    if not generation_config:
        _fail(
            "nonempty_mapping_required",
            f"{path}.candidate_generation_config",
            "must freeze candidate generation before synthesis",
        )
    allowed_surface_ids = _string_tuple(
        raw["allowed_surface_ids"], path=f"{path}.allowed_surface_ids"
    )
    raw_budgets = _mapping(raw["queue_budgets"], path=f"{path}.queue_budgets")
    if set(raw_budgets) != set(QUEUE_VALUES):
        _fail(
            "queue_budget_set_mismatch",
            f"{path}.queue_budgets",
            "must preregister all three search queues",
        )
    budgets = {
        queue: _nonnegative_integer(raw_budgets[queue], path=f"{path}.queue_budgets.{queue}")
        for queue in sorted(QUEUE_VALUES)
    }
    expected_count = _nonnegative_integer(
        raw["expected_candidate_count"], path=f"{path}.expected_candidate_count"
    )
    if expected_count == 0 or expected_count != sum(budgets.values()):
        _fail(
            "expected_candidate_count_mismatch",
            f"{path}.expected_candidate_count",
            "must be positive and equal the sum of preregistered queue budgets",
        )
    selection_limit = _nonnegative_integer(
        raw["selection_limit"], path=f"{path}.selection_limit"
    )
    if selection_limit == 0:
        _fail("selection_limit_required", f"{path}.selection_limit", "must be positive")
    batch_policy_bundle_id = raw["batch_policy_bundle_id"]
    if selection_limit == 1:
        if batch_policy_bundle_id is not None:
            _fail(
                "batch_policy_mismatch",
                f"{path}.batch_policy_bundle_id",
                "single-candidate selection requires null batch policy",
            )
    else:
        batch_policy_bundle_id = _text(
            batch_policy_bundle_id, path=f"{path}.batch_policy_bundle_id"
        )
    if raw["outcome_blind"] is not True:
        _fail("outcome_contamination", f"{path}.outcome_blind", "must be true")
    if raw["trade_enabled"] is not False:
        _fail("trade_enabled", f"{path}.trade_enabled", "must be false")
    prior_fingerprint_count = _nonnegative_integer(
        raw["prior_fingerprint_count"], path=f"{path}.prior_fingerprint_count"
    )
    prior_fingerprint_snapshot_hash = _sha256_digest(
        raw["prior_fingerprint_snapshot_hash"],
        path=f"{path}.prior_fingerprint_snapshot_hash",
    )
    if prior_fingerprint_count == 0 and prior_fingerprint_snapshot_hash != canonical_hash([]):
        _fail(
            "prior_fingerprint_snapshot_mismatch",
            f"{path}.prior_fingerprint_snapshot_hash",
            "an empty prior fingerprint set must use canonical_hash([])",
        )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "manifest_version": SCOPE_MANIFEST_VERSION,
        "scope_name": _text(raw["scope_name"], path=f"{path}.scope_name"),
        "preregistered_at": preregistered_at,
        "data_cutoff": data_cutoff,
        "freeze_at": freeze_at,
        "generator_version": _text(
            raw["generator_version"], path=f"{path}.generator_version"
        ),
        "candidate_generation_config": _plain(
            _frozen_json(generation_config, path=f"{path}.candidate_generation_config")
        ),
        "allowed_surface_ids": list(allowed_surface_ids),
        "surface_registry_hash": _sha256_digest(
            raw["surface_registry_hash"], path=f"{path}.surface_registry_hash"
        ),
        "prior_fingerprint_snapshot_hash": prior_fingerprint_snapshot_hash,
        "prior_fingerprint_count": prior_fingerprint_count,
        "selector_version": _text(
            raw["selector_version"], path=f"{path}.selector_version"
        ),
        "score_version": _text(raw["score_version"], path=f"{path}.score_version"),
        "queue_budgets": budgets,
        "expected_candidate_count": expected_count,
        "selection_limit": selection_limit,
        "batch_policy_bundle_id": batch_policy_bundle_id,
        "outcome_blind": True,
        "trade_enabled": False,
        "manifest_hash": _sha256_digest(
            raw["manifest_hash"], path=f"{path}.manifest_hash"
        ),
    }
    if result["manifest_hash"] != _hash_without_top_level(result, "manifest_hash"):
        _fail(
            "scope_manifest_hash_mismatch",
            f"{path}.manifest_hash",
            "does not match the preregistered manifest",
        )
    return _frozen_json(result, path=path)


@dataclass(frozen=True, slots=True)
class EvidenceSurface:
    surface_id: str
    data_source: str
    component_sources: tuple[str, ...]
    roles: tuple[str, ...]
    artifacts: tuple[str, ...]
    pit_status: str
    evidence_grade: str
    settled_count: int
    gate_ready: bool
    expectation_proxy: Mapping[str, str] | None = None
    independent_count: int | None = None
    candidate_overlap_count: int = 0
    saturation_status: str = "unknown"
    reopen_condition: Any = None
    source_contract_status: str = "partial"
    as_of: str | None = None
    artifact_snapshot_hashes: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", _text(self.surface_id, path="$.surface_id"))
        object.__setattr__(self, "data_source", _text(self.data_source, path="$.data_source"))
        object.__setattr__(
            self,
            "component_sources",
            _string_tuple(self.component_sources, path="$.component_sources"),
        )
        roles = _string_tuple(self.roles, path="$.roles", lower=True)
        object.__setattr__(self, "roles", roles)
        object.__setattr__(
            self, "artifacts", _string_tuple(self.artifacts, path="$.artifacts")
        )
        pit_status = _text(self.pit_status, path="$.pit_status", lower=True)
        if pit_status not in PIT_STATUSES:
            _fail("invalid_pit_status", "$.pit_status", f"must be one of {sorted(PIT_STATUSES)}")
        object.__setattr__(self, "pit_status", pit_status)
        grade = _text(self.evidence_grade, path="$.evidence_grade", lower=True)
        if grade not in EVIDENCE_GRADES:
            _fail(
                "invalid_evidence_grade",
                "$.evidence_grade",
                f"must be one of {sorted(EVIDENCE_GRADES)}",
            )
        object.__setattr__(self, "evidence_grade", grade)
        settled_count = _nonnegative_integer(self.settled_count, path="$.settled_count")
        object.__setattr__(self, "settled_count", settled_count)
        independent_count = (
            settled_count
            if self.independent_count is None
            else _nonnegative_integer(self.independent_count, path="$.independent_count")
        )
        if settled_count > independent_count:
            _fail(
                "independent_count_mismatch",
                "$.settled_count",
                "settled_count may not exceed independent_count",
            )
        object.__setattr__(self, "independent_count", independent_count)
        object.__setattr__(
            self,
            "candidate_overlap_count",
            _nonnegative_integer(
                self.candidate_overlap_count, path="$.candidate_overlap_count"
            ),
        )
        gate_ready = _boolean(self.gate_ready, path="$.gate_ready")
        object.__setattr__(self, "gate_ready", gate_ready)
        proxy = _expectation_proxy(self.expectation_proxy, path="$.expectation_proxy")
        object.__setattr__(self, "expectation_proxy", proxy)

        maximum_grade_by_pit = {
            "not_pit": "lead",
            "snapshot_only": "lead",
            "pit_forward_unsettled": "observer",
            "settled_forward_sufficient": "observed_only",
            "canonical_pit": "gate_candidate",
        }
        if _GRADE_RANK[grade] > _GRADE_RANK[maximum_grade_by_pit[pit_status]]:
            _fail(
                "pit_grade_mismatch",
                "$.evidence_grade",
                f"{pit_status} cannot support {grade}",
            )
        if gate_ready != (grade == "gate_candidate"):
            _fail(
                "gate_readiness_mismatch",
                "$.gate_ready",
                "must be true exactly when evidence_grade is gate_candidate",
            )
        if grade in {"observed_only", "gate_candidate"} and settled_count == 0:
            _fail(
                "settled_count_required",
                "$.settled_count",
                f"{grade} requires at least one settled decision",
            )
        if "market_expectation" in roles and proxy is None:
            _fail(
                "expectation_proxy_required",
                "$.expectation_proxy",
                "market_expectation surfaces require an observable proxy",
            )
        saturation_status = _text(
            self.saturation_status, path="$.saturation_status", lower=True
        )
        if saturation_status not in SATURATION_STATUSES:
            _fail(
                "invalid_saturation_status",
                "$.saturation_status",
                f"must be one of {sorted(SATURATION_STATUSES)}",
            )
        object.__setattr__(self, "saturation_status", saturation_status)
        if self.reopen_condition is not None:
            if isinstance(self.reopen_condition, str):
                reopen_condition = _text(
                    self.reopen_condition, path="$.reopen_condition"
                )
            else:
                reopen_condition = _frozen_json(
                    self.reopen_condition, path="$.reopen_condition"
                )
            object.__setattr__(self, "reopen_condition", reopen_condition)
        if saturation_status == "parked" and self.reopen_condition is None:
            _fail(
                "reopen_condition_required",
                "$.reopen_condition",
                "parked surfaces require a quantitative reopen condition",
            )
        source_contract_status = _text(
            self.source_contract_status,
            path="$.source_contract_status",
            lower=True,
        )
        if source_contract_status not in SOURCE_CONTRACT_STATUSES:
            _fail(
                "invalid_source_contract_status",
                "$.source_contract_status",
                f"must be one of {sorted(SOURCE_CONTRACT_STATUSES)}",
            )
        object.__setattr__(self, "source_contract_status", source_contract_status)
        if gate_ready and source_contract_status != "pass":
            _fail(
                "source_contract_not_ready",
                "$.source_contract_status",
                "gate-ready surfaces require a passing source contract",
            )
        if gate_ready and saturation_status in {"saturated", "frozen", "parked"}:
            _fail(
                "saturation_readiness_mismatch",
                "$.saturation_status",
                "saturated, frozen, or parked surfaces cannot be gate ready",
            )
        as_of = None if self.as_of is None else _known_at(self.as_of, path="$.as_of")
        object.__setattr__(self, "as_of", as_of)
        raw_hashes = {} if self.artifact_snapshot_hashes is None else _mapping(
            self.artifact_snapshot_hashes, path="$.artifact_snapshot_hashes"
        )
        snapshot_hashes = MappingProxyType(
            {
                _text(locator, path="$.artifact_snapshot_hashes.<key>"): _sha256_digest(
                    digest, path=f"$.artifact_snapshot_hashes.{locator}"
                )
                for locator, digest in sorted(raw_hashes.items())
            }
        )
        object.__setattr__(self, "artifact_snapshot_hashes", snapshot_hashes)
        if snapshot_hashes and set(snapshot_hashes) != set(self.artifacts):
            _fail(
                "artifact_snapshot_binding_mismatch",
                "$.artifact_snapshot_hashes",
                "hash keys must exactly match the registered artifact locators",
            )
        if gate_ready:
            if pit_status != "canonical_pit":
                _fail(
                    "gate_readiness_mismatch",
                    "$.pit_status",
                    "gate-ready surfaces require canonical_pit",
                )
            if self.candidate_overlap_count == 0:
                _fail(
                    "candidate_overlap_required",
                    "$.candidate_overlap_count",
                    "gate-ready surfaces require positive candidate overlap",
                )
            if as_of is None:
                _fail(
                    "surface_as_of_required",
                    "$.as_of",
                    "gate-ready surfaces require a timestamped snapshot",
                )
            if not snapshot_hashes:
                _fail(
                    "artifact_snapshot_hash_required",
                    "$.artifact_snapshot_hashes",
                    "gate-ready surfaces require immutable artifact snapshot hashes",
                )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceSurface":
        raw = _mapping(value, path="$")
        _reject_outcomes(raw)
        _check_fields(
            raw,
            required={
                "surface_id",
                "data_source",
                "component_sources",
                "roles",
                "artifacts",
                "pit_status",
                "evidence_grade",
                "settled_count",
                "gate_ready",
                "expectation_proxy",
            },
            optional={
                "schema_version",
                "independent_count",
                "candidate_overlap_count",
                "saturation_status",
                "reopen_condition",
                "source_contract_status",
                "as_of",
                "artifact_snapshot_hashes",
            },
            path="$",
        )
        values = dict(raw)
        schema_version = values.pop("schema_version", SCHEMA_VERSION)
        if schema_version != SCHEMA_VERSION:
            _fail(
                "schema_version_mismatch",
                "$.schema_version",
                f"must equal {SCHEMA_VERSION}",
            )
        if "source_contract_status" not in values:
            if values.get("gate_ready") is True:
                _fail(
                    "source_contract_status_required",
                    "$.source_contract_status",
                    "gate-ready surfaces require an explicit passing source contract",
                )
            values["source_contract_status"] = (
                "pass" if values.get("gate_ready") is True else "partial"
            )
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "surface_id": self.surface_id,
            "data_source": self.data_source,
            "component_sources": list(self.component_sources),
            "roles": list(self.roles),
            "artifacts": list(self.artifacts),
            "pit_status": self.pit_status,
            "evidence_grade": self.evidence_grade,
            "settled_count": self.settled_count,
            "independent_count": self.independent_count,
            "candidate_overlap_count": self.candidate_overlap_count,
            "gate_ready": self.gate_ready,
            "expectation_proxy": _plain(self.expectation_proxy),
            "saturation_status": self.saturation_status,
            "reopen_condition": _plain(self.reopen_condition),
            "source_contract_status": self.source_contract_status,
            "as_of": self.as_of,
            "artifact_snapshot_hashes": _plain(self.artifact_snapshot_hashes),
        }

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def validate(self) -> "EvidenceSurface":
        return self

    @property
    def schema_version(self) -> int:
        return SCHEMA_VERSION


def _market_prior(value: Any, *, path: str) -> Mapping[str, Any]:
    raw = _mapping(value, path=path)
    _check_fields(
        raw,
        required={"observable", "proxy_type", "source", "known_at"},
        optional={"value", "interval", "units", "provenance"},
        path=path,
    )
    observable = _boolean(raw["observable"], path=f"{path}.observable")
    if not observable:
        _fail(
            "market_prior_not_observable",
            f"{path}.observable",
            "market expectation must come from an observable proxy",
        )
    result: dict[str, Any] = {
        "observable": True,
        "proxy_type": _normalise_expectation_proxy_type(
            raw["proxy_type"], path=f"{path}.proxy_type"
        ),
        "source": _text(raw["source"], path=f"{path}.source"),
        "known_at": _known_at(raw["known_at"], path=f"{path}.known_at"),
    }
    if "value" in raw:
        result["value"] = _frozen_json(raw["value"], path=f"{path}.value")
    if "interval" in raw:
        interval = raw["interval"]
        if not isinstance(interval, Sequence) or isinstance(
            interval, (str, bytes, bytearray)
        ) or len(interval) != 2:
            _fail("invalid_interval", f"{path}.interval", "must contain [low, high]")
        low, high = interval
        if (
            not isinstance(low, (int, float))
            or isinstance(low, bool)
            or not isinstance(high, (int, float))
            or isinstance(high, bool)
            or not math.isfinite(float(low))
            or not math.isfinite(float(high))
            or float(low) > float(high)
        ):
            _fail(
                "invalid_interval",
                f"{path}.interval",
                "bounds must be finite numbers with low <= high",
            )
        result["interval"] = (low, high)
    for optional in ("units", "provenance"):
        if optional in raw:
            result[optional] = _frozen_json(raw[optional], path=f"{path}.{optional}")
    return MappingProxyType(result)


def _independent_evidence(value: Any, *, path: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list of evidence objects")
    if not value:
        _fail("nonempty_list_required", path, "must contain independent evidence")
    by_hash: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        raw = _mapping(item, path=item_path)
        for required in ("source", "known_at"):
            if required not in raw:
                _fail("missing_field", item_path, f"missing required field: {required}")
        normalised = dict(_plain(_frozen_json(raw, path=item_path)))
        normalised["source"] = _text(raw["source"], path=f"{item_path}.source")
        normalised["known_at"] = _known_at(raw["known_at"], path=f"{item_path}.known_at")
        frozen = _frozen_json(normalised, path=item_path)
        by_hash[canonical_hash(frozen)] = frozen
    return tuple(by_hash[key] for key in sorted(by_hash))


@dataclass(frozen=True, slots=True)
class ExpectationGap:
    market_prior: Mapping[str, Any]
    independent_evidence: tuple[Mapping[str, Any], ...]
    gap_definition: str
    transmission: Mapping[str, Any]
    our_posterior: Mapping[str, Any] | None = None
    gap: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _reject_outcomes(
            {
                "market_prior": self.market_prior,
                "independent_evidence": self.independent_evidence,
                "our_posterior": self.our_posterior,
                "gap": self.gap,
                "transmission": self.transmission,
            }
        )
        object.__setattr__(
            self, "market_prior", _market_prior(self.market_prior, path="$.market_prior")
        )
        object.__setattr__(
            self,
            "independent_evidence",
            _independent_evidence(self.independent_evidence, path="$.independent_evidence"),
        )
        prior_source = str(self.market_prior["source"]).casefold()
        evidence_sources = {
            str(item["source"]).casefold() for item in self.independent_evidence
        }
        if evidence_sources == {prior_source}:
            _fail(
                "independent_evidence_not_independent",
                "$.independent_evidence",
                "at least one evidence source must differ from the market-prior source",
            )
        object.__setattr__(
            self,
            "gap_definition",
            _text(self.gap_definition, path="$.gap_definition"),
        )
        transmission = _mapping(self.transmission, path="$.transmission")
        if not transmission:
            _fail("nonempty_mapping_required", "$.transmission", "must not be empty")
        required_transmission = {
            "affected_tickers",
            "expected_direction",
            "catalyst",
            "half_life",
        }
        missing_transmission = sorted(required_transmission - set(transmission))
        if missing_transmission:
            _fail(
                "missing_field",
                "$.transmission",
                f"missing required fields: {', '.join(missing_transmission)}",
            )
        transmission_values = dict(transmission)
        transmission_values["affected_tickers"] = _string_tuple(
            transmission["affected_tickers"],
            path="$.transmission.affected_tickers",
            required=False,
        )
        for field_name in ("expected_direction", "catalyst", "half_life"):
            transmission_values[field_name] = _text(
                transmission[field_name], path=f"$.transmission.{field_name}"
            )
        object.__setattr__(
            self,
            "transmission",
            _frozen_json(transmission_values, path="$.transmission"),
        )
        if self.our_posterior is not None:
            posterior = _mapping(self.our_posterior, path="$.our_posterior")
            if not posterior:
                _fail("nonempty_mapping_required", "$.our_posterior", "must not be empty")
            posterior_dict = dict(_plain(_frozen_json(posterior, path="$.our_posterior")))
            if "known_at" in posterior_dict:
                posterior_dict["known_at"] = _known_at(
                    posterior_dict["known_at"], path="$.our_posterior.known_at"
                )
            object.__setattr__(
                self,
                "our_posterior",
                _frozen_json(posterior_dict, path="$.our_posterior"),
            )
        if self.gap is not None:
            gap = _mapping(self.gap, path="$.gap")
            if not gap:
                _fail("nonempty_mapping_required", "$.gap", "must not be empty")
            object.__setattr__(self, "gap", _frozen_json(gap, path="$.gap"))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExpectationGap":
        raw = _mapping(value, path="$")
        _reject_outcomes(raw)
        _check_fields(
            raw,
            required={
                "market_prior",
                "independent_evidence",
                "gap_definition",
                "transmission",
            },
            optional={"schema_version", "our_posterior", "gap"},
            path="$",
        )
        values = dict(raw)
        schema_version = values.pop("schema_version", SCHEMA_VERSION)
        if schema_version != SCHEMA_VERSION:
            _fail(
                "schema_version_mismatch",
                "$.schema_version",
                f"must equal {SCHEMA_VERSION}",
            )
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "schema_version": SCHEMA_VERSION,
            "market_prior": _plain(self.market_prior),
            "independent_evidence": _plain(self.independent_evidence),
            "gap_definition": self.gap_definition,
            "transmission": _plain(self.transmission),
        }
        if self.our_posterior is not None:
            result["our_posterior"] = _plain(self.our_posterior)
        if self.gap is not None:
            result["gap"] = _plain(self.gap)
        return result

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def validate(self) -> "ExpectationGap":
        return self

    @property
    def schema_version(self) -> int:
        return SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class HypothesisCandidate:
    schema_version: int
    candidate_kind: str
    candidate_id: str
    search_queue: str
    hypothesis: str
    fingerprint: Mapping[str, Any]
    surface_ids: tuple[str, ...]
    expectation_gap: ExpectationGap | None
    why_not_arbitraged: str
    falsifier: str
    baseline: Mapping[str, Any]
    treatment: Mapping[str, Any]
    replacement_value_comparator: str
    expected_horizon: str
    execution_envelope: Mapping[str, Any]
    evidence_grade: str
    production_impact: Mapping[str, bool]
    title: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    source_readiness_snapshot: tuple[Any, ...] = ()
    prediction: Mapping[str, Any] | None = None
    reopen_condition: Any = None
    next_machine_action: str | None = None

    def __post_init__(self) -> None:
        _reject_outcomes(
            {
                "fingerprint": self.fingerprint,
                "expectation_gap": (
                    None
                    if isinstance(self.expectation_gap, ExpectationGap)
                    else self.expectation_gap
                ),
                "baseline": self.baseline,
                "treatment": self.treatment,
                "execution_envelope": self.execution_envelope,
                "source_readiness_snapshot": self.source_readiness_snapshot,
                "prediction": self.prediction,
                "reopen_condition": self.reopen_condition,
            }
        )
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version != SCHEMA_VERSION
        ):
            _fail(
                "schema_version_mismatch",
                "$.schema_version",
                f"must equal {SCHEMA_VERSION}",
            )
        candidate_kind = _text(
            self.candidate_kind, path="$.candidate_kind", lower=True
        )
        if candidate_kind not in CANDIDATE_KINDS:
            _fail(
                "invalid_candidate_kind",
                "$.candidate_kind",
                f"must be one of {sorted(CANDIDATE_KINDS)}",
            )
        object.__setattr__(self, "candidate_kind", candidate_kind)
        object.__setattr__(self, "candidate_id", _text(self.candidate_id, path="$.candidate_id"))
        raw_queue = _text(self.search_queue, path="$.search_queue", lower=True)
        queue = QUEUE_ALIASES.get(raw_queue)
        if queue is None:
            _fail(
                "invalid_queue",
                "$.search_queue",
                f"must be one of {sorted(QUEUE_ALIASES)}",
            )
        object.__setattr__(self, "search_queue", queue)
        for field_name in (
            "hypothesis",
            "why_not_arbitraged",
            "falsifier",
            "replacement_value_comparator",
            "expected_horizon",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), path=f"$.{field_name}"),
            )
        object.__setattr__(
            self, "surface_ids", _string_tuple(self.surface_ids, path="$.surface_ids")
        )
        gap: ExpectationGap | None
        if candidate_kind == "expectation_gap":
            if self.expectation_gap is None:
                _fail(
                    "expectation_gap_required",
                    "$.expectation_gap",
                    "expectation_gap candidates require an observable prior and independent evidence",
                )
            gap = validate_expectation_gap(self.expectation_gap)
        else:
            if self.expectation_gap is not None:
                _fail(
                    "plain_event_expectation_gap_forbidden",
                    "$.expectation_gap",
                    "plain_event_lead must abstain from claiming a market expectation gap",
                )
            gap = None
        object.__setattr__(self, "expectation_gap", gap)
        fingerprint = _fingerprint(self.fingerprint, path="$.fingerprint")
        object.__setattr__(self, "fingerprint", fingerprint)
        expected_proxy = (
            gap.market_prior["proxy_type"] if gap is not None else "unidentified"
        )
        fingerprint_matches = {
            "expectation_proxy": (fingerprint["expectation_proxy"], expected_proxy),
            "horizon": (fingerprint["horizon"], self.expected_horizon),
        }
        for field_name, (fingerprint_value, contract_value) in fingerprint_matches.items():
            if fingerprint_value != contract_value:
                _fail(
                    "fingerprint_mismatch",
                    f"$.fingerprint.{field_name}",
                    f"must match candidate field value {contract_value!r}",
                )
        grade = _text(self.evidence_grade, path="$.evidence_grade", lower=True)
        if grade not in EVIDENCE_GRADES:
            _fail(
                "invalid_evidence_grade",
                "$.evidence_grade",
                f"must be one of {sorted(EVIDENCE_GRADES)}",
            )
        object.__setattr__(self, "evidence_grade", grade)
        if candidate_kind == "plain_event_lead" and grade != "lead":
            _fail(
                "plain_event_grade_mismatch",
                "$.evidence_grade",
                "plain_event_lead candidates may only have lead evidence_grade",
            )
        if gap is not None and grade in {"observed_only", "gate_candidate"}:
            if not gap.transmission["affected_tickers"]:
                _fail(
                    "affected_tickers_required",
                    "$.expectation_gap.transmission.affected_tickers",
                    f"{grade} candidates require a non-empty ticker mapping",
                )
        for field_name in ("baseline", "treatment"):
            raw_policy = _mapping(getattr(self, field_name), path=f"$.{field_name}")
            if not raw_policy:
                _fail(
                    "nonempty_mapping_required",
                    f"$.{field_name}",
                    "must not be empty",
                )
            if "policy" not in raw_policy:
                _fail(
                    "missing_field",
                    f"$.{field_name}",
                    "missing required field: policy",
                )
            _text(raw_policy["policy"], path=f"$.{field_name}.policy")
            object.__setattr__(
                self,
                field_name,
                _frozen_json(raw_policy, path=f"$.{field_name}"),
            )
        execution = _mapping(self.execution_envelope, path="$.execution_envelope")
        required_execution_fields = {
            "intended_instrument",
            "liquidity_dependency",
            "costs_and_carry",
            "borrow_dependency",
            "capacity_constraint",
            "timing_constraint",
        }
        missing_execution = sorted(required_execution_fields - set(execution))
        if missing_execution:
            _fail(
                "missing_field",
                "$.execution_envelope",
                f"missing required fields: {', '.join(missing_execution)}",
            )
        for field_name in required_execution_fields:
            _text(execution[field_name], path=f"$.execution_envelope.{field_name}")
        _reject_outcomes(execution, path="$.execution_envelope")
        for flag in ("trade_enabled", "orders_enabled", "live_ready"):
            if flag in execution and execution[flag] is not False:
                _fail(
                    "research_execution_not_false",
                    f"$.execution_envelope.{flag}",
                    "research execution flags must be false",
                )
        object.__setattr__(
            self,
            "execution_envelope",
            _frozen_json(execution, path="$.execution_envelope"),
        )
        object.__setattr__(
            self,
            "production_impact",
            _production_impact(self.production_impact, path="$.production_impact"),
        )
        if self.title is not None:
            object.__setattr__(self, "title", _text(self.title, path="$.title"))
        if self.created_at is not None:
            object.__setattr__(
                self, "created_at", _known_at(self.created_at, path="$.created_at")
            )
        if self.created_by is not None:
            object.__setattr__(
                self, "created_by", _text(self.created_by, path="$.created_by")
            )
        readiness_references = _source_readiness_references(
            self.source_readiness_snapshot,
            surface_ids=self.surface_ids,
            path="$.source_readiness_snapshot",
        )
        if grade == "gate_candidate" and {
            item["surface_id"] for item in readiness_references
        } != set(self.surface_ids):
            _fail(
                "source_readiness_snapshot_incomplete",
                "$.source_readiness_snapshot",
                "gate_candidate must bind a snapshot hash for every referenced surface",
            )
        object.__setattr__(self, "source_readiness_snapshot", readiness_references)
        object.__setattr__(self, "prediction", _prediction(self.prediction, path="$.prediction"))
        if self.reopen_condition is not None:
            if isinstance(self.reopen_condition, str):
                reopen_condition = _text(
                    self.reopen_condition, path="$.reopen_condition"
                )
            else:
                reopen_condition = _frozen_json(
                    self.reopen_condition, path="$.reopen_condition"
                )
            _reject_outcomes(reopen_condition, path="$.reopen_condition")
            object.__setattr__(self, "reopen_condition", reopen_condition)
        if self.next_machine_action is not None:
            object.__setattr__(
                self,
                "next_machine_action",
                _text(self.next_machine_action, path="$.next_machine_action"),
            )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HypothesisCandidate":
        raw = _mapping(value, path="$")
        _reject_outcomes(raw)
        if "search_queue" in raw or "schema_version" in raw:
            return cls._from_document_dict(raw)
        return cls._from_legacy_dict(raw)

    @classmethod
    def _from_document_dict(cls, raw: Mapping[str, Any]) -> "HypothesisCandidate":
        flattened_gap = "market_prior" in raw
        required = {
            "schema_version",
            "candidate_id",
            "search_queue",
            "hypothesis",
            "fingerprint",
            "surface_ids",
            "expectation_gap",
            "why_not_arbitraged",
            "falsifier",
            "baseline",
            "treatment",
            "replacement_value_comparator",
            "expected_horizon",
            "execution_envelope",
            "evidence_grade",
        }
        if flattened_gap:
            required |= {"market_prior", "independent_evidence", "transmission"}
        optional = {
            "candidate_kind",
            "title",
            "created_at",
            "created_by",
            "our_posterior",
            "source_readiness_snapshot",
            "prediction",
            "reopen_condition",
            "production_impact",
            "next_machine_action",
        }
        _check_fields(
            raw,
            required=required,
            optional=optional,
            path="$",
        )
        if flattened_gap:
            prior_raw = _mapping(raw["market_prior"], path="$.market_prior")
            prior_source = prior_raw.get("source") or prior_raw.get("surface_id")
            prior_known_at = prior_raw.get("known_at") or prior_raw.get("as_of")
            observability = str(prior_raw.get("observability_grade") or "").lower()
            prior: dict[str, Any] = {
                "observable": prior_raw.get("observable", observability != "missing"),
                "proxy_type": prior_raw.get("proxy_type"),
                "source": prior_source,
                "known_at": prior_known_at,
            }
            for source_key, target_key in (
                ("value", "value"),
                ("interval", "interval"),
                ("unit", "units"),
            ):
                if source_key in prior_raw:
                    prior[target_key] = prior_raw[source_key]
            prior_extras = {
                key: item
                for key, item in prior_raw.items()
                if key
                not in {
                    "observable",
                    "proxy_type",
                    "source",
                    "surface_id",
                    "known_at",
                    "as_of",
                    "value",
                    "interval",
                    "unit",
                }
            }
            if prior_extras:
                prior["provenance"] = prior_extras
            evidence: list[dict[str, Any]] = []
            for item in raw["independent_evidence"]:
                evidence_item = dict(_mapping(item, path="$.independent_evidence[]"))
                evidence_item.setdefault("source", evidence_item.get("surface_id"))
                evidence.append(evidence_item)
            posterior = raw.get("our_posterior")
            if isinstance(posterior, Mapping) and "as_of" in posterior and "known_at" not in posterior:
                posterior = dict(posterior)
                posterior["known_at"] = posterior.pop("as_of")
            gap_value = _mapping(raw["expectation_gap"], path="$.expectation_gap")
            gap_definition = gap_value.get("pricing_map")
            if not isinstance(gap_definition, str) or not gap_definition.strip():
                gap_definition = "predeclared observable-prior expectation gap"
            expectation_gap: ExpectationGap | Mapping[str, Any] = {
                "market_prior": prior,
                "independent_evidence": evidence,
                "our_posterior": posterior,
                "gap_definition": gap_definition,
                "gap": dict(gap_value),
                "transmission": raw["transmission"],
            }
        else:
            expectation_gap = raw["expectation_gap"]
        return cls(
            schema_version=raw["schema_version"],
            candidate_kind=raw.get("candidate_kind", "expectation_gap"),
            candidate_id=raw["candidate_id"],
            search_queue=raw["search_queue"],
            title=raw.get("title"),
            created_at=raw.get("created_at"),
            created_by=raw.get("created_by"),
            hypothesis=raw["hypothesis"],
            fingerprint=raw["fingerprint"],
            surface_ids=raw["surface_ids"],
            expectation_gap=expectation_gap,
            why_not_arbitraged=raw["why_not_arbitraged"],
            falsifier=raw["falsifier"],
            baseline=raw["baseline"],
            treatment=raw["treatment"],
            replacement_value_comparator=raw["replacement_value_comparator"],
            expected_horizon=raw["expected_horizon"],
            execution_envelope=raw["execution_envelope"],
            evidence_grade=raw["evidence_grade"],
            source_readiness_snapshot=raw.get("source_readiness_snapshot", ()),
            prediction=raw.get("prediction"),
            reopen_condition=raw.get("reopen_condition"),
            production_impact=raw.get(
                "production_impact", {"trade_enabled": False}
            ),
            next_machine_action=raw.get("next_machine_action"),
        )

    @classmethod
    def _from_legacy_dict(cls, raw: Mapping[str, Any]) -> "HypothesisCandidate":
        _check_fields(
            raw,
            required={
                "candidate_id",
                "queue",
                "hypothesis",
                "baseline",
                "treatment",
                "horizon",
                "replacement_comparison",
                "fingerprint",
                "surface_ids",
                "expectation_gap",
                "why_not_arbitraged",
                "falsifier",
                "evidence_grade",
                "execution",
                "production_impact",
            },
            optional={
                "decision_surface",
                "mechanism_family",
                "data_source",
                "component_sources",
                "catalyst",
                "next_machine_action",
                "portfolio_role",
                "title",
                "source_readiness_snapshot",
                "prediction",
                "reopen_condition",
            },
            path="$",
        )
        gap = validate_expectation_gap(raw["expectation_gap"])
        if "catalyst" in raw and raw["catalyst"] != gap.transmission.get("catalyst"):
            _fail(
                "expectation_gap_mismatch",
                "$.catalyst",
                "must match expectation_gap.transmission.catalyst",
            )
        for alias, fingerprint_key in (
            ("decision_surface", "decision_surface"),
            ("mechanism_family", "economic_mechanism"),
            ("data_source", "data_source"),
            ("portfolio_role", "portfolio_role"),
        ):
            if alias in raw and raw[alias] != raw["fingerprint"].get(fingerprint_key):
                _fail(
                    "fingerprint_mismatch",
                    f"$.{alias}",
                    f"must match fingerprint.{fingerprint_key}",
                )
        if "component_sources" in raw and tuple(
            _string_tuple(raw["component_sources"], path="$.component_sources")
        ) != tuple(
            _string_tuple(
                raw["fingerprint"].get("component_sources"),
                path="$.fingerprint.component_sources",
            )
        ):
            _fail(
                "fingerprint_mismatch",
                "$.component_sources",
                "must match fingerprint.component_sources",
            )
        legacy_execution = dict(_mapping(raw["execution"], path="$.execution"))
        if not legacy_execution:
            _fail("nonempty_mapping_required", "$.execution", "must not be empty")
        execution_defaults = {
            "intended_instrument": legacy_execution.pop("instrument", "research_only"),
            "liquidity_dependency": "predeclared research constraint",
            "costs_and_carry": "predeclared research cost model",
            "borrow_dependency": "predeclared borrow requirement",
            "capacity_constraint": "predeclared capacity constraint",
            "timing_constraint": "predeclared timing constraint",
        }
        execution_defaults.update(legacy_execution)
        return cls(
            schema_version=SCHEMA_VERSION,
            candidate_kind="expectation_gap",
            candidate_id=raw["candidate_id"],
            search_queue=raw["queue"],
            title=raw.get("title"),
            hypothesis=raw["hypothesis"],
            fingerprint=raw["fingerprint"],
            surface_ids=raw["surface_ids"],
            expectation_gap=gap,
            why_not_arbitraged=raw["why_not_arbitraged"],
            falsifier=raw["falsifier"],
            baseline={"policy": _text(raw["baseline"], path="$.baseline")},
            treatment={"policy": _text(raw["treatment"], path="$.treatment")},
            replacement_value_comparator=raw["replacement_comparison"],
            expected_horizon=raw["horizon"],
            execution_envelope=execution_defaults,
            evidence_grade=raw["evidence_grade"],
            source_readiness_snapshot=raw.get("source_readiness_snapshot", ()),
            prediction=raw.get("prediction"),
            reopen_condition=raw.get("reopen_condition"),
            production_impact=raw["production_impact"],
            next_machine_action=raw.get("next_machine_action"),
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "schema_version": self.schema_version,
            "candidate_kind": self.candidate_kind,
            "candidate_id": self.candidate_id,
            "search_queue": self.search_queue,
            "hypothesis": self.hypothesis,
            "fingerprint": _plain(self.fingerprint),
            "surface_ids": list(self.surface_ids),
            "expectation_gap": (
                None if self.expectation_gap is None else self.expectation_gap.to_dict()
            ),
            "why_not_arbitraged": self.why_not_arbitraged,
            "falsifier": self.falsifier,
            "baseline": _plain(self.baseline),
            "treatment": _plain(self.treatment),
            "replacement_value_comparator": self.replacement_value_comparator,
            "expected_horizon": self.expected_horizon,
            "execution_envelope": _plain(self.execution_envelope),
            "evidence_grade": self.evidence_grade,
            "source_readiness_snapshot": _plain(self.source_readiness_snapshot),
            "production_impact": _plain(self.production_impact),
        }
        for field_name in ("title", "created_at", "created_by"):
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        if self.prediction is not None:
            result["prediction"] = _plain(self.prediction)
        if self.reopen_condition is not None:
            result["reopen_condition"] = _plain(self.reopen_condition)
        if self.next_machine_action is not None:
            result["next_machine_action"] = self.next_machine_action
        return result

    @property
    def queue(self) -> str:
        return self.search_queue

    @property
    def horizon(self) -> str:
        return self.expected_horizon

    @property
    def replacement_comparison(self) -> str:
        return self.replacement_value_comparator

    @property
    def execution(self) -> Mapping[str, Any]:
        return self.execution_envelope

    @property
    def data_source(self) -> str:
        return str(self.fingerprint["data_source"])

    @property
    def component_sources(self) -> tuple[str, ...]:
        return tuple(self.fingerprint["component_sources"])

    @property
    def decision_surface(self) -> str:
        return str(self.fingerprint["decision_surface"])

    @property
    def mechanism_family(self) -> str:
        return str(self.fingerprint["economic_mechanism"])

    @property
    def portfolio_role(self) -> str:
        return str(self.fingerprint["portfolio_role"])

    @property
    def catalyst(self) -> str | None:
        if self.expectation_gap is None:
            return None
        return str(self.expectation_gap.transmission["catalyst"])

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def semantic_payload(self) -> dict[str, Any]:
        """Return stable hypothesis identity, excluding mutable readiness state."""

        payload = self.to_dict()
        for field_name in (
            "candidate_id",
            "created_at",
            "created_by",
            "source_readiness_snapshot",
        ):
            payload.pop(field_name, None)
        return payload

    @property
    def semantic_hash(self) -> str:
        return canonical_hash(self.semantic_payload())

    @property
    def expected_candidate_id(self) -> str:
        return f"cand-{self.semantic_hash[:20]}"

    @property
    def has_semantic_candidate_id(self) -> bool:
        return self.candidate_id == self.expected_candidate_id

    def validate_semantic_id(self) -> "HypothesisCandidate":
        if not self.has_semantic_candidate_id:
            _fail(
                "candidate_id_mismatch",
                "$.candidate_id",
                f"expected {self.expected_candidate_id!r} for semantic content",
            )
        return self

    @classmethod
    def with_computed_id(cls, value: Mapping[str, Any]) -> "HypothesisCandidate":
        raw = dict(_mapping(value, path="$"))
        raw["candidate_id"] = "cand-pending-semantic-hash"
        provisional = cls.from_dict(raw)
        canonical = provisional.to_dict()
        canonical["candidate_id"] = provisional.expected_candidate_id
        return cls.from_dict(canonical)

    def validate(self) -> "HypothesisCandidate":
        return self


def _failure_reason(value: Any, *, path: str) -> FailureReason:
    if isinstance(value, FailureReason):
        return value
    text = _text(value, path=path, lower=True)
    try:
        return FailureReason(text)
    except ValueError as exc:
        raise ContractValidationError(
            "invalid_failure_reason",
            path,
            f"must be one of {sorted(reason.value for reason in FailureReason)}",
        ) from exc


@dataclass(frozen=True, slots=True)
class PreflightDecision:
    """Rich, outcome-blind D0-D3 decision emitted before reservation."""

    schema_version: int
    record_type: str
    candidate_id: str
    selection_scope_id: str | None
    evaluated_at: str
    preflight_version: str
    data_cutoff: str
    outcome_blind: bool
    outcome_fields_excluded: tuple[str, ...]
    source_snapshot_hashes: Mapping[str, str]
    declared_evidence_grade: str
    maximum_supported_evidence_grade: str
    fingerprint_hash: str
    gates: Mapping[str, Mapping[str, Any]]
    decision: str
    failure_reasons: tuple[FailureReason, ...]
    reopen_condition: Any
    trade_enabled: bool
    production_impact: Mapping[str, bool]
    preflight_hash: str

    def __post_init__(self) -> None:
        _reject_outcomes(
            {
                "outcome_fields_excluded": self.outcome_fields_excluded,
                "source_snapshot_hashes": self.source_snapshot_hashes,
                "gates": self.gates,
                "reopen_condition": self.reopen_condition,
                "production_impact": self.production_impact,
            }
        )
        if self.schema_version != SCHEMA_VERSION or isinstance(self.schema_version, bool):
            _fail("schema_version_mismatch", "$.schema_version", f"must equal {SCHEMA_VERSION}")
        if _text(self.record_type, path="$.record_type") != "preflight_decision":
            _fail("record_type_mismatch", "$.record_type", "must equal preflight_decision")
        object.__setattr__(self, "record_type", "preflight_decision")
        object.__setattr__(self, "candidate_id", _text(self.candidate_id, path="$.candidate_id"))
        selection_scope_id = (
            None
            if self.selection_scope_id is None
            else _text(self.selection_scope_id, path="$.selection_scope_id")
        )
        object.__setattr__(self, "selection_scope_id", selection_scope_id)
        object.__setattr__(self, "evaluated_at", _known_at(self.evaluated_at, path="$.evaluated_at"))
        object.__setattr__(
            self, "preflight_version", _text(self.preflight_version, path="$.preflight_version")
        )
        object.__setattr__(self, "data_cutoff", _known_at(self.data_cutoff, path="$.data_cutoff"))
        if _boolean(self.outcome_blind, path="$.outcome_blind") is not True:
            _fail("outcome_contamination", "$.outcome_blind", "must be true")
        object.__setattr__(self, "outcome_blind", True)
        excluded = _string_tuple(
            self.outcome_fields_excluded,
            path="$.outcome_fields_excluded",
        )
        object.__setattr__(self, "outcome_fields_excluded", excluded)

        raw_source_hashes = _mapping(
            self.source_snapshot_hashes, path="$.source_snapshot_hashes"
        )
        source_hashes = MappingProxyType(
            {
                _text(surface_id, path="$.source_snapshot_hashes.<key>"): _sha256_digest(
                    digest, path=f"$.source_snapshot_hashes.{surface_id}"
                )
                for surface_id, digest in sorted(raw_source_hashes.items())
            }
        )
        object.__setattr__(self, "source_snapshot_hashes", source_hashes)
        for field_name in (
            "declared_evidence_grade",
            "maximum_supported_evidence_grade",
        ):
            grade = _text(getattr(self, field_name), path=f"$.{field_name}", lower=True)
            if grade not in EVIDENCE_GRADES:
                _fail(
                    "invalid_evidence_grade",
                    f"$.{field_name}",
                    f"must be one of {sorted(EVIDENCE_GRADES)}",
                )
            object.__setattr__(self, field_name, grade)
        object.__setattr__(
            self,
            "fingerprint_hash",
            _sha256_digest(self.fingerprint_hash, path="$.fingerprint_hash"),
        )

        raw_gates = _mapping(self.gates, path="$.gates")
        if set(raw_gates) != {"D0", "D1", "D2", "D3"}:
            _fail("preflight_gate_set_mismatch", "$.gates", "must contain exactly D0-D3")
        gates: dict[str, Mapping[str, Any]] = {}
        for gate_name in ("D0", "D1", "D2", "D3"):
            gate_path = f"$.gates.{gate_name}"
            raw_gate = _mapping(raw_gates[gate_name], path=gate_path)
            _check_fields(raw_gate, required={"status", "reasons"}, path=gate_path)
            status = _text(raw_gate["status"], path=f"{gate_path}.status", lower=True)
            if status not in PREFLIGHT_GATE_STATUSES:
                _fail(
                    "invalid_preflight_gate_status",
                    f"{gate_path}.status",
                    f"must be one of {sorted(PREFLIGHT_GATE_STATUSES)}",
                )
            reasons = _string_tuple(
                raw_gate["reasons"], path=f"{gate_path}.reasons", required=False
            )
            if (status == "pass") != (not reasons):
                _fail(
                    "preflight_gate_reason_mismatch",
                    f"{gate_path}.reasons",
                    "pass gates require no reasons; park/reject gates require reasons",
                )
            gates[gate_name] = MappingProxyType({"status": status, "reasons": reasons})
        object.__setattr__(self, "gates", MappingProxyType(gates))

        statuses = [gate["status"] for gate in gates.values()]
        expected_decision = (
            "reject" if "reject" in statuses else "park" if "park" in statuses else "pass"
        )
        decision = _text(self.decision, path="$.decision", lower=True)
        if decision not in PREFLIGHT_DECISIONS:
            _fail("invalid_preflight_decision", "$.decision", "must be pass, park, or reject")
        if decision != expected_decision:
            _fail(
                "preflight_decision_mismatch",
                "$.decision",
                f"D0-D3 reduce to {expected_decision}",
            )
        object.__setattr__(self, "decision", decision)
        if (
            decision == "pass"
            and _GRADE_RANK[self.declared_evidence_grade]
            > _GRADE_RANK[self.maximum_supported_evidence_grade]
        ):
            _fail(
                "preflight_grade_mismatch",
                "$.declared_evidence_grade",
                "a passing preflight cannot exceed the machine-supported evidence grade",
            )

        if not isinstance(self.failure_reasons, Sequence) or isinstance(
            self.failure_reasons, (str, bytes, bytearray)
        ):
            _fail("list_required", "$.failure_reasons", "must be a list")
        failure_reasons = tuple(
            sorted(
                {
                    _failure_reason(item, path=f"$.failure_reasons[{index}]")
                    for index, item in enumerate(self.failure_reasons)
                },
                key=lambda reason: reason.value,
            )
        )
        if (decision == "pass") != (not failure_reasons):
            _fail(
                "preflight_failure_reason_mismatch",
                "$.failure_reasons",
                "pass requires no failure reasons; park/reject requires at least one",
            )
        object.__setattr__(self, "failure_reasons", failure_reasons)
        if self.reopen_condition is not None:
            reopen = (
                _text(self.reopen_condition, path="$.reopen_condition")
                if isinstance(self.reopen_condition, str)
                else _frozen_json(self.reopen_condition, path="$.reopen_condition")
            )
            _reject_outcomes(reopen, path="$.reopen_condition")
            object.__setattr__(self, "reopen_condition", reopen)
        if _boolean(self.trade_enabled, path="$.trade_enabled") is not False:
            _fail("trade_enabled", "$.trade_enabled", "preflight must not enable trading")
        object.__setattr__(self, "trade_enabled", False)
        object.__setattr__(
            self,
            "production_impact",
            _production_impact(self.production_impact, path="$.production_impact"),
        )
        claimed_hash = _sha256_digest(self.preflight_hash, path="$.preflight_hash")
        object.__setattr__(self, "preflight_hash", claimed_hash)
        if claimed_hash != _semantic_hash(self.to_dict()):
            _fail(
                "preflight_hash_mismatch",
                "$.preflight_hash",
                "does not match canonical preflight content",
            )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PreflightDecision":
        raw = _mapping(value, path="$")
        _reject_outcomes(raw)
        required = {
            "schema_version",
            "record_type",
            "candidate_id",
            "selection_scope_id",
            "evaluated_at",
            "preflight_version",
            "data_cutoff",
            "outcome_blind",
            "outcome_fields_excluded",
            "source_snapshot_hashes",
            "declared_evidence_grade",
            "maximum_supported_evidence_grade",
            "fingerprint_hash",
            "gates",
            "decision",
            "failure_reasons",
            "reopen_condition",
            "trade_enabled",
            "production_impact",
            "preflight_hash",
        }
        _check_fields(raw, required=required, path="$")
        return cls(**dict(raw))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "candidate_id": self.candidate_id,
            "selection_scope_id": self.selection_scope_id,
            "evaluated_at": self.evaluated_at,
            "preflight_version": self.preflight_version,
            "data_cutoff": self.data_cutoff,
            "outcome_blind": self.outcome_blind,
            "outcome_fields_excluded": list(self.outcome_fields_excluded),
            "source_snapshot_hashes": _plain(self.source_snapshot_hashes),
            "declared_evidence_grade": self.declared_evidence_grade,
            "maximum_supported_evidence_grade": self.maximum_supported_evidence_grade,
            "fingerprint_hash": self.fingerprint_hash,
            "gates": _plain(self.gates),
            "decision": self.decision,
            "failure_reasons": [reason.value for reason in self.failure_reasons],
            "reopen_condition": _plain(self.reopen_condition),
            "trade_enabled": self.trade_enabled,
            "production_impact": _plain(self.production_impact),
            "preflight_hash": self.preflight_hash,
        }

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def validate(self) -> "PreflightDecision":
        return PreflightDecision.from_dict(self.to_dict())


@dataclass(frozen=True, slots=True)
class SelectionPanel:
    """Complete rich panel whose candidates, decisions, scores, and selection are frozen."""

    schema_version: int
    record_type: str
    selection_scope_id: str
    created_at: str
    data_cutoff: str
    scope_manifest: Mapping[str, Any]
    scope_manifest_hash: str
    surface_registry_hash: str
    prior_fingerprint_snapshot_hash: str
    prior_fingerprint_count: int
    selector_version: str
    score_version: str
    queue_budgets: Mapping[str, int]
    queue_actual_counts: Mapping[str, int]
    expected_candidate_count: int
    candidate_pool_complete: bool
    selection_pool_complete: bool
    candidate_ids: tuple[str, ...]
    candidate_snapshots: tuple[HypothesisCandidate, ...]
    candidate_snapshot_hashes: Mapping[str, str]
    preflight_decisions: Mapping[str, PreflightDecision]
    preflight_decision_hashes: Mapping[str, str]
    scores: Mapping[str, Mapping[str, Any]]
    rejection_reasons: Mapping[str, tuple[FailureReason, ...]]
    selection_limit: int
    batch_policy_bundle_id: str | None
    selected_candidate_ids: tuple[str, ...]
    selected_candidate_id: str | None
    selection_reason: str
    outcome_blind: bool
    trade_enabled: bool
    experiment_id_reserved: bool
    production_impact: Mapping[str, bool]
    panel_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or isinstance(self.schema_version, bool):
            _fail("schema_version_mismatch", "$.schema_version", f"must equal {SCHEMA_VERSION}")
        if _text(self.record_type, path="$.record_type") != "panel_selection":
            _fail("record_type_mismatch", "$.record_type", "must equal panel_selection")
        object.__setattr__(self, "record_type", "panel_selection")
        object.__setattr__(self, "created_at", _known_at(self.created_at, path="$.created_at"))
        object.__setattr__(self, "data_cutoff", _known_at(self.data_cutoff, path="$.data_cutoff"))
        object.__setattr__(
            self, "selector_version", _text(self.selector_version, path="$.selector_version")
        )
        object.__setattr__(self, "score_version", _text(self.score_version, path="$.score_version"))
        manifest = _scope_manifest(self.scope_manifest)
        object.__setattr__(self, "scope_manifest", manifest)
        manifest_hash = str(manifest["manifest_hash"])
        if _sha256_digest(self.scope_manifest_hash, path="$.scope_manifest_hash") != manifest_hash:
            _fail(
                "scope_manifest_hash_mismatch",
                "$.scope_manifest_hash",
                "must match scope_manifest.manifest_hash",
            )
        object.__setattr__(self, "scope_manifest_hash", manifest_hash)
        registry_hash = _sha256_digest(
            self.surface_registry_hash, path="$.surface_registry_hash"
        )
        if registry_hash != manifest["surface_registry_hash"]:
            _fail(
                "surface_registry_hash_mismatch",
                "$.surface_registry_hash",
                "must match the preregistered manifest",
            )
        object.__setattr__(self, "surface_registry_hash", registry_hash)
        prior_snapshot_hash = _sha256_digest(
            self.prior_fingerprint_snapshot_hash,
            path="$.prior_fingerprint_snapshot_hash",
        )
        prior_count = _nonnegative_integer(
            self.prior_fingerprint_count, path="$.prior_fingerprint_count"
        )
        if (
            prior_snapshot_hash != manifest["prior_fingerprint_snapshot_hash"]
            or prior_count != manifest["prior_fingerprint_count"]
        ):
            _fail(
                "scope_manifest_binding_mismatch",
                "$.prior_fingerprint_snapshot_hash",
                "prior fingerprint snapshot hash/count must match the preregistered manifest",
            )
        object.__setattr__(self, "prior_fingerprint_snapshot_hash", prior_snapshot_hash)
        object.__setattr__(self, "prior_fingerprint_count", prior_count)
        expected_scope_id = f"scope-{manifest_hash[:24]}"
        if _text(self.selection_scope_id, path="$.selection_scope_id") != expected_scope_id:
            _fail(
                "selection_scope_hash_mismatch",
                "$.selection_scope_id",
                "must derive from the preregistered scope manifest",
            )
        object.__setattr__(self, "selection_scope_id", expected_scope_id)
        for field_name, panel_value, manifest_value in (
            ("created_at", self.created_at, manifest["freeze_at"]),
            ("data_cutoff", self.data_cutoff, manifest["data_cutoff"]),
            ("selector_version", self.selector_version, manifest["selector_version"]),
            ("score_version", self.score_version, manifest["score_version"]),
        ):
            if panel_value != manifest_value:
                _fail(
                    "scope_manifest_binding_mismatch",
                    f"$.{field_name}",
                    f"must equal scope_manifest.{field_name if field_name != 'created_at' else 'freeze_at'}",
                )

        def queue_counts(value: Any, *, path: str) -> Mapping[str, int]:
            raw_counts = _mapping(value, path=path)
            normalised = {queue: 0 for queue in QUEUE_VALUES}
            for raw_queue, count in raw_counts.items():
                queue = QUEUE_ALIASES.get(_text(raw_queue, path=f"{path}.<key>", lower=True))
                if queue is None:
                    _fail("invalid_queue", f"{path}.{raw_queue}", "unknown search queue")
                normalised[queue] = _nonnegative_integer(count, path=f"{path}.{raw_queue}")
            return MappingProxyType(dict(sorted(normalised.items())))

        budgets = queue_counts(self.queue_budgets, path="$.queue_budgets")
        actual_counts = queue_counts(self.queue_actual_counts, path="$.queue_actual_counts")
        object.__setattr__(self, "queue_budgets", budgets)
        object.__setattr__(self, "queue_actual_counts", actual_counts)
        expected_count = _nonnegative_integer(
            self.expected_candidate_count, path="$.expected_candidate_count"
        )
        object.__setattr__(self, "expected_candidate_count", expected_count)
        if dict(budgets) != dict(manifest["queue_budgets"]):
            _fail(
                "scope_manifest_binding_mismatch",
                "$.queue_budgets",
                "must equal preregistered queue budgets",
            )
        if expected_count != manifest["expected_candidate_count"]:
            _fail(
                "scope_manifest_binding_mismatch",
                "$.expected_candidate_count",
                "must equal preregistered expected candidate count",
            )
        if _boolean(self.candidate_pool_complete, path="$.candidate_pool_complete") is not True:
            _fail("incomplete_selection_panel", "$.candidate_pool_complete", "must be true")
        if _boolean(self.selection_pool_complete, path="$.selection_pool_complete") is not True:
            _fail("incomplete_selection_panel", "$.selection_pool_complete", "must be true")
        object.__setattr__(self, "candidate_pool_complete", True)
        object.__setattr__(self, "selection_pool_complete", True)

        if not isinstance(self.candidate_snapshots, Sequence) or isinstance(
            self.candidate_snapshots, (str, bytes, bytearray)
        ):
            _fail("list_required", "$.candidate_snapshots", "must be a list")
        candidates = tuple(
            sorted(
                (
                    validate_hypothesis_candidate(candidate).validate_semantic_id()
                    for candidate in self.candidate_snapshots
                ),
                key=lambda candidate: candidate.candidate_id,
            )
        )
        candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            _fail("duplicate_candidate_id", "$.candidate_snapshots", "candidate IDs must be unique")
        semantic_hashes = [candidate.semantic_hash for candidate in candidates]
        if len(semantic_hashes) != len(set(semantic_hashes)):
            _fail(
                "duplicate_candidate_semantics",
                "$.candidate_snapshots",
                "semantic duplicate candidates are not a complete independent panel",
            )
        if expected_count != len(candidates):
            _fail(
                "candidate_count_mismatch",
                "$.expected_candidate_count",
                "must equal the number of complete candidate snapshots",
            )
        claimed_ids = _string_tuple(self.candidate_ids, path="$.candidate_ids", required=False)
        if claimed_ids != candidate_ids:
            _fail("candidate_ids_mismatch", "$.candidate_ids", "must match sorted snapshots")
        object.__setattr__(self, "candidate_ids", candidate_ids)
        object.__setattr__(self, "candidate_snapshots", candidates)
        computed_actual = {queue: 0 for queue in QUEUE_VALUES}
        for candidate in candidates:
            computed_actual[candidate.search_queue] += 1
            if not set(candidate.surface_ids) <= set(manifest["allowed_surface_ids"]):
                _fail(
                    "surface_outside_scope_manifest",
                    f"$.candidate_snapshots.{candidate.candidate_id}.surface_ids",
                    "candidate references a surface not preregistered for this scope",
                )
        if dict(actual_counts) != dict(sorted(computed_actual.items())):
            _fail("queue_count_mismatch", "$.queue_actual_counts", "must match candidates")
        for queue in QUEUE_VALUES:
            if actual_counts[queue] > budgets[queue]:
                _fail("queue_budget_exceeded", f"$.queue_budgets.{queue}", "below actual count")

        expected_candidate_hashes = {
            candidate.candidate_id: _semantic_hash(candidate.to_dict())
            for candidate in candidates
        }
        raw_candidate_hashes = _mapping(
            self.candidate_snapshot_hashes, path="$.candidate_snapshot_hashes"
        )
        claimed_candidate_hashes = {
            _text(key, path="$.candidate_snapshot_hashes.<key>"): _sha256_digest(
                value, path=f"$.candidate_snapshot_hashes.{key}"
            )
            for key, value in sorted(raw_candidate_hashes.items())
        }
        if claimed_candidate_hashes != expected_candidate_hashes:
            _fail(
                "candidate_snapshot_hash_mismatch",
                "$.candidate_snapshot_hashes",
                "must hash every canonical candidate snapshot exactly once",
            )
        object.__setattr__(
            self, "candidate_snapshot_hashes", MappingProxyType(claimed_candidate_hashes)
        )
        raw_preflights = _mapping(self.preflight_decisions, path="$.preflight_decisions")
        if set(raw_preflights) != set(candidate_ids):
            _fail(
                "preflight_candidate_set_mismatch",
                "$.preflight_decisions",
                "must contain exactly one decision per candidate",
            )
        preflights: dict[str, PreflightDecision] = {}
        candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
        for candidate_id in candidate_ids:
            decision = validate_preflight_decision(raw_preflights[candidate_id])
            if decision.candidate_id != candidate_id:
                _fail(
                    "preflight_candidate_id_mismatch",
                    f"$.preflight_decisions.{candidate_id}.candidate_id",
                    "must match its mapping key",
                )
            if decision.selection_scope_id != expected_scope_id:
                _fail(
                    "preflight_scope_mismatch",
                    f"$.preflight_decisions.{candidate_id}.selection_scope_id",
                    "must bind to the panel selection_scope_id",
                )
            candidate_readiness_hashes = {
                item["surface_id"]: item["snapshot_hash"]
                for item in candidates_by_id[candidate_id].source_readiness_snapshot
            }
            if candidate_readiness_hashes != dict(decision.source_snapshot_hashes):
                _fail(
                    "candidate_preflight_readiness_mismatch",
                    f"$.preflight_decisions.{candidate_id}.source_snapshot_hashes",
                    "must equal the readiness hashes frozen in the candidate snapshot",
                )
            candidate = candidates_by_id[candidate_id]
            if candidate.candidate_kind == "plain_event_lead":
                if (
                    decision.decision != "park"
                    or decision.gates["D1"]["status"] != "park"
                    or FailureReason.MARKET_EXPECTATION_UNIDENTIFIED
                    not in decision.failure_reasons
                ):
                    _fail(
                        "plain_event_preflight_mismatch",
                        f"$.preflight_decisions.{candidate_id}",
                        "plain_event_lead must park at D1 with market_expectation_unidentified",
                    )
            preflights[candidate_id] = decision
        object.__setattr__(self, "preflight_decisions", MappingProxyType(preflights))
        expected_preflight_hashes = {
            candidate_id: decision.preflight_hash
            for candidate_id, decision in preflights.items()
        }
        raw_preflight_hashes = _mapping(
            self.preflight_decision_hashes, path="$.preflight_decision_hashes"
        )
        claimed_preflight_hashes = {
            _text(key, path="$.preflight_decision_hashes.<key>"): _sha256_digest(
                value, path=f"$.preflight_decision_hashes.{key}"
            )
            for key, value in sorted(raw_preflight_hashes.items())
        }
        if claimed_preflight_hashes != expected_preflight_hashes:
            _fail(
                "preflight_decision_hash_mismatch",
                "$.preflight_decision_hashes",
                "must match canonical preflight decisions",
            )
        object.__setattr__(
            self, "preflight_decision_hashes", MappingProxyType(claimed_preflight_hashes)
        )

        raw_scores = _mapping(self.scores, path="$.scores")
        if set(raw_scores) != set(candidate_ids):
            _fail("score_candidate_set_mismatch", "$.scores", "must score every candidate")
        scores: dict[str, Mapping[str, Any]] = {}
        for candidate_id in candidate_ids:
            score_path = f"$.scores.{candidate_id}"
            raw_score = _mapping(raw_scores[candidate_id], path=score_path)
            _reject_outcomes(raw_score, path=score_path)
            if raw_score.get("outcome_blind") is not True:
                _fail("outcome_contamination", f"{score_path}.outcome_blind", "must be true")
            if raw_score.get("score_version") != self.score_version:
                _fail("score_version_mismatch", f"{score_path}.score_version", "must match panel")
            total = raw_score.get("total")
            if (
                not isinstance(total, (int, float))
                or isinstance(total, bool)
                or not math.isfinite(float(total))
            ):
                _fail("invalid_score", f"{score_path}.total", "must be a finite number")
            scores[candidate_id] = _frozen_json(raw_score, path=score_path)
        object.__setattr__(self, "scores", MappingProxyType(scores))

        raw_rejections = _mapping(self.rejection_reasons, path="$.rejection_reasons")
        expected_rejected = {
            candidate_id
            for candidate_id, preflight in preflights.items()
            if preflight.decision != "pass"
        }
        if set(raw_rejections) != expected_rejected:
            _fail(
                "rejection_reason_set_mismatch",
                "$.rejection_reasons",
                "must contain exactly every park/reject candidate",
            )
        rejections: dict[str, tuple[FailureReason, ...]] = {}
        for candidate_id in sorted(expected_rejected):
            if not isinstance(raw_rejections[candidate_id], Sequence) or isinstance(
                raw_rejections[candidate_id], (str, bytes, bytearray)
            ):
                _fail("list_required", f"$.rejection_reasons.{candidate_id}", "must be a list")
            reasons = tuple(
                sorted(
                    {
                        _failure_reason(reason, path=f"$.rejection_reasons.{candidate_id}")
                        for reason in raw_rejections[candidate_id]
                    },
                    key=lambda reason: reason.value,
                )
            )
            if reasons != preflights[candidate_id].failure_reasons:
                _fail(
                    "rejection_reason_mismatch",
                    f"$.rejection_reasons.{candidate_id}",
                    "must equal its preflight failure reasons",
                )
            rejections[candidate_id] = reasons
        object.__setattr__(self, "rejection_reasons", MappingProxyType(rejections))

        limit = _nonnegative_integer(self.selection_limit, path="$.selection_limit")
        if limit == 0:
            _fail("selection_limit_required", "$.selection_limit", "must be positive")
        if limit != manifest["selection_limit"]:
            _fail(
                "scope_manifest_binding_mismatch",
                "$.selection_limit",
                "must equal preregistered selection limit",
            )
        object.__setattr__(self, "selection_limit", limit)
        batch_policy_bundle_id = (
            None
            if self.batch_policy_bundle_id is None
            else _text(self.batch_policy_bundle_id, path="$.batch_policy_bundle_id")
        )
        if batch_policy_bundle_id != manifest["batch_policy_bundle_id"]:
            _fail(
                "scope_manifest_binding_mismatch",
                "$.batch_policy_bundle_id",
                "must equal preregistered batch policy bundle",
            )
        object.__setattr__(self, "batch_policy_bundle_id", batch_policy_bundle_id)
        selected_ids = _string_tuple(
            self.selected_candidate_ids,
            path="$.selected_candidate_ids",
            required=False,
        )
        if len(selected_ids) > limit:
            _fail("selection_limit_exceeded", "$.selected_candidate_ids", "too many selected")
        pass_ids = {
            candidate_id
            for candidate_id, preflight in preflights.items()
            if preflight.decision == "pass"
        }
        if not set(selected_ids) <= pass_ids:
            _fail("ineligible_candidate_selected", "$.selected_candidate_ids", "only pass candidates may be selected")
        object.__setattr__(self, "selected_candidate_ids", selected_ids)
        expected_single = selected_ids[0] if limit == 1 and selected_ids else None
        selected_candidate_id = (
            None
            if self.selected_candidate_id is None
            else _text(self.selected_candidate_id, path="$.selected_candidate_id")
        )
        if selected_candidate_id != expected_single:
            _fail(
                "selected_candidate_id_mismatch",
                "$.selected_candidate_id",
                "must name the sole selected candidate only when selection_limit is one",
            )
        object.__setattr__(self, "selected_candidate_id", selected_candidate_id)
        object.__setattr__(
            self, "selection_reason", _text(self.selection_reason, path="$.selection_reason")
        )
        if _boolean(self.outcome_blind, path="$.outcome_blind") is not True:
            _fail("outcome_contamination", "$.outcome_blind", "must be true")
        object.__setattr__(self, "outcome_blind", True)
        for field_name in ("trade_enabled", "experiment_id_reserved"):
            if _boolean(getattr(self, field_name), path=f"$.{field_name}") is not False:
                _fail("research_boundary_not_false", f"$.{field_name}", "must be false")
            object.__setattr__(self, field_name, False)
        object.__setattr__(
            self,
            "production_impact",
            _production_impact(self.production_impact, path="$.production_impact"),
        )

        claimed_panel_hash = _sha256_digest(self.panel_hash, path="$.panel_hash")
        object.__setattr__(self, "panel_hash", claimed_panel_hash)
        if claimed_panel_hash != _semantic_hash(self.to_dict()):
            _fail("panel_hash_mismatch", "$.panel_hash", "does not match canonical rich panel")

    @property
    def candidates(self) -> tuple[HypothesisCandidate, ...]:
        """Compatibility alias for the former compact panel contract."""

        return self.candidate_snapshots

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SelectionPanel":
        raw = _mapping(value, path="$")
        _reject_outcomes(raw)
        required = {
            "schema_version",
            "record_type",
            "selection_scope_id",
            "created_at",
            "data_cutoff",
            "scope_manifest",
            "scope_manifest_hash",
            "surface_registry_hash",
            "prior_fingerprint_snapshot_hash",
            "prior_fingerprint_count",
            "selector_version",
            "score_version",
            "queue_budgets",
            "queue_actual_counts",
            "expected_candidate_count",
            "candidate_pool_complete",
            "selection_pool_complete",
            "candidate_ids",
            "candidate_snapshots",
            "candidate_snapshot_hashes",
            "preflight_decisions",
            "preflight_decision_hashes",
            "scores",
            "rejection_reasons",
            "selection_limit",
            "batch_policy_bundle_id",
            "selected_candidate_ids",
            "selected_candidate_id",
            "selection_reason",
            "outcome_blind",
            "trade_enabled",
            "experiment_id_reserved",
            "production_impact",
            "panel_hash",
        }
        _check_fields(raw, required=required, path="$")
        return cls(**dict(raw))

    @classmethod
    def build(
        cls,
        candidates: Iterable[HypothesisCandidate | Mapping[str, Any]],
        *,
        scope_manifest: Mapping[str, Any],
    ) -> "SelectionPanel":
        """Compatibility builder for an explicitly parked, unscored snapshot panel."""

        manifest = _scope_manifest(scope_manifest)
        normalised = [
            validate_hypothesis_candidate(candidate).validate_semantic_id()
            for candidate in candidates
        ]
        if not normalised:
            _fail("empty_panel", "$.candidate_snapshots", "selection panel must not be empty")
        by_id = {candidate.candidate_id: candidate for candidate in normalised}
        if len(by_id) != len(normalised):
            _fail("duplicate_candidate_id", "$.candidate_snapshots", "candidate IDs must be unique")
        ordered = [by_id[key] for key in sorted(by_id)]
        candidate_hashes = {
            candidate.candidate_id: _semantic_hash(candidate.to_dict()) for candidate in ordered
        }
        if len(ordered) != manifest["expected_candidate_count"]:
            _fail(
                "candidate_count_mismatch",
                "$.candidate_snapshots",
                "must equal the count frozen in scope_manifest",
            )
        data_cutoff = str(manifest["data_cutoff"])
        queue_actual = {queue: 0 for queue in QUEUE_VALUES}
        for candidate in ordered:
            queue_actual[candidate.search_queue] += 1
        score_version = str(manifest["score_version"])
        selection_scope_id = f"scope-{str(manifest['manifest_hash'])[:24]}"
        preflights: dict[str, dict[str, Any]] = {}
        for candidate in ordered:
            plain_event = candidate.candidate_kind == "plain_event_lead"
            failure_reasons = ["incomplete_selection_panel"]
            if plain_event:
                failure_reasons.append("market_expectation_unidentified")
            preflight = {
                "schema_version": SCHEMA_VERSION,
                "record_type": "preflight_decision",
                "candidate_id": candidate.candidate_id,
                "selection_scope_id": selection_scope_id,
                "evaluated_at": manifest["freeze_at"],
                "preflight_version": "contract-compatibility-v1",
                "data_cutoff": data_cutoff,
                "outcome_blind": True,
                "outcome_fields_excluded": sorted(_FORBIDDEN_OUTCOME_KEYS),
                "source_snapshot_hashes": {
                    item["surface_id"]: item["snapshot_hash"]
                    for item in candidate.source_readiness_snapshot
                },
                "declared_evidence_grade": candidate.evidence_grade,
                "maximum_supported_evidence_grade": candidate.evidence_grade,
                "fingerprint_hash": canonical_hash(candidate.fingerprint),
                "gates": {
                    "D0": {"status": "pass", "reasons": []},
                    "D1": {
                        "status": "park" if plain_event else "pass",
                        "reasons": ["market_expectation_unidentified"] if plain_event else [],
                    },
                    "D2": {"status": "pass", "reasons": []},
                    "D3": {
                        "status": "park",
                        "reasons": ["explicit_preflight_required"],
                    },
                },
                "decision": "park",
                "failure_reasons": sorted(failure_reasons),
                "reopen_condition": "provide explicit D0-D3 preflight decisions",
                "trade_enabled": False,
                "production_impact": research_only_production_impact(),
            }
            preflight["preflight_hash"] = _semantic_hash(preflight)
            preflights[candidate.candidate_id] = PreflightDecision.from_dict(preflight).to_dict()
        scores = {
            candidate.candidate_id: {
                "score_version": score_version,
                "outcome_blind": True,
                "components": {},
                "weights": {},
                "total": 0.0,
            }
            for candidate in ordered
        }
        panel: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "panel_selection",
            "created_at": manifest["freeze_at"],
            "data_cutoff": data_cutoff,
            "scope_manifest": _plain(manifest),
            "scope_manifest_hash": manifest["manifest_hash"],
            "surface_registry_hash": manifest["surface_registry_hash"],
            "prior_fingerprint_snapshot_hash": manifest[
                "prior_fingerprint_snapshot_hash"
            ],
            "prior_fingerprint_count": manifest["prior_fingerprint_count"],
            "selector_version": manifest["selector_version"],
            "score_version": score_version,
            "queue_budgets": _plain(manifest["queue_budgets"]),
            "queue_actual_counts": queue_actual,
            "expected_candidate_count": len(ordered),
            "candidate_pool_complete": True,
            "selection_pool_complete": True,
            "candidate_ids": [candidate.candidate_id for candidate in ordered],
            "candidate_snapshots": [candidate.to_dict() for candidate in ordered],
            "candidate_snapshot_hashes": candidate_hashes,
            "preflight_decisions": preflights,
            "preflight_decision_hashes": {
                candidate_id: preflight["preflight_hash"]
                for candidate_id, preflight in preflights.items()
            },
            "scores": scores,
            "rejection_reasons": {
                candidate.candidate_id: preflights[candidate.candidate_id]["failure_reasons"]
                for candidate in ordered
            },
            "selection_limit": manifest["selection_limit"],
            "batch_policy_bundle_id": manifest["batch_policy_bundle_id"],
            "selected_candidate_ids": [],
            "selected_candidate_id": None,
            "selection_reason": "compatibility snapshot only; explicit preflight is required",
            "outcome_blind": True,
            "trade_enabled": False,
            "experiment_id_reserved": False,
            "production_impact": research_only_production_impact(),
        }
        panel["selection_scope_id"] = selection_scope_id
        panel["panel_hash"] = _semantic_hash(panel)
        return cls.from_dict(panel)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "selection_scope_id": self.selection_scope_id,
            "created_at": self.created_at,
            "data_cutoff": self.data_cutoff,
            "scope_manifest": _plain(self.scope_manifest),
            "scope_manifest_hash": self.scope_manifest_hash,
            "surface_registry_hash": self.surface_registry_hash,
            "prior_fingerprint_snapshot_hash": self.prior_fingerprint_snapshot_hash,
            "prior_fingerprint_count": self.prior_fingerprint_count,
            "selector_version": self.selector_version,
            "score_version": self.score_version,
            "queue_budgets": _plain(self.queue_budgets),
            "queue_actual_counts": _plain(self.queue_actual_counts),
            "expected_candidate_count": self.expected_candidate_count,
            "candidate_pool_complete": self.candidate_pool_complete,
            "selection_pool_complete": self.selection_pool_complete,
            "candidate_ids": list(self.candidate_ids),
            "candidate_snapshots": [candidate.to_dict() for candidate in self.candidate_snapshots],
            "candidate_snapshot_hashes": _plain(self.candidate_snapshot_hashes),
            "preflight_decisions": {
                key: value.to_dict() for key, value in self.preflight_decisions.items()
            },
            "preflight_decision_hashes": _plain(self.preflight_decision_hashes),
            "scores": _plain(self.scores),
            "rejection_reasons": {
                key: [reason.value for reason in reasons]
                for key, reasons in self.rejection_reasons.items()
            },
            "selection_limit": self.selection_limit,
            "batch_policy_bundle_id": self.batch_policy_bundle_id,
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "selected_candidate_id": self.selected_candidate_id,
            "selection_reason": self.selection_reason,
            "outcome_blind": self.outcome_blind,
            "trade_enabled": self.trade_enabled,
            "experiment_id_reserved": self.experiment_id_reserved,
            "production_impact": _plain(self.production_impact),
            "panel_hash": self.panel_hash,
        }

    def validate(self) -> "SelectionPanel":
        return SelectionPanel.from_dict(self.to_dict())


def validate_evidence_surface(value: EvidenceSurface | Mapping[str, Any]) -> EvidenceSurface:
    if isinstance(value, EvidenceSurface):
        return EvidenceSurface.from_dict(value.to_dict())
    return EvidenceSurface.from_dict(value)


def normalize_evidence_surface(value: EvidenceSurface | Mapping[str, Any]) -> dict[str, Any]:
    return validate_evidence_surface(value).to_dict()


def validate_expectation_gap(value: ExpectationGap | Mapping[str, Any]) -> ExpectationGap:
    if isinstance(value, ExpectationGap):
        return ExpectationGap.from_dict(value.to_dict())
    return ExpectationGap.from_dict(value)


def normalize_expectation_gap(value: ExpectationGap | Mapping[str, Any]) -> dict[str, Any]:
    return validate_expectation_gap(value).to_dict()


def validate_hypothesis_candidate(
    value: HypothesisCandidate | Mapping[str, Any],
) -> HypothesisCandidate:
    if isinstance(value, HypothesisCandidate):
        return HypothesisCandidate.from_dict(value.to_dict())
    return HypothesisCandidate.from_dict(value)


def normalize_hypothesis_candidate(
    value: HypothesisCandidate | Mapping[str, Any],
) -> dict[str, Any]:
    return validate_hypothesis_candidate(value).to_dict()


def build_hypothesis_candidate(value: Mapping[str, Any]) -> HypothesisCandidate:
    """Build a candidate with its deterministic semantic ``cand-`` identity."""

    return HypothesisCandidate.with_computed_id(value)


def compute_candidate_id(value: HypothesisCandidate | Mapping[str, Any]) -> str:
    if isinstance(value, HypothesisCandidate):
        return value.expected_candidate_id
    return build_hypothesis_candidate(value).candidate_id


def validate_candidate_semantic_id(
    value: HypothesisCandidate | Mapping[str, Any],
) -> HypothesisCandidate:
    return validate_hypothesis_candidate(value).validate_semantic_id()


def validate_preflight_decision(
    value: PreflightDecision | Mapping[str, Any],
) -> PreflightDecision:
    if isinstance(value, PreflightDecision):
        return PreflightDecision.from_dict(value.to_dict())
    return PreflightDecision.from_dict(value)


def build_selection_panel(
    candidates: Iterable[HypothesisCandidate | Mapping[str, Any]],
    *,
    scope_manifest: Mapping[str, Any],
) -> SelectionPanel:
    return SelectionPanel.build(candidates, scope_manifest=scope_manifest)


def normalize_preflight_decision(
    value: PreflightDecision | Mapping[str, Any],
) -> dict[str, Any]:
    return validate_preflight_decision(value).to_dict()


def validate_selection_scope_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize the preregistered selection-scope anchor."""

    return _plain(_scope_manifest(value))


def normalize_selection_scope_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    return validate_selection_scope_manifest(value)


def validate_selection_panel(
    value: SelectionPanel | Mapping[str, Any],
) -> SelectionPanel:
    if isinstance(value, SelectionPanel):
        return value.validate()
    return SelectionPanel.from_dict(value)


def normalize_selection_panel(
    value: SelectionPanel | Mapping[str, Any],
) -> dict[str, Any]:
    return validate_selection_panel(value).to_dict()


__all__ = [
    "SCHEMA_VERSION",
    "SCOPE_MANIFEST_VERSION",
    "QUEUE_VALUES",
    "QUEUE_ALIASES",
    "EXPECTATION_PROXY_ALIASES",
    "CANDIDATE_KINDS",
    "EVIDENCE_GRADES",
    "PIT_STATUSES",
    "SATURATION_STATUSES",
    "SOURCE_CONTRACT_STATUSES",
    "FailureReason",
    "ContractValidationError",
    "EvidenceSurface",
    "ExpectationGap",
    "HypothesisCandidate",
    "PreflightDecision",
    "SelectionPanel",
    "canonical_json",
    "canonical_hash",
    "research_only_production_impact",
    "validate_evidence_surface",
    "normalize_evidence_surface",
    "validate_expectation_gap",
    "normalize_expectation_gap",
    "validate_hypothesis_candidate",
    "normalize_hypothesis_candidate",
    "build_hypothesis_candidate",
    "compute_candidate_id",
    "validate_candidate_semantic_id",
    "validate_preflight_decision",
    "normalize_preflight_decision",
    "validate_selection_scope_manifest",
    "normalize_selection_scope_manifest",
    "build_selection_panel",
    "validate_selection_panel",
    "normalize_selection_panel",
]
