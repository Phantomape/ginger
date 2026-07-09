"""Tests for the chop-regime pairs spread paper sleeve (exp-20260708-025)."""

from __future__ import annotations

import math

from chop_pairs_spread_sleeve import (
    CORR_LOOKBACK,
    Z_LOOKBACK,
    pearson,
    replay_chop_pairs_spread,
    spread_zscore,
    summarize_pair_trades,
)


def _trading_dates(n: int) -> list[str]:
    from datetime import date, timedelta

    d0 = date(2024, 1, 1)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def _bars_seq(prices: list[float], dates: list[str]) -> list[dict]:
    return [
        {"Date": d, "Open": p, "High": p, "Low": p, "Close": p}
        for d, p in zip(dates, prices)
    ]


def _labels(dates: list[str], label: str) -> dict:
    return {d: {"regime_label": label, "p_choppy_range": 0.8} for d in dates}


def test_pearson_perfect_and_anti():
    assert math.isclose(pearson([1, 2, 3], [2, 4, 6]), 1.0)
    assert math.isclose(pearson([1, 2, 3], [-1, -2, -3]), -1.0)
    assert pearson([1, 1, 1], [1, 2, 3]) is None  # zero variance


def test_spread_zscore_detects_stretch():
    stable_a = [100.0] * Z_LOOKBACK
    stable_b = [50.0] * Z_LOOKBACK
    assert spread_zscore(stable_a, stable_b) is None  # zero std
    wiggle_a = [100.0 + (0.5 if i % 2 else -0.5) for i in range(Z_LOOKBACK)]
    stretched = wiggle_a[:-1] + [112.0]  # last day breaks away
    z = spread_zscore(stretched, stable_b)
    assert z is not None and z > 2.0


def _pair_market(n_days: int = 320):
    """Two cointegrated tickers; B lags A for 3 days then converges back."""
    dates = _trading_dates(n_days)
    base = [100.0 + 0.05 * i + (0.8 if i % 2 else -0.8) for i in range(n_days)]
    a = list(base)
    b = [x * 0.5 for x in base]
    stretch_at = CORR_LOOKBACK + Z_LOOKBACK + 20
    # B drops 6% for a few days while A holds -> spread ln(A/B) stretches rich
    for i in range(stretch_at, stretch_at + 3):
        b[i] *= 0.94
    # convergence: B snaps back from stretch_at+3 onward (b already back to base)
    spy = _bars_seq([500.0 + 0.01 * i for i in range(n_days)], dates)
    return dates, _bars_seq(a, dates), _bars_seq(b, dates), spy, stretch_at


def test_replay_trades_stretched_pair_and_converges():
    dates, bars_a, bars_b, spy, stretch_at = _pair_market()
    result = replay_chop_pairs_spread(
        {"AAA": bars_a, "BBB": bars_b},
        spy,
        dates[0],
        dates[-1],
        regime_labels=_labels(dates, "choppy_range"),
    )
    trades = result["trades"]
    assert len(trades) >= 1
    first = trades[0]
    # B got cheap vs A -> long BBB, short AAA
    assert first["long_ticker"] == "BBB"
    assert first["short_ticker"] == "AAA"
    assert first["entry_zscore"] >= 2.0
    assert dates[stretch_at] <= first["signal_date"] <= dates[stretch_at + 4]
    assert first["exit_reason"] in {"spread_converged", "max_hold_timeout"}
    assert first["pnl_usd"] > 0  # convergence profits the long-cheap/short-rich book
    assert result["summary"]["trade_count"] == len(trades)


def test_replay_is_silent_outside_chop_label():
    dates, bars_a, bars_b, spy, _ = _pair_market()
    result = replay_chop_pairs_spread(
        {"AAA": bars_a, "BBB": bars_b},
        spy,
        dates[0],
        dates[-1],
        regime_labels=_labels(dates, "risk_on_trend"),
    )
    assert result["trades"] == []
    assert result["signals_generated"] == 0


def test_replay_requires_correlation():
    n = 320
    dates = _trading_dates(n)
    import random

    rng = random.Random(7)
    a = [100.0]
    b = [50.0]
    for _ in range(n - 1):
        a.append(max(1.0, a[-1] * (1 + rng.uniform(-0.02, 0.02))))
        b.append(max(1.0, b[-1] * (1 + rng.uniform(-0.02, 0.02))))
    spy = _bars_seq([500.0] * n, dates)
    result = replay_chop_pairs_spread(
        {"AAA": _bars_seq(a, dates), "BBB": _bars_seq(b, dates)},
        spy,
        dates[0],
        dates[-1],
        regime_labels=_labels(dates, "choppy_range"),
    )
    # independent random walks: correlation gate should keep this near-silent
    assert result["signals_generated"] <= 1


def test_summarize_pair_trades():
    trades = [
        {"pnl_usd": 80.0, "holding_days": 4, "exit_reason": "spread_converged"},
        {"pnl_usd": -30.0, "holding_days": 10, "exit_reason": "max_hold_timeout"},
    ]
    summary = summarize_pair_trades(trades)
    assert summary["trade_count"] == 2
    assert math.isclose(summary["total_pnl_usd"], 50.0)
    assert summary["converged_exit_count"] == 1
    assert summary["converged_share"] == 0.5
    assert summary["win_rate"] == 0.5
