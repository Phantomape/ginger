"""Incremental OHLCV warehouse refresh for the broad paper universe.

exp-20260612-002: the warehouse only accumulates rows for tickers the daily run
fetches, so the broad universe seeded from snapshots goes stale. This module
keeps a declared refresh universe (sector-cache covered tickers + PEAD broad
universe + reference tickers) current by fetching only the days each ticker is
missing, in chunked bulk vendor calls, and upserting through the existing
warehouse writer with ``update_existing=False`` so deterministic research rows
are never rewritten.

Read-only with ``--dry-run``; no trading rule reads or writes anywhere here.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

try:
    import broad_market_sector_map
    from ohlcv_warehouse import (
        DEFAULT_REFERENCE_TICKERS,
        DEFAULT_WAREHOUSE_PATH,
        connect_overlay_reader,
        hot_path_for,
        upsert_ohlcv_frames,
    )
    from pead_broad_universe_tickers import get_pead_broad_universe_tickers
except ImportError:  # pragma: no cover - package-style imports for tests
    from quant import broad_market_sector_map
    from quant.ohlcv_warehouse import (
        DEFAULT_REFERENCE_TICKERS,
        DEFAULT_WAREHOUSE_PATH,
        connect_overlay_reader,
        hot_path_for,
        upsert_ohlcv_frames,
    )
    from quant.pead_broad_universe_tickers import get_pead_broad_universe_tickers


REFRESH_RULE_VERSION = "broad_universe_warehouse_refresh_v1"
REFRESH_SOURCE_LABEL = "ohlcv_warehouse_refresh:yfinance"
DEFAULT_CHUNK_SIZE = 150
DEFAULT_PAD_DAYS = 5
DEFAULT_MAX_LOOKBACK_DAYS = 420
LOOKBACK_BUCKET_DAYS = (30, 90, 180, DEFAULT_MAX_LOOKBACK_DAYS)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_of_date(as_of: Any = None) -> pd.Timestamp:
    if as_of is None:
        return pd.Timestamp(datetime.now(timezone.utc).date())
    return pd.Timestamp(str(as_of)[:10])


def build_default_refresh_universe() -> list[str]:
    """Sector-cache covered tickers + PEAD broad universe + reference tickers.

    This matches the universe accepted replays were validated on (sector cache
    entries with ok coverage backed by warehouse OHLCV) while keeping the PEAD
    broad consumer and benchmark/reference tickers fresh too.
    """
    tickers: set[str] = set()
    cache = broad_market_sector_map.load_cache()
    entries = cache.get("entries", {}) if isinstance(cache, dict) else {}
    for ticker, meta in entries.items():
        if not isinstance(meta, dict):
            continue
        if not meta.get("sector"):
            continue
        if (meta.get("status") or "ok") != "ok":
            continue
        tickers.add(str(ticker).upper())
    tickers.update(str(t).upper() for t in get_pead_broad_universe_tickers())
    tickers.update(DEFAULT_REFERENCE_TICKERS)
    return sorted(t for t in tickers if t and "." not in t)


def warehouse_last_dates(
    db_path: str | Path,
    tickers: Iterable[str] | None = None,
) -> dict[str, str]:
    """Return ``{ticker: max(date)}`` for the warehouse, optionally restricted."""
    db = Path(db_path)
    # Overlay-aware: the hot tier carries the most recent days, so planning must
    # see them or the refresh would re-fetch days already accumulated in hot.
    if not db.exists() and not hot_path_for(db).exists():
        return {}
    conn = connect_overlay_reader(db)
    try:
        wanted = (
            {str(t).upper().strip() for t in tickers if str(t).strip()}
            if tickers is not None
            else None
        )
        out: dict[str, str] = {}
        for ticker, last in conn.execute(
            "SELECT ticker, MAX(date) FROM ohlcv_overlay GROUP BY ticker"
        ):
            key = str(ticker).upper()
            if wanted is not None and key not in wanted:
                continue
            if last:
                out[key] = str(last)[:10]
        return out
    finally:
        conn.close()


def _lookback_bucket(lookback_days: int, max_lookback_days: int) -> int:
    for bucket in LOOKBACK_BUCKET_DAYS:
        if lookback_days <= bucket:
            return min(bucket, max_lookback_days)
    return max_lookback_days


def _default_fetch_many(tickers: list[str], lookback_days: int) -> dict[str, Any]:
    try:
        from data_layer import get_ohlcv_many
    except ImportError:  # pragma: no cover
        from quant.data_layer import get_ohlcv_many
    return get_ohlcv_many(tickers, lookback_days=lookback_days)


def plan_refresh(
    *,
    db_path: str | Path = DEFAULT_WAREHOUSE_PATH,
    tickers: Iterable[str] | None = None,
    as_of: Any = None,
    pad_days: int = DEFAULT_PAD_DAYS,
    max_lookback_days: int = DEFAULT_MAX_LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Compute which tickers need fetching and at what lookback bucket."""
    universe = sorted(
        {str(t).upper().strip() for t in (tickers or build_default_refresh_universe()) if str(t).strip()}
    )
    as_of_ts = _as_of_date(as_of)
    last_dates = warehouse_last_dates(db_path, universe)
    buckets: dict[int, list[str]] = {}
    fresh: list[str] = []
    for ticker in universe:
        last_text = last_dates.get(ticker)
        if last_text is None:
            lookback = max_lookback_days
        else:
            gap_days = int((as_of_ts - pd.Timestamp(last_text)).days)
            if gap_days <= 0:
                fresh.append(ticker)
                continue
            lookback = gap_days + pad_days
        bucket = _lookback_bucket(lookback, max_lookback_days)
        buckets.setdefault(bucket, []).append(ticker)
    return {
        "as_of": str(as_of_ts.date()),
        "universe_size": len(universe),
        "fresh_count": len(fresh),
        "stale_count": sum(len(group) for group in buckets.values()),
        "buckets": {str(bucket): group for bucket, group in sorted(buckets.items())},
    }


def refresh_warehouse_ohlcv(
    *,
    db_path: str | Path = DEFAULT_WAREHOUSE_PATH,
    tickers: Iterable[str] | None = None,
    as_of: Any = None,
    fetch_many: Callable[[list[str], int], dict[str, Any]] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    pad_days: int = DEFAULT_PAD_DAYS,
    max_lookback_days: int = DEFAULT_MAX_LOOKBACK_DAYS,
    max_tickers: int | None = None,
    dry_run: bool = False,
    logger: Any = None,
) -> dict[str, Any]:
    """Incrementally refresh warehouse OHLCV for the broad universe.

    Existing rows are never rewritten (``update_existing=False``); fetching a
    generous overlap is safe and only missing days insert.
    """
    started = time.monotonic()
    fetcher = fetch_many or _default_fetch_many
    plan = plan_refresh(
        db_path=db_path,
        tickers=tickers,
        as_of=as_of,
        pad_days=pad_days,
        max_lookback_days=max_lookback_days,
    )
    summary: dict[str, Any] = {
        "rule_version": REFRESH_RULE_VERSION,
        "status": "dry_run" if dry_run else "completed",
        "generated_at": _utc_now_iso(),
        "as_of": plan["as_of"],
        "db_path": str(db_path),
        "universe_size": plan["universe_size"],
        "fresh_count": plan["fresh_count"],
        "stale_count": plan["stale_count"],
        "bucket_sizes": {bucket: len(group) for bucket, group in plan["buckets"].items()},
        "fetched_ticker_count": 0,
        "empty_ticker_count": 0,
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "errors": [],
    }
    if dry_run:
        summary["duration_seconds"] = round(time.monotonic() - started, 3)
        return summary

    budget = max_tickers if max_tickers is not None else None
    for bucket_text, group in plan["buckets"].items():
        lookback_days = int(bucket_text)
        remaining = list(group)
        if budget is not None:
            if budget <= 0:
                break
            remaining = remaining[:budget]
            budget -= len(remaining)
        for start in range(0, len(remaining), max(1, chunk_size)):
            chunk = remaining[start : start + max(1, chunk_size)]
            try:
                frames = fetcher(chunk, lookback_days) or {}
            except Exception as fetch_error:
                summary["errors"].append(
                    {"bucket": bucket_text, "tickers": len(chunk), "error": str(fetch_error)}
                )
                continue
            upsert = upsert_ohlcv_frames(
                hot_path_for(db_path),
                frames,
                source=REFRESH_SOURCE_LABEL,
                provider="yfinance",
                update_existing=False,
            )
            fetched = [t for t, frame in frames.items() if frame is not None]
            summary["fetched_ticker_count"] += len(fetched)
            summary["empty_ticker_count"] += len(chunk) - len(fetched)
            for key in ("inserted", "updated", "unchanged"):
                summary[key] += int(upsert.get(key) or 0)
            if logger is not None:
                logger.info(
                    "Warehouse refresh: bucket=%sd chunk=%d fetched=%d inserted=%d",
                    bucket_text,
                    len(chunk),
                    len(fetched),
                    int(upsert.get("inserted") or 0),
                )
    if summary["errors"]:
        summary["status"] = "partial_failed"
    summary["duration_seconds"] = round(time.monotonic() - started, 3)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Incremental broad-universe OHLCV warehouse refresh.")
    parser.add_argument("--db", default=str(DEFAULT_WAREHOUSE_PATH))
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD; defaults to today (UTC).")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--max-tickers", type=int, default=None, help="Cap fetched tickers (testing).")
    parser.add_argument("--dry-run", action="store_true", help="Print the fetch plan without fetching.")
    args = parser.parse_args()
    summary = refresh_warehouse_ohlcv(
        db_path=args.db,
        as_of=args.as_of,
        chunk_size=args.chunk_size,
        max_tickers=args.max_tickers,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
