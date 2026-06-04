from __future__ import annotations

from datetime import date, timedelta

from low_deployment_etf_overlay import (
    SLEEVE_NAME,
    build_low_deployment_etf_overlay_snapshot,
    empty_low_deployment_etf_overlay_state,
)


def _rows(start_price: float, daily_step: float, intraday_step: float = 0.001):
    start = date(2025, 1, 1)
    rows = []
    price = start_price
    for idx in range(230):
        price = price * (1.0 + daily_step)
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(price, 4),
                "close": round(price * (1.0 + intraday_step), 4),
            }
        )
    return rows


def test_low_deployment_overlay_selects_best_prior_momentum_etf_without_orders():
    ohlcv = {
        "QQQ": _rows(100.0, 0.003),
        "SPY": _rows(100.0, 0.001),
        "IWM": _rows(100.0, -0.001),
        "GLD": _rows(100.0, 0.0005),
        "SLV": _rows(100.0, 0.0001),
    }
    snapshot = build_low_deployment_etf_overlay_snapshot(
        as_of="2025-08-18",
        ohlcv_by_ticker=ohlcv,
        open_positions={"positions": []},
        portfolio_value=125_000.0,
        state=empty_low_deployment_etf_overlay_state(),
        persist=False,
    )

    assert snapshot["sleeve"] == SLEEVE_NAME
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    assert snapshot["candidate"]["ticker"] == "QQQ"
    assert snapshot["candidate"]["slot_policy"] == "sleeve_independent_paper_slot"
    assert snapshot["candidate"]["low_deployment_condition_passed"] is True
    assert snapshot["candidate"]["core_capacity_blocks_observation"] is False
    assert snapshot["closed_count_today"] == 1
    assert snapshot["closed_today"][0]["notional_usd"] == 125_000.0
    assert snapshot["closed_today"][0]["pnl"] > 0


def test_low_deployment_overlay_uses_independent_slot_when_core_book_is_deployed():
    ohlcv = {
        "QQQ": _rows(100.0, 0.003),
        "SPY": _rows(100.0, 0.001),
    }
    snapshot = build_low_deployment_etf_overlay_snapshot(
        as_of="2025-08-18",
        ohlcv_by_ticker=ohlcv,
        open_positions={
            "positions": [
                {"ticker": "NVDA", "shares": 10, "opened_by_strategy": "trend_long"},
                {"ticker": "META", "shares": 5, "opened_by_strategy": "breakout_long"},
            ]
        },
        portfolio_value=125_000.0,
        state=empty_low_deployment_etf_overlay_state(),
        config={"max_active_core_positions": 1},
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["candidate"]["ticker"] == "QQQ"
    assert snapshot["candidate"]["slot_policy"] == "sleeve_independent_paper_slot"
    assert snapshot["candidate"]["low_deployment_condition_passed"] is False
    assert snapshot["candidate"]["low_deployment_condition_status"] == (
        "core_above_reference_threshold"
    )
    assert snapshot["candidate"]["core_capacity_blocks_observation"] is False
    assert snapshot["closed_count_today"] == 1
    assert snapshot["skipped_today"] == []
    assert snapshot["closed_today"][0]["admission_reason"] == (
        "sleeve_independent_forward_observation_core_above_reference_threshold"
    )


def test_low_deployment_overlay_requires_positive_trend_and_momentum():
    ohlcv = {
        "QQQ": _rows(100.0, -0.002),
        "SPY": _rows(100.0, -0.001),
    }
    snapshot = build_low_deployment_etf_overlay_snapshot(
        as_of="2025-08-18",
        ohlcv_by_ticker=ohlcv,
        open_positions={"positions": []},
        portfolio_value=125_000.0,
        state=empty_low_deployment_etf_overlay_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["closed_count_today"] == 0
    assert snapshot["skipped_today"][0]["reason"] == "no_positive_trend_momentum_etf_candidate"
