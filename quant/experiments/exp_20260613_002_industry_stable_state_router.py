"""exp-20260613-002: industry-stable state router scout.

Alpha search. This is the single frozen Gate 1-4 follow-up queued by
exp-20260612-027: among broad accepted allocator source rows, the only
source x market-state cell that survived the ex-top-ticker robustness screen
was `industry_stable_core_flow` in `mixed|balanced|normal`.

This runner tests one decision hypothesis: when that exact source-state cell
appears, route it ahead of allocator sources ranked 4 and lower while leaving
lagged consensus, volatility relief, and rolling peer shock ahead of it.
Everything else is unchanged: source builders, top-1/day, notional, hold,
cooldown, core behavior, LLM/news, and live/default orders.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260611_005_lagged_consensus_shared_allocator_source as accepted
import exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution as statemod


framework = accepted.framework
exp008 = accepted.exp008

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from accepted_helper_source_priority_allocator_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    RULE_VERSION as ACCEPTED_ALLOCATOR_RULE_VERSION,
    SAME_TICKER_COOLDOWN_DAYS,
    SOURCE_PRIORITY,
    SOURCE_RULE_VERSION as ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
    _build_source_trades as build_source_trades,
    _normalise_source_row as normalise_accepted_source_row,
    build_accepted_helper_source_priority_allocator_historical_trades,
)
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260613-002"
STEM = "industry_stable_state_router"
TRIAL_FAMILY = "market_state_conditioned_sleeve_router"
TRIAL_VARIANT_ID = "industry_stable_core_flow_mixed_balanced_normal_rank4_router_v1"
CHANGED_VARIABLE = "industry_stable_core_flow_mixed_balanced_normal_rank4_state_router_v1"
OWNER = "alpha-search-automation"

ROUTER_RULE_VERSION = "industry_stable_core_flow_state_router_rank4_v1"
ROUTER_SOURCE_FAMILY = "industry_stable_core_flow"
ROUTER_CELL = "mixed|balanced|normal"
ROUTER_EFFECTIVE_RANK = 4
ROUTER_RANK_SORT_BONUS = -1

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_002_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MIN_ROUTER_SELECTED_TRADES = 9
MIN_ROUTER_SELECTED_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260611-005",
    "aggregate_ev_delta": 2.1849,
    "aggregate_pnl_delta": 40397.21,
    "window_deltas": {
        "late_strong": {"ev": 0.9092, "pnl": 9431.68},
        "mid_weak": {"ev": 0.6352, "pnl": 11133.95},
        "old_thin": {"ev": 0.6405, "pnl": 19831.58},
    },
}

PREDICTION = {
    "success_probability": 0.30,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_allocator_comparator_not_beaten",
        "late_strong_regression",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260612-027 found only one source-state survivor after "
        "ex-top-ticker robustness: industry_stable_core_flow x "
        "mixed|balanced|normal, 32 rows, 31 tickers, positive all three "
        "windows, top ticker only 20.9 percent. Risk remains high because the "
        "cell was screened on frozen windows and routing can displace stronger "
        "accepted allocator rows."
    ),
    "recorded_at": "2026-06-13T00:06:28+00:00",
}

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=BASE_NOTIONAL_USD,
    max_capital_pct=0.32,
    min_dollar_volume=10_000_000.0,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=8,
    order_semantics="next_open_paper_only",
    kill_switch_drawdown_pct=0.15,
    sleeve_drawdown_stop_pct=None,
    notes=(
        "Same accepted-helper allocator bucket as exp-20260612-024: fixed "
        "$4,000 paper notional, top-1/day, max 8 concurrent default-off paper "
        "positions, 10-trading-day hold, 12-trading-day same-ticker cooldown, "
        "and no core displacement. This scout does not change production; a "
        "positive result would require moving the state router into the shared "
        "allocator helper and daily snapshot parity before retention."
    ),
)

PRODUCTION_IMPACT_REPLAY_ONLY = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_state_router_scout",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "No production/shared helper is changed by this replay-only scout. If "
        "Gate 4 passes, the result remains a positive lead until the identical "
        "state-router rule is implemented in the shared allocator helper and "
        "daily default-off snapshot with parity tests. If Gate 4 fails, no "
        "strategy logic is retained."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "allocation/routing alpha: route the only exp-20260612-027 ex-top "
        "surviving source-state cell, industry_stable_core_flow x "
        "mixed|balanced|normal, ahead of allocator rank >=4 sources."
    ),
    "2_history_check": {
        "exp-20260612-027": (
            "Observed-only broad source-state attribution found exactly one "
            "robust survivor: industry_stable_core_flow x mixed|balanced|normal "
            "with 32 rows, 31 tickers, all three windows positive, ex-top edge "
            "+2.21pp, and top ticker share 20.9%."
        ),
        "exp-20260612-018": (
            "Lagged-consensus mixed|balanced|normal notional tilt improved EV "
            "but failed concentration on APP."
        ),
        "exp-20260612-020": (
            "Per-ticker cap for that consensus tilt also failed concentration; "
            "do not retry lagged-consensus state tilt on frozen windows."
        ),
        "exp-20260611-005": (
            "Current accepted source-priority allocator with lagged consensus: "
            "aggregate EV +2.1849 and PnL +$40,397.21; binding comparator."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "docs/backtesting.md canonical three windows. The router must improve "
        "aggregate EV/PnL versus the accepted allocator, avoid direct EV/PnL "
        "regressions versus the same-run accepted allocator control, beat the "
        "exp-20260611-005 per-window comparator versus core, satisfy survival, "
        "drawdown, sample, and both total/routed concentration guards."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_002_industry_stable_state_router.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _entry_date(row: dict[str, Any], window_dates: list[str]) -> str | None:
    entry = str(row.get("entry_date") or "")[:10]
    if entry:
        return entry
    signal = str(row.get("signal_date") or row.get("date") or "")[:10]
    if not signal:
        return None
    for day in window_dates:
        if day > signal:
            return day
    return None


def _annotate_market_state(
    row: dict[str, Any],
    *,
    state_snapshot: dict[str, list[dict[str, Any]]],
    state_dates: list[str],
) -> dict[str, Any]:
    out = dict(row)
    entry = _entry_date(out, state_dates)
    state = (
        statemod._state_for_entry_date(
            snapshot=state_snapshot,
            trading_dates=state_dates,
            entry_date=entry or "",
        )
        if entry
        else None
    )
    combined = str((state or {}).get("combined_state") or "")
    applies = (
        str(out.get("source_family") or "") == ROUTER_SOURCE_FAMILY
        and combined == ROUTER_CELL
    )
    out["state_router_entry_date"] = entry
    out["state_router_market_state"] = state
    out["state_router_combined_state"] = combined or None
    out["state_router_applied"] = applies
    out["state_router_rule_version"] = ROUTER_RULE_VERSION
    if applies:
        out["source_priority_original_rank"] = int(out.get("source_priority_rank") or 999)
        out["source_priority_effective_rank"] = ROUTER_EFFECTIVE_RANK
    else:
        out["source_priority_original_rank"] = int(out.get("source_priority_rank") or 999)
        out["source_priority_effective_rank"] = int(out.get("source_priority_rank") or 999)
    return out


def _effective_rank_sort_bucket(row: dict[str, Any]) -> int:
    rank = int(row.get("source_priority_effective_rank") or row.get("source_priority_rank") or 999)
    if row.get("state_router_applied"):
        return rank * 10 + ROUTER_RANK_SORT_BONUS
    return rank * 10


def _allocator_score(row: dict[str, Any]) -> float:
    rank = max(1, int(row.get("source_priority_effective_rank") or 999))
    return _round(1000.0 / rank + _float(row.get("source_priority_score")), 6) or 0.0


def _decision_id(row: dict[str, Any]) -> str:
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    source_family = str(row.get("source_family") or "unknown")
    return (
        "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER:"
        f"{ROUTER_RULE_VERSION}:{signal_date}:{ticker}:{source_family}"
    )


def _select_state_router_rows(
    *,
    source_rows: list[dict[str, Any]],
    trading_dates: list[str],
    state_snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    state_dates = statemod._trading_dates(state_snapshot)
    candidates = []
    for row in source_rows:
        source_family = str(row.get("source_family") or "")
        if source_family not in SOURCE_PRIORITY:
            continue
        normalised = normalise_accepted_source_row(row, source_family)
        candidates.append(
            _annotate_market_state(
                normalised,
                state_snapshot=state_snapshot,
                state_dates=state_dates,
            )
        )

    candidates.sort(
        key=lambda row: (
            str(row.get("signal_date") or "")[:10],
            _effective_rank_sort_bucket(row),
            -_float(row.get("source_priority_score")),
            str(row.get("ticker") or ""),
        )
    )

    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    used_date_counts: Counter[str] = Counter()
    next_allowed_pos_by_ticker: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("signal_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_position.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if used_date_counts[signal_date] >= 1:
            rejected.append({**row, "filter_reason": "daily_top1_source_priority_limit"})
            continue
        if pos < next_allowed_pos_by_ticker.get(ticker, -1):
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        out = {
            **deepcopy(row),
            "source": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
            "sleeve": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
            "rule_version": ROUTER_RULE_VERSION,
            "accepted_allocator_rule_version": ACCEPTED_ALLOCATOR_RULE_VERSION,
            "source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
            "decision_id": _decision_id(row),
            "candidate_score": _allocator_score(row),
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "notional_usd": BASE_NOTIONAL_USD,
            "paper_status": "closed",
            "trade_enabled": False,
            "alters_orders": False,
        }
        selected.append(out)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS

    router_candidates = [row for row in candidates if row.get("state_router_applied")]
    router_selected = [row for row in selected if row.get("state_router_applied")]
    router_rejected = [row for row in rejected if row.get("state_router_applied")]
    audit = {
        "source_candidate_count": len(candidates),
        "selected_priority_trade_count": len(selected),
        "filtered_priority_candidate_count": len(rejected),
        "source_candidate_counts": dict(Counter(str(row.get("source_family")) for row in candidates)),
        "selected_source_counts": dict(Counter(str(row.get("source_family")) for row in selected)),
        "router_candidate_count": len(router_candidates),
        "router_selected_count": len(router_selected),
        "router_rejected_count": len(router_rejected),
        "router_rejected_reasons": dict(
            Counter(str(row.get("filter_reason")) for row in router_rejected)
        ),
        "daily_entry_slots": 1,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "router_rule": {
            "source_family": ROUTER_SOURCE_FAMILY,
            "combined_state": ROUTER_CELL,
            "effective_rank": ROUTER_EFFECTIVE_RANK,
            "sorts_ahead_of_same_rank": True,
        },
    }
    return selected, rejected, audit


def _candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [row for row in rows if _float(row.get("pnl")) > 0]
    total = sum(_float(row.get("pnl")) for row in positive)
    if total <= 0:
        return {
            "positive_pnl": 0.0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "positive_by_ticker_pnl": {},
        }
    by_ticker: dict[str, float] = defaultdict(float)
    for row in positive:
        by_ticker[str(row.get("ticker") or "").upper()] += _float(row.get("pnl"))
    shares = [value / total for value in by_ticker.values()]
    return {
        "positive_pnl": round(total, 2),
        "max_single_positive_pnl_share": round(max(shares), 6) if shares else None,
        "positive_pnl_hhi": round(sum(share * share for share in shares), 6),
        "positive_by_ticker_pnl": {key: round(value, 2) for key, value in sorted(by_ticker.items())},
    }


def _direct_metric_delta(
    router_metrics: dict[str, Any],
    control_metrics: dict[str, Any],
) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "total_pnl",
        "total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
    ]
    return {
        key: _round(
            _float(router_metrics.get(key)) - _float(control_metrics.get(key)),
            6 if key != "total_pnl" else 2,
        )
        for key in keys
    }


def _binding_gate4(
    *,
    aggregate: dict[str, Any],
    control_direct_aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    router_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    window_rows: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    total_concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    router_concentration_passed = (
        router_summary["max_single_positive_pnl_share"] is not None
        and router_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and router_summary["positive_pnl_hhi"] is not None
        and router_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )

    failed: list[str] = []
    aggregate_ev = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    aggregate_pnl = float(aggregate["total_pnl_delta_sum"] or 0.0)
    direct_ev = float(control_direct_aggregate["expected_value_score_delta_sum"] or 0.0)
    direct_pnl = float(control_direct_aggregate["total_pnl_delta_sum"] or 0.0)
    if aggregate_ev <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]:
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if aggregate_pnl <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_allocator_pnl_comparator_not_beaten")
    if direct_ev <= 0.0:
        failed.append("direct_ev_vs_accepted_allocator_not_positive")
    if direct_pnl <= 0.0:
        failed.append("direct_pnl_vs_accepted_allocator_not_positive")
    if int(control_direct_aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("direct_window_ev_regression_vs_accepted_allocator")
    if int(control_direct_aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("direct_window_pnl_regression_vs_accepted_allocator")
    if int(target_summary["total_trade_count"] or 0) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if int(router_summary["trade_count"] or 0) < MIN_ROUTER_SELECTED_TRADES:
        failed.append("router_selected_sample_too_small")
    if len(router_summary["windows_with_trades"]) < MIN_ROUTER_SELECTED_WINDOWS:
        failed.append("router_selected_window_coverage_too_small")
    if float(control_direct_aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("direct_drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not total_concentration_passed:
        failed.append("total_target_concentration_failed")
    if not router_concentration_passed:
        failed.append("router_target_concentration_failed")

    comparator_regressions: list[str] = []
    for label, row in window_rows.items():
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        delta = row["delta_vs_core"]
        if float(delta.get("expected_value_score") or 0.0) < comparator["ev"]:
            comparator_regressions.append(f"{label}_ev")
        if float(delta.get("total_pnl") or 0.0) < comparator["pnl"]:
            comparator_regressions.append(f"{label}_pnl")
    if comparator_regressions:
        failed.append("accepted_allocator_window_comparator_regression")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_industry_stable_state_router_requires_shared_helper"
            if passed
            else "rejected_industry_stable_state_router"
        ),
        "failed_reasons": failed,
        "comparator_regressions": comparator_regressions,
        "aggregate_ev_delta_vs_core": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta_vs_core": aggregate["total_pnl_delta_sum"],
        "direct_ev_delta_vs_accepted_allocator": control_direct_aggregate[
            "expected_value_score_delta_sum"
        ],
        "direct_pnl_delta_vs_accepted_allocator": control_direct_aggregate[
            "total_pnl_delta_sum"
        ],
        "direct_windows_ev_improved": control_direct_aggregate["windows_ev_improved"],
        "direct_windows_ev_regressed": control_direct_aggregate["windows_ev_regressed"],
        "direct_windows_pnl_improved": control_direct_aggregate["windows_pnl_improved"],
        "direct_windows_pnl_regressed": control_direct_aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "router_selected_trade_count": router_summary["trade_count"],
        "router_selected_trade_count_min": MIN_ROUTER_SELECTED_TRADES,
        "router_selected_windows": router_summary["windows_with_trades"],
        "router_selected_window_count_min": MIN_ROUTER_SELECTED_WINDOWS,
        "max_direct_drawdown_worse": control_direct_aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "target_concentration": {
            "passed": total_concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "router_concentration": {
            "passed": router_concentration_passed,
            "max_single_positive_pnl_share": router_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": router_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            "positive_by_ticker_pnl": router_summary["positive_by_ticker_pnl"],
        },
    }


def _aggregate_direct_rows(window_rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev = [row["delta_vs_accepted_allocator"]["expected_value_score"] for row in window_rows.values()]
    pnl = [row["delta_vs_accepted_allocator"]["total_pnl"] for row in window_rows.values()]
    dd = [row["delta_vs_accepted_allocator"]["max_drawdown_pct"] for row in window_rows.values()]
    return {
        "expected_value_score_delta_sum": round(sum(_float(v) for v in ev), 6),
        "total_pnl_delta_sum": round(sum(_float(v) for v in pnl), 2),
        "max_drawdown_delta_max": round(max((_float(v) for v in dd), default=0.0), 6),
        "windows_ev_improved": sum(1 for v in ev if _float(v) > 0),
        "windows_ev_regressed": sum(1 for v in ev if _float(v) < 0),
        "windows_pnl_improved": sum(1 for v in pnl if _float(v) > 0),
        "windows_pnl_regressed": sum(1 for v in pnl if _float(v) < 0),
    }


def _full_stack_blocks(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    trades = int(target_summary["total_trade_count"] or 0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    window_metrics = {
        "aggregate_ev_delta": float(aggregate["expected_value_score_delta_sum"] or 0.0),
        "aggregate_pnl_delta": pnl_delta,
        "max_drawdown_worse_max": float(aggregate["max_drawdown_delta_max"] or 0.0),
        "windows_ev_improved": int(aggregate["windows_ev_improved"] or 0),
        "windows_ev_regressed": int(aggregate["windows_ev_regressed"] or 0),
        "adjusted_trade_count": trades,
        "adjusted_window_count": len(target_summary["windows_with_target_trades"]),
        "single_ticker_positive_share": target_summary["max_single_positive_pnl_share"],
        "top_5_contribution_pct": _top5_positive_share(target_summary),
        "hhi_concentration": target_summary["positive_pnl_hhi"],
        "baseline_single_ticker_positive_share": 0.50,
        "baseline_top_5_contribution_pct": 0.60,
        "baseline_hhi_concentration": 0.35,
        "avg_pnl_per_trade_delta": round(pnl_delta / trades, 2) if trades else None,
        "avg_return_delta_pp": round(100.0 * pnl_delta / (BASE_NOTIONAL_USD * trades), 4)
        if trades
        else None,
    }
    return {
        "window_metrics": window_metrics,
        "gate4_strict_materiality": evaluate_gate4(window_metrics, check_materiality=True),
        "gate4_canonical": evaluate_gate4(window_metrics, check_materiality=False),
        "materiality_note": (
            "Strict materiality is recorded for comparability. The binding "
            "candidate-pool materiality standard is direct improvement over "
            "the accepted exp-20260611-005 allocator and no per-window "
            "accepted-comparator regression."
        ),
    }


def _router_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [
        row
        for label in framework.WINDOWS
        for row in rows_by_window.get(label, [])
        if row.get("state_router_applied")
    ]
    concentration = _positive_concentration(rows)
    return {
        "trade_count": len(rows),
        "windows_with_trades": [
            label
            for label in framework.WINDOWS
            if any(row.get("state_router_applied") for row in rows_by_window.get(label, []))
        ],
        "pnl": round(sum(_float(row.get("pnl")) for row in rows), 2),
        **concentration,
    }


def _displacement_summary(
    *,
    control: list[dict[str, Any]],
    routed: list[dict[str, Any]],
) -> dict[str, Any]:
    control_by_date = {str(row.get("signal_date") or "")[:10]: row for row in control}
    routed_by_date = {str(row.get("signal_date") or "")[:10]: row for row in routed}
    changed = []
    for date_value, routed_row in sorted(routed_by_date.items()):
        control_row = control_by_date.get(date_value)
        if not control_row:
            continue
        if (
            str(control_row.get("ticker") or "").upper(),
            str(control_row.get("source_family") or ""),
        ) == (
            str(routed_row.get("ticker") or "").upper(),
            str(routed_row.get("source_family") or ""),
        ):
            continue
        changed.append(
            {
                "signal_date": date_value,
                "routed_ticker": str(routed_row.get("ticker") or "").upper(),
                "routed_source": str(routed_row.get("source_family") or ""),
                "routed_state": routed_row.get("state_router_combined_state"),
                "routed_pnl": _round(routed_row.get("pnl"), 2),
                "control_ticker": str(control_row.get("ticker") or "").upper(),
                "control_source": str(control_row.get("source_family") or ""),
                "control_pnl": _round(control_row.get("pnl"), 2),
                "replacement_pnl": _round(
                    _float(routed_row.get("pnl")) - _float(control_row.get("pnl")),
                    2,
                ),
            }
        )
    return {
        "changed_selection_count": len(changed),
        "changed_selection_pnl_delta": round(
            sum(_float(row.get("replacement_pnl")) for row in changed),
            2,
        ),
        "changed_rows": changed,
    }


def build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    control_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    control_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    helper_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] industry-stable state router")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = exp008._load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = _candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        calendar_dates = framework.shadow._trading_dates(snapshot)
        dates = [
            day
            for day in calendar_dates
            if str(cfg["start"]) <= day <= str(cfg["end"])
        ]

        control_trades, control_audit = (
            build_accepted_helper_source_priority_allocator_historical_trades(
                ohlcv_by_ticker=snapshot,
                core_entries_by_date=core_entries,
                windows=OrderedDict([(label, cfg)]),
                candidate_universe=candidate_universe,
                sector_entries=window_sector_entries,
                calendar_dates=calendar_dates,
            )
        )
        control_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            control_trades,
        )
        control_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            control_overlay,
        )

        source_trades, source_audit = build_source_trades(
            rows_by_ticker=snapshot,
            dates=dates,
            window_label=label,
            window=cfg,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
            candidate_universe=candidate_universe,
            calendar_dates=calendar_dates,
        )
        state_snapshot = statemod._load_snapshot(cfg["snapshot"])
        routed, filtered, priority_audit = _select_state_router_rows(
            source_rows=source_trades,
            trading_dates=dates,
            state_snapshot=state_snapshot,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, routed)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta_vs_core = framework.overlay_helper._delta(after, before)
        delta_vs_control = _direct_metric_delta(after, control_after)

        before_metrics[label] = before
        control_metrics[label] = control_after
        after_metrics[label] = after
        target_trades_by_window[label] = routed
        control_trades_by_window[label] = control_trades
        source_counts = source_audit["source_trade_counts"]
        selected_counts = priority_audit["selected_source_counts"]
        router_selected = [row for row in routed if row.get("state_router_applied")]
        displacement = _displacement_summary(control=control_trades, routed=routed)
        helper_audit_by_window[label] = {
            "accepted_allocator_control_audit": control_audit,
            "source_audit": source_audit,
            "state_router_priority_audit": priority_audit,
            "filtered_state_router_rows": len(filtered),
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "snapshot_lookback_calendar_days": exp008.SNAPSHOT_LOOKBACK_CALENDAR_DAYS,
            "source": _repo_rel(framework.WAREHOUSE),
            "state_snapshot": cfg["snapshot"],
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta_vs_core,
            "accepted_allocator_control_after": control_after,
            "delta_vs_core": delta_vs_core,
            "delta_vs_accepted_allocator": delta_vs_control,
            "target_trade_count": len(routed),
            "accepted_allocator_control_trade_count": len(control_trades),
            "all_source_trade_count": sum(int(count or 0) for count in source_counts.values()),
            "source_trade_counts": source_counts,
            "raw_source_candidate_counts": source_audit["raw_candidate_counts"],
            "selected_source_counts": selected_counts,
            "accepted_allocator_control_selected_source_counts": control_audit[
                "selected_source_counts_by_window"
            ][label],
            "router_candidate_count": priority_audit["router_candidate_count"],
            "router_selected_count": len(router_selected),
            "router_rejected_count": priority_audit["router_rejected_count"],
            "router_selected_tickers": sorted({row["ticker"] for row in router_selected}),
            "router_selected_pnl": round(sum(_float(row.get("pnl")) for row in router_selected), 2),
            "displacement": displacement,
            "filtered_priority_candidate_count": len(filtered),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "control_overlay_total_pnl": control_overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    control_direct_aggregate = _aggregate_direct_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    router_selected_summary = _router_summary(target_trades_by_window)
    binding_gate4 = _binding_gate4(
        aggregate=aggregate,
        control_direct_aggregate=control_direct_aggregate,
        target_summary=target_summary,
        router_summary=router_selected_summary,
        before_metrics=before_metrics,
        window_rows=window_rows,
    )
    full_stack = _full_stack_blocks(aggregate=aggregate, target_summary=target_summary)
    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    verdict = full_stack_verdict(
        gate4=full_stack["gate4_canonical"],
        live_readiness=live_readiness,
        envelope=EXECUTION_ENVELOPE,
    )
    if not binding_gate4["passed"]:
        verdict = {
            **verdict,
            "verdict": "reject",
            "gate4_passed": False,
            "next_step": (
                "Log the rejected state-router scout; no production/shared "
                "allocator logic is retained."
            ),
        }
    elif verdict["verdict"] != "reject":
        verdict = {
            **verdict,
            "verdict": "positive_replay_lead_not_promoted",
            "gate4_passed": True,
            "next_step": (
                "Implement the identical state router in the shared allocator "
                "helper and daily snapshot before any accepted alpha claim."
            ),
        }

    accepted = False
    status = "rejected" if not binding_gate4["passed"] else "positive_replay_lead_not_promoted"
    interpretation = (
        "The state-router replay failed Gate 4 and is not retained."
        if not binding_gate4["passed"]
        else (
            "The state-router replay passed numeric Gate 4, but remains a "
            "positive replay lead only because no shared daily/backtest helper "
            "was retained in this scout."
        )
    )
    reflection = (
        "The source-state router either displaced stronger accepted allocator "
        "rows or did not add enough direct replacement value after rank-1 to "
        "rank-3 sources kept priority."
        if not binding_gate4["passed"]
        else (
            "The ex-top robust industry-stable state cell translated into "
            "direct allocator replacement value, but the result must cross the "
            "shared helper and daily snapshot parity boundary before it can be "
            "accepted."
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": binding_gate4["decision"],
        "accepted": accepted,
        "accepted_alpha": False,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "regime_router",
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "observed_only_ex_top_ticker_survivor",
        "nearby_prior_experiments": [
            "exp-20260612-027",
            "exp-20260612-018",
            "exp-20260612-020",
            "exp-20260611-005",
        ],
        "prior_trial_count": 3,
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": binding_gate4["passed"],
            "failure_modes_observed": binding_gate4["failed_reasons"],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1.0 if binding_gate4["passed"] else 0.0))
                ** 2,
                6,
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "accepted-helper source-priority allocator overlay and a "
                "replay-only state-router variant"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "state_timing": "prior_trading_day_close_before_next_open_paper_entry",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Build the same accepted allocator source rows, annotate each "
                "row with the exp-20260606-022 market state at prior close, "
                "temporarily route only industry_stable_core_flow rows in "
                "mixed|balanced|normal at effective rank 4, then select top-1/"
                "day with the accepted 12-trading-day same-ticker cooldown."
            ),
        },
        "parameters": {
            "rule_version": ROUTER_RULE_VERSION,
            "accepted_allocator_rule_version": ACCEPTED_ALLOCATOR_RULE_VERSION,
            "accepted_allocator_source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
            "source_priority": SOURCE_PRIORITY,
            "router_source_family": ROUTER_SOURCE_FAMILY,
            "router_cell": ROUTER_CELL,
            "router_effective_rank": ROUTER_EFFECTIVE_RANK,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "daily_entry_slots": 1,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "accepted_allocator_control_metrics": control_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before/control metrics inside this artifact"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "SPY/QQQ OHLCV for prior-close market state",
                "accepted allocator source rows with signal_date/ticker/source_family",
                "industry_stable_core_flow source rows with entry_date and pnl",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": True,
            "minimum_core_survival_rate": _round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
            >= 0.05,
            "note": (
                "Default-off paper allocator only; core signals generated, "
                "survived, entries, exits, and live orders are unchanged."
            ),
        },
        "gate4": binding_gate4,
        "before_metrics": before_metrics,
        "accepted_allocator_control_metrics": control_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window_vs_core": OrderedDict(
                (label, row["delta_vs_core"]) for label, row in window_rows.items()
            ),
            "by_window_vs_accepted_allocator": OrderedDict(
                (label, row["delta_vs_accepted_allocator"])
                for label, row in window_rows.items()
            ),
            "aggregate_vs_core": aggregate,
            "aggregate_vs_accepted_allocator": control_direct_aggregate,
        },
        "window_rows": window_rows,
        "target_trades_by_window": target_trades_by_window,
        "accepted_allocator_control_trades_by_window": control_trades_by_window,
        "target_trade_summary": target_summary,
        "router_selected_summary": router_selected_summary,
        "helper_audit_by_window": helper_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "direct_expected_value_score_delta_vs_accepted_allocator": control_direct_aggregate[
            "expected_value_score_delta_sum"
        ],
        "direct_total_pnl_delta_vs_accepted_allocator": control_direct_aggregate[
            "total_pnl_delta_sum"
        ],
        "full_stack": {
            **full_stack,
            "live_readiness": live_readiness,
            "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
            "verdict": verdict,
        },
        "full_stack_verdict": verdict["verdict"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT_REPLAY_ONLY,
        "accepted_comparators": {
            "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "same_run_accepted_allocator_control": control_direct_aggregate,
        },
        "interpretation": interpretation,
        "rejection_reason": None if binding_gate4["passed"] else "; ".join(binding_gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "forbidden_near_neighbor_retry": (
                "Do not retry by moving this cell to rank 1/2/3, changing the "
                "state bucket, relaxing concentration, changing top-N, hold, "
                "cooldown, notional, or excluding specific tickers on the same "
                "frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs closed forward allocator replacement rows for "
                "industry_stable_core_flow in the mixed|balanced|normal state "
                "or a materially new relation/state field that survives the "
                "same ex-top-ticker screen before Gate 1-4."
            ),
        },
        "next_retry_requires": [
            "closed forward allocator replacement rows",
            "materially new relation/state discriminator",
            "shared helper plus daily parity if a replay lead passes",
        ],
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Core EV | Router EV | dEV vs core | dEV vs accepted | Core PnL | Router PnL | dPnL vs core | dPnL vs accepted | Router selected | Changed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        row = payload["window_rows"][label]
        dcore = row["delta_vs_core"]
        dcontrol = row["delta_vs_accepted_allocator"]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {dcev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${dcpnl:+,.2f} | {router} | {changed} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=dcore.get("expected_value_score", 0.0),
                dcev=dcontrol.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=dcore.get("total_pnl", 0.0),
                dcpnl=dcontrol.get("total_pnl", 0.0),
                router=row["router_selected_count"],
                changed=row["displacement"]["changed_selection_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    direct = payload["delta_metrics"]["aggregate_vs_accepted_allocator"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry Stable State Router",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            f"Full-stack verdict: `{payload['full_stack_verdict']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *_window_table(payload),
            "",
            "- Direct EV delta vs accepted allocator: `{:+.4f}`".format(
                direct["expected_value_score_delta_sum"],
            ),
            "- Direct PnL delta vs accepted allocator: `${:+,.2f}`".format(
                direct["total_pnl_delta_sum"],
            ),
            "- Router-selected trades: `{}` across `{}` windows".format(
                payload["router_selected_summary"]["trade_count"],
                len(payload["router_selected_summary"]["windows_with_trades"]),
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT_REPLAY_ONLY["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate_vs_core"]
    direct = payload["delta_metrics"]["aggregate_vs_accepted_allocator"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "full_stack_verdict": payload["full_stack_verdict"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "direct_expected_value_delta_vs_accepted_allocator": direct[
            "expected_value_score_delta_sum"
        ],
        "direct_pnl_delta_vs_accepted_allocator": direct["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
        "gate4": payload["gate4"],
        "full_stack": {
            "verdict": payload["full_stack"]["verdict"],
            "live_readiness": payload["full_stack"]["live_readiness"],
            "execution_envelope": payload["full_stack"]["execution_envelope"],
            "gate4_strict_materiality_status": payload["full_stack"][
                "gate4_strict_materiality"
            ]["status"],
            "gate4_canonical_status": payload["full_stack"]["gate4_canonical"]["status"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window_vs_core"][
                    label
                ]["expected_value_score"],
                "direct_expected_value_delta_vs_accepted_allocator": payload[
                    "delta_metrics"
                ]["by_window_vs_accepted_allocator"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window_vs_core"][
                    label
                ]["total_pnl"],
                "direct_pnl_delta_vs_accepted_allocator": payload["delta_metrics"][
                    "by_window_vs_accepted_allocator"
                ][label]["total_pnl"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "router_selected_count": payload["window_rows"][label][
                    "router_selected_count"
                ],
                "selected_source_counts": payload["window_rows"][label][
                    "selected_source_counts"
                ],
                "changed_selection_count": payload["window_rows"][label]["displacement"][
                    "changed_selection_count"
                ],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT_REPLAY_ONLY,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
        "related_files": payload["related_files"],
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "direct_expected_value_delta_vs_accepted_allocator": payload[
                    "direct_expected_value_score_delta_vs_accepted_allocator"
                ],
                "direct_total_pnl_delta_vs_accepted_allocator": payload[
                    "direct_total_pnl_delta_vs_accepted_allocator"
                ],
                "accepted": False,
                "calibration": payload["calibration"],
                "production_impact": PRODUCTION_IMPACT_REPLAY_ONLY,
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "direct_expected_value_delta_vs_accepted_allocator": payload[
            "direct_expected_value_score_delta_vs_accepted_allocator"
        ],
        "direct_total_pnl_delta_vs_accepted_allocator": payload[
            "direct_total_pnl_delta_vs_accepted_allocator"
        ],
        "accepted": False,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT_REPLAY_ONLY,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "direct_expected_value_delta_vs_accepted_allocator": payload[
            "direct_expected_value_score_delta_vs_accepted_allocator"
        ],
        "direct_total_pnl_delta_vs_accepted_allocator": payload[
            "direct_total_pnl_delta_vs_accepted_allocator"
        ],
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    file_hashes: dict[str, str] = {}
    for path in paths:
        resolved = path if path.is_absolute() else REPO_ROOT / path
        if resolved.exists():
            file_hashes[_repo_rel(resolved)] = framework._sha256(resolved)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": file_hashes,
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            framework._safe(_build_log_record(payload)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
