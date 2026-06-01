import os
import sys
from datetime import date

import pandas as pd


sys.path.insert(0, os.path.dirname(__file__))

from backtester import BacktestEngine  # noqa: E402


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
