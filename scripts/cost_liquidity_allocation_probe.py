#!/usr/bin/env python3
"""Read-only probe: does a PIT cost/liquidity state at the signal day separate
better vs worse CORE backtest trades? (allocation-field research)

Playbook lesson ("Transaction-Cost-Aware Allocation" + "Allocation Beats
Filtering"): a cheap, production-visible liquidity/range state may be a cleaner
allocation field than another alpha-shape threshold. VBB already accepted a
cost/liquidity support (dollar_volume>=$200m and signal-day range/close<=0.10
-> 1.05x). This probe asks the same question on the *core* trades: bucket
already-qualified trades by signal-day liquidity / intraday-range state and see
whether net return, win rate, and realized slippage differ -- i.e. whether an
allocation tilt is justified.

OBSERVE-ONLY. Touches no entries/exits/ranking/sizing/orders. PIT-safe: the
state is read from the trading day STRICTLY BEFORE entry_date (signal day);
the outcome (pnl_pct_net) is the trade's realized net return.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OHLCV = REPO / "data/ohlcv/ohlcv_snapshot_20251023_20260421.json"  # cumulative 2024-09..2026-04
# one file per non-overlapping standard window
WINDOW_FILES = [
    "data/backtests/backtest_results_20260520.json",  # 2024-10..2025-04
    "data/backtests/backtest_results_20260522.json",  # 2025-04..2025-10
    "data/backtests/backtest_results_20260510.json",  # 2025-10..2026-04
]


def first_obj(p):
    t = Path(p).read_text()
    i = 0
    while t[i] in " \t\r\n":
        i += 1
    return json.JSONDecoder().raw_decode(t, i)[0]


def load_trades():
    seen, trades = set(), []
    for f in WINDOW_FILES:
        for tr in first_obj(REPO / f).get("trades", []):
            k = tr.get("trade_key")
            if k and k not in seen and tr.get("entry_date"):
                seen.add(k)
                trades.append(tr)
    return trades


def load_panel():
    oh = json.loads(OHLCV.read_text())["ohlcv"]
    return {t.upper(): sorted(b, key=lambda x: x["Date"]) for t, b in oh.items()
            if isinstance(b, list)}


def signal_state(bars, entry_date):
    """Liquidity / range state from the last bar strictly before entry_date."""
    prior = [b for b in bars if b["Date"] < entry_date]
    if len(prior) < 21:
        return None
    sig = prior[-1]
    rng_over_close = (sig["High"] - sig["Low"]) / sig["Close"] if sig["Close"] else None
    adv20 = statistics.fmean(b["Close"] * b["Volume"] for b in prior[-20:])
    return {"dollar_vol_signal": sig["Close"] * sig["Volume"],
            "avg_dollar_vol_20d": adv20,
            "range_over_close": rng_over_close}


def summ(rows, key):
    rets = [r["ret"] for r in rows]
    if not rets:
        return None
    return {"n": len(rets),
            "mean_ret_pct": round(statistics.fmean(rets) * 100, 2),
            "median_ret_pct": round(statistics.median(rets) * 100, 2),
            "win_pct": round(sum(1 for x in rets if x > 0) / len(rets) * 100, 1),
            "mean_slip_bps": round(statistics.fmean(r["slip_frac"] for r in rows) * 1e4, 1)}


def tercile_bucket(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 3], s[2 * n // 3]


def main():
    trades = load_trades()
    panel = load_panel()
    rows, missing = [], 0
    for tr in trades:
        t = tr["ticker"].upper()
        if t not in panel:
            missing += 1
            continue
        st = signal_state(panel[t], tr["entry_date"])
        if not st or st["range_over_close"] is None:
            missing += 1
            continue
        notional = abs(tr.get("entry_price", 0) * tr.get("shares", 0)) or 1
        rows.append({
            "ticker": t, "ret": tr.get("pnl_pct_net", 0.0),
            "slip_frac": abs(tr.get("slippage_cost", 0.0)) / notional,
            "adv20": st["avg_dollar_vol_20d"],
            "roc": st["range_over_close"],
        })

    print(f"core trades: {len(trades)} | matched to OHLCV: {len(rows)} "
          f"| unmatched: {missing}")
    base = summ(rows, None)
    print(f"baseline (all matched): mean_ret={base['mean_ret_pct']}% "
          f"win={base['win_pct']}% mean_slip={base['mean_slip_bps']}bps n={base['n']}\n")

    # --- liquidity terciles (avg 20d dollar volume) ---
    lo, hi = tercile_bucket([r["adv20"] for r in rows])
    print("=== by 20d average dollar-volume (liquidity) ===")
    for name, pred in [("low_liquidity", lambda r: r["adv20"] <= lo),
                       ("mid_liquidity", lambda r: lo < r["adv20"] <= hi),
                       ("high_liquidity", lambda r: r["adv20"] > hi)]:
        s = summ([r for r in rows if pred(r)], None)
        if s:
            print(f"  {name:15} n={s['n']:>3} mean_ret={s['mean_ret_pct']:>6}% "
                  f"win={s['win_pct']:>5}% slip={s['mean_slip_bps']:>5}bps "
                  f"lift={s['mean_ret_pct']-base['mean_ret_pct']:>+6.2f}")

    # --- intraday range/close (tight vs wide execution state) ---
    rlo, rhi = tercile_bucket([r["roc"] for r in rows])
    print("\n=== by signal-day range/close (tight=cheap, wide=costly) ===")
    for name, pred in [("tight_range", lambda r: r["roc"] <= rlo),
                       ("mid_range", lambda r: rlo < r["roc"] <= rhi),
                       ("wide_range", lambda r: r["roc"] > rhi)]:
        s = summ([r for r in rows if pred(r)], None)
        if s:
            print(f"  {name:15} n={s['n']:>3} mean_ret={s['mean_ret_pct']:>6}% "
                  f"win={s['win_pct']:>5}% slip={s['mean_slip_bps']:>5}bps "
                  f"lift={s['mean_ret_pct']-base['mean_ret_pct']:>+6.2f}")

    # --- VBB-style combined cheap-execution flag ---
    print("\n=== VBB-style cheap-execution flag (high adv20 AND tight range) ===")
    cheap = [r for r in rows if r["adv20"] > lo and r["roc"] <= rhi]
    rest = [r for r in rows if not (r["adv20"] > lo and r["roc"] <= rhi)]
    for name, grp in [("cheap_exec", cheap), ("rest", rest)]:
        s = summ(grp, None)
        if s:
            print(f"  {name:12} n={s['n']:>3} mean_ret={s['mean_ret_pct']:>6}% "
                  f"win={s['win_pct']:>5}% slip={s['mean_slip_bps']:>5}bps "
                  f"lift={s['mean_ret_pct']-base['mean_ret_pct']:>+6.2f}")


if __name__ == "__main__":
    main()
