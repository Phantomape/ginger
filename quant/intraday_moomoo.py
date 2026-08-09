"""moomoo OpenD market context for the advisory intraday review.

This module is intentionally read-only.  It fetches current snapshots plus
daily/5-minute bars and derives display/triage context.  Nothing here creates
orders or feeds the EOD/backtest strategy path.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import math
import os
from typing import Any, Iterable

import pandas as pd

try:
    from moomoo_open_positions import (
        _redirect_moomoo_sdk_appdata,
        _restore_moomoo_sdk_appdata,
    )
except ImportError:  # pragma: no cover - package-style imports
    from quant.moomoo_open_positions import (
        _redirect_moomoo_sdk_appdata,
        _restore_moomoo_sdk_appdata,
    )


LEVERAGED_PRODUCTS: dict[str, dict[str, Any]] = {
    "MUU": {"underlying": "MU", "leverage": 2.0},
    "SNXX": {"underlying": "SNDK", "leverage": 2.0},
    "TQQQ": {"underlying": "QQQ", "leverage": 3.0},
}

SECTOR_PROXIES: dict[str, str] = {
    "APP": "IGV",
    "CRDO": "SMH",
    "DDOG": "IGV",
    "GEV": "XLI",
    "HOOD": "XLF",
    "MCD": "XLY",
    "MU": "SMH",
    "MUU": "SMH",
    "NVDA": "SMH",
    "SNDK": "SMH",
    "SNXX": "SMH",
    "TQQQ": "QQQ",
    "UNH": "XLV",
}

TECH_TICKERS = frozenset({"APP", "CRDO", "DDOG", "MU", "MUU", "NVDA", "SNDK", "SNXX", "TQQQ"})


def market_phase(now_et: datetime | pd.Timestamp) -> str:
    """Classify the US session from an America/New_York timestamp."""
    ts = pd.Timestamp(now_et)
    if ts.weekday() >= 5:
        return "CLOSED"
    current = ts.time()
    if time(9, 30) <= current < time(16, 0):
        return "RTH"
    if time(4, 0) <= current < time(9, 30):
        return "PREMARKET"
    if time(16, 0) <= current < time(20, 0):
        return "AFTER_HOURS"
    return "OVERNIGHT"


def underlying_for(ticker: str) -> str | None:
    row = LEVERAGED_PRODUCTS.get(str(ticker).upper())
    return str(row["underlying"]) if row else None


def sector_proxy_for(ticker: str) -> str:
    return SECTOR_PROXIES.get(str(ticker).upper(), "SPY")


def market_proxy_for(ticker: str) -> str:
    return "QQQ" if str(ticker).upper() in TECH_TICKERS else "SPY"


def build_analysis_universe(position_tickers: Iterable[str]) -> list[str]:
    tickers = {str(t).upper().strip() for t in position_tickers if t}
    result = set(tickers) | {"SPY", "QQQ"}
    for ticker in tickers:
        underlying = underlying_for(ticker)
        if underlying:
            result.add(underlying)
        result.add(sector_proxy_for(ticker))
        result.add(market_proxy_for(ticker))
    return sorted(result)


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value.item() if hasattr(value, "item") else value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _round(value: Any, digits: int = 6) -> float | None:
    number = _safe_float(value)
    return round(number, digits) if number is not None else None


def _records(frame: pd.DataFrame | None, columns: list[str]) -> list[dict]:
    if frame is None or frame.empty:
        return []
    rows: list[dict] = []
    for _, raw in frame.iterrows():
        row: dict[str, Any] = {}
        for column in columns:
            if column not in raw:
                continue
            value = raw[column]
            if column == "time_key":
                row[column] = str(value)
            else:
                row[column] = _safe_float(value)
        rows.append(row)
    return rows


def _history_pages(context, *, code: str, start: str, end: str, ktype, autype,
                   extended_time: bool, session) -> tuple[pd.DataFrame, str | None]:
    from moomoo import RET_OK

    pages: list[pd.DataFrame] = []
    page_key = None
    while True:
        ret, data, next_key = context.request_history_kline(
            code,
            start=start,
            end=end,
            ktype=ktype,
            autype=autype,
            max_count=1000,
            page_req_key=page_key,
            extended_time=extended_time,
            session=session,
        )
        if ret != RET_OK:
            return pd.concat(pages, ignore_index=True) if pages else pd.DataFrame(), str(data)
        if isinstance(data, pd.DataFrame) and not data.empty:
            pages.append(data)
        if next_key is None:
            break
        page_key = next_key
    return pd.concat(pages, ignore_index=True) if pages else pd.DataFrame(), None


def _reference_price(snapshot: dict, phase: str) -> tuple[float | None, str]:
    candidates = {
        "PREMARKET": ("pre_price", "moomoo_opend_premarket"),
        "RTH": ("last_price", "moomoo_opend_rth"),
        "AFTER_HOURS": ("after_price", "moomoo_opend_after_hours"),
        "OVERNIGHT": ("overnight_price", "moomoo_opend_overnight"),
    }
    field, source = candidates.get(phase, ("last_price", "moomoo_opend_last"))
    price = _safe_float(snapshot.get(field))
    if price is not None and price > 0:
        return price, source
    fallback = _safe_float(snapshot.get("last_price"))
    return fallback, "moomoo_opend_last_fallback"


def _wilder_atr(frame: pd.DataFrame, period: int = 14) -> float | None:
    if len(frame) < period + 1:
        return None
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")
    close = pd.to_numeric(frame["close"], errors="coerce")
    tr = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return _safe_float(tr.ewm(alpha=1.0 / period, adjust=False).mean().iloc[-1])


def _rsi(frame: pd.DataFrame, period: int = 14) -> float | None:
    if len(frame) < period + 1:
        return None
    close = pd.to_numeric(frame["close"], errors="coerce")
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1.0 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = _safe_float(loss.iloc[-1])
    avg_gain = _safe_float(gain.iloc[-1])
    if avg_loss is None or avg_gain is None:
        return None
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def _vwap(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    volume = pd.to_numeric(frame["volume"], errors="coerce").fillna(0)
    turnover = pd.to_numeric(frame["turnover"], errors="coerce").fillna(0)
    total_volume = float(volume.sum())
    if total_volume <= 0:
        return None
    return float(turnover.sum()) / total_volume


def derive_metrics(
    snapshot: dict,
    daily_rows: list[dict],
    intraday_rows: list[dict],
    *,
    asof_date: date,
    phase: str,
) -> dict:
    """Derive stable daily and session context from OpenD rows."""
    reference_price, reference_source = _reference_price(snapshot, phase)

    daily = pd.DataFrame(daily_rows)
    if not daily.empty:
        daily["time_key"] = pd.to_datetime(daily["time_key"], errors="coerce")
        daily = daily[daily["time_key"].dt.date < asof_date].sort_values("time_key")

    metrics: dict[str, Any] = {
        "reference_price": _round(reference_price),
        "reference_price_source": reference_source,
        "prev_close": _round(snapshot.get("prev_close_price")),
        "open_price": _round(snapshot.get("open_price")),
        "day_high": _round(snapshot.get("high_price")),
        "day_low": _round(snapshot.get("low_price")),
        "relative_volume": _round(snapshot.get("volume_ratio")),
        "bid": _round(snapshot.get("bid_price")),
        "ask": _round(snapshot.get("ask_price")),
        "update_time": snapshot.get("update_time"),
    }
    prev_close = metrics["prev_close"]
    if reference_price and prev_close:
        metrics["session_return_pct"] = round(reference_price / prev_close - 1.0, 6)
    else:
        metrics["session_return_pct"] = None

    if not daily.empty and reference_price:
        closes = pd.to_numeric(daily["close"], errors="coerce").dropna()
        atr = _wilder_atr(daily)
        metrics.update({
            "atr14": _round(atr),
            "atr_pct": round(atr / reference_price, 6) if atr else None,
            "rsi14": _round(_rsi(daily), 2),
            "sma5": _round(closes.tail(5).mean()) if len(closes) >= 5 else None,
            "sma10": _round(closes.tail(10).mean()) if len(closes) >= 10 else None,
            "sma20": _round(closes.tail(20).mean()) if len(closes) >= 20 else None,
            "sma50": _round(closes.tail(50).mean()) if len(closes) >= 50 else None,
            "ema8": _round(closes.ewm(span=8, adjust=False).mean().iloc[-1]),
            "ema21": _round(closes.ewm(span=21, adjust=False).mean().iloc[-1]),
            "return_5d_pct": round(reference_price / closes.iloc[-5] - 1.0, 6)
            if len(closes) >= 5 else None,
            "return_20d_pct": round(reference_price / closes.iloc[-20] - 1.0, 6)
            if len(closes) >= 20 else None,
        })
    else:
        metrics.update({key: None for key in (
            "atr14", "atr_pct", "rsi14", "sma5", "sma10", "sma20",
            "sma50", "ema8", "ema21", "return_5d_pct", "return_20d_pct",
        )})

    bars = pd.DataFrame(intraday_rows)
    if not bars.empty:
        bars["time_key"] = pd.to_datetime(bars["time_key"], errors="coerce")
        bars = bars[bars["time_key"].dt.date == asof_date].sort_values("time_key")
    rth = bars[
        (bars["time_key"].dt.time >= time(9, 30))
        & (bars["time_key"].dt.time < time(16, 0))
    ] if not bars.empty else pd.DataFrame()

    rth_vwap = _vwap(rth) if not rth.empty else _safe_float(snapshot.get("avg_price"))
    all_vwap = _vwap(bars) if not bars.empty else None
    rth_high = _safe_float(pd.to_numeric(rth["high"], errors="coerce").max()) if not rth.empty else metrics["day_high"]
    rth_low = _safe_float(pd.to_numeric(rth["low"], errors="coerce").min()) if not rth.empty else metrics["day_low"]
    range_location = None
    if reference_price and rth_high is not None and rth_low is not None and rth_high > rth_low:
        range_location = (reference_price - rth_low) / (rth_high - rth_low)
    tail_return = None
    if len(bars) >= 4:
        closes = pd.to_numeric(bars["close"], errors="coerce").dropna()
        if len(closes) >= 4 and closes.iloc[-4] > 0:
            tail_return = closes.iloc[-1] / closes.iloc[-4] - 1.0

    metrics.update({
        "rth_vwap": _round(rth_vwap),
        "all_session_vwap": _round(all_vwap),
        "rth_high": _round(rth_high),
        "rth_low": _round(rth_low),
        "rth_range_location": _round(range_location),
        "tail_15m_return_pct": _round(tail_return),
        "rth_bar_count": int(len(rth)),
        "all_session_bar_count": int(len(bars)),
    })
    required = ("reference_price", "atr_pct", "sma20", "ema8", "rth_vwap")
    metrics["technical_context_complete"] = all(metrics.get(key) is not None for key in required)
    return metrics


def quote_from_ticker_payload(payload: dict, capture_time_et: str) -> dict | None:
    metrics = payload.get("metrics") or {}
    price = metrics.get("reference_price")
    if price is None:
        return None
    quote_time = metrics.get("update_time")
    is_stale = False
    try:
        quote_date = pd.Timestamp(quote_time).date()
        capture_date = pd.Timestamp(capture_time_et.replace(" ET", "")).date()
        is_stale = quote_date != capture_date
    except Exception:
        is_stale = True
    return {
        "ticker": payload.get("ticker"),
        "price": price,
        "day_high": metrics.get("day_high"),
        "day_low": metrics.get("day_low"),
        "source": metrics.get("reference_price_source", "moomoo_opend"),
        "quote_time_et": quote_time,
        "capture_time_et": capture_time_et,
        "decision_time_et": capture_time_et,
        "quote_time_basis": "moomoo_opend_snapshot_update_time",
        "is_stale": is_stale,
    }


def _import_moomoo_quote_sdk() -> tuple[Any, Any, Any, Any, Any]:
    """Import the SDK while its import-time logger points at writable storage."""
    redirected = not os.environ.get("GINGER_MOOMOO_USE_SYSTEM_APPDATA")
    previous_appdata = _redirect_moomoo_sdk_appdata() if redirected else None
    try:
        from moomoo import AuType, KLType, OpenQuoteContext, RET_OK, Session
    finally:
        if redirected:
            _restore_moomoo_sdk_appdata(previous_appdata)
    return AuType, KLType, OpenQuoteContext, RET_OK, Session


def fetch_intraday_context(
    tickers: Iterable[str],
    *,
    now_et: datetime | pd.Timestamp,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> dict:
    """Fetch OpenD snapshots and bars for a small analysis universe."""
    requested = sorted({str(t).upper().strip() for t in tickers if t})
    ts = pd.Timestamp(now_et)
    phase = market_phase(ts)
    capture_time_et = ts.strftime("%Y-%m-%d %H:%M ET")
    result: dict[str, Any] = {
        "source": "moomoo_opend",
        "status": "unavailable",
        "capture_time_et": capture_time_et,
        "market_phase": phase,
        "host": host,
        "port": port,
        "requested_tickers": requested,
        "tickers": {},
        "errors": {},
        "trade_enabled": False,
        "strategy_behavior_changed": False,
    }
    if not requested:
        result["status"] = "empty"
        return result

    try:
        AuType, KLType, OpenQuoteContext, RET_OK, Session = _import_moomoo_quote_sdk()
    except Exception as exc:  # pragma: no cover - depends on local SDK
        result["errors"]["sdk"] = str(exc)
        return result

    context = None
    try:
        context = OpenQuoteContext(host=host, port=port)
        ret, snapshots = context.get_market_snapshot([f"US.{t}" for t in requested])
        if ret != RET_OK:
            result["errors"]["snapshots"] = str(snapshots)
            return result
        snapshot_map = {
            str(row["code"]).split(".", 1)[-1].upper(): row.to_dict()
            for _, row in snapshots.iterrows()
        }
        start_daily = (ts.date() - timedelta(days=430)).isoformat()
        end_date = ts.date().isoformat()
        for ticker in requested:
            code = f"US.{ticker}"
            snapshot = snapshot_map.get(ticker, {})
            daily, daily_error = _history_pages(
                context,
                code=code,
                start=start_daily,
                end=end_date,
                ktype=KLType.K_DAY,
                autype=AuType.QFQ,
                extended_time=False,
                session=Session.RTH,
            )
            intraday, intraday_error = _history_pages(
                context,
                code=code,
                start=end_date,
                end=end_date,
                ktype=KLType.K_5M,
                autype=AuType.QFQ,
                extended_time=True,
                session=Session.ALL,
            )
            if daily_error:
                result["errors"][f"{ticker}:daily"] = daily_error
            if intraday_error:
                result["errors"][f"{ticker}:5m"] = intraday_error
            snapshot_clean = {
                key: (str(value) if key == "update_time" else _safe_float(value))
                for key, value in snapshot.items()
                if key in {
                    "update_time", "last_price", "open_price", "high_price",
                    "low_price", "prev_close_price", "volume", "turnover",
                    "avg_price", "volume_ratio", "bid_price", "ask_price",
                    "pre_price", "pre_high_price", "pre_low_price", "pre_volume",
                    "after_price", "after_high_price", "after_low_price", "after_volume",
                    "overnight_price", "overnight_high_price", "overnight_low_price",
                    "overnight_volume",
                }
            }
            daily_rows = _records(daily, ["time_key", "open", "close", "high", "low", "volume", "turnover"])
            intraday_rows = _records(intraday, ["time_key", "open", "close", "high", "low", "volume", "turnover"])
            result["tickers"][ticker] = {
                "ticker": ticker,
                "snapshot": snapshot_clean,
                "daily_rows": daily_rows,
                "intraday_rows": intraday_rows,
                "metrics": derive_metrics(
                    snapshot_clean,
                    daily_rows,
                    intraday_rows,
                    asof_date=ts.date(),
                    phase=phase,
                ),
            }
    except Exception as exc:  # pragma: no cover - live OpenD failure path
        result["errors"]["connection"] = str(exc)
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass

    available = sum(
        1 for row in result["tickers"].values()
        if (row.get("metrics") or {}).get("reference_price") is not None
    )
    if available == len(requested):
        result["status"] = "ok" if not result["errors"] else "partial"
    elif available:
        result["status"] = "partial"
    result["available_tickers"] = available
    return result
