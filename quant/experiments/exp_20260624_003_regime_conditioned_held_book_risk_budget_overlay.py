"""exp-20260624-003: regime-conditioned held-book risk-budget overlay.

Follow-up to the rejected always-on overlay exp-20260623-026. Same overlay
(15% single-name risk cap + 30% vol target, excess to cash, monthly, trailing-90d
PIT covariance), but GATED on the production PIT market regime: apply the overlay
only when compute_market_regime() (SPY+QQQ vs 200d MA) is NOT BULL, and hold
static (full weights) when BULL. The regime classifier is unchanged production
code; the gate is the single new variable. North star: total_return_pct * sharpe_daily.

Compares three policies on the same held universe / windows:
  STATIC  -> buy-and-hold initial weights
  ALWAYS  -> overlay every rebalance (== exp-026)
  REGIME  -> overlay only when PIT regime != BULL, else static

Honest caveats (also in artifact): survivorship (universe = held winners),
per-window eligibility varies, 200d MA regime is slow. Observed-only.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT = REPO_ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))
from regime import compute_market_regime  # noqa: E402

WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
POSITIONS = REPO_ROOT / "operator_inputs" / "open_positions.json"
EXPERIMENT_ID = "exp-20260624-003"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260624_003_regime_conditioned_held_book_risk_budget_overlay.json"

WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
]
RISK_CAP = 0.15
VOL_TARGET_ANN = 0.30
LOOKBACK = 90
MIN_LOOKBACK = 60
TRADING_DAYS = 252


def load_weights():
    d = json.loads(POSITIONS.read_text(encoding="utf-8"))
    w = {}
    for key in ("core_positions", "positions", "sleeve_positions", "legacy_positions"):
        for p in d.get(key) or []:
            if p.get("market_val"):
                w[p["ticker"]] = w.get(p["ticker"], 0.0) + float(p["market_val"])
    return w


def load_panel(tickers):
    con = sqlite3.connect(WAREHOUSE)
    px, alldates = {}, set()
    for t in tickers:
        rows = con.execute(
            "SELECT date, close FROM ohlcv WHERE ticker=? AND close IS NOT NULL ORDER BY date", (t,)
        ).fetchall()
        if rows:
            px[t] = {d: float(c) for d, c in rows}
            alldates.update(px[t])
    con.close()
    return sorted(alldates), px


def apply_risk_cap(w0, cov, cap):
    w = w0.copy()
    for _ in range(100):
        pv = float(w @ cov @ w)
        if pv <= 0:
            break
        crc = w * (cov @ w) / pv
        over = crc > cap
        if not over.any():
            break
        w[over] = w[over] * np.sqrt(cap / crc[over])
    return w


def vol_target(w, cov, target_ann):
    v = float(w @ cov @ w) ** 0.5
    return w if (v <= target_ann or v == 0) else w * (target_ann / v)


def pit_regime(px, t):
    """PIT BULL/NEUTRAL/BEAR from SPY+QQQ vs 200d MA, trailing data only."""
    override = {}
    for idx in ("SPY", "QQQ"):
        if idx not in px:
            continue
        ser = {d: c for d, c in px[idx].items() if d <= t}
        if len(ser) < 200:
            continue
        df = pd.DataFrame({"Close": list(ser.values())},
                          index=pd.to_datetime(list(ser.keys()))).sort_index()
        override[idx] = df
    if len(override) < 2:
        return "UNKNOWN"
    return compute_market_regime(ohlcv_override=override).get("regime", "UNKNOWN")


def metrics(equity):
    eq = np.array(equity, dtype=float)
    rets = np.diff(eq) / eq[:-1]
    total_ret = float(eq[-1] / eq[0] - 1.0)
    sd = float(rets.std(ddof=1)) if len(rets) > 1 else 0.0
    # annualized to match repo convention (backtester.py: sharpe_daily = mean/std * sqrt(252))
    sharpe = float(rets.mean() / sd) * (TRADING_DAYS ** 0.5) if sd > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    max_dd = float(((eq - peak) / peak).min()) if len(eq) else 0.0
    return {"total_return_pct": round(100 * total_ret, 3), "sharpe_daily": round(sharpe, 4),
            "max_drawdown_pct": round(100 * max_dd, 3), "ev": round(100 * total_ret * sharpe, 4)}


def run_overlay(win_dates, full_dates, eligible, px, w0, regime_gate, regime_by_month):
    di = {d: i for i, d in enumerate(full_dates)}
    months, eq, cur_w, cur_cash = set(), [1.0], None, 0.0

    def price_row(d):
        return np.array([px[t][d] for t in eligible], dtype=float)

    prev_p = None
    for k, d in enumerate(win_dates):
        ym = d[:7]
        if cur_w is None or ym not in months:
            months.add(ym)
            j = di[d]
            lb = full_dates[max(0, j - LOOKBACK):j]
            if len(lb) >= MIN_LOOKBACK:
                M = np.column_stack([[px[t][x] for x in lb] for t in eligible])
                cov = np.cov(np.diff(np.log(M), axis=0), rowvar=False) * TRADING_DAYS
                reg = regime_by_month.get(ym, "UNKNOWN")
                if regime_gate and reg == "BULL":
                    w = w0.copy()                       # stay static in confirmed uptrend
                else:
                    w = vol_target(apply_risk_cap(w0, cov, RISK_CAP), cov, VOL_TARGET_ANN)
                cur_w, cur_cash = w, 1.0 - float(w.sum())
        if k == 0:
            prev_p = price_row(d); continue
        p = price_row(d)
        port_ret = float(cur_w @ (p / prev_p) + cur_cash) - 1.0
        eq.append(eq[-1] * (1.0 + port_ret)); prev_p = p
    return eq


def simulate_window(name, start, end, mv, dates, px):
    win_dates = [d for d in dates if start <= d <= end]
    if len(win_dates) < 40:
        return None
    eligible = sorted(t for t, m in mv.items() if t in px
                      and len([d for d in px[t] if d < start]) >= MIN_LOOKBACK
                      and all(d in px[t] for d in win_dates))
    if len(eligible) < 3:
        return {"window": name, "skipped": "fewer than 3 eligible names", "eligible": eligible}
    w0 = np.array([mv[t] for t in eligible], dtype=float); w0 /= w0.sum()
    full_dates = [d for d in dates if d <= end]

    # precompute PIT regime per month-start in the window
    months = sorted({d[:7] for d in win_dates})
    regime_by_month = {}
    for ym in months:
        first = next(d for d in win_dates if d[:7] == ym)
        regime_by_month[ym] = pit_regime(px, first)

    p0 = np.array([px[t][win_dates[0]] for t in eligible]); shares = w0 / p0
    static_eq = [float(shares @ np.array([px[t][d] for t in eligible])) for d in win_dates]
    always_eq = run_overlay(win_dates, full_dates, eligible, px, w0, False, regime_by_month)
    regime_eq = run_overlay(win_dates, full_dates, eligible, px, w0, True, regime_by_month)

    return {"window": name, "n_names": len(eligible), "eligible": eligible,
            "regime_by_month": regime_by_month,
            "static": metrics(static_eq), "always": metrics(always_eq), "regime": metrics(regime_eq)}


def main():
    mv = load_weights()
    dates, px = load_panel(sorted(mv) + ["SPY", "QQQ"])
    results = [r for r in (simulate_window(n, s, e, mv, dates, px) for n, s, e in WINDOWS) if r]
    full = [r for r in results if "static" in r]

    agg = {}
    for side in ("static", "always", "regime"):
        if full:
            agg[side] = {"ev_sum": round(sum(r[side]["ev"] for r in full), 4),
                         "mean_return_pct": round(float(np.mean([r[side]["total_return_pct"] for r in full])), 3),
                         "worst_dd_pct": round(min(r[side]["max_drawdown_pct"] for r in full), 3)}
    accept = bool(agg and agg["regime"]["ev_sum"] > agg["static"]["ev_sum"]
                  and agg["regime"]["ev_sum"] > agg["always"]["ev_sum"])
    payload = {"experiment_id": EXPERIMENT_ID,
               "policy": {"overlay": "exp-026 frozen (cap 0.15, vol_target 0.30)",
                          "gate": "compute_market_regime SPY+QQQ 200d MA; overlay only when != BULL", "pit": True},
               "windows": results, "aggregate": agg, "accepted": accept,
               "decision": ("accepted_regime_conditioned_overlay" if accept
                            else "rejected_regime_conditioned_overlay"),
               "caveats": ["Survivorship: universe = currently-held names.",
                           "200d MA regime is slow; per-window regime labels reported.",
                           "Observed-only; no core-strategy change."],
               "generated_at": date.today().isoformat()}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("=" * 80)
    for r in results:
        if "static" not in r:
            print(f"{r['window']:12s} SKIP {r.get('skipped')}"); continue
        regs = "/".join(sorted(set(r["regime_by_month"].values())))
        print(f"{r['window']:12s} n={r['n_names']:2d} regimes={regs}")
        for side in ("static", "always", "regime"):
            m = r[side]
            print(f"   {side:7s} ret={m['total_return_pct']:8.1f}% sharpe={m['sharpe_daily']:.3f} "
                  f"maxDD={m['max_drawdown_pct']:7.1f}% EV={m['ev']:.2f}")
    print("-" * 80)
    if agg:
        for side in ("static", "always", "regime"):
            a = agg[side]
            print(f"AGG {side:7s} EV_sum={a['ev_sum']:7.2f}  mean_ret={a['mean_return_pct']:7.1f}%  worst_DD={a['worst_dd_pct']:6.1f}%")
    print(f"DECISION: {payload['decision']}  (accepted={accept})")
    print(f"artifact: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
