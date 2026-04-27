"""Build the exp-20260427-018 LLM ranking-ready replay manifest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.experiments.exp_20260427_014_llm_production_aligned_ranking_manifest import (  # noqa: E501
    build_manifest,
)


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--baseline", default="data/backtest_results_20260426.json")
    parser.add_argument(
        "--output",
        default=(
            "data/experiments/exp-20260427-018/"
            "exp_20260427_018_llm_production_aligned_ranking_manifest_v2.json"
        ),
    )
    parser.add_argument("--start", default="2025-10-23")
    parser.add_argument("--end", default="2026-04-21")
    args = parser.parse_args()

    artifact = build_manifest(
        data_dir=Path(args.data_dir),
        baseline_file=Path(args.baseline),
        start=_parse_date(args.start),
        end=_parse_date(args.end),
    )
    artifact["experiment_id"] = "exp-20260427-018"
    artifact["notes"] = [
        "This is the finalized unique-ticket copy after exp-20260427-014 collided with a pre-existing closeout log.",
        "Strategy behavior is unchanged; the artifact only inventories existing replay archives.",
    ]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(artifact["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
