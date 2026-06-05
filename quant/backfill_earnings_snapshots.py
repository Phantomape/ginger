"""Backfill historical earnings snapshots for P-ERN replay."""

import argparse
import logging
from datetime import datetime

import pandas as pd
import yfinance as yf

from data_layer import get_earnings_data, get_universe
from data_paths import daily_artifact_path
from earnings_assets import empty_earnings_data, is_non_earnings_asset
from earnings_snapshot import persist_earnings_snapshot
from yfinance_bootstrap import configure_yfinance_runtime


logger = logging.getLogger(__name__)


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _iter_trading_days(start, end):
    return [ts.date() for ts in pd.bdate_range(start=start, end=end)]


def backfill_earnings_snapshots(start, end, universe=None, data_dir=None):
    """Write one earnings_snapshot_YYYYMMDD.json per trading day in [start, end]."""
    configure_yfinance_runtime()
    universe = universe or get_universe()
    data_dir = data_dir or str(daily_artifact_path("earnings_snapshot", "YYYYMMDD").parent)
    trading_days = _iter_trading_days(start, end)

    logger.info(
        "Backfilling earnings snapshots: %s -> %s (%d trading days, %d tickers)",
        start,
        end,
        len(trading_days),
        len(universe),
    )

    prefetched = {}
    skipped_non_earnings = []
    for ticker in universe:
        if is_non_earnings_asset(ticker):
            prefetched[ticker] = {"skip_non_earnings_asset": True}
            skipped_non_earnings.append(ticker)
            continue
        ticker_obj = yf.Ticker(ticker)
        try:
            dates_df = ticker_obj.get_earnings_dates(limit=20)
        except Exception as exc:
            logger.debug("%s: get_earnings_dates failed: %s", ticker, exc)
            dates_df = None
        try:
            info = ticker_obj.info
        except Exception as exc:
            logger.debug("%s: info fetch failed: %s", ticker, exc)
            info = None
        try:
            calendar = ticker_obj.calendar
        except Exception as exc:
            logger.debug("%s: calendar fetch failed: %s", ticker, exc)
            calendar = None
        prefetched[ticker] = {
            "ticker_obj": ticker_obj,
            "dates_df": dates_df,
            "info": info,
            "calendar": calendar,
        }
    if skipped_non_earnings:
        logger.info(
            "Skipping earnings prefetch for non-earnings assets: %s",
            ", ".join(sorted(skipped_non_earnings)),
        )

    written = []
    for day in trading_days:
        earnings_by_ticker = {}
        for ticker in universe:
            src = prefetched[ticker]
            if src.get("skip_non_earnings_asset"):
                earnings_by_ticker[ticker] = empty_earnings_data()
                continue
            earnings_by_ticker[ticker] = get_earnings_data(
                ticker,
                as_of=day,
                ticker_obj=src["ticker_obj"],
                dates_df=src["dates_df"],
                info=src["info"],
                calendar=src["calendar"],
            )
        snapshot_path = persist_earnings_snapshot(
            earnings_by_ticker,
            as_of=datetime.combine(day, datetime.min.time()),
            base_dir=data_dir,
            logger=logger,
        )
        written.append(snapshot_path)

    return written


def main():
    _setup_logging()
    parser = argparse.ArgumentParser(
        description="Backfill earnings snapshots for historical replay."
    )
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--data-dir", default=None, help="Override snapshot output directory")
    args = parser.parse_args()

    written = backfill_earnings_snapshots(
        args.start,
        args.end,
        data_dir=args.data_dir,
    )
    logger.info("Backfill complete: %d snapshot files processed", len(written))


if __name__ == "__main__":
    main()
