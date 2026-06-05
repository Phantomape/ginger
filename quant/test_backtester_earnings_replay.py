import os
import sys
from datetime import date
import json

import pandas as pd


sys.path.insert(0, os.path.dirname(__file__))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_earnings_data  # noqa: E402
from feature_layer import compute_earnings_features  # noqa: E402


def test_backtester_uses_calendar_dte_and_snapshot_eps_context():
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

    assert data["next_earnings_date"] == "2026-08-06"
    assert data["days_to_earnings"] == 65
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


def test_backtester_does_not_use_prior_snapshot_dte_for_calendar_fields():
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

    assert data["next_earnings_date"] == "2026-08-06"
    assert data["days_to_earnings"] == 65


def test_non_earnings_asset_earnings_data_skips_yfinance(monkeypatch):
    def fail_ticker(ticker):
        raise AssertionError(f"yfinance should not be called for {ticker}")

    monkeypatch.setattr("data_layer.yf.Ticker", fail_ticker)

    data = get_earnings_data("SPY", as_of=date(2026, 5, 7))

    assert data["next_earnings_date"] is None
    assert data["days_to_earnings"] is None
    assert data["historical_surprise_pct"] == []


def test_backtester_earnings_calendar_skips_non_earnings_assets(monkeypatch):
    calls = []

    class FakeTicker:
        def __init__(self, ticker):
            calls.append(ticker)

        def get_earnings_dates(self, limit=20):
            return pd.DataFrame(
                {"Reported EPS": [1.0]},
                index=pd.to_datetime(["2026-05-07"]),
            )

    monkeypatch.setattr("backtester.yf.Ticker", FakeTicker)

    engine = BacktestEngine(["SPY", "AAA"], start="2026-05-07", end="2026-05-07")
    calendar = engine._download_earnings_calendar()

    assert calls == ["AAA"]
    assert calendar["SPY"] == []
    assert calendar["AAA"] == [date(2026, 5, 7)]


def test_backfill_earnings_snapshots_skips_non_earnings_prefetch(tmp_path, monkeypatch):
    from backfill_earnings_snapshots import backfill_earnings_snapshots

    calls = []

    class FakeTicker:
        def __init__(self, ticker):
            calls.append(ticker)
            self.info = {"forwardEps": 2.5}
            self.calendar = None

        def get_earnings_dates(self, limit=20):
            return pd.DataFrame(
                {
                    "Reported EPS": [1.1, None],
                    "Surprise(%)": [7.0, None],
                    "EPS Estimate": [None, 1.25],
                },
                index=pd.to_datetime(["2026-01-20", "2026-01-23"]),
            )

    monkeypatch.setattr("backfill_earnings_snapshots.yf.Ticker", FakeTicker)

    written = backfill_earnings_snapshots(
        "2026-01-21",
        "2026-01-21",
        universe=["SPY", "AAA"],
        data_dir=str(tmp_path),
    )

    assert calls == ["AAA"]
    assert len(written) == 1

    payload = json.loads((tmp_path / "earnings_snapshot_20260121.json").read_text())
    assert payload["earnings"]["SPY"]["days_to_earnings"] is None
    assert payload["earnings"]["AAA"]["days_to_earnings"] == 2
