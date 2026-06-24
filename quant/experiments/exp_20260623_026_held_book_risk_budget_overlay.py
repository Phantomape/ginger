"""exp-20260623-026: held-book PIT risk-budget overlay vs static hold.

Observed-only policy simulation. Compares static buy-and-hold of the held names
against a risk-budget overlay (cap any single name at 15% of ex-ante portfolio
RISK, target 30% annualized vol, redeploy excess to cash), rebalanced monthly
using ONLY trailing-90d covariance (PIT, no lookahead), over the three standard
windows. North-star metric: expected_value_score = total_return_pct * sharpe_daily.

Honest caveats (also recorded in the artifact):
- Survivorship: the universe is the names you currently hold; static-hold of past
  winners is a hard baseline. Reported, not corrected.
- Per-window eligibility varies: names only enter once they have >=130d history
  (MUU, COHR, MRVL, etc. only exist in later windows). Per-window names reported.
- No core-strategy / order / ranking / sizing change; production path if it wins
  is a discretionary risk policy.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
POSITIONS = REPO_ROOT / "operator_inputs" / "open_positions.json"
EXPERIMENT_ID = "exp-20260623-026"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260623_026_held_book_risk_budget_overlay.json"

WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
]
RISK_CAP = 0.15          # max single-name share of ex-ante portfolio variance
VOL_TARGET_ANN = 0.30    # annualized vol target; excess -> cash
LOOKBACK = 90            # trailing days for PIT covariance
MIN_LOOKBACK = 60
TRADING_DAYS = 252


def load_weights() -> dict[str, float]:
    d = json.loads(POSITIONS.read_text(encoding="utf-8"))
    w: dict[str, float] = {}
    for key in ("core_positions", "positions", "sleeve_positions", "legacy_positions"):
        for p in d.get(key) or []:
            if p.get("market_val"):
                w[p["ticker"]] = w.get(p["ticker"], 0.0) + float(p["market_val"])
    return w


def load_panel(tickers: list[str]) -> tuple[list[str], dict[str, dict[str, float]]]:
    con = sqlite3.connect(WAREHOUSE)
    px: dict[str, dict[str, float]] = {}
    alldates: set[str] = set()
    for t in tickers:
        rows = con.execute(
            "SELECT date, close FROM ohlcv WHERE ticker=? AND close IS NOT NULL ORDER BY date", (t,)
        ).fetchall()
        if rows:
            px[t] = {d: float(c) for d, c in rows}
            alldates.update(px[t])
    con.close()
    return sorted(alldates), px


def apply_risk_cap(w0: np.ndarray, cov: np.ndarray, cap: float) -> np.ndarray:
    """Iteratively trim names whose risk contribution exceeds cap; excess -> cash."""
    w = w0.copy()
    for _ in range(100):
        pv = float(w @ cov @ w)
        if pv <= 0:
            break
        crc = w * (cov @ w) / pv
        over = crc > cap
        if not over.any():
            break
        # dampened multiplicative trim toward the cap
        w[over] = w[over] * np.sqrt(cap / crc[over])
    return w


def vol_target(w: np.ndarray, cov: np.ndarray, target_ann: float) -> np.ndarray:
    ann_vol = float(w @ cov @ w) ** 0.5 * np.sqrt(1.0)  # cov already annualized
    if ann_vol <= target_ann or ann_vol == 0:
        return w
    return w * (target_ann / ann_vol)


def metrics(equity: list[float]) -> dict[str, float]:
    eq = np.array(equity, dtype=float)
    rets = np.diff(eq) / eq[:-1]
    total_ret = float(eq[-1] / eq[0] - 1.0)
    sd = float(rets.std(ddof=1)) if len(rets) > 1 else 0.0
    # annualized to match repo convention (backtester.py: sharpe_daily = mean/std * sqrt(252))
    sharpe_daily = float(rets.mean() / sd) * (TRADING_DAYS ** 0.5) if sd > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    max_dd = float(((eq - peak) / peak).min()) if len(eq) else 0.0
    return {
        "total_return_pct": round(100 * total_ret, 3),
        "sharpe_daily": round(sharpe_daily, 4),
        "max_drawdown_pct": round(100 * max_dd, 3),
        "ev": round(100 * total_ret * sharpe_daily, 4),
    }


def simulate_window(name, start, end, mv, dates, px):
    win_dates = [d for d in dates if start <= d <= end]
    if len(win_dates) < 40:
        return None
    # eligible: has >=MIN_LOOKBACK history before window start AND covers the window
    eligible = []
    for t, m in mv.items():
        if t not in px:
            continue
        pre = [d for d in px[t] if d < start]
        if len(pre) >= MIN_LOOKBACK and all(d in px[t] for d in win_dates):
            eligible.append(t)
    if len(eligible) < 3:
        return {"window": name, "skipped": "fewer than 3 eligible names", "eligible": eligible}
    eligible.sort()
    w0 = np.array([mv[t] for t in eligible], dtype=float)
    w0 = w0 / w0.sum()

    def price_row(d):
        return np.array([px[t][d] for t in eligible], dtype=float)

    # STATIC: fixed shares from day 0
    p0 = price_row(win_dates[0])
    shares = w0 / p0
    static_eq = [float(shares @ price_row(d)) for d in win_dates]

    # OVERLAY: monthly rebalance using trailing-90d PIT cov
    full_dates = [d for d in dates if d <= end]
    di = {d: i for i, d in enumerate(full_dates)}
    rebal_months = set()
    overlay_eq = [1.0]
    cur_w = None
    cur_cash = 0.0
    turnover = 0.0
    for k, d in enumerate(win_dates):
        ym = d[:7]
        if cur_w is None or ym not in rebal_months:
            rebal_months.add(ym)
            j = di[d]
            lb = full_dates[max(0, j - LOOKBACK):j]  # strictly before d -> PIT
            if len(lb) >= MIN_LOOKBACK:
                M = np.column_stack([[px[t][x] for x in lb] for t in eligible])
                r = np.diff(np.log(M), axis=0)
                cov = np.cov(r, rowvar=False) * TRADING_DAYS
                w = apply_risk_cap(w0, cov, RISK_CAP)
                w = vol_target(w, cov, VOL_TARGET_ANN)
                if cur_w is not None:
                    turnover += float(np.abs(w - cur_w).sum())
                cur_w = w
                cur_cash = 1.0 - float(w.sum())
        if k == 0:
            prev_p = price_row(d)
            continue
        p = price_row(d)
        gross = cur_w @ (p / prev_p)            # invested grows with returns; cash flat
        port_ret = float(gross + cur_cash) - 1.0
        overlay_eq.append(overlay_eq[-1] * (1.0 + port_ret))
        prev_p = p

    return {
        "window": name,
        "eligible": eligible,
        "n_names": len(eligible),
        "static": metrics(static_eq),
        "overlay": metrics(overlay_eq),
        "overlay_turnover": round(turnover, 3),
        "avg_cash_weight_pct": round(100 * cur_cash, 1),
    }


def main() -> int:
    mv = load_weights()
    dates, px = load_panel(sorted(mv))
    results = []
    for name, s, e in WINDOWS:
        r = simulate_window(name, s, e, mv, dates, px)
        if r:
            results.append(r)

    # aggregate over windows with full results
    full = [r for r in results if "static" in r]
    agg = {}
    if full:
        for side in ("static", "overlay"):
            agg[side] = {
                "ev_sum": round(sum(r[side]["ev"] for r in full), 4),
                "mean_total_return_pct": round(float(np.mean([r[side]["total_return_pct"] for r in full])), 3),
                "mean_sharpe_daily": round(float(np.mean([r[side]["sharpe_daily"] for r in full])), 4),
                "worst_max_drawdown_pct": round(min(r[side]["max_drawdown_pct"] for r in full), 3),
            }
        agg["ev_delta"] = round(agg["overlay"]["ev_sum"] - agg["static"]["ev_sum"], 4)
        agg["drawdown_delta_pp"] = round(
            agg["overlay"]["worst_max_drawdown_pct"] - agg["static"]["worst_max_drawdown_pct"], 3)
        agg["return_delta_pp"] = round(
            agg["overlay"]["mean_total_return_pct"] - agg["static"]["mean_total_return_pct"], 3)

    # decision per acceptance rule: EV up AND drawdown reduced AND return not materially worse
    accept = bool(
        agg and agg["ev_delta"] > 0
        and agg["drawdown_delta_pp"] > 0  # less negative = reduced drawdown
        and agg["return_delta_pp"] > -15.0
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "policy": {
            "single_name_risk_cap": RISK_CAP, "vol_target_ann": VOL_TARGET_ANN,
            "lookback_days": LOOKBACK, "rebalance": "monthly", "pit": "trailing-only, no lookahead",
            "excess_to": "cash", "long_only": True,
        },
        "windows": results,
        "aggregate": agg,
        "accepted": accept,
        "decision": ("accepted_held_book_risk_budget_overlay" if accept
                     else "rejected_held_book_risk_budget_overlay"),
        "caveats": [
            "Survivorship: universe = currently-held names; static hold of winners is a hard baseline.",
            "Per-window eligibility varies; MUU/COHR/MRVL etc. only enter later windows.",
            "Observed-only; no core-strategy/order/sizing change.",
        ],
        "generated_at": date.today().isoformat(),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # console report
    print("=" * 78)
    for r in results:
        if "static" not in r:
            print(f"{r['window']:12s} SKIP ({r.get('skipped')}) eligible={r.get('eligible')}")
            continue
        s, o = r["static"], r["overlay"]
        print(f"{r['window']:12s} n={r['n_names']:2d} cash={r['avg_cash_weight_pct']:.0f}%")
        print(f"   STATIC  ret={s['total_return_pct']:8.1f}% sharpe={s['sharpe_daily']:.3f} "
              f"maxDD={s['max_drawdown_pct']:7.1f}% EV={s['ev']:.2f}")
        print(f"   OVERLAY ret={o['total_return_pct']:8.1f}% sharpe={o['sharpe_daily']:.3f} "
              f"maxDD={o['max_drawdown_pct']:7.1f}% EV={o['ev']:.2f}  turnover={r['overlay_turnover']}")
    print("-" * 78)
    if agg:
        print(f"AGG  EV: static {agg['static']['ev_sum']:.2f} -> overlay {agg['overlay']['ev_sum']:.2f} "
              f"(Δ {agg['ev_delta']:+.2f})")
        print(f"     worst maxDD: static {agg['static']['worst_max_drawdown_pct']:.1f}% -> "
              f"overlay {agg['overlay']['worst_max_drawdown_pct']:.1f}% (Δ {agg['drawdown_delta_pp']:+.1f}pp)")
        print(f"     mean return Δ {agg['return_delta_pp']:+.1f}pp")
    print(f"DECISION: {payload['decision']}  (accepted={accept})")
    print(f"artifact: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
