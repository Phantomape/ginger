from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_008_vcp_top2_followthrough_failure_attribution import (  # noqa: E402
    STATUS_ADVANCED,
    STATUS_FAILED,
    STATUS_HELD,
    STATUS_UNAVAILABLE,
    compute_post_entry_follow_through_context,
    infer_breakout_pivot_level,
)


def _rows(closes: list[float], *, start: date = date(2026, 1, 1)) -> list[dict]:
    rows = []
    for idx, close in enumerate(closes):
        rows.append(
            {
                "Date": (start + timedelta(days=idx)).isoformat(),
                "Open": close,
                "High": close + 1.0,
                "Low": close - 1.0,
                "Close": close,
                "Volume": 1_000_000,
            }
        )
    return rows


def _trade(**overrides):
    trade = {
        "ticker": "AAA",
        "signal_date": "2026-01-01",
        "entry_date": "2026-01-02",
        "entry_price": 104.0,
        "close": 105.0,
        "breakout_above_prior_20d_high_pct": 0.05,
    }
    trade.update(overrides)
    return trade


def test_infers_prior_20d_breakout_pivot_from_signal_close_and_breakout_pct():
    pivot, source = infer_breakout_pivot_level(_trade())

    assert round(pivot, 4) == 100.0
    assert source == "inferred_prior_20d_high_from_breakout_above_prior_20d_high_pct"


def test_marks_failure_when_any_first_three_entry_sessions_close_below_pivot():
    context = compute_post_entry_follow_through_context(
        _rows([95.0, 104.0, 99.5, 106.0, 110.0]),
        _trade(),
    )

    assert context["post_entry_follow_through_status_3d"] == STATUS_FAILED
    assert context["first_failed_below_pivot_date_3d"] == "2026-01-03"


def test_equal_pivot_close_does_not_fail():
    context = compute_post_entry_follow_through_context(
        _rows([95.0, 100.0, 100.1, 104.5, 80.0]),
        _trade(),
    )

    assert context["post_entry_follow_through_status_3d"] == STATUS_HELD
    assert context["first_failed_below_pivot_date_3d"] is None


def test_advances_when_pivot_holds_and_third_entry_session_beats_signal_close():
    context = compute_post_entry_follow_through_context(
        _rows([95.0, 103.0, 104.0, 106.0, 80.0]),
        _trade(),
    )

    assert context["post_entry_follow_through_status_3d"] == STATUS_ADVANCED
    assert context["observed_dates_3d"] == ["2026-01-02", "2026-01-03", "2026-01-04"]


def test_does_not_inspect_signal_day_or_fourth_entry_session():
    context = compute_post_entry_follow_through_context(
        _rows([1.0, 103.0, 104.0, 106.0, 80.0]),
        _trade(),
    )

    assert context["post_entry_follow_through_status_3d"] == STATUS_ADVANCED
    assert context["observed_dates_3d"] == ["2026-01-02", "2026-01-03", "2026-01-04"]


def test_missing_third_entry_session_is_unavailable():
    context = compute_post_entry_follow_through_context(
        _rows([95.0, 103.0, 104.0]),
        _trade(),
    )

    assert context["post_entry_follow_through_status_3d"] == STATUS_UNAVAILABLE
    assert context["post_entry_follow_through_unavailable_reason"] == (
        "fewer_than_3_entry_or_post_entry_rows"
    )
