"""Chop-regime long-short pairs spread paper sleeve (exp-20260708-025).

Default-off, read-only: nothing here alters live entries, ranking, sizing,
exits, or orders. First market-neutral construct in this repo: on days the
shared ``regime_chop_state_v1`` module labels ``choppy_range``, trade the
convergence of stretched spreads between highly-correlated core-universe
equity pairs — the trade that needs no market direction, matching what a
directionless regime actually offers (exp-20260708-023 showed single-name
long-only reversion does NOT clear the bar in chop).

Fixed policy bundle ``chop_pairs_spread_v1`` (predeclared; no sweeps —
conventional stat-arb constants):

- universe: production WATCHLIST equities (index/commodity ETFs excluded);
- pair eligibility at signal time (PIT): trailing 120-day daily-return
  correlation >= 0.6 on >= 100 overlapping observations;
- spread: s = ln(P_A / P_B); z = (s - mean_60d) / std_60d;
- entry signal at close of a chop-labeled day: |z| >= 2.0 -> short the rich
  leg, long the cheap leg, equal $4,000 notional per leg, filled next
  trading day's open through the shared fill model (both legs);
- exit at close when |z| <= 0.5 or after 10 trading days; window end
  force-closes and flags the pair;
- caps: max 2 new pairs/day, max 3 concurrent pairs, one open lot per ticker;
- costs: ROUND_TRIP_COST_PCT per leg plus entry/exit slippage per leg
  (megacap borrow cost for a <=10-day short is ignored; recorded as a caveat).
"""

from __future__ import annotations

import math
from typing import Any

from constants import ROUND_TRIP_COST_PCT
from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
from regime_chop_state import RULE_VERSION as REGIME_RULE_VERSION

# Reuse the sibling sleeve's bar plumbing and regime helpers so both chop
# sleeves label days identically.
from chop_mean_reversion_sleeve import (  # noqa: F401 (re-exported for runner)
    EXCLUDED_ENTRY_TICKERS,
    _dates_and_closes,
    breadth_by_date,
    regime_labels_by_date,
)

SLEEVE_RULE_VERSION = "chop_pairs_spread_v1"

CORR_LOOKBACK = 120
CORR_MIN_OBS = 100
CORR_MIN = 0.6
Z_LOOKBACK = 60
Z_ENTRY = 2.0
Z_EXIT = 0.5
MAX_HOLD_TRADING_DAYS = 10
MAX_NEW_PAIRS_PER_DAY = 2
MAX_OPEN_PAIRS = 3
LEG_NOTIONAL_USD = 4000.0


# --------------------------------------------------------------------------- #
# Pure math helpers
# --------------------------------------------------------------------------- #
def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return cov / math.sqrt(vx * vy)


def spread_zscore(closes_a: list[float], closes_b: list[float]) -> float | None:
    """z of ln(A/B) vs its trailing Z_LOOKBACK distribution (inclusive of today)."""
    n = min(len(closes_a), len(closes_b))
    if n < Z_LOOKBACK:
        return None
    spreads = [
        math.log(a / b)
        for a, b in zip(closes_a[n - Z_LOOKBACK:], closes_b[n - Z_LOOKBACK:])
        if a > 0 and b > 0
    ]
    if len(spreads) < Z_LOOKBACK:
        return None
    mean = sum(spreads) / len(spreads)
    var = sum((s - mean) ** 2 for s in spreads) / len(spreads)
    std = math.sqrt(var)
    # 1e-9 floor: a truly-constant spread yields std ~1e-16 from float error,
    # which would turn numerical noise into a huge fake z.
    if std < 1e-9:
        return None
    return (spreads[-1] - mean) / std


def _aligned_returns(
    dates_a: list[str], closes_a: list[float],
    dates_b: list[str], closes_b: list[float],
    upto_index_a: int, lookback: int = CORR_LOOKBACK,
) -> tuple[list[float], list[float]]:
    """Daily returns on the date intersection of the trailing window."""
    close_by_date_b = dict(zip(dates_b, closes_b))
    xs: list[float] = []
    ys: list[float] = []
    prev_a = prev_b = None
    start = max(1, upto_index_a - lookback)
    for i in range(start, upto_index_a + 1):
        date = dates_a[i]
        b = close_by_date_b.get(date)
        a = closes_a[i]
        if b is None or a is None or a <= 0 or b <= 0:
            prev_a = prev_b = None
            continue
        if prev_a and prev_b:
            xs.append(a / prev_a - 1.0)
            ys.append(b / prev_b - 1.0)
        prev_a, prev_b = a, b
    return xs, ys


# --------------------------------------------------------------------------- #
# Replay
# --------------------------------------------------------------------------- #
def _leg_pnl(direction: str, entry_px: float, exit_px: float, notional: float) -> float:
    if entry_px <= 0 or exit_px <= 0:
        return 0.0
    if direction == "long":
        gross = exit_px / entry_px - 1.0
    else:  # short: profit when price falls
        gross = entry_px / exit_px - 1.0
    return notional * (gross - ROUND_TRIP_COST_PCT)


def replay_chop_pairs_spread(
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    spy_bars: list[dict[str, Any]],
    start: str,
    end: str,
    *,
    entry_regime_label: str = "choppy_range",
    regime_labels: dict[str, dict[str, Any]] | None = None,
    leg_notional_usd: float = LEG_NOTIONAL_USD,
) -> dict[str, Any]:
    """Replay the fixed bundle over [start, end] (signal dates in-window).

    ``entry_regime_label`` exists ONLY for the predeclared risk_on attribution
    control; it is not a tunable production knob.
    """
    spy_dates, _, _ = _dates_and_closes(spy_bars)
    days = [d for d in spy_dates if start <= d <= end]

    if regime_labels is None:
        breadth = breadth_by_date(bars_by_ticker, days)
        regime_labels = regime_labels_by_date(spy_bars, breadth, days)

    data: dict[str, dict[str, Any]] = {}
    for ticker, bars in bars_by_ticker.items():
        tk = str(ticker).upper()
        if tk in EXCLUDED_ENTRY_TICKERS:
            continue
        dates, closes, opens = _dates_and_closes(bars)
        if len(dates) >= CORR_LOOKBACK + Z_LOOKBACK:
            data[tk] = {
                "dates": dates,
                "closes": closes,
                "opens": opens,
                "index": {d: i for i, d in enumerate(dates)},
            }
    tickers = sorted(data)

    open_pairs: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    chop_days = 0
    signal_count = 0

    def _busy_tickers() -> set[str]:
        busy: set[str] = set()
        for p in open_pairs + pending:
            busy.add(p["long_ticker"])
            busy.add(p["short_ticker"])
        return busy

    def _close_pair(pair: dict[str, Any], day: str, reason: str) -> None:
        info_l, info_s = data[pair["long_ticker"]], data[pair["short_ticker"]]
        i_l, i_s = info_l["index"].get(day), info_s["index"].get(day)
        if i_l is None or i_s is None:
            return
        exit_long = apply_slippage(info_l["closes"][i_l], SLIPPAGE_BPS_TARGET, "sell")
        exit_short = apply_slippage(info_s["closes"][i_s], SLIPPAGE_BPS_ENTRY, "buy")
        pnl_long = _leg_pnl("long", pair["entry_long_px"], exit_long, leg_notional_usd)
        pnl_short = _leg_pnl("short", pair["entry_short_px"], exit_short, leg_notional_usd)
        pnl = pnl_long + pnl_short
        trades.append(
            {
                "rule_version": SLEEVE_RULE_VERSION,
                "regime_rule_version": REGIME_RULE_VERSION,
                "pair": f"{pair['long_ticker']}/{pair['short_ticker']}",
                "long_ticker": pair["long_ticker"],
                "short_ticker": pair["short_ticker"],
                "signal_date": pair["signal_date"],
                "entry_date": pair["entry_date"],
                "exit_date": day,
                "exit_reason": reason,
                "holding_days": pair["held"],
                "entry_zscore": round(pair["entry_z"], 3),
                "exit_zscore": pair.get("last_z"),
                "pair_correlation": round(pair["corr"], 3),
                "regime_label_at_signal": pair["regime_label"],
                "p_choppy_at_signal": pair["p_choppy"],
                "leg_notional_usd": leg_notional_usd,
                "pnl_long_usd": round(pnl_long, 2),
                "pnl_short_usd": round(pnl_short, 2),
                "pnl_usd": round(pnl, 2),
                "return_pct_on_one_leg_notional": round(pnl / leg_notional_usd, 6),
            }
        )

    for day in days:
        # 1) fill pending pairs at today's open (both legs or wait)
        still_pending: list[dict[str, Any]] = []
        for sig in pending:
            info_l, info_s = data[sig["long_ticker"]], data[sig["short_ticker"]]
            i_l, i_s = info_l["index"].get(day), info_s["index"].get(day)
            if i_l is None or i_s is None:
                still_pending.append(sig)
                continue
            if len(open_pairs) >= MAX_OPEN_PAIRS:
                continue
            open_pairs.append(
                {
                    **sig,
                    "entry_date": day,
                    "entry_long_px": apply_slippage(info_l["opens"][i_l], SLIPPAGE_BPS_ENTRY, "buy"),
                    "entry_short_px": apply_slippage(info_s["opens"][i_s], SLIPPAGE_BPS_ENTRY, "sell"),
                    "held": 0,
                }
            )
        pending = still_pending

        # 2) exits at today's close: convergence or timeout
        for pair in list(open_pairs):
            info_l, info_s = data[pair["long_ticker"]], data[pair["short_ticker"]]
            i_l, i_s = info_l["index"].get(day), info_s["index"].get(day)
            if i_l is None or i_s is None:
                continue
            pair["held"] += 1
            # z is defined on the ORIGINAL orientation (rich/short leg = A)
            z = spread_zscore(
                info_s["closes"][: i_s + 1], info_l["closes"][: i_l + 1]
            )
            pair["last_z"] = round(z, 3) if z is not None else None
            if z is not None and abs(z) <= Z_EXIT:
                _close_pair(pair, day, "spread_converged")
                open_pairs.remove(pair)
            elif pair["held"] >= MAX_HOLD_TRADING_DAYS:
                _close_pair(pair, day, "max_hold_timeout")
                open_pairs.remove(pair)

        # 3) new signals at today's close (regime-conditioned)
        regime = regime_labels.get(day) or {}
        if regime.get("regime_label") != entry_regime_label:
            continue
        chop_days += 1
        busy = _busy_tickers()
        candidates: list[tuple[float, str, str, float]] = []  # (|z|, rich, cheap, corr)
        for a_i in range(len(tickers)):
            tk_a = tickers[a_i]
            info_a = data[tk_a]
            i_a = info_a["index"].get(day)
            if i_a is None or tk_a in busy:
                continue
            for b_i in range(a_i + 1, len(tickers)):
                tk_b = tickers[b_i]
                if tk_b in busy:
                    continue
                info_b = data[tk_b]
                i_b = info_b["index"].get(day)
                if i_b is None:
                    continue
                xs, ys = _aligned_returns(
                    info_a["dates"], info_a["closes"],
                    info_b["dates"], info_b["closes"], i_a,
                )
                if len(xs) < CORR_MIN_OBS:
                    continue
                corr = pearson(xs, ys)
                if corr is None or corr < CORR_MIN:
                    continue
                z = spread_zscore(info_a["closes"][: i_a + 1], info_b["closes"][: i_b + 1])
                if z is None or abs(z) < Z_ENTRY:
                    continue
                rich, cheap = (tk_a, tk_b) if z > 0 else (tk_b, tk_a)
                candidates.append((abs(z), rich, cheap, corr))
        candidates.sort(reverse=True)
        taken: set[str] = set()
        added = 0
        for abs_z, rich, cheap, corr in candidates:
            if added >= MAX_NEW_PAIRS_PER_DAY:
                break
            if rich in taken or cheap in taken:
                continue
            taken.update((rich, cheap))
            signal_count += 1
            added += 1
            pending.append(
                {
                    "long_ticker": cheap,
                    "short_ticker": rich,
                    "signal_date": day,
                    "entry_z": abs_z,
                    "corr": corr,
                    "regime_label": regime.get("regime_label"),
                    "p_choppy": regime.get("p_choppy_range"),
                }
            )

    for pair in list(open_pairs):
        info_l = data[pair["long_ticker"]]
        last_day = None
        for day in reversed(days):
            if info_l["index"].get(day) is not None and data[pair["short_ticker"]]["index"].get(day) is not None:
                last_day = day
                break
        if last_day is not None:
            _close_pair(pair, last_day, "window_end_force_close")

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
        "summary": summarize_pair_trades(trades),
    }


def summarize_pair_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [t["pnl_usd"] for t in trades]
    wins = [p for p in pnls if p > 0]
    converged = [t for t in trades if t["exit_reason"] == "spread_converged"]
    return {
        "trade_count": len(trades),
        "total_pnl_usd": round(sum(pnls), 2) if pnls else 0.0,
        "mean_pnl_usd": round(sum(pnls) / len(pnls), 2) if pnls else None,
        "win_rate": round(len(wins) / len(pnls), 4) if pnls else None,
        "worst_trade_usd": round(min(pnls), 2) if pnls else None,
        "best_trade_usd": round(max(pnls), 2) if pnls else None,
        "converged_exit_count": len(converged),
        "converged_share": round(len(converged) / len(trades), 4) if trades else None,
        "mean_holding_days": (
            round(sum(t["holding_days"] for t in trades) / len(trades), 2) if trades else None
        ),
        "forced_window_end_exits": sum(
            1 for t in trades if t["exit_reason"] == "window_end_force_close"
        ),
    }
