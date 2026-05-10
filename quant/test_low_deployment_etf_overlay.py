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
    assert snapshot["closed_count_today"] == 1
    assert snapshot["closed_today"][0]["notional_usd"] == 125_000.0
    assert snapshot["closed_today"][0]["pnl"] > 0


def test_low_deployment_overlay_blocks_when_core_book_is_deployed():
    ohlcv = {
        "QQQ": _rows(100.0, 0.003),
        "SPY": _rows(100.0, 0.001),
    }
    snapshot = build_low_deployment_etf_overlay_snapshot(
        as_of="2025-08-18",
        ohlcv_by_ticker=ohlcv,
        open_positions={
            "positions": [
                {"ticker": "NVDA", "shares": 10},
                {"ticker": "META", "shares": 5},
            ]
        },
        portfolio_value=125_000.0,
        state=empty_low_deployment_etf_overlay_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["closed_count_today"] == 0
    assert snapshot["skipped_today"][0]["reason"] == "active_core_positions_above_threshold"


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
