"""exp-20260609-018: industry pullback reclaim candidate pool.

Replay-only alpha search. This tests one production-visible free-OHLCV
relation source: within liquid industries with persistent relative strength,
select the stock that pulled back to its 50-day average and reclaimed it on the
signal day as a top-1 next-open default-off paper candidate with a fixed
10-trading-day hold.

No production code, shared helper, live/default orders, ranking, sizing, exits,
LLM/news path, watchlist, or run.py behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260609_008_low_turnover_rs_consolidation as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260609-018"
STEM = "industry_pullback_reclaim"
TRIAL_FAMILY = "industry_pullback_reclaim_candidate_pool"
TRIAL_VARIANT_ID = "industry_pullback_reclaim_top1_next_open_10d_v1"
CHANGED_VARIABLE = "industry_pullback_reclaim_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_018_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 12

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 60_000_000.0
GROUP_LOOKBACK_DAYS = 20
RECENT_LOOKBACK_DAYS = 5
TREND_LOOKBACK_DAYS = 60
SMA_LOOKBACK_DAYS = 50
PULLBACK_LOOKBACK_DAYS = 8

MIN_INDUSTRY_LIQUID_COUNT = 5
MIN_GROUP_MEDIAN_RET20_EXCESS_SPY = 0.020
MIN_GROUP_RET20_POSITIVE_FRACTION = 0.55
MIN_GROUP_MEDIAN_RET5_EXCESS_SPY = -0.025
MIN_GROUP_MEDIAN_RET60_EXCESS_SPY = 0.000
MIN_GROUP_LAG_20D = 0.020
MAX_GROUP_LAG_20D = 0.180
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.120
MAX_CANDIDATE_RET20_EXCESS_SPY = 0.050
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.045
MIN_CANDIDATE_RET5_EXCESS_SPY = -0.085
MAX_CANDIDATE_RET5_EXCESS_SPY = 0.040
MAX_PRIOR_CLOSE_DISTANCE_TO_SMA50 = 0.012
MAX_RECENT_MIN_DISTANCE_TO_SMA50 = 0.006
MIN_RECENT_MIN_DISTANCE_TO_SMA50 = -0.115
MIN_SIGNAL_DISTANCE_TO_SMA50 = 0.002
MAX_SIGNAL_DISTANCE_TO_SMA50 = 0.075
MIN_SMA50_RECLAIM_DELTA = 0.004
MIN_SIGNAL_RETURN = 0.004
MAX_SIGNAL_RETURN = 0.075
MIN_SIGNAL_RELATIVE_VS_SPY = 0.005
MIN_CLOSE_LOCATION = 0.60
MIN_VOLUME_RATIO_20D = 0.65
MAX_VOLUME_RATIO_20D = 2.40
MAX_REALIZED_VOL_20D = 0.085

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

EXCLUDED_TICKERS = previous.EXCLUDED_TICKERS

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "accepted_industry_laggard_comparator_not_beaten",
        "accepted_rolling_corr_comparator_not_beaten",
        "window_regression",
        "drawdown_drift",
        "pullback_value_trap",
        "too_close_to_laggard_repair",
    ],
    "confidence_reason": (
        "The accepted industry laggard repair alpha shows that free OHLCV "
        "industry-relative displacement can work, but many near-neighbor "
        "relation and gap variants fail. This tests a different field: "
        "SMA50 pullback/reclaim inside an already strong industry."
    ),
    "recorded_at": "2026-06-09T16:07:09+00:00",
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
        "Replay-only scout. This experiment changes no production code. A "
        "positive result would require a shared default-off adapter that "
        "computes the same broad liquid sector-known universe, PIT industry "
        "grouping, industry relative-strength medians, 50-day moving-average "
        "pullback/reclaim field, same-ticker core-overlap exclusion, next-open "
        "paper entry, 10-trading-day exit, costs, cooldown, accepted "
        "comparator checks, and concentration controls in both historical "
        "replay and daily production before any report queue, paper ledger, "
        "candidate priority, sizing, watchlist, or order surface could change."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR = {
    "experiment_id": "exp-20260607-008",
    "decision": "accepted_industry_relative_laggard_repair_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.2763,
    "total_pnl_delta_sum": 6208.99,
    "target_trade_count": 306,
}
ACCEPTED_ROLLING_CORR_COMPARATOR = {
    "experiment_id": "exp-20260606-025",
    "decision": "accepted_rolling_corr_peer_shock_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.3845,
    "total_pnl_delta_sum": 6107.66,
    "target_trade_count": 48,
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _group_key(meta: dict[str, Any]) -> str | None:
    industry = str(meta.get("industry") or "").strip()
    sector = str(meta.get("sector") or "").strip()
    if industry:
        return industry
    if sector:
        return f"Sector:{sector}"
    return None


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx + 1 < lookback:
        return None
    closes = [
        framework._value(row, "Close")
        for row in rows[idx - lookback + 1 : idx + 1]
    ]
    if any(value is None or value <= 0 for value in closes):
        return None
    return sum(float(value) for value in closes if value is not None) / lookback


def _recent_min_distance_to_sma(
    rows: list[dict[str, Any]],
    idx: int,
    *,
    lookback: int,
    recent_days: int,
) -> float | None:
    if idx < recent_days:
        return None
    distances: list[float] = []
    for prior_idx in range(idx - recent_days, idx):
        close = framework._value(rows[prior_idx], "Close")
        sma_value = _sma(rows, prior_idx, lookback)
        if close is None or sma_value is None or sma_value <= 0:
            return None
        distances.append(float(close) / sma_value - 1.0)
    return min(distances) if distances else None


def _ticker_day_metrics(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    min_idx = max(
        TREND_LOOKBACK_DAYS,
        SMA_LOOKBACK_DAYS + PULLBACK_LOOKBACK_DAYS,
        GROUP_LOOKBACK_DAYS,
        RECENT_LOOKBACK_DAYS,
        20,
    )
    if idx is None or spy_idx is None or idx < min_idx or spy_idx < min_idx:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    ret20 = framework._ret(rows, idx, GROUP_LOOKBACK_DAYS)
    spy_ret20 = framework._ret(spy_rows, spy_idx, GROUP_LOOKBACK_DAYS)
    ret5 = framework._ret(rows, idx, RECENT_LOOKBACK_DAYS)
    spy_ret5 = framework._ret(spy_rows, spy_idx, RECENT_LOOKBACK_DAYS)
    ret60 = framework._ret(rows, idx, TREND_LOOKBACK_DAYS)
    spy_ret60 = framework._ret(spy_rows, spy_idx, TREND_LOOKBACK_DAYS)
    signal_return = framework._daily_return(rows, idx)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    sma50 = _sma(rows, idx, SMA_LOOKBACK_DAYS)
    prior_sma50 = _sma(rows, idx - 1, SMA_LOOKBACK_DAYS)
    prior_close = framework._value(rows[idx - 1], "Close")
    recent_min_distance_to_sma50 = _recent_min_distance_to_sma(
        rows,
        idx,
        lookback=SMA_LOOKBACK_DAYS,
        recent_days=PULLBACK_LOOKBACK_DAYS,
    )
    required = [
        ret20,
        spy_ret20,
        ret5,
        spy_ret5,
        ret60,
        spy_ret60,
        signal_return,
        spy_signal_return,
        close_location,
        volume_ratio,
        realized_vol20,
        sma50,
        prior_sma50,
        prior_close,
        recent_min_distance_to_sma50,
    ]
    if any(value is None for value in required):
        return None

    assert ret20 is not None
    assert spy_ret20 is not None
    assert ret5 is not None
    assert spy_ret5 is not None
    assert ret60 is not None
    assert spy_ret60 is not None
    assert signal_return is not None
    assert spy_signal_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert realized_vol20 is not None
    assert sma50 is not None
    assert prior_sma50 is not None
    assert prior_close is not None
    assert recent_min_distance_to_sma50 is not None
    if sma50 <= 0 or prior_sma50 <= 0:
        return None

    meta = sector_entries[ticker]
    key = _group_key(meta)
    if key is None:
        return None
    prior_close_distance_to_sma50 = prior_close / prior_sma50 - 1.0
    signal_distance_to_sma50 = close / sma50 - 1.0
    sma50_reclaim_delta = signal_distance_to_sma50 - prior_close_distance_to_sma50
    return {
        "date": signal_date,
        "ticker": ticker,
        "group_key": key,
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "sector_coverage_status": meta.get("sector_coverage_status"),
        "close": close,
        "adv20": adv20,
        "ret20_excess_spy": ret20 - spy_ret20,
        "ret5_excess_spy": ret5 - spy_ret5,
        "ret60_excess_spy": ret60 - spy_ret60,
        "signal_return": signal_return,
        "signal_relative_vs_spy": signal_return - spy_signal_return,
        "close_location": close_location,
        "volume_ratio_20d": volume_ratio,
        "realized_vol_20d": realized_vol20,
        "sma50": sma50,
        "prior_close_distance_to_sma50": prior_close_distance_to_sma50,
        "recent_min_distance_to_sma50": recent_min_distance_to_sma50,
        "signal_distance_to_sma50": signal_distance_to_sma50,
        "sma50_reclaim_delta": sma50_reclaim_delta,
    }


def _candidate_from_metrics(
    *,
    metrics: dict[str, Any],
    group: dict[str, Any],
) -> dict[str, Any] | None:
    group_lag_20d = group["median_ret20_excess_spy"] - metrics["ret20_excess_spy"]
    if group_lag_20d < MIN_GROUP_LAG_20D or group_lag_20d > MAX_GROUP_LAG_20D:
        return None
    if metrics["ret20_excess_spy"] < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if metrics["ret20_excess_spy"] > MAX_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if metrics["ret60_excess_spy"] < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if metrics["ret5_excess_spy"] < MIN_CANDIDATE_RET5_EXCESS_SPY:
        return None
    if metrics["ret5_excess_spy"] > MAX_CANDIDATE_RET5_EXCESS_SPY:
        return None
    if metrics["prior_close_distance_to_sma50"] > MAX_PRIOR_CLOSE_DISTANCE_TO_SMA50:
        return None
    if metrics["recent_min_distance_to_sma50"] > MAX_RECENT_MIN_DISTANCE_TO_SMA50:
        return None
    if metrics["recent_min_distance_to_sma50"] < MIN_RECENT_MIN_DISTANCE_TO_SMA50:
        return None
    if metrics["signal_distance_to_sma50"] < MIN_SIGNAL_DISTANCE_TO_SMA50:
        return None
    if metrics["signal_distance_to_sma50"] > MAX_SIGNAL_DISTANCE_TO_SMA50:
        return None
    if metrics["sma50_reclaim_delta"] < MIN_SMA50_RECLAIM_DELTA:
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

    pullback_depth_score = min(
        max(-metrics["recent_min_distance_to_sma50"], 0.0),
        0.080,
    ) / 0.080
    reclaim_score = min(max(metrics["sma50_reclaim_delta"], 0.0), 0.080) / 0.080
    repair_vs_group_5d = metrics["ret5_excess_spy"] - group["median_ret5_excess_spy"]
    score = (
        1.45 * reclaim_score
        + 0.95 * pullback_depth_score
        + 1.15 * group_lag_20d
        + 0.95 * group["median_ret20_excess_spy"]
        + 0.70 * metrics["signal_relative_vs_spy"]
        + 0.55 * repair_vs_group_5d
        + 0.42 * metrics["close_location"]
        + 0.20 * metrics["ret60_excess_spy"]
        + 0.04 * math.log10(max(metrics["adv20"], 1.0) / 1_000_000.0)
        - 0.55 * metrics["realized_vol_20d"]
        - 0.08 * abs(metrics["volume_ratio_20d"] - 1.15)
    )
    return {
        "date": metrics["date"],
        "ticker": metrics["ticker"],
        "source": "INDUSTRY_PULLBACK_RECLAIM_PAPER",
        "candidate_score": round(score, 6),
        "candidate_group_key": metrics["group_key"],
        "candidate_industry_lag_20d": round(group_lag_20d, 6),
        "candidate_repair_vs_group_5d": round(repair_vs_group_5d, 6),
        "candidate_ret20_excess_spy": round(metrics["ret20_excess_spy"], 6),
        "candidate_ret5_excess_spy": round(metrics["ret5_excess_spy"], 6),
        "candidate_ret60_excess_spy": round(metrics["ret60_excess_spy"], 6),
        "candidate_signal_day_return": round(metrics["signal_return"], 6),
        "candidate_signal_relative_vs_spy": round(metrics["signal_relative_vs_spy"], 6),
        "candidate_close_location": round(metrics["close_location"], 6),
        "candidate_volume_ratio_20d": round(metrics["volume_ratio_20d"], 6),
        "candidate_realized_vol_20d": round(metrics["realized_vol_20d"], 6),
        "candidate_avg_dollar_volume_20d": round(metrics["adv20"], 2),
        "candidate_sma50": round(metrics["sma50"], 6),
        "candidate_prior_close_distance_to_sma50": round(
            metrics["prior_close_distance_to_sma50"],
            6,
        ),
        "candidate_recent_min_distance_to_sma50": round(
            metrics["recent_min_distance_to_sma50"],
            6,
        ),
        "candidate_signal_distance_to_sma50": round(
            metrics["signal_distance_to_sma50"],
            6,
        ),
        "candidate_sma50_reclaim_delta": round(metrics["sma50_reclaim_delta"], 6),
        "candidate_pullback_depth_score": round(pullback_depth_score, 6),
        "candidate_reclaim_score": round(reclaim_score, 6),
        "industry_context": {
            "group_key": metrics["group_key"],
            "liquid_group_count": group["liquid_group_count"],
            "median_ret20_excess_spy": round(group["median_ret20_excess_spy"], 6),
            "median_ret5_excess_spy": round(group["median_ret5_excess_spy"], 6),
            "median_ret60_excess_spy": round(group["median_ret60_excess_spy"], 6),
            "ret20_positive_fraction": round(group["ret20_positive_fraction"], 6),
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
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]

    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "days_with_strong_groups": 0,
        "days_with_raw_candidates": 0,
        "strong_group_rows": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "rule_version": RULE_VERSION,
    }
    candidate_tickers: set[str] = set()

    for signal_date in dates:
        group_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ticker in sorted(sector_entries):
            metrics = _ticker_day_metrics(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if metrics is None:
                continue
            group_members[metrics["group_key"]].append(metrics)

        group_summaries: dict[str, dict[str, Any]] = {}
        for group_key, rows in group_members.items():
            if len(rows) < MIN_INDUSTRY_LIQUID_COUNT:
                continue
            ret20_values = [float(row["ret20_excess_spy"]) for row in rows]
            ret5_values = [float(row["ret5_excess_spy"]) for row in rows]
            ret60_values = [float(row["ret60_excess_spy"]) for row in rows]
            positive_fraction = sum(value > 0.0 for value in ret20_values) / len(
                ret20_values
            )
            group_median_ret20 = median(ret20_values)
            group_median_ret5 = median(ret5_values)
            group_median_ret60 = median(ret60_values)
            if group_median_ret20 < MIN_GROUP_MEDIAN_RET20_EXCESS_SPY:
                continue
            if positive_fraction < MIN_GROUP_RET20_POSITIVE_FRACTION:
                continue
            if group_median_ret5 < MIN_GROUP_MEDIAN_RET5_EXCESS_SPY:
                continue
            if group_median_ret60 < MIN_GROUP_MEDIAN_RET60_EXCESS_SPY:
                continue
            group_summaries[group_key] = {
                "liquid_group_count": len(rows),
                "median_ret20_excess_spy": group_median_ret20,
                "median_ret5_excess_spy": group_median_ret5,
                "median_ret60_excess_spy": group_median_ret60,
                "ret20_positive_fraction": positive_fraction,
            }

        if not group_summaries:
            continue
        context_scan["days_with_strong_groups"] += 1
        context_scan["strong_group_rows"] += len(group_summaries)
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
                -float(row["candidate_reclaim_score"]),
                -float(row["candidate_pullback_depth_score"]),
                -float(row["candidate_signal_relative_vs_spy"]),
                -float(row["candidate_industry_lag_20d"]),
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
                "strong_group_count": len(group_summaries),
                "top_candidate": top["ticker"],
                "top_group_key": top["candidate_group_key"],
                "top_score": top["candidate_score"],
                "top_reclaim_score": top["candidate_reclaim_score"],
                "top_pullback_depth_score": top["candidate_pullback_depth_score"],
                "top_signal_distance_to_sma50": top[
                    "candidate_signal_distance_to_sma50"
                ],
                "top_recent_min_distance_to_sma50": top[
                    "candidate_recent_min_distance_to_sma50"
                ],
                "top_industry_lag_20d": top["candidate_industry_lag_20d"],
                "top_signal_relative_vs_spy": top["candidate_signal_relative_vs_spy"],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_reclaim_score"]),
            -float(row["candidate_pullback_depth_score"]),
            -float(row["candidate_signal_relative_vs_spy"]),
            -float(row["candidate_industry_lag_20d"]),
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
            "sma_lookback_days": SMA_LOOKBACK_DAYS,
            "pullback_lookback_days": PULLBACK_LOOKBACK_DAYS,
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_group_median_ret60_excess_spy": MIN_GROUP_MEDIAN_RET60_EXCESS_SPY,
            "min_group_lag_20d": MIN_GROUP_LAG_20D,
            "max_group_lag_20d": MAX_GROUP_LAG_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "max_candidate_ret5_excess_spy": MAX_CANDIDATE_RET5_EXCESS_SPY,
            "max_prior_close_distance_to_sma50": MAX_PRIOR_CLOSE_DISTANCE_TO_SMA50,
            "max_recent_min_distance_to_sma50": MAX_RECENT_MIN_DISTANCE_TO_SMA50,
            "min_recent_min_distance_to_sma50": MIN_RECENT_MIN_DISTANCE_TO_SMA50,
            "min_signal_distance_to_sma50": MIN_SIGNAL_DISTANCE_TO_SMA50,
            "max_signal_distance_to_sma50": MAX_SIGNAL_DISTANCE_TO_SMA50,
            "min_sma50_reclaim_delta": MIN_SMA50_RECLAIM_DELTA,
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
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= (
        ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR["expected_value_score_delta_sum"]
    ):
        gate.setdefault("failed_reasons", []).append(
            "accepted_industry_laggard_repair_ev_not_beaten"
        )
    if aggregate["total_pnl_delta_sum"] <= (
        ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR["total_pnl_delta_sum"]
    ):
        gate.setdefault("failed_reasons", []).append(
            "accepted_industry_laggard_repair_pnl_not_beaten"
        )
    if aggregate["expected_value_score_delta_sum"] <= (
        ACCEPTED_ROLLING_CORR_COMPARATOR["expected_value_score_delta_sum"]
    ):
        gate.setdefault("failed_reasons", []).append(
            "accepted_rolling_corr_ev_not_beaten"
        )
    if aggregate["total_pnl_delta_sum"] <= (
        ACCEPTED_ROLLING_CORR_COMPARATOR["total_pnl_delta_sum"]
    ):
        gate.setdefault("failed_reasons", []).append(
            "accepted_rolling_corr_pnl_not_beaten"
        )
    gate["accepted_comparators"] = {
        "industry_laggard_repair": ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR,
        "rolling_corr_peer_shock": ACCEPTED_ROLLING_CORR_COMPARATOR,
    }
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_industry_pullback_reclaim"
        if gate["passed"]
        else "rejected_industry_pullback_reclaim_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Within strong liquid industries, stocks that pull back to the "
                "50-day average and reclaim it on the signal day may identify "
                "healthier catch-up demand than generic industry laggard "
                "repair, using only free production-visible OHLCV data."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_industry_trend_sma50_pullback_reclaim",
            "nearby_prior_experiments": [
                "exp-20260607-007",
                "exp-20260607-008",
                "exp-20260607-009",
                "exp-20260609-014",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": {
                "industry_laggard_repair": ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR,
                "rolling_corr_peer_shock": ACCEPTED_ROLLING_CORR_COMPARATOR,
            },
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that SMA50 reclaim in a "
                "strong industry is a familiar laggard-repair relabel or "
                "post-pullback value trap rather than independent replacement "
                "value. Do not answer by sweeping SMA distance, lag, signal "
                "return, volume, top-N, hold-day, cooldown, or notional "
                "thresholds on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence such as forward "
                "shared-adapter replacement rows, catalyst provenance, borrow/"
                "options/ownership context, or a true industry-flow field. Pure "
                "SMA50 reclaim threshold retunes should stay frozen."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
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
            "sma_lookback_days": SMA_LOOKBACK_DAYS,
            "pullback_lookback_days": PULLBACK_LOOKBACK_DAYS,
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_group_median_ret60_excess_spy": MIN_GROUP_MEDIAN_RET60_EXCESS_SPY,
            "min_group_lag_20d": MIN_GROUP_LAG_20D,
            "max_group_lag_20d": MAX_GROUP_LAG_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "max_candidate_ret5_excess_spy": MAX_CANDIDATE_RET5_EXCESS_SPY,
            "max_prior_close_distance_to_sma50": MAX_PRIOR_CLOSE_DISTANCE_TO_SMA50,
            "max_recent_min_distance_to_sma50": MAX_RECENT_MIN_DISTANCE_TO_SMA50,
            "min_recent_min_distance_to_sma50": MIN_RECENT_MIN_DISTANCE_TO_SMA50,
            "min_signal_distance_to_sma50": MIN_SIGNAL_DISTANCE_TO_SMA50,
            "max_signal_distance_to_sma50": MAX_SIGNAL_DISTANCE_TO_SMA50,
            "min_sma50_reclaim_delta": MIN_SMA50_RECLAIM_DELTA,
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
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: in strong liquid industries, an individual "
            "member that pulled back to its 50-day average and reclaims it may "
            "capture repaired demand while avoiding generic momentum ticker "
            "expansion."
        ),
        "2_history_check": {
            "exp-20260607-007/008": (
                "Industry-relative laggard repair was accepted. This is an "
                "adjacent relation alpha, so it must beat that accepted "
                "comparator and is not kept as a simple lag threshold retune."
            ),
            "exp-20260607-009": (
                "The raw/source-family neighbor around industry relation "
                "selection did not justify local retunes without new evidence."
            ),
            "exp-20260609-014": (
                "Multi-peer cluster shock failed; relation alphas need an "
                "actual displacement field, not generic beta clustering."
            ),
            "exp-20260606-025": (
                "Accepted rolling-correlation peer shock remains the stronger "
                "relation comparator, so this replay must beat it before it "
                "has replacement value."
            ),
        },
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Require "
            "positive aggregate EV/PnL, no EV/PnL-regressed window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard pass, and aggregate EV/PnL above "
            "accepted industry-laggard and rolling-corr comparators."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_018_industry_pullback_reclaim.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or live entry rule was added. The SMA50 pullback "
        "reclaim source is additive default-off paper, so core signals "
        "generated/survived are unchanged from baseline."
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior history needed for industry medians, 50-day SMA, pullback depth, "
        "ADV, volume ratio, and volatility. Paper entry is next available open "
        "with existing entry slippage; exit is the close 10 trading days after "
        "the signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "positive_replay_lead_not_promoted" if passed else "rejected"
    payload["interpretation"] = (
        "The industry pullback reclaim source cleared strict Gate 4 and beat "
        "accepted relation comparators, but remains replay-only until a shared "
        "default-off adapter proves parity and forward replacement value."
        if passed
        else (
            "The industry pullback reclaim source did not clear Gate 4 or did "
            "not beat accepted relation comparators. Do not promote it or "
            "locally retune SMA distance, group-strength, signal-day reclaim, "
            "hold-day, cooldown, top-N, or paper-notional thresholds on these "
            "frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed SMA50 pullback/reclaim source beat accepted relation "
            "comparators across the canonical windows, suggesting the moving "
            "average repair field added replacement value beyond generic "
            "industry laggard repair. It is still replay-only and cannot be "
            "promoted without shared helper parity."
            if passed
            else (
                "The fixed SMA50 pullback/reclaim source failed Gate 4 or did "
                "not beat accepted relation comparators. The mechanism likely "
                "collapses into a familiar laggard-repair/value-trap pattern: "
                "a moving-average reclaim inside a strong group was not enough "
                "to identify independent demand after next-open execution, "
                "costs, cooldown, and concentration controls."
            )
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping SMA lookback, SMA distance, pullback "
            "lookback/depth, group lag, group median RS, signal return, volume, "
            "close location, volatility, top-N, hold-day, cooldown, or paper "
            "notional thresholds on these frozen windows."
        ),
        "new_evidence_required": (
            "Need materially new PIT relation/flow/catalyst evidence or closed "
            "forward replacement rows from a shared default-off adapter before "
            "revisiting industry pullback reclaim."
        ),
    }
    payload["context_alias"] = "industry_pullback_reclaim_candidate_day_contexts"
    payload["industry_context_samples_by_window"] = {
        label: rows[:20]
        for label, rows in payload["pressure_contexts_by_window"].items()
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
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
            f"# {EXPERIMENT_ID} Industry Pullback Reclaim",
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
            "- Industry-laggard comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR[
                    "expected_value_score_delta_sum"
                ],
                ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Rolling-corr comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_ROLLING_CORR_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_ROLLING_CORR_COMPARATOR["total_pnl_delta_sum"],
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
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_20260606_193249.json"
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
                "expected_value_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
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
        "accepted": False,
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
        "owner": "alpha-search-automation",
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


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
