import json
import logging
import os
from datetime import datetime


SNAPSHOT_FIELDS = (
    "days_to_earnings",
    "eps_estimate",
    "eps_actual_last",
    "avg_historical_surprise_pct",
    "historical_surprise_pct",
)


def persist_earnings_snapshot(
    earnings_by_ticker,
    as_of=None,
    base_dir=None,
    logger=None,
):
    """Persist a daily earnings snapshot for later backtest replay."""
    if as_of is None:
        as_of = datetime.now()
    if logger is None:
        logger = logging.getLogger(__name__)
    if base_dir is None:
        base_dir = os.path.join(os.path.dirname(__file__), "..", "data")

    date_str = as_of.strftime("%Y%m%d")
    snapshot_path = os.path.join(base_dir, f"earnings_snapshot_{date_str}.json")
    os.makedirs(os.path.dirname(os.path.abspath(snapshot_path)), exist_ok=True)

    if os.path.exists(snapshot_path):
        logger.info(f"Earnings snapshot already exists: {snapshot_path}")
        return snapshot_path

    snapshot = {
        "date": date_str,
        "timestamp": as_of.isoformat(),
        "earnings": {
            ticker: {
                key: value
                for key, value in (earnings_data or {}).items()
                if key in SNAPSHOT_FIELDS
            }
            for ticker, earnings_data in (earnings_by_ticker or {}).items()
            if earnings_data is not None
        },
    }

    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Earnings snapshot saved: {snapshot_path}")
    return snapshot_path
