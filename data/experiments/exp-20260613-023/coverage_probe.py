# Coverage probe: actual distinct-ticker breadth + freshness per production
# stream, to distinguish broad-universe accumulation from narrow/frozen. RO.
import json
import os
import sqlite3
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data"
TODAY = date(2026, 6, 13)
NOW = time.mktime(TODAY.timetuple()) + 12 * 3600
out = {}


def days_since_mtime(p: Path):
    return round((NOW - p.stat().st_mtime) / 86400, 1)


def newest(d: Path, pat="*"):
    fs = sorted(d.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
    return fs[0] if fs else None


def count_lines_tickers(p: Path, key_candidates=("ticker", "symbol", "Ticker")):
    tk = set()
    n = 0
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                o = json.loads(line)
            except Exception:
                continue
            for k in key_candidates:
                if isinstance(o, dict) and o.get(k):
                    tk.add(o[k])
                    break
    return n, len(tk)


# 1. OHLCV warehouse freshness distribution
try:
    import sys
    sys.path.insert(0, str(REPO))
    from quant.ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH
    wpath = Path(DEFAULT_WAREHOUSE_PATH)
except Exception as e:
    wpath = DATA / "warehouse" / "warehouse_main.sqlite"
if wpath.exists():
    con = sqlite3.connect(str(wpath))
    cur = con.cursor()
    tbl = cur.execute("select name from sqlite_master where type='table'").fetchall()
    # find ohlcv table & date column
    rows = cur.execute(
        "select ticker, max(date) m from ohlcv group by ticker"
    ).fetchall() if any("ohlcv" == t[0] for t in tbl) else []
    dist = Counter(r[1] for r in rows)
    top = sorted(dist.items(), key=lambda x: x[0], reverse=True)[:6]
    out["warehouse"] = {"path": str(wpath.relative_to(REPO)), "tickers": len(rows),
                        "max_date_dist_top": top, "tables": [t[0] for t in tbl]}
    con.close()
else:
    out["warehouse"] = {"missing": str(wpath)}

# 2. earnings snapshot breadth
es = newest(DATA / "daily/snapshots/earnings", "earnings_snapshot_*.json")
if es:
    o = json.loads(es.read_text(encoding="utf-8"))
    n = len(o) if isinstance(o, list) else len(o.get("entries", o) if isinstance(o, dict) else [])
    keys = list(o.keys())[:5] if isinstance(o, dict) else None
    out["earnings_snapshot"] = {"file": es.name, "type": type(o).__name__,
                                "len": n, "dict_keys_sample": keys}

# 3. kova streams breadth
kov = {}
for sub, pat in [("fundamentals", "companyfacts_growth_*.jsonl"),
                 ("institutional", "sec13f_ownership_*.jsonl"),
                 ("rs_proxy", "rs_proxy_*.jsonl"),
                 ("intraday", "intraday_ohlcv_*.jsonl")]:
    p = newest(DATA / "kova" / sub, pat)
    if p:
        n, t = count_lines_tickers(p)
        kov[sub] = {"file": p.name, "rows": n, "tickers": t}
out["kova"] = kov

# 4. companyfacts cache freshness (undated, by mtime)
cf = DATA / "cache/sec/companyfacts"
if cf.exists():
    fs = list(cf.glob("*.json"))
    ages = [days_since_mtime(p) for p in fs]
    buckets = Counter()
    for a in ages:
        b = "<=3d" if a <= 3 else ("<=10d" if a <= 10 else ("<=40d" if a <= 40 else ">40d"))
        buckets[b] += 1
    out["companyfacts_cache"] = {"files": len(fs), "age_buckets": dict(buckets)}

# 5. options cache freshness
opt = DATA / "cache/options/onclickmedia"
if opt.exists():
    fs = list(opt.glob("*.json"))
    ages = [days_since_mtime(p) for p in fs]
    buckets = Counter()
    for a in ages:
        b = "<=3d" if a <= 3 else ("<=10d" if a <= 10 else ("<=40d" if a <= 40 else ">40d"))
        buckets[b] += 1
    out["options_cache"] = {"files": len(fs), "age_buckets": dict(buckets)}

# 6. FINRA short interest rows
fr = DATA / "non_ohlcv/finra_short_interest/rows.json"
if fr.exists():
    o = json.loads(fr.read_text(encoding="utf-8"))
    recs = o if isinstance(o, list) else o.get("rows", [])
    sett = sorted({r.get("settlementDate") or r.get("settlement_date") for r in recs if isinstance(r, dict)}, key=lambda x: x or "")
    tk = {r.get("symbol") or r.get("ticker") for r in recs if isinstance(r, dict)}
    out["finra"] = {"file_mtime_days": days_since_mtime(fr), "rows": len(recs),
                    "tickers": len(tk), "settlement_max": sett[-3:] if sett else None}

# 7. 13F institutional cache
i13 = DATA / "non_ohlcv/sec13f_institutional"
if i13.exists():
    fs = list(i13.rglob("*"))
    files = [p for p in fs if p.is_file()]
    out["sec13f"] = {"files": len(files),
                     "newest_mtime_days": min((days_since_mtime(p) for p in files), default=None)}

# 8. news breadth
nc = newest(DATA / "daily/news/clean", "clean_news_*.json")
if nc:
    o = json.loads(nc.read_text(encoding="utf-8"))
    recs = o if isinstance(o, list) else o.get("articles", o.get("news", []))
    out["news_clean"] = {"file": nc.name, "records": len(recs) if hasattr(recs, "__len__") else None}

print(json.dumps(out, indent=1, default=str))
