from __future__ import annotations

from datetime import date, timedelta

from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report
from quant.move_rate_volatility_relief_paper_sleeve import (
    MOVE_DELIVERY_TICKER,
    RULE_VERSION,
    SLEEVE_NAME,
    SOURCE_RULE_VERSION,
    build_move_rate_volatility_relief_historical_trades,
    build_move_rate_volatility_relief_snapshot,
    empty_move_rate_volatility_relief_state,
    prep_and_build_move_rate_volatility_relief_snapshot,
)
from quant.report_generator import generate_daily_report


EVENT_DATE = "2025-01-15"


def _rows(start_price: float, daily_step: float, event_gain: float = 0.0) -> list[dict]:
    start = date(2024, 10, 1)
    price = start_price
    rows = []
    for offset in range(145):
        day_text = (start + timedelta(days=offset)).isoformat()
        open_price = price
        gain = event_gain if day_text == EVENT_DATE else daily_step
        close = open_price * (1.0 + gain)
        rows.append(
            {
                "date": day_text,
                "open": round(open_price, 4),
                "high": round(max(open_price, close) * 1.002, 4),
                "low": round(min(open_price, close) * 0.998, 4),
                "close": round(close, 4),
                "volume": 8_000_000 if day_text == EVENT_DATE else 5_000_000,
            }
        )
        price = close
    return rows


def _move_rows() -> list[dict]:
    rows = _rows(100.0, 0.0)
    for row in rows:
        if row["date"] == EVENT_DATE:
            row.update({"open": 100.0, "high": 100.0, "low": 90.0, "close": 90.0})
        elif row["date"] > EVENT_DATE:
            row.update({"open": 90.0, "high": 90.0, "low": 90.0, "close": 90.0})
    return rows


def _ohlcv() -> dict[str, list[dict]]:
    return {
        "MOVE": _move_rows(),
        "SPY": _rows(100.0, 0.0008, 0.012),
        "QQQ": _rows(100.0, 0.0010, 0.014),
        "AAA": _rows(70.0, 0.0018, 0.055),
        "BBB": _rows(60.0, 0.0016, 0.039),
        "CCC": _rows(55.0, 0.0015, 0.024),
    }


def _universe() -> dict:
    tickers = ["AAA", "BBB", "CCC"]
    return {
        "status": "test_broad_market_universe",
        "tickers": tickers,
        "records": {ticker: {"sector": "Technology", "industry": "Software"} for ticker in tickers},
    }


def test_shared_move_helper_daily_and_historical_semantics_match() -> None:
    ohlcv = _ohlcv()
    historical = build_move_rate_volatility_relief_historical_trades(
        ohlcv_by_ticker=ohlcv,
        dates=[EVENT_DATE],
        candidate_universe=_universe(),
    )
    daily = build_move_rate_volatility_relief_snapshot(
        as_of=EVENT_DATE,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=_universe(),
        state=empty_move_rate_volatility_relief_state(),
        persist=False,
    )

    assert historical["rule_version"] == daily["rule_version"] == RULE_VERSION
    assert historical["source_rule_version"] == daily["source_rule_version"] == SOURCE_RULE_VERSION
    assert [row["ticker"] for row in historical["trades"]] == ["AAA", "BBB"]
    assert [row["ticker"] for row in daily["candidates"]] == ["AAA", "BBB"]
    assert historical["trades"][0]["decision_id"] == daily["candidates"][0]["decision_id"]
    assert daily["move_rate_volatility_relief_context"]["passed"] is True
    assert daily["trade_enabled"] is False
    assert daily["production_impact"]["alters_orders"] is False


def test_daily_prep_requests_move_delivery_ticker_and_stays_default_off() -> None:
    ohlcv = _ohlcv()
    requested = []

    def cached(ticker: str):
        requested.append(ticker)
        return ohlcv["MOVE"] if ticker == MOVE_DELIVERY_TICKER else ohlcv.get(ticker)

    snapshot = prep_and_build_move_rate_volatility_relief_snapshot(
        as_of=EVENT_DATE,
        broad_market_ohlcv={key: value for key, value in ohlcv.items() if key != "MOVE"},
        broad_market_candidate_universe=_universe(),
        cached_ohlcv_fn=cached,
        persist=False,
    )

    assert MOVE_DELIVERY_TICKER in requested
    assert snapshot["sleeve"] == SLEEVE_NAME
    assert snapshot["candidate_count"] == 2
    assert snapshot["trade_enabled"] is False


def test_attribution_and_report_expose_move_default_off_surface() -> None:
    snapshot = build_move_rate_volatility_relief_snapshot(
        as_of=EVENT_DATE,
        ohlcv_by_ticker=_ohlcv(),
        candidate_universe=_universe(),
        state=empty_move_rate_volatility_relief_state(),
        persist=False,
    )
    attribution = build_default_off_alpha_attribution_report(
        as_of=EVENT_DATE,
        move_rate_volatility_relief_paper_sleeve=snapshot,
    )
    surfaces = {row["name"]: row for row in attribution["surfaces"]}
    surface = surfaces["move_rate_volatility_relief_stock_leadership"]

    assert surface["trade_enabled"] is False
    assert surface["extra_metrics"]["move_rate_volatility_relief_days"] == 1

    report = generate_daily_report(
        signals=[], move_rate_volatility_relief_paper_sleeve=snapshot
    )
    assert "MOVE RATE-VOLATILITY RELIEF PAPER SLEEVE" in report
    assert "AAA: score=" in report
