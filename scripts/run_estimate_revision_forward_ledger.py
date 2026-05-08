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
    build_revision_ledger_rows,
    load_snapshot_records,
    summarize_ledger_rows,
    write_json,
    write_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data", help="Directory containing earnings_snapshot_YYYYMMDD.json files.")
    parser.add_argument("--output-dir", default="data/non_ohlcv", help="Directory for ledger JSONL and summary output.")
    parser.add_argument("--as-of", required=True, help="Snapshot date to ledger, YYYY-MM-DD.")
    parser.add_argument("--start", help="Optional earliest snapshot date to load, YYYY-MM-DD.")
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc)
    records = load_snapshot_records(args.data_dir, start=args.start, end=args.as_of)
    rows = build_revision_ledger_rows(records, as_of=args.as_of, generated_at=generated_at)
    summary = summarize_ledger_rows(rows)
    tag = args.as_of.replace("-", "")

    output_dir = Path(args.output_dir)
    ledger_path = output_dir / f"estimate_revision_ledger_{tag}.jsonl"
    summary_path = output_dir / f"estimate_revision_ledger_summary_{tag}.json"

    summary.update(
        {
            "generated_at": generated_at.isoformat(timespec="seconds"),
            "as_of_date": args.as_of,
            "data_dir": str(Path(args.data_dir)).replace("\\", "/"),
            "ledger_path": str(ledger_path).replace("\\", "/"),
            "summary_path": str(summary_path).replace("\\", "/"),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
                "scope": "default_off_forward_estimate_revision_data_ledger",
            },
        }
    )

    write_jsonl(ledger_path, rows)
    write_json(summary_path, summary)
    print(f"wrote {len(rows)} rows to {ledger_path}")
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
