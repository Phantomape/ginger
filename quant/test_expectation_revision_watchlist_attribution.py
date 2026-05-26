from __future__ import annotations

from datetime import date
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "experiments"))

from exp_20260525_034_expectation_revision_watchlist_attribution import (  # noqa: E402
    build_candidate_index,
    classify_revision_signal,
    effective_trade_date_on_or_after,
    find_candidate_hit,
    latest_feature_date_on_or_before,
    next_weekday_on_or_after,
)


def test_revision_signal_separates_primary_and_wide_watchlist():
    primary = classify_revision_signal(
        {
            "estimate_revision_usable": True,
            "eps_estimate_delta_7d": 0.03,
            "eps_estimate_delta_30d": -0.01,
            "eps_estimate_delta_prev": None,
        }
    )
    prev_only = classify_revision_signal(
        {
            "estimate_revision_usable": True,
            "eps_estimate_delta_7d": None,
            "eps_estimate_delta_30d": None,
            "eps_estimate_delta_prev": 0.02,
        }
    )
    unusable = classify_revision_signal(
        {
            "estimate_revision_usable": False,
            "eps_estimate_delta_7d": 0.10,
            "eps_estimate_delta_prev": 0.10,
        }
    )

    assert primary["primary_expectation_positive"] is True
    assert primary["wide_watchlist_positive"] is True
    assert primary["watchlist_signal_basis"] == ["primary_7d"]
    assert prev_only["primary_expectation_positive"] is False
    assert prev_only["wide_watchlist_positive"] is True
    assert prev_only["watchlist_signal_basis"] == ["scout_prev"]
    assert unusable["wide_watchlist_positive"] is False


def test_future_weekend_watchlist_stays_pending_without_known_trade_date():
    trading_dates = [date(2026, 5, 22)]

    assert next_weekday_on_or_after("2026-05-24") == date(2026, 5, 25)

    effective, source = effective_trade_date_on_or_after("2026-05-24", trading_dates)

    assert effective is None
    assert source == "pending_future_trading_calendar"


def test_candidate_hit_uses_forward_trading_window_only():
    trading_dates = [
        date(2026, 5, 8),
        date(2026, 5, 11),
        date(2026, 5, 12),
        date(2026, 5, 13),
        date(2026, 5, 14),
    ]
    candidates = [
        {
            "as_of_date": "2026-05-08",
            "ticker": "AAA",
            "candidate_source": "signals",
            "record_type": "selected_signal",
            "selected_signal": True,
            "strategy": "trend_long",
        },
        {
            "as_of_date": "2026-05-13",
            "ticker": "AAA",
            "candidate_source": "pilot_signals",
            "record_type": "selected_pilot_signal",
            "selected_signal": True,
            "strategy": "breakout_long",
        },
    ]

    index = build_candidate_index(candidates, trading_dates)
    hit = find_candidate_hit(
        ticker="AAA",
        effective_date=date(2026, 5, 11),
        candidate_index=index,
        trading_dates=trading_dates,
        max_trading_days=3,
    )

    assert hit["hit"] is True
    assert hit["candidate_hit_trading_days"] == 2
    assert hit["candidate_hit"]["candidate_as_of_date"] == "2026-05-13"


def test_latest_feature_date_never_uses_future_context():
    feature_dates = [date(2026, 5, 8), date(2026, 5, 12)]

    assert latest_feature_date_on_or_before("2026-05-11", feature_dates) == date(2026, 5, 8)
    assert latest_feature_date_on_or_before("2026-05-07", feature_dates) is None
