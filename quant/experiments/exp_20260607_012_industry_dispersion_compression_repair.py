"""exp-20260607-012: industry dispersion-compression repair candidate pool.

Replay-only alpha search. It tests one free-OHLCV relation source:
when a strong liquid industry group has high 20-day internal return
dispersion, but the signal day shows broad synchronized repair with lower
same-day dispersion, select one liquid non-leader participant that joins the
repair. Paper entry is next-open with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260607_010_industry_breadth_repair_second_line as previous


EXPERIMENT_ID = "exp-20260607-012"
STEM = "industry_dispersion_compression_repair"
TRIAL_FAMILY = "industry_dispersion_compression_repair_candidate_pool"
TRIAL_VARIANT_ID = "industry_dispersion_compression_repair_top1_next_open_10d_v1"
CHANGED_VARIABLE = "industry_dispersion_compression_repair_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260607_012_industry_dispersion_compression_repair.json"
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

MIN_INDUSTRY_LIQUID_COUNT = 7
MIN_GROUP_MEDIAN_RET20_EXCESS_SPY = 0.015
MIN_GROUP_RET20_POSITIVE_FRACTION = 0.55
MIN_GROUP_RET20_DISPERSION = 0.080
MIN_GROUP_TOP_TO_MEDIAN_RET20 = 0.055
MIN_GROUP_SIGNAL_MEDIAN_RETURN = 0.003
MIN_GROUP_SIGNAL_POSITIVE_FRACTION = 0.62
MIN_GROUP_SIGNAL_RELATIVE_VS_SPY = 0.002
MAX_GROUP_SIGNAL_DISPERSION = 0.065
MIN_GROUP_MEDIAN_RET5_EXCESS_SPY = -0.020
MAX_GROUP_MEDIAN_RET5_EXCESS_SPY = 0.035

MIN_REPAIR_LAG_20D = 0.020
MAX_REPAIR_LAG_20D = 0.160
MAX_CANDIDATE_RET20_EXCESS_SPY_ABOVE_GROUP = 0.004
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.055
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.050
MIN_CANDIDATE_RET5_EXCESS_SPY = -0.010
MAX_CANDIDATE_RET5_EXCESS_SPY = 0.070
MIN_SIGNAL_RETURN = 0.004
MAX_SIGNAL_RETURN = 0.075
MIN_SIGNAL_RELATIVE_VS_SPY = 0.006
MIN_PARTICIPATION_VS_GROUP_SIGNAL = -0.006
MAX_PARTICIPATION_VS_GROUP_SIGNAL = 0.045
MIN_CLOSE_LOCATION = 0.62
MIN_VOLUME_RATIO_20D = 0.75
MAX_VOLUME_RATIO_20D = 2.80
MAX_REALIZED_VOL_20D = 0.082

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift",
        "dispersion_chase",
        "ohlcv_momentum_relabeling",
        "accepted_laggard_repair_near_neighbor",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Accepted industry laggard repair suggests industry-relative "
        "replacement can carry signal, while recent low-vol breakout, leader "
        "resilience, and breadth-only variants failed. This tests whether "
        "high prior intra-industry dispersion followed by synchronized repair "
        "is a distinct relation instead of another momentum relabel."
    ),
    "recorded_at": "2026-06-07T10:30:00Z",
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
        "warehouse liquid sector-known universe, PIT industry grouping, "
        "20-day group dispersion, top-to-median spread, same-day group repair "
        "and same-day dispersion fields, non-leader participation fields, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, and concentration controls in "
        "both replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}


def _repo_rel(path: Path | str) -> str:
    return previous._repo_rel(path)


def _iqr(values: list[float]) -> float:
    if len(values) < 4:
        return 0.0
    ordered = sorted(values)
    lower = ordered[len(ordered) // 4]
    upper = ordered[(len(ordered) * 3) // 4]
    return float(upper - lower)


def _candidate_from_metrics(
    *,
    metrics: dict[str, Any],
    group: dict[str, Any],
) -> dict[str, Any] | None:
    repair_lag_20d = group["median_ret20_excess_spy"] - metrics["ret20_excess_spy"]
    candidate_above_group_20d = (
        metrics["ret20_excess_spy"] - group["median_ret20_excess_spy"]
    )
    participation_vs_group_signal = metrics["signal_return"] - group[
        "median_signal_return"
    ]

    if repair_lag_20d < MIN_REPAIR_LAG_20D:
        return None
    if repair_lag_20d > MAX_REPAIR_LAG_20D:
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
    if participation_vs_group_signal < MIN_PARTICIPATION_VS_GROUP_SIGNAL:
        return None
    if participation_vs_group_signal > MAX_PARTICIPATION_VS_GROUP_SIGNAL:
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
        0.95 * group["median_ret20_excess_spy"]
        + 0.90 * group["ret20_dispersion"]
        + 0.70 * group["top_to_median_ret20"]
        + 1.15 * group["signal_positive_fraction"]
        + 1.35 * metrics["signal_relative_vs_spy"]
        + 0.65 * repair_lag_20d
        + 0.55 * metrics["close_location"]
        + 0.22 * metrics["ret60_excess_spy"]
        + 0.04 * math.log10(max(metrics["adv20"], 1.0) / 1_000_000.0)
        - 0.60 * metrics["realized_vol_20d"]
        - 0.22 * abs(participation_vs_group_signal)
        - 0.07 * max(metrics["volume_ratio_20d"] - 1.8, 0.0)
        - 0.35 * group["signal_dispersion"]
    )
    return {
        "date": metrics["date"],
        "ticker": metrics["ticker"],
        "source": "INDUSTRY_DISPERSION_COMPRESSION_REPAIR_PAPER",
        "candidate_score": round(score, 6),
        "candidate_group_key": metrics["group_key"],
        "candidate_repair_lag_20d": round(repair_lag_20d, 6),
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
        "industry_dispersion_compression_context": {
            "group_key": metrics["group_key"],
            "liquid_group_count": group["liquid_group_count"],
            "median_ret20_excess_spy": round(group["median_ret20_excess_spy"], 6),
            "median_ret5_excess_spy": round(group["median_ret5_excess_spy"], 6),
            "ret20_positive_fraction": round(group["ret20_positive_fraction"], 6),
            "ret20_dispersion": round(group["ret20_dispersion"], 6),
            "top_to_median_ret20": round(group["top_to_median_ret20"], 6),
            "median_signal_return": round(group["median_signal_return"], 6),
            "signal_positive_fraction": round(group["signal_positive_fraction"], 6),
            "median_signal_relative_vs_spy": round(
                group["median_signal_relative_vs_spy"],
                6,
            ),
            "signal_dispersion": round(group["signal_dispersion"], 6),
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
    entries_by_date = previous.base.framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: previous.base.framework.shadow._row_index(
            previous.base.framework.shadow._series(snapshot, ticker)
        )
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in previous.base.framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]

    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "days_with_dispersion_compression_groups": 0,
        "days_with_raw_candidates": 0,
        "dispersion_compression_group_rows": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "rule_version": RULE_VERSION,
    }
    candidate_tickers: set[str] = set()

    for signal_date in dates:
        group_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ticker in sector_entries:
            metrics = previous.base._ticker_day_metrics(
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
            ret20_dispersion = _iqr(ret20_values)
            signal_dispersion = _iqr(signal_values)
            top_to_median_ret20 = max(ret20_values) - group_median_ret20
            if group_median_ret20 < MIN_GROUP_MEDIAN_RET20_EXCESS_SPY:
                continue
            if ret20_positive_fraction < MIN_GROUP_RET20_POSITIVE_FRACTION:
                continue
            if ret20_dispersion < MIN_GROUP_RET20_DISPERSION:
                continue
            if top_to_median_ret20 < MIN_GROUP_TOP_TO_MEDIAN_RET20:
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
            if signal_dispersion > MAX_GROUP_SIGNAL_DISPERSION:
                continue
            group_summaries[group_key] = {
                "liquid_group_count": len(rows),
                "median_ret20_excess_spy": group_median_ret20,
                "median_ret5_excess_spy": group_median_ret5,
                "ret20_positive_fraction": ret20_positive_fraction,
                "ret20_dispersion": ret20_dispersion,
                "top_to_median_ret20": top_to_median_ret20,
                "median_signal_return": group_median_signal,
                "signal_positive_fraction": signal_positive_fraction,
                "median_signal_relative_vs_spy": group_median_signal_rel,
                "signal_dispersion": signal_dispersion,
            }

        if not group_summaries:
            continue
        context_scan["days_with_dispersion_compression_groups"] += 1
        context_scan["dispersion_compression_group_rows"] += len(group_summaries)
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
                -float(row["candidate_repair_lag_20d"]),
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
                "dispersion_compression_group_count": len(group_summaries),
                "top_candidate": top["ticker"],
                "top_group_key": top["candidate_group_key"],
                "top_score": top["candidate_score"],
                "top_repair_lag_20d": top["candidate_repair_lag_20d"],
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
            -float(row["candidate_repair_lag_20d"]),
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
            "min_group_ret20_dispersion": MIN_GROUP_RET20_DISPERSION,
            "min_group_top_to_median_ret20": MIN_GROUP_TOP_TO_MEDIAN_RET20,
            "min_group_signal_median_return": MIN_GROUP_SIGNAL_MEDIAN_RETURN,
            "min_group_signal_positive_fraction": MIN_GROUP_SIGNAL_POSITIVE_FRACTION,
            "min_group_signal_relative_vs_spy": MIN_GROUP_SIGNAL_RELATIVE_VS_SPY,
            "max_group_signal_dispersion": MAX_GROUP_SIGNAL_DISPERSION,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "max_group_median_ret5_excess_spy": MAX_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_repair_lag_20d": MIN_REPAIR_LAG_20D,
            "max_repair_lag_20d": MAX_REPAIR_LAG_20D,
            "max_candidate_ret20_excess_spy_above_group": (
                MAX_CANDIDATE_RET20_EXCESS_SPY_ABOVE_GROUP
            ),
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "max_candidate_ret5_excess_spy": MAX_CANDIDATE_RET5_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_participation_vs_group_signal": MIN_PARTICIPATION_VS_GROUP_SIGNAL,
            "max_participation_vs_group_signal": MAX_PARTICIPATION_VS_GROUP_SIGNAL,
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
    gate = previous.base.BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_industry_dispersion_compression_repair"
        if gate["passed"]
        else "rejected_industry_dispersion_compression_repair_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = previous.base.BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "In strong liquid industry groups with high prior 20-day "
                "internal dispersion, a signal day that shows broad repair "
                "and lower same-day dispersion may identify liquid non-leader "
                "participants before the group rotates inward."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_industry_dispersion_compression_relation",
            "nearby_prior_experiments": [
                "exp-20260606-015",
                "exp-20260607-007",
                "exp-20260607-008",
                "exp-20260607-009",
                "exp-20260607-010",
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
                "The industry dispersion-compression repair source cleared "
                "Gate 4 as a replay-only/default-off lead, but no production "
                "surface was promoted."
                if gate4["passed"]
                else (
                    "The industry dispersion-compression repair source did "
                    "not clear Gate 4. Do not promote it or answer by "
                    "retuning dispersion, signal-day repair, non-leader lag, "
                    "close-location, hold-day, cooldown, top-N, or notional "
                    "thresholds on these frozen windows."
                )
            ),
            "negative_reflection": (
                "If rejected, the likely reason is that prior intra-industry "
                "dispersion plus synchronized repair still behaves like a "
                "crowded momentum chase or a near-neighbor of accepted "
                "laggard repair rather than a distinct replacement edge."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "Pending run result. Replace with measured Gate 4 "
                    "behavior after the three-window replay."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping industry dispersion, "
                    "top-to-median spread, signal-day group repair, signal "
                    "dispersion, non-leader lag, signal relative strength, "
                    "close-location, volume, volatility, hold-day, top-N, "
                    "cooldown, or paper notional thresholds."
                ),
                "new_evidence_required": (
                    "A retry requires independent PIT confirmation such as "
                    "earnings peer provenance, news/event catalyst context, "
                    "options/borrow/ownership data with adequate history, or "
                    "closed forward rows from a shared default-off adapter."
                ),
            },
            "next_evidence_needed": (
                "Independent PIT context or shared-adapter forward rows are "
                "required before retrying near-neighbor industry dispersion "
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
            "concentration guardrails. That would suggest high prior "
            "intra-industry dispersion plus synchronized repair captured "
            "inward group rotation."
        )
    else:
        payload["post_run_reflection"]["why_result_happened"] = (
            "The candidate source failed to add robust replacement value, "
            "regressed a canonical window, or breached drawdown/concentration "
            "gates. That means high prior industry dispersion plus same-day "
            "repair did not reliably separate inward rotation from noisy "
            "catch-up under existing costs, slippage, and 10-day exit "
            "assumptions."
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
            "min_group_ret20_dispersion": MIN_GROUP_RET20_DISPERSION,
            "min_group_top_to_median_ret20": MIN_GROUP_TOP_TO_MEDIAN_RET20,
            "min_group_signal_median_return": MIN_GROUP_SIGNAL_MEDIAN_RETURN,
            "min_group_signal_positive_fraction": MIN_GROUP_SIGNAL_POSITIVE_FRACTION,
            "min_group_signal_relative_vs_spy": MIN_GROUP_SIGNAL_RELATIVE_VS_SPY,
            "max_group_signal_dispersion": MAX_GROUP_SIGNAL_DISPERSION,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "max_group_median_ret5_excess_spy": MAX_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_repair_lag_20d": MIN_REPAIR_LAG_20D,
            "max_repair_lag_20d": MAX_REPAIR_LAG_20D,
            "max_candidate_ret20_excess_spy_above_group": (
                MAX_CANDIDATE_RET20_EXCESS_SPY_ABOVE_GROUP
            ),
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "max_candidate_ret5_excess_spy": MAX_CANDIDATE_RET5_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_participation_vs_group_signal": MIN_PARTICIPATION_VS_GROUP_SIGNAL,
            "max_participation_vs_group_signal": MAX_PARTICIPATION_VS_GROUP_SIGNAL,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date "
        "plus prior close history needed for 20-day industry relative "
        "strength, 20-day intra-industry dispersion, 5-day extension control, "
        "same-day industry repair and same-day dispersion, 60-day trend "
        "guard, ADV, volume ratio, and realized volatility. Paper entry is "
        "next available open with existing entry slippage; exit is the close "
        "10 trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: synchronized repair after high "
            "intra-industry dispersion may identify inward rotation before "
            "the non-leader participant fully catches up."
        ),
        "2_history_check": {
            "exp-20260606-015": (
                "Low-vol 20d-high breakout improved aggregate EV but failed "
                "two windows and worsened drawdown; this avoids raw breakout "
                "and requires group dispersion plus broad same-day repair."
            ),
            "exp-20260607-007/008": (
                "Industry laggard repair was accepted; this is a scout for a "
                "different relation requiring high prior dispersion and "
                "same-day compression, not a retune of that shared helper."
            ),
            "exp-20260607-009": (
                "Pullback leader resilience failed as likely leader "
                "exhaustion; this excludes leaders by requiring below-group "
                "20-day position."
            ),
            "exp-20260607-010": (
                "Breadth repair second-line failed the old_thin window; this "
                "adds a distinct prior-dispersion and signal-dispersion "
                "condition rather than sweeping the breadth threshold."
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
            "exp_20260607_012_industry_dispersion_compression_repair.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The industry "
        "dispersion-compression repair source is additive default-off paper, "
        "so core signals generated/survived are unchanged from baseline."
    )
    payload["context_alias"] = "industry_dispersion_compression_contexts"
    payload["industry_dispersion_compression_context_samples_by_window"] = {
        label: rows[:20]
        for label, rows in payload["pressure_contexts_by_window"].items()
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in previous.base.framework.WINDOWS:
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
            f"# {EXPERIMENT_ID} Industry Dispersion-Compression Repair",
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
            for label in previous.base.framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _patch() -> None:
    previous.EXPERIMENT_ID = EXPERIMENT_ID
    previous.STEM = STEM
    previous.TRIAL_FAMILY = TRIAL_FAMILY
    previous.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    previous.CHANGED_VARIABLE = CHANGED_VARIABLE
    previous.RULE_VERSION = RULE_VERSION
    previous.OUT_DIR = OUT_DIR
    previous.OUT_JSON = OUT_JSON
    previous.LOG_JSON = LOG_JSON
    previous.TICKET_JSON = TICKET_JSON
    previous.CARD_MD = CARD_MD
    previous.MANIFEST_JSON = MANIFEST_JSON
    previous.EXPERIMENT_LOG = EXPERIMENT_LOG
    previous.REGISTRY_JSON = REGISTRY_JSON
    previous.SCRIPT_PATH = SCRIPT_PATH
    previous.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    previous.HOLD_DAYS = HOLD_DAYS
    previous.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    previous.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    previous.MIN_PRICE = MIN_PRICE
    previous.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    previous.GROUP_LOOKBACK_DAYS = GROUP_LOOKBACK_DAYS
    previous.RECENT_LOOKBACK_DAYS = RECENT_LOOKBACK_DAYS
    previous.TREND_LOOKBACK_DAYS = TREND_LOOKBACK_DAYS
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


def main() -> None:
    _patch()
    previous.main()


if __name__ == "__main__":
    main()
