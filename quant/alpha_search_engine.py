"""Outcome-blind alpha discovery preflight, selection, and failure feedback.

This module sits *before* Ginger's experiment protocol.  It is deliberately
unable to reserve an experiment, run a backtest, or alter a trading policy.
Candidates are checked only against their frozen research contract and source
metadata; candidate-specific realised outcomes are forbidden at this boundary.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time as datetime_time, timezone
from typing import Any, Iterable, Mapping, Sequence

try:
    from .alpha_search_contract import (
        canonical_hash as _contract_canonical_hash,
        canonical_json as _contract_canonical_json,
        normalize_hypothesis_candidate,
        normalize_preflight_decision,
        normalize_selection_scope_manifest,
        normalize_selection_panel,
        research_only_production_impact,
        validate_candidate_semantic_id,
    )
except ImportError:  # pragma: no cover - direct quant/ test import fallback.
    from alpha_search_contract import (  # type: ignore
        canonical_hash as _contract_canonical_hash,
        canonical_json as _contract_canonical_json,
        normalize_hypothesis_candidate,
        normalize_preflight_decision,
        normalize_selection_scope_manifest,
        normalize_selection_panel,
        research_only_production_impact,
        validate_candidate_semantic_id,
    )


SCHEMA_VERSION = 1
PREFLIGHT_VERSION = "alpha_search_preflight_v1"
SELECTOR_VERSION = "alpha_search_diversity_selector_v1"
SCORE_VERSION = "alpha_search_outcome_blind_score_v1"
SCOPE_MANIFEST_VERSION = "alpha_search_scope_manifest_v1"

SEARCH_QUEUES = ("exploration", "adjacent", "exploitation")
QUEUE_ALIASES = {
    "explore": "exploration",
    "exploration": "exploration",
    "adjacent": "adjacent",
    "exploit": "exploitation",
    "exploitation": "exploitation",
}
EVIDENCE_GRADES = ("lead", "observer", "observed_only", "gate_candidate")
_GRADE_RANK = {grade: index for index, grade in enumerate(EVIDENCE_GRADES)}

# Closed statistical keys.  Human detail may be attached separately, but it
# must never become the aggregation identity.
FAILURE_REASONS = (
    "no_gross_edge",
    "already_priced",
    "wrong_transmission_mapping",
    "no_candidate_overlap",
    "market_expectation_unidentified",
    "pit_or_source_failure",
    "cost_and_carry",
    "borrow_or_capacity",
    "core_opportunity_cost",
    "concentration",
    "tail_risk",
    "insufficient_independent_rows",
    "duplicate_or_frozen",
    "incomplete_selection_panel",
    "outcome_contamination",
    "unclassified",
)

FAILURE_SEARCH_POLICY = {
    "no_gross_edge": "downweight_source_x_mechanism",
    "already_priced": "require_earlier_clock_or_new_expectation_proxy",
    "wrong_transmission_mapping": "preserve_surface_require_independent_mapping_evidence",
    "no_candidate_overlap": "park_until_quantified_overlap_reopen",
    "market_expectation_unidentified": "downgrade_to_plain_event_lead",
    "pit_or_source_failure": "measurement_repair_or_park_before_price_read",
    "cost_and_carry": "freeze_current_execution_envelope",
    "borrow_or_capacity": "separate_signal_from_instrument_mapping",
    "core_opportunity_cost": "route_to_portfolio_increment_lane",
    "concentration": "wait_for_independent_breadth",
    "tail_risk": "require_new_payoff_or_risk_gate_shape",
    "insufficient_independent_rows": "observe_until_reopen_count",
    "duplicate_or_frozen": "obey_novelty_and_reopen_guards",
    "incomplete_selection_panel": "invalidate_selection_scope",
    "outcome_contamination": "invalidate_and_refreeze_new_scope",
    "unclassified": "manual_taxonomy_review",
}

# Exact semantic result fields, not vague words such as ``expected_payoff``.
# The recursive audit also catches prefixed/suffixed variants after normalising
# punctuation.  Metadata such as ``outcome_blind`` and surface readiness named
# ``outcome_ledger`` remain legal.
_FORBIDDEN_OUTCOME_KEYS = {
    "actual_return",
    "alpha_result",
    "backtest_result",
    "best_horizon",
    "candidate_return",
    "expected_value_score",
    "forward_return",
    "gate_metric",
    "gate_result",
    "label_positive_cash",
    "label_positive_qqq",
    "label_positive_spy",
    "max_drawdown",
    "outcome_label",
    "profit_and_loss",
    "realized_outcome",
    "realized_pnl",
    "realized_return",
    "realised_outcome",
    "realised_pnl",
    "realised_return",
    "settlement_return",
    "sharpe",
    "sharpe_daily",
    "sortino",
    "strategy_total_return_pct",
    "total_pnl",
    "total_return",
    "trade_result",
    "winning_horizon",
}
_FORBIDDEN_KEY_PARTS = (
    "forward_return",
    "realized_return",
    "realised_return",
    "realized_pnl",
    "realised_pnl",
    "backtest_result",
    "gate_result",
    "outcome_label",
)
_FORBIDDEN_KEY_SUFFIXES = (
    "_return",
    "_returns",
    "_pnl",
    "_sharpe",
    "_sortino",
    "_drawdown",
    "_win_rate",
)


class AlphaSearchError(ValueError):
    """Fail-closed discovery contract error with a stable reason code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_clock(value: Any, *, path: str, date_at_end: bool = True) -> datetime:
    """Parse an ISO clock into UTC; naive datetimes fail closed."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(
            value,
            datetime_time.max if date_at_end else datetime_time.min,
            tzinfo=timezone.utc,
        )
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            parsed_date = None
        if parsed_date is not None and parsed_date.isoformat() == text:
            parsed = datetime.combine(
                parsed_date,
                datetime_time.max if date_at_end else datetime_time.min,
                tzinfo=timezone.utc,
            )
        else:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError as exc:
                raise AlphaSearchError("invalid_clock", f"{path}: {value!r}") from exc
    else:
        raise AlphaSearchError("invalid_clock", f"{path}: missing or not ISO-8601")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AlphaSearchError("invalid_clock", f"{path}: timezone is required")
    return parsed.astimezone(timezone.utc)


def _normal_clock(value: Any, *, path: str, date_at_end: bool = True) -> str:
    return _parse_clock(value, path=path, date_at_end=date_at_end).isoformat().replace(
        "+00:00", "Z"
    )


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Return the one canonical serialisation used by discovery hashes."""
    return _contract_canonical_json(_plain(value))


def stable_hash(value: Any) -> str:
    return _contract_canonical_hash(_plain(value))


def _hash_without_top_level(value: Any, *excluded: str) -> str:
    """Hash an envelope while excluding only explicitly named top-level keys."""
    payload = _plain(value)
    if not isinstance(payload, Mapping):
        return stable_hash(payload)
    clean = dict(payload)
    for key in excluded:
        clean.pop(key, None)
    return stable_hash(clean)


def _semantic_hash(value: Any) -> str:
    """Compatibility helper: exclude only self-referential top-level hashes."""
    return _hash_without_top_level(value, "panel_hash", "preflight_hash")


def validate_selection_scope_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the scope anchor frozen *before* candidate selection."""
    if not isinstance(value, Mapping):
        raise AlphaSearchError("invalid_selection_scope_manifest", "manifest must be an object")
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
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing or unknown:
        raise AlphaSearchError(
            "invalid_selection_scope_manifest",
            f"missing={missing} unknown={unknown}",
        )
    row = dict(_plain(value))
    if row["schema_version"] != SCHEMA_VERSION or row["manifest_version"] != SCOPE_MANIFEST_VERSION:
        raise AlphaSearchError("invalid_selection_scope_manifest", "unsupported schema/manifest version")
    if not str(row["scope_name"] or "").strip() or not str(row["generator_version"] or "").strip():
        raise AlphaSearchError("invalid_selection_scope_manifest", "scope_name and generator_version are required")
    preregistered = _parse_clock(
        row["preregistered_at"], path="manifest.preregistered_at"
    )
    cutoff = _parse_clock(row["data_cutoff"], path="manifest.data_cutoff")
    freeze_at = _parse_clock(row["freeze_at"], path="manifest.freeze_at")
    if preregistered > cutoff or cutoff > freeze_at:
        raise AlphaSearchError(
            "invalid_selection_scope_manifest",
            "require preregistered_at <= data_cutoff <= freeze_at",
        )
    row["preregistered_at"] = preregistered.isoformat().replace("+00:00", "Z")
    row["data_cutoff"] = cutoff.isoformat().replace("+00:00", "Z")
    row["freeze_at"] = freeze_at.isoformat().replace("+00:00", "Z")
    if row["selector_version"] != SELECTOR_VERSION or row["score_version"] != SCORE_VERSION:
        raise AlphaSearchError("invalid_selection_scope_manifest", "selector/score version mismatch")
    if not isinstance(row["candidate_generation_config"], Mapping) or not row["candidate_generation_config"]:
        raise AlphaSearchError("invalid_selection_scope_manifest", "candidate_generation_config is required")
    assert_outcome_blind(row["candidate_generation_config"])
    surface_ids = row["allowed_surface_ids"]
    if not isinstance(surface_ids, list) or not surface_ids or any(not str(item).strip() for item in surface_ids):
        raise AlphaSearchError("invalid_selection_scope_manifest", "allowed_surface_ids must be non-empty")
    if surface_ids != sorted(set(str(item) for item in surface_ids)):
        raise AlphaSearchError("invalid_selection_scope_manifest", "allowed_surface_ids must be sorted and unique")
    if not re.fullmatch(r"[0-9a-f]{64}", str(row["surface_registry_hash"] or "")):
        raise AlphaSearchError("invalid_selection_scope_manifest", "surface_registry_hash must be SHA-256")
    if not re.fullmatch(
        r"[0-9a-f]{64}", str(row["prior_fingerprint_snapshot_hash"] or "")
    ):
        raise AlphaSearchError(
            "invalid_selection_scope_manifest",
            "prior_fingerprint_snapshot_hash must be SHA-256",
        )
    prior_count = row["prior_fingerprint_count"]
    if not isinstance(prior_count, int) or isinstance(prior_count, bool) or prior_count < 0:
        raise AlphaSearchError(
            "invalid_selection_scope_manifest",
            "prior_fingerprint_count must be a non-negative integer",
        )
    budgets = row["queue_budgets"]
    if not isinstance(budgets, Mapping) or set(budgets) != set(SEARCH_QUEUES):
        raise AlphaSearchError("invalid_selection_scope_manifest", "all three queue budgets are required")
    normal_budgets: dict[str, int] = {}
    for queue in SEARCH_QUEUES:
        count = budgets[queue]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise AlphaSearchError("invalid_selection_scope_manifest", f"invalid budget for {queue}")
        normal_budgets[queue] = count
    row["queue_budgets"] = normal_budgets
    expected = row["expected_candidate_count"]
    if not isinstance(expected, int) or isinstance(expected, bool) or expected <= 0:
        raise AlphaSearchError("invalid_selection_scope_manifest", "expected_candidate_count must be positive")
    if expected != sum(normal_budgets.values()):
        raise AlphaSearchError("invalid_selection_scope_manifest", "expected count must equal queue budgets")
    limit = row["selection_limit"]
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise AlphaSearchError("invalid_selection_scope_manifest", "selection_limit must be positive")
    batch_id = row["batch_policy_bundle_id"]
    if limit != 1 and not str(batch_id or "").strip():
        raise AlphaSearchError(
            "invalid_selection_scope_manifest",
            "multiple winners require a predeclared batch_policy_bundle_id",
        )
    if limit == 1 and batch_id is not None:
        raise AlphaSearchError("invalid_selection_scope_manifest", "single selection must use null batch policy")
    if row["outcome_blind"] is not True or row["trade_enabled"] is not False:
        raise AlphaSearchError("invalid_selection_scope_manifest", "scope must be outcome-blind and no-trade")
    claimed = str(row["manifest_hash"] or "")
    recomputed = _hash_without_top_level(row, "manifest_hash")
    if claimed != recomputed:
        raise AlphaSearchError("selection_scope_manifest_hash_mismatch", f"expected {recomputed}")
    try:
        return normalize_selection_scope_manifest(row)
    except Exception as exc:
        raise AlphaSearchError(
            getattr(exc, "code", "invalid_selection_scope_manifest"),
            str(exc),
        ) from exc


def build_selection_scope_manifest(
    *,
    scope_name: str,
    preregistered_at: str,
    data_cutoff: str,
    freeze_at: str,
    generator_version: str,
    candidate_generation_config: Mapping[str, Any],
    allowed_surface_ids: Sequence[str],
    surface_registry_hash: str,
    prior_fingerprints: Iterable[str | Mapping[str, Any]],
    queue_budgets: Mapping[str, int],
    expected_candidate_count: int,
    selection_limit: int = 1,
    batch_policy_bundle_id: str | None = None,
) -> dict[str, Any]:
    prior_hashes = _normalise_prior_fingerprint_hashes(prior_fingerprints)
    row = {
        "schema_version": SCHEMA_VERSION,
        "manifest_version": SCOPE_MANIFEST_VERSION,
        "scope_name": scope_name,
        "preregistered_at": _normal_clock(
            preregistered_at, path="manifest.preregistered_at"
        ),
        "data_cutoff": _normal_clock(data_cutoff, path="manifest.data_cutoff"),
        "freeze_at": _normal_clock(freeze_at, path="manifest.freeze_at"),
        "generator_version": generator_version,
        "candidate_generation_config": dict(_plain(candidate_generation_config)),
        "allowed_surface_ids": sorted(set(str(item) for item in allowed_surface_ids)),
        "surface_registry_hash": surface_registry_hash,
        "prior_fingerprint_snapshot_hash": _prior_fingerprint_snapshot_hash(prior_hashes),
        "prior_fingerprint_count": len(prior_hashes),
        "selector_version": SELECTOR_VERSION,
        "score_version": SCORE_VERSION,
        "queue_budgets": {queue: int(queue_budgets.get(queue, 0)) for queue in SEARCH_QUEUES},
        "expected_candidate_count": expected_candidate_count,
        "selection_limit": selection_limit,
        "batch_policy_bundle_id": batch_policy_bundle_id,
        "outcome_blind": True,
        "trade_enabled": False,
    }
    row["manifest_hash"] = _hash_without_top_level(row, "manifest_hash")
    return validate_selection_scope_manifest(row)


def _normal_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def outcome_field_paths(value: Any, *, _path: str = "candidate") -> list[str]:
    """List candidate-specific result fields recursively, without reading values."""
    hits: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = _normal_key(raw_key)
            path = f"{_path}.{raw_key}"
            if (
                key in _FORBIDDEN_OUTCOME_KEYS
                or any(part in key for part in _FORBIDDEN_KEY_PARTS)
                or key.endswith(_FORBIDDEN_KEY_SUFFIXES)
            ):
                hits.append(path)
            hits.extend(outcome_field_paths(item, _path=path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            hits.extend(outcome_field_paths(item, _path=f"{_path}[{index}]"))
    return hits


def assert_outcome_blind(value: Any) -> None:
    hits = outcome_field_paths(_plain(value))
    if hits:
        raise AlphaSearchError("outcome_contamination", ", ".join(sorted(hits)))


def _candidate_id(candidate: Mapping[str, Any]) -> str:
    value = candidate.get("candidate_id") or candidate.get("id")
    return str(value or "").strip()


def _normalise_candidate(candidate: Any, *, require_semantic_id: bool) -> dict[str, Any]:
    """Route every persisted/frozen candidate through the canonical contract."""
    try:
        normalised = normalize_hypothesis_candidate(_plain(candidate))
        if require_semantic_id:
            validate_candidate_semantic_id(normalised)
        return dict(normalised)
    except Exception as exc:
        raise AlphaSearchError(
            getattr(exc, "code", "invalid_candidate"),
            str(exc),
        ) from exc


def _bind_candidate_readiness(candidate: Any, surfaces: Any) -> dict[str, Any]:
    """Bind a candidate snapshot to the exact registered surface rows."""
    row = dict(_plain(candidate))
    by_id, _, _ = _surface_indexes(surfaces)
    surface_ids = [str(item) for item in row.get("surface_ids") or []]
    missing = sorted(set(surface_ids) - set(by_id))
    if missing:
        raise AlphaSearchError(
            "pit_or_source_failure",
            f"candidate {_candidate_id(row)} references unknown surfaces: {missing}",
        )
    expected = [
        {"surface_id": surface_id, "snapshot_hash": _semantic_hash(by_id[surface_id])}
        for surface_id in sorted(set(surface_ids))
    ]
    supplied = row.get("source_readiness_snapshot")
    if supplied not in (None, [], ()):
        supplied_plain = sorted(
            [dict(_plain(item)) for item in supplied],
            key=lambda item: str(item.get("surface_id") or ""),
        )
        if supplied_plain != expected:
            raise AlphaSearchError(
                "source_readiness_snapshot_mismatch",
                f"candidate {_candidate_id(row)} does not match the frozen registry",
            )
    row["source_readiness_snapshot"] = expected
    return _normalise_candidate(row, require_semantic_id=True)


def _queue(candidate: Mapping[str, Any]) -> str:
    raw = candidate.get("search_queue", candidate.get("queue", ""))
    return QUEUE_ALIASES.get(str(raw).strip().lower(), str(raw).strip().lower())


def _fingerprint(candidate: Mapping[str, Any]) -> dict[str, Any]:
    raw = candidate.get("fingerprint")
    if isinstance(raw, Mapping):
        return dict(raw)
    # Compatibility with the smaller v1 candidate contract.
    gap = candidate.get("expectation_gap")
    prior = gap.get("market_prior") if isinstance(gap, Mapping) else {}
    execution = candidate.get("execution") if isinstance(candidate.get("execution"), Mapping) else {}
    transmission = gap.get("transmission") if isinstance(gap, Mapping) else {}
    return {
        "data_source": candidate.get("data_source"),
        "component_sources": candidate.get("component_sources") or [],
        "expectation_proxy": candidate.get("expectation_proxy")
        or (prior.get("proxy_type") if isinstance(prior, Mapping) else None),
        "economic_mechanism": candidate.get("economic_mechanism")
        or candidate.get("mechanism_family"),
        "decision_surface": candidate.get("decision_surface"),
        "payoff_shape": candidate.get("payoff_shape")
        or (transmission.get("payoff_shape") if isinstance(transmission, Mapping) else None),
        "horizon": candidate.get("expected_horizon") or candidate.get("horizon"),
        "execution_dependency": candidate.get("execution_dependency")
        or (execution.get("execution_dependency") if isinstance(execution, Mapping) else None),
        "portfolio_role": candidate.get("portfolio_role"),
    }


def _market_prior(candidate: Mapping[str, Any]) -> dict[str, Any]:
    prior = candidate.get("market_prior")
    if isinstance(prior, Mapping):
        return dict(prior)
    gap = candidate.get("expectation_gap")
    if isinstance(gap, Mapping) and isinstance(gap.get("market_prior"), Mapping):
        return dict(gap["market_prior"])
    return {}


def _independent_evidence(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = candidate.get("independent_evidence")
    if raw is None and isinstance(candidate.get("expectation_gap"), Mapping):
        raw = candidate["expectation_gap"].get("independent_evidence")
    return [dict(row) for row in (raw or []) if isinstance(row, Mapping)]


def _posterior(candidate: Mapping[str, Any]) -> dict[str, Any]:
    raw = candidate.get("our_posterior")
    if isinstance(raw, Mapping):
        return dict(raw)
    gap = candidate.get("expectation_gap")
    if isinstance(gap, Mapping) and isinstance(gap.get("our_posterior"), Mapping):
        return dict(gap["our_posterior"])
    return {}


def _surface_rows(surfaces: Any) -> list[dict[str, Any]]:
    if hasattr(surfaces, "all") and callable(surfaces.all):
        surfaces = surfaces.all()
    elif hasattr(surfaces, "surfaces"):
        surfaces = surfaces.surfaces
    if isinstance(surfaces, Mapping):
        if isinstance(surfaces.get("surfaces"), list):
            raw_rows = surfaces["surfaces"]
        else:
            raw_rows = []
            for key, value in surfaces.items():
                if isinstance(value, Mapping):
                    raw_rows.append({"surface_id": key, **dict(value)})
    else:
        raw_rows = surfaces or []
    return [dict(_plain(row)) for row in raw_rows if isinstance(_plain(row), Mapping)]


def _surface_indexes(
    surfaces: Any,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]:
    by_id: dict[str, dict[str, Any]] = {}
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_primary: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _surface_rows(surfaces):
        surface_id = str(row.get("surface_id") or "").strip()
        source = str(row.get("data_source") or row.get("source_key") or "").strip()
        if surface_id:
            by_id[surface_id] = row
        if source:
            by_source[source].append(row)
            by_primary[source].append(row)
        for component in row.get("component_sources") or []:
            by_source[str(component)].append(row)
    return by_id, by_source, by_primary


def _surface_registry_hash(surfaces: Any) -> str:
    claimed = getattr(surfaces, "canonical_hash", None)
    if isinstance(claimed, str) and re.fullmatch(r"[0-9a-f]{64}", claimed):
        return claimed
    rows = sorted(_surface_rows(surfaces), key=lambda row: str(row.get("surface_id") or ""))
    return stable_hash({"schema_version": SCHEMA_VERSION, "surfaces": rows})


def _surface_readiness(surface: Mapping[str, Any]) -> dict[str, Any]:
    raw = surface.get("readiness")
    if isinstance(raw, Mapping):
        return dict(raw)
    # A row that has already passed the strict EvidenceSurface contract has a
    # valid source contract; gate readiness remains the explicit top-level flag.
    if surface.get("surface_id") and surface.get("pit_status"):
        return {
            "source_contract": surface.get("source_contract_status") or "pass",
            "gate_ready": surface.get("gate_ready") is True,
        }
    return {}


def _surface_grade(surface: Mapping[str, Any]) -> str:
    grade = str(surface.get("evidence_grade") or "").strip()
    if grade in _GRADE_RANK:
        return grade
    readiness = _surface_readiness(surface)
    if readiness.get("gate_ready") is True:
        return "gate_candidate"
    pit = surface.get("pit_status")
    if pit is None and isinstance(surface.get("pit_contract"), Mapping):
        pit = surface["pit_contract"].get("status")
    pit = str(pit or "").lower()
    settled = int(
        surface.get("settled_count")
        or (surface.get("coverage") or {}).get("settled_independent_decisions")
        or 0
    )
    if pit in {"canonical", "canonical_pit", "pass"} and settled > 0:
        return "observed_only"
    if pit in {"pit_forward_unsettled", "forward", "partial"}:
        return "observer"
    return "lead"


def _declared_grade(candidate: Mapping[str, Any]) -> str:
    grade = str(candidate.get("evidence_grade") or "lead").strip()
    return grade if grade in _GRADE_RANK else "lead"


def _gate(status: str, reasons: Iterable[str]) -> dict[str, Any]:
    unique = sorted({str(reason) for reason in reasons if reason})
    return {"status": status, "reasons": unique}


def _status(reject: Sequence[str], park: Sequence[str]) -> str:
    if reject:
        return "reject"
    if park:
        return "park"
    return "pass"


def _fingerprint_key(candidate: Mapping[str, Any]) -> str:
    fp = _fingerprint(candidate)
    semantic = {
        key: fp.get(key)
        for key in (
            "data_source",
            "component_sources",
            "expectation_proxy",
            "economic_mechanism",
            "decision_surface",
            "payoff_shape",
            "horizon",
            "execution_dependency",
            "portfolio_role",
        )
    }
    return stable_hash(semantic)


def _normalise_prior_fingerprint_hashes(
    prior_fingerprints: Iterable[str | Mapping[str, Any]],
) -> tuple[str, ...]:
    hashes: set[str] = set()
    for index, prior in enumerate(prior_fingerprints):
        if isinstance(prior, Mapping):
            fingerprint = prior.get("fingerprint", prior)
            if not isinstance(fingerprint, Mapping):
                raise AlphaSearchError(
                    "invalid_prior_fingerprints", f"row {index} fingerprint must be an object"
                )
            digest = _fingerprint_key({"fingerprint": fingerprint})
        else:
            digest = str(prior or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise AlphaSearchError(
                    "invalid_prior_fingerprints",
                    f"row {index} must be a SHA-256 fingerprint hash or mapping",
                )
        hashes.add(digest)
    return tuple(sorted(hashes))


def _prior_fingerprint_snapshot_hash(fingerprint_hashes: Sequence[str]) -> str:
    return stable_hash(list(fingerprint_hashes))


def _verify_prior_fingerprint_anchor(
    manifest: Mapping[str, Any],
    prior_fingerprints: Iterable[str | Mapping[str, Any]],
) -> tuple[str, ...]:
    hashes = _normalise_prior_fingerprint_hashes(prior_fingerprints)
    actual_hash = _prior_fingerprint_snapshot_hash(hashes)
    if len(hashes) != manifest.get("prior_fingerprint_count"):
        raise AlphaSearchError(
            "prior_fingerprint_snapshot_mismatch",
            f"manifest count={manifest.get('prior_fingerprint_count')} actual={len(hashes)}",
        )
    if actual_hash != manifest.get("prior_fingerprint_snapshot_hash"):
        raise AlphaSearchError(
            "prior_fingerprint_snapshot_mismatch",
            f"manifest={manifest.get('prior_fingerprint_snapshot_hash')} actual={actual_hash}",
        )
    return hashes


def evaluate_preflight(
    candidate: Any,
    surfaces: Any,
    *,
    prior_fingerprints: Iterable[str | Mapping[str, Any]] = (),
    data_cutoff: str,
    evaluated_at: str | None = None,
    selection_scope_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate deterministic D0-D3 gates without candidate outcome access."""
    row = dict(_plain(candidate))
    candidate_id = _candidate_id(row)
    contamination = outcome_field_paths(row)
    cutoff_dt = _parse_clock(data_cutoff, path="data_cutoff")
    cutoff_text = cutoff_dt.isoformat().replace("+00:00", "Z")
    evaluated_dt = _parse_clock(
        evaluated_at or cutoff_text,
        path="evaluated_at",
    )
    if evaluated_dt < cutoff_dt:
        raise AlphaSearchError(
            "invalid_clock",
            "evaluated_at must be at or after data_cutoff",
        )
    evaluated_text = evaluated_dt.isoformat().replace("+00:00", "Z")
    by_id, by_source, by_primary = _surface_indexes(surfaces)

    d0_reject: list[str] = []
    d0_park: list[str] = []
    d1_reject: list[str] = []
    d1_park: list[str] = []
    d2_reject: list[str] = []
    d2_park: list[str] = []
    d3_reject: list[str] = []
    d3_park: list[str] = []
    failures: set[str] = set()
    temporal_clean = True

    if not candidate_id:
        d3_reject.append("missing_candidate_id")
    if contamination:
        d3_reject.extend(f"forbidden_outcome_field:{path}" for path in contamination)
        failures.add("outcome_contamination")

    surface_ids = [str(value) for value in row.get("surface_ids") or row.get("evidence_surface_ids") or []]
    if not surface_ids:
        d0_park.append("no_evidence_surface_declared")
        failures.add("pit_or_source_failure")
    missing_ids = [surface_id for surface_id in surface_ids if surface_id not in by_id]
    if missing_ids:
        d0_reject.extend(f"surface_not_registered:{value}" for value in sorted(missing_ids))
        failures.add("pit_or_source_failure")

    fp = _fingerprint(row)
    component_sources = sorted({str(value) for value in fp.get("component_sources") or [] if value})
    primary_source = str(fp.get("data_source") or "").strip()
    if primary_source:
        component_sources = sorted(set(component_sources + [primary_source]))
    # Every join member must have its own primary registry row.  Appearing only
    # inside another surface's component list is not an independently audited
    # data source.
    missing_sources = [source for source in component_sources if source not in by_primary]
    if missing_sources:
        d0_reject.extend(f"component_source_not_registered:{value}" for value in missing_sources)
        failures.add("pit_or_source_failure")

    declared_id_set = set(surface_ids)
    # A join label is never enough by itself.  Every member must resolve to one
    # unambiguous primary registry row and that row must be explicitly included
    # in the candidate dependency set.  This prevents a candidate from borrowing
    # the readiness of a convenient aggregate or unrelated gate-ready surface.
    for source in component_sources:
        primary_rows = by_primary.get(source, [])
        if len(primary_rows) > 1:
            d0_reject.append(f"component_source_primary_row_ambiguous:{source}")
            failures.add("pit_or_source_failure")
            continue
        if len(primary_rows) == 1:
            primary_surface_id = str(primary_rows[0].get("surface_id") or "").strip()
            if not primary_surface_id or primary_surface_id not in declared_id_set:
                d0_reject.append(
                    f"component_primary_surface_not_declared:{source}:{primary_surface_id or 'missing'}"
                )
                failures.add("pit_or_source_failure")

    referenced = [by_id[surface_id] for surface_id in surface_ids if surface_id in by_id]
    expanded_referenced_sources: set[str] = set()
    for surface in referenced:
        sid = str(surface.get("surface_id") or "unknown")
        expanded_referenced_sources.add(str(surface.get("data_source") or ""))
        expanded_referenced_sources.update(str(value) for value in surface.get("component_sources") or [])
        readiness = _surface_readiness(surface)
        source_status = str(readiness.get("source_contract") or surface.get("status") or "").lower()
        if source_status in {"fail", "failed", "blocked", "unavailable"}:
            d0_reject.append(f"surface_source_contract_failed:{sid}")
            failures.add("pit_or_source_failure")
        elif source_status in {"partial", "unknown", ""}:
            d0_park.append(f"surface_source_contract_not_ready:{sid}")
            failures.add("pit_or_source_failure")
        saturation = surface.get("saturation")
        saturation_status = (
            str(saturation.get("status") or "").lower()
            if isinstance(saturation, Mapping)
            else str(surface.get("saturation_status") or "").lower()
        )
        if saturation_status in {"saturated", "frozen", "parked"}:
            d3_reject.append(f"component_surface_{saturation_status}:{sid}")
            failures.add("duplicate_or_frozen")
        if "candidate_overlap_count" in surface and int(surface.get("candidate_overlap_count") or 0) == 0:
            d0_park.append(f"surface_candidate_overlap_absent:{sid}")
            failures.add("no_candidate_overlap")
        surface_as_of = surface.get("as_of") or readiness.get("as_of")
        if not surface_as_of:
            d0_park.append(f"surface_as_of_missing:{sid}")
            failures.add("pit_or_source_failure")
            temporal_clean = False
        else:
            try:
                if _parse_clock(surface_as_of, path=f"surface[{sid}].as_of") > cutoff_dt:
                    d0_reject.append(f"surface_as_of_after_data_cutoff:{sid}")
                    failures.add("outcome_contamination")
                    temporal_clean = False
            except AlphaSearchError:
                d0_reject.append(f"surface_as_of_invalid:{sid}")
                failures.add("pit_or_source_failure")
                temporal_clean = False

    fp_source_set = set(component_sources)
    expanded_referenced_sources.discard("")
    if referenced and fp_source_set != expanded_referenced_sources:
        d0_reject.append(
            "fingerprint_component_sources_mismatch:"
            f"declared={sorted(fp_source_set)} registry={sorted(expanded_referenced_sources)}"
        )
        failures.add("pit_or_source_failure")

    declared_grade = _declared_grade(row)
    permitted_grade = min(
        (_surface_grade(surface) for surface in referenced),
        key=lambda value: _GRADE_RANK[value],
        default="lead",
    )
    if _GRADE_RANK[declared_grade] > _GRADE_RANK[permitted_grade]:
        d0_park.append(f"evidence_grade_exceeds_surface:{declared_grade}>{permitted_grade}")
        failures.add("insufficient_independent_rows")
    if declared_grade == "gate_candidate":
        not_gate_ready = [
            str(surface.get("surface_id"))
            for surface in referenced
            if _surface_readiness(surface).get("gate_ready") is not True
        ]
        if not_gate_ready:
            d0_park.extend(f"surface_not_gate_ready:{sid}" for sid in not_gate_ready)
            failures.add("pit_or_source_failure")

    prior = _market_prior(row)
    proxy_type = str(prior.get("proxy_type") or fp.get("expectation_proxy") or "").strip()
    prior_source = str(prior.get("surface_id") or prior.get("source") or "").strip()
    prior_as_of = prior.get("as_of") or prior.get("known_at")
    observability = str(prior.get("observability_grade") or "").lower()
    if not observability and prior.get("observable") is True:
        observability = "direct"
    if not proxy_type or not prior_source or not prior_as_of or observability in {"", "missing"}:
        d1_park.append("observable_market_prior_incomplete")
        failures.add("market_expectation_unidentified")
    elif prior_source not in by_id and prior_source not in by_primary:
        d1_reject.append(f"market_prior_source_not_registered:{prior_source}")
        failures.add("market_expectation_unidentified")
    elif prior_as_of:
        try:
            if _parse_clock(prior_as_of, path="market_prior.known_at") > cutoff_dt:
                d1_reject.append("market_prior_known_at_after_data_cutoff")
                failures.add("outcome_contamination")
                temporal_clean = False
        except AlphaSearchError:
            d1_reject.append("market_prior_known_at_invalid")
            failures.add("pit_or_source_failure")
            temporal_clean = False

    def source_surfaces(source: str) -> list[dict[str, Any]]:
        if source in by_id:
            return [by_id[source]]
        return list(by_primary.get(source, []))

    prior_surfaces = source_surfaces(prior_source) if prior_source else []
    prior_declared = [
        surface for surface in prior_surfaces
        if str(surface.get("surface_id") or "") in declared_id_set
    ]
    if prior_source and prior_surfaces and not prior_declared:
        d1_reject.append(f"market_prior_surface_not_declared:{prior_source}")
        failures.add("pit_or_source_failure")
    for surface in prior_declared:
        sid = str(surface.get("surface_id") or "unknown")
        roles = {str(role).lower() for role in surface.get("roles") or []}
        if "market_expectation" not in roles:
            d1_reject.append(f"market_prior_role_mismatch:{sid}")
            failures.add("market_expectation_unidentified")
        surface_proxy = surface.get("expectation_proxy")
        surface_proxy_type = (
            str(surface_proxy.get("type") or "").lower()
            if isinstance(surface_proxy, Mapping)
            else ""
        )
        if surface_proxy_type != proxy_type.lower():
            d1_reject.append(f"market_prior_proxy_mismatch:{sid}")
            failures.add("market_expectation_unidentified")

    evidence = _independent_evidence(row)
    if not evidence:
        d1_park.append("independent_evidence_missing")
    for index, item in enumerate(evidence):
        evidence_source = str(item.get("surface_id") or item.get("source") or "").strip()
        known_at = item.get("known_at") or item.get("as_of")
        if not evidence_source or not known_at:
            d1_park.append(f"independent_evidence_incomplete:{index}")
        elif evidence_source not in by_id and evidence_source not in by_primary:
            d1_reject.append(f"independent_evidence_source_not_registered:{evidence_source}")
            failures.add("pit_or_source_failure")
        elif known_at:
            try:
                if _parse_clock(known_at, path=f"independent_evidence[{index}].known_at") > cutoff_dt:
                    d1_reject.append(f"independent_evidence_after_data_cutoff:{index}")
                    failures.add("outcome_contamination")
                    temporal_clean = False
            except AlphaSearchError:
                d1_reject.append(f"independent_evidence_clock_invalid:{index}")
                failures.add("pit_or_source_failure")
                temporal_clean = False
        evidence_surfaces = source_surfaces(evidence_source) if evidence_source else []
        evidence_declared = [
            surface for surface in evidence_surfaces
            if str(surface.get("surface_id") or "") in declared_id_set
        ]
        if evidence_source and evidence_surfaces and not evidence_declared:
            d1_reject.append(f"independent_evidence_surface_not_declared:{index}")
            failures.add("pit_or_source_failure")
        for surface in evidence_declared:
            sid = str(surface.get("surface_id") or "unknown")
            roles = {str(role).lower() for role in surface.get("roles") or []}
            if "independent_evidence" not in roles:
                d1_reject.append(f"independent_evidence_role_mismatch:{sid}")
                failures.add("pit_or_source_failure")
        prior_members = {
            member
            for surface in prior_declared
            for member in (
                [str(surface.get("data_source") or "")]
                + [str(value) for value in surface.get("component_sources") or []]
            )
            if member
        }
        evidence_members = {
            member
            for surface in evidence_declared
            for member in (
                [str(surface.get("data_source") or "")]
                + [str(value) for value in surface.get("component_sources") or []]
            )
            if member
        }
        if prior_members & evidence_members:
            d1_reject.append(f"prior_evidence_component_overlap:{index}")
            failures.add("market_expectation_unidentified")
        if prior_source and evidence_source == prior_source:
            independence = str(item.get("independence_from_prior") or "").lower()
            if independence not in {"pass", "independent", "yes", "true"}:
                d1_reject.append(f"prior_evidence_circularity:{index}")
                failures.add("market_expectation_unidentified")

    posterior = _posterior(row)
    if posterior.get("value") is not None:
        if not posterior.get("method") or not posterior.get("calibration_reference"):
            d1_park.append("posterior_not_replayable")
    posterior_clock = posterior.get("known_at") or posterior.get("as_of")
    if posterior_clock:
        try:
            if _parse_clock(posterior_clock, path="our_posterior.known_at") > cutoff_dt:
                d1_reject.append("posterior_known_at_after_data_cutoff")
                failures.add("outcome_contamination")
                temporal_clean = False
        except AlphaSearchError:
            d1_reject.append("posterior_known_at_invalid")
            failures.add("pit_or_source_failure")
            temporal_clean = False

    required_text = {
        "hypothesis": row.get("hypothesis"),
        "why_not_arbitraged": row.get("why_not_arbitraged"),
        "falsifier": row.get("falsifier"),
    }
    for field, value in required_text.items():
        if not str(value or "").strip():
            d2_park.append(f"missing_{field}")
    if row.get("baseline") in (None, "", [], {}):
        d2_park.append("missing_baseline")
    if row.get("treatment") in (None, "", [], {}):
        d2_park.append("missing_treatment")
    if not row.get("replacement_value_comparator") and not row.get("replacement_comparison"):
        d2_park.append("missing_replacement_value_comparator")
    if not row.get("expected_horizon") and not row.get("horizon"):
        d2_park.append("missing_expected_horizon")
    transmission = row.get("transmission")
    if not isinstance(transmission, Mapping) or not transmission:
        gap = row.get("expectation_gap")
        transmission = gap.get("transmission") if isinstance(gap, Mapping) else None
    if not isinstance(transmission, Mapping) or not transmission:
        d2_park.append("missing_transmission")
        failures.add("wrong_transmission_mapping")
    elif not transmission.get("affected_tickers"):
        d2_park.append("affected_ticker_mapping_unresolved")
        failures.add("no_candidate_overlap")

    envelope = row.get("execution_envelope") or row.get("execution")
    if not isinstance(envelope, Mapping) or not envelope:
        d2_park.append("missing_execution_envelope")
    else:
        declared_dependencies = [
            envelope.get("liquidity_dependency"),
            envelope.get("costs_and_carry"),
            envelope.get("borrow_dependency"),
            envelope.get("capacity_constraint"),
            envelope.get("timing_constraint"),
            envelope.get("execution_dependency"),
        ]
        if all(value in (None, "", [], {}) for value in declared_dependencies):
            d2_park.append("execution_dependencies_undeclared")

    queue = _queue(row)
    if queue not in SEARCH_QUEUES:
        d3_reject.append(f"invalid_search_queue:{queue or 'missing'}")
    fingerprint_values = [fp.get(key) for key in (
        "data_source", "expectation_proxy", "economic_mechanism", "decision_surface",
        "payoff_shape", "horizon", "execution_dependency", "portfolio_role",
    )]
    if any(value in (None, "", [], {}) for value in fingerprint_values):
        d3_park.append("incomplete_mechanism_fingerprint")

    current_fp = _fingerprint_key(row)
    existing_fps: set[str] = set()
    for prior_fp in prior_fingerprints:
        if isinstance(prior_fp, Mapping):
            if "fingerprint" in prior_fp or "data_source" in prior_fp:
                existing_fps.add(_fingerprint_key({"fingerprint": prior_fp.get("fingerprint", prior_fp)}))
        else:
            existing_fps.add(str(prior_fp))
    if current_fp in existing_fps:
        d3_reject.append("exact_prior_fingerprint")
        failures.add("duplicate_or_frozen")

    gates = {
        "D0": _gate(_status(d0_reject, d0_park), [*d0_reject, *d0_park]),
        "D1": _gate(_status(d1_reject, d1_park), [*d1_reject, *d1_park]),
        "D2": _gate(_status(d2_reject, d2_park), [*d2_reject, *d2_park]),
        "D3": _gate(_status(d3_reject, d3_park), [*d3_reject, *d3_park]),
    }
    statuses = [gate["status"] for gate in gates.values()]
    decision = "reject" if "reject" in statuses else "park" if "park" in statuses else "pass"
    if decision == "park" and not failures:
        failures.add("pit_or_source_failure")

    result = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "preflight_decision",
        "candidate_id": candidate_id,
        "selection_scope_id": selection_scope_id,
        "evaluated_at": evaluated_text,
        "preflight_version": PREFLIGHT_VERSION,
        "data_cutoff": cutoff_text,
        "outcome_blind": not contamination and temporal_clean,
        "outcome_fields_excluded": sorted(_FORBIDDEN_OUTCOME_KEYS),
        "source_snapshot_hashes": {
            sid: _semantic_hash(by_id[sid]) for sid in surface_ids if sid in by_id
        },
        "declared_evidence_grade": declared_grade,
        "maximum_supported_evidence_grade": permitted_grade,
        "fingerprint_hash": current_fp,
        "gates": gates,
        "decision": decision,
        "failure_reasons": sorted(failures),
        "reopen_condition": row.get("reopen_condition") or next(
            (
                surface.get("reopen_condition")
                for surface in referenced
                if surface.get("reopen_condition")
            ),
            None,
        ),
        "trade_enabled": False,
        "production_impact": research_only_production_impact(),
    }
    result["preflight_hash"] = _semantic_hash(result)
    if result["outcome_blind"] is True:
        try:
            result = normalize_preflight_decision(result)
        except Exception as exc:
            raise AlphaSearchError(
                getattr(exc, "code", "invalid_preflight_decision"), str(exc)
            ) from exc
    return result


def _filled(value: Any) -> float:
    return 1.0 if value not in (None, "", [], {}) else 0.0


def score_candidate(candidate: Any, preflight: Mapping[str, Any]) -> dict[str, Any]:
    """Score research readiness with fixed, outcome-blind components."""
    row = dict(_plain(candidate))
    assert_outcome_blind(row)
    fp = _fingerprint(row)
    prior = _market_prior(row)
    observability = str(prior.get("observability_grade") or "missing").lower()
    if observability == "missing" and prior.get("observable") is True:
        observability = "direct"
    expectation = {"direct": 1.0, "strong_proxy": 0.8, "weak_proxy": 0.4}.get(observability, 0.0)
    queue = _queue(row)
    information_gain = {"exploration": 1.0, "adjacent": 0.7, "exploitation": 0.45}.get(queue, 0.0)
    maturity = _GRADE_RANK.get(str(row.get("evidence_grade") or "lead"), 0) / 3.0
    mechanism_independence = sum(
        _filled(fp.get(field))
        for field in ("expectation_proxy", "economic_mechanism", "payoff_shape", "portfolio_role")
    ) / 4.0
    envelope = row.get("execution_envelope") or row.get("execution") or {}
    execution = min(1.0, sum(_filled(value) for value in envelope.values()) / 4.0) if isinstance(envelope, Mapping) else 0.0
    falsifiability = (
        _filled(row.get("falsifier"))
        + _filled(row.get("baseline"))
        + _filled(row.get("treatment"))
        + _filled(row.get("replacement_value_comparator") or row.get("replacement_comparison"))
    ) / 4.0
    portfolio_role = str(fp.get("portfolio_role") or row.get("portfolio_role") or "").lower()
    orthogonality = 1.0 if any(token in portfolio_role for token in ("independent", "orthogonal", "hedge", "tail")) else 0.4
    unresolved = sum(1 for gate in preflight.get("gates", {}).values() if gate.get("status") != "pass") / 4.0
    components = {
        "expectation_identifiability": expectation,
        "information_gain": information_gain,
        "mechanism_independence": mechanism_independence,
        "evidence_maturity": maturity,
        "execution_feasibility": execution,
        "falsifiability": falsifiability,
        "portfolio_orthogonality_proxy": orthogonality,
        "unresolved_source_or_contract_risk": unresolved,
    }
    weights = {
        "expectation_identifiability": 0.20,
        "information_gain": 0.18,
        "mechanism_independence": 0.16,
        "evidence_maturity": 0.14,
        "execution_feasibility": 0.10,
        "falsifiability": 0.14,
        "portfolio_orthogonality_proxy": 0.08,
        "unresolved_source_or_contract_risk": -0.20,
    }
    raw = sum(components[key] * weight for key, weight in weights.items())
    if preflight.get("decision") == "reject":
        raw -= 1.0
    elif preflight.get("decision") == "park":
        raw -= 0.35
    return {
        "score_version": SCORE_VERSION,
        "outcome_blind": True,
        "components": {key: round(value, 6) for key, value in components.items()},
        "weights": weights,
        "total": round(raw, 6),
    }


def select_diverse_candidates(
    candidates: Sequence[Any],
    preflights: Mapping[str, Mapping[str, Any]],
    scores: Mapping[str, Mapping[str, Any]],
    *,
    limit: int = 1,
) -> list[str]:
    """Select deterministically, covering queues before taking close neighbours."""
    if limit < 0:
        raise AlphaSearchError("invalid_selection_limit", str(limit))
    rows = [dict(_plain(candidate)) for candidate in candidates]
    eligible = [
        row for row in rows
        if preflights.get(_candidate_id(row), {}).get("decision") == "pass"
    ]
    ranked = sorted(
        eligible,
        key=lambda row: (
            -float(scores.get(_candidate_id(row), {}).get("total", -math.inf)),
            _candidate_id(row),
        ),
    )
    selected: list[dict[str, Any]] = []
    # One representative per queue first.  With the default limit=1 this still
    # picks the globally best candidate; larger predeclared batches get coverage.
    if limit >= len(SEARCH_QUEUES):
        for queue in SEARCH_QUEUES:
            match = next((row for row in ranked if _queue(row) == queue), None)
            if match is not None:
                selected.append(match)

    def similarity_penalty(row: Mapping[str, Any]) -> int:
        fp = _fingerprint(row)
        dimensions = ("data_source", "economic_mechanism", "decision_surface", "payoff_shape", "horizon", "portfolio_role")
        return sum(
            1
            for chosen in selected
            for field in dimensions
            if fp.get(field) not in (None, "") and fp.get(field) == _fingerprint(chosen).get(field)
        )

    while len(selected) < min(limit, len(ranked)):
        remaining = [row for row in ranked if row not in selected]
        if not remaining:
            break
        remaining.sort(
            key=lambda row: (
                similarity_penalty(row),
                -float(scores.get(_candidate_id(row), {}).get("total", -math.inf)),
                _candidate_id(row),
            )
        )
        selected.append(remaining[0])
    return [_candidate_id(row) for row in selected]


def freeze_selection_panel(
    candidates: Sequence[Any],
    surfaces: Any,
    *,
    scope_manifest: Mapping[str, Any],
    selection_pool_complete: bool,
    prior_fingerprints: Iterable[str | Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Freeze the complete candidate pool under a predeclared scope anchor."""
    manifest = validate_selection_scope_manifest(scope_manifest)
    prior_fingerprint_rows = _verify_prior_fingerprint_anchor(
        manifest, prior_fingerprints
    )
    data_cutoff = str(manifest["data_cutoff"])
    expected_candidate_count = int(manifest["expected_candidate_count"])
    normal_budgets = dict(manifest["queue_budgets"])
    selection_limit = int(manifest["selection_limit"])
    actual_registry_hash = _surface_registry_hash(surfaces)
    if actual_registry_hash != manifest["surface_registry_hash"]:
        raise AlphaSearchError(
            "surface_registry_hash_mismatch",
            f"manifest={manifest['surface_registry_hash']} actual={actual_registry_hash}",
        )
    rows = [_bind_candidate_readiness(candidate, surfaces) for candidate in candidates]
    for row in rows:
        assert_outcome_blind(row)
    if selection_pool_complete is not True:
        raise AlphaSearchError("incomplete_selection_panel", "selection_pool_complete must be exactly true")
    if expected_candidate_count != len(rows):
        raise AlphaSearchError(
            "incomplete_selection_panel",
            f"expected {expected_candidate_count} candidates, received {len(rows)}",
        )
    ids = [_candidate_id(row) for row in rows]
    if any(not candidate_id for candidate_id in ids):
        raise AlphaSearchError("incomplete_selection_panel", "every candidate needs candidate_id")
    duplicates = sorted(candidate_id for candidate_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise AlphaSearchError("incomplete_selection_panel", f"duplicate candidate ids: {duplicates}")
    allowed_surface_ids = set(manifest["allowed_surface_ids"])
    candidate_generation_floor = _parse_clock(
        manifest["data_cutoff"], path="manifest.data_cutoff"
    )
    freeze_dt = _parse_clock(manifest["freeze_at"], path="manifest.freeze_at")
    for row in rows:
        undeclared = sorted(set(row.get("surface_ids") or []) - allowed_surface_ids)
        if undeclared:
            raise AlphaSearchError(
                "incomplete_selection_panel",
                f"candidate {_candidate_id(row)} uses surfaces outside scope: {undeclared}",
            )
        candidate_created_at = row.get("created_at")
        if not candidate_created_at:
            raise AlphaSearchError(
                "incomplete_selection_panel",
                f"candidate {_candidate_id(row)} is missing created_at",
            )
        created_dt = _parse_clock(
            candidate_created_at,
            path=f"candidate[{_candidate_id(row)}].created_at",
        )
        if created_dt < candidate_generation_floor or created_dt > freeze_dt:
            raise AlphaSearchError(
                "incomplete_selection_panel",
                f"candidate {_candidate_id(row)} must be generated between data cutoff and freeze",
            )
    actual_counts = Counter(_queue(row) for row in rows)
    for queue in SEARCH_QUEUES:
        if actual_counts.get(queue, 0) != normal_budgets.get(queue, 0):
            raise AlphaSearchError(
                "incomplete_selection_panel",
                f"queue {queue} expected {normal_budgets.get(queue, 0)}, got {actual_counts.get(queue, 0)}",
            )

    selection_scope_id = f"scope-{manifest['manifest_hash'][:24]}"
    preflights = {
        _candidate_id(row): evaluate_preflight(
            row,
            surfaces,
            prior_fingerprints=prior_fingerprint_rows,
            data_cutoff=data_cutoff,
            evaluated_at=manifest["freeze_at"],
            selection_scope_id=selection_scope_id,
        )
        for row in rows
    }
    contaminated = [
        candidate_id
        for candidate_id, preflight in preflights.items()
        if preflight.get("outcome_blind") is not True
    ]
    if contaminated:
        raise AlphaSearchError(
            "outcome_contamination",
            f"selection scope invalidated by candidates {sorted(contaminated)}",
        )
    scores = {
        _candidate_id(row): score_candidate(row, preflights[_candidate_id(row)])
        for row in rows
    }
    selected_ids = sorted(
        select_diverse_candidates(rows, preflights, scores, limit=selection_limit)
    )
    if len(selected_ids) > selection_limit:
        raise AlphaSearchError("incomplete_selection_panel", "selector exceeded selection_limit")

    ordered_rows = sorted(rows, key=lambda row: _candidate_id(row))
    candidate_hashes = {_candidate_id(row): stable_hash(row) for row in ordered_rows}
    preflight_hashes = {
        candidate_id: _hash_without_top_level(preflight, "preflight_hash")
        for candidate_id, preflight in sorted(preflights.items())
    }
    panel = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "panel_selection",
        "selection_scope_id": selection_scope_id,
        "created_at": manifest["freeze_at"],
        "data_cutoff": data_cutoff,
        "scope_manifest": manifest,
        "scope_manifest_hash": manifest["manifest_hash"],
        "surface_registry_hash": actual_registry_hash,
        "prior_fingerprint_snapshot_hash": manifest["prior_fingerprint_snapshot_hash"],
        "prior_fingerprint_count": manifest["prior_fingerprint_count"],
        "selector_version": SELECTOR_VERSION,
        "score_version": SCORE_VERSION,
        "queue_budgets": normal_budgets,
        "queue_actual_counts": {queue: actual_counts.get(queue, 0) for queue in SEARCH_QUEUES},
        "expected_candidate_count": expected_candidate_count,
        "candidate_pool_complete": True,
        "selection_pool_complete": True,
        "candidate_ids": [_candidate_id(row) for row in ordered_rows],
        "candidate_snapshots": ordered_rows,
        "candidate_snapshot_hashes": candidate_hashes,
        "preflight_decisions": {key: preflights[key] for key in sorted(preflights)},
        "preflight_decision_hashes": preflight_hashes,
        "scores": {key: scores[key] for key in sorted(scores)},
        "rejection_reasons": {
            key: preflights[key].get("failure_reasons", [])
            for key in sorted(preflights)
            if preflights[key].get("decision") != "pass"
        },
        "selection_limit": selection_limit,
        "batch_policy_bundle_id": manifest["batch_policy_bundle_id"],
        "selected_candidate_ids": selected_ids,
        "selected_candidate_id": selected_ids[0] if selection_limit == 1 and selected_ids else None,
        "selection_reason": "highest fixed outcome-blind score after queue coverage and fingerprint diversity",
        "outcome_blind": True,
        "trade_enabled": False,
        "experiment_id_reserved": False,
        "production_impact": research_only_production_impact(),
    }
    panel["panel_hash"] = _hash_without_top_level(panel, "panel_hash")
    try:
        panel = normalize_selection_panel(panel)
    except Exception as exc:
        raise AlphaSearchError(
            getattr(exc, "code", "invalid_selection_panel"), str(exc)
        ) from exc
    verify_selection_panel(
        panel,
        surfaces=surfaces,
        scope_manifest=manifest,
        prior_fingerprints=prior_fingerprint_rows,
        require_external_context=True,
    )
    return panel


def verify_selection_panel(
    panel: Mapping[str, Any],
    *,
    surfaces: Any | None = None,
    scope_manifest: Mapping[str, Any] | None = None,
    prior_fingerprints: Iterable[str | Mapping[str, Any]] = (),
    require_external_context: bool = False,
) -> dict[str, Any]:
    """Recompute a discovery panel and fail closed on omission or tampering.

    Structural verification is useful for parsing an archived artifact.  A
    trust-bearing verification additionally supplies the independently stored
    scope manifest and evidence-surface registry; that mode re-runs every
    D0-D3 preflight and is what the CLI and panel freezer use.
    """
    row = dict(_plain(panel))
    errors: list[str] = []
    try:
        contract_panel = normalize_selection_panel(row)
    except Exception as exc:
        errors.append(
            f"selection_panel_contract_invalid:{getattr(exc, 'code', type(exc).__name__)}"
        )
    else:
        if contract_panel != row:
            errors.append("selection_panel_not_canonical")
    try:
        manifest = validate_selection_scope_manifest(row.get("scope_manifest") or {})
    except AlphaSearchError as exc:
        manifest = {}
        errors.append(f"scope_manifest_invalid:{exc.code}")
    external_manifest: dict[str, Any] | None = None
    if scope_manifest is not None:
        try:
            external_manifest = validate_selection_scope_manifest(scope_manifest)
        except AlphaSearchError as exc:
            errors.append(f"external_scope_manifest_invalid:{exc.code}")
        else:
            if manifest and external_manifest != manifest:
                errors.append("external_scope_manifest_mismatch")
    elif require_external_context:
        errors.append("external_scope_manifest_required")
    if surfaces is None and require_external_context:
        errors.append("external_surface_registry_required")
    prior_fingerprint_rows: tuple[str, ...] = ()
    if manifest:
        try:
            prior_fingerprint_rows = _verify_prior_fingerprint_anchor(
                manifest, prior_fingerprints
            )
        except AlphaSearchError as exc:
            errors.append(exc.code)
    if manifest:
        if row.get("scope_manifest_hash") != manifest.get("manifest_hash"):
            errors.append("scope_manifest_hash_mismatch")
        expected_scope_id = f"scope-{manifest['manifest_hash'][:24]}"
        if row.get("selection_scope_id") != expected_scope_id:
            errors.append("selection_scope_recomputation_mismatch")
        for panel_key, manifest_key in (
            ("created_at", "freeze_at"),
            ("data_cutoff", "data_cutoff"),
            ("selector_version", "selector_version"),
            ("score_version", "score_version"),
            ("queue_budgets", "queue_budgets"),
            ("expected_candidate_count", "expected_candidate_count"),
            ("selection_limit", "selection_limit"),
            ("batch_policy_bundle_id", "batch_policy_bundle_id"),
            ("surface_registry_hash", "surface_registry_hash"),
            ("prior_fingerprint_snapshot_hash", "prior_fingerprint_snapshot_hash"),
            ("prior_fingerprint_count", "prior_fingerprint_count"),
        ):
            if row.get(panel_key) != manifest.get(manifest_key):
                errors.append(f"manifest_binding_mismatch:{panel_key}")
    if row.get("candidate_pool_complete") is not True or row.get("selection_pool_complete") is not True:
        errors.append("selection_pool_not_declared_complete")
    candidates = row.get("candidate_snapshots")
    if not isinstance(candidates, list):
        errors.append("candidate_snapshots_missing")
        candidates = []
    ids = [_candidate_id(candidate) for candidate in candidates if isinstance(candidate, Mapping)]
    if len(ids) != len(candidates) or len(set(ids)) != len(ids):
        errors.append("candidate_ids_invalid_or_duplicate")
    if int(row.get("expected_candidate_count") or -1) != len(candidates):
        errors.append("expected_candidate_count_mismatch")
    if row.get("candidate_ids") != sorted(ids):
        errors.append("candidate_ids_mismatch")
    if manifest:
        allowed_surface_ids = set(manifest.get("allowed_surface_ids") or [])
        candidate_generation_floor = _parse_clock(
            manifest["data_cutoff"], path="manifest.data_cutoff"
        )
        freeze_dt = _parse_clock(manifest["freeze_at"], path="manifest.freeze_at")
        for candidate in candidates:
            candidate_id = _candidate_id(candidate)
            try:
                normal_candidate = _normalise_candidate(
                    candidate, require_semantic_id=True
                )
                if normal_candidate != candidate:
                    errors.append(f"candidate_not_canonical:{candidate_id}")
            except AlphaSearchError as exc:
                errors.append(f"candidate_contract_invalid:{candidate_id}:{exc.code}")
            undeclared = sorted(
                set(candidate.get("surface_ids") or []) - allowed_surface_ids
            )
            if undeclared:
                errors.append(f"candidate_surface_outside_scope:{candidate_id}")
            try:
                candidate_created_at = _parse_clock(
                    candidate.get("created_at"),
                    path=f"candidate[{candidate_id}].created_at",
                )
                if candidate_created_at < candidate_generation_floor or candidate_created_at > freeze_dt:
                    errors.append(f"candidate_generation_clock_outside_scope:{candidate_id}")
            except AlphaSearchError:
                errors.append(f"candidate_generation_clock_invalid:{candidate_id}")
    expected_hashes = {
        _candidate_id(candidate): stable_hash(candidate)
        for candidate in candidates
        if isinstance(candidate, Mapping)
    }
    if row.get("candidate_snapshot_hashes") != expected_hashes:
        errors.append("candidate_snapshot_hash_mismatch")
    preflights = row.get("preflight_decisions") or {}
    if set(preflights) != set(ids):
        errors.append("preflight_candidate_set_mismatch")
    expected_preflight_hashes = {
        str(candidate_id): _hash_without_top_level(value, "preflight_hash")
        for candidate_id, value in preflights.items()
        if isinstance(value, Mapping)
    }
    if row.get("preflight_decision_hashes") != expected_preflight_hashes:
        errors.append("preflight_decision_hash_mismatch")
    expected_rejections: dict[str, list[str]] = {}
    for candidate_id, preflight in preflights.items():
        if not isinstance(preflight, Mapping):
            errors.append(f"preflight_not_object:{candidate_id}")
            continue
        if preflight.get("candidate_id") != candidate_id:
            errors.append(f"preflight_candidate_id_mismatch:{candidate_id}")
        expected_scope_id = row.get("selection_scope_id")
        if preflight.get("selection_scope_id") != expected_scope_id:
            errors.append(f"preflight_selection_scope_mismatch:{candidate_id}")
        if preflight.get("data_cutoff") != row.get("data_cutoff"):
            errors.append(f"preflight_data_cutoff_mismatch:{candidate_id}")
        if preflight.get("evaluated_at") != row.get("created_at"):
            errors.append(f"preflight_evaluated_at_mismatch:{candidate_id}")
        if preflight.get("preflight_version") != PREFLIGHT_VERSION:
            errors.append(f"preflight_version_mismatch:{candidate_id}")
        expected_preflight_hash = expected_preflight_hashes.get(str(candidate_id))
        if preflight.get("preflight_hash") != expected_preflight_hash:
            errors.append(f"preflight_embedded_hash_mismatch:{candidate_id}")
        if preflight.get("outcome_fields_excluded") != sorted(_FORBIDDEN_OUTCOME_KEYS):
            errors.append(f"preflight_outcome_exclusion_set_mismatch:{candidate_id}")
        gates = preflight.get("gates")
        if not isinstance(gates, Mapping) or set(gates) != {"D0", "D1", "D2", "D3"}:
            errors.append(f"preflight_gates_invalid:{candidate_id}")
        else:
            statuses = [
                gate.get("status") if isinstance(gate, Mapping) else None
                for gate in gates.values()
            ]
            if any(status not in {"pass", "park", "reject"} for status in statuses):
                errors.append(f"preflight_gate_status_invalid:{candidate_id}")
            for gate_name, gate in gates.items():
                if not isinstance(gate, Mapping) or set(gate) != {"status", "reasons"}:
                    errors.append(f"preflight_gate_shape_invalid:{candidate_id}:{gate_name}")
                    continue
                reasons = gate.get("reasons")
                if not isinstance(reasons, list):
                    errors.append(f"preflight_gate_reasons_invalid:{candidate_id}:{gate_name}")
                elif (gate.get("status") == "pass") != (len(reasons) == 0):
                    errors.append(f"preflight_gate_reason_status_mismatch:{candidate_id}:{gate_name}")
            reduced = "reject" if "reject" in statuses else "park" if "park" in statuses else "pass"
            if preflight.get("decision") != reduced:
                errors.append(f"preflight_decision_reduction_mismatch:{candidate_id}")
        if preflight.get("outcome_blind") is not True:
            errors.append(f"preflight_outcome_blind_false:{candidate_id}")
        candidate = next(
            (item for item in candidates if _candidate_id(item) == candidate_id),
            {},
        )
        source_hashes = preflight.get("source_snapshot_hashes") or {}
        if set(source_hashes) != set(candidate.get("surface_ids") or []):
            errors.append(f"preflight_source_set_mismatch:{candidate_id}")
        elif any(not re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in source_hashes.values()):
            errors.append(f"preflight_source_hash_invalid:{candidate_id}")
        if preflight.get("fingerprint_hash") != _fingerprint_key(candidate):
            errors.append(f"preflight_fingerprint_hash_mismatch:{candidate_id}")
        failures = preflight.get("failure_reasons")
        if not isinstance(failures, list) or any(reason not in FAILURE_REASONS for reason in failures):
            errors.append(f"preflight_failure_reasons_invalid:{candidate_id}")
        elif (preflight.get("decision") == "pass") != (len(failures) == 0):
            errors.append(f"preflight_failure_decision_mismatch:{candidate_id}")
        if preflight.get("trade_enabled") is not False:
            errors.append(f"preflight_trade_boundary_violation:{candidate_id}")
        preflight_impact = preflight.get("production_impact")
        if not isinstance(preflight_impact, Mapping) or not preflight_impact or any(
            value is not False for value in preflight_impact.values()
        ):
            errors.append(f"preflight_production_boundary_violation:{candidate_id}")
        if preflight.get("decision") != "pass":
            expected_rejections[str(candidate_id)] = sorted(preflight.get("failure_reasons") or [])
    claimed_rejections = {
        str(key): sorted(value or [])
        for key, value in (row.get("rejection_reasons") or {}).items()
    }
    if claimed_rejections != expected_rejections:
        errors.append("rejection_reasons_mismatch")
    if surfaces is not None:
        actual_registry_hash = _surface_registry_hash(surfaces)
        if row.get("surface_registry_hash") != actual_registry_hash:
            errors.append("external_surface_registry_hash_mismatch")
        if manifest and manifest.get("surface_registry_hash") != actual_registry_hash:
            errors.append("manifest_external_surface_registry_hash_mismatch")
        for candidate in candidates:
            candidate_id = _candidate_id(candidate)
            try:
                recomputed_preflight = evaluate_preflight(
                    candidate,
                    surfaces,
                    prior_fingerprints=prior_fingerprint_rows,
                    data_cutoff=str(row.get("data_cutoff") or ""),
                    evaluated_at=str(row.get("created_at") or ""),
                    selection_scope_id=str(row.get("selection_scope_id") or ""),
                )
            except (AlphaSearchError, TypeError, ValueError) as exc:
                errors.append(f"preflight_recomputation_failed:{candidate_id}:{getattr(exc, 'code', type(exc).__name__)}")
                continue
            if _plain(preflights.get(candidate_id)) != recomputed_preflight:
                errors.append(f"preflight_recomputation_mismatch:{candidate_id}")
    scores = row.get("scores") or {}
    if set(scores) != set(ids):
        errors.append("score_candidate_set_mismatch")
    else:
        recomputed_scores = {
            _candidate_id(candidate): score_candidate(
                candidate, preflights.get(_candidate_id(candidate), {})
            )
            for candidate in candidates
            if isinstance(candidate, Mapping)
        }
        if scores != recomputed_scores:
            errors.append("score_recomputation_mismatch")
    queue_actual = Counter(
        _queue(candidate) for candidate in candidates if isinstance(candidate, Mapping)
    )
    expected_queue_actual = {queue: queue_actual.get(queue, 0) for queue in SEARCH_QUEUES}
    if row.get("queue_actual_counts") != expected_queue_actual:
        errors.append("queue_actual_counts_mismatch")
    budgets = row.get("queue_budgets") or {}
    if any(queue_actual.get(queue, 0) != int(budgets.get(queue, -1)) for queue in SEARCH_QUEUES):
        errors.append("queue_budget_or_completeness_mismatch")
    selected = row.get("selected_candidate_ids") or []
    if not isinstance(selected, list) or any(candidate_id not in ids for candidate_id in selected):
        errors.append("selected_candidate_not_in_panel")
    if len(selected) > int(row.get("selection_limit") or 0):
        errors.append("selection_limit_exceeded")
    if row.get("selected_candidate_id") not in ({None} | set(ids)):
        errors.append("selected_candidate_id_not_in_panel")
    if set(preflights) == set(ids) and set(scores) == set(ids):
        recomputed_selected = sorted(
            select_diverse_candidates(
                candidates,
                preflights,
                scores,
                limit=int(row.get("selection_limit") or 0),
            )
        )
        if selected != recomputed_selected:
            errors.append("selection_recomputation_mismatch")
    expected_single = selected[0] if int(row.get("selection_limit") or 0) == 1 and selected else None
    if row.get("selected_candidate_id") != expected_single:
        errors.append("selected_candidate_id_mismatch")
    if row.get("outcome_blind") is not True:
        errors.append("outcome_blind_not_attested")
    if row.get("trade_enabled") is not False:
        errors.append("trade_enabled_boundary_violation")
    if row.get("experiment_id_reserved") is not False:
        errors.append("experiment_reservation_boundary_violation")
    production_impact = row.get("production_impact")
    if not isinstance(production_impact, Mapping) or not production_impact or any(
        value is not False for value in production_impact.values()
    ):
        errors.append("production_impact_boundary_violation")
    contamination = []
    contamination.extend(outcome_field_paths(row, _path="panel"))
    if contamination:
        errors.append("outcome_contamination")
    claimed_hash = row.get("panel_hash")
    recomputed_hash = _hash_without_top_level(row, "panel_hash")
    if claimed_hash != recomputed_hash:
        errors.append("panel_hash_mismatch")
    if errors:
        raise AlphaSearchError("incomplete_selection_panel", ", ".join(sorted(set(errors))))
    return {
        "valid": True,
        "selection_scope_id": row.get("selection_scope_id"),
        "panel_hash": claimed_hash,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "outcome_blind": row.get("outcome_blind"),
        "trade_enabled": row.get("trade_enabled"),
    }


def build_search_report(
    panel: Mapping[str, Any],
    *,
    surfaces: Any | None = None,
    scope_manifest: Mapping[str, Any] | None = None,
    prior_fingerprints: Iterable[str | Mapping[str, Any]] = (),
    require_external_context: bool = False,
) -> dict[str, Any]:
    prior_fingerprint_rows = tuple(prior_fingerprints)
    verification = verify_selection_panel(
        panel,
        surfaces=surfaces,
        scope_manifest=scope_manifest,
        prior_fingerprints=prior_fingerprint_rows,
        require_external_context=require_external_context,
    )
    preflights = panel.get("preflight_decisions") or {}
    decision_counts = Counter(
        str(row.get("decision") or "unknown")
        for row in preflights.values()
        if isinstance(row, Mapping)
    )
    failure_counts = Counter(
        reason
        for row in preflights.values()
        if isinstance(row, Mapping)
        for reason in row.get("failure_reasons") or []
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": "alpha_search_discovery_report",
        "generated_at": utc_now(),
        "selection_scope_id": panel.get("selection_scope_id"),
        "panel_hash": panel.get("panel_hash"),
        "panel_verification": verification,
        "queue_budgets": panel.get("queue_budgets"),
        "queue_actual_counts": panel.get("queue_actual_counts"),
        "candidate_count": len(panel.get("candidate_ids") or []),
        "preflight_decision_counts": dict(sorted(decision_counts.items())),
        "failure_reason_counts": dict(sorted(failure_counts.items())),
        "selected_candidate_ids": panel.get("selected_candidate_ids") or [],
        "selected_candidate_id": panel.get("selected_candidate_id"),
        "outcome_blind": True,
        "trade_enabled": False,
        "experiment_id_reserved": False,
        "next_boundary": "selected gate_candidate may separately enter experiment.py novelty/reserve workflow",
        "production_impact": panel.get("production_impact") or {},
    }


_FAILURE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("outcome_contamination", ("outcome contamination", "look-ahead", "post-selection outcome")),
    ("incomplete_selection_panel", ("selection panel", "panel incomplete", "trial panel incomplete")),
    ("duplicate_or_frozen", ("duplicate", "frozen", "near-neighbor", "novelty", "reopen guard")),
    ("pit_or_source_failure", ("point-in-time", " pit ", "source contract", "publication clock", "permission", "unavailable")),
    ("market_expectation_unidentified", ("market expectation", "market prior", "consensus unidentified", "expectation proxy")),
    ("no_candidate_overlap", ("no overlap", "zero overlap", "candidate overlap")),
    ("insufficient_independent_rows", ("insufficient", "small sample", "not enough", "settled rows", "independent rows")),
    ("already_priced", ("already priced", "priced in", "absorbed before entry", "too late")),
    ("wrong_transmission_mapping", ("wrong mapping", "ticker mapping", "direction mapping", "transmission")),
    ("cost_and_carry", ("transaction cost", "cost and carry", "costs", "carry", "slippage")),
    ("borrow_or_capacity", ("borrow", "capacity", "liquidity", "loan availability")),
    ("core_opportunity_cost", ("opportunity cost", "did not beat core", "core replacement")),
    ("concentration", ("concentration", "single ticker", "few dates", "top ticker")),
    ("tail_risk", ("tail risk", "drawdown", "left tail")),
    ("no_gross_edge", ("no gross edge", "negative gross", "no alpha", "no edge")),
)


def classify_failure(record: Mapping[str, Any]) -> dict[str, Any]:
    """Map a historical closeout to the closed taxonomy without rewriting it."""
    structured = record.get("primary_failure_reason")
    if structured in FAILURE_REASONS:
        return {
            "primary_failure_reason": structured,
            "secondary_failure_reasons": [
                reason for reason in record.get("secondary_failure_reasons") or []
                if reason in FAILURE_REASONS and reason != structured
            ],
            "mapping_confidence": 1.0,
            "mapping_source": "structured",
            "raw_failure_text": None,
        }
    fields = (
        record.get("decision"),
        record.get("rejection_reason"),
        record.get("why_result_happened"),
        record.get("summary"),
        record.get("post_run_reflection"),
    )
    raw = " | ".join(str(value) for value in fields if value not in (None, ""))
    text = f" {raw.lower()} "
    matches = [reason for reason, patterns in _FAILURE_PATTERNS if any(pattern in text for pattern in patterns)]
    primary = matches[0] if matches else "unclassified"
    return {
        "primary_failure_reason": primary,
        "secondary_failure_reasons": matches[1:],
        "mapping_confidence": 0.75 if matches else 0.0,
        "mapping_source": "legacy_text_heuristic" if matches else "unclassified",
        "raw_failure_text": raw or None,
    }


def build_failure_taxonomy(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a deduplicated historical failure view for search-prior feedback."""
    seen: set[str] = set()
    mapped: list[dict[str, Any]] = []
    for index, raw_record in enumerate(records):
        record = dict(raw_record)
        structured_reason = record.get("primary_failure_reason")
        decision_text = " ".join(
            str(record.get(key) or "").lower()
            for key in ("decision", "status", "rejection_reason", "why_blocked")
        )
        failure_shaped = structured_reason in FAILURE_REASONS or any(
            token in decision_text
            for token in ("reject", "block", "fail", "invalid", "park", "duplicate")
        )
        if not failure_shaped:
            continue
        identity = str(record.get("experiment_id") or record.get("id") or stable_hash(record))
        if identity in seen:
            continue
        seen.add(identity)
        classification = classify_failure(record)
        fp = record.get("fingerprint") if isinstance(record.get("fingerprint"), Mapping) else {}
        mapped.append(
            {
                "record_id": identity,
                "source_index": index,
                "fingerprint": dict(fp),
                **classification,
            }
        )
    counts = Counter(row["primary_failure_reason"] for row in mapped)
    by_mechanism: dict[str, Counter[str]] = defaultdict(Counter)
    for row in mapped:
        mechanism = str(row["fingerprint"].get("economic_mechanism") or "unknown")
        by_mechanism[mechanism][row["primary_failure_reason"]] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": "alpha_search_failure_taxonomy_v1",
        "record_count": len(mapped),
        "primary_failure_counts": dict(sorted(counts.items())),
        "failure_search_policy": FAILURE_SEARCH_POLICY,
        "by_mechanism": {
            mechanism: dict(sorted(counter.items()))
            for mechanism, counter in sorted(by_mechanism.items())
        },
        "records": mapped,
    }
