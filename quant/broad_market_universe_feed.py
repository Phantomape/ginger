"""Generate the authoritative broad-market paper universe feed.

exp-20260612-002: ``load_broad_market_candidate_universe`` has always returned
``status=missing`` in production because nothing ever wrote the maintained
universe file, so daily sleeve runs fell back to the ~27-name governance
observation feed while accepted replays were validated on the sector-cache /
warehouse universe. This module writes that file from the same two sources the
replays used: sector-cache entries with ok coverage, intersected with warehouse
OHLCV that is actually fresh.

Records carry sector/industry/sector_coverage_status so sleeves resolve sector
metadata directly from the feed without any fallback. No liquidity thresholds
are applied here — sleeves enforce their own candidate-level liquidity rules,
and adding feed-level filters would diverge from the replay-validated universe.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import broad_market_sector_map
    from broad_market_paper_sleeve import DEFAULT_UNIVERSE_PATH
    from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH
except ImportError:  # pragma: no cover - package-style imports for tests
    from quant import broad_market_sector_map
    from quant.broad_market_paper_sleeve import DEFAULT_UNIVERSE_PATH
    from quant.ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH


FEED_RULE_VERSION = "warehouse_sector_cache_feed_v1"
DEFAULT_FRESHNESS_DAYS = 7
DEFAULT_MIN_ROWS = 60
COVERAGE_LOOKBACK_DAYS = 420


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_of_date(as_of: Any = None) -> pd.Timestamp:
    if as_of is None:
        return pd.Timestamp(datetime.now(timezone.utc).date())
    return pd.Timestamp(str(as_of)[:10])


def _eligible_sector_entries(sector_entries: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if sector_entries is None:
        cache = broad_market_sector_map.load_cache()
        sector_entries = cache.get("entries", {}) if isinstance(cache, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in (sector_entries or {}).items():
        key = str(ticker).upper().strip()
        if not key or "." in key or "-" in key:
            continue
        if not isinstance(meta, dict):
            continue
        if not meta.get("sector"):
            continue
        if (meta.get("status") or meta.get("sector_coverage_status") or "ok") != "ok":
            continue
        out[key] = meta
    return out


def _warehouse_coverage(
    db_path: str | Path,
    tickers: list[str],
    *,
    as_of: pd.Timestamp,
) -> dict[str, dict[str, Any]]:
    db = Path(db_path)
    if not db.exists() or not tickers:
        return {}
    start_text = str((as_of - pd.Timedelta(days=COVERAGE_LOOKBACK_DAYS)).date())
    end_text = str(as_of.date())
    conn = sqlite3.connect(db)
    try:
        placeholders = ",".join("?" for _ in tickers)
        sql = (
            "SELECT ticker, MAX(date), COUNT(*) FROM ohlcv "
            f"WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ? "
            "GROUP BY ticker"
        )
        out: dict[str, dict[str, Any]] = {}
        for ticker, last, rows in conn.execute(sql, [*tickers, start_text, end_text]):
            out[str(ticker).upper()] = {
                "last_ohlcv_date": str(last)[:10] if last else None,
                "ohlcv_row_count": int(rows or 0),
            }
        return out
    finally:
        conn.close()


def generate_broad_market_paper_universe(
    *,
    db_path: str | Path = DEFAULT_WAREHOUSE_PATH,
    as_of: Any = None,
    freshness_days: int = DEFAULT_FRESHNESS_DAYS,
    min_rows: int = DEFAULT_MIN_ROWS,
    sector_entries: dict[str, Any] | None = None,
    out_path: str | Path = DEFAULT_UNIVERSE_PATH,
    write: bool = True,
) -> dict[str, Any]:
    """Build (and by default persist) the broad-market paper universe feed."""
    as_of_ts = _as_of_date(as_of)
    eligible = _eligible_sector_entries(sector_entries)
    coverage = _warehouse_coverage(db_path, sorted(eligible), as_of=as_of_ts)
    freshness_floor = str((as_of_ts - pd.Timedelta(days=freshness_days)).date())

    records: dict[str, dict[str, Any]] = {}
    excluded = {"missing_ohlcv": 0, "stale_ohlcv": 0, "thin_history": 0}
    for ticker in sorted(eligible):
        info = coverage.get(ticker)
        if not info or not info.get("last_ohlcv_date"):
            excluded["missing_ohlcv"] += 1
            continue
        if info["last_ohlcv_date"] < freshness_floor:
            excluded["stale_ohlcv"] += 1
            continue
        if info["ohlcv_row_count"] < min_rows:
            excluded["thin_history"] += 1
            continue
        meta = eligible[ticker]
        records[ticker] = {
            "ticker": ticker,
            "title": str(meta.get("title") or ""),
            "sector": meta.get("sector"),
            "industry": meta.get("industry"),
            "sector_coverage_status": "ok",
            "last_ohlcv_date": info["last_ohlcv_date"],
            "ohlcv_row_count": info["ohlcv_row_count"],
            "feed_rule_version": FEED_RULE_VERSION,
        }

    payload: dict[str, Any] = {
        "status": "generated",
        "rule_version": FEED_RULE_VERSION,
        "generated_at": _utc_now_iso(),
        "as_of": str(as_of_ts.date()),
        "freshness_days": freshness_days,
        "min_rows": min_rows,
        "source": {
            "warehouse": str(db_path),
            "sector_cache": str(broad_market_sector_map.DEFAULT_CACHE_PATH),
        },
        "eligible_sector_entry_count": len(eligible),
        "excluded_counts": excluded,
        "tickers": sorted(records),
        "records": records,
    }
    if write:
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(target)
        payload["path"] = str(target)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the broad-market paper universe feed.")
    parser.add_argument("--db", default=str(DEFAULT_WAREHOUSE_PATH))
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD; defaults to today (UTC).")
    parser.add_argument("--freshness-days", type=int, default=DEFAULT_FRESHNESS_DAYS)
    parser.add_argument("--min-rows", type=int, default=DEFAULT_MIN_ROWS)
    parser.add_argument("--out", default=str(DEFAULT_UNIVERSE_PATH))
    parser.add_argument("--dry-run", action="store_true", help="Build without writing the file.")
    args = parser.parse_args()
    payload = generate_broad_market_paper_universe(
        db_path=args.db,
        as_of=args.as_of,
        freshness_days=args.freshness_days,
        min_rows=args.min_rows,
        out_path=args.out,
        write=not args.dry_run,
    )
    digest = {key: payload[key] for key in payload if key != "records"}
    digest["ticker_count"] = len(payload["tickers"])
    digest.pop("tickers", None)
    print(json.dumps(digest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
