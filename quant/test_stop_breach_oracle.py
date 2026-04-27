import pytest

from stop_breach_oracle import (
    ATR_STOP_MULT,
    ROUND_TRIP_COST_PCT,
    build_stop_breach_oracle,
    _simulate_reanchored_trade,
)


def test_reanchored_trade_uses_conservative_stop_first_ordering():
    result = _simulate_reanchored_trade(
        entry_open=100.0,
        atr=2.0,
        rows=[
            {
                "Date": "2026-01-02",
                "Open": 100.0,
                "High": 110.0,
                "Low": 90.0,
                "Close": 105.0,
            }
        ],
    )

    assert result["exit_reason"] == "stop"
    expected_stop_return = ((100.0 - ATR_STOP_MULT * 2.0) * (1 - ROUND_TRIP_COST_PCT) / 100.0) - 1
    assert result["return_pct"] == pytest.approx(round(expected_stop_return, 6))


def test_build_stop_breach_oracle_reanchors_cancelled_entry():
    historical_rows = []
    close = 100.0
    for day in range(1, 16):
        historical_rows.append({
            "Date": f"2026-01-{day:02d}",
            "Open": close,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
        })
        close += 1.0
    historical_rows.append({
        "Date": "2026-01-16",
        "Open": 120.0,
        "High": 140.0,
        "Low": 119.0,
        "Close": 135.0,
    })

    backtest = {
        "entry_execution_attribution": {
            "sample_skips": [
                {
                    "date": "2026-01-15",
                    "ticker": "XYZ",
                    "strategy": "trend",
                    "candidate_rank": 1,
                    "decision": "stop_breach_cancel",
                    "details": {
                        "fill_date": "2026-01-16",
                        "fill_price": 120.0,
                        "stop_price": 121.0,
                    },
                }
            ]
        }
    }
    snapshot = {"ohlcv": {"XYZ": historical_rows}}

    result = build_stop_breach_oracle(backtest, snapshot, horizon_days=2)

    assert result["sample_count"] == 1
    assert result["missing_count"] == 0
    row = result["rows"][0]
    assert row["ticker"] == "XYZ"
    assert row["old_stop_price"] == 121.0
    assert row["reanchored_stop_price"] < row["entry_open"]
    assert row["exit_reason"] == "target"
