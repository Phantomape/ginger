"""EXPLORATORY SCOUT (not Gate-4): does the core stack's edge generalize to a
broader *liquid* universe? Runs late_strong window on warehouse broad OHLCV for
core-52 vs liquidity-ranked top-N tiers. Observation-only; touches no prod code.

Simplifications (uniform across all tiers, so comparison stays apples-to-apples):
  - earnings calendar disabled (no network); dte<=3 gate off for everyone
  - oracle diagnostics off (top-line metrics only)
  - data source = broad warehouse (NOT the canonical frozen snapshot), so the
    core-52 number here is a warehouse-control, not the canonical snapshot run.
"""
import sqlite3, sys, json
from pathlib import Path

REPO = Path(r"D:\Github\ginger")
sys.path.insert(0, str(REPO / "quant"))

WAREHOUSE = str(REPO / "data" / "warehouse" / "warehouse_main.sqlite")
WINDOWS = {
    "old_thin":    ("2024-10-02", "2025-04-22"),
    "mid_weak":    ("2025-04-23", "2025-10-22"),
}

import backtester as B
from filter import _BASE_WATCHLIST

# --- disable network earnings download uniformly ---
B.BacktestEngine._download_earnings_calendar = lambda self: {}

core52 = sorted(set(_BASE_WATCHLIST))
cfg = {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True}


def ranked_for_window(start, end):
    con = sqlite3.connect(WAREHOUSE)
    rows = con.execute(
        """SELECT ticker, AVG(close*volume) adv, AVG(close) px, COUNT(*) n
           FROM ohlcv WHERE date BETWEEN ? AND ? GROUP BY ticker""",
        (start, end)).fetchall()
    con.close()
    liquid = [r for r in rows if r[3] >= 110 and r[2] and r[2] >= 5 and r[1]]
    liquid.sort(key=lambda r: -r[1])
    return [r[0] for r in liquid]


def run(uni, start, end):
    eng = B.BacktestEngine(
        list(uni), start=start, end=end, config=cfg,
        ohlcv_warehouse_path=WAREHOUSE,
        ohlcv_warehouse_snapshot_source=None,   # broad path
        include_oracle_diagnostics=False,
    )
    return eng.run()


hdr = f"{'window':12} {'universe':9} {'N':>4} {'EV':>7} {'sharpe':>7} {'PnL$':>10} {'maxDD%':>7} {'win':>5} {'trades':>6} {'surv%':>6} {'sigGen':>7}"
out = {}
for win, (start, end) in WINDOWS.items():
    ranked = ranked_for_window(start, end)
    tiers = {"core": core52,
             "top300": sorted(set(core52) | set(ranked[:300])),
             "top500": sorted(set(core52) | set(ranked[:500]))}
    print("\n" + hdr); print("-" * len(hdr))
    out[win] = {}
    for name, uni in tiers.items():
        r = run(uni, start, end)
        if "error" in r:
            print(f"{win:12} {name:9} ERROR {r['error']}"); continue
        g = lambda k: r.get(k)
        print(f"{win:12} {name:9} {len(uni):4d} {g('expected_value_score') or 0:7.3f} "
              f"{g('sharpe_daily') or 0:7.2f} {g('total_pnl') or 0:10.0f} "
              f"{(g('max_drawdown_pct') or 0)*100:7.2f} {(g('win_rate') or 0):5.2f} "
              f"{g('total_trades') or 0:6d} {(g('survival_rate') or 0)*100:6.1f} "
              f"{g('signals_generated') or 0:7d}")
        out[win][name] = {k: g(k) for k in ('expected_value_score','sharpe_daily',
                          'total_pnl','max_drawdown_pct','win_rate','total_trades',
                          'survival_rate','signals_generated')}
        out[win][name]['universe_size'] = len(uni)

Path(r"C:\Users\ADMINI~1\AppData\Local\Temp\claude\D--Github-ginger\b77c7d01-9f8b-4aa2-b144-07d21af3d97c\scratchpad\universe_expansion_results.json").write_text(json.dumps(out, indent=2))
print("\nsaved results json")
