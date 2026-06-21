from __future__ import annotations

from datetime import date, timedelta

import pytest

from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report
from quant.report_generator import generate_daily_report
from quant.volatility_relief_stock_leadership_paper_sleeve import (
    SLEEVE_NAME,
    SOURCE_RULE_VERSION,
    build_volatility_relief_stock_leadership_historical_trades,
    build_volatility_relief_stock_leadership_snapshot,
    empty_volatility_relief_stock_leadership_state,
    prep_and_build_volatility_relief_stock_leadership_snapshot,
)


def _rows(
    *,
    start_price: float,
    daily_step: float,
    event_gain: float = 0.0,
    event_date: str = "2025-01-15",
    days: int = 145,
) -> list[dict[str, float | str]]:
    start = date(2024, 10, 1)
    price = start_price
    out: list[dict[str, float | str]] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        day_text = day.isoformat()
        open_price = price
        gain = event_gain if day_text == event_date else daily_step
        close = open_price * (1.0 + gain)
        high = max(open_price, close) * 1.002
        low = min(open_price, close) * 0.998
        volume = 8_000_000 if day_text == event_date else 5_000_000
        out.append(
            {
                "date": day_text,
                "open": round(open_price, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume,
            }
        )
        price = close
    return out


def _universe(*tickers: str) -> dict:
    return {
        "status": "test_broad_market_universe",
        "tickers": list(tickers),
        "records": {
            ticker: {"sector": "Technology", "industry": "Software"}
            for ticker in tickers
        },
    }


def _ohlcv() -> dict:
    return {
        "VIXY": _rows(start_price=100.0, daily_step=-0.0005, event_gain=-0.052),
        "SPY": _rows(start_price=100.0, daily_step=0.0008, event_gain=0.012),
        "QQQ": _rows(start_price=100.0, daily_step=0.0010, event_gain=0.014),
        "AAA": _rows(start_price=70.0, daily_step=0.0018, event_gain=0.055),
        "BBB": _rows(start_price=60.0, daily_step=0.0016, event_gain=0.039),
        "CCC": _rows(start_price=55.0, daily_step=0.0015, event_gain=0.024),
    }


def test_volatility_relief_leadership_selects_top_two_without_orders() -> None:
    snapshot = build_volatility_relief_stock_leadership_snapshot(
        as_of="2025-01-15",
        ohlcv_by_ticker=_ohlcv(),
        candidate_universe=_universe("AAA", "BBB", "CCC"),
        state=empty_volatility_relief_stock_leadership_state(),
        persist=False,
    )

    assert snapshot["sleeve"] == SLEEVE_NAME
    assert snapshot["source_rule_version"] == SOURCE_RULE_VERSION
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    assert snapshot["volatility_relief_context"]["passed"] is True
    assert snapshot["raw_candidate_count"] == 3
    assert snapshot["candidate_count"] == 2
    assert [row["ticker"] for row in snapshot["candidates"]] == ["AAA", "BBB"]
    assert snapshot["new_pending_count"] == 2
    assert snapshot["pending_entries"][0]["paper_status"] == "pending_entry"
    assert snapshot["pending_entries"][0]["entry_timing"] == "next_session_open"


def test_prep_handles_dataframe_index_fallbacks_without_boolean_coercion() -> None:
    pd = pytest.importorskip("pandas")
    ohlcv = _ohlcv()

    def frame(rows: list[dict]) -> object:
        return pd.DataFrame(rows).set_index("date")

    snapshot = prep_and_build_volatility_relief_stock_leadership_snapshot(
        as_of="2025-01-15",
        broad_market_ohlcv={
            "SPY": frame(ohlcv["SPY"]),
            "AAA": frame(ohlcv["AAA"]),
        },
        broad_market_candidate_universe=_universe("AAA"),
        ohlcv_dict={
            "QQQ": frame(ohlcv["QQQ"]),
            "VIXY": frame(ohlcv["VIXY"]),
        },
        persist=False,
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["volatility_relief_context"]["passed"] is True


def test_volatility_relief_historical_and_daily_candidate_semantics_match() -> None:
    ohlcv = _ohlcv()
    historical = build_volatility_relief_stock_leadership_historical_trades(
        ohlcv_by_ticker=ohlcv,
        dates=["2025-01-15"],
        candidate_universe=_universe("AAA", "BBB", "CCC"),
    )
    daily = build_volatility_relief_stock_leadership_snapshot(
        as_of="2025-01-15",
        ohlcv_by_ticker=ohlcv,
        candidate_universe=_universe("AAA", "BBB", "CCC"),
        state=empty_volatility_relief_stock_leadership_state(),
        persist=False,
    )

    assert [row["ticker"] for row in historical["trades"]] == ["AAA", "BBB"]
    assert [row["ticker"] for row in daily["candidates"]] == ["AAA", "BBB"]
    assert historical["trades"][0]["entry_date"] == "2025-01-16"
    assert historical["trades"][0]["exit_date"] == "2025-01-25"
    assert daily["candidates"][0]["decision_id"] == historical["trades"][0]["decision_id"]


def test_volatility_relief_leadership_skips_non_relief_day() -> None:
    snapshot = build_volatility_relief_stock_leadership_snapshot(
        as_of="2025-01-16",
        ohlcv_by_ticker=_ohlcv(),
        candidate_universe=_universe("AAA"),
        state=empty_volatility_relief_stock_leadership_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["volatility_relief_context"]["passed"] is False
    assert snapshot["trade_enabled"] is False


def test_default_off_attribution_and_report_include_volatility_relief_surface() -> None:
    snapshot = {
        "sleeve": SLEEVE_NAME,
        "rule_version": "volatility_relief_stock_leadership_shared_default_off_adapter_v1",
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
        "candidate_count": 1,
        "raw_candidate_count": 3,
        "candidate_universe": {
            "status": "test_broad_market_universe",
            "ticker_count": 3,
        },
        "context_scan": {"volatility_relief_days": 1},
        "volatility_relief_context": {"passed": True, "vixy_return": -0.052},
        "candidates": [
            {
                "ticker": "AAA",
                "candidate_score": 0.58,
                "candidate_relative_vs_spy": 0.02,
                "signal_date": "2025-01-15",
                "paper_notional_usd": 4_000.0,
            }
        ],
        "forward_paper_gate": {
            "passed": False,
            "status": "blocked",
            "reasons": ["min_closed_trades"],
            "metrics": {"closed_trades": 0, "realized_pnl": 0.0},
        },
        "production_impact": {"uses_free_ohlcv_only": True},
    }

    attribution = build_default_off_alpha_attribution_report(
        as_of="2025-01-15",
        volatility_relief_stock_leadership_paper_sleeve=snapshot,
    )
    surfaces = {row["name"]: row for row in attribution["surfaces"]}

    assert surfaces["volatility_relief_stock_leadership"]["label"] == SLEEVE_NAME
    assert surfaces["volatility_relief_stock_leadership"]["trade_enabled"] is False
    assert (
        surfaces["volatility_relief_stock_leadership"]["extra_metrics"][
            "volatility_relief_days"
        ]
        == 1
    )
    assert "min_closed_trades" in surfaces["volatility_relief_stock_leadership"]["blockers"]

    report = generate_daily_report(
        signals=[],
        volatility_relief_stock_leadership_paper_sleeve=snapshot,
    )

    assert "VOLATILITY RELIEF LEADERSHIP PAPER SLEEVE" in report
    assert "AAA: score=0.58" in report
