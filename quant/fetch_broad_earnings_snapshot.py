"""Daily supplemental earnings-snapshot fetch for the PEAD broad universe.

exp-20260607-003: PEAD_BROAD_500_TICKER_EARNINGS_EXPANSION

This script is intended to run AFTER the main run.py has already written
today's earnings snapshot for the core ~44-ticker watchlist.  It fetches
yfinance earnings data for the remaining ~500 broad-universe tickers and
MERGES them into the existing snapshot (additive only -- core tickers are
never overwritten).

Usage (run from repo root, after run.py):
    .\.venv\Scripts\python.exe -B quant\fetch_broad_earnings_snapshot.py

Or via scheduling (after run.py completes):
    .\.venv\Scripts\python.exe -B quant\fetch_broad_earnings_snapshot.py
        --date YYYY-MM-DD
        --batch-size 25
        --batch-sleep-secs 1.5

Rate-limiting design:
- tickers are processed in batches of `batch_size` (default 25)
- After each batch a short sleep (`batch_sleep_secs`, default 1.5s) is added
- Individual ticker failures are caught and logged; they do NOT abort the run
- This keeps total fetch time for 500 tickers roughly under 5 minutes

Production safety:
- trade_enabled: False (this script only writes earnings snapshots)
- Does NOT touch any order, position, or live strategy state
- Does NOT import or modify run.py, backtester.py, or any live sleeve code
- All writes go to data/daily/snapshots/earnings/ (same dir as run.py)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure quant/ is in sys.path when called from repo root or directly
_QUANT_DIR = Path(__file__).resolve().parent
if str(_QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(_QUANT_DIR))

import yfinance as yf

from data_paths import daily_artifact_path
from earnings_assets import empty_earnings_data, is_non_earnings_asset
from earnings_snapshot import merge_earnings_into_snapshot
from pead_broad_universe_tickers import get_pead_broad_universe_tickers
from yfinance_bootstrap import configure_yfinance_runtime

try:
    from data_layer import get_earnings_data
except ImportError:
    get_earnings_data = None


logger = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260607-003"
DEFAULT_BATCH_SIZE = 25
DEFAULT_BATCH_SLEEP_SECS = 1.5


def _setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _prefetch_ticker(ticker: str) -> dict:
    """Fetch yfinance earnings data for a single ticker; return empty on error."""
    try:
        obj = yf.Ticker(ticker)
        try:
            dates_df = obj.get_earnings_dates(limit=20)
        except Exception:
            dates_df = None
        try:
            info = obj.info
        except Exception:
            info = None
        try:
            calendar = obj.calendar
        except Exception:
            calendar = None
        return {
            "ticker_obj": obj,
            "dates_df": dates_df,
            "info": info,
            "calendar": calendar,
        }
    except Exception as exc:
        logger.debug("Prefetch failed for %s: %s", ticker, exc)
        return {}


def fetch_broad_universe_earnings(
    as_of: datetime | None = None,
    *,
    tickers: list[str] | None = None,
    base_dir: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_sleep_secs: float = DEFAULT_BATCH_SLEEP_SECS,
    dry_run: bool = False,
) -> dict:
    """Fetch earnings data for a broad universe of tickers and merge into snapshot.

    When ``tickers`` is provided (e.g. the production broad-market universe feed,
    ~1200 names) it is used directly; otherwise the curated PEAD broad universe
    (~500) is used. Returns a summary dict with fetch statistics.
    """
    configure_yfinance_runtime()
    if as_of is None:
        as_of = datetime.now()
    if base_dir is None:
        base_dir = str(daily_artifact_path("earnings_snapshot", as_of.strftime("%Y%m%d")).parent)

    # Use the caller-supplied universe when given, else the curated PEAD set.
    # Either way merge_earnings_into_snapshot skips tickers already in the
    # snapshot, so core watchlist data is never overwritten.
    if tickers:
        seen: set[str] = set()
        broad_tickers = []
        for raw in tickers:
            sym = str(raw).strip().upper()
            if sym and sym not in seen:
                seen.add(sym)
                broad_tickers.append(sym)
    else:
        broad_tickers = get_pead_broad_universe_tickers()

    logger.info(
        "%s: Fetching broad-universe earnings for %d tickers (as_of=%s, batch=%d, sleep=%.1fs)",
        EXPERIMENT_ID,
        len(broad_tickers),
        as_of.date(),
        batch_size,
        batch_sleep_secs,
    )

    results: dict[str, dict] = {}
    failed: list[str] = []
    skipped_non_earnings: list[str] = []

    # Process in batches with rate-limiting sleep between batches
    for batch_start in range(0, len(broad_tickers), batch_size):
        batch = broad_tickers[batch_start: batch_start + batch_size]
        for ticker in batch:
            if is_non_earnings_asset(ticker):
                results[ticker] = empty_earnings_data()
                skipped_non_earnings.append(ticker)
                continue
            try:
                prefetched = _prefetch_ticker(ticker)
                if not prefetched:
                    results[ticker] = empty_earnings_data()
                    failed.append(ticker)
                    continue

                if get_earnings_data is not None:
                    earnings = get_earnings_data(
                        ticker,
                        as_of=as_of.date(),
                        ticker_obj=prefetched.get("ticker_obj"),
                        dates_df=prefetched.get("dates_df"),
                        info=prefetched.get("info"),
                        calendar=prefetched.get("calendar"),
                    )
                else:
                    # Minimal fallback if data_layer.get_earnings_data unavailable
                    earnings = _minimal_earnings_from_info(prefetched.get("info") or {}, as_of)
                results[ticker] = earnings or empty_earnings_data()
            except Exception as exc:
                logger.debug("Earnings fetch error for %s: %s", ticker, exc)
                results[ticker] = empty_earnings_data()
                failed.append(ticker)

        # Rate-limit: sleep between batches (not after the last one)
        if batch_start + batch_size < len(broad_tickers):
            time.sleep(batch_sleep_secs)

        batch_end = min(batch_start + batch_size, len(broad_tickers))
        logger.info(
            "%s: Fetched batch %d-%d / %d (failed in batch: %d)",
            EXPERIMENT_ID,
            batch_start + 1,
            batch_end,
            len(broad_tickers),
            sum(1 for t in batch if t in failed),
        )

    if skipped_non_earnings:
        logger.info(
            "%s: Skipped %d non-earnings assets: %s",
            EXPERIMENT_ID,
            len(skipped_non_earnings),
            ", ".join(sorted(skipped_non_earnings)[:10]),
        )

    if failed:
        logger.warning(
            "%s: %d tickers had fetch errors (using empty data): %s",
            EXPERIMENT_ID,
            len(failed),
            ", ".join(sorted(failed)[:20]),
        )

    if dry_run:
        eps_covered = sum(
            1 for data in results.values()
            if isinstance(data, dict) and data.get("eps_estimate") is not None
        )
        logger.info(
            "%s: DRY RUN -- would merge %d tickers (%d with EPS estimate) into %s",
            EXPERIMENT_ID,
            len(results),
            eps_covered,
            base_dir,
        )
        return {
            "experiment_id": EXPERIMENT_ID,
            "status": "dry_run",
            "as_of": str(as_of.date()),
            "tickers_fetched": len(results),
            "tickers_failed": len(failed),
            "tickers_skipped_non_earnings": len(skipped_non_earnings),
            "tickers_with_eps_estimate": eps_covered,
        }

    snapshot_path = merge_earnings_into_snapshot(
        results,
        as_of=as_of,
        base_dir=base_dir,
        logger=logger,
    )

    eps_covered = sum(
        1 for data in results.values()
        if isinstance(data, dict) and data.get("eps_estimate") is not None
    )
    surprise_covered = sum(
        1 for data in results.values()
        if isinstance(data, dict) and (
            data.get("avg_historical_surprise_pct") is not None
            or data.get("historical_surprise_pct")
        )
    )

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "status": "merged",
        "as_of": str(as_of.date()),
        "snapshot_path": str(snapshot_path),
        "tickers_fetched": len(results),
        "tickers_failed": len(failed),
        "tickers_failed_list": sorted(failed)[:50],
        "tickers_skipped_non_earnings": len(skipped_non_earnings),
        "tickers_with_eps_estimate": eps_covered,
        "tickers_with_surprise_history": surprise_covered,
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "scope": "pead_broad_universe_earnings_snapshot_expansion",
            "experiment_id": EXPERIMENT_ID,
        },
    }
    logger.info(
        "%s: Merge complete -- tickers=%d failed=%d eps_covered=%d surprise=%d snapshot=%s",
        EXPERIMENT_ID,
        len(results),
        len(failed),
        eps_covered,
        surprise_covered,
        snapshot_path,
    )
    return summary


def _minimal_earnings_from_info(info: dict, as_of: datetime) -> dict:
    """Extract earnings fields directly from yfinance info dict (fallback)."""
    from earnings_snapshot import _normalize_snapshot_row, SNAPSHOT_FIELDS
    raw = {
        "eps_estimate": info.get("forwardEps") or info.get("epsCurrentYear"),
        "eps_actual_last": info.get("trailingEps"),
        "days_to_earnings": None,
        "next_earnings_date": None,
        "historical_surprise_pct": [],
        "avg_historical_surprise_pct": None,
    }
    return _normalize_snapshot_row(raw, as_of)


def main() -> None:
    _setup_logging()
    parser = argparse.ArgumentParser(
        description=(
            f"[{EXPERIMENT_ID}] Fetch broad-universe earnings and merge into daily snapshot. "
            "Run after main run.py to expand PEAD coverage from ~44 to ~500 tickers."
        )
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Target date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Tickers per batch before sleep (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--batch-sleep-secs",
        type=float,
        default=DEFAULT_BATCH_SLEEP_SECS,
        help=f"Seconds to sleep between batches (default: {DEFAULT_BATCH_SLEEP_SECS})",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override snapshot output directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch but do not write snapshot (logging only)",
    )
    args = parser.parse_args()

    if args.date:
        as_of = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        as_of = datetime.now()

    summary = fetch_broad_universe_earnings(
        as_of=as_of,
        base_dir=args.data_dir,
        batch_size=args.batch_size,
        batch_sleep_secs=args.batch_sleep_secs,
        dry_run=args.dry_run,
    )
    logger.info("Summary: %s", summary)


if __name__ == "__main__":
    main()
