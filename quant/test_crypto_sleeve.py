from datetime import datetime, timezone

import pandas as pd

from crypto_sleeve import (
    build_crypto_snapshot,
    build_rebalance_action,
    completed_daily_bars,
    decide_crypto_target,
)


def test_decide_crypto_target_full_risk_on():
    snapshot = {
        "close": 120.0,
        "ema20": 110.0,
        "ema100": 100.0,
        "sma200": 105.0,
    }

    decision = decide_crypto_target(snapshot)

    assert decision["state"] == "RISK_ON_FULL"
    assert decision["target_position_pct"] == 1.0


def test_decide_crypto_target_partial_when_below_200_day():
    snapshot = {
        "close": 120.0,
        "ema20": 110.0,
        "ema100": 100.0,
        "sma200": 125.0,
    }

    decision = decide_crypto_target(snapshot)

    assert decision["state"] == "RISK_ON_PARTIAL"
    assert decision["target_position_pct"] == 0.70


def test_decide_crypto_target_risk_off_when_trend_switch_off():
    snapshot = {
        "close": 95.0,
        "ema20": 98.0,
        "ema100": 100.0,
        "sma200": 105.0,
    }

    decision = decide_crypto_target(snapshot)

    assert decision["state"] == "RISK_OFF"
    assert decision["target_position_pct"] == 0.0


def test_build_rebalance_action_uses_sleeve_value_threshold():
    config = {
        "sleeve_value_usd": 8000.0,
        "current_position_pct": 1.0,
        "min_rebalance_delta_pct": 0.10,
    }

    action = build_rebalance_action(0.70, config)

    assert action["action"] == "SELL"
    assert action["trade_value_usd"] == -2400.0


def test_build_rebalance_action_holds_for_small_delta():
    config = {
        "sleeve_value_usd": 8000.0,
        "current_position_pct": 0.66,
        "min_rebalance_delta_pct": 0.10,
    }

    action = build_rebalance_action(0.70, config)

    assert action["action"] == "HOLD"
    assert action["trade_value_usd"] == 320.0


def test_completed_daily_bars_drops_partial_utc_day():
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1.0, 1.0],
        },
        index=pd.to_datetime(["2026-05-03", "2026-05-04"]),
    )

    completed = completed_daily_bars(
        df,
        now=datetime(2026, 5, 4, 20, 30, tzinfo=timezone.utc),
    )

    assert list(completed.index.date) == [datetime(2026, 5, 3).date()]


def test_build_crypto_snapshot_uses_latest_completed_bar():
    dates = pd.date_range("2025-01-01", periods=230, freq="D")
    close = pd.Series(range(230), index=dates, dtype=float) + 100
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1.0,
        }
    )

    snapshot = build_crypto_snapshot(
        df,
        now=datetime(2025, 8, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert snapshot["asof_date"] == "2025-08-18"
    assert snapshot["close"] == 329.0
    assert snapshot["ema20"] is not None
    assert snapshot["sma200"] is not None

