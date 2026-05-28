import os
import sys

import pandas as pd


sys.path.insert(0, os.path.dirname(__file__))

from feature_layer import compute_trend_features  # noqa: E402


def test_compute_trend_features_includes_daily_close_location():
    dates = pd.date_range("2026-01-01", periods=21, freq="B")
    rows = []
    for index, date in enumerate(dates):
        price = 100.0 + index
        rows.append(
            {
                "Date": date,
                "Open": price,
                "High": price + 4.0,
                "Low": price - 4.0,
                "Close": price,
                "Volume": 1_000_000 + index,
            }
        )
    rows[-1]["High"] = 120.0
    rows[-1]["Low"] = 100.0
    rows[-1]["Close"] = 115.0
    frame = pd.DataFrame(rows)

    features = compute_trend_features(frame)

    assert features["daily_close_location"] == 0.75
