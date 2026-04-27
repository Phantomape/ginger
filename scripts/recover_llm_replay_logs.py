"""Recover replayable LLM advice archives from existing raw llm_output files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from import_advice import normalize_replay_file, recover_advice_from_raw_output  # noqa: E402


def _candidate_raw_files(data_dir: Path, date: str | None):
    if date:
        yield data_dir / f"llm_output_{date}.json"
        return
    yield from sorted(data_dir.glob("llm_output_*.json"))


def _candidate_replay_files(data_dir: Path, date: str | None):
    if date:
        yield data_dir / f"llm_prompt_resp_{date}.json"
        return
    yield from sorted(data_dir.glob("llm_prompt_resp_*.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Recover only YYYYMMDD (or YYYY-MM-DD).")
    parser.add_argument(
        "--data-dir",
        default=str(REPO_ROOT / "data"),
        help="Directory containing llm_output/investment_advice files.",
    )
    parser.add_argument(
        "--normalize-existing-replay",
        action="store_true",
        help="Normalize existing llm_prompt_resp_YYYYMMDD.json archives in place.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    results = []
    if args.normalize_existing_replay:
        for replay_path in _candidate_replay_files(data_dir, args.date):
            if not replay_path.exists():
                continue
            results.append(
                normalize_replay_file(
                    str(replay_path),
                    date_str=args.date,
                    output_dir=str(data_dir),
                )
            )
    else:
        for raw_path in _candidate_raw_files(data_dir, args.date):
            if not raw_path.exists():
                continue
            results.append(
                recover_advice_from_raw_output(
                    str(raw_path),
                    date_str=args.date,
                    output_dir=str(data_dir),
                )
            )

    print(json.dumps({"results": results}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
