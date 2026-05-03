"""Build replayable event-shock snapshots from existing daily archives."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from event_shocks import build_event_snapshot
from data_layer import get_universe


logger = logging.getLogger(__name__)


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def backfill_event_shocks(start: str, end: str, *, data_dir: str | None = None) -> list[Path]:
    universe = get_universe()
    data_root = Path(data_dir) if data_dir else None
    written = []
    for ts in pd.bdate_range(start=start, end=end):
        date_key = ts.strftime("%Y%m%d")
        payload = build_event_snapshot(
            date_key,
            data_dir=data_root,
            universe=universe,
            persist=True,
        )
        if payload.get("coverage", {}).get("event_rows_total", 0) > 0:
            path = (data_root or Path(__file__).resolve().parents[1] / "data") / f"event_snapshot_{date_key}.json"
            written.append(path)
            logger.info(
                "event snapshot %s rows=%s earnings=%s sec=%s",
                date_key,
                payload["coverage"]["event_rows_total"],
                payload["coverage"]["tickers_with_dte0_event"],
                payload["coverage"]["sec_items_mapped_to_ticker"],
            )
    return written


def main() -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(description="Backfill replayable event-shock snapshots.")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()
    written = backfill_event_shocks(args.start, args.end, data_dir=args.data_dir)
    logger.info("event snapshot backfill complete: %d files with event rows", len(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
