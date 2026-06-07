"""exp-20260607-010: industry breadth-repair second-line candidate pool.

Replay-only alpha search. It tests one free-OHLCV relation source:
when a strong liquid industry group shows same-day breadth repair without
being 5-day overextended, select one liquid second-line participant that joins
the repair but is not already the group leader. Paper entry is next-open with
a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260607_009_industry_pullback_leader_resilience as base


EXPERIMENT_ID = "exp-20260607-010"
STEM = "industry_breadth_repair_second_line"
TRIAL_FAMILY = "industry_breadth_repair_second_line_candidate_pool"
TRIAL_VARIANT_ID = "industry_breadth_repair_second_line_top1_next_open_10d_v1"
CHANGED_VARIABLE = "industry_breadth_repair_second_line_participation_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260607_010_industry_breadth_repair_second_line.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
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

MIN_INDUSTRY_LIQUID_COUNT = 6
MIN_GROUP_MEDIAN_RET20_EXCESS_SPY = 0.012
MIN_GROUP_RET20_POSITIVE_FRACTION = 0.55
MIN_GROUP_SIGNAL_MEDIAN_RETURN = 0.0035
MIN_GROUP_SIGNAL_POSITIVE_FRACTION = 0.62
MIN_GROUP_SIGNAL_RELATIVE_VS_SPY = 0.0025
MIN_GROUP_MEDIAN_RET5_EXCESS_SPY = -0.025
MAX_GROUP_MEDIAN_RET5_EXCESS_SPY = 0.025

MIN_SECOND_LINE_LAG_20D = 0.010
MAX_SECOND_LINE_LAG_20D = 0.125
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.045
MAX_CANDIDATE_RET20_EXCESS_SPY_ABOVE_GROUP = 0.010
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.045
MIN_CANDIDATE_RET5_EXCESS_SPY = -0.006
MAX_CANDIDATE_RET5_EXCESS_SPY = 0.065
MIN_SIGNAL_RETURN = 0.005
MAX_SIGNAL_RETURN = 0.075
MIN_SIGNAL_RELATIVE_VS_SPY = 0.007
MIN_CLOSE_LOCATION = 0.62
MIN_VOLUME_RATIO_20D = 0.80
MAX_VOLUME_RATIO_20D = 2.70
MAX_REALIZED_VOL_20D = 0.080

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift",
        "breadth_repair_chase",
        "ohlcv_momentum_relabeling",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Free OHLCV relation sources worked when the relation was explicit, "
        "but recent short reversal and industry pullback leader variants "
        "failed. This tests breadth repair by second-line participants, a "
        "distinct relation from laggard repair and leader exhaustion."
    ),
    "recorded_at": "2026-06-07T08:04:08Z",
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
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same broad "
        "warehouse liquid sector-known universe, PIT industry grouping, group "
        "same-day breadth repair context, second-line participation fields, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, and concentration controls in "
        "both replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _candidate_from_metrics(
    *,
    metrics: dict[str, Any],
    group: dict[str, Any],
) -> dict[str, Any] | None:
    second_line_lag_20d = group["median_ret20_excess_spy"] - metrics["ret20_excess_spy"]
    candidate_above_group_20d = metrics["ret20_excess_spy"] - group["median_ret20_excess_spy"]
    participation_vs_group_signal = metrics["signal_return"] - group["median_signal_return"]

    if second_line_lag_20d < MIN_SECOND_LINE_LAG_20D:
        return None
    if second_line_lag_20d > MAX_SECOND_LINE_LAG_20D:
        return None
    if candidate_above_group_20d > MAX_CANDIDATE_RET20_EXCESS_SPY_ABOVE_GROUP:
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

    score = (
        1.05 * group["median_ret20_excess_spy"]
        + 1.25 * group["signal_positive_fraction"]
        + 1.45 * metrics["signal_relative_vs_spy"]
        + 0.85 * participation_vs_group_signal
        + 0.70 * second_line_lag_20d
        + 0.55 * metrics["close_location"]
        + 0.20 * metrics["ret60_excess_spy"]
        + 0.04 * math.log10(max(metrics["adv20"], 1.0) / 1_000_000.0)
        - 0.65 * metrics["realized_vol_20d"]
        - 0.06 * max(metrics["volume_ratio_20d"] - 1.8, 0.0)
    )
    return {
        "date": metrics["date"],
        "ticker": metrics["ticker"],
        "source": "INDUSTRY_BREADTH_REPAIR_SECOND_LINE_PAPER",
        "candidate_score": round(score, 6),
        "candidate_group_key": metrics["group_key"],
        "candidate_second_line_lag_20d": round(second_line_lag_20d, 6),
        "candidate_participation_vs_group_signal": round(
            participation_vs_group_signal,
            6,
        ),
        "candidate_ret20_excess_spy": round(metrics["ret20_excess_spy"], 6),
        "candidate_ret5_excess_spy": round(metrics["ret5_excess_spy"], 6),
        "candidate_ret60_excess_spy": round(metrics["ret60_excess_spy"], 6),
        "candidate_signal_day_return": round(metrics["signal_return"], 6),
        "candidate_signal_relative_vs_spy": round(metrics["signal_relative_vs_spy"], 6),
        "candidate_close_location": round(metrics["close_location"], 6),
        "candidate_volume_ratio_20d": round(metrics["volume_ratio_20d"], 6),
        "candidate_realized_vol_20d": round(metrics["realized_vol_20d"], 6),
        "candidate_avg_dollar_volume_20d": round(metrics["adv20"], 2),
        "industry_breadth_repair_context": {
            "group_key": metrics["group_key"],
            "liquid_group_count": group["liquid_group_count"],
            "median_ret20_excess_spy": round(group["median_ret20_excess_spy"], 6),
            "median_ret5_excess_spy": round(group["median_ret5_excess_spy"], 6),
            "ret20_positive_fraction": round(group["ret20_positive_fraction"], 6),
            "median_signal_return": round(group["median_signal_return"], 6),
            "signal_positive_fraction": round(group["signal_positive_fraction"], 6),
            "median_signal_relative_vs_spy": round(
                group["median_signal_relative_vs_spy"],
                6,
            ),
            "rule_version": RULE_VERSION,
        },
        "sector": metrics.get("sector"),
        "industry": metrics.get("industry"),
        "sector_coverage_status": metrics.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
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
    entries_by_date = base.framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in base.framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]

    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "days_with_breadth_repair_groups": 0,
        "days_with_raw_candidates": 0,
        "breadth_repair_group_rows": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "rule_version": RULE_VERSION,
    }
    candidate_tickers: set[str] = set()

    for signal_date in dates:
        group_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ticker in sector_entries:
            metrics = base._ticker_day_metrics(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if metrics is not None:
                group_members[metrics["group_key"]].append(metrics)

        group_summaries: dict[str, dict[str, Any]] = {}
        for group_key, rows in group_members.items():
            if len(rows) < MIN_INDUSTRY_LIQUID_COUNT:
                continue
            ret20_values = [float(row["ret20_excess_spy"]) for row in rows]
            ret5_values = [float(row["ret5_excess_spy"]) for row in rows]
            signal_values = [float(row["signal_return"]) for row in rows]
            signal_rel_values = [float(row["signal_relative_vs_spy"]) for row in rows]
            ret20_positive_fraction = sum(value > 0.0 for value in ret20_values) / len(
                ret20_values
            )
            signal_positive_fraction = sum(value > 0.0 for value in signal_values) / len(
                signal_values
            )
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
            if group_median_signal < MIN_GROUP_SIGNAL_MEDIAN_RETURN:
                continue
            if signal_positive_fraction < MIN_GROUP_SIGNAL_POSITIVE_FRACTION:
                continue
            if group_median_signal_rel < MIN_GROUP_SIGNAL_RELATIVE_VS_SPY:
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
        context_scan["days_with_breadth_repair_groups"] += 1
        context_scan["breadth_repair_group_rows"] += len(group_summaries)
        day_rows: list[dict[str, Any]] = []
        for group_key, rows in group_members.items():
            group = group_summaries.get(group_key)
            if group is None:
                continue
            for metrics in rows:
                row = _candidate_from_metrics(metrics=metrics, group=group)
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

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_signal_relative_vs_spy"]),
                -float(row["candidate_participation_vs_group_signal"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        context_scan["days_with_raw_candidates"] += 1
        context_scan["raw_candidate_rows"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "breadth_repair_group_count": len(group_summaries),
                "top_candidate": top["ticker"],
                "top_group_key": top["candidate_group_key"],
                "top_score": top["candidate_score"],
                "top_second_line_lag_20d": top["candidate_second_line_lag_20d"],
                "top_signal_relative_vs_spy": top["candidate_signal_relative_vs_spy"],
                "top_participation_vs_group_signal": top[
                    "candidate_participation_vs_group_signal"
                ],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_signal_relative_vs_spy"]),
            -float(row["candidate_participation_vs_group_signal"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
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
            "min_group_signal_median_return": MIN_GROUP_SIGNAL_MEDIAN_RETURN,
            "min_group_signal_positive_fraction": MIN_GROUP_SIGNAL_POSITIVE_FRACTION,
            "min_group_signal_relative_vs_spy": MIN_GROUP_SIGNAL_RELATIVE_VS_SPY,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "max_group_median_ret5_excess_spy": MAX_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_second_line_lag_20d": MIN_SECOND_LINE_LAG_20D,
            "max_second_line_lag_20d": MAX_SECOND_LINE_LAG_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy_above_group": (
                MAX_CANDIDATE_RET20_EXCESS_SPY_ABOVE_GROUP
            ),
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
        }
    )
    return candidates, day_contexts, context_scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_industry_breadth_repair_second_line"
        if gate["passed"]
        else "rejected_industry_breadth_repair_second_line_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = base.BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "In strong liquid industry groups that show same-day breadth "
                "repair without 5-day overextension, liquid second-line "
                "participants that join the repair may add cleaner "
                "replacement candidates than exhausted leaders or raw "
                "short-horizon reversals."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_industry_breadth_repair_relation",
            "nearby_prior_experiments": [
                "exp-20260607-005",
                "exp-20260607-007",
                "exp-20260607-008",
                "exp-20260607-009",
            ],
            "prior_trial_count": 4,
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
                "The industry breadth-repair second-line source cleared Gate "
                "4 as a replay-only/default-off lead, but no production "
                "surface was promoted."
                if gate4["passed"]
                else (
                    "The industry breadth-repair second-line source did not "
                    "clear Gate 4. Do not promote it or answer by retuning "
                    "breadth fraction, group repair, second-line lag, "
                    "close-location, hold-day, cooldown, top-N, or notional "
                    "thresholds on these frozen windows."
                )
            ),
            "negative_reflection": (
                "If rejected, the likely reason is that breadth repair "
                "participants are still a crowded continuation chase or weak "
                "momentum relabel, not a distinct displacement edge after "
                "costs."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "Pending run result. Replace with measured Gate 4 "
                    "behavior after the three-window replay."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping group breadth fraction, group "
                    "signal-day repair, 5-day group extension, second-line "
                    "lag, signal-day return, close-location, volume, "
                    "volatility, hold-day, top-N, cooldown, or paper notional "
                    "thresholds."
                ),
                "new_evidence_required": (
                    "A retry requires independent PIT confirmation such as "
                    "industry event/news context, earnings peer provenance, "
                    "borrow/options/ownership data with adequate historical "
                    "coverage, or closed forward replacement rows from a "
                    "shared default-off adapter."
                ),
            },
            "next_evidence_needed": (
                "Independent PIT context or shared-adapter forward rows are "
                "required before retrying near-neighbor industry breadth "
                "repair variants."
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
            "concentration guardrails, suggesting same-day industry breadth "
            "repair plus second-line participation captured a distinct "
            "relation."
        )
    else:
        payload["post_run_reflection"]["why_result_happened"] = (
            "The candidate source failed to add robust replacement value, "
            "regressed a canonical window, or breached drawdown/concentration "
            "gates. That means same-day industry breadth repair did not "
            "reliably separate second-line catch-up from continuation chase "
            "under existing costs, slippage, and 10-day exit assumptions."
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
            "min_group_signal_median_return": MIN_GROUP_SIGNAL_MEDIAN_RETURN,
            "min_group_signal_positive_fraction": MIN_GROUP_SIGNAL_POSITIVE_FRACTION,
            "min_group_signal_relative_vs_spy": MIN_GROUP_SIGNAL_RELATIVE_VS_SPY,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "max_group_median_ret5_excess_spy": MAX_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_second_line_lag_20d": MIN_SECOND_LINE_LAG_20D,
            "max_second_line_lag_20d": MAX_SECOND_LINE_LAG_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy_above_group": (
                MAX_CANDIDATE_RET20_EXCESS_SPY_ABOVE_GROUP
            ),
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
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior close history needed for 20-day industry relative strength, "
        "5-day extension control, same-day industry breadth repair, 60-day "
        "trend guard, ADV, volume ratio, and realized volatility. Paper entry "
        "is next available open with existing entry slippage; exit is the "
        "close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: same-day breadth repair in a strong "
            "industry group may identify second-line participants before "
            "they fully catch up."
        ),
        "2_history_check": {
            "exp-20260607-005": (
                "Short-horizon reversal failed with enough sample; this "
                "requires group-level breadth repair and strong 20-day "
                "context, not raw selloff/reclaim."
            ),
            "exp-20260607-007/008": (
                "Industry laggard repair was accepted; this is a different "
                "relation requiring same-day group breadth repair and only "
                "moderate second-line lag, not a parameter sweep of that "
                "accepted helper."
            ),
            "exp-20260607-009": (
                "Industry pullback leader resilience failed as likely "
                "exhaustion; this avoids leaders and requires broad group "
                "participation."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260607_010_industry_breadth_repair_second_line.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The industry "
        "breadth-repair second-line source is additive default-off paper, so "
        "core signals generated/survived are unchanged from baseline."
    )
    payload["context_alias"] = "industry_breadth_repair_contexts"
    payload["industry_breadth_repair_context_samples_by_window"] = {
        label: rows[:20]
        for label, rows in payload["pressure_contexts_by_window"].items()
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
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
            f"# {EXPERIMENT_ID} Industry Breadth-Repair Second-Line",
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
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
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
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
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
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in base.framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(SCRIPT_PATH),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(SCRIPT_PATH): base.framework._sha256(SCRIPT_PATH),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _patch() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.SCRIPT_PATH = SCRIPT_PATH
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    base.MIN_PRICE = MIN_PRICE
    base.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    base.GROUP_LOOKBACK_DAYS = GROUP_LOOKBACK_DAYS
    base.PULLBACK_LOOKBACK_DAYS = RECENT_LOOKBACK_DAYS
    base.TREND_LOOKBACK_DAYS = TREND_LOOKBACK_DAYS
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base._candidate_from_metrics = _candidate_from_metrics
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._build_payload = _build_payload
    base._build_card = _build_card
    base._build_log_record = _build_log_record
    base._write_manifest = _write_manifest
    base._patch_framework()


def main() -> None:
    _patch()
    base.main()


if __name__ == "__main__":
    main()
