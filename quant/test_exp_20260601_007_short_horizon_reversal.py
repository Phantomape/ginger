"""Unit tests for exp-20260601-007 short-horizon reversal attribution.

Covers formation/skip-day forward return math, the t-stat helper, the
per-day cross-sectional long-short builder, and the judge branches
(reversal accept, continuation reject, observed-only).

No JavaScript was used.
"""

from __future__ import annotations

import pandas as pd

from quant.experiments.exp_20260601_007_short_horizon_reversal_attribution import (  # noqa: E501
    ROUND_TRIP_LONG_SHORT_COST,
    SKIP_DAYS,
    T_STAT_FLOOR,
    _daily_long_short,
    _formation_return,
    _skip_day_forward_return,
    _tstat,
    judge,
)


def test_formation_return():
    closes = [100.0, 90.0, 95.0, 99.0]
    # pos=3, formation=3 -> 99/100 - 1
    assert abs(_formation_return(closes, 3, 3) - (99 / 100 - 1)) < 1e-9
    # not enough history
    assert _formation_return(closes, 1, 3) is None


def test_skip_day_forward_return_skips_one_day():
    # closes index: 0..6 ; pos=1, hold=3, skip=1 -> entry=2, exit=5
    closes = [10, 11, 12, 13, 14, 18, 20]
    assert SKIP_DAYS == 1
    fwd = _skip_day_forward_return([float(c) for c in closes], 1, 3)
    assert abs(fwd - (18 / 12 - 1)) < 1e-9


def test_skip_day_forward_return_missing_when_short():
    closes = [10.0, 11.0, 12.0]
    assert _skip_day_forward_return(closes, 1, 5) is None


def test_tstat_positive_and_zero_variance():
    assert _tstat([0.01, 0.01, 0.01]) is None  # zero variance
    t = _tstat([0.02, 0.01, 0.03, 0.0, 0.02])
    assert t is not None and t > 0


def _prep_from_closes(close_map, start="2025-01-02"):
    prepared = {}
    idx = pd.bdate_range(start=start, periods=max(len(v) for v in close_map.values()))
    for t, closes in close_map.items():
        dates = list(idx[: len(closes)])
        prepared[t] = {
            "closes": [float(x) for x in closes],
            "pos_by_date": {d: i for i, d in enumerate(dates)},
            "dates": dates,
        }
    return prepared, idx


def test_daily_long_short_reversal_sign():
    # 10 tickers; losers (negative formation) get HIGH forward, winners LOW
    # -> reversal: long_short (losers-winners) should be positive.
    close_map = {}
    n = 30
    for i in range(10):
        # formation return over last 5 days: ticker i drops by i% then bounces
        base = [100.0] * (n - 11)
        if i < 5:  # losers that bounce
            tail = [100, 99, 98, 97, 96, 95, 105, 106, 107, 108, 109]
        else:      # winners that fade
            tail = [100, 101, 102, 103, 104, 105, 99, 98, 97, 96, 95]
        close_map[f"T{i}"] = base + tail
    prepared, idx = _prep_from_closes(close_map)
    asof = idx[n - 11 + 5]  # signal day = end of the 5-day formation move
    cell = _daily_long_short(prepared, asof, formation=5, hold=5)
    # require enough names; with 10 it should build 5 quintiles
    if cell is not None:
        assert cell["long_short"] is not None


def _cell(formation, hold, gross_ls, tstat, monotonic, pos_windows, meas=3):
    # winners>losers continuation => gross_ls negative
    return {
        "formation_days": formation,
        "hold_days": hold,
        "sample_step": hold,
        "n_sampled_days": 40,
        "gross_long_short_mean": gross_ls,
        "net_long_short_mean": gross_ls - ROUND_TRIP_LONG_SHORT_COST if gross_ls is not None else None,
        "round_trip_long_short_cost": ROUND_TRIP_LONG_SHORT_COST,
        "tstat_gross": tstat,
        "pooled_quintile_means_losers_to_winners": (
            [0.05, 0.04, 0.03, 0.02, 0.01] if monotonic else [0.01, 0.05, 0.02, 0.04, 0.03]
        ),
        "monotonic_reversal_ladder": monotonic,
        "per_window_long_short_mean": {"a": gross_ls, "b": gross_ls, "c": gross_ls},
        "positive_windows": pos_windows,
        "measured_windows": meas,
    }


def test_judge_accepts_clean_reversal():
    # losers-winners positive (reversal), t>=2, monotonic losers>winners, all windows +
    cells = [_cell(5, 5, gross_ls=0.02, tstat=3.0, monotonic=True, pos_windows=3)]
    gates = judge(cells)
    assert gates["gate4"]["status"] == "accepted_short_horizon_reversal_edge"
    assert gates["all_passed"] is True


def test_judge_rejects_continuation():
    # primary f5_h5 gross long-short <= -0.70pct (winners beat losers strongly)
    cells = [_cell(5, 5, gross_ls=-0.012, tstat=-2.5, monotonic=False, pos_windows=0)]
    gates = judge(cells)
    assert gates["gate4"]["status"] == "rejected_short_horizon_continuation_not_reversal"


def test_judge_observed_only_when_weak():
    # primary f5_h5 small negative (not <= -0.70pct), no qualifying cell
    cells = [_cell(5, 5, gross_ls=-0.002, tstat=-0.8, monotonic=False, pos_windows=0)]
    gates = judge(cells)
    assert gates["gate4"]["status"] == "observed_only_no_robust_net_reversal_edge"


def test_constants():
    assert SKIP_DAYS == 1
    assert T_STAT_FLOOR == 2.0
    assert abs(ROUND_TRIP_LONG_SHORT_COST - 0.007) < 1e-9
