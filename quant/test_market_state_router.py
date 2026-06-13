from __future__ import annotations

from datetime import date, timedelta

from quant import market_state_router


def _business_dates(days: int) -> list[str]:
    current = date(2026, 1, 1)
    out: list[str] = []
    while len(out) < days:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _rows(step: float, days: int = 45) -> list[dict]:
    close = 100.0
    rows = []
    for day in _business_dates(days):
        close *= 1.0 + step
        rows.append(
            {
                "date": day,
                "open": round(close, 4),
                "high": round(close * 1.002, 4),
                "low": round(close * 0.998, 4),
                "close": round(close, 4),
                "volume": 1_000_000,
            }
        )
    return rows


def test_state_for_entry_date_uses_prior_close_mixed_balanced_normal() -> None:
    ohlcv = {"SPY": _rows(0.0010), "QQQ": _rows(0.0012)}
    entry_date = ohlcv["SPY"][31]["date"]

    state = market_state_router.state_for_entry_date(
        ohlcv_by_ticker=ohlcv,
        entry_date=entry_date,
    )

    assert state is not None
    assert state["state_date"] == ohlcv["SPY"][30]["date"]
    assert state["state_known_at"] == market_state_router.STATE_KNOWN_AT
    assert state["combined_state"] == market_state_router.MIXED_BALANCED_NORMAL_CELL
    assert state["features"]["spy_20d_return"] is not None
    assert state["features"]["qqq_minus_spy_ret20"] is not None


def test_state_for_entry_date_requires_spy_and_qqq() -> None:
    ohlcv = {"SPY": _rows(0.0010)}

    assert (
        market_state_router.state_for_entry_date(
            ohlcv_by_ticker=ohlcv,
            entry_date=ohlcv["SPY"][31]["date"],
        )
        is None
    )
