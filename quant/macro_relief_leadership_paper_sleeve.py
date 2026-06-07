"""Default-off macro relief leadership paper sleeve.

This shared helper promotes the accepted exp-20260606-019 replay lead into a
production-visible forward observation boundary. On official CPI/FOMC/NFP
release days where both SPY and QQQ rally and close high in their daily ranges,
the two highest-scoring liquid stock leaders are admitted as next-open paper
candidates with a fixed 10-trading-day hold.

It emits paper candidates and ledger state only; it never emits live orders and
never changes core signal generation, ranking, sizing, exits, heat, LLM, or
news behavior.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import data_artifact_path
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage


SLEEVE_NAME = "MACRO_RELIEF_LEADERSHIP_PAPER"
RULE_VERSION = "macro_relief_top2_leadership_v1"
RELIEF_DAY_RULE_VERSION = "official_macro_relief_day_spy_qqq_close_high_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("macro_relief_leadership_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("macro_relief_leadership_paper_snapshots")

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "hold_days": 10,
    "max_paper_trades_per_day": 2,
    "same_ticker_cooldown_days": 10,
    "official_macro_event_families": ["CPI", "FOMC", "NFP"],
    "min_spy_relief_return": 0.004,
    "min_qqq_relief_return": 0.006,
    "min_spy_close_location": 0.65,
    "min_qqq_close_location": 0.65,
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "min_signal_return": 0.010,
    "min_relative_vs_spy": 0.008,
    "min_relative_vs_qqq": 0.004,
    "min_close_location": 0.70,
    "min_volume_ratio_20d": 1.05,
    "min_ret20_excess_spy": 0.0,
    "min_ret60_excess_spy": -0.02,
    "min_ret5": -0.03,
    "max_ret5": 0.15,
    "max_realized_vol_20d": 0.080,
    "forward_gate_min_closed_trades": 30,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_max_single_ticker_positive_share": 0.50,
}

MACRO_EVENTS: list[dict[str, str]] = [
    {"date": "2024-10-04", "family": "NFP", "label": "Sep 2024 Employment Situation"},
    {"date": "2024-10-10", "family": "CPI", "label": "Sep 2024 CPI"},
    {"date": "2024-11-01", "family": "NFP", "label": "Oct 2024 Employment Situation"},
    {"date": "2024-11-07", "family": "FOMC", "label": "Nov 2024 FOMC decision"},
    {"date": "2024-11-13", "family": "CPI", "label": "Oct 2024 CPI"},
    {"date": "2024-12-06", "family": "NFP", "label": "Nov 2024 Employment Situation"},
    {"date": "2024-12-11", "family": "CPI", "label": "Nov 2024 CPI"},
    {"date": "2024-12-18", "family": "FOMC", "label": "Dec 2024 FOMC decision"},
    {"date": "2025-01-10", "family": "NFP", "label": "Dec 2024 Employment Situation"},
    {"date": "2025-01-15", "family": "CPI", "label": "Dec 2024 CPI"},
    {"date": "2025-01-29", "family": "FOMC", "label": "Jan 2025 FOMC decision"},
    {"date": "2025-02-07", "family": "NFP", "label": "Jan 2025 Employment Situation"},
    {"date": "2025-02-12", "family": "CPI", "label": "Jan 2025 CPI"},
    {"date": "2025-03-07", "family": "NFP", "label": "Feb 2025 Employment Situation"},
    {"date": "2025-03-12", "family": "CPI", "label": "Feb 2025 CPI"},
    {"date": "2025-03-19", "family": "FOMC", "label": "Mar 2025 FOMC decision"},
    {"date": "2025-04-04", "family": "NFP", "label": "Mar 2025 Employment Situation"},
    {"date": "2025-04-10", "family": "CPI", "label": "Mar 2025 CPI"},
    {"date": "2025-05-02", "family": "NFP", "label": "Apr 2025 Employment Situation"},
    {"date": "2025-05-07", "family": "FOMC", "label": "May 2025 FOMC decision"},
    {"date": "2025-05-13", "family": "CPI", "label": "Apr 2025 CPI"},
    {"date": "2025-06-06", "family": "NFP", "label": "May 2025 Employment Situation"},
    {"date": "2025-06-11", "family": "CPI", "label": "May 2025 CPI"},
    {"date": "2025-06-18", "family": "FOMC", "label": "Jun 2025 FOMC decision"},
    {"date": "2025-07-03", "family": "NFP", "label": "Jun 2025 Employment Situation"},
    {"date": "2025-07-15", "family": "CPI", "label": "Jun 2025 CPI"},
    {"date": "2025-07-30", "family": "FOMC", "label": "Jul 2025 FOMC decision"},
    {"date": "2025-08-01", "family": "NFP", "label": "Jul 2025 Employment Situation"},
    {"date": "2025-08-12", "family": "CPI", "label": "Jul 2025 CPI"},
    {"date": "2025-09-05", "family": "NFP", "label": "Aug 2025 Employment Situation"},
    {"date": "2025-09-11", "family": "CPI", "label": "Aug 2025 CPI"},
    {"date": "2025-09-17", "family": "FOMC", "label": "Sep 2025 FOMC decision"},
    {"date": "2025-10-03", "family": "NFP", "label": "Sep 2025 Employment Situation"},
    {"date": "2025-10-29", "family": "FOMC", "label": "Oct 2025 FOMC decision"},
    {"date": "2025-11-07", "family": "NFP", "label": "Oct 2025 Employment Situation"},
    {"date": "2025-12-05", "family": "NFP", "label": "Nov 2025 Employment Situation"},
    {"date": "2025-12-10", "family": "FOMC", "label": "Dec 2025 FOMC decision"},
    {"date": "2025-12-18", "family": "CPI", "label": "Nov 2025 CPI"},
    {"date": "2026-01-09", "family": "NFP", "label": "Dec 2025 Employment Situation"},
    {"date": "2026-01-13", "family": "CPI", "label": "Dec 2025 CPI"},
    {"date": "2026-01-28", "family": "FOMC", "label": "Jan 2026 FOMC decision"},
    {"date": "2026-02-06", "family": "NFP", "label": "Jan 2026 Employment Situation"},
    {"date": "2026-02-13", "family": "CPI", "label": "Jan 2026 CPI"},
    {"date": "2026-03-06", "family": "NFP", "label": "Feb 2026 Employment Situation"},
    {"date": "2026-03-11", "family": "CPI", "label": "Feb 2026 CPI"},
    {"date": "2026-03-18", "family": "FOMC", "label": "Mar 2026 FOMC decision"},
    {"date": "2026-04-03", "family": "NFP", "label": "Mar 2026 Employment Situation"},
    {"date": "2026-04-10", "family": "CPI", "label": "Mar 2026 CPI"},
]

MACRO_EVENTS_BY_DATE: dict[str, list[dict[str, str]]] = {}
for _ev in MACRO_EVENTS:
    _d = str(_ev.get("date") or "")[:10]
    MACRO_EVENTS_BY_DATE.setdefault(_d, []).append(_ev)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# OHLCV utility functions (self-contained, no experiment imports)
# ---------------------------------------------------------------------------

def _date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _float_val(row: dict[str, Any], key: str) -> float | None:
    val = row.get(key) or row.get(key.lower())
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows)}


def _series(snapshot: dict[str, list[dict[str, Any]]], ticker: str) -> list[dict[str, Any]]:
    return sorted(snapshot.get(ticker) or [], key=_date)


def _trading_dates(snapshot: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [_date(row) for row in _series(snapshot, "SPY")]


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = _float_val(rows[idx - 1], "Close")
    close = _float_val(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = _float_val(rows[idx - lookback], "Close")
    close = _float_val(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback - 1:
        return None
    vals: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = _float_val(row, "Close")
        volume = _float_val(row, "Volume")
        if close is None or volume is None:
            return None
        vals.append(close * volume)
    return sum(vals) / len(vals) if vals else None


def _volume_ratio(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    avg_vol: list[float] = []
    for row in rows[idx - lookback : idx]:
        vol = _float_val(row, "Volume")
        if vol is None:
            return None
        avg_vol.append(vol)
    cur_vol = _float_val(rows[idx], "Volume")
    if cur_vol is None or not avg_vol:
        return None
    mean_vol = sum(avg_vol) / len(avg_vol)
    if mean_vol <= 0:
        return None
    return cur_vol / mean_vol


def _range_location(row: dict[str, Any]) -> float | None:
    high = _float_val(row, "High")
    low = _float_val(row, "Low")
    close = _float_val(row, "Close")
    if high is None or low is None or close is None or high <= low:
        return None
    return (close - low) / (high - low)


def _close_location(row: dict[str, Any]) -> float | None:
    high = _float_val(row, "High")
    low = _float_val(row, "Low")
    close = _float_val(row, "Close")
    if high is None or low is None or close is None:
        return None
    span = high - low
    if span <= 0:
        return 0.5
    return (close - low) / span


def _realized_vol(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    returns = [_daily_return(rows, i) for i in range(idx - lookback + 1, idx + 1)]
    if any(v is None for v in returns):
        return None
    valid = [float(v) for v in returns if v is not None]
    if not valid:
        return None
    mean_r = sum(valid) / len(valid)
    variance = sum((v - mean_r) ** 2 for v in valid) / len(valid)
    return math.sqrt(variance)


def _round(value: float | None, ndigits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, ndigits)


def _apply_entry_fill(open_price: float) -> float:
    return open_price * (1.0 + SLIPPAGE_BPS_ENTRY / 10_000.0)


def _apply_exit_slippage(close_price: float) -> float:
    return close_price * (1.0 - SLIPPAGE_BPS_TARGET / 10_000.0)


def _baseline_entries(before_result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in before_result.get("trades", []):
        if trade.get("strategy") in {"trend_long", "breakout_long"}:
            by_date[str(trade.get("entry_date") or "")[:10]].append(trade)
    return by_date


# ---------------------------------------------------------------------------
# Macro relief day detection
# ---------------------------------------------------------------------------

def _relief_context_for_day(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    events = MACRO_EVENTS_BY_DATE.get(signal_date)
    if not events:
        return None
    allowed_families = set(config.get("official_macro_event_families") or ["CPI", "FOMC", "NFP"])
    events = [ev for ev in events if ev.get("family") in allowed_families]
    if not events:
        return None
    spy_rows = _series(snapshot, "SPY")
    qqq_rows = _series(snapshot, "QQQ")
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None:
        return {
            "date": signal_date,
            "passed": False,
            "reason": "missing_spy_or_qqq_event_row",
            "events": events,
        }
    spy_return = _daily_return(spy_rows, spy_idx)
    qqq_return = _daily_return(qqq_rows, qqq_idx)
    spy_close_location = _range_location(spy_rows[spy_idx])
    qqq_close_location = _range_location(qqq_rows[qqq_idx])
    context = {
        "date": signal_date,
        "events": events,
        "event_families": sorted({str(ev.get("family") or "") for ev in events}),
        "spy_return": _round(spy_return, 6),
        "qqq_return": _round(qqq_return, 6),
        "spy_close_location": _round(spy_close_location, 6),
        "qqq_close_location": _round(qqq_close_location, 6),
        "min_spy_relief_return": config["min_spy_relief_return"],
        "min_qqq_relief_return": config["min_qqq_relief_return"],
        "min_spy_close_location": config["min_spy_close_location"],
        "min_qqq_close_location": config["min_qqq_close_location"],
    }
    if spy_return is None or qqq_return is None:
        return {**context, "passed": False, "reason": "missing_daily_return"}
    if spy_close_location is None or qqq_close_location is None:
        return {**context, "passed": False, "reason": "missing_close_location"}
    if spy_return < config["min_spy_relief_return"]:
        return {**context, "passed": False, "reason": "spy_relief_return_too_low"}
    if qqq_return < config["min_qqq_relief_return"]:
        return {**context, "passed": False, "reason": "qqq_relief_return_too_low"}
    if spy_close_location < config["min_spy_close_location"]:
        return {**context, "passed": False, "reason": "spy_close_location_too_low"}
    if qqq_close_location < config["min_qqq_close_location"]:
        return {**context, "passed": False, "reason": "qqq_close_location_too_low"}
    return {**context, "passed": True, "reason": "official_macro_relief_day_passed"}


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------

def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    rows = _series(snapshot, ticker)
    spy_rows = _series(snapshot, "SPY")
    qqq_rows = _series(snapshot, "QQQ")
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    hold_days = config.get("hold_days", 10)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or qqq_idx < 60 or idx + hold_days >= len(rows):
        return None
    close = _float_val(rows[idx], "Close")
    if close is None or close < config.get("min_price", 10.0):
        return None
    adv20 = _avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < config.get("min_avg_dollar_volume_20d", 50_000_000.0):
        return None
    signal_return = _daily_return(rows, idx)
    spy_return = _daily_return(spy_rows, spy_idx)
    qqq_return = _daily_return(qqq_rows, qqq_idx)
    close_location = _close_location(rows[idx])
    volume_ratio = _volume_ratio(rows, idx)
    ret5 = _ret(rows, idx, 5)
    ret20 = _ret(rows, idx, 20)
    ret60 = _ret(rows, idx, 60)
    spy_ret20 = _ret(spy_rows, spy_idx, 20)
    spy_ret60 = _ret(spy_rows, spy_idx, 60)
    realized_vol20 = _realized_vol(rows, idx, 20)
    required = [
        signal_return, spy_return, qqq_return, close_location, volume_ratio,
        ret5, ret20, ret60, spy_ret20, spy_ret60, realized_vol20,
    ]
    if any(v is None for v in required):
        return None
    assert signal_return is not None
    assert spy_return is not None
    assert qqq_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    relative_vs_spy = signal_return - spy_return
    relative_vs_qqq = signal_return - qqq_return
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_return < config.get("min_signal_return", 0.010):
        return None
    if relative_vs_spy < config.get("min_relative_vs_spy", 0.008):
        return None
    if relative_vs_qqq < config.get("min_relative_vs_qqq", 0.004):
        return None
    if close_location < config.get("min_close_location", 0.70):
        return None
    if volume_ratio < config.get("min_volume_ratio_20d", 1.05):
        return None
    if ret20_excess_spy < config.get("min_ret20_excess_spy", 0.0):
        return None
    if ret60_excess_spy < config.get("min_ret60_excess_spy", -0.02):
        return None
    if ret5 < config.get("min_ret5", -0.03) or ret5 > config.get("max_ret5", 0.15):
        return None
    if realized_vol20 > config.get("max_realized_vol_20d", 0.080):
        return None
    sector_meta = sector_entries.get(ticker, {})
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        2.25 * relative_vs_spy
        + 1.25 * relative_vs_qqq
        + 0.80 * ret20_excess_spy
        + 0.35 * ret60_excess_spy
        + 0.30 * close_location
        + 0.10 * min(volume_ratio, 3.0)
        + 0.04 * liquidity_score
        - 0.55 * realized_vol20
        - 0.20 * max(ret5, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": SLEEVE_NAME,
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_spy_signal_day_return": round(spy_return, 6),
        "candidate_qqq_signal_day_return": round(qqq_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": round(relative_vs_qqq, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret60": round(spy_ret60, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "macro_relief_context": context,
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


# ---------------------------------------------------------------------------
# Candidate pool generation for historical replay
# ---------------------------------------------------------------------------

def candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Generate macro relief leadership candidate rows for a backtest window.

    Returns (candidates, relief_contexts, scan_summary).
    """
    cfg_eff = {**DEFAULT_CONFIG, **(config or {})}
    entries_by_date = _baseline_entries(before_result)
    indices = {
        ticker: _row_index(_series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = [
        d
        for d in _trading_dates(snapshot)
        if str(cfg.get("start", "")) <= d <= str(cfg.get("end", ""))
    ]
    candidates: list[dict[str, Any]] = []
    relief_contexts: list[dict[str, Any]] = []
    scan: dict[str, Any] = {
        "scanned_trading_days": len(dates),
        "official_macro_event_trading_days": 0,
        "macro_relief_days": 0,
        "non_relief_macro_days": 0,
        "days_with_raw_macro_relief_candidates": 0,
        "raw_macro_relief_candidates": 0,
    }
    for signal_date in dates:
        context = _relief_context_for_day(snapshot, indices, signal_date, cfg_eff)
        if context is None:
            continue
        scan["official_macro_event_trading_days"] += 1
        if not context.get("passed"):
            scan["non_relief_macro_days"] += 1
            relief_contexts.append(context)
            continue
        scan["macro_relief_days"] += 1
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
                config=cfg_eff,
            )
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            day_rows.append(row)
        if not day_rows:
            relief_contexts.append({**context, "raw_candidate_count": 0})
            continue
        day_rows.sort(
            key=lambda r: (
                -float(r["candidate_score"]),
                -float(r["candidate_relative_vs_spy"]),
                -float(r["candidate_ret20_excess_spy"]),
                -float(r["candidate_avg_dollar_volume_20d"]),
                str(r.get("sector") or ""),
                r["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_macro_relief_candidates"] += 1
        scan["raw_macro_relief_candidates"] += len(day_rows)
        relief_contexts.append(
            {
                **context,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_relative_vs_spy": day_rows[0]["candidate_relative_vs_spy"],
                "top_candidate_ret20_excess_spy": day_rows[0]["candidate_ret20_excess_spy"],
            }
        )
    candidates.sort(
        key=lambda r: (
            r["date"],
            -float(r["candidate_score"]),
            -float(r["candidate_relative_vs_spy"]),
            -float(r["candidate_ret20_excess_spy"]),
            -float(r["candidate_avg_dollar_volume_20d"]),
            str(r.get("sector") or ""),
            r["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "macro_event_families": ["CPI", "FOMC", "NFP"],
            "min_spy_relief_return": cfg_eff["min_spy_relief_return"],
            "min_qqq_relief_return": cfg_eff["min_qqq_relief_return"],
            "min_spy_close_location": cfg_eff["min_spy_close_location"],
            "min_qqq_close_location": cfg_eff["min_qqq_close_location"],
            "min_signal_return": cfg_eff["min_signal_return"],
            "min_relative_vs_spy": cfg_eff["min_relative_vs_spy"],
            "min_relative_vs_qqq": cfg_eff["min_relative_vs_qqq"],
            "min_close_location": cfg_eff["min_close_location"],
            "min_volume_ratio_20d": cfg_eff["min_volume_ratio_20d"],
            "min_ret20_excess_spy": cfg_eff["min_ret20_excess_spy"],
            "min_ret60_excess_spy": cfg_eff["min_ret60_excess_spy"],
            "min_ret5": cfg_eff["min_ret5"],
            "max_ret5": cfg_eff["max_ret5"],
            "max_realized_vol_20d": cfg_eff["max_realized_vol_20d"],
        }
    )
    return candidates, relief_contexts, scan


def select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select top-N paper trades per day with same-ticker cooldown."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    max_per_day = cfg.get("max_paper_trades_per_day", 2)
    cooldown = cfg.get("same_ticker_cooldown_days", 10)
    hold_days = cfg.get("hold_days", 10)
    notional = cfg.get("paper_notional_usd", 4_000.0)
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    all_dates = _trading_dates(snapshot)
    date_pos = {d: i for i, d in enumerate(all_dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= max_per_day:
            filtered.append({**row, "filter_reason": "daily_top_n_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = _paper_trade_from_candidate(snapshot, row, notional=notional, hold_days=hold_days)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + cooldown
    return selected, filtered


def _paper_trade_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    notional: float = 4_000.0,
    hold_days: int = 10,
) -> dict[str, Any] | None:
    ticker = str(candidate.get("ticker") or "").upper()
    rows = _series(snapshot, ticker)
    row_idx = _row_index(rows)
    signal_date = str(candidate.get("date") or "")
    idx = row_idx.get(signal_date)
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + hold_days
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = _float_val(rows[entry_idx], "Open")
    exit_raw = _float_val(rows[exit_idx], "Close")
    if not entry_raw or not exit_raw:
        return None
    entry_price = _apply_entry_fill(entry_raw)
    exit_price = _apply_exit_slippage(exit_raw)
    pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = notional * pnl_pct_net
    return {
        **candidate,
        "signal_date": signal_date,
        "entry_date": _date(rows[entry_idx]),
        "exit_date": _date(rows[exit_idx]),
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": hold_days,
        "paper_notional_usd": notional,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
    }


# ---------------------------------------------------------------------------
# State management (production use)
# ---------------------------------------------------------------------------

def empty_macro_relief_leadership_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def load_macro_relief_leadership_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_macro_relief_leadership_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_macro_relief_leadership_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    return state


def save_macro_relief_leadership_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_macro_relief_leadership_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True) + "\n")


def _production_impact() -> dict[str, Any]:
    return {
        "trade_enabled": False,
        "alters_orders": False,
        "shared_policy": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
    }


def empty_macro_relief_leadership_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "is_macro_relief_day": False,
        "macro_events_today": [],
        "candidate_count": 0,
        "new_pending_count": 0,
        "pending_count": 0,
        "filled_count": 0,
        "open_position_count": 0,
        "closed_count_today": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "candidates": [],
        "new_pending_entries": [],
        "open_positions": [],
        "closed_today": [],
        "forward_paper_gate": {
            "passed": False,
            "status": "blocked",
            "reasons": [reason],
        },
        "production_impact": _production_impact(),
        "error": reason,
    }


# ---------------------------------------------------------------------------
# Production snapshot builder
# ---------------------------------------------------------------------------

def build_macro_relief_leadership_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    open_positions: dict[str, Any] | None = None,
    sector_map: dict[str, dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    """Build a daily macro relief leadership paper sleeve snapshot.

    Checks whether today is an official macro relief day, scores liquid stock
    candidates, and queues up to two paper entries for the next open.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    as_of_date = str(as_of)[:10]
    working_state = deepcopy(
        state if state is not None else load_macro_relief_leadership_paper_state(state_path)
    )

    def _normalise_rows(raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)]
        if isinstance(raw, dict):
            rows = []
            for date_val, price_data in raw.items():
                if isinstance(price_data, dict):
                    rows.append({"Date": date_val, **price_data})
            return sorted(rows, key=_date)
        return []

    snapshot = {
        ticker: _normalise_rows(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }

    # Advance open positions to today
    closed_today: list[dict[str, Any]] = []
    still_open: list[dict[str, Any]] = []
    for pos in working_state.get("open_positions", []):
        exit_date = str(pos.get("exit_date") or "")[:10]
        ticker = str(pos.get("ticker") or "").upper()
        if exit_date <= as_of_date:
            rows = _series(snapshot, ticker)
            idx = _row_index(rows).get(as_of_date)
            if idx is None:
                idx = len(rows) - 1
            exit_raw = _float_val(rows[idx], "Close") if rows and idx >= 0 else None
            if exit_raw is not None:
                exit_price = _apply_exit_slippage(exit_raw)
                entry_price = float(pos.get("entry_price") or 0.0)
                notional = float(pos.get("paper_notional_usd") or cfg["paper_notional_usd"])
                pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT if entry_price > 0 else 0.0
                pnl = notional * pnl_pct_net
                closed = {
                    **pos,
                    "actual_exit_date": as_of_date,
                    "exit_raw_close": _round(exit_raw, 4),
                    "exit_price": _round(exit_price, 4),
                    "pnl_pct_net": _round(pnl_pct_net, 6),
                    "pnl": _round(pnl, 2),
                }
                closed_today.append(closed)
                working_state.setdefault("closed_positions", []).append(closed)
            else:
                still_open.append(pos)
        else:
            still_open.append(pos)
    working_state["open_positions"] = still_open

    # Fill pending entries from previous day
    filled_today: list[dict[str, Any]] = []
    still_pending: list[dict[str, Any]] = []
    for entry in working_state.get("pending_entries", []):
        entry_date = str(entry.get("entry_date") or "")[:10]
        ticker = str(entry.get("ticker") or "").upper()
        if entry_date == as_of_date:
            rows = _series(snapshot, ticker)
            idx = _row_index(rows).get(as_of_date)
            entry_raw = _float_val(rows[idx], "Open") if rows and idx is not None else None
            if entry_raw is not None:
                entry_price = _apply_entry_fill(entry_raw)
                hold_days = cfg.get("hold_days", 10)
                all_dates = _trading_dates(snapshot)
                pos_idx = all_dates.index(as_of_date) if as_of_date in all_dates else -1
                exit_date = all_dates[pos_idx + hold_days] if pos_idx >= 0 and pos_idx + hold_days < len(all_dates) else ""
                filled = {
                    **entry,
                    "entry_raw_open": _round(entry_raw, 4),
                    "entry_price": _round(entry_price, 4),
                    "actual_entry_date": as_of_date,
                    "exit_date": exit_date,
                    "status": "open",
                }
                filled_today.append(filled)
                working_state["open_positions"].append(filled)
            else:
                still_pending.append(entry)
        elif entry_date > as_of_date:
            still_pending.append(entry)
    working_state["pending_entries"] = still_pending

    # Check if today is a macro relief day
    indices = {ticker: _row_index(_series(snapshot, ticker)) for ticker in snapshot}
    relief_ctx = _relief_context_for_day(snapshot, indices, as_of_date, cfg)
    is_macro_relief_day = bool(relief_ctx and relief_ctx.get("passed"))
    macro_events_today = MACRO_EVENTS_BY_DATE.get(as_of_date, [])

    # Generate candidates if macro relief day
    new_pending_entries: list[dict[str, Any]] = []
    day_candidates: list[dict[str, Any]] = []
    if is_macro_relief_day and relief_ctx is not None:
        sector_entries_map: dict[str, dict[str, Any]] = {}
        if sector_map:
            sector_entries_map = sector_map
        else:
            for ticker in snapshot:
                if ticker not in {"SPY", "QQQ", "IWM", "GLD", "SLV"}:
                    sector_entries_map[ticker] = {}

        for ticker in sorted(sector_entries_map):
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries_map,
                ticker=ticker,
                signal_date=as_of_date,
                context=relief_ctx,
                config=cfg,
            )
            if row is None:
                continue
            row["same_day_ab_overlap"] = False
            row["same_ticker_ab_overlap"] = False
            day_candidates.append(row)

        day_candidates.sort(
            key=lambda r: (
                -float(r["candidate_score"]),
                -float(r["candidate_relative_vs_spy"]),
                -float(r["candidate_ret20_excess_spy"]),
                -float(r["candidate_avg_dollar_volume_20d"]),
                str(r.get("sector") or ""),
                r["ticker"],
            )
        )

        # Queue top-N paper entries for next open
        active_tickers = {str(p.get("ticker") or "").upper() for p in working_state.get("open_positions", [])}
        active_tickers |= {str(p.get("ticker") or "").upper() for p in working_state.get("pending_entries", [])}
        selected_today = 0
        all_dates = _trading_dates(snapshot)
        today_pos = all_dates.index(as_of_date) if as_of_date in all_dates else -1
        for candidate in day_candidates:
            if selected_today >= cfg.get("max_paper_trades_per_day", 2):
                break
            ticker = str(candidate.get("ticker") or "").upper()
            if ticker in active_tickers:
                continue
            entry_date = all_dates[today_pos + 1] if today_pos >= 0 and today_pos + 1 < len(all_dates) else ""
            if not entry_date:
                continue
            pending = {
                **candidate,
                "entry_date": entry_date,
                "status": "pending",
            }
            new_pending_entries.append(pending)
            working_state.setdefault("pending_entries", []).append(pending)
            active_tickers.add(ticker)
            selected_today += 1

    if persist:
        save_macro_relief_leadership_paper_state(working_state, state_path)

    all_closed = working_state.get("closed_positions", [])
    realized_pnl = sum(float(p.get("pnl") or 0.0) for p in all_closed)

    snapshot_out = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "is_macro_relief_day": is_macro_relief_day,
        "macro_events_today": macro_events_today,
        "relief_context": relief_ctx,
        "candidate_count": len(day_candidates),
        "new_pending_count": len(new_pending_entries),
        "pending_count": len(working_state.get("pending_entries", [])),
        "filled_count": len(filled_today),
        "open_position_count": len(working_state.get("open_positions", [])),
        "closed_count_today": len(closed_today),
        "closed_position_count": len(all_closed),
        "realized_pnl_to_date": round(realized_pnl, 2),
        "candidates": day_candidates[:10],
        "new_pending_entries": new_pending_entries,
        "open_positions": working_state.get("open_positions", []),
        "closed_today": closed_today,
        "forward_paper_gate": _forward_paper_gate(working_state, cfg),
        "production_impact": _production_impact(),
    }

    if persist:
        append_macro_relief_leadership_paper_snapshot(snapshot_out, snapshot_log_path)

    return snapshot_out


def _forward_paper_gate(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    all_closed = state.get("closed_positions", [])
    min_closed = config.get("forward_gate_min_closed_trades", 30)
    min_win_rate = config.get("forward_gate_min_win_rate", 0.50)
    max_single_share = config.get("forward_gate_max_single_ticker_positive_share", 0.50)
    reasons: list[str] = []
    if len(all_closed) < min_closed:
        reasons.append(f"needs_min_{min_closed}_closed_trades")
    if reasons:
        return {"passed": False, "status": "blocked", "reasons": reasons}
    wins = sum(1 for p in all_closed if float(p.get("pnl") or 0.0) > 0)
    win_rate = wins / len(all_closed) if all_closed else 0.0
    net_pnl = sum(float(p.get("pnl") or 0.0) for p in all_closed)
    if win_rate < min_win_rate:
        reasons.append(f"win_rate_{win_rate:.2f}_below_{min_win_rate}")
    if not config.get("forward_gate_positive_net_pnl", True):
        pass
    elif net_pnl <= 0:
        reasons.append("net_pnl_not_positive")
    if reasons:
        return {"passed": False, "status": "blocked", "reasons": reasons}
    return {"passed": True, "status": "eligible", "reasons": []}
