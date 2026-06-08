"""exp-20260608-001: fundamental cluster laggard repair candidate pool.

Replay-only alpha search.  Tests one PIT-safe non-OHLCV relation source:
within a strong liquid industry group, restrict laggard repair candidates to
stocks with confirmed positive YoY revenue growth from SEC Companyfacts
(filed-date PIT-safe).  The hypothesis is that a fundamentally strong company
temporarily lagging its industry peers shows stronger catch-up alpha than
average laggards.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Optional

import exp_20260607_014_industry_volume_breadth_laggard_repair as previous

QUANT_DIR = previous.previous.base.framework.REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from fundamental_growth_rs_paper_sleeve import (  # noqa: E402
    CompanyfactsFundamentalIndex,
    load_companyfacts_rows,
)


EXPERIMENT_ID = "exp-20260608-001"
STEM = "fundamental_cluster_laggard_repair"
TRIAL_FAMILY = "fundamental_cluster_laggard_repair_candidate_pool"
TRIAL_VARIANT_ID = "fundamental_cluster_laggard_repair_top1_next_open_10d_v1"
CHANGED_VARIABLE = "peer_relation_source_bucket=fundamental_cluster_laggard_repair_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.previous.base.framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_001_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
SCRIPT_PATH = Path(__file__)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 15

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
GROUP_LOOKBACK_DAYS = 20
RECENT_LOOKBACK_DAYS = 5
TREND_LOOKBACK_DAYS = 60

# Group qualification thresholds (same as accepted industry_relative_laggard_repair, exp-20260607-008)
MIN_INDUSTRY_LIQUID_COUNT = 5
MIN_GROUP_MEDIAN_RET20_EXCESS_SPY = 0.018
MIN_GROUP_RET20_POSITIVE_FRACTION = 0.55
MIN_GROUP_MEDIAN_RET5_EXCESS_SPY = -0.015
MAX_GROUP_MEDIAN_RET5_EXCESS_SPY = 0.060

# Laggard repair thresholds (same as exp-20260607-008)
MIN_INDUSTRY_LAG_20D = 0.055
MAX_INDUSTRY_LAG_20D = 0.220
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.095
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.060
MIN_CANDIDATE_RET5_EXCESS_SPY = -0.010
MAX_CANDIDATE_RET5_EXCESS_SPY = 0.070
MIN_SIGNAL_RETURN = 0.004
MAX_SIGNAL_RETURN = 0.080
MIN_SIGNAL_RELATIVE_VS_SPY = 0.006
MIN_CLOSE_LOCATION = 0.62
MIN_VOLUME_RATIO_20D = 0.75
MAX_VOLUME_RATIO_20D = 2.60
MAX_REALIZED_VOL_20D = 0.080

# Single causal variable: fundamental quality filter
MIN_REVENUE_GROWTH = 0.0   # require YoY revenue growth >= 0 (non-negative)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

FUNDAMENTAL_CONFIG = {
    "gross_margin_duration_min": 60,
    "gross_margin_duration_max": 400,
    "quarterly_duration_min": 60,
    "quarterly_duration_max": 130,
}

PREDICTION = {
    "success_probability": 0.25,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "old_thin_regression",
        "concentration_failed",
        "fundamental_data_sparsity",
    ],
    "confidence_reason": (
        "Industry laggard repair (exp-20260607-008) is an accepted signal. "
        "Adding fundamental quality filtering via Companyfacts revenue growth "
        "is a materially new PIT relation field that could improve candidate "
        "precision. The main risk is thin sample due to only ~48 tickers with "
        "available Companyfacts data."
    ),
    "recorded_at": "2026-06-08T00:00:00Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This experiment changes no production code. A positive result "
        "would require a shared default-off adapter that loads PIT-safe "
        "Companyfacts revenue growth, computes the same group-relative "
        "laggard repair fields, applies the fundamental quality filter, "
        "and uses next-open paper entry with 10-trading-day exit before "
        "any production surface could change."
    ),
}


# Module-level Companyfacts index cache (loaded once per process)
_FUNDAMENTALS_INDEX: Optional[CompanyfactsFundamentalIndex] = None


def _get_fundamentals() -> CompanyfactsFundamentalIndex:
    global _FUNDAMENTALS_INDEX
    if _FUNDAMENTALS_INDEX is None:
        sector_entries = _load_sector_entries()
        rows = load_companyfacts_rows(
            max_filed="2030-01-01",
            tickers=list(sector_entries.keys()),
            non_ohlcv_dir=NON_OHLCV_DIR,
        )
        _FUNDAMENTALS_INDEX = CompanyfactsFundamentalIndex(rows, config=FUNDAMENTAL_CONFIG)
    return _FUNDAMENTALS_INDEX


def _repo_rel(path: Path | str) -> str:
    return previous._repo_rel(path)


def _load_sector_entries() -> dict[str, dict[str, Any]]:
    return previous.previous.base.framework._load_sector_entries()


def _candidate_from_metrics(
    *,
    metrics: dict[str, Any],
    group: dict[str, Any],
    fundamentals: CompanyfactsFundamentalIndex,
) -> dict[str, Any] | None:
    ticker = metrics["ticker"]
    signal_date = metrics["date"]
    industry_lag_20d = group["median_ret20_excess_spy"] - metrics["ret20_excess_spy"]
    candidate_above_group_20d = metrics["ret20_excess_spy"] - group["median_ret20_excess_spy"]

    # Standard laggard repair filters
    if industry_lag_20d < MIN_INDUSTRY_LAG_20D:
        return None
    if industry_lag_20d > MAX_INDUSTRY_LAG_20D:
        return None
    if candidate_above_group_20d > 0.004:
        return None
    if metrics["ret20_excess_spy"] < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if metrics["ret60_excess_spy"] < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if metrics["ret5_excess_spy"] < MIN_CANDIDATE_RET5_EXCESS_SPY:
        return None
    if metrics["ret5_excess_spy"] > MAX_CANDIDATE_RET5_EXCESS_SPY:
        return None
    if metrics["signal_return"] < MIN_SIGNAL_RETURN:
        return None
    if metrics["signal_return"] > MAX_SIGNAL_RETURN:
        return None
    if metrics["signal_relative_vs_spy"] < MIN_SIGNAL_RELATIVE_VS_SPY:
        return None
    if metrics["close_location"] < MIN_CLOSE_LOCATION:
        return None
    if metrics["volume_ratio_20d"] < MIN_VOLUME_RATIO_20D:
        return None
    if metrics["volume_ratio_20d"] > MAX_VOLUME_RATIO_20D:
        return None
    if metrics["realized_vol_20d"] > MAX_REALIZED_VOL_20D:
        return None

    # Single causal variable: fundamental quality filter
    rev_growth = fundamentals.growth(ticker, "revenue", signal_date)
    if not rev_growth.get("available"):
        return None
    yoy_growth = rev_growth.get("yoy_growth")
    if yoy_growth is None or yoy_growth < MIN_REVENUE_GROWTH:
        return None

    score = (
        1.20 * group["median_ret20_excess_spy"]
        + 1.10 * group["ret20_positive_fraction"]
        + 1.00 * metrics["signal_relative_vs_spy"]
        + 0.85 * industry_lag_20d
        + 0.60 * metrics["close_location"]
        + 0.40 * metrics["volume_ratio_20d"]
        + 0.25 * metrics["ret60_excess_spy"]
        + 0.15 * math.log10(max(metrics["adv20"], 1.0) / 1_000_000.0)
        + 0.10 * float(yoy_growth)
        - 0.50 * metrics["realized_vol_20d"]
        - 0.20 * max(metrics["volume_ratio_20d"] - 2.0, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "FUNDAMENTAL_CLUSTER_LAGGARD_REPAIR_PAPER",
        "candidate_score": round(score, 6),
        "candidate_group_key": metrics["group_key"],
        "candidate_industry_lag_20d": round(industry_lag_20d, 6),
        "candidate_ret20_excess_spy": round(metrics["ret20_excess_spy"], 6),
        "candidate_ret5_excess_spy": round(metrics["ret5_excess_spy"], 6),
        "candidate_ret60_excess_spy": round(metrics["ret60_excess_spy"], 6),
        "candidate_signal_day_return": round(metrics["signal_return"], 6),
        "candidate_signal_relative_vs_spy": round(metrics["signal_relative_vs_spy"], 6),
        "candidate_close_location": round(metrics["close_location"], 6),
        "candidate_volume_ratio_20d": round(metrics["volume_ratio_20d"], 6),
        "candidate_realized_vol_20d": round(metrics["realized_vol_20d"], 6),
        "candidate_avg_dollar_volume_20d": round(metrics["adv20"], 2),
        "candidate_revenue_yoy_growth": round(float(yoy_growth), 6),
        "candidate_revenue_filed": rev_growth.get("current_filed"),
        "candidate_revenue_period_end": rev_growth.get("current_period_end"),
        "fundamental_group_context": {
            "group_key": metrics["group_key"],
            "liquid_group_count": group["liquid_group_count"],
            "median_ret20_excess_spy": round(group["median_ret20_excess_spy"], 6),
            "median_ret5_excess_spy": round(group["median_ret5_excess_spy"], 6),
            "ret20_positive_fraction": round(group["ret20_positive_fraction"], 6),
            "median_signal_return": round(group["median_signal_return"], 6),
            "signal_positive_fraction": round(group["signal_positive_fraction"], 6),
            "rule_version": RULE_VERSION,
        },
        "sector": metrics.get("sector"),
        "industry": metrics.get("industry"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": False,
        "uses_companyfacts": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    fundamentals = _get_fundamentals()
    entries_by_date = previous.previous.base.framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: previous.previous.base.framework.shadow._row_index(
            previous.previous.base.framework.shadow._series(snapshot, ticker)
        )
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in previous.previous.base.framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]

    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    context_scan: dict[str, Any] = {
        "scanned_trading_days": len(dates),
        "days_with_qualified_groups": 0,
        "days_with_raw_candidates": 0,
        "days_with_fundamental_candidates": 0,
        "qualified_group_rows": 0,
        "raw_candidate_rows": 0,
        "fundamental_candidate_rows": 0,
        "candidate_filtered_no_data": 0,
        "candidate_filtered_negative_growth": 0,
        "unique_candidate_tickers": 0,
        "rule_version": RULE_VERSION,
    }
    candidate_tickers: set[str] = set()

    for signal_date in dates:
        group_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ticker in sector_entries:
            metrics = previous.previous.base._ticker_day_metrics(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if metrics is not None:
                group_members[metrics["group_key"]].append(metrics)

        # Qualify groups (same thresholds as accepted exp-20260607-008)
        group_summaries: dict[str, dict[str, Any]] = {}
        for group_key, rows in group_members.items():
            if len(rows) < MIN_INDUSTRY_LIQUID_COUNT:
                continue
            ret20_values = [float(row["ret20_excess_spy"]) for row in rows]
            ret5_values = [float(row["ret5_excess_spy"]) for row in rows]
            signal_values = [float(row["signal_return"]) for row in rows]
            signal_rel_values = [float(row["signal_relative_vs_spy"]) for row in rows]
            ret20_positive_fraction = sum(v > 0.0 for v in ret20_values) / len(ret20_values)
            signal_positive_fraction = sum(v > 0.0 for v in signal_values) / len(signal_values)
            group_median_ret20 = median(ret20_values)
            group_median_ret5 = median(ret5_values)
            group_median_signal = median(signal_values)
            group_median_signal_rel = median(signal_rel_values)
            if group_median_ret20 < MIN_GROUP_MEDIAN_RET20_EXCESS_SPY:
                continue
            if ret20_positive_fraction < MIN_GROUP_RET20_POSITIVE_FRACTION:
                continue
            if group_median_ret5 < MIN_GROUP_MEDIAN_RET5_EXCESS_SPY:
                continue
            if group_median_ret5 > MAX_GROUP_MEDIAN_RET5_EXCESS_SPY:
                continue
            group_summaries[group_key] = {
                "liquid_group_count": len(rows),
                "median_ret20_excess_spy": group_median_ret20,
                "median_ret5_excess_spy": group_median_ret5,
                "ret20_positive_fraction": ret20_positive_fraction,
                "median_signal_return": group_median_signal,
                "signal_positive_fraction": signal_positive_fraction,
                "median_signal_relative_vs_spy": group_median_signal_rel,
            }

        if not group_summaries:
            continue
        context_scan["days_with_qualified_groups"] += 1
        context_scan["qualified_group_rows"] += len(group_summaries)

        day_rows: list[dict[str, Any]] = []
        for group_key, rows in group_members.items():
            group = group_summaries.get(group_key)
            if group is None:
                continue
            for metrics in rows:
                # Apply fundamental quality filter
                ticker = metrics["ticker"]
                signal_date_str = metrics["date"]
                rev_growth = fundamentals.growth(ticker, "revenue", signal_date_str)
                if not rev_growth.get("available"):
                    context_scan["candidate_filtered_no_data"] += 1
                    continue
                yoy = rev_growth.get("yoy_growth")
                if yoy is None or yoy < MIN_REVENUE_GROWTH:
                    context_scan["candidate_filtered_negative_growth"] += 1
                    continue
                row = _candidate_from_metrics(
                    metrics=metrics,
                    group=group,
                    fundamentals=fundamentals,
                )
                if row is None:
                    continue
                ab_entries = entries_by_date.get(signal_date, [])
                row["same_day_ab_entry_count"] = len(ab_entries)
                row["same_day_ab_overlap"] = bool(ab_entries)
                row["same_ticker_ab_overlap"] = any(
                    trade.get("ticker") == row["ticker"] for trade in ab_entries
                )
                day_rows.append(row)
                candidate_tickers.add(str(row["ticker"]))

        context_scan["raw_candidate_rows"] += len(day_rows)
        if day_rows:
            context_scan["days_with_raw_candidates"] += 1

        if not day_rows:
            continue

        day_rows.sort(
            key=lambda r: (
                -float(r["candidate_score"]),
                -float(r["candidate_signal_relative_vs_spy"]),
                -float(r["candidate_industry_lag_20d"]),
                -float(r["candidate_avg_dollar_volume_20d"]),
                r["ticker"],
            )
        )
        candidates.extend(day_rows)
        context_scan["fundamental_candidate_rows"] += len(day_rows)
        context_scan["days_with_fundamental_candidates"] += 1
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "qualified_group_count": len(group_summaries),
                "top_candidate": top["ticker"],
                "top_group_key": top["candidate_group_key"],
                "top_score": top["candidate_score"],
                "top_industry_lag_20d": top["candidate_industry_lag_20d"],
                "top_signal_relative_vs_spy": top["candidate_signal_relative_vs_spy"],
                "top_revenue_yoy_growth": top["candidate_revenue_yoy_growth"],
            }
        )

    candidates.sort(
        key=lambda r: (
            r["date"],
            -float(r["candidate_score"]),
            -float(r["candidate_signal_relative_vs_spy"]),
            -float(r["candidate_industry_lag_20d"]),
            -float(r["candidate_avg_dollar_volume_20d"]),
            r["ticker"],
        )
    )
    context_scan.update(
        {
            "unique_candidate_tickers": len(candidate_tickers),
            "group_lookback_days": GROUP_LOOKBACK_DAYS,
            "recent_lookback_days": RECENT_LOOKBACK_DAYS,
            "trend_lookback_days": TREND_LOOKBACK_DAYS,
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "max_group_median_ret5_excess_spy": MAX_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_industry_lag_20d": MIN_INDUSTRY_LAG_20D,
            "max_industry_lag_20d": MAX_INDUSTRY_LAG_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "max_candidate_ret5_excess_spy": MAX_CANDIDATE_RET5_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "min_revenue_growth": MIN_REVENUE_GROWTH,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    return candidates, day_contexts, context_scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = previous.previous.base.BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_fundamental_cluster_laggard_repair"
        if gate["passed"]
        else "rejected_fundamental_cluster_laggard_repair_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = previous.previous.base.BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Within strong liquid industry groups, stocks with confirmed "
                "positive YoY revenue growth from SEC Companyfacts "
                "(filed-date PIT-safe) that are temporarily lagging the group "
                "show stronger subsequent catch-up alpha than average "
                "group laggards."
            ),
            "change_type": "default_off_paper_allocation",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_companyfacts_relation_alpha",
            "new_evidence_type": "pit_safe_companyfacts_revenue_growth_filter",
            "nearby_prior_experiments": [
                "exp-20260607-007",
                "exp-20260607-008",
                "exp-20260607-009",
                "exp-20260607-010",
                "exp-20260607-014",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "decision": gate4["decision"],
            "status": (
                "positive_replay_lead_not_promoted"
                if gate4["passed"]
                else "rejected"
            ),
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The fundamental cluster laggard repair source cleared Gate 4 "
                "as a replay-only lead, suggesting fundamental quality "
                "filtering improves industry laggard repair precision."
                if gate4["passed"]
                else (
                    "The fundamental cluster laggard repair source did not "
                    "clear Gate 4. The most likely cause is thin sample "
                    "from limited Companyfacts coverage (~48 tickers). "
                    "Do not retry by sweeping growth threshold, hold days, "
                    "laggard lag bounds, or notional on these frozen windows."
                )
            ),
            "negative_reflection": (
                "If rejected, the primary cause is expected to be thin_sample "
                "due to limited Companyfacts coverage. The hypothesis itself "
                "may still be valid; retesting requires expanded Companyfacts "
                "universe (more SEC tickers loaded) rather than threshold tuning."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "Pending run result. Replace after three-window replay."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping group thresholds, lag bounds, "
                    "signal-day return, close-location, volume, volatility, "
                    "revenue growth threshold, hold days, top-N, cooldown, "
                    "or paper notional on these frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires either expanded Companyfacts universe "
                    "(more than ~48 tickers with revenue data) or a different "
                    "PIT-safe non-OHLCV field (EPS growth, gross margin, "
                    "filing timeliness)."
                ),
            },
            "next_evidence_needed": (
                "Expanded Companyfacts universe or a different PIT-safe "
                "fundamental field is required before retrying near-neighbor "
                "fundamental quality filter variants."
            ),
            "related_files": [
                _repo_rel(SCRIPT_PATH),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    if gate4["passed"]:
        payload["post_run_reflection"]["why_result_happened"] = (
            "The source produced positive replacement value in all three "
            "canonical windows without breaching drawdown, survival, or "
            "concentration guardrails. That suggests Companyfacts revenue "
            "growth is a materially useful PIT filter for industry laggard "
            "repair candidate selection."
        )
    else:
        payload["post_run_reflection"]["why_result_happened"] = (
            "The candidate source failed to add aggregate replacement value, "
            "regressed a canonical window, or breached drawdown/concentration "
            "or thin-sample gates. With only ~48 tickers having Companyfacts "
            "data, thin_sample is the most likely root cause."
        )

    payload.setdefault("parameters", {}).clear()
    payload["parameters"].update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "group_lookback_days": GROUP_LOOKBACK_DAYS,
            "recent_lookback_days": RECENT_LOOKBACK_DAYS,
            "trend_lookback_days": TREND_LOOKBACK_DAYS,
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "max_group_median_ret5_excess_spy": MAX_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_industry_lag_20d": MIN_INDUSTRY_LAG_20D,
            "max_industry_lag_20d": MAX_INDUSTRY_LAG_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "max_candidate_ret5_excess_spy": MAX_CANDIDATE_RET5_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "min_revenue_growth": MIN_REVENUE_GROWTH,
            "single_causal_variable": CHANGED_VARIABLE,
            "companyfacts_source": "sec_companyfacts_selected_*.jsonl",
            "companyfacts_pit_method": "filed_date_lte_signal_date",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses close-of-day OHLCV plus prior close history for 20-day "
        "industry relative strength, 5-day extension, signal-day repair, "
        "60-day trend guard, ADV, volume ratio, and realized volatility. "
        "PLUS PIT-safe SEC Companyfacts revenue growth (filed date <= signal "
        "date). Paper entry is next available open; exit is 10 trading days "
        "after signal with ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: adding SEC Companyfacts positive revenue "
            "growth as a quality filter on industry laggard repair candidates "
            "should improve hit rate by eliminating fundamental deterioration."
        ),
        "2_history_check": {
            "exp-20260607-007/008": (
                "Industry laggard repair accepted; this adds a PIT-safe "
                "fundamental filter (positive Companyfacts revenue growth) "
                "on top, which is a materially new relation field per playbook."
            ),
            "exp-20260607-009/010/014": (
                "Pullback leader, breadth repair, volume breadth variants "
                "rejected; this is not a retune but a different PIT-safe "
                "data source (SEC Companyfacts) applied to the accepted base."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no regression window, target sample "
            ">=20 across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
            "and concentration guard passes."
        ),
        "5_reproducibility": (
            "python3 -B quant/experiments/"
            "exp_20260608_001_fundamental_cluster_laggard_repair.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The fundamental cluster "
        "laggard repair source is additive default-off paper; core signals "
        "generated/survived are unchanged from baseline."
    )
    payload["context_alias"] = "fundamental_cluster_laggard_repair_contexts"
    payload["fundamental_cluster_context_samples_by_window"] = {
        label: rows[:20]
        for label, rows in payload["pressure_contexts_by_window"].items()
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in previous.previous.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Fundamental Cluster Laggard Repair",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Results",
            "",
            "\n".join(rows),
            "",
            f"Aggregate EV delta: {aggregate.get('expected_value_score_delta_sum', 0.0):+.4f}",
            f"Aggregate PnL delta: ${aggregate.get('total_pnl_delta_sum', 0.0):+,.2f}",
            f"Gate 4 passed: {payload['gate4']['passed']}",
            "",
            "## Fundamental Coverage",
            "",
            "Companyfacts universe: ~48 tickers with SEC revenue data.",
            "Coverage note: thin_sample is the primary risk.",
        ]
    )


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_companyfacts_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
                "expected_value_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"][
                    "by_window"
                ][label]["total_pnl"],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(
                    payload["target_trades_by_window"][label]
                ),
            }
            for label in previous.previous.base.framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    _fw = previous.previous.base.framework
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "script": _repo_rel(SCRIPT_PATH),
        "artifact": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
        "sha256": {
            _repo_rel(SCRIPT_PATH): _fw._sha256(SCRIPT_PATH),
            _repo_rel(OUT_JSON): _fw._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _fw._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _fw._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _fw._sha256(CARD_MD),
        },
    }
    _fw._write_json(MANIFEST_JSON, manifest)


def _patch() -> None:
    previous.OUT_DIR = OUT_DIR
    previous.OUT_JSON = OUT_JSON
    previous.LOG_JSON = LOG_JSON
    previous.TICKET_JSON = TICKET_JSON
    previous.CARD_MD = CARD_MD
    previous.MANIFEST_JSON = MANIFEST_JSON
    previous.EXPERIMENT_LOG = EXPERIMENT_LOG
    previous.REGISTRY_JSON = REGISTRY_JSON
    previous.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    previous.HOLD_DAYS = HOLD_DAYS
    previous.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    previous.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    previous.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    previous.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    previous.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    previous.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    previous.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    previous.PREDICTION = PREDICTION
    previous.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    previous._candidate_from_metrics = _candidate_from_metrics
    previous._candidate_rows_for_window = _candidate_rows_for_window
    previous._gate4 = _gate4
    previous._build_payload = _build_payload
    previous._build_card = _build_card
    previous._build_log_record = _build_log_record
    previous._write_manifest = _write_manifest


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _patch()
    previous.main()


if __name__ == "__main__":
    main()
