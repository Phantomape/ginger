# Data inventory scan: per-directory accumulation analysis.
# For each directory under data/: file count, size, latest mtime, and
# dated-filename families (YYYYMMDD / YYYY-MM-DD) with min/max date, count,
# and staleness vs today. Read-only.
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data"
TODAY = "20260611"

DATE8 = re.compile(r"(20\d{6})")


def family_key(name: str) -> str:
    return DATE8.sub("<D>", name)


rows = []
for directory in sorted({p.parent for p in DATA.rglob("*") if p.is_file()}):
    rel = str(directory.relative_to(REPO_ROOT)).replace("\\", "/")
    if "/experiments/exp-" in rel:
        continue  # experiment artifacts are per-ticket, not production streams
    files = [p for p in directory.iterdir() if p.is_file()]
    if not files:
        continue
    families = defaultdict(list)
    undated = 0
    for p in files:
        m = DATE8.search(p.name)
        valid = None
        if m:
            text = m.group(1)
            try:
                date(int(text[:4]), int(text[4:6]), int(text[6:8]))
                valid = text
            except ValueError:
                valid = None
        if valid:
            families[family_key(p.name)].append(valid)
        else:
            undated += 1
    fam_rows = []
    for fam, dates in sorted(families.items()):
        dates.sort()
        last = dates[-1]
        fam_rows.append(
            {
                "pattern": fam,
                "count": len(dates),
                "first": dates[0],
                "last": last,
                "days_stale": (
                    date(2026, 6, 11) - date(int(last[:4]), int(last[4:6]), int(last[6:8]))
                ).days,
            }
        )
    rows.append(
        {
            "dir": rel,
            "file_count": len(files),
            "size_mb": round(sum(p.stat().st_size for p in files) / 1e6, 1),
            "undated_files": undated,
            "dated_families": fam_rows,
        }
    )

print(json.dumps(rows, indent=1))
