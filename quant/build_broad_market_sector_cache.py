"""One-shot builder for the broad-market sector cache.

Reads the warehouse `ticker_universe` (hygiene_pass=1, all_windows_full_liquid=1)
from `data/experiments/exp-20260519-030/warehouse_main.sqlite`, then calls
yfinance for each ticker via `broad_market_sector_map.build_cache`. The cache
lives at `data/reference/broad_market_sector_map.json`.

Safe to re-run: existing entries are skipped by default. Pass `--refresh`
to force a refetch for all listed tickers.

No JavaScript is used.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from broad_market_sector_map import (  # noqa: E402
    DEFAULT_CACHE_PATH,
    build_cache,
    coverage_report,
    load_cache,
)
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH  # noqa: E402


WAREHOUSE_SQLITE = DEFAULT_WAREHOUSE_PATH


def _warehouse_tickers() -> list[str]:
    if not WAREHOUSE_SQLITE.exists():
        raise RuntimeError(f"Missing warehouse: {WAREHOUSE_SQLITE}")
    with sqlite3.connect(WAREHOUSE_SQLITE) as con:
        rows = con.execute(
            """
            select u.ticker
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1 and c.all_windows_full_liquid = 1
            order by u.ticker
            """
        ).fetchall()
    return [str(row[0]).upper() for row in rows]


def _format_progress(idx: int, total: int, ticker: str, entry: dict) -> None:
    sector = entry.get("sector") or "-"
    status = entry.get("status") or "?"
    if idx == 1 or idx % 50 == 0 or idx == total:
        print(f"[{idx}/{total}] {ticker:8s} status={status:14s} sector={sector}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch all tickers")
    parser.add_argument(
        "--cache-path",
        default=str(DEFAULT_CACHE_PATH),
        help=f"Cache JSON path (default: {DEFAULT_CACHE_PATH})",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=25,
        help="Persist cache every N tickers (default: 25)",
    )
    args = parser.parse_args()

    tickers = _warehouse_tickers()
    print(f"warehouse tickers: {len(tickers)}")
    cache_path = Path(args.cache_path)
    pre = load_cache(cache_path)
    pre_count = len(pre.get("entries") or {})
    print(
        f"cache before: path={cache_path} entries={pre_count} "
        f"generated_at={pre.get('generated_at')}"
    )
    payload = build_cache(
        tickers,
        path=cache_path,
        skip_existing=not args.refresh,
        save_every=args.save_every,
        on_progress=_format_progress,
    )
    post_count = len(payload.get("entries") or {})
    report = coverage_report(tickers, cache=payload, path=cache_path)
    print(
        f"cache after: entries={post_count} "
        f"ok_share={report['ok_share']} sector_unique={report['sector_unique_count']}"
    )
    print(f"status_counts: {report['status_counts']}")
    print(f"top sectors: {dict(list(report['sector_counts'].items())[:8])}")
    if report["unresolved_sample"]:
        print(
            f"unresolved sample (up to 25): {report['unresolved_sample'][:25]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
