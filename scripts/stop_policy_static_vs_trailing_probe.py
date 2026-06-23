"""exp-20260623-020: static (frozen entry stop) vs ATR-trailing stop, 3 windows.

Confirmation on CURRENT code/windows that the static stop beats trailing (prior
exp-20260503-009 rejected trailing on the old 5.18 baseline). Runs the canonical
warehouse-backed backtest; 'static' must reproduce the documented baseline.
Observation-only. Out -> data/experiments/exp-20260623-020/static_vs_trailing.json
"""
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
BT = str(REPO / "quant" / "backtester.py")
WAREHOUSE = str(REPO / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite")
BT_DIR = REPO / "data" / "backtests"
OUT = REPO / "data" / "experiments" / "exp-20260623-020" / "static_vs_trailing.json"


def latest_result():
    cands = [p for p in BT_DIR.glob("backtest_results_*.json")
             if re.fullmatch(r"backtest_results_\d{8}\.json", p.name)]
    return max(cands, key=lambda p: p.stat().st_mtime)


WINDOWS = [
    ("late_strong", "2025-10-23", "2026-04-21", "data/ohlcv/ohlcv_snapshot_20251023_20260421.json"),
    ("mid_weak",    "2025-04-23", "2025-10-22", "data/ohlcv/ohlcv_snapshot_20250423_20251022.json"),
    ("old_thin",    "2024-10-02", "2025-04-22", "data/ohlcv/ohlcv_snapshot_20241002_20250422.json"),
]
VARIANTS = [
    ("static", []),  # regression: must reproduce the documented baseline
    ("trail_3_2", ["--set", "TRAIL_TRIGGER_ATR_MULT", "3", "--set", "TRAIL_OFFSET_ATR_MULT", "2"]),
    ("trail_4_2", ["--set", "TRAIL_TRIGGER_ATR_MULT", "4", "--set", "TRAIL_OFFSET_ATR_MULT", "2"]),
]
METRICS = ["expected_value_score", "sharpe_daily", "total_pnl",
           "max_drawdown_pct", "total_trades", "survival_rate"]

out = {"per_window": {}, "aggregate": {}}
for wlabel, start, end, snap in WINDOWS:
    for vlabel, flags in VARIANTS:
        cmd = [PY, BT, "--start", start, "--end", end,
               "--ohlcv-warehouse", WAREHOUSE,
               "--ohlcv-warehouse-snapshot-source", snap,
               "--no-secondary", "--no-oracle-diagnostics", *flags]
        print(f"RUN {wlabel}/{vlabel} ...", flush=True)
        r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"  FAILED rc={r.returncode}\n{r.stdout[-1200:]}\n{r.stderr[-600:]}", flush=True)
            out["per_window"][f"{wlabel}/{vlabel}"] = {"error": r.returncode}
            continue
        d = json.load(open(latest_result(), encoding="utf-8"))
        m = {k: d.get(k) for k in METRICS}
        m["return_pct"] = round(d.get("benchmarks", {}).get("strategy_total_return_pct", 0) * 100, 2)
        out["per_window"][f"{wlabel}/{vlabel}"] = m
        print(f"  EV={m['expected_value_score']} PnL={m['total_pnl']} "
              f"trades={m['total_trades']} DD={m['max_drawdown_pct']}", flush=True)

# Aggregate EV/PnL per variant (sum across windows).
for vlabel, _ in VARIANTS:
    ev = sum((out["per_window"].get(f"{w[0]}/{vlabel}", {}) or {}).get("expected_value_score", 0) or 0 for w in WINDOWS)
    pnl = sum((out["per_window"].get(f"{w[0]}/{vlabel}", {}) or {}).get("total_pnl", 0) or 0 for w in WINDOWS)
    out["aggregate"][vlabel] = {"ev_sum": round(ev, 4), "pnl_sum": round(pnl, 2)}

base_ev = out["aggregate"].get("static", {}).get("ev_sum", 0)
for vlabel, _ in VARIANTS:
    if vlabel == "static":
        continue
    out["aggregate"][vlabel]["ev_delta_vs_static"] = round(out["aggregate"][vlabel]["ev_sum"] - base_ev, 4)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("\nAGGREGATE:", json.dumps(out["aggregate"], indent=2), flush=True)
print(f"DONE -> {OUT}", flush=True)
