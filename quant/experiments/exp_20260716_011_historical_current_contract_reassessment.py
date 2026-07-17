"""Run exp-20260716-011: exhaustive recoverable-history reassessment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.historical_current_contract_reassessment import (
    DEFAULT_BLOCK_LENGTH,
    DEFAULT_BOOTSTRAP_REPLICATES,
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_WAREHOUSE,
    run_reassessment,
)


EXPERIMENT_ID = "exp-20260716-011"
DEFAULT_OUTPUT_DIR = Path("data/experiments") / EXPERIMENT_ID


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--warehouse", default=str(DEFAULT_WAREHOUSE))
    parser.add_argument(
        "--ohlcv-snapshot",
        default=None,
        help="Replay from a previously frozen exact OHLCV rowset.",
    )
    parser.add_argument(
        "--evidence-manifest",
        default=None,
        help="Replay the exact frozen candidate panel and source hashes.",
    )
    parser.add_argument(
        "--evidence-manifest-sha256",
        default=None,
        help="Expected SHA256 of the frozen evidence manifest.",
    )
    parser.add_argument(
        "--ohlcv-snapshot-sha256",
        default=None,
        help="Expected gzip SHA256 of the frozen OHLCV rowset.",
    )
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=DEFAULT_BOOTSTRAP_REPLICATES,
    )
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--block-length", type=int, default=DEFAULT_BLOCK_LENGTH)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_reassessment(
        experiment_id=EXPERIMENT_ID,
        output_dir=args.output_dir,
        warehouse_path=args.warehouse,
        ohlcv_snapshot_path=args.ohlcv_snapshot,
        ohlcv_snapshot_sha256=args.ohlcv_snapshot_sha256,
        evidence_manifest_path=args.evidence_manifest,
        evidence_manifest_sha256=args.evidence_manifest_sha256,
        bootstrap_replicates=args.bootstrap_replicates,
        bootstrap_seed=args.bootstrap_seed,
        block_length=args.block_length,
    )
    compact = {
        "experiment_id": summary["experiment_id"],
        "decision": summary["decision"],
        "accepted_alpha": summary["accepted_alpha"],
        "historical_artifact_summary": summary["historical_artifact_summary"],
        "gate4p_summary": {
            key: summary["gate4p_summary"][key]
            for key in (
                "candidate_count",
                "verdict_counts",
                "formal_positive_ev_and_pnl_count",
                "simultaneous_positive_lower_bound_count",
                "portfolio_forward_watch_count",
            )
        },
        "artifacts": summary["artifacts"],
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
