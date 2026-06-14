# Fresh data inventory scan dated to today (2026-06-13). Read-only.
# Per production-read data stream: dated-filename family freshness + (for key
# streams) actual distinct-ticker coverage in the latest artifact, so we can
# tell broad-universe accumulation apart from narrow/frozen accumulation.
import json
import re
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data"
TODAY = date(2026, 6, 13)
DATE8 = re.compile(r"(20\d{6})")


def family_key(name: str) -> str:
    return DATE8.sub("<D>", name)


def stale(last: str) -> int:
    return (TODAY - date(int(last[:4]), int(last[4:6]), int(last[6:8]))).days


rows = []
for directory in sorted({p.parent for p in DATA.rglob("*") if p.is_file()}):
    rel = str(directory.relative_to(REPO_ROOT)).replace("\\", "/")
    if "/experiments/exp-" in rel or "/intraday/reports" in rel:
        continue
    files = [p for p in directory.iterdir() if p.is_file()]
    if not files:
        continue
    families = defaultdict(list)
    undated = 0
    for p in files:
        m = DATE8.search(p.name)
        valid = None
        if m:
            t = m.group(1)
            try:
                date(int(t[:4]), int(t[4:6]), int(t[6:8]))
                valid = t
            except ValueError:
                valid = None
        if valid:
            families[family_key(p.name)].append(valid)
        else:
            undated += 1
    fam_rows = []
    for fam, dates in sorted(families.items()):
        dates.sort()
        fam_rows.append(
            {"pattern": fam, "count": len(dates), "first": dates[0],
             "last": dates[-1], "days_stale": stale(dates[-1])}
        )
    rows.append({"dir": rel, "file_count": len(files),
                 "size_mb": round(sum(p.stat().st_size for p in files) / 1e6, 1),
                 "undated_files": undated, "dated_families": fam_rows})

print(json.dumps({"as_of": str(TODAY), "dirs": rows}, indent=1))
