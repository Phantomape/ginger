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
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import broad_market_sector_map
    from broad_market_paper_sleeve import DEFAULT_UNIVERSE_PATH
    from entry_universe_ledger import (
        append_membership_snapshot,
        build_membership_snapshot,
    )
    from ohlcv_warehouse import (
        DEFAULT_WAREHOUSE_PATH,
        connect_overlay_reader,
        hot_path_for,
    )
except ImportError:  # pragma: no cover - package-style imports for tests
    from quant import broad_market_sector_map
    from quant.broad_market_paper_sleeve import DEFAULT_UNIVERSE_PATH
    from quant.entry_universe_ledger import (
        append_membership_snapshot,
        build_membership_snapshot,
    )
    from quant.ohlcv_warehouse import (
        DEFAULT_WAREHOUSE_PATH,
        connect_overlay_reader,
        hot_path_for,
    )


FEED_RULE_VERSION = "warehouse_sector_cache_feed_v1"
FORWARD_GENERATION = "broad_market_clean_forward_v1"
DEFAULT_CLEAN_CUTOFF = "2026-07-17"
DEFAULT_MEMBERSHIP_LEDGER_PATH = Path(DEFAULT_UNIVERSE_PATH).with_name(
    "universe_membership.jsonl"
)
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
    if (not db.exists() and not hot_path_for(db).exists()) or not tickers:
        return {}
    start_text = str((as_of - pd.Timedelta(days=COVERAGE_LOOKBACK_DAYS)).date())
    end_text = str(as_of.date())
    # Overlay-aware: freshness (MAX(date)) must include the hot tier, else every
    # name reads as stale once daily bars land in hot instead of cold.
    conn = connect_overlay_reader(db)
    try:
        placeholders = ",".join("?" for _ in tickers)
        sql = (
            "SELECT ticker, MAX(date), COUNT(*) FROM ohlcv_overlay "
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
    ledger_path: str | Path = DEFAULT_MEMBERSHIP_LEDGER_PATH,
    clean_cutoff: Any = DEFAULT_CLEAN_CUTOFF,
    forward_generation: str = FORWARD_GENERATION,
    write: bool = True,
) -> dict[str, Any]:
    """Build and, after the declared cutoff, ledger the complete membership.

    ``clean_cutoff`` is deliberately prospective: calls whose ``as_of`` date is
    earlier are labelled but never appended.  ``write=False`` is fully dry-run
    for both the maintained feed and the append-only membership ledger.
    """
    as_of_ts = _as_of_date(as_of)
    as_of_text = str(as_of_ts.date())
    clean_cutoff_text = (
        str(_as_of_date(clean_cutoff).date()) if clean_cutoff is not None else None
    )
    generated_at = _utc_now_iso()
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
        "generated_at": generated_at,
        "as_of": as_of_text,
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

    membership_snapshot = build_membership_snapshot(
        effective_as_of=as_of_text,
        tickers=payload["tickers"],
        source="broad_market_universe_feed",
        clean_cutoff=clean_cutoff_text,
        provenance={
            "generation": forward_generation,
            "feed_rule_version": FEED_RULE_VERSION,
            "freshness_days": int(freshness_days),
            "min_rows": int(min_rows),
            "sector_source": "broad_market_sector_map_cache",
            "warehouse_source": "ohlcv_warehouse_overlay",
        },
        generated_at=generated_at,
    )
    membership_result: dict[str, Any]
    if not write:
        membership_result = {"status": "dry_run_not_persisted"}
    elif clean_cutoff_text is not None and as_of_text < clean_cutoff_text:
        membership_result = {"status": "pre_clean_not_persisted"}
    else:
        membership_result = append_membership_snapshot(
            Path(ledger_path), membership_snapshot
        )

    membership = {
        "effective_as_of": membership_snapshot["effective_as_of"],
        "membership_hash": membership_snapshot["membership_hash"],
        "snapshot_hash": membership_snapshot["snapshot_hash"],
        "ticker_count": membership_snapshot["ticker_count"],
        "snapshot_semantics": membership_snapshot["snapshot_semantics"],
        "clean_cutoff": clean_cutoff_text,
        "forward_generation": forward_generation,
        "ledger_path": str(ledger_path),
        "ledger_status": membership_result.get("status"),
        "ledger_hash": membership_result.get("ledger_hash"),
    }
    payload["membership"] = membership
    # Flat copies keep downstream snapshot attribution simple and preserve the
    # existing feed's records/tickers shape for older consumers.
    payload["membership_hash"] = membership["membership_hash"]
    payload["membership_as_of"] = membership["effective_as_of"]
    payload["membership_snapshot_hash"] = membership["snapshot_hash"]
    payload["membership_ledger_hash"] = membership["ledger_hash"]
    payload["membership_ledger_status"] = membership["ledger_status"]
    payload["clean_cutoff"] = clean_cutoff_text
    payload["forward_generation"] = forward_generation
    if write:
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        _atomic_replace_with_retry(tmp, target)
        payload["path"] = str(target)
    return payload


def _atomic_replace_with_retry(
    tmp: Path, target: Path, *, attempts: int = 6, base_delay: float = 0.25
) -> None:
    """Replace ``target`` with ``tmp``, retrying transient Windows file locks.

    On Windows another process holding a handle to ``target`` (the auto-committer
    / git-LFS / antivirus during a scheduled run) makes the atomic rename raise
    ``PermissionError`` (WinError 5, access denied). The write itself is valid, so
    retry with short backoff instead of aborting the whole universe-feed step.
    """
    last_exc: Exception | None = None
    for i in range(max(1, attempts)):
        try:
            tmp.replace(target)
            return
        except PermissionError as exc:  # WinError 5 / 32 transient lock
            last_exc = exc
            time.sleep(base_delay * (2 ** i))
    # Final attempt: let the exception propagate so the caller logs it.
    if last_exc is not None:
        tmp.replace(target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the broad-market paper universe feed.")
    parser.add_argument("--db", default=str(DEFAULT_WAREHOUSE_PATH))
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD; defaults to today (UTC).")
    parser.add_argument("--freshness-days", type=int, default=DEFAULT_FRESHNESS_DAYS)
    parser.add_argument("--min-rows", type=int, default=DEFAULT_MIN_ROWS)
    parser.add_argument("--out", default=str(DEFAULT_UNIVERSE_PATH))
    parser.add_argument(
        "--membership-ledger", default=str(DEFAULT_MEMBERSHIP_LEDGER_PATH)
    )
    parser.add_argument("--clean-cutoff", default=DEFAULT_CLEAN_CUTOFF)
    parser.add_argument("--dry-run", action="store_true", help="Build without writing the file.")
    args = parser.parse_args()
    payload = generate_broad_market_paper_universe(
        db_path=args.db,
        as_of=args.as_of,
        freshness_days=args.freshness_days,
        min_rows=args.min_rows,
        out_path=args.out,
        ledger_path=args.membership_ledger,
        clean_cutoff=args.clean_cutoff,
        write=not args.dry_run,
    )
    digest = {key: payload[key] for key in payload if key != "records"}
    digest["ticker_count"] = len(payload["tickers"])
    digest.pop("tickers", None)
    print(json.dumps(digest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
