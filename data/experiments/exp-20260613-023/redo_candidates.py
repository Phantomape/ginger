# Find experiments whose signal depended on a data stream that was
# narrow/frozen/broken before the 2026-06-12/06-13 data repairs, so we can
# judge which conclusions are worth redoing on the now-fixed broad data. RO.
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
log = (REPO / "docs/experiment_log.jsonl").read_text(encoding="utf-8").splitlines()

# stream -> regex of terms that imply the experiment consumed it
STREAMS = {
    "companyfacts/fundamentals": r"companyfact|fundamental|balance.?sheet|earnings.?growth|revenue.?growth|gross.?margin|net.?income",
    "form4_insider": r"form.?4|insider|tax.?withhold",
    "sec_filing_text": r"filing.?text|8-?k text|10-?[kq]",
    "earnings_snapshot": r"earnings.?(snapshot|surprise|estimate)|pead|post.?earnings|eps.?",
    "13f_institutional": r"13f|institutional.?(holding|ownership)|whale",
    "finra_short": r"finra|short.?interest|short.?pressure|short.?squeeze|days.?to.?cover",
    "kova_alt": r"\bkova\b|rs.?proxy",
    "broad_warehouse_ohlcv": r"broad.?(universe|market).?(sleeve|ohlcv|warehouse)|warehouse.?batch|broad.?500",
}

rows = []
for ln in log:
    ln = ln.strip()
    if not ln:
        continue
    try:
        o = json.loads(ln)
    except Exception:
        continue
    blob = " ".join(str(o.get(k, "")) for k in (
        "changed_variable", "hypothesis", "mechanism_family", "trial_family",
        "trial_variant_id", "experiment_id")).lower()
    hits = [s for s, pat in STREAMS.items() if re.search(pat, blob)]
    if not hits:
        continue
    rows.append({
        "id": o.get("experiment_id"),
        "ts": (o.get("timestamp") or "")[:10],
        "decision": o.get("decision") or o.get("status"),
        "accepted": o.get("accepted"),
        "accepted_alpha": o.get("accepted_alpha"),
        "lane": o.get("lane"),
        "streams": hits,
        "ev_delta": o.get("aggregate_expected_value_delta"),
        "cv": (o.get("changed_variable") or "")[:120],
    })

rows.sort(key=lambda r: r["ts"])
# focus on those run during the degraded window (warehouse stale since 04-24,
# narrow universe always, companyfacts frozen 06-04, broken CIK map)
print(f"total stream-dependent experiments: {len(rows)}\n")
for r in rows:
    if r["ts"] >= "2026-04-24":
        acc = "ACC" if r["accepted"] else ("acc?" if r["accepted_alpha"] else "rej/obs")
        print(f"{r['ts']} {r['id']:>18} [{acc:7}] {r['decision']!s:42.42} "
              f"{','.join(r['streams'])[:38]:38} | {r['cv']}")
