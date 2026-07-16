import math
import sys
from pathlib import Path

import pandas as pd
import pytest

from active_book_marginal_variance import (
    apply_scalar_to_sizing,
    evaluate_active_book_marginal_variance,
    sample_covariance,
)

EXPERIMENTS = Path(__file__).resolve().parent / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))
from exp_20260716_001_active_book_marginal_variance import (  # noqa: E402
    _returns_through_signal_day,
)


def _returns(count=60, *, sign=1.0, offset=0):
    return {
        f"2025-{1 + ((day + offset) // 28):02d}-{1 + ((day + offset) % 28):02d}":
        sign * (((day % 7) - 3) / 100.0)
        for day in range(count)
    }


def test_sample_covariance_requires_aligned_inputs():
    assert sample_covariance([1.0, 2.0], [2.0, 4.0]) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        sample_covariance([1.0], [1.0, 2.0])


def test_no_active_book_fails_open():
    result = evaluate_active_book_marginal_variance(_returns(), 10_000.0, [])
    assert result == {
        "status": "no_active_book",
        "scalar": 1.0,
        "lookback_returns": 60,
    }


def test_positive_identical_covariance_uses_preregistered_root():
    returns = _returns()
    result = evaluate_active_book_marginal_variance(
        returns,
        10_000.0,
        [{"ticker": "AAA", "notional_usd": 10_000.0, "returns_by_date": returns}],
    )
    assert result["status"] == "applied"
    assert result["cross_covariance"] == pytest.approx(
        2.0 * result["standalone_variance"]
    )
    assert result["scalar"] == pytest.approx(math.sqrt(2.0) - 1.0)


def test_negative_covariance_does_not_penalize_candidate():
    returns = _returns()
    inverse = {day: -value for day, value in returns.items()}
    result = evaluate_active_book_marginal_variance(
        returns,
        10_000.0,
        [{"ticker": "HEDGE", "notional_usd": 10_000.0, "returns_by_date": inverse}],
    )
    assert result["status"] == "nonpositive_cross_covariance"
    assert result["cross_covariance"] < 0
    assert result["scalar"] == 1.0


def test_requires_sixty_joint_dates_and_uses_common_alignment():
    candidate = _returns(61)
    insufficient = _returns(59)
    result = evaluate_active_book_marginal_variance(
        candidate,
        1_000.0,
        [{"ticker": "SHORT", "notional_usd": 2_000.0, "returns_by_date": insufficient}],
    )
    assert result["status"] == "insufficient_joint_history"
    assert result["joint_history_count"] == 59

    active = dict(candidate)
    active.pop(next(iter(active)))
    aligned = evaluate_active_book_marginal_variance(
        candidate,
        1_000.0,
        [{"ticker": "ALIGNED", "notional_usd": 2_000.0, "returns_by_date": active}],
    )
    assert aligned["joint_history_count"] == 60


def test_sizing_application_is_copy_only_and_preserves_one_share_floor():
    original = {
        "shares_to_buy": 10,
        "position_value_usd": 1000.0,
        "position_pct_of_portfolio": 0.01,
        "risk_amount_usd": 100.0,
        "risk_pct": 0.001,
        "base_risk_pct": 0.002,
    }
    updated, audit = apply_scalar_to_sizing(original, 0.01)
    assert original["shares_to_buy"] == 10
    assert updated["shares_to_buy"] == 1
    assert updated["position_value_usd"] == pytest.approx(100.0)
    assert updated["risk_pct"] == pytest.approx(0.0001)
    assert updated["base_risk_pct"] == original["base_risk_pct"]
    assert audit["realized_scalar"] == pytest.approx(0.1)


def test_runner_return_window_is_contiguous_and_future_invariant():
    sessions = list(pd.bdate_range("2025-01-02", periods=62))
    today = sessions[-2]
    frame = pd.DataFrame(
        {"Close": [100.0 + index for index in range(62)]}, index=sessions
    )
    before, audit = _returns_through_signal_day(frame, today, sessions)
    assert before is not None
    assert len(before) == 60
    assert audit["aligned_end"] == str(today)[:10]
    assert audit["asof_boundary_passed"] is True

    frame.loc[sessions[-1], "Close"] = 1_000_000.0
    after, after_audit = _returns_through_signal_day(frame, today, sessions)
    assert after == before
    assert after_audit == audit


def test_runner_return_window_fails_open_on_missing_required_session():
    sessions = list(pd.bdate_range("2025-01-02", periods=61))
    frame = pd.DataFrame(
        {"Close": [100.0 + index for index in range(60)]}, index=sessions[:-1]
    )
    returns, audit = _returns_through_signal_day(frame, sessions[-1], sessions)
    assert returns is None
    assert audit["status"] == "nonconsecutive_ticker_sessions"
    assert audit["missing_sessions"] == [str(sessions[-1])[:10]]
