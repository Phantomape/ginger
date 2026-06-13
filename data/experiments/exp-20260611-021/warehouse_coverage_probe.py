# exp-20260611-021 observation: warehouse ticker coverage and freshness probe.
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB = REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"

conn = sqlite3.connect(DB)
cur = conn.cursor()
total = cur.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv").fetchone()[0]
maxd = cur.execute("SELECT MAX(date) FROM ohlcv").fetchone()[0]
last_dates = cur.execute(
    "SELECT last, COUNT(*) FROM (SELECT ticker, MAX(date) AS last FROM ohlcv GROUP BY ticker) "
    "GROUP BY last ORDER BY last DESC LIMIT 12"
).fetchall()
fresh = cur.execute(
    "SELECT COUNT(*) FROM (SELECT ticker, MAX(date) AS last FROM ohlcv GROUP BY ticker) "
    "WHERE last >= '2026-06-01'"
).fetchone()[0]
stale = cur.execute(
    "SELECT COUNT(*) FROM (SELECT ticker, MAX(date) AS last FROM ohlcv GROUP BY ticker) "
    "WHERE last < '2026-06-01'"
).fetchone()[0]
out = {
    "distinct_tickers": total,
    "max_date_overall": maxd,
    "tickers_fresh_since_2026_06_01": fresh,
    "tickers_stale_before_2026_06_01": stale,
    "ticker_count_by_last_date_top12": [{"last_date": r[0], "tickers": r[1]} for r in last_dates],
}
print(json.dumps(out, indent=2))
