"""Ticker-level price as-of guards for paper sleeves."""

from __future__ import annotations

from typing import Any


def date10(value: Any) -> str:
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except Exception:
            pass
    return str(value or "")[:10]


def normalise_price_dates(price_dates: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for ticker, value in (price_dates or {}).items():
        parsed = date10(value)
        if parsed:
            out[str(ticker).upper()] = parsed
    return out


def filter_prices_for_asof(
    prices: dict[str, float],
    price_dates: dict[str, Any] | None,
    *,
    as_of: str,
) -> dict[str, float]:
    if price_dates is None:
        return dict(prices)
    target = date10(as_of)
    dates = normalise_price_dates(price_dates)
    return {
        str(ticker).upper(): price
        for ticker, price in (prices or {}).items()
        if dates.get(str(ticker).upper()) == target
    }


def latest_ohlcv_dates(ohlcv_by_ticker: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for ticker, rows in (ohlcv_by_ticker or {}).items():
        latest = _latest_ohlcv_date(rows)
        if latest:
            out[str(ticker).upper()] = latest
    return out


def _latest_ohlcv_date(rows: Any) -> str | None:
    if rows is None:
        return None
    if hasattr(rows, "empty"):
        try:
            if rows.empty:
                return None
            if "Date" in rows:
                return date10(rows["Date"].iloc[-1])
            return date10(rows.index[-1])
        except Exception:
            return None
    if isinstance(rows, list) and rows:
        last = rows[-1]
        if isinstance(last, dict):
            return date10(last.get("Date") or last.get("date"))
    return None
