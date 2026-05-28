"""exp-20260528-037: ticker accumulation-quality breakout sleeve.

This alpha search tests one stock-only, free-OHLCV candidate-pool source:
breakouts whose price and on-balance volume both make a fresh 20-day high.
The sleeve is default-off paper only, admits at most one candidate per signal
day, enters at the next available open, and exits after ten trading days.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260426_volatility_contraction_breakout_shadow as ohlcv_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260528-037"
STEM = "ticker_accumulation_quality_breakout"
TRIAL_FAMILY = "ticker_accumulation_quality_breakout_candidate_pool"
CHANGED_VARIABLE = "ticker_accumulation_quality_breakout_candidate_source_v1"
RULE_VERSION = "obv_price_breakout_stock_only_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BREAKOUT_LOOKBACK_DAYS = 20
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
MIN_DOLLAR_VOLUME = 40_000_000.0
MIN_SIGNAL_CLOSE_LOCATION = 0.70
MIN_RS_20D_VS_SPY = 0.0
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EXCLUDED_TICKERS = {
    "ARKX",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = ohlcv_helper
    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(ohlcv_helper, name):
            setattr(ohlcv_helper, name, None)


def _avg(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start = ohlcv_helper._value(rows[start_idx], "Close")
    end = ohlcv_helper._value(rows[end_idx], "Close")
    if not start or end is None:
        return None
    return (end / start) - 1.0


def _prior_high(rows: list[dict[str, Any]], idx: int, days: int, field: str) -> float | None:
    if idx < days:
        return None
    values = [ohlcv_helper._value(row, field) for row in rows[idx - days:idx]]
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return max(clean)


def _prior_average(rows: list[dict[str, Any]], idx: int, days: int, field: str) -> float | None:
    if idx < days:
        return None
    values = [ohlcv_helper._value(row, field) for row in rows[idx - days:idx]]
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return _avg(clean)


def _close_location(row: dict[str, Any]) -> float | None:
    high = ohlcv_helper._value(row, "High")
    low = ohlcv_helper._value(row, "Low")
    close = ohlcv_helper._value(row, "Close")
    if high is None or low is None or close is None or high <= low:
        return None
    return (close - low) / (high - low)


def _obv_series(rows: list[dict[str, Any]]) -> list[float | None]:
    out: list[float | None] = []
    obv = 0.0
    previous_close: float | None = None
    for row in rows:
        close = ohlcv_helper._value(row, "Close")
        volume = ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            out.append(None)
            previous_close = close
            continue
        if previous_close is not None:
            if close > previous_close:
                obv += float(volume)
            elif close < previous_close:
                obv -= float(volume)
        out.append(obv)
        previous_close = close
    return out


def _audit_snapshot_fields(
    snapshots: dict[str, dict[str, list[dict[str, Any]]]]
) -> dict[str, Any]:
    required = ["Date", "Open", "High", "Low", "Close", "Volume"]
    missing: Counter[str] = Counter()
    row_count = 0
    for snapshot in snapshots.values():
        for ticker, rows in snapshot.items():
            if ticker in EXCLUDED_TICKERS:
                continue
            for row in rows:
                row_count += 1
                for field in required:
                    if row.get(field) in (None, ""):
                        missing[field] += 1
    return {
        "required_fields": required,
        "stock_row_count": row_count,
        "missing_by_field": dict(sorted(missing.items())),
        "passed": row_count > 0 and not missing,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = ohlcv_helper._baseline_entries(before_result)
    dates = [
        date
        for date in ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    spy_rows = ohlcv_helper._series(snapshot, "SPY")
    spy_index = ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        rows = ohlcv_helper._series(snapshot, ticker)
        idx_by_date = ohlcv_helper._row_index(rows)
        obv_values = _obv_series(rows)
        for date in dates:
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            min_idx = max(BREAKOUT_LOOKBACK_DAYS, MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS)
            if idx is None or spy_idx is None or idx < min_idx or spy_idx < RELATIVE_STRENGTH_DAYS:
                audit["insufficient_history"] += 1
                continue

            close = ohlcv_helper._value(rows[idx], "Close")
            volume = ohlcv_helper._value(rows[idx], "Volume")
            if not close or not volume:
                audit["missing_close_or_volume"] += 1
                continue
            dollar_volume = float(close) * float(volume)
            if dollar_volume < MIN_DOLLAR_VOLUME:
                audit["low_dollar_volume"] += 1
                continue

            price_prior_high = _prior_high(rows, idx, BREAKOUT_LOOKBACK_DAYS, "High")
            ma50 = _prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if not price_prior_high or not ma50:
                audit["missing_price_context"] += 1
                continue
            if close <= price_prior_high or close <= ma50:
                audit["not_price_breakout_or_above_ma50"] += 1
                continue

            obv = obv_values[idx]
            prior_obv_values = [
                value
                for value in obv_values[idx - BREAKOUT_LOOKBACK_DAYS:idx]
                if isinstance(value, (int, float))
            ]
            if obv is None or len(prior_obv_values) < BREAKOUT_LOOKBACK_DAYS:
                audit["missing_obv_context"] += 1
                continue
            prior_obv_high = max(prior_obv_values)
            if obv <= prior_obv_high:
                audit["obv_not_breaking_out"] += 1
                continue

            signal_close_location = _close_location(rows[idx])
            if (
                signal_close_location is None
                or signal_close_location < MIN_SIGNAL_CLOSE_LOCATION
            ):
                audit["weak_signal_close_location"] += 1
                continue

            ret20 = _close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
            spy_ret20 = _close_return(spy_rows, spy_idx - RELATIVE_STRENGTH_DAYS, spy_idx)
            if ret20 is None or spy_ret20 is None:
                audit["missing_relative_strength"] += 1
                continue
            rs20_vs_spy = ret20 - spy_ret20
            if rs20_vs_spy <= MIN_RS_20D_VS_SPY:
                audit["rs20_not_positive_vs_spy"] += 1
                continue

            ab_entries = entries_by_date.get(date, [])
            obv_breakout_ratio = (float(obv) - prior_obv_high) / max(abs(prior_obv_high), 1.0)
            distance_above_price_high = (float(close) / price_prior_high) - 1.0
            candidates.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "close": base._round(close, 4),
                    "volume": base._round(volume, 2),
                    "dollar_volume": base._round(dollar_volume, 2),
                    "ma50": base._round(ma50, 4),
                    "price_prior_high_20d": base._round(price_prior_high, 4),
                    "distance_above_price_high_20d": base._round(
                        distance_above_price_high, 6
                    ),
                    "obv": base._round(obv, 2),
                    "prior_obv_high_20d": base._round(prior_obv_high, 2),
                    "obv_breakout_ratio_20d": base._round(obv_breakout_ratio, 6),
                    "signal_close_location": base._round(signal_close_location, 6),
                    "ret20": base._round(ret20, 6),
                    "spy_ret20": base._round(spy_ret20, 6),
                    "rs20_vs_spy": base._round(rs20_vs_spy, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "known_at": "after_signal_date_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["obv_breakout_ratio_20d"]),
            -float(row["rs20_vs_spy"]),
            -float(row["signal_close_location"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "audit_reject_counts": dict(sorted(audit.items())),
    }


def _select_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        date = str(row.get("date") or "")
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = base._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[date] += 1
    return selected, filtered


def _target_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    by_window_pnl: dict[str, float] = {}
    for label, trades in target_trades_by_window.items():
        by_window_pnl[label] = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl

    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_positive_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    positive_hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [
            label for label, trades in target_trades_by_window.items() if trades
        ],
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "by_window_pnl": by_window_pnl,
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "positive_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_pnl_share": max_positive_share,
        "positive_pnl_hhi": positive_hhi,
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": base._round(ev_before, 6),
        "after_expected_value_score_sum": base._round(ev_after, 6),
        "expected_value_score_delta_sum": base._round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": base._round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": base._round(pnl_before, 2),
        "after_total_pnl_sum": base._round(pnl_after, 2),
        "total_pnl_delta_sum": base._round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": base._round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "windows_ev_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": base._round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def _gate4(
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    min_survival: float,
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(base.WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )
    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_improved"] != len(base.WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    return {
        "passed": passed,
        "failed_reasons": failed,
        "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
        "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "survival_guard_passed": min_survival >= 0.05,
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


def _aggregate_result_for_judge(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total_return = sum(
        float(row.get("strategy_total_return_pct") or 0.0)
        for row in metrics_by_window.values()
    )
    return {
        "expected_value_score": base._round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics_by_window.values()),
            6,
        ),
        "total_pnl": base._round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics_by_window.values()),
            2,
        ),
        "max_drawdown_pct": base._round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics_by_window.values()),
            6,
        ),
        "survival_rate": base._round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics_by_window.values()),
            6,
        ),
        "total_trades": sum(int(row.get("trade_count") or 0) for row in metrics_by_window.values()),
        "win_rate": None,
        "sharpe_daily": None,
        "benchmarks": {"strategy_total_return_pct": base._round(total_return, 6)},
    }


def _field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    total = len(rows)
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present": present,
            "missing": total - present,
            "coverage_ratio": base._round(present / total, 6) if total else None,
        }
    return out


def _build_payload() -> dict[str, Any]:
    _configure_base_module()
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    candidate_day_counts: "OrderedDict[str, int]" = OrderedDict()
    candidate_audits: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    snapshots: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = ohlcv_helper._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = ohlcv_helper._load_snapshot(cfg["snapshot"])
        snapshots[label] = snapshot
        candidates, candidate_audit = _candidate_rows_for_window(
            snapshot,
            cfg,
            universe,
            before_result,
        )
        selected_trades, filtered_candidates = _select_paper_trades(snapshot, candidates)
        overlay = base._overlay_from_paper_trades(before_result, selected_trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        candidate_day_counts[label] = len({row["date"] for row in candidates})
        candidate_audits[label] = candidate_audit
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "raw_candidate_days": candidate_day_counts[label],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = _aggregate(window_rows)
    target_summary = _target_trade_summary(target_trades_by_window)
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    gate4 = _gate4(aggregate, target_summary, min_survival)
    decision = (
        "accepted_candidate_ticker_accumulation_quality_breakout"
        if gate4["passed"]
        else "rejected_ticker_accumulation_quality_breakout"
    )
    all_target_trades = [
        trade
        for trades in target_trades_by_window.values()
        for trade in trades
    ]
    snapshot_field_audit = _audit_snapshot_fields(snapshots)
    if not snapshot_field_audit["passed"]:
        raise RuntimeError(f"Gate 2 OHLCV field check failed: {snapshot_field_audit}")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prediction = {
        "success_probability": 0.31,
        "expected_ev_delta": 0.20,
        "expected_pnl_delta": 3000.0,
        "main_failure_modes": [
            "nearby_down_volume_absorption_failure",
            "thin_sample",
            "late_strong_regression",
            "overlap_with_existing_vbb",
        ],
        "confidence_reason": (
            "Meta research favors production-visible candidate-pool alpha, but "
            "recent OHLCV source refinements have failed often."
        ),
        "recorded_at": "2026-05-28T23:10:45+00:00",
    }
    actual_success = 1 if gate4["passed"] else 0
    prediction["brier_score"] = round((prediction["success_probability"] - actual_success) ** 2, 6)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Stock-only ticker-level accumulation-quality breakouts may improve "
            "candidate-pool replacement value versus the core stack using only "
            "free OHLCV fields."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_variant_id": "ticker_accumulation_quality_breakout_v1",
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260527-011",
            "exp-20260528-034",
            "exp-20260528-035",
            "exp-20260528-036",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_ohlcv_ticker_level_obv_price_breakout_candidate_source",
        "prediction": prediction,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only OHLCV known after the signal-date close; paper "
                "entry is the next available open with production entry slippage; "
                "exit is ten trading days after the signal with target-side sell "
                "slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "base_universe_count": len(universe),
            "stock_excluded_tickers": sorted(EXCLUDED_TICKERS),
            "paper_notional_usd": base.BASE_NOTIONAL_USD,
            "hold_days": base.HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "breakout_lookback_days": BREAKOUT_LOOKBACK_DAYS,
            "moving_average_days": MOVING_AVERAGE_DAYS,
            "relative_strength_days": RELATIVE_STRENGTH_DAYS,
            "min_dollar_volume": MIN_DOLLAR_VOLUME,
            "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
            "min_rs20_vs_spy": MIN_RS_20D_VS_SPY,
            "source_definition": [
                "stock ticker only",
                "close above prior 20-day high",
                "close above prior 50-day moving average",
                "on-balance volume above prior 20-day OBV high",
                "signal-day close location >= 0.70",
                "20-day return exceeds SPY",
                "dollar volume >= 40 million",
            ],
            "selection_rank": [
                "signal_date",
                "obv_breakout_ratio_20d desc",
                "rs20_vs_spy desc",
                "signal_close_location desc",
                "dollar_volume desc",
                "ticker asc",
            ],
            "locked_variables": [
                "core universe membership",
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "watchlists",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / entry: stock breakouts confirmed by both price "
                "and OBV new highs should represent cleaner accumulation than "
                "price-only or sector-breadth retreads."
            ),
            "2_history_check": {
                "exp-20260527-011": (
                    "Down-volume absorption used prior 10-day up/down volume "
                    "dominance and failed aggregate EV/PnL. This run does not "
                    "retune those thresholds; it tests OBV new-high confirmation."
                ),
                "exp-20260528-034_to_036": (
                    "Industry/sector/breadth refinements failed; this run avoids "
                    "sector/industry routing and uses ticker-level confirmation."
                ),
                "exp-20260528-018_and_022": (
                    "VBB support scouts succeeded on market breadth and high "
                    "close. This run is a separate stock-only source, not a VBB "
                    "notional support retune."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                "3/3 EV-improved windows; no PnL-regressed window; >=20 paper "
                "trades across all 3 windows; drawdown drift <=0.5pp; survival "
                ">=5%; concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260528_037_ticker_accumulation_quality_breakout.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{base._repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "snapshot_fields": snapshot_field_audit,
            "target_trade_field_coverage": _field_coverage(
                all_target_trades,
                [
                    "ticker",
                    "signal_date",
                    "entry_date",
                    "exit_date",
                    "entry_price",
                    "exit_price",
                    "pnl",
                    "known_at",
                    "obv",
                    "prior_obv_high_20d",
                    "signal_close_location",
                    "rs20_vs_spy",
                ],
            ),
            "runtime_fields": [
                "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
                "SPY OHLCV rows for same-window relative strength",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
            "note": (
                "The sleeve uses only same-day and trailing OHLCV fields plus "
                "next-open/exit prices available to the replay. It does not ask "
                "LLM or production to infer hidden fields."
            ),
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": base._round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter or live entry rule was added. The target source "
                "is additive default-off paper, so core survival is unchanged."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "judge_before_aggregate": _aggregate_result_for_judge(before_metrics),
        "judge_after_aggregate": _aggregate_result_for_judge(after_metrics),
        "raw_candidate_counts": raw_candidate_counts,
        "candidate_day_counts": candidate_day_counts,
        "candidate_audits": candidate_audits,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "A retained result would still require a shared default-off paper "
                "adapter and parity tests before any daily report or live/default "
                "behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because candidate-level replay coverage "
            "remains sparse; skipped more Companyfacts scalars because the "
            "playbook asks for forward rows instead of frozen-sample retunes; "
            "skipped sector/industry routing because the latest variants failed "
            "Gate 4. This uses a separate stock-level free-OHLCV source."
        ),
        "interpretation": (
            "The ticker accumulation-quality breakout sleeve cleared Gate 4 as "
            "a replay-only lead, but no production/shared policy was promoted."
            if gate4["passed"]
            else (
                "The ticker accumulation-quality breakout sleeve did not clear "
                "Gate 4. Do not promote it or retry nearby OBV/price-breakout "
                "thresholds on the same frozen windows without forward paper "
                "rows or an orthogonal source-quality field."
            )
        ),
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "If revisited, use forward replacement-value rows or a materially "
            "new free-data source such as official short-interest/ownership "
            "context; do not just retune OBV or close-location thresholds."
        ),
        "related_files": [
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(BEFORE_AGG_JSON),
            base._repo_rel(AFTER_AGG_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(DOC_TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    title = "# exp-20260528-037 Ticker Accumulation-Quality Breakout"
    return "\n".join(
        [
            title,
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits stock-only OBV-new-high plus price-breakout candidates, top-1 per day, next-open entry, ten-trading-day exit.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Ticker accumulation-quality breakout sleeve",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_json(DOC_TICKET_JSON, ticket_payload)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
