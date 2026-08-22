"""Fail-closed contract for outcome-blind external mechanism scans.

An external mechanism generator is a proposal source for the research map.  It
is deliberately *not* an :class:`EvidenceSurface`, a strategy, a selector, or
an experiment launcher.  This module validates an agent-produced scan and
renders deterministic lead-only research-map sections.  A strict
``HypothesisCandidate`` projection is optional and is emitted only when the
scan explicitly names surface IDs that the caller has verified against an
existing surface registry.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from quant.alpha_search_contract import (
    HypothesisCandidate,
    canonical_hash,
    research_only_production_impact,
)


SCHEMA_VERSION = 1
SCAN_RECORD_TYPE = "external_mechanism_scan"
OUTPUT_RECORD_TYPE = "external_mechanism_lead_batch"
LEAD_RECORD_TYPE = "research_map_mechanism_lead"
HISTORY_POLICY = "veto_after_generation_only"

_ALLOWED_QUEUES = frozenset({"exploration", "adjacent", "exploitation"})
_AUTHORIZATION_STATUSES = frozenset({"pass", "partial", "fail", "unverified"})
_PIT_STATUSES = frozenset(
    {
        "canonical_pit",
        "research_pit",
        "snapshot_only",
        "pit_forward_unsettled",
        "not_pit",
        "unproven",
    }
)
_EXPECTATION_STATUSES = frozenset({"observable", "unidentified"})
_EXPECTATION_PROXY_TYPES = frozenset(
    {
        "direct_implied_probability",
        "explicit_consensus",
        "price_revealed",
        "positioning_constraint",
        "unidentified",
    }
)
_HISTORY_EFFECTS = frozenset({"no_conflict", "park", "reject_near_neighbor"})

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
        "max_drawdown",
        "mae",
        "mae_bps",
        "mae_pct",
        "max_adverse_excursion",
        "max_favorable_excursion",
        "max_favourable_excursion",
        "maximum_adverse_excursion",
        "maximum_favorable_excursion",
        "maximum_favourable_excursion",
        "mfe",
        "mfe_bps",
        "mfe_pct",
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
_FORBIDDEN_OUTCOME_PARTS = (
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
    "max_adverse_excursion",
    "max_favorable_excursion",
    "max_favourable_excursion",
    "maximum_adverse_excursion",
    "maximum_favorable_excursion",
    "maximum_favourable_excursion",
    "adverse_excursion",
    "favorable_excursion",
    "favourable_excursion",
)
_FORBIDDEN_OUTCOME_PREFIXES = ("mae_", "mfe_")
_FORBIDDEN_OUTCOME_SUFFIXES = (
    "_return",
    "_returns",
    "_pnl",
    "_sharpe",
    "_sortino",
    "_drawdown",
    "_win_rate",
)

_PERMISSION_KEYS = frozenset(
    {
        "allow_orders",
        "allow_panel_building",
        "allow_ranking",
        "allow_replay",
        "allow_strategy_mutation",
        "allow_trading",
        "backtester_adapter_changed",
        "build_panel",
        "can_place_orders",
        "can_rank",
        "can_reserve_experiment",
        "can_trade",
        "candidate_ranking_enabled",
        "daily_snapshot_exposed",
        "entry_rules_changed",
        "experiment_id_reserved",
        "experiment_reservation",
        "experiment_reservation_allowed",
        "exit_rules_changed",
        "live_ready",
        "live_realism_evaluated",
        "order_placement",
        "order_placement_allowed",
        "orders",
        "orders_allowed",
        "orders_changed",
        "orders_enabled",
        "panel",
        "panel_building",
        "panel_building_allowed",
        "panel_built",
        "parity_test_added",
        "policy_mutation",
        "ranking",
        "ranking_allowed",
        "ranking_changed",
        "ranking_enabled",
        "replay_only",
        "reserve_experiment",
        "reserve_experiment_id",
        "run_adapter_changed",
        "selection_enabled",
        "shared_policy_changed",
        "sizing_changed",
        "strategy_changed",
        "strategy_mutation",
        "strategy_mutation_allowed",
        "trade",
        "trade_allowed",
        "trade_enabled",
        "trading",
        "trading_allowed",
    }
)


class MechanismScanError(ValueError):
    """Validation failure with a stable machine-readable code and path."""

    def __init__(self, code: str, path: str, detail: str):
        self.code = str(code)
        self.path = str(path)
        self.detail = str(detail)
        super().__init__(f"[{self.code}] {self.path}: {self.detail}")


def _fail(code: str, path: str, detail: str) -> None:
    raise MechanismScanError(code, path, detail)


def _mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("mapping_required", path, "must be an object")
    if any(not isinstance(key, str) for key in value):
        _fail("string_key_required", path, "all object keys must be strings")
    return value


def _fields(
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


def _text(value: Any, *, path: str, lower: bool = False) -> str:
    if not isinstance(value, str):
        _fail("string_required", path, "must be a string")
    result = value.strip()
    if not result:
        _fail("empty_string", path, "must not be empty")
    return result.lower() if lower else result


def _line_text(value: Any, *, path: str) -> str:
    result = _text(value, path=path)
    return " ".join(result.split())


def _false(value: Any, *, path: str) -> bool:
    if value is not False:
        _fail("research_permission_not_false", path, "must be false")
    return False


def _true(value: Any, *, path: str) -> bool:
    if value is not True:
        _fail("required_true", path, "must be true")
    return True


def _sequence(value: Any, *, path: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list")
    return value


def _string_list(
    value: Any,
    *,
    path: str,
    minimum: int = 0,
    lower: bool = False,
) -> list[str]:
    rows = _sequence(value, path=path)
    result = sorted(
        {
            _text(item, path=f"{path}[{index}]", lower=lower)
            for index, item in enumerate(rows)
        }
    )
    if len(result) < minimum:
        _fail("insufficient_values", path, f"requires at least {minimum} distinct values")
    return result


def _timestamp(value: Any, *, path: str) -> tuple[str, datetime]:
    text = _text(value, path=path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MechanismScanError("invalid_timestamp", path, "must be ISO-8601") from exc
    if parsed.tzinfo is None:
        _fail("timezone_required", path, "must include a timezone")
    utc = parsed.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z"), utc


def _sha256(value: Any, *, path: str) -> str:
    digest = _text(value, path=path, lower=True)
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        _fail("invalid_sha256", path, "must be a 64-character hexadecimal SHA-256 digest")
    return digest


def _reject_outcome_fields(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = re.sub(r"[^a-z0-9]+", "_", str(raw_key).strip().lower()).strip("_")
            item_path = f"{path}.{raw_key}"
            if (
                key in _FORBIDDEN_OUTCOME_KEYS
                or key.startswith(_FORBIDDEN_OUTCOME_PREFIXES)
                or re.match(r"^(?:mae|mfe)(?:\d|_|$)", key) is not None
                or key.endswith(_FORBIDDEN_OUTCOME_SUFFIXES)
                or any(part in key for part in _FORBIDDEN_OUTCOME_PARTS)
            ):
                _fail(
                    "forbidden_outcome_field",
                    item_path,
                    "realized outcomes and performance may not enter mechanism generation",
                )
            _reject_outcome_fields(item, path=item_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_outcome_fields(item, path=f"{path}[{index}]")


def _reject_permission_escalation(value: Any, *, path: str = "$") -> None:
    """Require every permission-like declaration anywhere in a scan to be false."""

    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = re.sub(r"[^a-z0-9]+", "_", str(raw_key).strip().lower()).strip("_")
            item_path = f"{path}.{raw_key}"
            if key in _PERMISSION_KEYS and item is not False:
                _fail(
                    "permission_escalation",
                    item_path,
                    "mechanism-generation permission declarations must be exactly false",
                )
            _reject_permission_escalation(item, path=item_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_permission_escalation(item, path=f"{path}[{index}]")


def _normalised_source_fingerprint(publisher: str, url: str) -> tuple[str, str]:
    normalised_publisher = " ".join(publisher.casefold().split())
    parsed = urlsplit(url)
    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    normalised_url = urlunsplit(
        # Query strings and fragments do not create an independent publisher
        # or document family; ignoring them also closes tracking-parameter
        # aliases such as ``?utm_source=...``.
        (parsed.scheme.casefold(), parsed.netloc.casefold(), path, "", "")
    )
    return normalised_publisher, normalised_url


def _markdown_inline(value: Any) -> str:
    """Collapse rendered free text and escape marker/heading-looking prefixes."""

    text = " ".join(str(value).split())
    if re.match(r"^(?:#{1,6}\s|```|[a-z][a-z0-9_-]*\s*:)", text, re.IGNORECASE):
        return "\\" + text
    return text


def _plain(value: Any) -> Any:
    """Return JSON-shaped values with deterministic mapping key order."""

    if isinstance(value, Mapping):
        return {str(key): _plain(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _normalise_registry(value: Any) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    raw = _mapping(value, path="$.generator_registry")
    _fields(
        raw,
        required={"schema_version", "registry_version", "generators"},
        path="$.generator_registry",
    )
    if raw["schema_version"] != SCHEMA_VERSION or isinstance(raw["schema_version"], bool):
        _fail("schema_version_mismatch", "$.generator_registry.schema_version", "must equal 1")
    registry_version = _text(
        raw["registry_version"], path="$.generator_registry.registry_version"
    )
    generators: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(_sequence(raw["generators"], path="$.generator_registry.generators")):
        path = f"$.generator_registry.generators[{index}]"
        row = _mapping(item, path=path)
        _fields(
            row,
            required={
                "generator_id",
                "generator_version",
                "skill",
                "skill_sha256",
                "research_timezone",
                "status",
                "stage",
                "max_leads",
                "min_independent_source_groups",
                "allowed_queues",
                "history_policy",
                "output_evidence_grade",
                "permissions",
            },
            path=path,
        )
        generator_id = _text(row["generator_id"], path=f"{path}.generator_id", lower=True)
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", generator_id) is None:
            _fail("invalid_generator_id", f"{path}.generator_id", "must be marker-safe")
        if generator_id in generators:
            _fail("duplicate_generator", f"{path}.generator_id", generator_id)
        max_leads = row["max_leads"]
        min_groups = row["min_independent_source_groups"]
        for name, count in (("max_leads", max_leads), ("min_independent_source_groups", min_groups)):
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                _fail("nonnegative_integer_required", f"{path}.{name}", "must be an integer >= 0")
        if max_leads > 2:
            _fail("generator_lead_cap_exceeded", f"{path}.max_leads", "may not exceed 2")
        if min_groups < 2:
            _fail(
                "source_independence_contract_too_weak",
                f"{path}.min_independent_source_groups",
                "must be at least 2",
            )
        allowed_queues = _string_list(
            row["allowed_queues"], path=f"{path}.allowed_queues", minimum=1, lower=True
        )
        if not set(allowed_queues) <= _ALLOWED_QUEUES:
            _fail("invalid_queue", f"{path}.allowed_queues", "contains an unknown queue")
        if _text(row["history_policy"], path=f"{path}.history_policy", lower=True) != HISTORY_POLICY:
            _fail("invalid_history_policy", f"{path}.history_policy", f"must equal {HISTORY_POLICY}")
        if _text(row["output_evidence_grade"], path=f"{path}.output_evidence_grade", lower=True) != "lead":
            _fail("generator_grade_not_lead", f"{path}.output_evidence_grade", "must equal lead")
        status = _text(row["status"], path=f"{path}.status", lower=True)
        if status not in {"active", "disabled"}:
            _fail("invalid_generator_status", f"{path}.status", "must be active or disabled")
        permissions = _mapping(row["permissions"], path=f"{path}.permissions")
        permission_fields = {
            "experiment_reservation",
            "trading",
            "orders",
            "ranking",
            "strategy_mutation",
            "panel_building",
        }
        _fields(permissions, required=permission_fields, path=f"{path}.permissions")
        normalised_permissions = {
            key: _false(permissions[key], path=f"{path}.permissions.{key}")
            for key in sorted(permission_fields)
        }
        generator_version = _line_text(
            row["generator_version"], path=f"{path}.generator_version"
        )
        if re.fullmatch(r"[^\s]+", generator_version) is None:
            _fail("invalid_generator_version", f"{path}.generator_version", "must not contain whitespace")
        generators[generator_id] = {
            "generator_id": generator_id,
            "generator_version": generator_version,
            "skill": _text(row["skill"], path=f"{path}.skill"),
            "skill_sha256": _sha256(row["skill_sha256"], path=f"{path}.skill_sha256"),
            "research_timezone": _text(
                row["research_timezone"], path=f"{path}.research_timezone"
            ),
            "status": status,
            "stage": _text(row["stage"], path=f"{path}.stage", lower=True),
            "max_leads": max_leads,
            "min_independent_source_groups": min_groups,
            "allowed_queues": allowed_queues,
            "history_policy": HISTORY_POLICY,
            "output_evidence_grade": "lead",
            "permissions": normalised_permissions,
        }
    if not generators:
        _fail("empty_generator_registry", "$.generator_registry.generators", "must not be empty")
    normalised = {
        "schema_version": SCHEMA_VERSION,
        "registry_version": registry_version,
        "generators": [generators[key] for key in sorted(generators)],
    }
    return normalised, generators


def _normalise_source_groups(
    value: Any,
    *,
    path: str,
    data_cutoff: datetime,
    minimum: int,
) -> list[dict[str, Any]]:
    rows = _sequence(value, path=path)
    if len(rows) < minimum:
        _fail(
            "insufficient_independent_source_groups",
            path,
            f"requires at least {minimum} source groups",
        )
    by_group: dict[str, dict[str, Any]] = {}
    independence_keys: set[str] = set()
    source_ids: set[str] = set()
    source_fingerprints: dict[tuple[str, str], str] = {}
    publisher_groups: dict[str, str] = {}
    url_groups: dict[str, str] = {}
    for index, item in enumerate(rows):
        item_path = f"{path}[{index}]"
        row = _mapping(item, path=item_path)
        _fields(
            row,
            required={
                "group_id",
                "independence_key",
                "independence_basis",
                "evidence_summary",
                "sources",
            },
            path=item_path,
        )
        group_id = _text(row["group_id"], path=f"{item_path}.group_id", lower=True)
        if group_id in by_group:
            _fail("duplicate_source_group", f"{item_path}.group_id", group_id)
        independence_key = _text(
            row["independence_key"], path=f"{item_path}.independence_key", lower=True
        )
        if independence_key in independence_keys:
            _fail(
                "source_groups_not_independent",
                f"{item_path}.independence_key",
                "independence_key must be distinct across groups",
            )
        independence_keys.add(independence_key)
        sources: list[dict[str, Any]] = []
        raw_sources = _sequence(row["sources"], path=f"{item_path}.sources")
        if not raw_sources:
            _fail("empty_source_group", f"{item_path}.sources", "must contain a source")
        for source_index, source_item in enumerate(raw_sources):
            source_path = f"{item_path}.sources[{source_index}]"
            source = _mapping(source_item, path=source_path)
            _fields(
                source,
                required={
                    "source_id",
                    "publisher",
                    "url",
                    "source_type",
                    "known_at",
                    "authorization_status",
                    "authorization_basis",
                    "pit_status",
                    "pit_basis",
                },
                path=source_path,
            )
            source_id = _text(source["source_id"], path=f"{source_path}.source_id", lower=True)
            if source_id in source_ids:
                _fail("duplicate_source", f"{source_path}.source_id", source_id)
            source_ids.add(source_id)
            url = _text(source["url"], path=f"{source_path}.url")
            if re.match(r"^https?://", url, flags=re.IGNORECASE) is None:
                _fail("invalid_source_url", f"{source_path}.url", "must be an http(s) URL")
            publisher = _line_text(source["publisher"], path=f"{source_path}.publisher")
            source_fingerprint = _normalised_source_fingerprint(publisher, url)
            normalised_publisher = source_fingerprint[0]
            prior_publisher_group = publisher_groups.get(normalised_publisher)
            if prior_publisher_group is not None and prior_publisher_group != group_id:
                _fail(
                    "source_groups_not_independent",
                    f"{source_path}.publisher",
                    "the same normalized publisher appears in distinct source groups "
                    f"{prior_publisher_group!r} and {group_id!r}",
                )
            publisher_groups[normalised_publisher] = group_id
            normalised_url = source_fingerprint[1]
            prior_url_group = url_groups.get(normalised_url)
            if prior_url_group is not None and prior_url_group != group_id:
                _fail(
                    "source_groups_not_independent",
                    f"{source_path}.url",
                    "the same normalized URL appears in distinct source groups "
                    f"{prior_url_group!r} and {group_id!r}",
                )
            url_groups[normalised_url] = group_id
            if source_fingerprint in source_fingerprints:
                _fail(
                    "duplicate_underlying_source",
                    source_path,
                    "normalized publisher+URL duplicates a source in group "
                    f"{source_fingerprints[source_fingerprint]!r}; it cannot establish independence",
                )
            source_fingerprints[source_fingerprint] = group_id
            known_at, known_clock = _timestamp(source["known_at"], path=f"{source_path}.known_at")
            if known_clock > data_cutoff:
                _fail("source_after_data_cutoff", f"{source_path}.known_at", "must not exceed data_cutoff")
            authorization_status = _text(
                source["authorization_status"],
                path=f"{source_path}.authorization_status",
                lower=True,
            )
            if authorization_status not in _AUTHORIZATION_STATUSES:
                _fail(
                    "invalid_authorization_status",
                    f"{source_path}.authorization_status",
                    f"must be one of {sorted(_AUTHORIZATION_STATUSES)}",
                )
            pit_status = _text(
                source["pit_status"], path=f"{source_path}.pit_status", lower=True
            )
            if pit_status not in _PIT_STATUSES:
                _fail(
                    "invalid_pit_status",
                    f"{source_path}.pit_status",
                    f"must be one of {sorted(_PIT_STATUSES)}",
                )
            sources.append(
                {
                    "source_id": source_id,
                    "publisher": publisher,
                    "url": url,
                    "source_type": _text(
                        source["source_type"], path=f"{source_path}.source_type", lower=True
                    ),
                    "known_at": known_at,
                    "authorization_status": authorization_status,
                    "authorization_basis": _text(
                        source["authorization_basis"], path=f"{source_path}.authorization_basis"
                    ),
                    "pit_status": pit_status,
                    "pit_basis": _text(source["pit_basis"], path=f"{source_path}.pit_basis"),
                }
            )
        by_group[group_id] = {
            "group_id": group_id,
            "independence_key": independence_key,
            "independence_basis": _text(
                row["independence_basis"], path=f"{item_path}.independence_basis"
            ),
            "evidence_summary": _text(
                row["evidence_summary"], path=f"{item_path}.evidence_summary"
            ),
            "sources": sorted(sources, key=lambda item: item["source_id"]),
        }
    if len(independence_keys) < minimum:
        _fail("insufficient_independent_source_groups", path, f"requires {minimum} independent keys")
    return [by_group[key] for key in sorted(by_group)]


def _normalise_counterevidence(
    value: Any,
    *,
    path: str,
    source_group_ids: set[str],
) -> list[dict[str, Any]]:
    rows = _sequence(value, path=path)
    if not rows:
        _fail("counterevidence_required", path, "must include at least one contrary observation")
    by_hash: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(rows):
        item_path = f"{path}[{index}]"
        row = _mapping(item, path=item_path)
        _fields(
            row,
            required={"statement", "source_group_ids", "implication"},
            path=item_path,
        )
        refs = _string_list(
            row["source_group_ids"], path=f"{item_path}.source_group_ids", minimum=1, lower=True
        )
        unknown = sorted(set(refs) - source_group_ids)
        if unknown:
            _fail("unknown_source_group", f"{item_path}.source_group_ids", str(unknown))
        normalised = {
            "statement": _line_text(row["statement"], path=f"{item_path}.statement"),
            "source_group_ids": refs,
            "implication": _line_text(row["implication"], path=f"{item_path}.implication"),
        }
        by_hash[canonical_hash(normalised)] = normalised
    return [by_hash[key] for key in sorted(by_hash)]


def _normalise_market_expectation(
    value: Any,
    *,
    path: str,
    source_group_ids: set[str],
    data_cutoff: datetime,
) -> dict[str, Any]:
    row = _mapping(value, path=path)
    _fields(
        row,
        required={"status", "proxy_type", "description", "source_group_id", "known_at"},
        path=path,
    )
    status = _text(row["status"], path=f"{path}.status", lower=True)
    if status not in _EXPECTATION_STATUSES:
        _fail("invalid_expectation_status", f"{path}.status", str(sorted(_EXPECTATION_STATUSES)))
    proxy_type = _text(row["proxy_type"], path=f"{path}.proxy_type", lower=True)
    if proxy_type not in _EXPECTATION_PROXY_TYPES:
        _fail("invalid_expectation_proxy", f"{path}.proxy_type", str(sorted(_EXPECTATION_PROXY_TYPES)))
    source_group_id = row["source_group_id"]
    known_at = row["known_at"]
    if status == "unidentified":
        if proxy_type != "unidentified" or source_group_id is not None or known_at is not None:
            _fail(
                "unidentified_expectation_contract",
                path,
                "unidentified prior requires proxy_type=unidentified and null source_group_id/known_at",
            )
        normalised_source = None
        normalised_known_at = None
    else:
        if proxy_type == "unidentified":
            _fail("observable_expectation_proxy_required", f"{path}.proxy_type", "must be observable")
        normalised_source = _text(source_group_id, path=f"{path}.source_group_id", lower=True)
        if normalised_source not in source_group_ids:
            _fail("unknown_source_group", f"{path}.source_group_id", normalised_source)
        normalised_known_at, known_clock = _timestamp(known_at, path=f"{path}.known_at")
        if known_clock > data_cutoff:
            _fail("expectation_after_data_cutoff", f"{path}.known_at", "must not exceed data_cutoff")
    return {
        "status": status,
        "proxy_type": proxy_type,
        "description": _text(row["description"], path=f"{path}.description"),
        "source_group_id": normalised_source,
        "known_at": normalised_known_at,
    }


def _normalise_policy(value: Any, *, path: str) -> dict[str, Any]:
    row = dict(_mapping(value, path=path))
    if "policy" not in row:
        _fail("missing_field", path, "missing required field: policy")
    row["policy"] = _line_text(row["policy"], path=f"{path}.policy")
    return _plain(row)


def _normalise_execution(value: Any, *, path: str) -> dict[str, Any]:
    row = _mapping(value, path=path)
    required = {
        "intended_instrument",
        "liquidity_dependency",
        "costs_and_carry",
        "borrow_dependency",
        "capacity_constraint",
        "timing_constraint",
        "trade_enabled",
        "orders_enabled",
        "live_ready",
    }
    _fields(row, required=required, path=path)
    result = {
        field: _text(row[field], path=f"{path}.{field}")
        for field in sorted(required - {"trade_enabled", "orders_enabled", "live_ready"})
    }
    for field in ("trade_enabled", "orders_enabled", "live_ready"):
        result[field] = _false(row[field], path=f"{path}.{field}")
    return dict(sorted(result.items()))


def _normalise_fingerprint(
    value: Any,
    *,
    path: str,
    economic_mechanism: str,
    expected_horizon: str,
    expectation_proxy: str,
) -> dict[str, Any]:
    row = _mapping(value, path=path)
    required = {
        "data_source",
        "component_sources",
        "economic_mechanism",
        "decision_surface",
        "payoff_shape",
        "horizon",
        "execution_dependency",
        "portfolio_role",
    }
    _fields(row, required=required, path=path)
    result = {
        "data_source": _text(row["data_source"], path=f"{path}.data_source"),
        "component_sources": _string_list(
            row["component_sources"], path=f"{path}.component_sources", minimum=2
        ),
        "expectation_proxy": expectation_proxy,
        "economic_mechanism": _text(
            row["economic_mechanism"], path=f"{path}.economic_mechanism"
        ),
        "decision_surface": _text(row["decision_surface"], path=f"{path}.decision_surface"),
        "payoff_shape": _text(row["payoff_shape"], path=f"{path}.payoff_shape"),
        "horizon": _text(row["horizon"], path=f"{path}.horizon"),
        "execution_dependency": _text(
            row["execution_dependency"], path=f"{path}.execution_dependency"
        ),
        "portfolio_role": _text(row["portfolio_role"], path=f"{path}.portfolio_role"),
    }
    if result["economic_mechanism"] != economic_mechanism:
        _fail("fingerprint_mismatch", f"{path}.economic_mechanism", "must match lead")
    if result["horizon"] != expected_horizon:
        _fail("fingerprint_mismatch", f"{path}.horizon", "must match expected_horizon")
    return result


def _normalise_lead(
    value: Any,
    *,
    path: str,
    generator: Mapping[str, Any],
    data_cutoff: datetime,
) -> dict[str, Any]:
    row = _mapping(value, path=path)
    _fields(
        row,
        required={
            "lead_key",
            "title",
            "search_queue",
            "hypothesis",
            "bottleneck_node",
            "supply_response_lag",
            "economic_mechanism",
            "causal_chain",
            "source_groups",
            "counterevidence",
            "market_expectation",
            "expectation_gap",
            "why_not_arbitraged",
            "falsifier",
            "baseline",
            "treatment",
            "replacement_value_comparator",
            "expected_horizon",
            "fingerprint",
            "execution_envelope",
            "registered_surface_ids",
            "source_preflight_next_action",
            "reopen_condition",
        },
        optional={"research_refs"},
        path=path,
    )
    lead_key = _text(row["lead_key"], path=f"{path}.lead_key", lower=True)
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", lead_key) is None:
        _fail("invalid_lead_key", f"{path}.lead_key", "use lowercase slug characters")
    queue = _text(row["search_queue"], path=f"{path}.search_queue", lower=True)
    if queue not in set(generator["allowed_queues"]):
        _fail("queue_not_allowed", f"{path}.search_queue", queue)
    causal_chain = [
        _line_text(item, path=f"{path}.causal_chain[{index}]")
        for index, item in enumerate(_sequence(row["causal_chain"], path=f"{path}.causal_chain"))
    ]
    if len(causal_chain) < 3:
        _fail("causal_chain_too_short", f"{path}.causal_chain", "requires at least three ordered links")
    groups = _normalise_source_groups(
        row["source_groups"],
        path=f"{path}.source_groups",
        data_cutoff=data_cutoff,
        minimum=int(generator["min_independent_source_groups"]),
    )
    group_ids = {item["group_id"] for item in groups}
    counterevidence = _normalise_counterevidence(
        row["counterevidence"],
        path=f"{path}.counterevidence",
        source_group_ids=group_ids,
    )
    expectation = _normalise_market_expectation(
        row["market_expectation"],
        path=f"{path}.market_expectation",
        source_group_ids=group_ids,
        data_cutoff=data_cutoff,
    )
    expectation_gap = row["expectation_gap"]
    if expectation["status"] == "unidentified":
        if expectation_gap is not None:
            _fail(
                "unidentified_expectation_gap_forbidden",
                f"{path}.expectation_gap",
                "must be null until a market prior is observable",
            )
        candidate_kind = "plain_event_lead"
    else:
        if not isinstance(expectation_gap, Mapping):
            _fail(
                "observable_expectation_gap_required",
                f"{path}.expectation_gap",
                "must provide the existing strict expectation-gap contract",
            )
        candidate_kind = "expectation_gap"
    economic_mechanism = _text(
        row["economic_mechanism"], path=f"{path}.economic_mechanism"
    )
    expected_horizon = _text(row["expected_horizon"], path=f"{path}.expected_horizon")
    fingerprint = _normalise_fingerprint(
        row["fingerprint"],
        path=f"{path}.fingerprint",
        economic_mechanism=economic_mechanism,
        expected_horizon=expected_horizon,
        expectation_proxy=expectation["proxy_type"],
    )
    registered_surface_ids = _string_list(
        row["registered_surface_ids"],
        path=f"{path}.registered_surface_ids",
        minimum=0,
    )
    research_refs = _string_list(
        row.get("research_refs", []), path=f"{path}.research_refs", minimum=0, lower=True
    )
    for index, ref in enumerate(research_refs):
        if re.fullmatch(r"res-\d{8}-[a-z0-9][a-z0-9._-]*", ref) is None:
            _fail("invalid_research_ref", f"{path}.research_refs[{index}]", ref)
    return {
        "lead_key": lead_key,
        "title": _line_text(row["title"], path=f"{path}.title"),
        "search_queue": queue,
        "hypothesis": _line_text(row["hypothesis"], path=f"{path}.hypothesis"),
        "bottleneck_node": _text(row["bottleneck_node"], path=f"{path}.bottleneck_node"),
        "supply_response_lag": _text(
            row["supply_response_lag"], path=f"{path}.supply_response_lag"
        ),
        "economic_mechanism": economic_mechanism,
        "causal_chain": causal_chain,
        "source_groups": groups,
        "counterevidence": counterevidence,
        "market_expectation": expectation,
        "expectation_gap": None if expectation_gap is None else _plain(expectation_gap),
        "candidate_kind": candidate_kind,
        "why_not_arbitraged": _text(
            row["why_not_arbitraged"], path=f"{path}.why_not_arbitraged"
        ),
        "falsifier": _line_text(row["falsifier"], path=f"{path}.falsifier"),
        "baseline": _normalise_policy(row["baseline"], path=f"{path}.baseline"),
        "treatment": _normalise_policy(row["treatment"], path=f"{path}.treatment"),
        "replacement_value_comparator": _line_text(
            row["replacement_value_comparator"],
            path=f"{path}.replacement_value_comparator",
        ),
        "expected_horizon": expected_horizon,
        "fingerprint": fingerprint,
        "execution_envelope": _normalise_execution(
            row["execution_envelope"], path=f"{path}.execution_envelope"
        ),
        "registered_surface_ids": registered_surface_ids,
        "source_preflight_next_action": _line_text(
            row["source_preflight_next_action"],
            path=f"{path}.source_preflight_next_action",
        ),
        "reopen_condition": _plain(row["reopen_condition"]),
        "research_refs": research_refs,
    }


def _normalise_history_vetoes(
    value: Any,
    *,
    lead_keys: set[str],
    path: str,
) -> dict[str, dict[str, Any]]:
    rows = _sequence(value, path=path)
    by_lead: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(rows):
        item_path = f"{path}[{index}]"
        row = _mapping(item, path=item_path)
        _fields(
            row,
            required={"lead_key", "effect", "prior_experiment_ids", "reason"},
            path=item_path,
        )
        lead_key = _text(row["lead_key"], path=f"{item_path}.lead_key", lower=True)
        if lead_key not in lead_keys:
            _fail("unknown_veto_lead", f"{item_path}.lead_key", lead_key)
        if lead_key in by_lead:
            _fail("duplicate_history_veto", f"{item_path}.lead_key", lead_key)
        effect = _text(row["effect"], path=f"{item_path}.effect", lower=True)
        if effect not in _HISTORY_EFFECTS:
            _fail("invalid_history_veto_effect", f"{item_path}.effect", effect)
        experiment_ids = _string_list(
            row["prior_experiment_ids"],
            path=f"{item_path}.prior_experiment_ids",
            minimum=0,
            lower=True,
        )
        for experiment_id in experiment_ids:
            if re.fullmatch(r"exp-\d{8}-\d{3}", experiment_id) is None:
                _fail("invalid_experiment_id", f"{item_path}.prior_experiment_ids", experiment_id)
        if effect != "no_conflict" and not experiment_ids:
            _fail(
                "history_veto_evidence_required",
                f"{item_path}.prior_experiment_ids",
                "park/reject effects require at least one prior experiment",
            )
        by_lead[lead_key] = {
            "lead_key": lead_key,
            "effect": effect,
            "prior_experiment_ids": experiment_ids,
            "reason": _text(row["reason"], path=f"{item_path}.reason"),
        }
    if set(by_lead) != lead_keys:
        missing = sorted(lead_keys - set(by_lead))
        _fail("history_veto_incomplete", path, f"missing lead decisions: {missing}")
    return by_lead


def _source_contract_summary(lead: Mapping[str, Any]) -> tuple[str, str]:
    authorization = [
        source["authorization_status"]
        for group in lead["source_groups"]
        for source in group["sources"]
    ]
    pit = [
        source["pit_status"]
        for group in lead["source_groups"]
        for source in group["sources"]
    ]
    if "fail" in authorization:
        authorization_summary = "fail"
    elif all(status == "pass" for status in authorization):
        authorization_summary = "pass"
    else:
        authorization_summary = "partial"
    if all(status == "canonical_pit" for status in pit):
        pit_summary = "canonical_pit"
    elif pit and all(status in {"canonical_pit", "research_pit"} for status in pit):
        pit_summary = "research_pit"
    else:
        pit_summary = "not_gate_ready"
    return authorization_summary, pit_summary


def _candidate_projection(
    lead: Mapping[str, Any],
    *,
    entry_id: str,
    generated_at: str,
    generator_id: str,
    generator_version: str,
) -> dict[str, Any]:
    raw = {
        "schema_version": SCHEMA_VERSION,
        "candidate_kind": lead["candidate_kind"],
        "candidate_id": "pending",
        "search_queue": lead["search_queue"],
        "title": lead["title"],
        "created_at": generated_at,
        "created_by": f"{generator_id}:{generator_version}",
        "hypothesis": lead["hypothesis"],
        "fingerprint": lead["fingerprint"],
        "surface_ids": lead["registered_surface_ids"],
        "expectation_gap": lead["expectation_gap"],
        "why_not_arbitraged": lead["why_not_arbitraged"],
        "falsifier": lead["falsifier"],
        "baseline": lead["baseline"],
        "treatment": lead["treatment"],
        "replacement_value_comparator": lead["replacement_value_comparator"],
        "expected_horizon": lead["expected_horizon"],
        "execution_envelope": lead["execution_envelope"],
        "evidence_grade": "lead",
        "source_readiness_snapshot": [],
        "production_impact": research_only_production_impact(),
        "reopen_condition": lead["reopen_condition"],
        "next_machine_action": lead["source_preflight_next_action"],
        "research_refs": sorted(set([entry_id, *lead["research_refs"]])),
    }
    return HypothesisCandidate.with_computed_id(raw).to_dict()


def _render_markdown(section: Mapping[str, Any]) -> str:
    lead = section["lead"]
    expectation = lead["market_expectation"]
    lines = [
        f"### {_markdown_inline(lead['title'])}",
        "",
        f"generator_id: {section['generator_provenance']['generator_id']}",
        f"generator_version: {section['generator_provenance']['generator_version']}",
        f"mechanism_id: {section['mechanism_lead_id']}",
        "evidence_grade: lead",
        f"market_prior_status: {expectation['status']}",
        f"source_authorization: {section['source_authorization_status']}",
        f"scan_run_id: {section['generator_provenance']['run_id']}",
        f"scan_completed_at: {section['generator_provenance']['scan_completed_at']}",
        f"expectation_proxy: {expectation['proxy_type']}",
        f"pit_feasibility: {section['pit_readiness_status']}",
        f"falsifier: {_markdown_inline(lead['falsifier'])}",
        f"entry_id: {section['entry_id']}",
        "",
        _markdown_inline(lead["hypothesis"]),
        "",
        "Causal chain:",
    ]
    lines.extend(
        f"{index}. {_markdown_inline(item)}"
        for index, item in enumerate(lead["causal_chain"], 1)
    )
    lines.extend(["", "Counterevidence:"])
    lines.extend(
        f"- {_markdown_inline(item['statement'])} — {_markdown_inline(item['implication'])}"
        for item in lead["counterevidence"]
    )
    lines.extend(
        [
            "",
            f"Baseline: {_markdown_inline(lead['baseline']['policy'])}",
            f"Treatment: {_markdown_inline(lead['treatment']['policy'])}",
            "Replacement comparator: "
            f"{_markdown_inline(lead['replacement_value_comparator'])}",
            f"Next action: {_markdown_inline(lead['source_preflight_next_action'])}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_mechanism_lead_batch(
    scan: Mapping[str, Any],
    generator_registry: Mapping[str, Any],
    *,
    known_surface_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Validate ``scan`` and return deterministic lead-only map sections.

    ``known_surface_ids`` must be supplied whenever a lead requests a strict
    candidate projection.  Merely naming IDs in the scan is not accepted as
    proof that an EvidenceSurface exists.
    """

    _reject_outcome_fields(scan)
    _reject_permission_escalation(scan)
    registry, generators = _normalise_registry(generator_registry)
    raw = _mapping(scan, path="$.scan")
    _fields(
        raw,
        required={
            "schema_version",
            "record_type",
            "generator_id",
            "generator_version",
            "skill_sha256",
            "run_id",
            "research_date",
            "timezone",
            "generated_at",
            "data_cutoff",
            "history_checked_at",
            "outcome_blind",
            "history_read_before_generation",
            "history_veto_applied_after_generation",
            "history_policy",
            "experiment_id_reserved",
            "trade_enabled",
            "orders_enabled",
            "ranking_enabled",
            "strategy_changed",
            "leads",
            "history_vetoes",
        },
        path="$.scan",
    )
    if raw["schema_version"] != SCHEMA_VERSION or isinstance(raw["schema_version"], bool):
        _fail("schema_version_mismatch", "$.scan.schema_version", "must equal 1")
    if _text(raw["record_type"], path="$.scan.record_type") != SCAN_RECORD_TYPE:
        _fail("record_type_mismatch", "$.scan.record_type", f"must equal {SCAN_RECORD_TYPE}")
    generator_id = _text(raw["generator_id"], path="$.scan.generator_id", lower=True)
    if generator_id not in generators:
        _fail("unregistered_generator", "$.scan.generator_id", generator_id)
    generator = generators[generator_id]
    if generator["status"] != "active":
        _fail("generator_disabled", "$.scan.generator_id", generator_id)
    generator_version = _text(raw["generator_version"], path="$.scan.generator_version")
    if generator_version != generator["generator_version"]:
        _fail(
            "generator_version_mismatch",
            "$.scan.generator_version",
            f"expected {generator['generator_version']}",
        )
    skill_sha256 = _sha256(raw["skill_sha256"], path="$.scan.skill_sha256")
    if skill_sha256 != generator["skill_sha256"]:
        _fail(
            "skill_hash_mismatch",
            "$.scan.skill_sha256",
            f"expected {generator['skill_sha256']}",
        )
    run_id = _text(raw["run_id"], path="$.scan.run_id", lower=True)
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", run_id) is None:
        _fail("invalid_run_id", "$.scan.run_id", "must use lowercase marker-safe slug characters")
    research_date_text = _text(raw["research_date"], path="$.scan.research_date")
    try:
        research_day = date.fromisoformat(research_date_text)
    except ValueError as exc:
        raise MechanismScanError(
            "invalid_research_date", "$.scan.research_date", "must be YYYY-MM-DD"
        ) from exc
    if research_date_text != research_day.isoformat():
        _fail("invalid_research_date", "$.scan.research_date", "must be canonical YYYY-MM-DD")
    timezone_name = _text(raw["timezone"], path="$.scan.timezone")
    if timezone_name != generator["research_timezone"]:
        _fail(
            "research_timezone_mismatch",
            "$.scan.timezone",
            f"expected {generator['research_timezone']}",
        )
    try:
        research_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise MechanismScanError(
            "invalid_research_timezone", "$.scan.timezone", "must be an installed IANA timezone"
        ) from exc
    generated_at, generated_clock = _timestamp(raw["generated_at"], path="$.scan.generated_at")
    data_cutoff, cutoff_clock = _timestamp(raw["data_cutoff"], path="$.scan.data_cutoff")
    history_checked_at, history_clock = _timestamp(
        raw["history_checked_at"], path="$.scan.history_checked_at"
    )
    if cutoff_clock > generated_clock:
        _fail("scan_clock_order", "$.scan", "data_cutoff must not exceed generated_at")
    if history_clock < generated_clock:
        _fail(
            "history_before_generation",
            "$.scan.history_checked_at",
            "history must be checked only after generation is frozen",
        )
    if generated_clock.astimezone(research_timezone).date() != research_day:
        _fail(
            "research_date_mismatch",
            "$.scan.generated_at",
            "generated_at local date must equal research_date",
        )
    if history_clock.astimezone(research_timezone).date() != research_day:
        _fail(
            "research_date_mismatch",
            "$.scan.history_checked_at",
            "completed local date must equal research_date",
        )
    allowed_cutoff_dates = {research_day, research_day - timedelta(days=1)}
    if cutoff_clock.astimezone(research_timezone).date() not in allowed_cutoff_dates:
        _fail(
            "research_date_mismatch",
            "$.scan.data_cutoff",
            "data_cutoff local date must be research_date or the immediately preceding date",
        )
    _true(raw["outcome_blind"], path="$.scan.outcome_blind")
    _false(
        raw["history_read_before_generation"],
        path="$.scan.history_read_before_generation",
    )
    _true(
        raw["history_veto_applied_after_generation"],
        path="$.scan.history_veto_applied_after_generation",
    )
    if _text(raw["history_policy"], path="$.scan.history_policy", lower=True) != HISTORY_POLICY:
        _fail("invalid_history_policy", "$.scan.history_policy", f"must equal {HISTORY_POLICY}")
    for field in (
        "experiment_id_reserved",
        "trade_enabled",
        "orders_enabled",
        "ranking_enabled",
        "strategy_changed",
    ):
        _false(raw[field], path=f"$.scan.{field}")
    raw_leads = _sequence(raw["leads"], path="$.scan.leads")
    if len(raw_leads) > int(generator["max_leads"]):
        _fail(
            "too_many_mechanism_leads",
            "$.scan.leads",
            f"generator allows at most {generator['max_leads']}",
        )
    leads: list[dict[str, Any]] = []
    lead_keys: set[str] = set()
    for index, item in enumerate(raw_leads):
        lead = _normalise_lead(
            item,
            path=f"$.scan.leads[{index}]",
            generator=generator,
            data_cutoff=cutoff_clock,
        )
        if lead["lead_key"] in lead_keys:
            _fail("duplicate_mechanism_lead", f"$.scan.leads[{index}].lead_key", lead["lead_key"])
        lead_keys.add(lead["lead_key"])
        leads.append(lead)
    history_vetoes = _normalise_history_vetoes(
        raw["history_vetoes"], lead_keys=lead_keys, path="$.scan.history_vetoes"
    )
    known = None if known_surface_ids is None else {str(item) for item in known_surface_ids}
    sections: list[dict[str, Any]] = []
    for lead in leads:
        semantic = dict(lead)
        semantic.pop("lead_key", None)
        semantic.pop("registered_surface_ids", None)
        semantic.pop("research_refs", None)
        mechanism_lead_id = f"mech-{canonical_hash(semantic)[:20]}"
        date_token = research_date_text.replace("-", "")
        entry_id = f"res-{date_token}-{generator_id.replace('_', '-')}-{mechanism_lead_id[5:17]}"
        requested_surfaces = set(lead["registered_surface_ids"])
        if requested_surfaces:
            if known is None:
                _fail(
                    "surface_registry_required",
                    f"$.scan.leads.{lead['lead_key']}.registered_surface_ids",
                    "candidate projection requires a verified surface registry",
                )
            unknown = sorted(requested_surfaces - known)
            if unknown:
                _fail(
                    "unknown_registered_surface",
                    f"$.scan.leads.{lead['lead_key']}.registered_surface_ids",
                    str(unknown),
                )
        authorization_status, pit_status = _source_contract_summary(lead)
        veto = history_vetoes[lead["lead_key"]]
        source_preflight_only = (
            lead["market_expectation"]["status"] == "unidentified"
            or authorization_status != "pass"
            or pit_status not in {"canonical_pit", "research_pit"}
            or not requested_surfaces
            or veto["effect"] != "no_conflict"
        )
        disposition = "source_preflight_only" if source_preflight_only else "lead_only_pending_d0_d3"
        projection = None
        if requested_surfaces and not source_preflight_only:
            projection = _candidate_projection(
                lead,
                entry_id=entry_id,
                generated_at=generated_at,
                generator_id=generator_id,
                generator_version=generator_version,
            )
        section = {
            "schema_version": SCHEMA_VERSION,
            "record_type": LEAD_RECORD_TYPE,
            "entry_id": entry_id,
            "mechanism_lead_id": mechanism_lead_id,
            "generator_provenance": {
                "generator_id": generator_id,
                "generator_version": generator_version,
                "skill": generator["skill"],
                "skill_sha256": generator["skill_sha256"],
                "run_id": run_id,
                "scan_completed_at": history_checked_at,
                "research_date": research_date_text,
                "timezone": timezone_name,
            },
            "candidate_kind": lead["candidate_kind"],
            "evidence_grade": "lead",
            "disposition": disposition,
            "source_authorization_status": authorization_status,
            "pit_readiness_status": pit_status,
            "history_veto": veto,
            "lead": lead,
            "candidate_projection": projection,
            "candidate_projection_caveat": (
                "A projection is only a lead snapshot. D0 must rebind every source claim "
                "to the immutable metadata of the referenced EvidenceSurface registry."
            ),
            "eligible_for_panel": False,
            "experiment_id_reserved": False,
            "trade_enabled": False,
            "orders_enabled": False,
            "ranking_enabled": False,
            "strategy_changed": False,
            "gate_candidate": False,
        }
        section["research_map_markdown"] = _render_markdown(section)
        sections.append(section)
    sections.sort(key=lambda item: item["mechanism_lead_id"])
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": OUTPUT_RECORD_TYPE,
        "generator_provenance": {
            "registry_version": registry["registry_version"],
            "registry_hash": canonical_hash(registry),
            "generator_id": generator_id,
            "generator_version": generator_version,
            "skill": generator["skill"],
            "skill_sha256": generator["skill_sha256"],
            "run_id": run_id,
            "research_date": research_date_text,
            "timezone": timezone_name,
            "generated_at": generated_at,
            "data_cutoff": data_cutoff,
            "history_checked_at": history_checked_at,
        },
        "history_policy": HISTORY_POLICY,
        "history_read_before_generation": False,
        "history_veto_applied_after_generation": True,
        "outcome_blind": True,
        "lead_count": len(sections),
        "research_map_sections": sections,
        "experiment_id_reserved": False,
        "trade_enabled": False,
        "orders_enabled": False,
        "ranking_enabled": False,
        "strategy_changed": False,
        "panel_built": False,
        "candidate_projection_policy": (
            "Emit only when source authorization, PIT, observable prior, post-generation "
            "history veto and explicitly verified surface IDs all pass; D0 still rechecks "
            "immutable registry metadata."
        ),
    }
    scan_manifest = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "external_mechanism_scan_manifest",
        "status": "no_new_lead" if not sections else "leads_generated",
        "generator_id": generator_id,
        "generator_version": generator_version,
        "skill_sha256": generator["skill_sha256"],
        "run_id": run_id,
        "research_date": research_date_text,
        "timezone": timezone_name,
        "data_cutoff": data_cutoff,
        "completed_at": history_checked_at,
        "lead_count": len(sections),
        "outcome_blind": True,
        "history_read_before_generation": False,
        "history_veto_applied_after_generation": True,
        "experiment_id_reserved": False,
        "trade_enabled": False,
        "orders_enabled": False,
        "ranking_enabled": False,
        "strategy_changed": False,
        "panel_built": False,
    }
    scan_manifest["manifest_hash"] = canonical_hash(scan_manifest)
    result["scan_manifest"] = scan_manifest
    result["batch_hash"] = canonical_hash(result)
    return result


__all__ = [
    "HISTORY_POLICY",
    "LEAD_RECORD_TYPE",
    "MechanismScanError",
    "OUTPUT_RECORD_TYPE",
    "SCAN_RECORD_TYPE",
    "build_mechanism_lead_batch",
]
