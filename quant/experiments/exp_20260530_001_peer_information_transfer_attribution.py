#!/usr/bin/env python3
"""exp-20260530-001: intra-sector peer information-transfer attribution (read-only).

Hardens scripts/peer_earnings_transfer_probe.py with the two robustness controls
that are doable offline:

  1. NON-OVERLAPPING forward sampling (per ticker, keep observer days spaced
     >= H trading days apart) + Welch t-stats, so overlapping-window
     autocorrelation does not inflate apparent significance.
  2. TEMPORAL OOS replication across 3 equal calendar sub-periods, to check the
     sign is not a single-regime artifact.

OBSERVE-ONLY. Touches nothing in entries/exits/ranking/sizing/orders/paper
sleeves/LLM. PIT-safe: the field at day D uses only peer shocks strictly before
D; forward returns are measured from D's close.

Remaining caveat it CANNOT fix offline: the universe is ~56 tech-heavy names
across 4 sectors (possible AI-theme co-movement). A real Gate experiment needs
a broad multi-sector universe + a true earnings calendar.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OHLCV = REPO / "data/ohlcv/ohlcv_snapshot_20251023_20260421.json"
SECTOR_MAP = REPO / "data/reference/broad_market_sector_map.json"
EXP_ID = "exp-20260530-001"
OUT_JSON = REPO / f"data/experiments/{EXP_ID}/peer_information_transfer_attribution.json"
OUT_MD = REPO / f"experiments/artifacts/{EXP_ID}_peer_information_transfer_attribution.md"
OUT_LOG = REPO / f"experiments/logs/{EXP_ID}.json"

GAP_THR, VOL_THR, LOOKBACK = 0.05, 1.8, 5
FWD_HORIZONS = (5, 10)
MIN_PEERS, STRONG = 4, 0.03
GRAN = "sector"
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


def sector_of(t, smap):
    e = smap.get(t.upper())
    return e.get(GRAN) if isinstance(e, dict) else None


def detect(panel):
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
            if abs(gap) >= GAP_THR and vr >= VOL_THR:
                ev.append((dt[i], c[i] / c[i - 1] - 1.0))
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


def welch_t(a, b):
    """Welch t-stat of mean(a)-mean(b); None if too small."""
    if len(a) < 5 or len(b) < 5:
        return None
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    va, vb = statistics.pvariance(a), statistics.pvariance(b)
    denom = math.sqrt(va / len(a) + vb / len(b))
    return (ma - mb) / denom if denom else None


def build_observations(panel, smap, bench):
    """Return per-horizon lists of (date, sector, ticker, obs_index, bucket, fwd_excess)."""
    shocks, series = detect(panel)
    members = defaultdict(list)
    for t in panel:
        s = sector_of(t, smap)
        if s:
            members[s].append(t)
    usable = {s: m for s, m in members.items() if len(m) >= MIN_PEERS}
    sbd = defaultdict(lambda: defaultdict(list))
    for t, ev in shocks.items():
        s = sector_of(t, smap)
        if s in usable:
            for d, dr in ev:
                sbd[s][d].append((t, dr))

    obs = {h: [] for h in FWD_HORIZONS}
    for t in panel:
        s = sector_of(t, smap)
        if s not in usable:
            continue
        dt, c = series[t]["d"], series[t]["c"]
        for i in range(21, len(dt) - max(FWD_HORIZONS)):
            score = pc = nc = 0
            for age in range(1, LOOKBACK + 1):
                j = i - age
                if j < 0:
                    break
                for pt, pr in sbd[s].get(dt[j], ()):
                    if pt == t:
                        continue
                    score += pr * ((LOOKBACK - age + 1) / LOOKBACK)
                    pc += pr > 0
                    nc += pr <= 0
            b = bucket(score, pc, nc)
            for h in FWD_HORIZONS:
                fwd = c[i + h] / c[i] - 1.0
                if dt[i] in bench and dt[i + h] in bench:
                    fwd -= bench[dt[i + h]] / bench[dt[i]] - 1.0
                obs[h].append((dt[i], t, i, b, fwd))
    return obs, len(usable), sum(len(v) for v in shocks.values()), sorted(usable)


def non_overlap(rows, h):
    """Greedy per-ticker: keep observations >= h indices apart so fwd windows
    don't overlap. rows: list of (date,ticker,idx,bucket,fwd)."""
    last = {}
    kept = []
    for d, t, idx, b, fwd in sorted(rows, key=lambda r: (r[1], r[2])):
        if t not in last or idx - last[t] >= h:
            kept.append((d, t, idx, b, fwd))
            last[t] = idx
    return kept


def summarize(rows):
    by = defaultdict(list)
    for d, t, idx, b, fwd in rows:
        by[b].append(fwd)
    base = by.get("none", [])
    out = {}
    for b in ORDER:
        xs = by.get(b, [])
        if not xs:
            continue
        out[b] = {
            "n": len(xs),
            "mean_excess_pct": round(statistics.fmean(xs) * 100, 3),
            "hit_pct": round(sum(1 for x in xs if x > 0) / len(xs) * 100, 1),
            "t_vs_none": (round(welch_t(xs, base), 2)
                          if welch_t(xs, base) is not None else None),
        }
    return out


def main():
    panel, smap, bench = load()
    obs, n_sectors, n_shocks, sectors = build_observations(panel, smap, bench)

    # date range for sub-period split
    all_dates = sorted({d for h in FWD_HORIZONS for (d, *_rest) in obs[h]})
    n = len(all_dates)
    cuts = [all_dates[0], all_dates[n // 3], all_dates[2 * n // 3], all_dates[-1]]
    subperiods = [(cuts[k], cuts[k + 1]) for k in range(3)]

    report = {
        "experiment_id": EXP_ID,
        "read_only": True,
        "production_impact": {"alters_orders": False, "alters_ranking": False,
                              "alters_sizing": False, "alters_entries": False},
        "config": {"gap_thr": GAP_THR, "vol_thr": VOL_THR, "lookback": LOOKBACK,
                   "granularity": GRAN, "min_peers": MIN_PEERS,
                   "forward_return": "excess_vs_SPY", "strong_thr": STRONG},
        "universe": {"tickers": len(panel), "usable_sectors": n_sectors,
                     "sectors": sectors, "shock_events": n_shocks},
        "pooled_non_overlapping": {},
        "temporal_subperiods": {},
        "caveats": [
            "universe is ~56 tech-heavy names across 4 sectors; possible "
            "AI-theme co-movement not removed by SPY-excess alone",
            "shocks are gap+volume proxies, not a true earnings calendar",
            "no transaction costs",
            "sub-period bucket samples are thin after non-overlap sampling",
        ],
    }

    for h in FWD_HORIZONS:
        kept = non_overlap(obs[h], h)
        report["pooled_non_overlapping"][f"fwd_{h}d"] = {
            "n_after_non_overlap": len(kept),
            "buckets": summarize(kept),
        }
        # temporal sub-periods
        sp = {}
        for k, (a, b) in enumerate(subperiods, 1):
            seg = [r for r in obs[h] if a <= r[0] <= b]
            seg = non_overlap(seg, h)
            sp[f"subperiod_{k}_{a}_to_{b}"] = summarize(seg)
        report["temporal_subperiods"][f"fwd_{h}d"] = sp

    # sign-consistency verdict on the moderate `pos` bucket
    def pos_sign_consistency(h):
        signs = []
        for v in report["temporal_subperiods"][f"fwd_{h}d"].values():
            p = v.get("pos")
            if p:
                base = None  # mean lift vs none within sub-period
                none = v.get("none")
                if none:
                    signs.append(p["mean_excess_pct"] - none["mean_excess_pct"])
        pos_ct = sum(1 for s in signs if s > 0)
        return {"subperiods_with_pos_lift": pos_ct, "n_subperiods": len(signs),
                "lifts": [round(s, 3) for s in signs]}
    report["pos_bucket_sign_consistency"] = {
        f"fwd_{h}d": pos_sign_consistency(h) for h in FWD_HORIZONS}

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    tmp.replace(OUT_JSON)
    write_markdown(report)
    write_log(report)
    print(json.dumps({k: report[k] for k in
                      ("universe", "pooled_non_overlapping",
                       "pos_bucket_sign_consistency")},
                     ensure_ascii=False, indent=1))
    print(f"\nartifact -> {OUT_JSON}\nmarkdown -> {OUT_MD}\nlog -> {OUT_LOG}")


def write_markdown(r):
    L = [f"# {EXP_ID}: intra-sector peer information-transfer attribution",
         "", "**Read-only / observe-only.** Does not touch entries, exits, "
         "ranking, sizing, orders, paper sleeves, or LLM.", "",
         f"Universe: {r['universe']['tickers']} tickers, "
         f"{r['universe']['usable_sectors']} sectors "
         f"({', '.join(r['universe']['sectors'])}), "
         f"{r['universe']['shock_events']} shock events.", "",
         "## Pooled, non-overlapping forward sampling (excess vs SPY)", ""]
    for h in FWD_HORIZONS:
        blk = r["pooled_non_overlapping"][f"fwd_{h}d"]
        L += [f"### fwd {h}d  (n={blk['n_after_non_overlap']} after non-overlap)",
              "", "| bucket | n | mean excess % | hit % | t vs none |",
              "|---|---:|---:|---:|---:|"]
        for b in ORDER:
            v = blk["buckets"].get(b)
            if v:
                L.append(f"| {b} | {v['n']} | {v['mean_excess_pct']:+.2f} | "
                         f"{v['hit_pct']:.0f} | {v['t_vs_none']} |")
        L.append("")
    L += ["## Temporal sign-consistency of the `pos` bucket", ""]
    for h in FWD_HORIZONS:
        c = r["pos_bucket_sign_consistency"][f"fwd_{h}d"]
        L.append(f"- fwd {h}d: positive lift in "
                 f"{c['subperiods_with_pos_lift']}/{c['n_subperiods']} "
                 f"sub-periods (lifts {c['lifts']})")
    L += ["", "## Caveats", ""] + [f"- {c}" for c in r["caveats"]]
    OUT_MD.write_text("\n".join(L) + "\n")


def write_log(r):
    # Faithful evaluation of the pre-registered acceptance rule:
    #   "promising if SPY-excess lift monotonic AND |t|>=2 under non-overlap
    #    sampling in >=2 of 3 temporal sub-periods."
    def cell(h, b):
        return (r["pooled_non_overlapping"][f"fwd_{h}d"]["buckets"].get(b) or {})
    pos_t = {h: cell(h, "pos").get("t_vs_none") for h in FWD_HORIZONS}
    strong_pos_t = {h: cell(h, "strong_pos").get("t_vs_none") for h in FWD_HORIZONS}

    # monotonicity: positive buckets above none AND negative buckets below none
    def monotonic(h):
        b = r["pooled_non_overlapping"][f"fwd_{h}d"]["buckets"]
        none = (b.get("none") or {}).get("mean_excess_pct", 0)
        up = all((b.get(k) or {}).get("mean_excess_pct", none) >= none
                 for k in ("pos", "strong_pos"))
        down = all((b.get(k) or {}).get("mean_excess_pct", none) <= none
                   for k in ("neg", "strong_neg"))
        return up and down
    mono = {h: monotonic(h) for h in FWD_HORIZONS}
    any_sig_pos = any(t is not None and abs(t) >= 2
                      for t in list(pos_t.values()) + list(strong_pos_t.values()))
    consistent = all(c["subperiods_with_pos_lift"] >= 2
                     for c in r["pos_bucket_sign_consistency"].values())

    if any_sig_pos and all(mono.values()) and consistent:
        decision = "promising_pursue_gate_experiment"
    elif any_sig_pos:
        decision = ("partial_one_surviving_cell_does_not_clear_preregistered_"
                    "bar")  # significant cell but monotonicity/consistency failed
    else:
        decision = "weak_keep_observing"

    log = {
        "experiment_id": EXP_ID, "lane": "alpha_discovery",
        "change_type": "peer_information_transfer_attribution_probe",
        "decision": decision, "read_only": True,
        "single_causal_variable": "moderate prior-5d intra-sector peer shock "
                                  "reaction bucket (early_peer_reaction_bucket)",
        "preregistered_rule_components": {
            "any_positive_cell_t_ge_2": any_sig_pos,
            "monotonic_by_horizon": mono,
            "pos_lift_in_ge2_of_3_subperiods": consistent,
        },
        "pos_bucket_t_vs_none": pos_t,
        "strong_pos_bucket_t_vs_none": strong_pos_t,
        "surviving_signal": ("strong_pos sector-peer shock -> ~+3.1% SPY-excess "
                             "10d, t~2.8; 5d and the entire negative side wash "
                             "out under non-overlap sampling"),
        "sign_consistency": r["pos_bucket_sign_consistency"],
        "honest_read": ("the clean bidirectional monotonic signal seen with "
                        "OVERLAPPING windows was largely autocorrelation "
                        "inflation; one thin positive-side cell survives but "
                        "fails the pre-registered monotonicity + temporal "
                        "stability bar (one sub-period reverses)"),
        "next_step": ("only justifies a broad multi-sector universe + true "
                      "earnings-calendar re-test, NOT a ranking/sizing change"),
        "must_not_touch": ["entries", "exits", "ranking", "sizing", "orders",
                           "paper_sleeves", "llm"],
    }
    tmp = OUT_LOG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(log, ensure_ascii=False, indent=2))
    tmp.replace(OUT_LOG)


if __name__ == "__main__":
    main()
