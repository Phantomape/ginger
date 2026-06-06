from __future__ import annotations

from datetime import date, timedelta

from low_deployment_etf_overlay import (
    SLEEVE_NAME,
    build_low_deployment_etf_overlay_snapshot,
    empty_low_deployment_etf_overlay_state,
    replay_low_deployment_etf_cash_substitute_trades,
)


def _rows(start_price: float, daily_step: float, intraday_step: float = 0.001, days: int = 245):
    start = date(2025, 1, 1)
    rows = []
    price = start_price
    for idx in range(days):
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
    assert snapshot["candidate"]["entry_timing"] == "next_session_open"
    assert snapshot["new_pending_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["open_position_count"] == 0
    assert snapshot["closed_count_today"] == 0
    assert snapshot["new_pending_entries"][0]["notional_usd"] == 125_000.0
    assert snapshot["new_pending_entries"][0]["paper_status"] == "pending_entry"


def test_low_deployment_overlay_skips_candidate_when_core_book_is_deployed():
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

    assert snapshot["candidate_count"] == 0
    assert snapshot["pending_count"] == 0
    assert snapshot["closed_count_today"] == 0
    assert snapshot["low_deployment_condition_passed"] is False
    assert snapshot["skipped_today"][0]["reason"] == "core_above_low_deployment_threshold"


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


def test_shared_replay_uses_next_open_and_10_day_close_without_orders():
    ohlcv = {
        "QQQ": _rows(100.0, 0.003),
        "SPY": _rows(100.0, 0.001),
        "IWM": _rows(100.0, -0.001),
        "GLD": _rows(100.0, 0.0005),
        "SLV": _rows(100.0, 0.0001),
    }
    signal_date = "2025-08-08"
    core_result = {
        "equity_curve": [
            ((date(2025, 8, 8) + timedelta(days=idx)).isoformat(), 100000.0)
            for idx in range(12)
        ],
        "trades": [],
    }

    trades, diagnostics = replay_low_deployment_etf_cash_substitute_trades(
        core_backtest_result=core_result,
        ohlcv_by_ticker=ohlcv,
    )

    assert diagnostics["low_deployment_day_count"] == 12
    assert trades[0]["ticker"] == "QQQ"
    assert trades[0]["signal_date"] == signal_date
    assert trades[0]["entry_date"] == "2025-08-09"
    assert trades[0]["exit_date"] == "2025-08-18"
    assert trades[0]["hold_days"] == 10
    assert trades[0]["trade_enabled"] is False
    assert trades[0]["alters_orders"] is False
