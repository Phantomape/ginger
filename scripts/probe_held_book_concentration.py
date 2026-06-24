"""Read-only risk-concentration diagnostic for the live held book.

Scoping analysis (observed-only, no strategy change, nothing wired) for the
held-book de-risking exploration. Answers: how much of portfolio RISK (not just
dollars) comes from the AI/semis cluster, and what would capping that cluster
buy in vol / return / Sharpe terms?

Weights come from operator_inputs/open_positions.json market_val. Prices come
from the broad warehouse. Names with no/insufficient history are excluded and
reported. Trailing realized return is a biased expected-return proxy (winner's
look-back, short window) -> treat the RETURN/Sharpe deltas as illustrative; the
VOL / correlation / risk-contribution figures are the robust part.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
POSITIONS = REPO_ROOT / "operator_inputs" / "open_positions.json"

# Clear semis / AI-infra names. MUU classified empirically below (uncertain).
SEMIS_AI = {"NVDA", "AMD", "COHR", "MRVL", "CRDO", "NBIS"}
TRADING_DAYS = 252
CLUSTER_CAP = 0.30  # counterfactual: cap combined semis/AI weight at 30%


def load_weights() -> dict[str, float]:
    d = json.loads(POSITIONS.read_text(encoding="utf-8"))
    w: dict[str, float] = {}
    for key in ("core_positions", "positions", "sleeve_positions", "legacy_positions"):
        for p in d.get(key) or []:
            mv = p.get("market_val")
            if mv:
                w[p["ticker"]] = w.get(p["ticker"], 0.0) + float(mv)
    return w


def load_closes(tickers: list[str]) -> dict[str, dict[str, float]]:
    con = sqlite3.connect(WAREHOUSE)
    out: dict[str, dict[str, float]] = {}
    for t in tickers:
        rows = con.execute(
            "SELECT date, close FROM ohlcv WHERE ticker=? AND close IS NOT NULL ORDER BY date", (t,)
        ).fetchall()
        if rows:
            out[t] = {d: float(c) for d, c in rows}
    con.close()
    return out


def main() -> int:
    mv = load_weights()
    tickers = sorted(mv)
    closes = load_closes(tickers + ["SPY"])

    priced = [t for t in tickers if t in closes and len(closes[t]) > 60]
    dropped = [t for t in tickers if t not in priced]

    # common date window across priced names
    common = set.intersection(*[set(closes[t]) for t in priced])
    dates = sorted(common)
    if len(dates) < 60:
        print("Not enough common history:", len(dates))
        return 1

    def returns(t: str) -> np.ndarray:
        px = np.array([closes[t][d] for d in dates], dtype=float)
        return np.diff(np.log(px))

    R = np.column_stack([returns(t) for t in priced])           # (T, N) daily log returns
    spy_r = returns("SPY") if "SPY" in closes else None

    w = np.array([mv[t] for t in priced], dtype=float)
    w = w / w.sum()

    cov = np.cov(R, rowvar=False) * TRADING_DAYS                 # annualized
    port_var = float(w @ cov @ w)
    port_vol = port_var ** 0.5
    mrc = cov @ w                                                # marginal risk contribution
    crc = w * mrc                                                # component contribution (sums to port_var)
    pct_risk = crc / port_var
    pct_wt = w
    corr = np.corrcoef(R, rowvar=False)
    ann_ret = R.mean(axis=0) * TRADING_DAYS                      # biased trailing proxy

    idx = {t: i for i, t in enumerate(priced)}
    semis = [t for t in priced if t in SEMIS_AI]
    semis_i = [idx[t] for t in semis]
    semis_wt = float(pct_wt[semis_i].sum())
    semis_risk = float(pct_risk[semis_i].sum())
    # avg intra-cluster correlation
    if len(semis_i) > 1:
        sub = corr[np.ix_(semis_i, semis_i)]
        intra = float((sub.sum() - len(semis_i)) / (len(semis_i) * (len(semis_i) - 1)))
    else:
        intra = float("nan")
    # MUU empirical correlation to the cluster (it's classified uncertain)
    muu_corr = None
    if "MUU" in idx and semis_i:
        muu_corr = float(np.mean([corr[idx["MUU"], j] for j in semis_i]))

    print("=" * 70)
    print(f"HELD-BOOK RISK CONCENTRATION  | window {dates[0]}..{dates[-1]} ({len(dates)}d)")
    print(f"priced names: {len(priced)}  | excluded (no/short history): {dropped}")
    print("=" * 70)
    print(f"{'ticker':6s} {'wt%':>6s} {'risk%':>6s} {'ann_vol%':>9s} {'ann_ret%':>9s} {'beta_spy':>9s}")
    order = sorted(range(len(priced)), key=lambda i: -pct_risk[i])
    for i in order:
        t = priced[i]
        own_vol = (cov[i, i]) ** 0.5
        beta = (np.cov(R[:, i], spy_r)[0, 1] * TRADING_DAYS / (spy_r.var() * TRADING_DAYS)) if spy_r is not None else float("nan")
        print(f"{t:6s} {100*pct_wt[i]:6.1f} {100*pct_risk[i]:6.1f} {100*own_vol:9.1f} {100*ann_ret[i]:9.1f} {beta:9.2f}")
    print("-" * 70)
    port_ret = float(w @ ann_ret)
    print(f"PORTFOLIO: ann_vol={100*port_vol:.1f}%  trailing ann_ret(proxy)={100*port_ret:.1f}%  "
          f"Sharpe(proxy)={port_ret/port_vol:.2f}")
    print(f"SEMIS/AI cluster {sorted(semis)}:")
    print(f"   weight={100*semis_wt:.1f}%  RISK share={100*semis_risk:.1f}%  avg intra-corr={intra:.2f}")
    if muu_corr is not None:
        print(f"   MUU avg corr to cluster = {muu_corr:.2f} (classified uncertain; fold in if high)")

    # ---- counterfactual: cap cluster weight, redeploy excess pro-rata to non-cluster ----
    if semis_wt > CLUSTER_CAP:
        w2 = w.copy()
        excess = semis_wt - CLUSTER_CAP
        # scale cluster down to the cap
        for i in semis_i:
            w2[i] = w[i] * (CLUSTER_CAP / semis_wt)
        non_i = [i for i in range(len(priced)) if i not in semis_i]
        non_wt = w[non_i].sum()
        for i in non_i:
            w2[i] = w[i] + excess * (w[i] / non_wt)            # redeploy pro-rata into non-cluster
        v2 = float(w2 @ cov @ w2) ** 0.5
        r2 = float(w2 @ ann_ret)
        print("-" * 70)
        print(f"COUNTERFACTUAL: cap semis/AI at {100*CLUSTER_CAP:.0f}% (redeploy excess pro-rata to non-cluster)")
        print(f"   ann_vol {100*port_vol:.1f}% -> {100*v2:.1f}%  (Δ {100*(v2-port_vol):+.1f}pp)")
        print(f"   trailing ann_ret(proxy) {100*port_ret:.1f}% -> {100*r2:.1f}%  (Δ {100*(r2-port_ret):+.1f}pp)")
        print(f"   Sharpe(proxy) {port_ret/port_vol:.2f} -> {r2/v2:.2f}")
        # also: redeploy excess to CASH (vol 0) instead of other equities
        wc = w.copy()
        for i in semis_i:
            wc[i] = w[i] * (CLUSTER_CAP / semis_wt)
        cash_wt = 1.0 - wc.sum()
        vc = float(wc @ cov @ wc) ** 0.5   # cash contributes 0 vol
        rc = float(wc @ ann_ret)           # cash contributes 0 return
        print(f"   [alt: excess to CASH] ann_vol -> {100*vc:.1f}%  ann_ret(proxy) -> {100*rc:.1f}%  "
              f"cash_wt={100*cash_wt:.0f}%  Sharpe {rc/vc:.2f}")
    print("=" * 70)
    print("CAVEAT: trailing ann_ret is a biased winner's-lookback proxy on a short window; "
          "the vol/corr/risk-share figures are the robust part. Cash & 2 dataless names excluded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
