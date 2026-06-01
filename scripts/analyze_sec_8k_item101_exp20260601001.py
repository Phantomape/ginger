#!/usr/bin/env python3
"""
SEC 8-K Item 1.01 candidate pool analysis for exp-20260601-001.
Analyzes 10-day forward returns across three backtest windows.
"""

import json
import statistics
import math
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

BASE = Path("/home/user/ginger")
DATA = BASE / "data"

CRYPTO_EXCLUDE = {'APLD','WULF','CRWV','CIFR','MARA','CORZ','RIOT','IREN','COIN'}
ROUND_TRIP_COST = 0.002
NOTIONAL = 10_000.0
TRADING_DAYS_HOLD = 10

WINDOWS = {
    "late_strong":  ("2025-10-23", "2026-04-21", "ohlcv_snapshot_20251023_20260421.json"),
    "mid_weak":     ("2025-04-23", "2025-10-22", "ohlcv_snapshot_20250423_20251022.json"),
    "old_thin":     ("2024-10-02", "2025-04-22", "ohlcv_snapshot_20241002_20250422.json"),
}

# ── helpers ──────────────────────────────────────────────────────────────────

def load_ohlcv_snapshot(snap_name: str) -> dict:
    """Returns {ticker: {date_str: {Open, High, Low, Close, Volume}}}"""
    path = DATA / "ohlcv" / snap_name
    with open(path) as f:
        raw = json.load(f)
    result = {}
    for ticker, records in raw["ohlcv"].items():
        result[ticker] = {}
        for r in records:
            result[ticker][r["Date"]] = r
    return result

def sorted_dates(ohlcv_ticker: dict) -> list:
    return sorted(ohlcv_ticker.keys())

def next_trading_day(ohlcv_ticker: dict, after_date: str) -> str | None:
    """Return the first trading date strictly after after_date that exists in ohlcv."""
    dates = sorted_dates(ohlcv_ticker)
    for d in dates:
        if d > after_date:
            return d
    return None

def nth_trading_day_after(ohlcv_ticker: dict, entry_date: str, n: int) -> str | None:
    """Return the nth trading day at or after entry_date (0-indexed: entry_date itself is day 0)."""
    dates = sorted_dates(ohlcv_ticker)
    try:
        idx = dates.index(entry_date)
    except ValueError:
        # Find first date >= entry_date
        for i, d in enumerate(dates):
            if d >= entry_date:
                idx = i
                break
        else:
            return None
    target_idx = idx + n
    if target_idx < len(dates):
        return dates[target_idx]
    return None

def compute_sharpe(returns: list[float]) -> float:
    """Simple daily Sharpe approximation (no risk-free)."""
    if len(returns) < 2:
        return 0.0
    mu = statistics.mean(returns)
    sd = statistics.stdev(returns)
    if sd == 0:
        return 0.0
    return mu / sd * math.sqrt(252)

# ── load SEC events ───────────────────────────────────────────────────────────

print("=" * 70)
print("SEC 8-K Item 1.01 Candidate Pool Analysis — exp-20260601-001")
print("=" * 70)

events_path = DATA / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
with open(events_path) as f:
    all_events = [json.loads(l) for l in f]

# Filter: Item 1.01, not crypto, pit_safe_flag=True
filtered_events = [
    e for e in all_events
    if "1.01" in e.get("eight_k_item_codes", [])
    and e.get("ticker") not in CRYPTO_EXCLUDE
    and e.get("pit_safe_flag") is True
]

print(f"\nTotal SEC filing events: {len(all_events)}")
print(f"After filter (Item 1.01, non-crypto, pit_safe=True): {len(filtered_events)}")

# Show unique tickers
unique_tickers = sorted(set(e["ticker"] for e in filtered_events))
print(f"Unique tickers: {len(unique_tickers)} — {unique_tickers}")

# ── load backtest trades for slot-conflict check ──────────────────────────────

bt_path = DATA / "backtests" / "backtest_results_20260529.json"
with open(bt_path) as f:
    bt_data = json.load(f)

# Build set of (ticker, entry_date) for core trades
core_trades = set()
core_trade_windows = []  # list of (ticker, entry_date, exit_date)
for t in bt_data.get("trades", []):
    ticker = t["ticker"]
    entry = t["entry_date"]
    exit_d = t["exit_date"]
    core_trades.add((ticker, entry))
    core_trade_windows.append((ticker, entry, exit_d))

print(f"\nCore backtest trades loaded: {len(bt_data.get('trades', []))}")

# ── per-window analysis ───────────────────────────────────────────────────────

window_results = {}

for win_name, (win_start, win_end, snap_file) in WINDOWS.items():
    print(f"\n{'─'*70}")
    print(f"WINDOW: {win_name}  ({win_start} → {win_end})")
    print(f"{'─'*70}")

    ohlcv = load_ohlcv_snapshot(snap_file)

    # Filter events to this window by usable_trade_date
    win_events = [
        e for e in filtered_events
        if win_start <= e.get("usable_trade_date", "") <= win_end
    ]
    print(f"  Qualifying events in window: {len(win_events)}")

    trades = []
    skipped = []

    for ev in win_events:
        ticker = ev["ticker"]
        usable_date = ev["usable_trade_date"]
        filing_date = ev["filing_date"]

        # Need OHLCV data for this ticker
        if ticker not in ohlcv:
            skipped.append((ticker, usable_date, "ticker_not_in_ohlcv"))
            continue

        tk_ohlcv = ohlcv[ticker]

        # Entry: open on the day AFTER usable_trade_date
        entry_date = next_trading_day(tk_ohlcv, usable_date)
        if entry_date is None:
            skipped.append((ticker, usable_date, "no_entry_date"))
            continue

        entry_price = tk_ohlcv[entry_date].get("Open")
        if entry_price is None or entry_price == 0:
            skipped.append((ticker, usable_date, "no_entry_price"))
            continue

        # Exit: close 10 trading days after entry
        exit_date = nth_trading_day_after(tk_ohlcv, entry_date, TRADING_DAYS_HOLD)
        if exit_date is None:
            skipped.append((ticker, usable_date, "no_exit_date"))
            continue

        exit_price = tk_ohlcv[exit_date].get("Close")
        if exit_price is None or exit_price == 0:
            skipped.append((ticker, usable_date, "no_exit_price"))
            continue

        # Gross return
        gross_return = (exit_price - entry_price) / entry_price
        net_return = gross_return - ROUND_TRIP_COST
        pnl = net_return * NOTIONAL

        # SPY return for same period
        spy_return = None
        if "SPY" in ohlcv:
            spy_ohlcv = ohlcv["SPY"]
            spy_entry_date = next_trading_day(spy_ohlcv, usable_date)
            if spy_entry_date:
                spy_exit_date = nth_trading_day_after(spy_ohlcv, spy_entry_date, TRADING_DAYS_HOLD)
                if spy_exit_date:
                    spy_entry_px = spy_ohlcv[spy_entry_date].get("Open")
                    spy_exit_px = spy_ohlcv[spy_exit_date].get("Close")
                    if spy_entry_px and spy_exit_px:
                        spy_return = (spy_exit_px - spy_entry_px) / spy_entry_px

        # Slot conflict check
        has_conflict = False
        conflict_detail = None
        for (ct_ticker, ct_entry, ct_exit) in core_trade_windows:
            if ct_ticker == ticker:
                # Check if the 10-day windows overlap
                if ct_entry <= exit_date and ct_exit >= entry_date:
                    has_conflict = True
                    conflict_detail = f"core_trade_{ct_entry}_to_{ct_exit}"
                    break

        trades.append({
            "ticker": ticker,
            "filing_date": filing_date,
            "usable_trade_date": usable_date,
            "entry_date": entry_date,
            "entry_price": entry_price,
            "exit_date": exit_date,
            "exit_price": exit_price,
            "gross_return": gross_return,
            "net_return": net_return,
            "pnl": pnl,
            "spy_return": spy_return,
            "alpha_vs_spy": (net_return - spy_return) if spy_return is not None else None,
            "win": net_return > 0,
            "slot_conflict": has_conflict,
            "conflict_detail": conflict_detail,
            "items": ev.get("eight_k_item_codes", []),
        })

    print(f"  Tradeable (OHLCV match): {len(trades)}")
    print(f"  Skipped: {len(skipped)}")
    if skipped:
        for s in skipped[:5]:
            print(f"    skip: {s}")

    if not trades:
        print("  No trades to analyze.")
        window_results[win_name] = None
        continue

    # ── metrics ──────────────────────────────────────────────────────────────
    net_returns = [t["net_return"] for t in trades]
    pnls = [t["pnl"] for t in trades]
    wins = [t for t in trades if t["win"]]
    spy_alphas = [t["alpha_vs_spy"] for t in trades if t["alpha_vs_spy"] is not None]

    trade_count = len(trades)
    win_rate = len(wins) / trade_count
    avg_net_return = statistics.mean(net_returns)
    avg_pnl = statistics.mean(pnls)
    total_return_pct = sum(net_returns) / trade_count * 100  # avg return as pct
    sharpe = compute_sharpe(net_returns)
    ev_score = total_return_pct * sharpe
    avg_spy_alpha = statistics.mean(spy_alphas) if spy_alphas else None

    conflicts = [t for t in trades if t["slot_conflict"]]

    print(f"\n  ── Metrics ──")
    print(f"  Trade count:        {trade_count}")
    print(f"  Win rate:           {win_rate:.1%}")
    print(f"  Avg net return:     {avg_net_return:.4f}  ({avg_net_return*100:.2f}%)")
    print(f"  Avg PnL ($10k):     ${avg_pnl:+.2f}")
    print(f"  Total PnL:          ${sum(pnls):+.2f}")
    print(f"  Avg return vs SPY:  {avg_spy_alpha*100:.2f}%" if avg_spy_alpha is not None else "  Avg return vs SPY:  N/A")
    print(f"  Sharpe (approx):    {sharpe:.3f}")
    print(f"  EV score:           {ev_score:.4f}")
    print(f"  Slot conflicts:     {len(conflicts)}")

    # Per-trade detail
    print(f"\n  ── Trade Detail ──")
    print(f"  {'Ticker':<8} {'Filing':<12} {'Entry':<12} {'Exit':<12} {'Net%':>8} {'PnL':>10} {'vs SPY%':>9} {'Conflict'}")
    for t in sorted(trades, key=lambda x: x["entry_date"]):
        alpha_str = f"{t['alpha_vs_spy']*100:+.2f}%" if t["alpha_vs_spy"] is not None else "   N/A"
        conflict_str = "YES" if t["slot_conflict"] else "-"
        print(f"  {t['ticker']:<8} {t['filing_date']:<12} {t['entry_date']:<12} {t['exit_date']:<12} "
              f"{t['net_return']*100:>+7.2f}% ${t['pnl']:>+8.2f} {alpha_str:>9} {conflict_str}")

    # Conflict detail
    if conflicts:
        print(f"\n  ── Slot Conflicts ──")
        for t in conflicts:
            print(f"  {t['ticker']} event={t['filing_date']} entry={t['entry_date']}→{t['exit_date']}: {t['conflict_detail']}")

    window_results[win_name] = {
        "trade_count": trade_count,
        "win_rate": win_rate,
        "avg_net_return": avg_net_return,
        "avg_pnl": avg_pnl,
        "total_pnl": sum(pnls),
        "ev_score": ev_score,
        "sharpe": sharpe,
        "avg_spy_alpha": avg_spy_alpha,
        "slot_conflicts": len(conflicts),
        "trades": trades,
    }

# ── aggregate summary ─────────────────────────────────────────────────────────

print(f"\n{'='*70}")
print("AGGREGATE SUMMARY — 3-WINDOW")
print(f"{'='*70}")

valid_windows = {k: v for k, v in window_results.items() if v is not None}

if valid_windows:
    all_trades_flat = []
    for wn, wr in valid_windows.items():
        all_trades_flat.extend(wr["trades"])

    total_trades = len(all_trades_flat)
    all_net_returns = [t["net_return"] for t in all_trades_flat]
    all_pnls = [t["pnl"] for t in all_trades_flat]
    all_spy_alphas = [t["alpha_vs_spy"] for t in all_trades_flat if t["alpha_vs_spy"] is not None]
    wins_all = [t for t in all_trades_flat if t["win"]]

    agg_win_rate = len(wins_all) / total_trades if total_trades else 0
    agg_avg_return = statistics.mean(all_net_returns) if all_net_returns else 0
    agg_avg_pnl = statistics.mean(all_pnls) if all_pnls else 0
    agg_total_pnl = sum(all_pnls)
    agg_sharpe = compute_sharpe(all_net_returns)
    agg_ev_score = (agg_avg_return * 100) * agg_sharpe
    agg_spy_alpha = statistics.mean(all_spy_alphas) if all_spy_alphas else None
    all_conflicts = [t for t in all_trades_flat if t["slot_conflict"]]

    print(f"\n  {'Window':<14} {'Trades':>7} {'WinRate':>9} {'AvgNet%':>9} {'AvgPnL':>10} {'vsSPY%':>9} {'Sharpe':>8} {'EVscore':>9}")
    for wn, wr in valid_windows.items():
        alpha_s = f"{wr['avg_spy_alpha']*100:+.2f}%" if wr['avg_spy_alpha'] is not None else "  N/A"
        print(f"  {wn:<14} {wr['trade_count']:>7} {wr['win_rate']:>8.1%} {wr['avg_net_return']*100:>+8.2f}% "
              f"${wr['avg_pnl']:>+8.2f} {alpha_s:>9} {wr['sharpe']:>8.3f} {wr['ev_score']:>9.4f}")

    print(f"  {'AGGREGATE':<14} {total_trades:>7} {agg_win_rate:>8.1%} {agg_avg_return*100:>+8.2f}% "
          f"${agg_avg_pnl:>+8.2f} "
          + (f"{agg_spy_alpha*100:>+8.2f}%" if agg_spy_alpha else "     N/A")
          + f" {agg_sharpe:>8.3f} {agg_ev_score:>9.4f}")

    print(f"\n  Total PnL across all windows: ${agg_total_pnl:+.2f}")
    print(f"  Slot conflicts (total):       {len(all_conflicts)}")

    # Per-item-code breakdown (co-occurring items with 1.01)
    item_co_counts = defaultdict(int)
    for t in all_trades_flat:
        for item in t["items"]:
            if item != "1.01":
                item_co_counts[item] += 1
    print(f"\n  ── Co-occurring 8-K items with 1.01 ──")
    for item, cnt in sorted(item_co_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    Item {item}: {cnt} events")

    # Per-ticker breakdown
    print(f"\n  ── Per-ticker aggregate ──")
    ticker_returns = defaultdict(list)
    ticker_pnls = defaultdict(list)
    for t in all_trades_flat:
        ticker_returns[t["ticker"]].append(t["net_return"])
        ticker_pnls[t["ticker"]].append(t["pnl"])
    print(f"  {'Ticker':<8} {'Count':>6} {'AvgNet%':>9} {'TotalPnL':>12}")
    for tk in sorted(ticker_pnls.keys(), key=lambda x: -sum(ticker_pnls[x])):
        avg_r = statistics.mean(ticker_returns[tk])
        total_pnl_tk = sum(ticker_pnls[tk])
        print(f"  {tk:<8} {len(ticker_pnls[tk]):>6} {avg_r*100:>+8.2f}% ${total_pnl_tk:>+10.2f}")

else:
    print("No valid windows to aggregate.")

print(f"\n{'='*70}")
print("PRELIMINARY ASSESSMENT (exp-20260601-001)")
print(f"{'='*70}")
if valid_windows:
    print(f"\n  Total events filtered to Item 1.01 (non-crypto, pit_safe): {len(filtered_events)}")
    print(f"  Tradeable across all windows: {total_trades}")
    print(f"  Sample is {'thin' if total_trades < 30 else 'moderate' if total_trades < 80 else 'healthy'} ({total_trades} trades).")
    if agg_avg_return * 100 >= 5 and agg_avg_pnl >= 500:
        print("  SIGNAL: Meets scout materiality threshold (>5pp avg return, >$500 avg PnL).")
    else:
        print(f"  SIGNAL: Does NOT meet scout materiality threshold.")
        print(f"    Avg return {agg_avg_return*100:.2f}% (need >=5pp), Avg PnL ${agg_avg_pnl:.2f} (need >=$500).")
    if total_trades < 30:
        print("  WARNING: Fewer than 30 total trades — results not statistically reliable.")
print()
