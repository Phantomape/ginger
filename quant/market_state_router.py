"""Shared prior-close market-state labels for default-off paper sleeves.

The router is deterministic and uses only SPY/QQQ OHLCV known at the prior
trading-day close before a next-open paper entry.
"""

from __future__ import annotations

import math
from typing import Any

try:
    from regime_engine import classify_market_regime
    from sentiment_surface import classify_sentiment_surface
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.regime_engine import classify_market_regime
    from quant.sentiment_surface import classify_sentiment_surface


STATE_ROUTER_SCHEMA_VERSION = 1
STATE_KNOWN_AT = "prior_trading_day_close_before_entry_open"
MIXED_BALANCED_NORMAL_CELL = "mixed|balanced|normal"


def state_for_entry_date(
    *,
    ohlcv_by_ticker: dict[str, Any],
    entry_date: str,
    trading_dates: list[str] | None = None,
) -> dict[str, Any] | None:
    """Return the market state known before ``entry_date`` opens."""

    entry = _date10(entry_date)
    dates = trading_dates or trading_dates_from_ohlcv(ohlcv_by_ticker)
    date_pos = {value: idx for idx, value in enumerate(dates)}
    entry_pos = date_pos.get(entry)
    if entry_pos is None or entry_pos < 1:
        return None
    return state_for_state_date(ohlcv_by_ticker=ohlcv_by_ticker, state_date=dates[entry_pos - 1])


def state_for_state_date(
    *,
    ohlcv_by_ticker: dict[str, Any],
    state_date: str,
) -> dict[str, Any] | None:
    """Return the market state at a close already known to production."""

    date_value = _date10(state_date)
    spy_rows = _series(ohlcv_by_ticker, "SPY")
    qqq_rows = _series(ohlcv_by_ticker, "QQQ")
    spy_idx = _row_index(spy_rows).get(date_value)
    qqq_idx = _row_index(qqq_rows).get(date_value)
    if spy_idx is None or qqq_idx is None:
        return None

    context = {
        "spy_pct_from_ma": _pct_from_sma(spy_rows, spy_idx, 200),
        "qqq_pct_from_ma": _pct_from_sma(qqq_rows, qqq_idx, 200),
        "spy_10d_return": _ret(spy_rows, spy_idx, 10),
        "qqq_10d_return": _ret(qqq_rows, qqq_idx, 10),
        "spy_20d_return": _ret(spy_rows, spy_idx, 20),
        "qqq_20d_return": _ret(qqq_rows, qqq_idx, 20),
        "theme_signal_count": 0,
        "breakout_signal_count": 0,
        "ai_signal_count": 0,
        "crypto_signal_count": 0,
        "space_signal_count": 0,
    }
    if context["qqq_20d_return"] is not None and context["spy_20d_return"] is not None:
        context["qqq_minus_spy_ret20"] = (
            float(context["qqq_20d_return"]) - float(context["spy_20d_return"])
        )
    else:
        context["qqq_minus_spy_ret20"] = None

    regime = classify_market_regime(context)
    sentiment = classify_sentiment_surface(context)
    buckets = bucket_market_context(context)
    return {
        "schema_version": STATE_ROUTER_SCHEMA_VERSION,
        "state_date": date_value,
        "state_known_at": STATE_KNOWN_AT,
        "regime": regime.get("regime"),
        "regime_confidence": regime.get("confidence"),
        "sentiment": sentiment.get("sentiment"),
        "sentiment_confidence": sentiment.get("confidence"),
        "sentiment_why": sentiment.get("why") or [],
        **buckets,
        "features": {
            key: _round(value)
            for key, value in context.items()
            if key
            in {
                "spy_pct_from_ma",
                "qqq_pct_from_ma",
                "spy_10d_return",
                "qqq_10d_return",
                "spy_20d_return",
                "qqq_20d_return",
                "qqq_minus_spy_ret20",
            }
        },
    }


def bucket_market_context(context: dict[str, Any]) -> dict[str, str]:
    spy20 = context.get("spy_20d_return")
    qqq20 = context.get("qqq_20d_return")
    spy10 = context.get("spy_10d_return")
    qqq10 = context.get("qqq_10d_return")
    spy_pct = context.get("spy_pct_from_ma")
    qqq_pct = context.get("qqq_pct_from_ma")
    qqq_rel = context.get("qqq_minus_spy_ret20")

    broad_up = (
        spy20 is not None
        and qqq20 is not None
        and spy20 > 0.03
        and qqq20 > 0.04
        and (spy_pct is None or spy_pct > 0.0)
        and (qqq_pct is None or qqq_pct > 0.0)
    )
    broad_down = (
        (spy20 is not None and spy20 < -0.03)
        or (qqq20 is not None and qqq20 < -0.04)
        or (spy_pct is not None and spy_pct < -0.02)
        or (qqq_pct is not None and qqq_pct < -0.02)
    )
    if broad_up:
        trend_pressure = "broad_up"
    elif broad_down:
        trend_pressure = "broad_down"
    else:
        trend_pressure = "mixed"

    if qqq_rel is None:
        growth_leadership = "unknown"
    elif qqq_rel >= 0.03:
        growth_leadership = "qqq_leads"
    elif qqq_rel <= -0.015:
        growth_leadership = "spy_defensive_leads"
    else:
        growth_leadership = "balanced"

    max_10 = max([value for value in [spy10, qqq10] if value is not None], default=None)
    max_20 = max([value for value in [spy20, qqq20] if value is not None], default=None)
    min_10 = min([value for value in [spy10, qqq10] if value is not None], default=None)
    if (max_10 is not None and max_10 >= 0.05) or (max_20 is not None and max_20 >= 0.08):
        extension = "extended"
    elif min_10 is not None and min_10 <= -0.03:
        extension = "pullback"
    else:
        extension = "normal"

    return {
        "trend_pressure": trend_pressure,
        "growth_leadership": growth_leadership,
        "extension": extension,
        "combined_state": f"{trend_pressure}|{growth_leadership}|{extension}",
    }


def trading_dates_from_ohlcv(ohlcv_by_ticker: dict[str, Any]) -> list[str]:
    spy_rows = _series(ohlcv_by_ticker, "SPY")
    if spy_rows:
        return [_date(row) for row in spy_rows if _date(row)]
    return sorted(
        {
            _date(row)
            for rows in (ohlcv_by_ticker or {}).values()
            for row in _rows(rows)
            if _date(row)
        }
    )


def _series(ohlcv_by_ticker: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    return sorted(_rows((ohlcv_by_ticker or {}).get(ticker)), key=_date)


def _rows(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            return value.reset_index().to_dict("records")
        except Exception:
            return []
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows) if _date(row)}


def _date(row: dict[str, Any]) -> str:
    return _date10(row.get("Date") or row.get("date") or row.get("datetime"))


def _date10(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _value(row: dict[str, Any], field: str) -> float | None:
    keys = {
        "close": ("Close", "close", "Adj Close", "adj_close"),
    }.get(field, (field,))
    for key in keys:
        try:
            value = row.get(key)
            if value is None:
                continue
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return None


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback or idx >= len(rows):
        return None
    start = _value(rows[idx - lookback], "close")
    end = _value(rows[idx], "close")
    if start is None or end is None or start <= 0:
        return None
    return (end / start) - 1.0


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1 or idx >= len(rows):
        return None
    values = [_value(row, "close") for row in rows[idx - lookback + 1 : idx + 1]]
    if any(value is None for value in values):
        return None
    clean = [float(value) for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def _pct_from_sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    close = _value(rows[idx], "close") if 0 <= idx < len(rows) else None
    avg = _sma(rows, idx, lookback)
    if close is None or avg is None or avg <= 0:
        return None
    return (close / avg) - 1.0


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)
