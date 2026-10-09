"""V3 step 3: comparator readings on the dev window, checked against an independent hand calculation.

The hand calculation reads the raw CSVs directly and does not import the engine, so an engine
bug cannot hide behind itself.  Output: v3/ledger/baselines_dev.json.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

V3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3 / "evaluator"))
import baselines  # noqa: E402
import evaluate  # noqa: E402
import metrics  # noqa: E402

BPS = 3e-4
FEE = 1.0
CAPITAL = 100_000.0


def hand_inputs():
    spy = pd.read_csv(V3 / "data/raw/etf/SPY.csv", dtype={"date": str})
    idx = pd.to_datetime(spy["date"])
    r = pd.Series(((spy["close"] + spy["dividend"] + spy["capital_gain"]) / spy["close"].shift(1) - 1).values, index=idx)
    bill = pd.read_csv(V3 / "data/raw/fred/DTB3.csv", dtype={"date": str})
    rate = pd.Series(bill["value"].values / 100, index=pd.to_datetime(bill["date"]))
    full = rate.reindex(rate.index.union(idx)).ffill()
    prev = full.shift(1).reindex(idx)  # rate known the day before
    cash = (prev / 252).fillna(0.0)
    return r, cash


def hand_run(r: pd.Series, cash: pd.Series, start, end, want_in) -> pd.Series:
    """want_in(month_end_date) -> bool.  Signal at month end, fill at next close."""
    days = r.loc[start:end].index
    month_ends = set(pd.Series(r.index, index=r.index).groupby(r.index.to_period("M")).max())
    nav, inside, pending, out = CAPITAL, False, None, []
    for i, d in enumerate(days):
        g = r[d] if inside else cash[d]
        nav *= 1 + g
        cost = 0.0
        if pending is not None and pending[0] == i:
            if pending[1] != inside:
                cost = BPS + FEE / nav
                nav *= 1 - cost
                inside = pending[1]
            pending = None
        if d in month_ends and i < len(days) - 1:
            pending = (i + 1, want_in(d))
        out.append((1 + g) * (1 - cost) - 1)
    return pd.Series(out, index=days)


def ann(x: pd.Series) -> dict:
    yrs = len(x) / 252
    return {"ann_return": (1 + x).prod() ** (1 / yrs) - 1, "ann_vol": x.std() * math.sqrt(252)}


def main() -> int:
    lock = evaluate.verify_lock()
    tr, cash = evaluate.panels(lock)["trading"]
    tr, cash = tr.loc[:evaluate.DEV_END], cash.loc[:evaluate.DEV_END]
    start = evaluate.first_start(tr)
    end = evaluate.DEV_END
    eng = {n: evaluate.run_layer(f, "trading", (tr, cash), start, end, "M").net
           for n, f in (("S0", baselines.s0_spy), ("S1", baselines.s1_spy_200dma))}

    r, hcash = hand_inputs()
    r, hcash = r.loc[:end], hcash.loc[:end]
    tri = (1 + r.fillna(0)).cumprod()
    hand = {
        "S0": hand_run(r, hcash, start, end, lambda d: True),
        "S1": hand_run(r, hcash, start, end, lambda d: tri.loc[:d].iloc[-1] > tri.loc[:d].iloc[-200:].mean()),
    }

    report = {"window": [str(start.date()), end], "readings": {}, "hand_check": {}}
    for n in ("S0", "S1"):
        e, h = eng[n], hand[n]
        report["readings"][n] = metrics.summary(e, cash)
        report["hand_check"][n] = {
            "max_abs_daily_diff": float((e - h.reindex(e.index)).abs().max()),
            "hand": ann(h), "engine": ann(e),
        }
    s2 = metrics.vol_matched(eng["S1"], eng["S0"], cash)
    c = hcash.reindex(hand["S1"].index)
    k = (hand["S1"] - c).std() / (hand["S0"] - c).std()
    hand_s2 = ((hand["S1"] - (c + k * (hand["S0"] - c))).mean() * 252)
    report["readings"]["S2_vs_S1"] = s2
    report["hand_check"]["S2"] = {"k_engine": s2["k"], "k_hand": float(k),
                                  "excess_engine": s2["excess_ann"], "excess_hand": float(hand_s2)}
    s1_switches = int((evaluate.run_layer(baselines.s1_spy_200dma, "trading", (tr, cash), start, end, "M").turnover > 0).sum())
    report["readings"]["S1_trades"] = s1_switches
    out = V3 / "ledger" / "baselines_dev.json"
    out.write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
