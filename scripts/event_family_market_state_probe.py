#!/usr/bin/env python3
"""Read-only probe: SEC 8-K event-family x market-state forward-return drift.

Playbook §6 ("Event / SEC / News / LLM") names "event-family by market-state"
as an underexplored structured-event direction. This probe joins the historical
SEC filing-event panel (item codes = event family, PIT usable_trade_date) to
OHLCV forward returns (excess vs SPY) and splits by market regime, to see
whether any 8-K family drifts predictably and regime-dependently.

OBSERVE-ONLY. Touches no entries/exits/ranking/sizing/orders. PIT-safe: forward
return starts from the SEC-pipeline's usable_trade_date (first tradeable date
after the filing); market state uses SPY data up to that date only.

Robustness (from exp-20260530-001): forward returns are EXCESS vs SPY, and a
non-overlapping per-ticker sample + Welch t-stat guards against
overlapping-window inflation.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OHLCV = REPO / "data/ohlcv/ohlcv_snapshot_20251023_20260421.json"
EVENTS = REPO / "data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl"

FWD = (5, 10)
# event family priority (assign each filing one primary family; skip pure exhibits/admin)
PRIORITY = ["2.02", "5.02", "1.01", "7.01", "8.01"]
FAMILY_NAME = {"2.02": "results(2.02)", "5.02": "leadership(5.02)",
               "1.01": "agreement(1.01)", "7.01": "regFD(7.01)", "8.01": "other(8.01)"}


def load_panel():
    oh = json.loads(OHLCV.read_text())["ohlcv"]
    panel = {t.upper(): sorted(b, key=lambda x: x["Date"])
             for t, b in oh.items() if isinstance(b, list)}
    spy = panel.get("SPY")
    return panel, spy


def idx_on_or_after(bars, date):
    for i, b in enumerate(bars):
        if b["Date"] >= date:
            return i
    return None


def spy_state(spy, date):
    """risk_on if SPY close >= its 50d MA on the last bar < date, else risk_off."""
    prior = [b for b in spy if b["Date"] < date]
    if len(prior) < 50:
        return None
    ma50 = statistics.fmean(b["Close"] for b in prior[-50:])
    return "risk_on" if prior[-1]["Close"] >= ma50 else "risk_off"


def primary_family(codes):
    codes = set(codes or [])
    for f in PRIORITY:
        if f in codes:
            return f
    return None


def welch_t(a, b):
    if len(a) < 5 or len(b) < 5:
        return None
    va, vb = statistics.pvariance(a), statistics.pvariance(b)
    d = math.sqrt(va / len(a) + vb / len(b))
    return (statistics.fmean(a) - statistics.fmean(b)) / d if d else None


def non_overlap(items, h):
    """items: list of (ticker, idx, payload). Keep per-ticker >= h apart."""
    last, kept = {}, []
    for tk, idx, pay in sorted(items, key=lambda x: (x[0], x[1])):
        if tk not in last or idx - last[tk] >= h:
            kept.append((tk, idx, pay))
            last[tk] = idx
    return kept


def main():
    panel, spy = load_panel()
    pset = set(panel)
    rows = [json.loads(l) for l in EVENTS.read_text().splitlines() if l.strip()]

    obs = {h: [] for h in FWD}     # (ticker, idx, {family, state, exc})
    n_join = 0
    for r in rows:
        tk = str(r.get("ticker", "")).upper()
        d = r.get("usable_trade_date")
        if tk not in pset or tk == "SPY" or not d:
            continue
        fam = primary_family(r.get("eight_k_item_codes"))
        if not fam:
            continue
        bars = panel[tk]
        i = idx_on_or_after(bars, d)
        if i is None or i < 1 or i + max(FWD) >= len(bars):
            continue
        st = spy_state(spy, d)
        if st is None:
            continue
        n_join += 1
        for h in FWD:
            fwd = bars[i + h]["Close"] / bars[i]["Close"] - 1.0
            si, sj = idx_on_or_after(spy, bars[i]["Date"]), idx_on_or_after(spy, bars[i + h]["Date"])
            if si is not None and sj is not None:
                fwd -= spy[sj]["Close"] / spy[si]["Close"] - 1.0
            obs[h].append((tk, i, {"family": fam, "state": st, "exc": fwd}))

    print(f"events joined: {n_join} | tickers: "
          f"{len({o[0] for o in obs[FWD[0]]})}\n")

    for h in FWD:
        kept = non_overlap(obs[h], h)
        allx = [p["exc"] for _, _, p in kept]
        base = statistics.fmean(allx) * 100 if allx else 0
        print(f"=== fwd {h}d EXCESS vs SPY (non-overlap n={len(kept)}, "
              f"baseline={base:.2f}%) ===")
        print(f"  {'family':17}{'state':9}{'n':>4}{'mean%':>8}{'hit%':>7}{'t_vs_rest':>10}")
        by = defaultdict(list)
        for _, _, p in kept:
            by[(p["family"], p["state"])].append(p["exc"])
            by[(p["family"], "ALL")].append(p["exc"])
        rest_all = allx
        for fam in PRIORITY:
            for state in ("ALL", "risk_on", "risk_off"):
                xs = by.get((fam, state), [])
                if len(xs) < 5:
                    continue
                rest = [x for x in allx if x not in xs] or rest_all
                t = welch_t(xs, rest)
                m = statistics.fmean(xs) * 100
                hit = sum(1 for x in xs if x > 0) / len(xs) * 100
                flag = " *" if t is not None and abs(t) >= 2 else ""
                print(f"  {FAMILY_NAME[fam]:17}{state:9}{len(xs):>4}{m:>8.2f}"
                      f"{hit:>7.1f}{(round(t,2) if t is not None else 'NA'):>10}{flag}")
        print()


if __name__ == "__main__":
    main()
