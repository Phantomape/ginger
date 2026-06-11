"""exp-20260611-019: distribution-pressure low-beta defensive leadership.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-pool variable: after recent SPY/QQQ distribution pressure, admit the
one liquid sector-known stock that resisted the pressure with low beta, low
realized volatility, and a mild same-day confirmation.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for import_path in (ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260611-019"
STEM = "distribution_pressure_low_beta_defensive_leadership"
TRIAL_FAMILY = "distribution_pressure_low_beta_defensive_leadership_candidate_pool"
TRIAL_VARIANT_ID = (
    "distribution_pressure_low_beta_defensive_leadership_top1_next_open_10d_v1"
)
CHANGED_VARIABLE = "distribution_pressure_low_beta_defensive_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_019_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
PRESSURE_LOOKBACK_DAYS = 8
MIN_COMBINED_DISTRIBUTION_EVENTS = 2
MAX_INDEX_DISTRIBUTION_RETURN = -0.004
MIN_INDEX_DISTRIBUTION_VOLUME_RATIO = 1.04
MAX_INDEX_DISTRIBUTION_CLOSE_LOCATION = 0.58
MIN_RECENT_SPY_QQQ_RET5 = -0.110
MAX_RECENT_SPY_QQQ_RET5 = 0.030

MIN_CANDIDATE_PRESSURE_RELATIVE_VS_SPY = 0.025
MIN_CANDIDATE_PRESSURE_RELATIVE_VS_QQQ = 0.030
MIN_CANDIDATE_PRESSURE_RETURN = -0.035
MAX_CANDIDATE_PRESSURE_DRAWDOWN = 0.090
MIN_CANDIDATE_SIGNAL_RETURN = -0.003
MAX_CANDIDATE_SIGNAL_RETURN = 0.026
MIN_CANDIDATE_RELATIVE_VS_SPY = 0.004
MIN_CANDIDATE_RELATIVE_VS_QQQ = 0.004
MIN_CANDIDATE_CLOSE_LOCATION = 0.58
MIN_CANDIDATE_VOLUME_RATIO_20D = 0.65
MAX_CANDIDATE_VOLUME_RATIO_20D = 1.90
MAX_CANDIDATE_RET5 = 0.075
MAX_CANDIDATE_RET20 = 0.220
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.020
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.030
MIN_CANDIDATE_BETA60 = 0.05
MAX_CANDIDATE_BETA60 = 0.85
MAX_CANDIDATE_REALIZED_VOL_20 = 0.060

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
    "target_trade_count": 113,
    "by_window": {
        "late_strong": {"ev": 0.0537, "pnl": 947.59},
        "mid_weak": {"ev": 0.4134, "pnl": 7582.39},
        "old_thin": {"ev": 0.0615, "pnl": 1902.93},
    },
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "cross_section_resilience_relabel",
        "accepted_distribution_comparator_not_beaten",
        "old_thin_regression",
        "thin_sample",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Accepted distribution absorption shows pressure-context stock selection "
        "can work, while generic resilience and macro stress variants failed; "
        "this tests a distinct low-beta low-volatility defensive leadership "
        "field rather than another reclaim or high-beta momentum sweep."
    ),
    "recorded_at": "2026-06-11T16:06:04+00:00",
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
    "uses_free_ohlcv_only": True,
    "uses_llm": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation envelope pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes in this scout",
        "failure_handling": "missing OHLCV, beta, pressure context, or future bars rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain a replay lead until a shared default-off helper computes the "
        "same distribution-pressure context, low-beta/low-volatility resilience "
        "fields, same-ticker overlap exclusion, next-open paper entry, 10-day "
        "exit, costs, cooldown, comparator, and concentration controls in both "
        "historical replay and daily production."
    ),
}

BASE_BUILD_PAYLOAD = framework._build_payload
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
    parsed = _float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _period_return(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    start = framework._value(rows[idx - lookback], "Close")
    end = framework._value(rows[idx], "Close")
    if start is None or end is None or start <= 0:
        return None
    return (end / start) - 1.0


def _period_drawdown(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    closes = [framework._value(row, "Close") for row in rows[idx - lookback : idx + 1]]
    if any(value is None or value <= 0 for value in closes):
        return None
    peak = float(closes[0])
    max_dd = 0.0
    for close in closes:
        close_f = float(close)
        peak = max(peak, close_f)
        max_dd = max(max_dd, (peak / close_f) - 1.0)
    return max_dd


def _beta_vs_spy(
    rows: list[dict[str, Any]],
    spy_rows: list[dict[str, Any]],
    idx: int,
    spy_idx: int,
    lookback: int = 60,
) -> float | None:
    if idx < lookback or spy_idx < lookback:
        return None
    stock_returns: list[float] = []
    spy_returns: list[float] = []
    for offset in range(lookback - 1, -1, -1):
        stock_pos = idx - offset
        spy_pos = spy_idx - offset
        stock_ret = framework._daily_return(rows, stock_pos)
        spy_ret = framework._daily_return(spy_rows, spy_pos)
        if stock_ret is None or spy_ret is None:
            return None
        stock_returns.append(float(stock_ret))
        spy_returns.append(float(spy_ret))
    spy_mean = sum(spy_returns) / len(spy_returns)
    stock_mean = sum(stock_returns) / len(stock_returns)
    variance = sum((value - spy_mean) ** 2 for value in spy_returns)
    if variance <= 0.0:
        return None
    covariance = sum(
        (stock_returns[pos] - stock_mean) * (spy_returns[pos] - spy_mean)
        for pos in range(len(stock_returns))
    )
    return covariance / variance


def _distribution_events(rows: list[dict[str, Any]], idx: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    start = max(20, idx - PRESSURE_LOOKBACK_DAYS)
    for pos in range(start, idx):
        signal_return = framework._daily_return(rows, pos)
        volume_ratio = framework._volume_ratio(rows, pos)
        close_location = framework._close_location(rows[pos])
        if signal_return is None or volume_ratio is None or close_location is None:
            continue
        if (
            signal_return <= MAX_INDEX_DISTRIBUTION_RETURN
            and volume_ratio >= MIN_INDEX_DISTRIBUTION_VOLUME_RATIO
            and close_location <= MAX_INDEX_DISTRIBUTION_CLOSE_LOCATION
        ):
            events.append(
                {
                    "date": rows[pos]["Date"],
                    "return": round(float(signal_return), 6),
                    "volume_ratio_20d": round(float(volume_ratio), 6),
                    "close_location": round(float(close_location), 6),
                }
            )
    return events


def _pressure_context(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None or spy_idx < 60 or qqq_idx < 60:
        return None
    spy_events = _distribution_events(spy_rows, spy_idx)
    qqq_events = _distribution_events(qqq_rows, qqq_idx)
    spy_ret5 = framework._ret(spy_rows, spy_idx, 5)
    qqq_ret5 = framework._ret(qqq_rows, qqq_idx, 5)
    spy_signal = framework._daily_return(spy_rows, spy_idx)
    qqq_signal = framework._daily_return(qqq_rows, qqq_idx)
    if spy_ret5 is None or qqq_ret5 is None or spy_signal is None or qqq_signal is None:
        return None
    combined = len(spy_events) + len(qqq_events)
    passed = (
        combined >= MIN_COMBINED_DISTRIBUTION_EVENTS
        and MIN_RECENT_SPY_QQQ_RET5 <= min(float(spy_ret5), float(qqq_ret5))
        and max(float(spy_ret5), float(qqq_ret5)) <= MAX_RECENT_SPY_QQQ_RET5
    )
    return {
        "date": signal_date,
        "passed": passed,
        "reason": "distribution_pressure_passed" if passed else "distribution_pressure_failed",
        "pressure_lookback_days": PRESSURE_LOOKBACK_DAYS,
        "combined_distribution_event_count": combined,
        "spy_distribution_event_count": len(spy_events),
        "qqq_distribution_event_count": len(qqq_events),
        "spy_distribution_events": spy_events,
        "qqq_distribution_events": qqq_events,
        "spy_ret5": round(float(spy_ret5), 6),
        "qqq_ret5": round(float(qqq_ret5), 6),
        "spy_signal_day_return": round(float(spy_signal), 6),
        "qqq_signal_day_return": round(float(qqq_signal), 6),
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "rule_version": RULE_VERSION,
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in framework.EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or qqq_idx < 60:
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    signal_return = framework._daily_return(rows, idx)
    spy_signal = framework._daily_return(spy_rows, spy_idx)
    qqq_signal = framework._daily_return(qqq_rows, qqq_idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx)
    beta60 = _beta_vs_spy(rows, spy_rows, idx, spy_idx, 60)
    pressure_return = _period_return(rows, idx, PRESSURE_LOOKBACK_DAYS)
    pressure_drawdown = _period_drawdown(rows, idx, PRESSURE_LOOKBACK_DAYS)
    spy_pressure_return = _period_return(spy_rows, spy_idx, PRESSURE_LOOKBACK_DAYS)
    qqq_pressure_return = _period_return(qqq_rows, qqq_idx, PRESSURE_LOOKBACK_DAYS)
    required = [
        signal_return,
        spy_signal,
        qqq_signal,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol,
        beta60,
        pressure_return,
        pressure_drawdown,
        spy_pressure_return,
        qqq_pressure_return,
    ]
    if any(value is None for value in required):
        return None

    relative_vs_spy = float(signal_return) - float(spy_signal)
    relative_vs_qqq = float(signal_return) - float(qqq_signal)
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    pressure_relative_vs_spy = float(pressure_return) - float(spy_pressure_return)
    pressure_relative_vs_qqq = float(pressure_return) - float(qqq_pressure_return)

    if pressure_relative_vs_spy < MIN_CANDIDATE_PRESSURE_RELATIVE_VS_SPY:
        return None
    if pressure_relative_vs_qqq < MIN_CANDIDATE_PRESSURE_RELATIVE_VS_QQQ:
        return None
    if pressure_return < MIN_CANDIDATE_PRESSURE_RETURN:
        return None
    if pressure_drawdown > MAX_CANDIDATE_PRESSURE_DRAWDOWN:
        return None
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if signal_return > MAX_CANDIDATE_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_CANDIDATE_RELATIVE_VS_SPY:
        return None
    if relative_vs_qqq < MIN_CANDIDATE_RELATIVE_VS_QQQ:
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20D:
        return None
    if volume_ratio > MAX_CANDIDATE_VOLUME_RATIO_20D:
        return None
    if ret5 > MAX_CANDIDATE_RET5:
        return None
    if ret20 > MAX_CANDIDATE_RET20:
        return None
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if beta60 < MIN_CANDIDATE_BETA60 or beta60 > MAX_CANDIDATE_BETA60:
        return None
    if realized_vol > MAX_CANDIDATE_REALIZED_VOL_20:
        return None

    defensive_score = (MAX_CANDIDATE_BETA60 - float(beta60)) / MAX_CANDIDATE_BETA60
    vol_score = (MAX_CANDIDATE_REALIZED_VOL_20 - float(realized_vol)) / MAX_CANDIDATE_REALIZED_VOL_20
    score = (
        2.0 * pressure_relative_vs_spy
        + 1.7 * pressure_relative_vs_qqq
        + 1.2 * defensive_score
        + 0.9 * vol_score
        + 0.55 * float(close_location)
        + 0.35 * relative_vs_spy
        + 0.25 * relative_vs_qqq
        + 0.10 * min(float(volume_ratio), 1.9)
        + 0.05 * math.log10(max(float(adv20), 1.0) / 1_000_000.0)
        - 0.35 * max(float(ret5), 0.0)
    )
    sector_meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "DISTRIBUTION_PRESSURE_LOW_BETA_DEFENSIVE_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(float(signal_return), 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": round(relative_vs_qqq, 6),
        "candidate_ret5": round(float(ret5), 6),
        "candidate_ret20": round(float(ret20), 6),
        "candidate_ret60": round(float(ret60), 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_pressure_return": round(float(pressure_return), 6),
        "candidate_pressure_drawdown": round(float(pressure_drawdown), 6),
        "candidate_pressure_relative_vs_spy": round(pressure_relative_vs_spy, 6),
        "candidate_pressure_relative_vs_qqq": round(pressure_relative_vs_qqq, 6),
        "candidate_beta60_vs_spy": round(float(beta60), 6),
        "candidate_close_location": round(float(close_location), 6),
        "candidate_avg_dollar_volume_20d": round(float(adv20), 2),
        "candidate_volume_ratio_20d": round(float(volume_ratio), 6),
        "candidate_realized_vol_20d": round(float(realized_vol), 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "distribution_pressure_low_beta_context": context,
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
    contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "pressure_days": 0,
        "non_pressure_days": 0,
        "missing_context_days": 0,
        "raw_defensive_candidates": 0,
        "days_with_raw_defensive_candidates": 0,
        "pressure_lookback_days": PRESSURE_LOOKBACK_DAYS,
        "min_combined_distribution_events": MIN_COMBINED_DISTRIBUTION_EVENTS,
        "rule_version": RULE_VERSION,
    }
    for signal_date in dates:
        context = _pressure_context(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if context is None:
            context_scan["missing_context_days"] += 1
            continue
        if not context["passed"]:
            context_scan["non_pressure_days"] += 1
            continue
        context_scan["pressure_days"] += 1
        contexts.append(context)
        day_count = 0
        for ticker in sector_entries:
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
            )
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            candidates.append(row)
            day_count += 1
        if day_count:
            context_scan["days_with_raw_defensive_candidates"] += 1
            context_scan["raw_defensive_candidates"] += day_count
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            float(row["candidate_beta60_vs_spy"]),
            float(row["candidate_realized_vol_20d"]),
            -float(row["candidate_pressure_relative_vs_spy"]),
            str(row.get("sector") or ""),
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
        <= ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"]
    ):
        failed.append("accepted_distribution_ev_not_beaten")
    if (
        float(aggregate["total_pnl_delta_sum"] or 0.0)
        <= ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"]
    ):
        failed.append("accepted_distribution_pnl_not_beaten")
    gate.update(
        {
            "passed": not failed,
            "decision": (
                "positive_replay_lead_not_promoted_distribution_pressure_low_beta_defensive_leadership"
                if not failed
                else "rejected_distribution_pressure_low_beta_defensive_leadership_candidate_pool"
            ),
            "failed_reasons": failed,
            "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
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
        "The distribution-pressure low-beta defensive leadership source beat "
        "Gate 4, but no shared daily/backtest helper was implemented, so this "
        "is only a replay lead."
        if passed
        else (
            "The distribution-pressure low-beta defensive leadership source "
            "did not clear Gate 4 or the accepted distribution-day comparator. "
            "This defensive filter either removes the convex post-pressure "
            "winners or only relabels prior cross-section resilience."
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
                "After SPY/QQQ distribution pressure, low-beta, low-volatility "
                "stocks that resisted the pressure and then confirmed mildly "
                "may have cleaner next-open 10-day replacement value than "
                "high-beta rebound leadership."
            ),
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_tail_state_candidate_pool",
            "nearby_prior_experiments": [
                "exp-20260605-033",
                "exp-20260606-027",
                "exp-20260611-007",
                "exp-20260611-011",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_free_ohlcv_low_beta_resilience_field",
            "prediction": {
                **PREDICTION,
                "actual_success": 1 if passed else 0,
                "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
                "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
                "brier_score": brier,
            },
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
            "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
            "post_run_reflection": {
                "why_result_happened": rationale,
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping low-beta, realized-volatility, "
                    "pressure-lookback, distribution-event count, mild-confirmation, "
                    "volume-ratio, top-N, hold-day, cooldown, or paper-notional "
                    "thresholds on these frozen windows."
                ),
                "new_evidence_required": (
                    "Retry only with closed forward replacement-value rows or a "
                    "materially different PIT flow/ownership/borrow/options field "
                    "that separates durable defensive sponsorship from stale "
                    "low-beta laggards."
                ),
            },
            "negative_reflection": None
            if passed
            else (
                "The likely failure mode is that low beta and low volatility "
                "favor safe-but-slow stocks after distribution pressure, while "
                "the accepted absorption helper captures the actual demand "
                "reclaim. This is not a reason to retune defensive thresholds "
                "on the frozen windows."
            ),
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool: after SPY/QQQ distribution pressure, "
                    "low-beta low-volatility stocks that resist pressure and "
                    "mildly confirm may add default-off paper replacement value."
                ),
                "2_history_check": {
                    "exp-20260605-033": (
                        "Generic cross-section pressure resilience was rejected "
                        "with aggregate EV -0.1547 and PnL -$2,932.46."
                    ),
                    "exp-20260606-027": (
                        "Macro stress resilient leadership was rejected with "
                        "thin sample and negative aggregate PnL."
                    ),
                    "exp-20260611-007": (
                        "Accepted distribution-day absorption is the closest "
                        "comparator and must be beaten before this source matters."
                    ),
                    "exp-20260611-011": (
                        "Market follow-through leadership failed; this uses "
                        "defensive low-beta pressure resistance rather than "
                        "high-volume rebound confirmation."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Use docs/backtesting.md canonical three windows. Pass only "
                    "if aggregate EV/PnL improve, no EV/PnL window regresses, "
                    "target sample >=20 across all 3 windows, survival >=5%, "
                    "drawdown drift <=0.5pp, concentration passes, and aggregate "
                    "EV/PnL beats accepted distribution-day absorption."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260611_019_distribution_pressure_low_beta_defensive_leadership.py"
                ),
            },
        }
    )
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. Low-beta defensive "
        "leadership is additive default-off paper, so core signals generated "
        "and survived are unchanged from baseline."
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Pressure days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {pressure} | {candidate_days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                pressure=scan.get("pressure_days", 0),
                candidate_days=scan.get("days_with_raw_defensive_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["accepted_distribution_comparator"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Distribution-Pressure Low-Beta Defensive Leadership",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                comparator["expected_value_score_delta_sum"],
                comparator["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": "private_replay_scout",
        "causal_components": [
            "distribution_pressure_context",
            "low_beta_resilience_gate",
            "low_volatility_gate",
            "mild_confirmation",
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
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
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
                "pressure_day_count": payload["context_scan_by_window"][label].get(
                    "pressure_days"
                ),
                "candidate_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_raw_defensive_candidates"
                ),
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
            _repo_rel(REGISTRY_JSON),
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
    framework.MIN_CANDIDATE_RELATIVE_VS_QQQ = MIN_CANDIDATE_RELATIVE_VS_QQQ
    framework.MIN_CANDIDATE_CLOSE_LOCATION = MIN_CANDIDATE_CLOSE_LOCATION
    framework.MIN_CANDIDATE_RET20_EXCESS_SPY = MIN_CANDIDATE_RET20_EXCESS_SPY
    framework.MAX_CANDIDATE_RET5 = MAX_CANDIDATE_RET5
    framework.MAX_CANDIDATE_REALIZED_VOL_20 = MAX_CANDIDATE_REALIZED_VOL_20
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


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
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
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=ticket["result"],
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
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
        },
    )


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
