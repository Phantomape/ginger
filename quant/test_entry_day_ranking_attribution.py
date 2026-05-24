from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parent))

from daily_context_archive import build_daily_context_archive  # noqa: E402
from entry_day_ranking_attribution import (  # noqa: E402
    build_entry_day_ranking_attribution,
)


def _frame(start, step, periods=35):
    dates = pd.bdate_range("2026-01-01", periods=periods)
    rows = []
    for idx, date in enumerate(dates):
        close = start + step * idx
        rows.append({
            "Date": date,
            "Open": close - 0.2,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": 1_000_000 + idx * 1_000,
        })
    frame = pd.DataFrame(rows).set_index("Date")
    frame.index.name = None
    return frame


def test_daily_context_archive_includes_canonical_state_vectors():
    features = {
        "AAA": {
            "ticker": "AAA",
            "close": 50.0,
            "trend_score": 0.8,
            "breakout_20d": True,
            "above_200ma": True,
            "momentum_20d_pct": 0.24,
            "momentum_60d_pct": 0.42,
        },
        "SPY": {
            "ticker": "SPY",
            "close": 500.0,
            "trend_score": 0.4,
            "breakout_20d": False,
            "above_200ma": True,
            "momentum_20d_pct": 0.02,
            "momentum_60d_pct": 0.05,
        },
    }

    payload = build_daily_context_archive(
        as_of_date="2026-01-30",
        universe=["AAA", "SPY"],
        features_dict=features,
        market_regime={"regime": "BULL"},
    )

    vectors = payload["canonical_state_vectors"]
    assert vectors["read_only"] is True
    assert "AAA" in vectors["ticker_vectors"]
    assert vectors["ticker_vectors"]["AAA"]["leadership_vector"]["state"] in {
        "strong",
        "neutral",
        "weak",
    }
    assert payload["production_impact"]["alters_orders"] is False


def test_entry_day_ranking_attribution_uses_previous_trading_day_context():
    ohlcv = {
        "AAA": _frame(20.0, 1.0),
        "BBB": _frame(80.0, -0.1),
        "SPY": _frame(400.0, 0.2),
    }
    entry_date = str(ohlcv["AAA"].index[30].date())
    expected_asof = str(ohlcv["AAA"].index[29].date())
    result = {
        "period": "unit",
        "expected_value_score": 1.23,
        "trades": [
            {
                "ticker": "AAA",
                "strategy": "trend_long",
                "entry_date": entry_date,
                "exit_date": str(ohlcv["AAA"].index[34].date()),
                "entry_price": 50.0,
                "exit_price": 54.0,
                "stop_price": 47.0,
                "shares": 10,
                "pnl": 40.0,
            }
        ],
    }

    report = build_entry_day_ranking_attribution(result=result, ohlcv=ohlcv)

    assert report["coverage"]["point_in_time_safe_coverage"] == 1.0
    assert report["coverage"]["policy_research_ready"] is True
    trade = report["annotated_trades"][0]
    assert trade["signal_asof_date"] == expected_asof
    assert trade["point_in_time_safe"] is True
    assert trade["alpha_score"] is not None
    assert trade["leadership_vector_state"] in {"strong", "neutral", "weak"}

    component_attribution = report["component_attribution"]
    assert "trend" in component_attribution
    trend = component_attribution["trend"]
    assert trend["coverage"]["coverage"] == 1.0
    assert trend["value_diagnostics"]["unique_value_count"] >= 1
    assert sum(row["trades"] for row in trend["buckets"]) == 1
