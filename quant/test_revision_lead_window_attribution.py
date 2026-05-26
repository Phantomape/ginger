from __future__ import annotations

from datetime import date
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "experiments"))

from exp_20260525_031_revision_lead_window_attribution import (  # noqa: E402
    classify_revision_row,
    find_revision_lead_match,
    next_trading_date_on_or_after,
    trading_day_distance,
)


def test_weekend_revision_effective_date_maps_to_next_trade_date():
    trading_dates = [
        date(2026, 5, 8),
        date(2026, 5, 11),
        date(2026, 5, 12),
    ]

    assert next_trading_date_on_or_after("2026-05-09", trading_dates) == date(2026, 5, 11)
    assert trading_day_distance(date(2026, 5, 11), date(2026, 5, 12), trading_dates) == 1


def test_positive_revision_lead_match_includes_cohr_like_weekend_to_monday():
    trading_dates = [
        date(2026, 5, 8),
        date(2026, 5, 11),
        date(2026, 5, 12),
        date(2026, 5, 13),
    ]
    positive_index = {
        "COHR": [
            {
                "ticker": "COHR",
                "revision_as_of_date": "2026-05-09",
                "revision_effective_trade_date": "2026-05-11",
                "eps_estimate_delta_prev": 0.06,
                "revision_direction_prev": "up",
            }
        ]
    }

    match = find_revision_lead_match(
        ticker="COHR",
        candidate_as_of="2026-05-11",
        positive_revision_index=positive_index,
        trading_dates=trading_dates,
    )

    assert match["matched"] is True
    assert match["revision_lead_trading_days"] == 0
    assert match["revision_lead_calendar_days"] == 2
    assert match["eps_estimate_delta_prev"] == 0.06


def test_positive_revision_classification_requires_usable_positive_prev_delta():
    usable_positive = classify_revision_row(
        {"estimate_revision_usable": True, "eps_estimate_delta_prev": 0.01}
    )
    unusable_positive = classify_revision_row(
        {"estimate_revision_usable": False, "eps_estimate_delta_prev": 0.01}
    )
    usable_flat = classify_revision_row(
        {"estimate_revision_usable": True, "eps_estimate_delta_prev": 0.0}
    )

    assert usable_positive["positive_revision"] is True
    assert unusable_positive["positive_revision"] is False
    assert usable_flat["positive_revision"] is False
