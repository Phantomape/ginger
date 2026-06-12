"""exp-20260612-014: dynamic correlation-cluster breadth leadership scout.

Replay-only alpha search. This tests one free-OHLCV relation/candidate-pool
variable: when a same-day core-flow entry belongs to a dynamic correlation
cluster with broad positive breadth, admit one liquid non-core cluster member
with controlled extension as a next-open 10-day paper candidate.

This is intentionally a private replay scout because the data shape is still
uncertain. A positive result would be only a replay lead until a shared
default-off helper and daily snapshot parity compute the same fields in both
historical replay and production.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for import_path in (ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402


EXPERIMENT_ID = "exp-20260612-014"
STEM = "dynamic_corr_cluster_breadth_leadership"
TRIAL_FAMILY = "dynamic_corr_cluster_breadth_leadership_candidate_pool"
TRIAL_VARIANT_ID = "core_flow_corr_cluster_breadth_top1_next_open_10d_v1"
CHANGED_VARIABLE = "dynamic_corr_cluster_core_flow_breadth_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260612_014_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
CORR_LOOKBACK_DAYS = 60
MIN_CORR_OBSERVATIONS = 45
MIN_ANCHOR_SIGNAL_RETURN = 0.002
MIN_ANCHOR_RELATIVE_VS_SPY = -0.006
MIN_ANCHOR_CLOSE_LOCATION = 0.48
MIN_ANCHOR_AVG_DOLLAR_VOLUME_20D = 75_000_000.0
MAX_ANCHORS_PER_DAY = 3
MAX_CORRELATED_MEMBERS_PER_ANCHOR = 24
MIN_CLUSTER_CORRELATION = 0.48
MIN_CLUSTER_MEMBER_COUNT = 5
MIN_CLUSTER_POSITIVE_FRACTION = 0.58
MIN_CLUSTER_MEDIAN_RETURN = 0.0025
MIN_CLUSTER_AVG_VOLUME_RATIO_20D = 0.85

MIN_CANDIDATE_SIGNAL_RETURN = -0.003
MAX_CANDIDATE_SIGNAL_RETURN = 0.033
MIN_CANDIDATE_RELATIVE_VS_SPY = -0.002
MIN_CANDIDATE_CLOSE_LOCATION = 0.50
MIN_CANDIDATE_VOLUME_RATIO_20D = 0.65
MAX_CANDIDATE_VOLUME_RATIO_20D = 2.75
MAX_CANDIDATE_RET5 = 0.085
MAX_CANDIDATE_RET20_EXCESS_SPY = 0.180
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.035
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.080
MAX_CANDIDATE_REALIZED_VOL_20D = 0.095

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_PEER_SHOCK_COMPARATOR = {
    "experiment_id": "exp-20260606-025",
    "decision": "accepted_rolling_corr_peer_shock_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.3845,
    "total_pnl_delta_sum": 6107.66,
    "target_trade_count": 48,
}

PREDICTION = {
    "success_probability": 0.19,
    "expected_ev_delta": 0.16,
    "expected_pnl_delta": 2800.0,
    "main_failure_modes": [
        "correlation_cluster_relabels_beta",
        "accepted_peer_shock_comparator_not_beaten",
        "window_regression",
        "concentration_failed",
        "thin_sample",
    ],
    "confidence_reason": (
        "Accepted rolling-correlation peer shock proves a free-OHLCV relation "
        "edge can exist; rejected static industry, lead-lag, and breadth "
        "variants show this must add anchor-conditioned cluster breadth "
        "evidence rather than broader noise."
    ),
    "recorded_at": "2026-06-12T16:07:23+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_dynamic_corr_cluster_breadth_scout",
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
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "max_active_positions": 8,
        "liquidity_source": "signal-date price >= $10 and ADV20 >= $50M",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none; replay-only paper overlay versus core baseline",
        "kill_switch": (
            "not live; positive replay requires shared helper parity, forward "
            "replacement-value rows, and a separate activation envelope"
        ),
    },
    "parity_note": (
        "This experiment changes no production path. A positive result remains "
        "a replay lead until a shared default-off helper computes the same "
        "anchor, rolling-correlation, cluster breadth, candidate gates, core "
        "overlap exclusion, next-open paper entry, 10-day exit, costs, cooldown, "
        "comparator, and concentration controls in historical replay and daily "
        "production snapshots."
    ),
}

BASE_BUILD_PAYLOAD = framework._build_payload
BASE_BUILD_LOG_RECORD = framework._build_log_record
BASE_GATE4 = framework._gate4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float(value)
    if number is None:
        return None
    return round(number, digits)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _pearson_corr(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < MIN_CORR_OBSERVATIONS:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (left[idx] - left_mean) * (right[idx] - right_mean)
        for idx in range(len(left))
    )
    left_denominator = sum((value - left_mean) ** 2 for value in left)
    right_denominator = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_denominator * right_denominator)
    if denominator <= 0:
        return None
    return numerator / denominator


def _return_vector(
    *,
    rows: list[dict[str, Any]],
    index: dict[str, int],
    prior_dates: list[str],
) -> list[float] | None:
    values: list[float] = []
    for date_value in prior_dates:
        idx = index.get(date_value)
        if idx is None:
            continue
        daily_return = framework._daily_return(rows, idx)
        if daily_return is None:
            continue
        values.append(float(daily_return))
    if len(values) < MIN_CORR_OBSERVATIONS:
        return None
    return values


def _core_entries_by_date(before_result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return framework.shadow._baseline_entries(before_result)


def _anchor_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < CORR_LOOKBACK_DAYS + 1 or spy_idx < 60:
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_ANCHOR_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    if (
        signal_return is None
        or spy_return is None
        or close_location is None
        or volume_ratio is None
    ):
        return None
    relative_vs_spy = signal_return - spy_return
    if signal_return < MIN_ANCHOR_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_ANCHOR_RELATIVE_VS_SPY:
        return None
    if close_location < MIN_ANCHOR_CLOSE_LOCATION:
        return None
    sector_meta = sector_entries.get(ticker) or {}
    anchor_score = (
        1.8 * signal_return
        + 1.2 * relative_vs_spy
        + 0.20 * min(volume_ratio, 4.0)
        + 0.05 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    return {
        "ticker": ticker,
        "date": signal_date,
        "anchor_signal_return": round(signal_return, 6),
        "anchor_relative_vs_spy": round(relative_vs_spy, 6),
        "anchor_close_location": round(close_location, 6),
        "anchor_volume_ratio_20d": round(volume_ratio, 6),
        "anchor_avg_dollar_volume_20d": round(adv20, 2),
        "anchor_score": round(anchor_score, 6),
        "anchor_sector": sector_meta.get("sector"),
        "anchor_industry": sector_meta.get("industry"),
    }


def _candidate_metrics(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < CORR_LOOKBACK_DAYS + 1 or spy_idx < 60 or idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    required = [
        signal_return,
        spy_return,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert signal_return is not None
    assert spy_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    relative_vs_spy = signal_return - spy_return
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if signal_return > MAX_CANDIDATE_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_CANDIDATE_RELATIVE_VS_SPY:
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20D:
        return None
    if volume_ratio > MAX_CANDIDATE_VOLUME_RATIO_20D:
        return None
    if ret5 > MAX_CANDIDATE_RET5:
        return None
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret20_excess_spy > MAX_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if realized_vol20 > MAX_CANDIDATE_REALIZED_VOL_20D:
        return None
    sector_meta = sector_entries.get(ticker) or {}
    return {
        "ticker": ticker,
        "candidate_signal_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
    }


def _cluster_members_for_anchor(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    anchor: dict[str, Any],
    signal_date: str,
    prior_dates: list[str],
    vector_cache: dict[tuple[str, str], list[float] | None],
) -> list[dict[str, Any]]:
    anchor_ticker = str(anchor["ticker"])
    anchor_rows = snapshot.get(anchor_ticker) or []
    anchor_vector = _return_vector(
        rows=anchor_rows,
        index=indices.get(anchor_ticker, {}),
        prior_dates=prior_dates,
    )
    if anchor_vector is None:
        return []

    members: list[dict[str, Any]] = []
    for ticker in sorted(sector_entries):
        if ticker == anchor_ticker:
            continue
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < CORR_LOOKBACK_DAYS + 1:
            continue
        vector_key = (signal_date, ticker)
        if vector_key not in vector_cache:
            vector_cache[vector_key] = _return_vector(
                rows=rows,
                index=indices.get(ticker, {}),
                prior_dates=prior_dates,
            )
        member_vector = vector_cache[vector_key]
        if member_vector is None or len(member_vector) != len(anchor_vector):
            continue
        corr = _pearson_corr(anchor_vector, member_vector)
        if corr is None or corr < MIN_CLUSTER_CORRELATION:
            continue
        daily_return = framework._daily_return(rows, idx)
        volume_ratio = framework._volume_ratio(rows, idx)
        adv20 = framework._avg_dollar_volume(rows, idx)
        if daily_return is None or volume_ratio is None or adv20 is None:
            continue
        members.append(
            {
                "ticker": ticker,
                "cluster_corr_to_anchor": round(corr, 6),
                "cluster_member_signal_return": round(daily_return, 6),
                "cluster_member_volume_ratio_20d": round(volume_ratio, 6),
                "cluster_member_avg_dollar_volume_20d": round(adv20, 2),
            }
        )
    members.sort(
        key=lambda row: (
            -float(row["cluster_corr_to_anchor"]),
            -float(row["cluster_member_avg_dollar_volume_20d"]),
            str(row["ticker"]),
        )
    )
    return members[:MAX_CORRELATED_MEMBERS_PER_ANCHOR]


def _cluster_context(
    *,
    anchor: dict[str, Any],
    members: list[dict[str, Any]],
    signal_date: str,
) -> dict[str, Any] | None:
    if len(members) + 1 < MIN_CLUSTER_MEMBER_COUNT:
        return None
    returns = [float(anchor["anchor_signal_return"])] + [
        float(member["cluster_member_signal_return"]) for member in members
    ]
    volume_ratios = [float(anchor["anchor_volume_ratio_20d"])] + [
        float(member["cluster_member_volume_ratio_20d"]) for member in members
    ]
    positive_fraction = sum(1 for value in returns if value > 0.0) / len(returns)
    median_return = _median(returns)
    avg_volume_ratio = sum(volume_ratios) / len(volume_ratios)
    if median_return is None:
        return None
    if positive_fraction < MIN_CLUSTER_POSITIVE_FRACTION:
        return None
    if median_return < MIN_CLUSTER_MEDIAN_RETURN:
        return None
    if avg_volume_ratio < MIN_CLUSTER_AVG_VOLUME_RATIO_20D:
        return None
    return {
        "date": signal_date,
        "anchor_ticker": anchor["ticker"],
        "anchor_signal_return": anchor["anchor_signal_return"],
        "anchor_relative_vs_spy": anchor["anchor_relative_vs_spy"],
        "anchor_score": anchor["anchor_score"],
        "member_count_including_anchor": len(returns),
        "cluster_positive_fraction": round(positive_fraction, 6),
        "cluster_median_return": round(median_return, 6),
        "cluster_avg_volume_ratio_20d": round(avg_volume_ratio, 6),
        "top_member_tickers": [member["ticker"] for member in members[:8]],
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_row_from_member(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
    anchor: dict[str, Any],
    context: dict[str, Any],
    member: dict[str, Any],
    core_tickers: set[str],
    ab_entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    ticker = str(member["ticker"])
    if ticker in core_tickers:
        return None
    metrics = _candidate_metrics(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
    )
    if metrics is None:
        return None
    candidate_score = (
        1.80 * float(member["cluster_corr_to_anchor"])
        + 1.15 * float(context["cluster_positive_fraction"])
        + 12.0 * float(context["cluster_median_return"])
        + 2.0 * float(metrics["candidate_relative_vs_spy"])
        + 0.65 * float(metrics["candidate_close_location"])
        + 0.45 * float(metrics["candidate_ret20_excess_spy"])
        + 0.25 * math.log10(max(float(metrics["candidate_avg_dollar_volume_20d"]), 1.0))
        - 0.45 * max(float(metrics["candidate_ret5"]), 0.0)
        - 0.20 * float(metrics["candidate_realized_vol_20d"])
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "candidate_score": round(candidate_score, 6),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "same_day_ab_entry_count": len(ab_entries),
        "same_day_ab_overlap": bool(ab_entries),
        "same_ticker_ab_overlap": any(entry.get("ticker") == ticker for entry in ab_entries),
        "anchor": anchor,
        "cluster_context": context,
        "cluster_corr_to_anchor": member["cluster_corr_to_anchor"],
        **metrics,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = _core_entries_by_date(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    all_dates = framework.shadow._trading_dates(snapshot)
    date_pos = {date_value: pos for pos, date_value in enumerate(all_dates)}
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "days_without_core_anchor": 0,
        "anchor_candidates_seen": 0,
        "anchors_passing_gate": 0,
        "cluster_context_days": 0,
        "cluster_contexts": 0,
        "raw_candidate_rows": 0,
        "missing_prior_history_days": 0,
    }
    vector_cache: dict[tuple[str, str], list[float] | None] = {}
    for signal_date in dates:
        signal_pos = date_pos.get(signal_date)
        if signal_pos is None or signal_pos < CORR_LOOKBACK_DAYS + 1:
            context_scan["missing_prior_history_days"] += 1
            continue
        ab_entries = entries_by_date.get(signal_date, [])
        core_tickers = {
            str(entry.get("ticker") or "").upper()
            for entry in ab_entries
            if entry.get("ticker")
        }
        if not core_tickers:
            context_scan["days_without_core_anchor"] += 1
            continue
        prior_dates = all_dates[signal_pos - CORR_LOOKBACK_DAYS : signal_pos]
        anchors: list[dict[str, Any]] = []
        for ticker in sorted(core_tickers):
            if ticker not in sector_entries:
                continue
            context_scan["anchor_candidates_seen"] += 1
            anchor = _anchor_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if anchor is not None:
                anchors.append(anchor)
        anchors.sort(
            key=lambda row: (
                -float(row["anchor_score"]),
                -float(row["anchor_avg_dollar_volume_20d"]),
                str(row["ticker"]),
            )
        )
        anchors = anchors[:MAX_ANCHORS_PER_DAY]
        context_scan["anchors_passing_gate"] += len(anchors)
        day_context_count = 0
        for anchor in anchors:
            members = _cluster_members_for_anchor(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                anchor=anchor,
                signal_date=signal_date,
                prior_dates=prior_dates,
                vector_cache=vector_cache,
            )
            context = _cluster_context(
                anchor=anchor,
                members=members,
                signal_date=signal_date,
            )
            if context is None:
                continue
            contexts.append(context)
            day_context_count += 1
            for member in members:
                row = _candidate_row_from_member(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    signal_date=signal_date,
                    anchor=anchor,
                    context=context,
                    member=member,
                    core_tickers=core_tickers,
                    ab_entries=ab_entries,
                )
                if row is not None:
                    candidates.append(row)
        if day_context_count:
            context_scan["cluster_context_days"] += 1
            context_scan["cluster_contexts"] += day_context_count
    context_scan["raw_candidate_rows"] = len(candidates)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["cluster_context"]["cluster_positive_fraction"]),
            -float(row["cluster_corr_to_anchor"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, contexts, context_scan


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
    failed = list(gate.get("failed_reasons") or [])
    if (
        float(aggregate["expected_value_score_delta_sum"] or 0.0)
        <= ACCEPTED_PEER_SHOCK_COMPARATOR["expected_value_score_delta_sum"]
    ):
        failed.append("accepted_peer_shock_ev_not_beaten")
    if (
        float(aggregate["total_pnl_delta_sum"] or 0.0)
        <= ACCEPTED_PEER_SHOCK_COMPARATOR["total_pnl_delta_sum"]
    ):
        failed.append("accepted_peer_shock_pnl_not_beaten")
    gate.update(
        {
            "passed": not failed,
            "decision": (
                "positive_replay_lead_not_promoted_dynamic_corr_cluster_breadth"
                if not failed
                else "rejected_dynamic_corr_cluster_breadth_candidate_pool"
            ),
            "failed_reasons": failed,
            "accepted_peer_shock_comparator": ACCEPTED_PEER_SHOCK_COMPARATOR,
        }
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    passed = bool(gate4["passed"])
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    rationale = (
        "The dynamic correlation-cluster breadth source cleared the numeric "
        "three-window gate and beat the accepted peer-shock comparator, but no "
        "shared helper was promoted, so it remains a replay lead."
        if passed
        else (
            "The dynamic correlation-cluster breadth source did not clear Gate "
            "4 or the accepted peer-shock comparator. Cluster breadth around "
            "core-flow anchors appears to relabel broad beta/flow sponsorship "
            "instead of creating incremental replacement candidates."
        )
    )
    brier = round(
        (PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2,
        6,
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": gate4["decision"],
            "hypothesis": (
                "Dynamic correlation-cluster breadth anchored on same-day "
                "core-flow entries can identify free-OHLCV relation candidates "
                "that outperform the accepted single-pair peer-shock helper "
                "without adding noisy tickers."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "mechanism_family": "production_visible_free_ohlcv_relation_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260606-025",
                "exp-20260608-025",
                "exp-20260610-022",
                "exp-20260609-019",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "free_ohlcv_dynamic_correlation_cluster_breadth",
            "prediction": PREDICTION,
            "calibration": {
                "predicted_success_probability": PREDICTION["success_probability"],
                "actual_gate4_passed": passed,
                "failure_modes_observed": gate4["failed_reasons"],
                "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
                "brier_score": brier,
            },
            "production_impact": PRODUCTION_IMPACT,
            "interpretation": rationale,
            "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
            "accepted_peer_shock_comparator": ACCEPTED_PEER_SHOCK_COMPARATOR,
            "parameters": {
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "hold_days": HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
                "corr_lookback_days": CORR_LOOKBACK_DAYS,
                "min_corr_observations": MIN_CORR_OBSERVATIONS,
                "min_cluster_correlation": MIN_CLUSTER_CORRELATION,
                "min_cluster_member_count": MIN_CLUSTER_MEMBER_COUNT,
                "min_cluster_positive_fraction": MIN_CLUSTER_POSITIVE_FRACTION,
                "min_cluster_median_return": MIN_CLUSTER_MEDIAN_RETURN,
                "min_cluster_avg_volume_ratio_20d": MIN_CLUSTER_AVG_VOLUME_RATIO_20D,
                "max_anchors_per_day": MAX_ANCHORS_PER_DAY,
                "max_correlated_members_per_anchor": MAX_CORRELATED_MEMBERS_PER_ANCHOR,
                "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
                "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
                "min_candidate_relative_vs_spy": MIN_CANDIDATE_RELATIVE_VS_SPY,
                "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
                "min_candidate_volume_ratio_20d": MIN_CANDIDATE_VOLUME_RATIO_20D,
                "max_candidate_volume_ratio_20d": MAX_CANDIDATE_VOLUME_RATIO_20D,
                "max_candidate_ret5": MAX_CANDIDATE_RET5,
                "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
                "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
                "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
                "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
            },
            "pre_run_questions": {
                "1_alpha_hypothesis": (
                    "candidate-pool alpha: when a same-day core-flow anchor is "
                    "confirmed by broad dynamic-correlation cluster breadth, "
                    "liquid non-core cluster members may be better replacement "
                    "candidates than arbitrary broad-market additions."
                ),
                "2_history_check": {
                    "exp-20260606-025": (
                        "Accepted rolling-correlation peer shock shared helper "
                        "set the relation comparator at +0.3845 EV and "
                        "+$6,107.66 PnL."
                    ),
                    "exp-20260608-025": (
                        "Same-industry characteristic peer shock was rejected; "
                        "this uses dynamic correlation plus core-flow anchoring "
                        "instead of static industry/characteristic peers."
                    ),
                    "exp-20260610-022": (
                        "Rolling lead-lag peer underreaction was rejected; this "
                        "tests same-day cluster breadth confirmation instead of "
                        "lagged one-peer underreaction."
                    ),
                    "exp-20260609-019": (
                        "Industry breadth acceleration was rejected; this avoids "
                        "static sector breadth and requires a live core-flow "
                        "anchor plus PIT rolling correlations."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three canonical windows. Aggregate EV/PnL must be "
                    "positive, no EV/PnL regression window, at least 20 paper "
                    "trades across all three windows, survival >=5%, drawdown "
                    "drift <=0.5pp, concentration pass, and accepted peer-shock "
                    "comparator beaten on EV and PnL."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260612_014_dynamic_corr_cluster_breadth_leadership.py"
                ),
            },
            "post_run_reflection": {
                "why_result_happened": rationale,
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping cluster correlation, positive "
                    "fraction, member count, volume ratio, candidate extension, "
                    "top-N, hold-day, cooldown, or paper-notional thresholds on "
                    "these frozen windows."
                ),
                "new_evidence_required": (
                    "Retry only with materially new point-in-time relation "
                    "evidence, such as external free supplier/customer/ETF "
                    "constituent maps, forward replacement-value rows, or a "
                    "shared helper that demonstrates daily production parity."
                ),
            },
            "negative_reflection": (
                "If rejected, the likely reason is that same-day cluster breadth "
                "selects stocks already explained by market beta and broad flow; "
                "the accepted single-pair peer shock is more selective."
            ),
            "next_evidence_needed": (
                "Use a different free relation map or forward replacement-value "
                "data. Do not retune this cluster-breadth bundle on the same "
                "frozen windows."
            ),
            "backtest_protocol": {
                **payload["backtest_protocol"],
                "source": (
                    "docs/backtesting.md canonical three-window core replay plus "
                    "replay-only broad warehouse default-off paper overlay"
                ),
                "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
                "implementation_mode": "private_replay_scout",
            },
            "registry_persistence_note": (
                "experiment.py reservation created the ticket temp file but this "
                "Windows ACL denied atomic rename for ticket/registry writes. "
                "The recovered ticket, per-experiment artifact, card, manifest, "
                "and log preserve the run; no production code was changed."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["llm_metrics"] = {"used_llm": False, "llm_change_scope": "none"}
    payload["gate3"].update(
        {
            "candidate_pool_changed": False,
            "note": (
                "No core filter or production entry rule was added. This is an "
                "additive default-off paper candidate source, so core signals "
                "generated/survived are unchanged from baseline."
            ),
        }
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Cluster contexts | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {contexts} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                contexts=len(payload["pressure_contexts_by_window"][label]),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Dynamic Correlation-Cluster Breadth Leadership",
            "",
            "## Decision",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Rejection reason: `{payload.get('rejection_reason') or 'none'}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Prior Check",
            "",
            "- `exp-20260606-025`: accepted peer-shock comparator (+0.3845 EV, +$6,107.66 PnL).",
            "- `exp-20260608-025`: rejected static same-industry peer shock.",
            "- `exp-20260610-022`: rejected rolling lead-lag underreaction.",
            "- `exp-20260609-019`: rejected static industry breadth acceleration.",
            "",
            "## Gate 1-4 Results",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
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
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260612_014_dynamic_corr_cluster_breadth_leadership.py",
            "```",
            "",
            "No JavaScript was used.",
            "",
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
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": "private_replay_scout",
        "causal_components": [
            "dynamic_correlation_cluster",
            "same_day_core_flow_anchor",
            "cluster_breadth_confirmation",
            "non_core_candidate_exclusion",
            "next_open_paper_entry",
            "10d_exit",
            "costs",
            "three_window_gate4",
        ],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
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
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "cluster_context_count": len(payload["pressure_contexts_by_window"][label]),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": payload["pre_run_questions"],
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "registry_persistence_note": payload["registry_persistence_note"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    script_path = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(script_path),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "file_hashes": {
            _repo_rel(script_path): framework._sha256(script_path),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _update_ticket(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "owner": OWNER,
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
                "accepted": False,
                "numeric_gate4_passed": log_record["numeric_gate4_passed"],
                "calibration": payload["calibration"],
                "production_impact": PRODUCTION_IMPACT,
                "post_run_reflection": payload["post_run_reflection"],
            },
        }
    )
    framework._write_json(TICKET_JSON, ticket)


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
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_PRICE = MIN_PRICE
    framework.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    framework.MIN_CONTEXT_LIQUID_COUNT = 0
    framework.MIN_PRESSURE_DOWN_FRACTION = 0.0
    framework.MIN_PRESSURE_TAIL_DOWN_FRACTION = 0.0
    framework.MAX_PRESSURE_MEDIAN_RETURN = 1.0
    framework.MIN_PRESSURE_DISPERSION = 0.0
    framework.MAX_SPY_PRESSURE_RETURN = 1.0
    framework.MAX_QQQ_PRESSURE_RETURN = 1.0
    framework.MIN_CANDIDATE_SIGNAL_RETURN = MIN_CANDIDATE_SIGNAL_RETURN
    framework.MIN_CANDIDATE_RELATIVE_VS_SPY = MIN_CANDIDATE_RELATIVE_VS_SPY
    framework.MIN_CANDIDATE_RELATIVE_VS_QQQ = -1.0
    framework.MIN_CANDIDATE_CLOSE_LOCATION = MIN_CANDIDATE_CLOSE_LOCATION
    framework.MIN_CANDIDATE_RET20_EXCESS_SPY = MIN_CANDIDATE_RET20_EXCESS_SPY
    framework.MAX_CANDIDATE_RET5 = MAX_CANDIDATE_RET5
    framework.MAX_CANDIDATE_REALIZED_VOL_20 = MAX_CANDIDATE_REALIZED_VOL_20D
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
    framework._write_manifest = _write_manifest


_patch_framework()


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
