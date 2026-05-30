#!/usr/bin/env python3
"""Read-only probe: does market breadth at the breakout day separate good vs bad
breakouts? (breadth-confirmation, data-edge priority surface #2)

Playbook: "market participation confirmation is more valuable than retuning
price-shape thresholds" -- VBB's acceptance is direct evidence. This probe asks
the same on the BROAD breakout panel (not a sleeve): for every 20-day-high
breakout across the universe, bucket by same-day market breadth and attribute
forward SPY-excess returns with non-overlap sampling + Welch t.

OBSERVE-ONLY. No entries/exits/ranking/sizing/orders. PIT-safe: breadth and the
breakout test use data through the signal day's close; forward return is
measured from that close.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OHLCV = REPO / "data/ohlcv/ohlcv_snapshot_20251023_20260421.json"
EXCLUDE = {"SPY", "QQQ", "IWM", "IEF", "TLT", "USO", "UUP", "XLE", "XLP",
           "XLU", "XLV", "DIA", "GLD", "SLV", "ARKX", "ARKK"}
FWD = (5, 10)


def load():
    oh = json.loads(OHLCV.read_text())["ohlcv"]
    panel = {t.upper(): sorted(b, key=lambda x: x["Date"])
             for t, b in oh.items()
             if t.upper() not in EXCLUDE and isinstance(b, list) and len(b) >= 60}
    spy = {b["Date"]: b["Close"] for b in oh["SPY"]} if "SPY" in oh else {}
    return panel, spy


def welch_t(a, b):
    if len(a) < 5 or len(b) < 5:
        return None
    d = math.sqrt(statistics.pvariance(a) / len(a) + statistics.pvariance(b) / len(b))
    return round((statistics.fmean(a) - statistics.fmean(b)) / d, 2) if d else None


def non_overlap(items, h):
    last, kept = {}, []
    for tk, idx, pay in sorted(items, key=lambda x: (x[0], x[1])):
        if tk not in last or idx - last[tk] >= h:
            kept.append((tk, idx, pay))
            last[tk] = idx
    return kept


def main():
    panel, spy = load()
    # all trading dates (union), sorted
    dates = sorted({b["Date"] for bars in panel.values() for b in bars})
    # per-ticker date->index and close/ma50 helpers
    series = {}
    for t, bars in panel.items():
        closes = [b["Close"] for b in bars]
        highs = [b["High"] for b in bars]
        dmap = {b["Date"]: i for i, b in enumerate(bars)}
        series[t] = {"bars": bars, "closes": closes, "highs": highs, "dmap": dmap}

    # market breadth per date: fraction of tickers with close >= own 50d MA (PIT, uses close[i])
    breadth = {}
    for d in dates:
        above = tot = 0
        for t, s in series.items():
            i = s["dmap"].get(d)
            if i is None or i < 50:
                continue
            ma50 = statistics.fmean(s["closes"][i - 50:i])
            tot += 1
            if s["closes"][i] >= ma50:
                above += 1
        if tot >= 15:
            breadth[d] = above / tot

    # detect 20d-high breakouts; record breadth + forward excess return
    obs = {h: [] for h in FWD}
    for t, s in series.items():
        closes, highs, bars = s["closes"], s["highs"], s["bars"]
        for i in range(21, len(bars) - max(FWD)):
            # breakout: close above prior 20-day high (excl today)
            if closes[i] <= max(highs[i - 20:i]):
                continue
            d = bars[i]["Date"]
            if d not in breadth:
                continue
            for h in FWD:
                fwd = closes[i + h] / closes[i] - 1.0
                d0, dh = bars[i]["Date"], bars[i + h]["Date"]
                if d0 in spy and dh in spy:
                    fwd -= spy[dh] / spy[d0] - 1.0
                obs[h].append((t, i, {"breadth": breadth[d], "exc": fwd}))

    # breadth terciles from the breakout sample
    bvals = sorted(p["breadth"] for _t, _i, p in obs[FWD[0]])
    if not bvals:
        print("no breakouts")
        return
    blo, bhi = bvals[len(bvals) // 3], bvals[2 * len(bvals) // 3]
    print(f"breakouts: {len(obs[FWD[0]])} | breadth terciles: "
          f"low<={blo:.2f} mid high>{bhi:.2f}\n")

    for h in FWD:
        kept = non_overlap(obs[h], h)
        allx = [p["exc"] for _t, _i, p in kept]
        base = statistics.fmean(allx) * 100
        print(f"=== fwd {h}d EXCESS vs SPY (non-overlap n={len(kept)}, "
              f"baseline={base:.2f}%) ===")
        buckets = {
            "low_breadth": [p["exc"] for _t, _i, p in kept if p["breadth"] <= blo],
            "mid_breadth": [p["exc"] for _t, _i, p in kept if blo < p["breadth"] <= bhi],
            "high_breadth": [p["exc"] for _t, _i, p in kept if p["breadth"] > bhi],
        }
        print(f"  {'bucket':14}{'n':>5}{'mean%':>8}{'hit%':>7}{'t_vs_low':>10}")
        low = buckets["low_breadth"]
        for name, xs in buckets.items():
            if not xs:
                continue
            m = statistics.fmean(xs) * 100
            hit = sum(1 for x in xs if x > 0) / len(xs) * 100
            t = welch_t(xs, low) if name != "low_breadth" else None
            print(f"  {name:14}{len(xs):>5}{m:>8.2f}{hit:>7.1f}"
                  f"{(t if t is not None else '-'):>10}")
        print()


if __name__ == "__main__":
    main()
