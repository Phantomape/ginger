from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_022_vcp_base_geometry_higher_low_attribution import (  # noqa: E402
    BUCKET_CONSTRUCTIVE,
    BUCKET_INSUFFICIENT,
    BUCKET_NONCONSTRUCTIVE,
    BUCKET_UNAVAILABLE,
    compute_pre_signal_base_geometry_context,
    infer_breakout_pivot_level,
)


def _rows(lows: list[float | None], *, start: date = date(2026, 1, 1)) -> list[dict]:
    rows = []
    for idx, low in enumerate(lows):
        close = 100.0 + idx
        row = {
            "Date": (start + timedelta(days=idx)).isoformat(),
            "Open": close,
            "High": close + 2.0,
            "Close": close,
            "Volume": 1_000_000,
        }
        if low is not None:
            row["Low"] = low
        rows.append(row)
    return rows


def _trade(**overrides):
    trade = {
        "ticker": "AAA",
        "signal_date": "2026-01-10",
        "close": 110.0,
        "breakout_above_prior_20d_high_pct": 0.10,
    }
    trade.update(overrides)
    return trade


def test_infers_prior_20d_breakout_pivot_from_signal_close_and_breakout_pct():
    pivot, source = infer_breakout_pivot_level(_trade())

    assert round(pivot, 4) == 100.0
    assert source == "inferred_prior_20d_high_from_breakout_above_prior_20d_high_pct"


def test_constructive_when_latest_prior_swing_low_is_above_prior_swing_low():
    context = compute_pre_signal_base_geometry_context(
        _rows([100.0, 95.0, 101.0, 104.0, 98.0, 106.0, 108.0, 102.0, 109.0, 80.0]),
        _trade(close=121.0),
    )

    assert context["pre_signal_base_geometry_bucket_v1"] == BUCKET_CONSTRUCTIVE
    assert context["latest_pre_signal_swing_low"] == 102.0
    assert context["prior_pre_signal_swing_low"] == 98.0


def test_equal_latest_swing_low_does_not_pass_constructive_bucket():
    context = compute_pre_signal_base_geometry_context(
        _rows([100.0, 95.0, 101.0, 104.0, 95.0, 106.0, 108.0, 95.0, 109.0, 80.0]),
        _trade(),
    )

    assert context["pre_signal_base_geometry_bucket_v1"] == BUCKET_NONCONSTRUCTIVE
    assert context["latest_swing_low_vs_prior_pct"] == 0.0


def test_signal_date_is_excluded_from_prior_support_calculation():
    context = compute_pre_signal_base_geometry_context(
        _rows([100.0, 95.0, 101.0, 104.0, 106.0, 108.0, 109.0, 110.0, 112.0, 98.0]),
        _trade(),
    )

    assert context["pre_signal_base_geometry_bucket_v1"] == BUCKET_INSUFFICIENT
    assert context["pre_signal_observed_end_date"] == "2026-01-09"
    assert context["latest_pre_signal_swing_low"] == 95.0


def test_future_rows_are_not_inspected():
    before_future = compute_pre_signal_base_geometry_context(
        _rows([100.0, 95.0, 101.0, 104.0, 98.0, 106.0, 108.0, 102.0, 109.0]),
        _trade(close=121.0),
    )
    after_future = compute_pre_signal_base_geometry_context(
        _rows(
            [
                100.0,
                95.0,
                101.0,
                104.0,
                98.0,
                106.0,
                108.0,
                102.0,
                109.0,
                40.0,
                130.0,
                20.0,
            ]
        ),
        _trade(close=121.0),
    )

    assert after_future["pre_signal_base_geometry_bucket_v1"] == before_future[
        "pre_signal_base_geometry_bucket_v1"
    ]
    assert after_future["pre_signal_swing_lows_last3"] == before_future[
        "pre_signal_swing_lows_last3"
    ]


def test_missing_low_in_prior_window_yields_unavailable():
    context = compute_pre_signal_base_geometry_context(
        _rows([100.0, 95.0, None, 104.0, 98.0, 106.0, 108.0, 102.0, 109.0]),
        _trade(),
    )

    assert context["pre_signal_base_geometry_bucket_v1"] == BUCKET_UNAVAILABLE
    assert context["pre_signal_base_geometry_unavailable_reason"] == (
        "missing_low_in_prior_window"
    )
