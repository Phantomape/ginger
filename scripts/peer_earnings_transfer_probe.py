#!/usr/bin/env python3
"""Read-only probe: intra-sector peer shock -> forward return transfer.

Hypothesis (docs/alpha-optimization-playbook.md "Event Graphs / peer
information transfer"): when a sector/industry peer prints a news/earnings
shock (overnight gap + volume spike), the *other* names in the same group drift
in the same direction over the next few days. If true, an
`early_peer_reaction_bucket` field carries forward-return information BEFORE the
trade -- a new PIT ranking/candidate signal that does not need a matured paper
sleeve to evaluate.

OBSERVE-ONLY. Does not touch entries, exits, ranking, sizing, or orders. It
reads OHLCV + an industry/sector map and prints bucketed forward returns.

PIT safety: the field at day D uses ONLY peer shocks strictly before D
(ages 1..LOOKBACK). Forward returns are measured from D's close forward.

Finding (2026-05-30, snapshot 20251023_20260421, 56-name universe):
  - INDUSTRY granularity collapses to ~1 usable group (Semiconductors) on this
    narrow universe and shows a *contrarian* quirk -- not generalizable.
  - SECTOR granularity (Tech / Comm Svcs / Industrials / Financials, ~9.9k
    obs) shows the hypothesized *momentum* direction, and it SURVIVES
    beta-neutralization (excess vs SPY): moderate positive peer shock -> ~+1.5%
    (5d) / +2.1% (10d) excess lift; negative peer shock -> ~-1.0% / -1.4%.
  - The signal lives in MODERATE peer shocks; EXTREME (strong_*) shocks are
    muted (idiosyncratic / over-reaction).
  Caveats before any Gate use: narrow tech-heavy universe (confounded by AI
  theme co-movement), overlapping forward windows inflate significance, shocks
  are gap+volume proxies (not a real earnings calendar), no transaction costs.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OHLCV = REPO / "data/ohlcv/ohlcv_snapshot_20251023_20260421.json"
SECTOR_MAP = REPO / "data/reference/broad_market_sector_map.json"

GAP_THR = 0.05
VOL_THR = 1.8
LOOKBACK = 5
FWD_HORIZONS = (5, 10)
MIN_PEERS = 4
STRONG = 0.03
EXCLUDE = {"SPY", "QQQ", "IWM", "IEF", "TLT", "USO", "UUP", "XLE", "XLP",
           "XLU", "XLV", "DIA", "GLD", "SLV", "ARKX", "ARKK"}
BENCH = "SPY"
ORDER = ["strong_pos", "pos", "none", "neg", "strong_neg"]


def load():
    oh = json.loads(OHLCV.read_text())["ohlcv"]
    smap = json.loads(SECTOR_MAP.read_text()).get("entries", {})
    panel = {t.upper(): sorted(b, key=lambda x: x["Date"])
             for t, b in oh.items()
             if t.upper() not in EXCLUDE and isinstance(b, list) and len(b) >= 60}
    bench = {b["Date"]: b["Close"] for b in oh[BENCH]} if BENCH in oh else {}
    return panel, smap, bench


def group_of(t, smap, gran):
    e = smap.get(t.upper())
    return e.get(gran) if isinstance(e, dict) else None


def detect_shocks(panel):
    shocks, series = {}, {}
    for t, bars in panel.items():
        c = [b["Close"] for b in bars]
        o = [b["Open"] for b in bars]
        v = [b["Volume"] for b in bars]
        dt = [b["Date"] for b in bars]
        series[t] = {"d": dt, "c": c}
        ev = []
        for i in range(21, len(bars)):
            if not c[i - 1]:
                continue
            gap = o[i] / c[i - 1] - 1.0
            av = statistics.fmean(v[i - 20:i]) or 0.0
            vr = (v[i] / av) if av else 0.0
            dr = c[i] / c[i - 1] - 1.0
            if abs(gap) >= GAP_THR and vr >= VOL_THR:
                ev.append((dt[i], dr))
        shocks[t] = ev
    return shocks, series


def bucket(score, pc, nc):
    if pc == 0 and nc == 0:
        return "none"
    if score >= STRONG:
        return "strong_pos"
    if score > 0:
        return "pos"
    if score <= -STRONG:
        return "strong_neg"
    return "neg"


def run(gran, excess):
    panel, smap, bench = load()
    shocks, series = detect_shocks(panel)
    members = defaultdict(list)
    for t in panel:
        g = group_of(t, smap, gran)
        if g:
            members[g].append(t)
    usable = {g: m for g, m in members.items() if len(m) >= MIN_PEERS}
    sbd = defaultdict(lambda: defaultdict(list))
    for t, ev in shocks.items():
        g = group_of(t, smap, gran)
        if g in usable:
            for d, dr in ev:
                sbd[g][d].append((t, dr))

    buckets = defaultdict(lambda: {h: [] for h in FWD_HORIZONS})
    overall = {h: [] for h in FWD_HORIZONS}
    for t in panel:
        g = group_of(t, smap, gran)
        if g not in usable:
            continue
        dt, c = series[t]["d"], series[t]["c"]
        for i in range(21, len(dt) - max(FWD_HORIZONS)):
            score = pc = nc = 0
            for age in range(1, LOOKBACK + 1):
                j = i - age
                if j < 0:
                    break
                for pt, pr in sbd[g].get(dt[j], ()):
                    if pt == t:
                        continue
                    score += pr * ((LOOKBACK - age + 1) / LOOKBACK)
                    pc += pr > 0
                    nc += pr <= 0
            b = bucket(score, pc, nc)
            for h in FWD_HORIZONS:
                fwd = c[i + h] / c[i] - 1.0
                if excess and dt[i] in bench and dt[i + h] in bench:
                    fwd -= bench[dt[i + h]] / bench[dt[i]] - 1.0
                buckets[b][h].append(fwd)
                overall[h].append(fwd)

    tag = f"granularity={gran} | return={'EXCESS vs SPY' if excess else 'raw'}"
    print(f"\n##### {tag} | usable groups={len(usable)} {list(usable)[:6]} #####")
    for h in FWD_HORIZONS:
        ov = overall[h]
        om = statistics.fmean(ov) * 100 if ov else 0
        print(f" fwd{h}d baseline mean={om:.2f}% n={len(ov)}")
        print(f"   {'bucket':11}{'n':>6}{'mean%':>9}{'hit%':>7}{'lift%':>8}")
        for b in ORDER:
            xs = buckets[b][h]
            if not xs:
                continue
            m = statistics.fmean(xs) * 100
            hr = sum(1 for x in xs if x > 0) / len(xs) * 100
            print(f"   {b:11}{len(xs):>6}{m:>9.2f}{hr:>7.1f}{m - om:>+8.2f}")


def main():
    run("industry", excess=False)
    run("sector", excess=False)
    run("sector", excess=True)   # decisive beta-neutralized test


if __name__ == "__main__":
    main()
