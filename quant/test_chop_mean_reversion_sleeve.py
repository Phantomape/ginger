"""Tests for the chop-regime mean-reversion paper sleeve (exp-20260708-023)."""

from __future__ import annotations

import math

from chop_mean_reversion_sleeve import (
    ENTRY_SMA_LONG,
    MAX_HOLD_TRADING_DAYS,
    breadth_by_date,
    replay_chop_mean_reversion,
    sma,
    summarize_trades,
    wilder_rsi,
)


def _bars(prices: list[float], start_index: int = 0) -> list[dict]:
    out = []
    for i, price in enumerate(prices):
        day = f"2025-{(start_index + i) // 21 % 12 + 1:02d}-{(start_index + i) % 21 + 1:02d}"
        out.append({"Date": day, "Open": price, "High": price, "Low": price, "Close": price})
    return out


def _bars_seq(prices: list[float], dates: list[str]) -> list[dict]:
    return [
        {"Date": d, "Open": p, "High": p, "Low": p, "Close": p}
        for d, p in zip(dates, prices)
    ]


def _trading_dates(n: int) -> list[str]:
    # simple synthetic strictly-increasing ISO dates (ignores weekends)
    from datetime import date, timedelta

    d0 = date(2024, 1, 1)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def test_wilder_rsi_extremes_and_bounds():
    assert wilder_rsi([1, 2, 3, 4, 5]) == 100.0  # straight up
    down = wilder_rsi([5, 4, 3, 2, 1])
    assert down is not None and down < 1e-9  # straight down
    mixed = wilder_rsi([10, 9.5, 9.8, 9.2, 9.6])
    assert mixed is not None and 0.0 < mixed < 100.0
    assert wilder_rsi([1.0, 2.0], period=2) is None  # too short


def test_sma_basic():
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert sma([1, 2], 3) is None


def test_breadth_counts_only_covered_equities():
    dates = _trading_dates(60)
    up = _bars_seq([100 + i for i in range(60)], dates)          # above SMA50
    down = _bars_seq([200 - i for i in range(60)], dates)        # below SMA50
    spy = _bars_seq([400.0] * 60, dates)                          # excluded ticker
    breadth = breadth_by_date({"UP": up, "DOWN": down, "SPY": spy}, dates)
    assert breadth[dates[-1]] == 0.5
    assert breadth[dates[10]] is None  # < 50 bars of coverage


def _synthetic_market(n_days: int = 260):
    """One ticker with a deep 3-day pullback inside an uptrend; SPY flat-ish."""
    dates = _trading_dates(n_days)
    prices = [100.0 + 0.2 * i for i in range(n_days)]
    dip_start = ENTRY_SMA_LONG + 10
    prices[dip_start] = prices[dip_start - 1] - 4.0
    prices[dip_start + 1] = prices[dip_start] - 4.0
    prices[dip_start + 2] = prices[dip_start + 1] - 4.0
    for i in range(dip_start + 3, n_days):
        prices[i] = prices[i - 1] + 3.0  # sharp recovery -> SMA5 cross exit
    ticker_bars = _bars_seq(prices, dates)
    spy_bars = _bars_seq([500.0 + 0.01 * i for i in range(n_days)], dates)
    return dates, ticker_bars, spy_bars, dip_start


def _labels(dates: list[str], label: str) -> dict:
    return {d: {"regime_label": label, "p_choppy_range": 0.8} for d in dates}


def test_replay_enters_on_chop_dip_and_exits_on_sma5_cross():
    dates, ticker_bars, spy_bars, dip_start = _synthetic_market()
    result = replay_chop_mean_reversion(
        {"ACME": ticker_bars},
        spy_bars,
        dates[0],
        dates[-1],
        regime_labels=_labels(dates, "choppy_range"),
        qqq_bars=spy_bars,
    )
    trades = result["trades"]
    assert len(trades) >= 1
    first = trades[0]
    assert first["ticker"] == "ACME"
    # RSI(2) pins low somewhere inside the 3-day dip; fill is next-day open
    assert dates[dip_start] <= first["signal_date"] <= dates[dip_start + 2]
    assert first["entry_date"] == dates[dates.index(first["signal_date"]) + 1]
    assert first["exit_reason"] in {"close_above_sma5", "max_hold_timeout"}
    assert first["holding_days"] <= MAX_HOLD_TRADING_DAYS
    assert first["pnl_usd"] > 0  # bought the dip, recovered
    assert result["summary"]["trade_count"] == len(trades)


def test_replay_ignores_dip_when_regime_is_not_chop():
    dates, ticker_bars, spy_bars, _ = _synthetic_market()
    result = replay_chop_mean_reversion(
        {"ACME": ticker_bars},
        spy_bars,
        dates[0],
        dates[-1],
        regime_labels=_labels(dates, "risk_on_trend"),
        qqq_bars=spy_bars,
    )
    assert result["trades"] == []
    assert result["signals_generated"] == 0
    assert result["entry_label_days"] == 0


def test_replay_never_enters_below_sma200():
    n = 260
    dates = _trading_dates(n)
    prices = [100.0 - 0.2 * i for i in range(n)]  # persistent downtrend
    result = replay_chop_mean_reversion(
        {"ACME": _bars_seq(prices, dates)},
        _bars_seq([500.0] * n, dates),
        dates[0],
        dates[-1],
        regime_labels=_labels(dates, "choppy_range"),
    )
    assert result["trades"] == []  # dips galore but below SMA200 -> no entries


def test_replay_excludes_etf_tickers_from_entries():
    dates, ticker_bars, spy_bars, _ = _synthetic_market()
    result = replay_chop_mean_reversion(
        {"TQQQ": ticker_bars},  # excluded ETF gets the same juicy dip
        spy_bars,
        dates[0],
        dates[-1],
        regime_labels=_labels(dates, "choppy_range"),
    )
    assert result["trades"] == []


def test_summarize_trades_replacement_values():
    trades = [
        {"pnl_usd": 100.0, "holding_days": 3, "exit_reason": "close_above_sma5",
         "spy_same_window_pnl_usd": 20.0, "qqq_same_window_pnl_usd": None},
        {"pnl_usd": -50.0, "holding_days": 10, "exit_reason": "max_hold_timeout",
         "spy_same_window_pnl_usd": 10.0, "qqq_same_window_pnl_usd": 5.0},
    ]
    summary = summarize_trades(trades)
    assert summary["trade_count"] == 2
    assert math.isclose(summary["total_pnl_usd"], 50.0)
    assert math.isclose(summary["replacement_value_vs_spy_usd"], 100.0 - 20.0 + (-50.0 - 10.0))
    assert math.isclose(summary["replacement_value_vs_qqq_usd"], -55.0)
    assert summary["win_rate"] == 0.5
