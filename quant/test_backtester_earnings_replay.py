import os
import sys
from datetime import date

import pandas as pd


sys.path.insert(0, os.path.dirname(__file__))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_earnings_data  # noqa: E402
from feature_layer import compute_earnings_features  # noqa: E402


def test_backtester_prefers_exact_daily_earnings_snapshot_for_dte():
    engine = BacktestEngine(["DDOG"], start="2026-05-07", end="2026-05-07")
    engine._earnings_snapshots = {
        "20260507": {
            "DDOG": {
                "next_earnings_date": "2026-05-07",
                "days_to_earnings": 0,
                "eps_estimate": 2.6427,
                "avg_historical_surprise_pct": 11.99,
            }
        }
    }

    data = engine._earnings_dict_for(
        pd.Timestamp("2026-05-07"),
        [date(2026, 8, 6)],
        ticker="DDOG",
    )

    assert data["next_earnings_date"] == "2026-05-07"
    assert data["days_to_earnings"] == 0
    assert data["eps_estimate"] == 2.6427
    assert data["avg_historical_surprise_pct"] == 11.99
    assert data["post_earnings_continuation_confirmed"] is False


def test_backtester_rolls_confirmed_same_day_earnings_to_next_future_date():
    engine = BacktestEngine(["DDOG"], start="2026-05-07", end="2026-05-07")
    engine._earnings_snapshots = {
        "20260507": {
            "DDOG": {
                "next_earnings_date": "2026-05-07",
                "days_to_earnings": 0,
                "eps_actual_last": 1.23,
                "eps_estimate": 2.6427,
                "avg_historical_surprise_pct": 11.99,
            }
        }
    }

    data = engine._earnings_dict_for(
        pd.Timestamp("2026-05-07"),
        [date(2026, 5, 7), date(2026, 8, 6)],
        ticker="DDOG",
    )

    assert data["last_earnings_date"] == "2026-05-07"
    assert data["days_since_last_earnings"] == 0
    assert data["next_earnings_date"] == "2026-08-06"
    assert data["days_to_earnings"] == 65
    assert data["post_earnings_continuation_confirmed"] is True
    assert data["post_earnings_event_date"] == "2026-05-07"
    assert data["eps_actual_last"] == 1.23


def test_data_layer_marks_same_day_post_earnings_continuation():
    dates_df = pd.DataFrame(
        {
            "Reported EPS": [1.23, None],
            "EPS Estimate": [1.0, 2.5],
            "Surprise(%)": [23.0, None],
        },
        index=pd.to_datetime(["2026-05-07", "2026-08-06"]),
    )

    data = get_earnings_data("DDOG", as_of=date(2026, 5, 7), dates_df=dates_df)
    features = compute_earnings_features(data)

    assert data["last_earnings_date"] == "2026-05-07"
    assert data["days_since_last_earnings"] == 0
    assert data["next_earnings_date"] == "2026-08-06"
    assert data["days_to_earnings"] == 65
    assert features["post_earnings_continuation_confirmed"] is True
    assert features["post_earnings_event_date"] == "2026-05-07"


def test_backtester_recomputes_prior_snapshot_dte_from_snapshot_date():
    engine = BacktestEngine(["DDOG"], start="2026-05-07", end="2026-05-07")
    engine._earnings_snapshots = {
        "20260506": {
            "DDOG": {
                "next_earnings_date": "2026-05-08",
                "days_to_earnings": 2,
            }
        }
    }

    data = engine._earnings_dict_for(
        pd.Timestamp("2026-05-07"),
        [date(2026, 8, 6)],
        ticker="DDOG",
    )

    assert data["next_earnings_date"] == "2026-05-08"
    assert data["days_to_earnings"] == 1
