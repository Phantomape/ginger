"""exp-20260610-004: accepted helper source-priority allocation replay.

Replay-only alpha search. It tests one fixed capital-allocation hypothesis:
when multiple accepted default-off stock helper families emit paper candidates
on the same signal date, keep only one candidate using an ex-ante helper
priority order instead of stacking overlapping default-off risk.

This does not change production orders, shared helpers, daily snapshots, core
ranking, sizing, exits, LLM/news behavior, watchlists, or run.py. No JavaScript
is used.
"""

from __future__ import annotations

import math
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
from data_layer import get_universe
from industry_relative_laggard_repair_paper_sleeve import (
    build_industry_relative_laggard_repair_historical_trades,
)
from industry_stable_core_flow_paper_sleeve import (
    build_industry_stable_core_flow_historical_trades,
)
from narrow_range_compression_breakout_paper_sleeve import (
    build_narrow_range_compression_breakout_historical_trades,
)
from rolling_corr_peer_shock_paper_sleeve import (
    build_rolling_corr_peer_shock_historical_trades,
)
from turn_of_month_liquid_leadership_paper_sleeve import (
    build_turn_of_month_liquid_leadership_historical_trades,
)
from volatility_relief_stock_leadership_paper_sleeve import (
    build_volatility_relief_stock_leadership_historical_trades,
)


EXPERIMENT_ID = "exp-20260610-004"
STEM = "accepted_helper_source_priority_allocation"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = "accepted_helper_source_priority_top1_allocation_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
RULE_VERSION = TRIAL_VARIANT_ID
OWNER = "alpha-search-automation"

REPO_ROOT = framework.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_004_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 12
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

SOURCE_PRIORITY = OrderedDict(
    [
        (
            "volatility_relief",
            {
                "rank": 1,
                "description": "accepted volatility relief stock leadership",
                "accepted_experiment": "exp-20260607-019",
                "accepted_ev_delta_sum": 0.5732,
                "accepted_pnl_delta_sum": 11934.79,
            },
        ),
        (
            "rolling_peer_shock",
            {
                "rank": 2,
                "description": "accepted rolling correlation peer shock",
                "accepted_experiment": "exp-20260606-025",
                "accepted_ev_delta_sum": 0.3845,
                "accepted_pnl_delta_sum": 6107.66,
            },
        ),
        (
            "turn_of_month",
            {
                "rank": 3,
                "description": "accepted turn-of-month liquid leadership",
                "accepted_experiment": "exp-20260609-027",
                "accepted_ev_delta_sum": 0.2774,
                "accepted_pnl_delta_sum": 5287.69,
            },
        ),
        (
            "industry_laggard_repair",
            {
                "rank": 4,
                "description": "accepted industry relative laggard repair",
                "accepted_experiment": "exp-20260607-008",
                "accepted_ev_delta_sum": 0.2763,
                "accepted_pnl_delta_sum": 4875.91,
            },
        ),
        (
            "compression",
            {
                "rank": 5,
                "description": "accepted narrow range compression breakout",
                "accepted_experiment": "exp-20260608-013",
                "accepted_ev_delta_sum": 0.1608,
                "accepted_pnl_delta_sum": 2248.98,
            },
        ),
        (
            "industry_stable_core_flow",
            {
                "rank": 6,
                "description": "accepted industry stable core-flow",
                "accepted_experiment": "exp-20260608-008",
                "accepted_ev_delta_sum": 0.1459,
                "accepted_pnl_delta_sum": 3523.28,
            },
        ),
    ]
)

STRONGEST_INCLUDED_COMPARATOR = SOURCE_PRIORITY["volatility_relief"]

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "source_priority_discards_useful_lower_priority_rows",
        "strongest_single_helper_comparator_not_beaten",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Accepted default-off stock helpers are individually positive and "
        "production-visible, but recent consensus/additional-source experiments "
        "show overlap often relabels noise. A fixed top1 allocator tests "
        "whether conflict management adds replacement value without adding a "
        "new noisy ticker source."
    ),
    "recorded_at": "2026-06-10T03:13:33+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
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
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "This runner changes no production code. A positive result would still "
        "require a shared default-off allocator/helper that consumes the exact "
        "same helper source rows in historical replay and daily snapshot "
        "generation before any report, paper ledger, ranking, sizing, watchlist, "
        "or order surface could change."
    ),
}


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _source_score(trade: dict[str, Any]) -> float:
    for key in (
        "candidate_score",
        "paper_candidate_score",
        "peer_shock_score",
        "compression_score",
        "source_score",
        "score",
        "rank_score",
    ):
        if trade.get(key) is not None:
            return _float(trade.get(key))
    return 0.0


def _normalise_trade(trade: dict[str, Any], source_family: str) -> dict[str, Any]:
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    ticker = str(trade.get("ticker") or "").upper()
    source_meta = SOURCE_PRIORITY[source_family]
    score = _source_score(trade)
    return {
        **trade,
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source_family": source_family,
        "source_priority_rank": source_meta["rank"],
        "source_priority_accepted_experiment": source_meta["accepted_experiment"],
        "source_priority_score": _round(score, 6),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "uses_llm": False,
        "uses_free_ohlcv_only": True,
    }


def _build_source_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    cfg: dict[str, str],
    label: str,
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_trades: list[dict[str, Any]] = []
    source_trade_counts: OrderedDict[str, int] = OrderedDict()
    raw_candidate_counts: OrderedDict[str, int | None] = OrderedDict()
    source_audits: OrderedDict[str, Any] = OrderedDict()

    volatility = build_volatility_relief_stock_leadership_historical_trades(
        ohlcv_by_ticker=snapshot,
        dates=dates,
        candidate_universe=sector_entries,
        core_entries_by_date=core_entries_by_date,
    )
    volatility_trades = [
        _normalise_trade(row, "volatility_relief") for row in volatility["trades"]
    ]
    source_trades.extend(volatility_trades)
    source_trade_counts["volatility_relief"] = len(volatility_trades)
    raw_candidate_counts["volatility_relief"] = len(volatility.get("candidates") or [])
    source_audits["volatility_relief"] = {
        "rule_version": volatility.get("rule_version"),
        "source_rule_version": volatility.get("source_rule_version"),
        "context_scan": volatility.get("context_scan"),
    }

    rolling_trades, rolling_audit = build_rolling_corr_peer_shock_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries_by_date,
        windows=OrderedDict([(label, cfg)]),
        candidate_universe=sector_entries,
        sector_entries=sector_entries,
    )
    rolling_normalised = [
        _normalise_trade(row, "rolling_peer_shock") for row in rolling_trades
    ]
    source_trades.extend(rolling_normalised)
    source_trade_counts["rolling_peer_shock"] = len(rolling_normalised)
    raw_candidate_counts["rolling_peer_shock"] = rolling_audit.get(
        "raw_candidate_count_by_window", {}
    ).get(label)
    source_audits["rolling_peer_shock"] = {
        "rule_version": rolling_audit.get("rule_version"),
        "source_rule_version": rolling_audit.get("source_rule_version"),
        "scan": rolling_audit.get("scan_by_window", {}).get(label),
    }

    turn_trades, turn_audit = build_turn_of_month_liquid_leadership_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries_by_date,
        windows=OrderedDict([(label, cfg)]),
        candidate_universe=sector_entries,
        calendar_dates=framework.shadow._trading_dates(snapshot),
    )
    turn_normalised = [_normalise_trade(row, "turn_of_month") for row in turn_trades]
    source_trades.extend(turn_normalised)
    source_trade_counts["turn_of_month"] = len(turn_normalised)
    raw_candidate_counts["turn_of_month"] = turn_audit.get(
        "raw_candidate_count_by_window", {}
    ).get(label)
    source_audits["turn_of_month"] = {
        "rule_version": turn_audit.get("rule_version"),
        "source_rule_version": turn_audit.get("source_rule_version"),
        "scan": turn_audit.get("scan_by_window", {}).get(label),
    }

    builders = [
        (
            "industry_laggard_repair",
            build_industry_relative_laggard_repair_historical_trades,
        ),
        ("compression", build_narrow_range_compression_breakout_historical_trades),
        ("industry_stable_core_flow", build_industry_stable_core_flow_historical_trades),
    ]
    for source_family, builder in builders:
        trades, audit = builder(
            ohlcv_by_ticker=snapshot,
            core_entries_by_date=core_entries_by_date,
            windows=OrderedDict([(label, cfg)]),
            candidate_universe=sector_entries,
            sector_entries=sector_entries,
        )
        normalised = [_normalise_trade(row, source_family) for row in trades]
        source_trades.extend(normalised)
        source_trade_counts[source_family] = len(normalised)
        raw_candidate_counts[source_family] = audit.get(
            "raw_candidate_count_by_window", {}
        ).get(label)
        source_audits[source_family] = {
            "rule_version": audit.get("rule_version"),
            "source_rule_version": audit.get("source_rule_version"),
            "scan": audit.get("scan_by_window", {}).get(label),
        }

    return source_trades, {
        "source_priority": SOURCE_PRIORITY,
        "source_trade_counts": source_trade_counts,
        "raw_candidate_counts": raw_candidate_counts,
        "source_audits": source_audits,
        "excluded_helpers": {
            "lagged_consensus": (
                "Different source-family interface and already has accepted "
                "source timing; not mixed into this stock-helper allocator."
            ),
            "low_deployment_etf": (
                "ETF cash-substitute sleeve, not a single-stock candidate-pool helper."
            ),
            "macro_relief": (
                "No uniform historical helper API matching these stock helpers."
            ),
            "revision_low_extension": (
                "Uses earnings snapshot side data with shorter coverage; excluded "
                "to avoid data-limited replay mismatch."
            ),
        },
    }


def _select_priority_trades(
    *,
    source_trades: list[dict[str, Any]],
    trading_dates: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = [
        row
        for row in source_trades
        if str(row.get("signal_date") or "")[:10] and str(row.get("ticker") or "").upper()
    ]
    candidates.sort(
        key=lambda row: (
            str(row.get("signal_date") or "")[:10],
            int(row.get("source_priority_rank") or 999),
            -_float(row.get("source_priority_score")),
            str(row.get("ticker") or ""),
        )
    )

    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    used_date_counts: Counter[str] = Counter()
    next_allowed_pos_by_ticker: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("signal_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_position.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_source_priority_limit"})
            continue
        if pos < next_allowed_pos_by_ticker.get(ticker, -1):
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        selected.append(
            {
                **row,
                "source": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
                "rule_version": RULE_VERSION,
                "candidate_score": _round(
                    1000.0 / max(1, int(row.get("source_priority_rank") or 999))
                    + _float(row.get("source_priority_score")),
                    6,
                ),
                "paper_notional_usd": BASE_NOTIONAL_USD,
            }
        )
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS

    source_counts = Counter(str(row.get("source_family") or "unknown") for row in candidates)
    selected_counts = Counter(str(row.get("source_family") or "unknown") for row in selected)
    audit = {
        "source_candidate_count": len(candidates),
        "selected_priority_trade_count": len(selected),
        "filtered_priority_candidate_count": len(filtered),
        "source_candidate_counts": source_counts,
        "selected_source_counts": selected_counts,
        "daily_top1_limit": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
    }
    return selected, filtered, audit


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    aggregate_ev = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    aggregate_pnl = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if aggregate_ev <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if aggregate_pnl <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if aggregate_ev <= float(STRONGEST_INCLUDED_COMPARATOR["accepted_ev_delta_sum"]):
        failed.append("strongest_single_helper_ev_comparator_not_beaten")
    if aggregate_pnl <= float(STRONGEST_INCLUDED_COMPARATOR["accepted_pnl_delta_sum"]):
        failed.append("strongest_single_helper_pnl_comparator_not_beaten")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_accepted_helper_source_priority_allocation"
            if passed
            else "rejected_accepted_helper_source_priority_allocation"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "strongest_included_comparator": STRONGEST_INCLUDED_COMPARATOR,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_candidates_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and accepted-helper source-priority replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        dates = [
            day
            for day in framework.shadow._trading_dates(snapshot)
            if str(cfg["start"]) <= day <= str(cfg["end"])
        ]
        core_entries = framework.shadow._baseline_entries(before_result)
        source_trades, source_audit = _build_source_trades(
            snapshot=snapshot,
            dates=dates,
            cfg=cfg,
            label=label,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
        )
        selected, filtered, priority_audit = _select_priority_trades(
            source_trades=source_trades,
            trading_dates=dates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected
        filtered_candidates_by_window[label] = filtered[:300]
        source_audit_by_window[label] = source_audit
        priority_audit_by_window[label] = priority_audit
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected),
            "all_source_trade_count": len(source_trades),
            "source_trade_counts": source_audit["source_trade_counts"],
            "raw_source_candidate_counts": source_audit["raw_candidate_counts"],
            "selected_source_counts": priority_audit["selected_source_counts"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    status = "accepted" if gate4["passed"] else "rejected"
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    if gate4["passed"]:
        interpretation = (
            "The fixed accepted-helper source-priority top1 allocator cleared "
            "the replay gate, but remains unpromoted until implemented as a "
            "shared default-off helper with daily snapshot parity."
        )
        reflection = (
            "The source-priority allocator added enough replacement value over "
            "the strongest included helper to justify a shared-helper parity "
            "follow-up. Its value likely came from avoiding same-day overlapping "
            "helper exposure while still harvesting the highest-evidence accepted "
            "source on each signal date."
        )
    else:
        interpretation = (
            "The fixed accepted-helper source-priority top1 allocator failed "
            "Gate 4. Treat it as evidence that accepted helper stacking cannot "
            "be improved by this simple static conflict policy."
        )
        reflection = (
            "The allocator used many accepted helper rows, but a fixed priority "
            "stack can discard lower-priority candidates that were actually "
            "independent, while still inheriting weak windows from the top "
            "source. Do not retry by merely changing priority order, top-N, "
            "notional, hold days, or cooldown on the same frozen windows."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": (
            "Accepted default-off stock helpers may produce better replacement "
            "value when same-day helper conflicts are resolved by a fixed "
            "ex-ante source-priority top1 allocator instead of allowing "
            "overlapping helper risk."
        ),
        "change_type": "default_off_paper_candidate_priority",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "accepted_helper_conflict_allocation",
        "nearby_prior_experiments": [
            "exp-20260604-009",
            "exp-20260606-025",
            "exp-20260607-008",
            "exp-20260607-019",
            "exp-20260608-008",
            "exp-20260608-009",
            "exp-20260608-013",
            "exp-20260609-017",
            "exp-20260609-023",
            "exp-20260609-027",
        ],
        "prior_trial_count": 3,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only accepted helper source-priority top1 paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Each included helper already uses signal-date OHLCV and "
                "default-off next-open paper semantics. This runner adds only "
                "fixed source priority, one selected paper trade per signal "
                "date, and a 12-trading-day same-ticker cooldown."
            ),
        },
        "parameters": {
            "source_priority": SOURCE_PRIORITY,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "strongest_included_comparator": STRONGEST_INCLUDED_COMPARATOR,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "capital-allocation/candidate-priority alpha: accepted helper "
                "outputs may be better used as competing default-off risk slots "
                "than as independent same-day additive exposures."
            ),
            "2_history_check": {
                "exp-20260608-009": (
                    "Accepted relation-helper same-industry consensus was "
                    "sparse/rejected; this test does not require cross-helper "
                    "agreement and instead tests top1 conflict allocation."
                ),
                "exp-20260609-017_and_023": (
                    "Lagged-consensus source-family additions were rejected; "
                    "this test avoids adding a source family and avoids LLM "
                    "soft ranking."
                ),
                "accepted_single_helper_comparators": (
                    "Volatility relief, rolling peer shock, industry laggard "
                    "repair, industry stable core-flow, compression, and "
                    "turn-of-month helpers are used as fixed sensors; their "
                    "thresholds are not retuned."
                ),
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use the same three canonical windows. Aggregate EV/PnL must "
                "be positive; no EV/PnL regression window; at least 20 trades "
                "across all 3 windows; survival >=5%; drawdown drift <=0.5pp; "
                "concentration guard passes; and aggregate EV/PnL must beat "
                "the strongest included accepted single-helper comparator."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260610_004_accepted_helper_source_priority_allocation.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "data/reference/broad_market_sector_map.json sector/industry/status",
                "accepted helper source rows with signal_date/ticker/source_family",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter or live candidate ranking changed. The source "
                "is replay-only/default-off paper, so core signals generated "
                "and survived are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "filtered_priority_candidates_by_window": filtered_candidates_by_window,
        "source_audit_by_window": source_audit_by_window,
        "priority_audit_by_window": priority_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "accepted_comparators": {
            "strongest_included_single_helper": STRONGEST_INCLUDED_COMPARATOR,
            "included_source_priority": SOURCE_PRIORITY,
        },
        "interpretation": interpretation,
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "forbidden_near_neighbor_retry": (
                "Do not rerun this static source-priority allocator by only "
                "changing helper order, top-N, notional, hold days, or cooldown "
                "on the same frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs forward helper displacement evidence, a shared "
                "daily allocator surface, or a materially new production-visible "
                "source that changes same-day conflict information."
            ),
        },
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Source trades | Trades | Top source |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        selected_counts = row["selected_source_counts"]
        top_source = "none"
        if selected_counts:
            top_source = sorted(selected_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {source} | {trades} | {top_source} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                source=row["all_source_trade_count"],
                trades=row["target_trade_count"],
                top_source=top_source,
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["gate4"]["strongest_included_comparator"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted Helper Source-Priority Allocation",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Strongest included comparator: `{}` EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                comparator["accepted_experiment"],
                comparator["accepted_ev_delta_sum"],
                comparator["accepted_pnl_delta_sum"],
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Production Impact",
            "",
            "Replay-only/default-off paper. No shared helper, daily run adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": False,
        "production_accepted": False,
        "shared_adapter_required": True,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "source_trade_count": payload["window_rows"][label]["all_source_trade_count"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "selected_source_counts": payload["window_rows"][label][
                    "selected_source_counts"
                ],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": False,
        "production_accepted": False,
        "shared_adapter_required": True,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
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
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
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

    ticket = {}
    if TICKET_JSON.exists():
        ticket = framework.json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "result": result,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        }
    )
    framework._write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)
    print(
        "completed {experiment_id}: {decision} | dEV={ev:+.4f} | dPnL=${pnl:+,.2f}".format(
            experiment_id=EXPERIMENT_ID,
            decision=payload["decision"],
            ev=payload["delta_metrics"]["aggregate"]["expected_value_score_delta_sum"],
            pnl=payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
        )
    )


if __name__ == "__main__":
    main()
