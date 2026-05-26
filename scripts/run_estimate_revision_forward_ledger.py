"""Build a default-off forward estimate revision ledger from earnings snapshots."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from estimate_revision_ledger import (  # noqa: E402
    persist_estimate_revision_ledger,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data", help="Directory containing organized or legacy earnings snapshots.")
    parser.add_argument("--output-dir", default="data/non_ohlcv", help="Directory for ledger JSONL and summary output.")
    parser.add_argument("--as-of", required=True, help="Snapshot date to ledger, YYYY-MM-DD.")
    parser.add_argument("--start", help="Optional earliest snapshot date to load, YYYY-MM-DD.")
    parser.add_argument(
        "--signal-data-dir",
        help="Directory containing organized or legacy quant/trend signal snapshots. Defaults to --data-dir.",
    )
    parser.add_argument(
        "--skip-signal-match",
        action="store_true",
        help="Do not attach same-day candidate/signal touch fields.",
    )
    args = parser.parse_args()

    summary = persist_estimate_revision_ledger(
        as_of=args.as_of,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        start=args.start,
        generated_at=datetime.now(timezone.utc),
        run_adapter_changed=False,
        signal_data_dir=args.signal_data_dir,
        match_daily_signals=not args.skip_signal_match,
    )
    print(f"wrote {summary['row_count']} rows to {summary['ledger_path']}")
    print(f"summary: {summary['summary_path']}")


if __name__ == "__main__":
    main()
