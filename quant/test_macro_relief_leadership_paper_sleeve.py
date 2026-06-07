"""Parity tests for macro_relief_leadership_paper_sleeve shared adapter."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_QUANT = Path(__file__).resolve().parent
if str(_QUANT) not in sys.path:
    sys.path.insert(0, str(_QUANT))

from macro_relief_leadership_paper_sleeve import (
    DEFAULT_CONFIG,
    MACRO_EVENTS_BY_DATE,
    RULE_VERSION,
    SLEEVE_NAME,
    _candidate_for_ticker,
    _relief_context_for_day,
    _row_index,
    _series,
    build_macro_relief_leadership_paper_sleeve_snapshot,
    candidate_rows_for_window,
    empty_macro_relief_leadership_paper_state,
    select_paper_trades,
)

# 2025-01-15 = Dec 2024 CPI (in MACRO_EVENTS)
_SIGNAL_DATE = "2025-01-15"
_N_ROWS = 90
# 2024-11-10 + 66 days = 2025-01-15
_START_DATE = "2024-11-10"


def _make_rows(
    n: int,
    start: str = _START_DATE,
    price: float = 100.0,
    ret: float = 0.0005,
    volume: float = 1_000_000.0,
    signal_idx: int | None = None,
    signal_ret: float = 0.007,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    d = date.fromisoformat(start)
    p = price
    for i in range(n):
        close = round(p, 4)
        high = round(close * 1.008, 4)
        low = round(close * 0.992, 4)
        vol = volume
        if signal_idx is not None and i == signal_idx:
            prev_close = rows[-1]["Close"] if rows else close
            close = round(prev_close * (1.0 + signal_ret), 4)
            high = round(close * 1.002, 4)
            low = round(close * 0.982, 4)
        rows.append(
            {
                "Date": d.isoformat(),
                "Open": round(close * 0.999, 4),
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": vol,
            }
        )
        p = close * (1.0 + ret)
        d += timedelta(days=1)
    return rows


def _signal_idx() -> int:
    s = date.fromisoformat(_START_DATE)
    t = date.fromisoformat(_SIGNAL_DATE)
    return (t - s).days


def _snapshot_with_relief_day() -> dict[str, list[dict[str, Any]]]:
    sig = _signal_idx()
    spy = _make_rows(_N_ROWS, signal_idx=sig, signal_ret=0.007)
    qqq = _make_rows(_N_ROWS, price=400.0, signal_idx=sig, signal_ret=0.009)
    ticker = _make_rows(
        _N_ROWS,
        price=80.0,
        ret=0.0006,
        volume=900_000.0,
        signal_idx=sig,
        signal_ret=0.025,
    )
    ticker[sig]["Volume"] = 1_500_000.0
    return {"SPY": spy, "QQQ": qqq, "TICK": ticker}


def _indices(snapshot: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    return {ticker: _row_index(_series(snapshot, ticker)) for ticker in snapshot}


def test_macro_events_by_date_contains_signal_date():
    assert _SIGNAL_DATE in MACRO_EVENTS_BY_DATE
    event = MACRO_EVENTS_BY_DATE[_SIGNAL_DATE][0]
    assert event["family"] == "CPI"


def test_relief_day_detected_on_official_event():
    snapshot = _snapshot_with_relief_day()
    indices = _indices(snapshot)
    ctx = _relief_context_for_day(snapshot, indices, _SIGNAL_DATE, DEFAULT_CONFIG)
    assert ctx is not None
    assert ctx["passed"] is True
    assert ctx["reason"] == "official_macro_relief_day_passed"
    assert ctx["date"] == _SIGNAL_DATE


def test_relief_day_rejected_low_spy_return():
    snapshot = _snapshot_with_relief_day()
    sig = _signal_idx()
    # Overwrite SPY signal day to a tiny return
    prev = snapshot["SPY"][sig - 1]["Close"]
    close = round(prev * 1.001, 4)  # only 0.1%, below 0.4% threshold
    snapshot["SPY"][sig]["Close"] = close
    snapshot["SPY"][sig]["High"] = round(close * 1.002, 4)
    snapshot["SPY"][sig]["Low"] = round(close * 0.992, 4)
    indices = _indices(snapshot)
    ctx = _relief_context_for_day(snapshot, indices, _SIGNAL_DATE, DEFAULT_CONFIG)
    assert ctx is not None
    assert ctx["passed"] is False
    assert ctx["reason"] == "spy_relief_return_too_low"


def test_relief_day_rejected_spy_close_too_low():
    snapshot = _snapshot_with_relief_day()
    sig = _signal_idx()
    row = snapshot["SPY"][sig]
    # Force close near bottom of range so location < 0.65
    close = row["Low"] + 0.01  # just above low → location ~0
    snapshot["SPY"][sig] = {**row, "Close": close}
    indices = _indices(snapshot)
    ctx = _relief_context_for_day(snapshot, indices, _SIGNAL_DATE, DEFAULT_CONFIG)
    assert ctx is not None
    assert ctx["passed"] is False
    # Either spy_close_location_too_low or spy_relief_return_too_low depending on data
    assert "too_low" in ctx["reason"]


def test_non_event_date_returns_none():
    snapshot = _snapshot_with_relief_day()
    indices = _indices(snapshot)
    ctx = _relief_context_for_day(snapshot, indices, "2025-01-16", DEFAULT_CONFIG)
    assert ctx is None


def test_candidate_admitted_on_relief_day():
    snapshot = _snapshot_with_relief_day()
    indices = _indices(snapshot)
    sig = _signal_idx()
    ctx = _relief_context_for_day(snapshot, indices, _SIGNAL_DATE, DEFAULT_CONFIG)
    assert ctx is not None and ctx["passed"]

    cfg = {**DEFAULT_CONFIG, "hold_days": 10}
    row = _candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries={"TICK": {"sector": "Technology", "industry": "Software"}},
        ticker="TICK",
        signal_date=_SIGNAL_DATE,
        context=ctx,
        config=cfg,
    )
    assert row is not None
    assert row["ticker"] == "TICK"
    assert row["source"] == SLEEVE_NAME
    assert row["rule_version"] == RULE_VERSION
    assert row["trade_enabled"] is False
    assert row["uses_llm"] is False
    assert row["candidate_score"] > 0


def test_candidate_rejected_below_min_price():
    snapshot = _snapshot_with_relief_day()
    sig = _signal_idx()
    # Overwrite ticker price to < 10.0
    for r in snapshot["TICK"]:
        r["Close"] = 5.0
        r["Open"] = 4.99
        r["High"] = 5.05
        r["Low"] = 4.95
    indices = _indices(snapshot)
    ctx = _relief_context_for_day(snapshot, indices, _SIGNAL_DATE, DEFAULT_CONFIG)
    assert ctx is not None and ctx["passed"]
    row = _candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries={"TICK": {}},
        ticker="TICK",
        signal_date=_SIGNAL_DATE,
        context=ctx,
        config=DEFAULT_CONFIG,
    )
    assert row is None


def test_candidate_rejected_low_close_location():
    snapshot = _snapshot_with_relief_day()
    sig = _signal_idx()
    row = snapshot["TICK"][sig]
    # Close near bottom of wide range → location < 0.70
    close = row["Low"] + 0.10
    snapshot["TICK"][sig] = {**row, "Close": close, "High": row["Low"] + 10.0}
    indices = _indices(snapshot)
    ctx = _relief_context_for_day(snapshot, indices, _SIGNAL_DATE, DEFAULT_CONFIG)
    assert ctx is not None and ctx["passed"]
    result = _candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries={"TICK": {}},
        ticker="TICK",
        signal_date=_SIGNAL_DATE,
        context=ctx,
        config=DEFAULT_CONFIG,
    )
    assert result is None


def _two_ticker_snapshot() -> dict[str, list[dict[str, Any]]]:
    sig = _signal_idx()
    spy = _make_rows(_N_ROWS, signal_idx=sig, signal_ret=0.007)
    qqq = _make_rows(_N_ROWS, price=400.0, signal_idx=sig, signal_ret=0.009)
    t1 = _make_rows(_N_ROWS, price=80.0, ret=0.0006, volume=900_000.0, signal_idx=sig, signal_ret=0.030)
    t2 = _make_rows(_N_ROWS, price=70.0, ret=0.0005, volume=800_000.0, signal_idx=sig, signal_ret=0.020)
    t3 = _make_rows(_N_ROWS, price=60.0, ret=0.0004, volume=1_000_000.0, signal_idx=sig, signal_ret=0.015)
    for rows in [t1, t2, t3]:
        rows[sig]["Volume"] = 1_500_000.0
    return {"SPY": spy, "QQQ": qqq, "T1": t1, "T2": t2, "T3": t3}


def test_select_paper_trades_admits_top2_per_day():
    snapshot = _two_ticker_snapshot()
    sector_entries = {
        "T1": {"sector": "Technology"},
        "T2": {"sector": "Health Care"},
        "T3": {"sector": "Financials"},
    }
    before_result: dict[str, Any] = {"trades": []}
    cfg = {"start": "2024-11-10", "end": "2025-02-07"}
    candidates, _, _ = candidate_rows_for_window(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    selected, filtered = select_paper_trades(snapshot=snapshot, candidates=candidates)
    assert len(selected) == 2  # top-2 only
    assert all(t["trade_enabled"] is False for t in selected)
    assert all(t["pnl"] is not None for t in selected)
    assert len(filtered) >= 1  # T3 filtered


def test_select_paper_trades_same_ticker_cooldown():
    snapshot = _two_ticker_snapshot()
    sector_entries = {"T1": {"sector": "Technology"}}
    before_result: dict[str, Any] = {"trades": []}
    cfg = {"start": "2024-11-10", "end": "2025-02-07"}
    candidates, _, _ = candidate_rows_for_window(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    # Should get at most 1 trade for T1 (only one macro relief day in window)
    selected, _ = select_paper_trades(snapshot=snapshot, candidates=candidates)
    assert len(selected) <= 1


def test_build_snapshot_default_off_no_live_orders():
    snapshot = _snapshot_with_relief_day()
    as_of = _SIGNAL_DATE
    result = build_macro_relief_leadership_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"SPY": snapshot["SPY"], "QQQ": snapshot["QQQ"], "TICK": snapshot["TICK"]},
        sector_map={"TICK": {"sector": "Technology", "industry": "Software"}},
        state=empty_macro_relief_leadership_paper_state(),
        persist=False,
    )
    assert result["trade_enabled"] is False
    assert result["enabled"] is False
    assert result["paper_enabled"] is True
    assert result["sleeve"] == SLEEVE_NAME
    assert result["is_macro_relief_day"] is True
    assert result["new_pending_count"] >= 1
    # No live orders emitted
    prod = result["production_impact"]
    assert prod["trade_enabled"] is False
    assert prod["alters_orders"] is False


def test_build_snapshot_non_relief_day_no_candidates():
    snapshot = _snapshot_with_relief_day()
    as_of = "2025-01-16"  # day after the relief day, not a macro event
    result = build_macro_relief_leadership_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"SPY": snapshot["SPY"], "QQQ": snapshot["QQQ"], "TICK": snapshot["TICK"]},
        sector_map={"TICK": {"sector": "Technology"}},
        state=empty_macro_relief_leadership_paper_state(),
        persist=False,
    )
    assert result["is_macro_relief_day"] is False
    assert result["candidate_count"] == 0
    assert result["new_pending_count"] == 0
    assert result["trade_enabled"] is False
