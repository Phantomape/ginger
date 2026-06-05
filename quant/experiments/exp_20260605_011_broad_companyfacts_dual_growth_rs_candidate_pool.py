"""exp-20260605-011: Broad Companyfacts dual-growth + RS candidate pool.

This alpha search tests one replay-only/default-off paper candidate source:
SEC Companyfacts broad-universe realized dual growth combined with OHLCV
relative strength. It uses the broad Companyfacts data asset from
exp-20260605-007 but does not touch the active exp-20260605-010 read-only
quantile-attribution variable.

No production adapter, live order path, shared policy, ranking, sizing, exits,
LLM/news path, or watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E402
    load_warehouse_frames,
)

import exp_20260504_034_form4_satellite_overlay as overlay  # noqa: E402


EXP_ID = "exp-20260605-011"
STEM = "broad_companyfacts_dual_growth_rs_candidate_pool"
TRIAL_FAMILY = "broad_universe_companyfacts_candidate_pool"
CHANGED_VARIABLE = "broad_companyfacts_dual_growth_rs_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

GROWTH_PATH = (
    REPO_ROOT
    / "data"
    / "kova"
    / "fundamentals"
    / "companyfacts_growth_broad_universe_20260604.jsonl"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260605_011_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

INITIAL_CAPITAL = 100_000.0
PAPER_NOTIONAL = 4_000.0
HOLD_DAYS = 10
MAX_DRAWDOWN_WORSE = 0.005
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

MAX_FUNDAMENTAL_AGE_DAYS = 190
MIN_REVENUE_YOY_GROWTH = 0.15
MIN_PROFIT_YOY_GROWTH = 0.15
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET20_EXCESS_SPY = 0.02
MIN_CLOSE_LOCATION = 0.55
MIN_VOLUME_RATIO_20D = 0.90
SAME_TICKER_COOLDOWN_DAYS = 30

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

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
        "This runner changes no production code. A positive result would require "
        "a separate shared default-off Companyfacts broad-universe adapter, "
        "daily production exposure of the same PIT growth fields, warehouse/"
        "snapshot replay parity, and focused tests before any report queue, "
        "paper ledger, candidate priority, or order surface could change."
    ),
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(parsed):
        return parsed
    return None


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _configure_overlay_module() -> None:
    overlay.WINDOWS = WINDOWS
    overlay.INITIAL_CAPITAL = INITIAL_CAPITAL
    overlay.EVENT_NOTIONAL = PAPER_NOTIONAL
    overlay.HOLD_DAYS = HOLD_DAYS


def _frame_pos(frame: pd.DataFrame, day: pd.Timestamp) -> int | None:
    try:
        loc = frame.index.get_loc(day)
    except KeyError:
        return None
    if isinstance(loc, slice):
        return loc.start
    if isinstance(loc, int):
        return loc
    return int(loc[0]) if len(loc) else None


def _ret(frame: pd.DataFrame, pos: int, lookback: int) -> float | None:
    prior = pos - lookback
    if prior < 0:
        return None
    a = float(frame["Close"].iloc[prior])
    b = float(frame["Close"].iloc[pos])
    if a <= 0.0 or b <= 0.0:
        return None
    return b / a - 1.0


def _avg_dollar_volume(frame: pd.DataFrame, pos: int, lookback: int = 20) -> float | None:
    start = pos - lookback + 1
    if start < 0:
        return None
    rows = frame.iloc[start : pos + 1]
    values = rows["Close"].astype(float) * rows["Volume"].astype(float)
    return float(values.mean()) if len(values) == lookback else None


def _volume_ratio(frame: pd.DataFrame, pos: int, lookback: int = 20) -> float | None:
    start = pos - lookback + 1
    if start < 0:
        return None
    avg = float(frame["Volume"].iloc[start : pos + 1].mean())
    current = float(frame["Volume"].iloc[pos])
    if avg <= 0.0:
        return None
    return current / avg


def _close_location(frame: pd.DataFrame, pos: int) -> float | None:
    high = float(frame["High"].iloc[pos])
    low = float(frame["Low"].iloc[pos])
    close = float(frame["Close"].iloc[pos])
    if high <= low:
        return 0.5
    return (close - low) / (high - low)


def _load_growth_index() -> dict[str, dict[str, list[dict[str, Any]]]]:
    index: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    with GROWTH_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("growth_status") != "ok":
                continue
            ticker = str(row.get("ticker") or "").upper()
            canonical = str(row.get("canonical") or "")
            asof = str(row.get("asof_date") or "")[:10]
            growth = _float_or_none(row.get("yoy_growth"))
            current_value = _float_or_none(row.get("current_value"))
            prior_value = _float_or_none(row.get("prior_value"))
            if not ticker or canonical not in {"revenue", "eps_basic", "eps_diluted", "net_income"}:
                continue
            if not asof or growth is None:
                continue
            index[ticker][canonical].append(
                {
                    "ticker": ticker,
                    "canonical": canonical,
                    "asof_date": asof,
                    "yoy_growth": growth,
                    "current_value": current_value,
                    "prior_value": prior_value,
                    "current_form": row.get("current_form"),
                    "current_fy": row.get("current_fy"),
                    "current_fp": row.get("current_fp"),
                    "current_period_end": row.get("current_period_end"),
                }
            )
    for ticker_rows in index.values():
        for rows in ticker_rows.values():
            rows.sort(key=lambda item: item["asof_date"])
    return {ticker: dict(rows) for ticker, rows in index.items()}


def _latest_growth_row(
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    canonical: str,
    signal_day: str,
) -> dict[str, Any] | None:
    rows = growth_index.get(ticker, {}).get(canonical)
    if not rows:
        return None
    best = None
    for row in rows:
        if row["asof_date"] <= signal_day:
            best = row
        else:
            break
    if best is None:
        return None
    age = (pd.Timestamp(signal_day) - pd.Timestamp(best["asof_date"])).days
    if age < 0 or age > MAX_FUNDAMENTAL_AGE_DAYS:
        return None
    return {**best, "asof_age_days": age}


def _profit_growth_row(
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day: str,
) -> dict[str, Any] | None:
    candidates = [
        row
        for canonical in ("eps_diluted", "eps_basic", "net_income")
        if (row := _latest_growth_row(growth_index, ticker, canonical, signal_day)) is not None
    ]
    candidates = [
        row
        for row in candidates
        if (row.get("current_value") is not None and float(row["current_value"]) > 0.0)
        and (row.get("prior_value") is not None and float(row["prior_value"]) > 0.0)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: float(row["yoy_growth"]))


def _trading_days(frames: dict[str, pd.DataFrame], start: str, end: str) -> list[pd.Timestamp]:
    days: set[pd.Timestamp] = set()
    for frame in frames.values():
        days.update(frame.loc[start:end].index)
    return sorted(days)


def _price_map_from_frames(frames: dict[str, pd.DataFrame]) -> dict[str, list[dict[str, Any]]]:
    prices: dict[str, list[dict[str, Any]]] = {}
    for ticker, frame in frames.items():
        rows: list[dict[str, Any]] = []
        for day, row in frame.iterrows():
            rows.append(
                {
                    "date": str(day.date()),
                    "open": float(row["Open"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
            )
        prices[ticker] = rows
    return prices


def _candidate_trade(
    ticker: str,
    frame: pd.DataFrame,
    signal_day: pd.Timestamp,
    pos: int,
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    entry_pos = pos + 1
    exit_pos = entry_pos + HOLD_DAYS
    if exit_pos >= len(frame):
        return None
    entry_open = float(frame["Open"].iloc[entry_pos])
    exit_close = float(frame["Close"].iloc[exit_pos])
    if entry_open <= 0.0 or exit_close <= 0.0:
        return None
    gross_return = exit_close / entry_open - 1.0
    net_return = gross_return - ROUND_TRIP_COST_PCT
    return {
        "ticker": ticker,
        "signal_date": str(signal_day.date()),
        "entry_date": str(frame.index[entry_pos].date()),
        "exit_date": str(frame.index[exit_pos].date()),
        "entry_open": round(entry_open, 4),
        "exit_close": round(exit_close, 4),
        "notional": PAPER_NOTIONAL,
        "shares": PAPER_NOTIONAL / entry_open,
        "gross_return": round(gross_return, 6),
        "net_return": round(net_return, 6),
        "pnl": round(PAPER_NOTIONAL * net_return, 2),
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        **metadata,
    }


def _score_candidate(
    *,
    revenue_growth: float,
    profit_growth: float,
    ret20_excess_spy: float,
    close_location: float,
    volume_ratio_20d: float,
) -> float:
    return (
        min(max(revenue_growth, -1.0), 1.5)
        + min(max(profit_growth, -1.0), 1.5)
        + 4.0 * ret20_excess_spy
        + close_location
        + 0.15 * min(volume_ratio_20d, 3.0)
    )


def _candidate_for_ticker_day(
    *,
    ticker: str,
    frame: pd.DataFrame,
    spy_frame: pd.DataFrame,
    signal_day: pd.Timestamp,
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any] | None:
    pos = _frame_pos(frame, signal_day)
    spy_pos = _frame_pos(spy_frame, signal_day)
    if pos is None or spy_pos is None:
        return None
    if pos < 20 or spy_pos < 20:
        return None

    signal_day_s = str(signal_day.date())
    revenue = _latest_growth_row(growth_index, ticker, "revenue", signal_day_s)
    profit = _profit_growth_row(growth_index, ticker, signal_day_s)
    if revenue is None or profit is None:
        return None
    revenue_growth = float(revenue["yoy_growth"])
    profit_growth = float(profit["yoy_growth"])
    if revenue_growth < MIN_REVENUE_YOY_GROWTH or profit_growth < MIN_PROFIT_YOY_GROWTH:
        return None
    if revenue.get("current_value") is None or float(revenue["current_value"]) <= 0.0:
        return None

    close = float(frame["Close"].iloc[pos])
    if close < MIN_PRICE:
        return None
    adv20 = _avg_dollar_volume(frame, pos)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    volume_ratio_20d = _volume_ratio(frame, pos)
    if volume_ratio_20d is None or volume_ratio_20d < MIN_VOLUME_RATIO_20D:
        return None
    close_location = _close_location(frame, pos)
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    ret20 = _ret(frame, pos, 20)
    spy_ret20 = _ret(spy_frame, spy_pos, 20)
    if ret20 is None or spy_ret20 is None:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None

    score = _score_candidate(
        revenue_growth=revenue_growth,
        profit_growth=profit_growth,
        ret20_excess_spy=ret20_excess_spy,
        close_location=close_location,
        volume_ratio_20d=volume_ratio_20d,
    )
    metadata = {
        "companyfacts_revenue_yoy_growth": round(revenue_growth, 6),
        "companyfacts_profit_yoy_growth": round(profit_growth, 6),
        "companyfacts_profit_canonical": profit["canonical"],
        "companyfacts_revenue_asof_date": revenue["asof_date"],
        "companyfacts_profit_asof_date": profit["asof_date"],
        "companyfacts_revenue_asof_age_days": revenue["asof_age_days"],
        "companyfacts_profit_asof_age_days": profit["asof_age_days"],
        "companyfacts_revenue_form": revenue.get("current_form"),
        "companyfacts_profit_form": profit.get("current_form"),
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "close_location": round(close_location, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "volume_ratio_20d": round(volume_ratio_20d, 6),
        "candidate_score": round(score, 6),
        "source": "BROAD_COMPANYFACTS_DUAL_GROWTH_RS_PAPER",
    }
    return _candidate_trade(ticker, frame, signal_day, pos, metadata)


def _generate_candidates(
    frames: dict[str, pd.DataFrame],
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy_frame = frames.get("SPY")
    if spy_frame is None:
        raise RuntimeError("SPY missing from warehouse frames")

    selected: list[dict[str, Any]] = []
    candidates_by_window: dict[str, int] = defaultdict(int)
    selected_by_window: dict[str, int] = defaultdict(int)
    last_selected_by_ticker: dict[str, pd.Timestamp] = {}

    for label, window in WINDOWS.items():
        for day in _trading_days(frames, window["start"], window["end"]):
            day_candidates: list[dict[str, Any]] = []
            for ticker, frame in frames.items():
                if ticker == "SPY":
                    continue
                last_selected = last_selected_by_ticker.get(ticker)
                if last_selected is not None and (day - last_selected).days < SAME_TICKER_COOLDOWN_DAYS:
                    continue
                candidate = _candidate_for_ticker_day(
                    ticker=ticker,
                    frame=frame,
                    spy_frame=spy_frame,
                    signal_day=day,
                    growth_index=growth_index,
                )
                if candidate is None:
                    continue
                day_candidates.append({**candidate, "window": label})
            candidates_by_window[label] += len(day_candidates)
            if not day_candidates:
                continue
            best = max(day_candidates, key=lambda item: float(item["candidate_score"]))
            selected.append(best)
            selected_by_window[label] += 1
            last_selected_by_ticker[str(best["ticker"])] = day

    audit = {
        "raw_candidate_count": len(selected),
        "candidate_rows_before_daily_top1_by_window": dict(candidates_by_window),
        "selected_by_window": dict(selected_by_window),
        "growth_ticker_count": len(growth_index),
        "warehouse_frame_count": len(frames),
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
    }
    return selected, audit


def _aggregate_metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in rows.values()), 4
        ),
        "strategy_total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in rows.values()), 2
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in rows.values()),
        "max_drawdown_pct_max": max(
            float(row.get("max_drawdown_pct") or 0.0) for row in rows.values()
        ),
        "min_survival_rate": min(
            float(row.get("survival_rate") or 0.0) for row in rows.values()
        ),
    }


def _compare_aggregate(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    ev_before = float(before.get("expected_value_score") or 0.0)
    ev_after = float(after.get("expected_value_score") or 0.0)
    pnl_before = float(before.get("strategy_total_pnl") or 0.0)
    pnl_after = float(after.get("strategy_total_pnl") or 0.0)
    return {
        "expected_value_score_delta": round(ev_after - ev_before, 4),
        "expected_value_score_delta_pct": round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "strategy_total_pnl_delta": round(pnl_after - pnl_before, 2),
        "strategy_total_pnl_delta_pct": round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "trade_count_delta": int(after.get("trade_count") or 0)
        - int(before.get("trade_count") or 0),
        "max_drawdown_delta": round(
            float(after.get("max_drawdown_pct_max") or 0.0)
            - float(before.get("max_drawdown_pct_max") or 0.0),
            6,
        ),
    }


def _target_summary(selected: list[dict[str, Any]]) -> dict[str, Any]:
    positive_by_ticker: defaultdict[str, float] = defaultdict(float)
    pnl_by_ticker: defaultdict[str, float] = defaultdict(float)
    by_window: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "pnl": 0.0}
    )
    for trade in selected:
        ticker = str(trade.get("ticker") or "").upper()
        pnl = float(trade.get("pnl") or 0.0)
        pnl_by_ticker[ticker] += pnl
        if pnl > 0.0:
            positive_by_ticker[ticker] += pnl
        window = str(trade.get("window") or "")
        by_window[window]["count"] += 1
        by_window[window]["pnl"] += pnl

    total_positive = sum(positive_by_ticker.values())
    if total_positive > 0.0:
        shares = {
            ticker: value / total_positive
            for ticker, value in positive_by_ticker.items()
        }
        max_share = max(shares.values())
        hhi = sum(value * value for value in shares.values())
    else:
        max_share = None
        hhi = None

    return {
        "target_trade_count": len(selected),
        "target_trade_pnl_usd": round(sum(float(row.get("pnl") or 0.0) for row in selected), 2),
        "target_windows": sorted({str(row.get("window")) for row in selected}),
        "target_by_window": {
            label: {"count": int(row["count"]), "pnl": round(float(row["pnl"]), 2)}
            for label, row in sorted(by_window.items())
        },
        "max_single_positive_share": round(max_share, 6) if max_share is not None else None,
        "positive_pnl_hhi": round(hhi, 6) if hhi is not None else None,
        "positive_pnl_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(positive_by_ticker.items())
        },
        "total_pnl_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(pnl_by_ticker.items())
        },
    }


def _gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    ev_regressed_windows = [
        row["label"]
        for row in results
        if float(row["comparison"]["expected_value_score_delta"]) < 0.0
    ]
    pnl_regressed_windows = [
        row["label"]
        for row in results
        if float(row["comparison"]["strategy_total_pnl_delta"]) < 0.0
    ]
    target_trade_count = int(target_summary["target_trade_count"])
    target_windows = target_summary["target_windows"]
    max_share = target_summary["max_single_positive_share"]
    hhi = target_summary["positive_pnl_hhi"]
    failed = []
    if aggregate_comparison["expected_value_score_delta"] <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if aggregate_comparison["strategy_total_pnl_delta"] <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if ev_regressed_windows:
        failed.append("window_ev_regression")
    if pnl_regressed_windows:
        failed.append("window_pnl_regression")
    if aggregate_comparison["max_drawdown_delta"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if target_trade_count < MIN_TARGET_TRADES:
        failed.append("target_trade_count_too_low")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_low")
    if max_share is not None and max_share > MAX_SINGLE_POSITIVE_SHARE:
        failed.append("single_ticker_concentration")
    if hhi is not None and hhi > MAX_POSITIVE_HHI:
        failed.append("positive_pnl_hhi_concentration")

    passed = not failed
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if passed
        else "rejected_broad_companyfacts_dual_growth_rs_candidate_pool"
    )
    return {
        "passed": passed,
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "failed_reasons": failed,
        "windows_ev_regressed": ev_regressed_windows,
        "windows_pnl_regressed": pnl_regressed_windows,
        "drawdown_guard": f"<= {MAX_DRAWDOWN_WORSE}",
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "single_ticker_positive_share_guard": f"<= {MAX_SINGLE_POSITIVE_SHARE}",
        "positive_pnl_hhi_guard": f"<= {MAX_POSITIVE_HHI}",
        "requires_parity_before_promotion": True,
    }


def _position_field_check() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "operator_inputs/open_positions.json missing"}
    payload = _load_json(OPEN_POSITIONS_JSON, {})
    groups = []
    if isinstance(payload, dict):
        for key in ("positions", "core_positions", "observations"):
            value = payload.get(key)
            if isinstance(value, list):
                groups.extend(value)
    elif isinstance(payload, list):
        groups = payload
    missing = []
    for idx, position in enumerate(groups):
        if not isinstance(position, dict):
            missing.append({"index": idx, "reason": "not_object"})
            continue
        absent = [
            field
            for field in ("entry_date", "target_price")
            if position.get(field) in (None, "")
        ]
        if absent:
            missing.append(
                {
                    "index": idx,
                    "ticker": position.get("ticker"),
                    "missing_fields": absent,
                }
            )
    return {
        "passed": not missing,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(groups),
        "missing_entry_date_or_target_price": missing,
    }


def _append_experiment_log(record: dict[str, Any]) -> None:
    compact = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not EXPERIMENT_LOG.exists():
        EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")
        return
    lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = [
        line
        for line in lines
        if f'"experiment_id":"{EXP_ID}"' not in line
        and f'"experiment_id": "{EXP_ID}"' not in line
    ]
    lines.append(compact)
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    prediction = ticket.get("prediction") if isinstance(ticket.get("prediction"), dict) else {}
    actual_success = 1 if payload["gate4"]["passed"] else 0
    if isinstance(prediction, dict):
        prediction.update(
            {
                "actual_success": actual_success,
                "actual_ev_delta": payload["aggregate"]["comparison"]["expected_value_score_delta"],
                "actual_pnl_delta": payload["aggregate"]["comparison"]["strategy_total_pnl_delta"],
                "brier_score": round(
                    (float(prediction.get("success_probability") or 0.0) - actual_success) ** 2,
                    6,
                ),
            }
        )
    ticket.update(
        {
            "status": payload["gate4"]["status"],
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "prediction": prediction,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "decision": payload["gate4"]["decision"],
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
                "artifact": _repo_rel(ARTIFACT_MD),
                "log": _repo_rel(LOG_JSON),
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    if not isinstance(registry, dict):
        return
    experiments = registry.setdefault("experiments", [])
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXP_ID:
            item["status"] = payload["gate4"]["status"]
            item["decision"] = payload["gate4"]["decision"]
            item["updated_at"] = payload["completed_at"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXP_ID,
        "timestamp": payload["completed_at"],
        "status": payload["gate4"]["status"],
        "lane": "alpha_search",
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Tested broad SEC Companyfacts dual growth plus OHLCV relative "
            "strength as a replay-only default-off paper candidate source."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": "default_off_paper_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "broad_companyfacts_dual_growth_rs_top1_v1",
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260605-007",
            "exp-20260605-010",
            "exp-20260601-026",
            "exp-20260602-010",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "broad_universe_companyfacts_realized_growth_pit_dataset",
        "component": _repo_rel(Path(__file__)),
        "parameters": payload["parameters"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": comparison,
        "production_impact": PRODUCTION_IMPACT,
        "decision": payload["gate4"]["decision"],
        "rejection_reason": ";".join(payload["gate4"]["failed_reasons"])
        if payload["gate4"]["failed_reasons"]
        else None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "prediction": {
            **(payload.get("prediction") or {}),
            "actual_success": actual_success,
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "brier_score": round(
                (float((payload.get("prediction") or {}).get("success_probability") or 0.0) - actual_success) ** 2,
                6,
            ),
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "anti_js": "No JavaScript was used.",
    }


def _window_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            "| {label} | {count} | ${target_pnl:,.2f} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | ${pnl_delta:+,.2f} | {dd_delta:+.4f} |".format(
                label=row["label"],
                count=row["target_trade_count"],
                target_pnl=float(row["target_trade_pnl_usd"]),
                before_ev=float(row["before"]["expected_value_score"]),
                after_ev=float(row["after"]["expected_value_score"]),
                ev_delta=float(row["comparison"]["expected_value_score_delta"]),
                pnl_delta=float(row["comparison"]["strategy_total_pnl_delta"]),
                dd_delta=float(row["comparison"]["max_drawdown_delta"]),
            )
        )
    return "\n".join(lines)


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} Broad Companyfacts Dual-Growth RS Candidate Pool",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Gate 4",
        "",
    ]
    for key, value in payload["gate4"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_011_broad_companyfacts_dual_growth_rs_candidate_pool.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    _configure_overlay_module()
    completed_at = _utc_now()
    universe = get_universe()
    growth_index = _load_growth_index()
    frames = load_warehouse_frames()
    prices = _price_map_from_frames(frames)
    candidates, candidate_audit = _generate_candidates(frames, growth_index)

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected = [
            trade
            for trade in candidates
            if trade.get("window") == label
            and window["start"] <= str(trade.get("signal_date")) <= window["end"]
        ]
        event_curve = overlay._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before = overlay._core_metrics(result)
        after = overlay._combined_metrics(result, event_curve, selected)
        before_metrics[label] = before
        after_metrics[label] = after
        comparison = {
            "expected_value_score_delta": round(
                float(after.get("expected_value_score") or 0.0)
                - float(before.get("expected_value_score") or 0.0),
                4,
            ),
            "strategy_total_pnl_delta": round(
                float(after.get("total_pnl") or 0.0)
                - float(before.get("total_pnl") or 0.0),
                2,
            ),
            "max_drawdown_delta": round(
                float(after.get("max_drawdown_pct") or 0.0)
                - float(before.get("max_drawdown_pct") or 0.0),
                6,
            ),
        }
        results.append(
            {
                "label": label,
                "window": window,
                "before": before,
                "after": after,
                "comparison": comparison,
                "target_trade_count": len(selected),
                "target_trade_pnl_usd": round(
                    sum(float(trade.get("pnl") or 0.0) for trade in selected),
                    2,
                ),
                "selected_trades": selected,
            }
        )

    aggregate_before = _aggregate_metrics(before_metrics)
    aggregate_after = _aggregate_metrics(after_metrics)
    aggregate_comparison = _compare_aggregate(aggregate_before, aggregate_after)
    target_summary = _target_summary(candidates)
    gate4 = _gate4(aggregate_comparison, results, target_summary)

    payload = {
        "experiment_id": EXP_ID,
        "completed_at": completed_at,
        "anti_js": "No JavaScript was used.",
        "lane": "alpha_search",
        "preflight": {
            "alpha_hypothesis": (
                "Broad SEC Companyfacts dual realized growth plus OHLCV relative "
                "strength can add a cleaner default-off paper candidate source "
                "beyond the curated Fundamental Growth RS universe."
            ),
            "category": "entry_candidate_pool",
            "nearby_prior_experiments": [
                "exp-20260605-007",
                "exp-20260605-010",
                "exp-20260601-026",
                "exp-20260602-010",
            ],
            "single_causal_variable": CHANGED_VARIABLE,
            "success_standard": (
                "Canonical three-window before/after aggregate EV and PnL must "
                "improve, no window EV/PnL regression, max drawdown drift <= "
                f"{MAX_DRAWDOWN_WORSE}, target trades >= {MIN_TARGET_TRADES}, "
                "all three windows represented, concentration within guardrails."
            ),
            "reproducible_if_failed": True,
        },
        "parameters": {
            "paper_notional": PAPER_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "max_fundamental_age_days": MAX_FUNDAMENTAL_AGE_DAYS,
            "min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
            "min_profit_yoy_growth": MIN_PROFIT_YOY_GROWTH,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "daily_selection": "top_1_by_fixed_growth_rs_score",
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "trade_enabled": False,
        },
        "source_data": {
            "growth_path": _repo_rel(GROWTH_PATH),
            "warehouse": "data/experiments/exp-20260519-030/warehouse_main.sqlite",
            "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        },
        "gate2": _position_field_check(),
        "gate3": {
            "survival_rate_unchanged": True,
            "min_survival_rate": aggregate_before["min_survival_rate"],
            "note": "Replay-only paper candidate source does not alter core signal filters.",
        },
        "candidate_audit": candidate_audit,
        "target_summary": target_summary,
        "results": results,
        "aggregate": {
            "before": aggregate_before,
            "after": aggregate_after,
            "comparison": aggregate_comparison,
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "prediction": (_load_json(TICKET_JSON, {}).get("prediction") or {}),
        "next_retry_requires": [
            "closed forward replacement-value rows",
            "proof that broad Companyfacts growth is incremental to ret20 momentum",
            "shared default-off adapter and parity tests before promotion",
            "avoid threshold/scalar retunes on the same frozen sample",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(GROWTH_PATH),
        ],
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _experiment_log_record(payload))
    _write_json(BEFORE_JSON, payload["aggregate"]["before"])
    _write_json(AFTER_JSON, payload["aggregate"]["after"])
    _write_artifact(payload)
    _update_ticket(payload)
    _update_registry(payload)
    _append_experiment_log(_experiment_log_record(payload))
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": {
                    "target_trade_count": payload["target_summary"]["target_trade_count"],
                    "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
                    "max_single_positive_share": payload["target_summary"][
                        "max_single_positive_share"
                    ],
                    "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
                },
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
