# Bucket stream-dependent experiments by "redo value" given the broad-data
# repair. Redo-worthy = blocked-by-missing-data OR positive-but-underpowered
# (narrow universe = tiny samples). Aggregate by stream x mechanism_family. RO.
import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
log = (REPO / "docs/experiment_log.jsonl").read_text(encoding="utf-8").splitlines()

STREAMS = {
    "companyfacts/fundamentals": r"companyfact|fundamental|balance.?sheet|earnings.?growth|revenue.?growth|gross.?margin|net.?income",
    "form4_insider": r"form.?4|insider|tax.?withhold",
    "sec_filing_text": r"filing.?text|8-?k|10-?[kq]|financial.?report",
    "earnings_snapshot": r"earnings.?(snapshot|surprise|estimate)|pead|post.?earnings",
    "13f_institutional": r"13f|institutional.?(holding|ownership)|whale",
    "finra_short": r"finra|short.?(interest|pressure|squeeze|crowd)|days.?to.?cover",
    "kova_alt": r"\bkova\b|rs.?proxy",
}


def bucket(dec: str) -> str:
    d = (dec or "").lower()
    if "data_gap" in d or "data gap" in d:
        return "A_blocked_missing_data"
    if "immaterial" in d or "not_material" in d or "underpowered" in d or "marginal" in d or ("positive" in d and "not" in d):
        return "B_positive_but_underpowered"
    if "shadow" in d or "observed" in d or "forward" in d or "default_off" in d or "queue" in d:
        return "C_shadow_observed_forward"
    if "accept" in d:
        return "D_accepted_on_narrow_data"
    if "reject" in d:
        return "E_rejected_hard"
    return "F_other"


agg = defaultdict(lambda: {"n": 0, "ids": [], "dates": []})
for ln in log:
    ln = ln.strip()
    if not ln:
        continue
    try:
        o = json.loads(ln)
    except Exception:
        continue
    ts = (o.get("timestamp") or "")[:10]
    if ts < "2026-04-24":
        continue
    blob = " ".join(str(o.get(k, "")) for k in (
        "changed_variable", "hypothesis", "mechanism_family", "trial_family",
        "trial_variant_id", "experiment_id")).lower()
    streams = [s for s, pat in STREAMS.items() if re.search(pat, blob)]
    if not streams:
        continue
    b = bucket(o.get("decision") or o.get("status"))
    for s in streams:
        key = (b, s)
        a = agg[key]
        a["n"] += 1
        a["dates"].append(ts)
        if len(a["ids"]) < 6:
            a["ids"].append(o.get("experiment_id"))

order = ["A_blocked_missing_data", "B_positive_but_underpowered",
         "C_shadow_observed_forward", "D_accepted_on_narrow_data",
         "E_rejected_hard", "F_other"]
for b in order:
    keys = [(k, v) for k, v in agg.items() if k[0] == b]
    if not keys:
        continue
    tot = sum(v["n"] for _, v in keys)
    print(f"\n### {b}  (total {tot})")
    for (bb, s), v in sorted(keys, key=lambda x: -x[1]["n"]):
        dr = f"{min(v['dates'])}..{max(v['dates'])}"
        print(f"  {s:28} n={v['n']:<3} {dr}  e.g. {', '.join(str(i) for i in v['ids'][:4])}")
