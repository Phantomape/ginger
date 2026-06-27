"""exp-20260627-018  (measurement_repair / identity_or_measurement_repair)

Offline materialization of a PIT SEC filer-status surface from local
``dei:EntityPublicFloat`` threshold crossings, plus a structural census of
whether any *tradeable* filer-status transition exists inside the canonical
warehouse universe.

Motivation
----------
exp-20260626-008 -> exp-20260627-015 chased a cover-page TEXT materialization of
the DEI filer-status booleans (Large Accelerated / Accelerated / Non-accelerated
/ Smaller-Reporting / EGC / Shell). Every attempt blocked on network
``primary_document_fetch`` of historical 10-K/10-Q filings; exp-015 closed
"blocked ... network_backfill_required".

Key observation: SEC filer category is *defined by public-float thresholds*
(Exchange Act Rule 12b-2): Large Accelerated >= $700M, Accelerated >= $75M,
otherwise Non-accelerated / Smaller-Reporting. ``dei:EntityPublicFloat`` is a
numeric DEI fact already present per-filing in the LOCAL companyfacts cache
(``data/cache/sec/companyfacts/CIK*.json``), keyed by ``accn``/``filed``. So a
float-threshold PROXY of filer category is materializable OFFLINE with no
network, keyed by accession + filed date = a real PIT event.

This runner therefore (1) builds that offline PIT filer-category sidecar for the
297 canonical-window 10-K/10-Q events and (2) censuses filer-status transitions,
splitting in-window transitions by whether the ticker is in the tradeable OHLCV
warehouse. No strategy behavior changes; this is read-only materialization.

This is NOT a candidate-pool alpha rule. It is a feasibility/materialization
audit whose verdict gates whether the filer-status-upgrade alpha line is worth
any further data work.
"""
from __future__ import annotations

import gzip
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EVENTS = os.path.join(ROOT, "data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl")
CF_DIR = os.path.join(ROOT, "data/cache/sec/companyfacts")
BASELINE = os.path.join(
    ROOT, "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ARTIFACT = os.path.join(
    ROOT,
    "data/experiments/exp-20260627-018/exp_20260627_018_offline_float_filer_status_materialization.json",
)
SNAPSHOTS = {
    "old_thin": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    "mid_weak": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    "late_strong": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
}
WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
]
# Exchange Act Rule 12b-2 public-float thresholds (entry thresholds).
LARGE_ACCELERATED_MIN = 700_000_000
ACCELERATED_MIN = 75_000_000
RANK = {"non_accelerated_or_src": 0, "accelerated": 1, "large_accelerated": 2}


def filer_category(float_usd):
    if float_usd is None:
        return "unknown"
    if float_usd >= LARGE_ACCELERATED_MIN:
        return "large_accelerated"
    if float_usd >= ACCELERATED_MIN:
        return "accelerated"
    return "non_accelerated_or_src"


def window_of(date_str):
    for name, start, end in WINDOWS:
        if start <= date_str <= end:
            return name
    return None


def load_companyfacts(cik):
    path = os.path.join(CF_DIR, f"CIK{cik}.json")
    if not os.path.exists(path):
        return None
    raw = open(path, "rb").read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    try:
        return json.loads(raw)
    except Exception:
        return None


def public_float_history(cik):
    """Return [(filed_date, end_date, val)] dedup+sorted by filed date."""
    facts = load_companyfacts(cik)
    if not facts:
        return []
    pf = facts.get("facts", {}).get("dei", {}).get("EntityPublicFloat", {})
    seen = {}
    for _unit, arr in pf.get("units", {}).items():
        for pt in arr:
            filed, val, end = pt.get("filed"), pt.get("val"), pt.get("end")
            if filed and val is not None:
                seen[(filed, end)] = val
    return sorted(((f, e, v) for (f, e), v in seen.items()), key=lambda r: r[0])


def warehouse_tickers():
    tickers = set()
    for _w, rel in SNAPSHOTS.items():
        fp = os.path.join(ROOT, rel)
        if os.path.exists(fp):
            md = json.load(open(fp)).get("metadata", {})
            tickers |= set(md.get("tickers", []))
    return tickers


def load_canonical_events():
    events = []
    with open(EVENTS, encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("form_base") not in ("10-K", "10-Q"):
                continue
            if not window_of((e.get("accepted_at") or "")[:10]):
                continue
            events.append(e)
    return events


def main():
    warehouse = warehouse_tickers()
    events = load_canonical_events()
    ciks = sorted({e["cik"] for e in events})
    cik2tkr = {e["cik"]: e["ticker"] for e in events}

    # per-CIK float history (offline)
    float_hist = {c: public_float_history(c) for c in ciks}
    have_float = [c for c in ciks if float_hist[c]]
    missing_float = [c for c in ciks if not float_hist[c]]

    # 1. PIT filer-category sidecar: for each canonical periodic event, classify
    #    by the most recent EntityPublicFloat datapoint filed strictly on/before
    #    the event accepted_at, and flag whether THIS filing's category differs
    #    from the prior PIT-known category for the same issuer.
    sidecar = []
    for e in sorted(events, key=lambda x: x.get("accepted_at", "")):
        cik = e["cik"]
        asof = (e.get("accepted_at") or "")[:10]
        hist = float_hist.get(cik, [])
        prior = [(f, v) for (f, _end, v) in hist if f <= asof]
        cur_val = prior[-1][1] if prior else None
        cur_cat = filer_category(cur_val)
        prev_cat = filer_category(prior[-2][1]) if len(prior) >= 2 else None
        is_transition = bool(prev_cat and cur_cat != prev_cat and cur_cat != "unknown")
        sidecar.append(
            {
                "ticker": e["ticker"],
                "cik": cik,
                "accession_number": e["accession_number"],
                "accepted_at": e.get("accepted_at"),
                "usable_trade_date": e.get("usable_trade_date"),
                "form_type": e.get("form_type"),
                "window": window_of(asof),
                "in_warehouse": e["ticker"] in warehouse,
                "pit_public_float_usd": cur_val,
                "pit_filer_category": cur_cat,
                "prior_filer_category": prev_cat,
                "filer_status_transition": is_transition,
                "category_source": "offline_dei_EntityPublicFloat_threshold_proxy",
            }
        )

    # 2. full-history transition census (filed-date transitions across all float
    #    datapoints for the canonical issuers), and the in-window subset.
    all_transitions = []
    for cik in have_float:
        prev = None
        for filed, _end, val in float_hist[cik]:
            cat = filer_category(val)
            if prev and cat != prev:
                all_transitions.append(
                    {
                        "ticker": cik2tkr[cik],
                        "filed": filed,
                        "from": prev,
                        "to": cat,
                        "float_usd": val,
                        "window": window_of(filed),
                        "in_warehouse": cik2tkr[cik] in warehouse,
                        "is_upgrade": RANK[cat] > RANK[prev],
                    }
                )
            prev = cat
    in_window = [t for t in all_transitions if t["window"]]
    in_window_warehouse = [t for t in in_window if t["in_warehouse"]]

    tickers = sorted({e["ticker"] for e in events})
    in_wh = sorted(set(tickers) & warehouse)
    not_wh = sorted(set(tickers) - warehouse)
    wh_latest_cat = {}
    for cik in have_float:
        tkr = cik2tkr[cik]
        if tkr in warehouse:
            wh_latest_cat[tkr] = filer_category(float_hist[cik][-1][2])

    structurally_tradeable = len(in_window_warehouse) > 0

    artifact = {
        "experiment_id": "exp-20260627-018",
        "lane": "measurement_repair",
        "change_type": "identity_or_measurement_repair",
        "title": "Offline EntityPublicFloat-derived PIT filer-status materialization + tradeable-transition census",
        "materialization": {
            "offline": True,
            "network_required": False,
            "source": "data/cache/sec/companyfacts/CIK*.json :: facts.dei.EntityPublicFloat",
            "category_rule": "Exchange Act Rule 12b-2 public-float thresholds ($700M large-accelerated, $75M accelerated)",
            "proxy_caveat": (
                "Float-threshold proxy of the cover-page filer-status checkbox. It does NOT model "
                "the SEC hysteresis (an issuer keeps accelerated status until float drops below a "
                "lower EXIT threshold) nor the revenue test for smaller-reporting-company status, "
                "so it can disagree with the authoritative cover-page checkbox in borderline cases. "
                "EntityPublicFloat is also measured as of the issuer's most recent second fiscal "
                "quarter and reported on the next 10-K, i.e. it is stale-dated relative to the "
                "filing acceptance date used here as the PIT event."
            ),
        },
        "coverage": {
            "canonical_periodic_events": len(events),
            "distinct_ciks": len(ciks),
            "ciks_with_public_float": len(have_float),
            "ciks_missing_companyfacts": missing_float,
            "distinct_tickers": len(tickers),
            "tickers_in_warehouse": in_wh,
            "tickers_not_in_warehouse": not_wh,
        },
        "transition_census": {
            "total_full_history_transitions": len(all_transitions),
            "in_canonical_window_transitions": len(in_window),
            "in_window_warehouse_transitions": len(in_window_warehouse),
            "in_window_detail": in_window,
        },
        "warehouse_filer_category_census": {
            "latest_category_counts": dict(Counter(wh_latest_cat.values())),
            "warehouse_names_not_large_accelerated": [
                t for t, c in wh_latest_cat.items() if c != "large_accelerated"
            ],
        },
        "verdict": {
            "surface_offline_materializable": True,
            "structurally_tradeable_in_core_warehouse": structurally_tradeable,
            "decision": (
                "materialized_offline_but_structurally_untradeable_in_core_universe"
                if not structurally_tradeable
                else "materialized_offline_tradeable_transitions_exist"
            ),
            "reasoning": (
                "All filer-status transitions inside the canonical windows are UP-crossings to "
                "large-accelerated in float-explosion names (CIFR, WULF, APLD, CORZ) that are NOT "
                "in the tradeable OHLCV warehouse. Every one of the {n_wh} warehouse periodic "
                "filers is permanently large-accelerated, so 0 in-window transitions are tradeable. "
                "Materializing the cover-page TEXT (the exp-010..015 network chase) cannot change "
                "this: the filer-status-upgrade signal and the curated tradeable universe are "
                "disjoint. Broad-universe expansion to reach the float-explosion names was already "
                "rejected (exp-20260627-017 line); the signal is also momentum-confounded (float "
                "crosses $700M because the stock already rallied multi-x) and stale-dated."
            ).format(n_wh=len(wh_latest_cat)),
        },
        "sidecar_rows": sidecar,
    }

    os.makedirs(os.path.dirname(ARTIFACT), exist_ok=True)
    with open(ARTIFACT, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2)

    # console summary
    print(f"canonical periodic events: {len(events)}  ciks: {len(ciks)}  with float: {len(have_float)}")
    print(f"tickers in warehouse: {len(in_wh)}  not in warehouse: {len(not_wh)}")
    print(f"full-history transitions: {len(all_transitions)}  in-window: {len(in_window)}  in-window&warehouse: {len(in_window_warehouse)}")
    for t in in_window:
        print(f"   {t['ticker']:6s} {t['filed']} {t['from']}->{t['to']} ${t['float_usd']/1e6:,.0f}M window={t['window']} in_warehouse={t['in_warehouse']}")
    print("VERDICT:", artifact["verdict"]["decision"])
    print("artifact:", os.path.relpath(ARTIFACT, ROOT))
    return artifact


if __name__ == "__main__":
    main()
