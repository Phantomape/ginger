"""Chop-regime mean-reversion paper sleeve (exp-20260708-023).

Default-off, read-only: nothing here alters live entries, ranking, sizing,
exits, or orders. The sleeve tests the structural mirror of the confirmed
chop loss axis (exp-20260615-019: momentum/breakout entries lose specifically
in ``choppy_range``): on days the shared ``regime_chop_state_v1`` module labels
``choppy_range``, buy short-horizon oversold pullbacks and exit on the snap
back to the short moving average or a fixed timeout.

Fixed policy bundle ``chop_mean_reversion_v1`` (predeclared in the ticket; no
parameter sweeps — conventional Connors-style constants):

- universe: production WATCHLIST equities (index/commodity ETFs excluded);
- condition: entry days must carry ``regime_label == "choppy_range"`` at the
  same fidelity the live snapshot uses (SPY bars + universe breadth);
- entry signal at close of day t: RSI(2) < 10 AND close > SMA200;
  fill next trading day's open through the shared fill model;
- ranking when over budget: lowest RSI(2) first; max 3 new lots/day, one open
  lot per ticker, max 6 concurrent lots;
- exit at close of the first day with close > SMA5, or after 10 trading days,
  whichever comes first (window end force-closes and flags the lot);
- $4,000 notional per lot; round-trip cost and slippage from the shared
  constants/fill model; SPY and QQQ same-window comparators per closed lot.
"""

from __future__ import annotations

from typing import Any

from constants import ROUND_TRIP_COST_PCT
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
from regime_chop_state import RULE_VERSION as REGIME_RULE_VERSION
from regime_chop_state import regime_chop_from_spy_universe

SLEEVE_RULE_VERSION = "chop_mean_reversion_v1"

ENTRY_RSI_PERIOD = 2
ENTRY_RSI_MAX = 10.0
ENTRY_SMA_LONG = 200
EXIT_SMA_SHORT = 5
MAX_HOLD_TRADING_DAYS = 10
MAX_NEW_LOTS_PER_DAY = 3
MAX_OPEN_LOTS = 6
NOTIONAL_USD = 4000.0
BREADTH_SMA_WINDOW = 50  # mirrors market_context._breadth_above_sma

# Index / commodity ETFs never take mean-reversion entries (single-stock
# premise); they still contribute to comparators (SPY/QQQ) and breadth is
# equity-only, mirroring market_context._INDEX_TICKERS conventions.
EXCLUDED_ENTRY_TICKERS = {"SPY", "QQQ", "IWM", "TQQQ", "GLD", "IAU", "SLV"}


# --------------------------------------------------------------------------- #
# Pure indicator helpers
# --------------------------------------------------------------------------- #
def wilder_rsi(closes: list[float], period: int = ENTRY_RSI_PERIOD) -> float | None:
    """Wilder-smoothed RSI of the last close; None with < period+1 closes."""
    if closes is None or len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for prev, cur in zip(closes[:-1], closes[1:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def sma(closes: list[float], window: int) -> float | None:
    if closes is None or len(closes) < window:
        return None
    return sum(closes[-window:]) / window


# --------------------------------------------------------------------------- #
# Bar plumbing: {ticker: [{"Date","Open","High","Low","Close"}, ...]} sorted
# --------------------------------------------------------------------------- #
def _dates_and_closes(bars: list[dict[str, Any]]) -> tuple[list[str], list[float], list[float]]:
    dates, closes, opens = [], [], []
    for bar in bars or []:
        date = str(bar.get("Date") or "")[:10]
        close = bar.get("Close")
        if not date or close is None:
            continue
        dates.append(date)
        closes.append(float(close))
        opens.append(float(bar.get("Open") or close))
    return dates, closes, opens


def breadth_by_date(
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    *,
    sma_window: int = BREADTH_SMA_WINDOW,
) -> dict[str, float | None]:
    """Equity-universe breadth (share of tickers above SMA50), per date."""
    series: dict[str, tuple[list[str], list[float]]] = {}
    for ticker, bars in bars_by_ticker.items():
        if str(ticker).upper() in EXCLUDED_ENTRY_TICKERS:
            continue
        tk_dates, tk_closes, _ = _dates_and_closes(bars)
        if tk_dates:
            series[ticker] = (tk_dates, tk_closes)

    out: dict[str, float | None] = {}
    cursor = {ticker: 0 for ticker in series}
    for date in dates:
        above = total = 0
        for ticker, (tk_dates, tk_closes) in series.items():
            i = cursor[ticker]
            while i < len(tk_dates) and tk_dates[i] <= date:
                i += 1
            cursor[ticker] = i
            if i < sma_window:
                continue
            window = tk_closes[i - sma_window : i]
            avg = sum(window) / sma_window
            if avg <= 0:
                continue
            total += 1
            if tk_closes[i - 1] > avg:
                above += 1
        out[date] = round(above / total, 4) if total else None
    return out


def regime_labels_by_date(
    spy_bars: list[dict[str, Any]],
    breadth: dict[str, float | None],
    dates: list[str],
) -> dict[str, dict[str, Any]]:
    """Full-fidelity regime_chop_state_v1 label per date (same module as live)."""
    return {
        date: regime_chop_from_spy_universe(spy_bars, date, breadth=breadth.get(date))
        for date in dates
    }


# --------------------------------------------------------------------------- #
# Replay
# --------------------------------------------------------------------------- #
def _comparator_pnl(
    bars: list[dict[str, Any]],
    entry_date: str,
    exit_date: str,
    notional: float,
) -> float | None:
    dates, closes, opens = _dates_and_closes(bars)
    by_date = dict(zip(dates, range(len(dates))))
    i, j = by_date.get(entry_date), by_date.get(exit_date)
    if i is None or j is None:
        return None
    entry_px = apply_entry_fill(opens[i])
    exit_px = apply_slippage(closes[j], SLIPPAGE_BPS_TARGET, "sell")
    if entry_px <= 0:
        return None
    return notional * (exit_px / entry_px - 1.0 - ROUND_TRIP_COST_PCT)


def replay_chop_mean_reversion(
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    spy_bars: list[dict[str, Any]],
    start: str,
    end: str,
    *,
    entry_regime_label: str = "choppy_range",
    regime_labels: dict[str, dict[str, Any]] | None = None,
    qqq_bars: list[dict[str, Any]] | None = None,
    notional_usd: float = NOTIONAL_USD,
) -> dict[str, Any]:
    """Replay the fixed bundle over [start, end] (signal dates in-window).

    ``entry_regime_label`` exists ONLY so the runner can produce the predeclared
    risk_on attribution control; it is not a tunable production knob.
    """
    spy_dates, _, _ = _dates_and_closes(spy_bars)
    days = [d for d in spy_dates if start <= d <= end]

    if regime_labels is None:
        breadth = breadth_by_date(bars_by_ticker, days)
        regime_labels = regime_labels_by_date(spy_bars, breadth, days)

    # Per-ticker aligned arrays.
    data: dict[str, dict[str, Any]] = {}
    for ticker, bars in bars_by_ticker.items():
        tk = str(ticker).upper()
        if tk in EXCLUDED_ENTRY_TICKERS:
            continue
        dates, closes, opens = _dates_and_closes(bars)
        if len(dates) >= ENTRY_SMA_LONG:
            data[tk] = {
                "dates": dates,
                "closes": closes,
                "opens": opens,
                "index": {d: i for i, d in enumerate(dates)},
            }

    open_lots: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []  # signaled at close, fill next open
    trades: list[dict[str, Any]] = []
    chop_days = 0
    signal_count = 0

    def _close_lot(ticker: str, lot: dict[str, Any], exit_date: str, exit_close: float, reason: str) -> None:
        exit_px = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell")
        pnl = notional_usd * (exit_px / lot["entry_px"] - 1.0 - ROUND_TRIP_COST_PCT)
        trades.append(
            {
                "rule_version": SLEEVE_RULE_VERSION,
                "regime_rule_version": REGIME_RULE_VERSION,
                "ticker": ticker,
                "signal_date": lot["signal_date"],
                "entry_date": lot["entry_date"],
                "entry_price": round(lot["entry_px"], 4),
                "exit_date": exit_date,
                "exit_price": round(exit_px, 4),
                "exit_reason": reason,
                "holding_days": lot["held"],
                "entry_rsi2": round(lot["rsi"], 2),
                "regime_label_at_signal": lot["regime_label"],
                "p_choppy_at_signal": lot["p_choppy"],
                "notional_usd": notional_usd,
                "pnl_usd": round(pnl, 2),
                "return_pct": round(pnl / notional_usd, 6),
                "spy_same_window_pnl_usd": _round_or_none(
                    _comparator_pnl(spy_bars, lot["entry_date"], exit_date, notional_usd)
                ),
                "qqq_same_window_pnl_usd": _round_or_none(
                    _comparator_pnl(qqq_bars or [], lot["entry_date"], exit_date, notional_usd)
                ),
            }
        )

    for day in days:
        # 1) fill pending entries at today's open
        still_pending: list[dict[str, Any]] = []
        for sig in pending:
            tk = sig["ticker"]
            info = data.get(tk)
            i = info["index"].get(day) if info else None
            if info is None or i is None:
                still_pending.append(sig)  # ticker had no bar today; wait one day
                continue
            if tk in open_lots or len(open_lots) >= MAX_OPEN_LOTS:
                continue
            open_lots[tk] = {
                **sig,
                "entry_date": day,
                "entry_px": apply_entry_fill(info["opens"][i]),
                "held": 0,
            }
        pending = still_pending

        # 2) exits at today's close
        for tk in list(open_lots):
            info = data[tk]
            i = info["index"].get(day)
            if i is None:
                continue
            lot = open_lots[tk]
            lot["held"] += 1
            close = info["closes"][i]
            sma5 = sma(info["closes"][: i + 1], EXIT_SMA_SHORT)
            if sma5 is not None and close > sma5:
                _close_lot(tk, lot, day, close, "close_above_sma5")
                del open_lots[tk]
            elif lot["held"] >= MAX_HOLD_TRADING_DAYS:
                _close_lot(tk, lot, day, close, "max_hold_timeout")
                del open_lots[tk]

        # 3) new signals at today's close (regime-conditioned)
        regime = regime_labels.get(day) or {}
        if regime.get("regime_label") != entry_regime_label:
            continue
        chop_days += 1
        candidates: list[tuple[float, str]] = []
        for tk, info in data.items():
            i = info["index"].get(day)
            if i is None or i + 1 < ENTRY_SMA_LONG:
                continue
            if tk in open_lots or any(p["ticker"] == tk for p in pending):
                continue
            closes_to_day = info["closes"][: i + 1]
            sma200 = sma(closes_to_day, ENTRY_SMA_LONG)
            rsi = wilder_rsi(closes_to_day[-(ENTRY_RSI_PERIOD + 40):])
            if sma200 is None or rsi is None:
                continue
            if closes_to_day[-1] > sma200 and rsi < ENTRY_RSI_MAX:
                candidates.append((rsi, tk))
        candidates.sort()
        for rsi, tk in candidates[:MAX_NEW_LOTS_PER_DAY]:
            signal_count += 1
            pending.append(
                {
                    "ticker": tk,
                    "signal_date": day,
                    "rsi": rsi,
                    "regime_label": regime.get("regime_label"),
                    "p_choppy": regime.get("p_choppy_range"),
                }
            )

    # window end: force-close remaining lots at their last in-window close
    for tk, lot in list(open_lots.items()):
        info = data[tk]
        last_i = None
        for day in reversed(days):
            last_i = info["index"].get(day)
            if last_i is not None:
                break
        if last_i is not None:
            _close_lot(tk, lot, info["dates"][last_i], info["closes"][last_i], "window_end_force_close")

    return {
        "rule_version": SLEEVE_RULE_VERSION,
        "regime_rule_version": REGIME_RULE_VERSION,
        "entry_regime_label": entry_regime_label,
        "start": start,
        "end": end,
        "trading_days": len(days),
        "entry_label_days": chop_days,
        "signals_generated": signal_count,
        "trades": trades,
        "summary": summarize_trades(trades),
    }


def _round_or_none(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [t["pnl_usd"] for t in trades]
    wins = [p for p in pnls if p > 0]
    vs_spy = [
        t["pnl_usd"] - t["spy_same_window_pnl_usd"]
        for t in trades
        if t.get("spy_same_window_pnl_usd") is not None
    ]
    vs_qqq = [
        t["pnl_usd"] - t["qqq_same_window_pnl_usd"]
        for t in trades
        if t.get("qqq_same_window_pnl_usd") is not None
    ]
    return {
        "trade_count": len(trades),
        "total_pnl_usd": round(sum(pnls), 2) if pnls else 0.0,
        "mean_pnl_usd": round(sum(pnls) / len(pnls), 2) if pnls else None,
        "win_rate": round(len(wins) / len(pnls), 4) if pnls else None,
        "worst_trade_usd": round(min(pnls), 2) if pnls else None,
        "best_trade_usd": round(max(pnls), 2) if pnls else None,
        "replacement_value_vs_spy_usd": round(sum(vs_spy), 2) if vs_spy else None,
        "replacement_value_vs_qqq_usd": round(sum(vs_qqq), 2) if vs_qqq else None,
        "mean_holding_days": (
            round(sum(t["holding_days"] for t in trades) / len(trades), 2) if trades else None
        ),
        "forced_window_end_exits": sum(
            1 for t in trades if t["exit_reason"] == "window_end_force_close"
        ),
    }
