#!/usr/bin/env python3
"""Validate and persist a semantic intraday decision response."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from data_paths import DATA_ROOT
    from intraday_triage import finalize_decision_payload, persist_final_decision
except ImportError:  # pragma: no cover - package-style imports
    from quant.data_paths import DATA_ROOT
    from quant.intraday_triage import finalize_decision_payload, persist_final_decision


def main(template_path: str | Path, response_path: str | Path,
         output_dir: str | Path | None = None) -> Path:
    template = json.loads(Path(template_path).read_text(encoding="utf-8"))
    response = json.loads(Path(response_path).read_text(encoding="utf-8"))
    finalized = finalize_decision_payload(template, response)
    destination = output_dir or (DATA_ROOT / "daily" / "intraday" / "decisions")
    return persist_final_decision(finalized, destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True)
    parser.add_argument("--response", required=True)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    path = main(args.template, args.response, args.output_dir)
    print(path)
