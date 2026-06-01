"""Unit tests for exp-20260601-006 broad-universe ranking validation helpers.

The heavy scoring/judging machinery is reused from exp-20260601-003 and
exp-20260531-006 (already tested there). These tests cover the new
broad-universe helpers: forward-return computation and trading-day
sampling on synthetic frames (no warehouse needed).

No JavaScript was used.
"""

from __future__ import annotations

import pandas as pd

from quant.experiments.exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E501
    SAMPLE_STEP,
    _forward_returns,
    _sample_days,
)


def _frame(closes, start="2025-01-02"):
    idx = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1] * len(closes),
        },
        index=idx,
    )


def test_forward_returns_horizons():
    closes = [100, 101, 102, 103, 104, 110, 100, 100, 100, 100, 100, 120, 130]
    frame = _frame([float(c) for c in closes])
    fwd = _forward_returns(frame, frame.index[0])
    assert abs(fwd[5] - 0.10) < 1e-9   # idx 5 = 110
    assert abs(fwd[10] - 0.0) < 1e-9   # idx 10 = 100
    assert 20 not in fwd               # only 13 bars, idx 20 missing


def test_forward_returns_requires_exact_bar():
    frame = _frame([100.0, 101.0, 102.0])
    assert _forward_returns(frame, pd.Timestamp("2030-06-01")) == {}


def test_sample_days_respects_step_and_buffer():
    # 60 business days; buffer = max horizon (20) trimmed from the end.
    frames = {"A": _frame([100.0 + i for i in range(60)])}
    start = str(frames["A"].index[0].date())
    end = str(frames["A"].index[-1].date())
    days = _sample_days(frames, start, end)
    # eligible = first 40 (60 - 20 buffer), sampled every SAMPLE_STEP
    assert len(days) == len(range(0, 40, SAMPLE_STEP))
    # all sampled days must leave >= 20 forward bars
    for d in days:
        assert d <= frames["A"].index[40 - 1]


def test_sample_days_empty_when_too_short():
    frames = {"A": _frame([100.0] * 10)}  # fewer than buffer
    days = _sample_days(frames, "2025-01-02", "2025-12-31")
    assert days == []


def test_sample_days_union_across_tickers():
    a = _frame([100.0 + i for i in range(40)], start="2025-01-02")
    # B has a slightly different (overlapping) calendar
    b = _frame([50.0 + i for i in range(40)], start="2025-01-03")
    days = _sample_days({"A": a, "B": b}, "2025-01-02", "2025-12-31")
    # union of both calendars, trimmed + sampled; must be sorted unique
    assert days == sorted(set(days))
    assert len(days) > 0
