"""Unit tests for exp-20260601-009 overnight/intraday decomposition.

Covers the t-stat helper, the per-day cross-sectional component means with
the microstructure clip + min-names guard, and the accept/observed-only
decision logic.

No JavaScript was used.
"""

from __future__ import annotations

import pandas as pd

from quant.experiments.exp_20260601_009_overnight_intraday_decomposition import (  # noqa: E501
    COMPONENT_CLIP,
    MIN_NAMES_PER_DAY,
    T_STAT_FLOOR,
    _daily_means,
    _tstat,
)


def test_tstat_significance():
    assert _tstat([0.01, 0.011, 0.009, 0.012, 0.010]) > 2
    t = _tstat([0.05, -0.05, 0.04, -0.04, 0.0])
    assert t is not None and abs(t) < 2
    assert _tstat([0.01, 0.01, 0.01]) is None  # zero variance


def _frame(rows, start="2025-01-02"):
    idx = pd.bdate_range(start=start, periods=len(rows))
    return pd.DataFrame(
        {
            "Open": [r[0] for r in rows],
            "High": [max(r) for r in rows],
            "Low": [min(r) for r in rows],
            "Close": [r[1] for r in rows],
            "Volume": [1] * len(rows),
        },
        index=idx,
    )


def test_daily_means_decomposition_and_min_names_guard():
    # 60 tickers, day t: prev_close=100, open=101 (overnight +1%), close=102 (intraday ~+0.99%)
    frames = {}
    for i in range(60):
        frames[f"T{i}"] = _frame([(100.0, 100.0), (101.0, 102.0)])
    days = _daily_means(frames, "2025-01-02", "2025-01-31")
    # day 0 has no prev bar -> skipped; day 1 has 60 names -> included
    assert len(days) == 1
    d = days[0]
    assert d["n"] == 60
    assert abs(d["overnight"] - (101 / 100 - 1)) < 1e-9
    assert abs(d["intraday"] - (102 / 101 - 1)) < 1e-9
    assert abs(d["close_to_close"] - (102 / 100 - 1)) < 1e-9


def test_daily_means_drops_day_below_min_names():
    frames = {f"T{i}": _frame([(100.0, 100.0), (101.0, 102.0)]) for i in range(MIN_NAMES_PER_DAY - 1)}
    days = _daily_means(frames, "2025-01-02", "2025-01-31")
    assert days == []  # below MIN_NAMES_PER_DAY


def test_component_clip_drops_split_like_prints():
    # one ticker has a 60% overnight jump (split/bad print) -> clipped out;
    # need >= MIN_NAMES_PER_DAY good names for the day to survive.
    frames = {f"T{i}": _frame([(100.0, 100.0), (101.0, 102.0)]) for i in range(MIN_NAMES_PER_DAY)}
    frames["SPLIT"] = _frame([(100.0, 100.0), (170.0, 171.0)])  # +70% overnight
    days = _daily_means(frames, "2025-01-02", "2025-01-31")
    assert len(days) == 1
    # SPLIT excluded -> n == MIN_NAMES_PER_DAY, overnight mean unaffected by the jump
    assert days[0]["n"] == MIN_NAMES_PER_DAY
    assert abs(days[0]["overnight"] - (101 / 100 - 1)) < 1e-9
    assert COMPONENT_CLIP == 0.50


def test_decision_logic_mirror():
    # mirror gate4: accept requires overnight t>=2 AND majority windows AND diff t>=2
    def decide(on_t, diff_t, pos_w, meas_w):
        on_sig = on_t is not None and on_t >= T_STAT_FLOOR
        diff_sig = diff_t is not None and diff_t >= T_STAT_FLOOR
        maj = meas_w > 0 and pos_w > meas_w / 2
        return "accepted_overnight_premium_structure" if (on_sig and maj and diff_sig) else "observed_only_no_robust_overnight_structure"

    # the real exp-009 case: on_t=1.15, diff_t=0.11 -> observed_only
    assert decide(1.15, 0.11, 2, 3) == "observed_only_no_robust_overnight_structure"
    # strong robust case -> accepted
    assert decide(3.0, 2.5, 3, 3) == "accepted_overnight_premium_structure"
    # significant overnight but insignificant difference -> observed_only
    assert decide(3.0, 0.5, 3, 3) == "observed_only_no_robust_overnight_structure"
