#!/usr/bin/env python3
"""Validate Investment Team research cards and project testable leads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.alpha_search_contract import ContractValidationError  # noqa: E402
from quant.data_paths import atomic_write_json  # noqa: E402
from quant.investment_team_research_card import (  # noqa: E402
    normalise_research_card,
    project_hypothesis_candidate,
    research_card_semantic_hash,
    validate_research_card,
)


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _emit(value: Any, output: str | None) -> None:
    if output:
        atomic_write_json(value, Path(output), indent=2, ensure_ascii=False)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed bridge from Investment Team research to D0-D3 inputs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("normalise", "Compute card/candidate IDs and write a canonical card."),
        ("validate", "Validate an already-normalised card."),
        ("project", "Project a valid test card to a HypothesisCandidate."),
    ):
        child = subparsers.add_parser(command, help=help_text)
        child.add_argument("input", help="Input research-card JSON path.")
        child.add_argument("--output", help="Optional output JSON path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        raw = _load(args.input)
        if args.command == "normalise":
            result = normalise_research_card(raw)
        elif args.command == "validate":
            card = validate_research_card(raw)
            candidate = card["decision"]["candidate"]
            result = {
                "valid": True,
                "card_id": card["card_id"],
                "card_hash": research_card_semantic_hash(card),
                "disposition": card["decision"]["disposition"],
                "candidate_id": None if candidate is None else candidate["candidate_id"],
                "next_machine_action": card["decision"]["next_machine_action"],
            }
        else:
            result = project_hypothesis_candidate(raw)
        _emit(result, args.output)
        return 0
    except (OSError, json.JSONDecodeError, ContractValidationError) as exc:
        if isinstance(exc, ContractValidationError):
            payload = exc.to_dict()
        else:
            payload = {"code": "input_error", "path": args.input, "message": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
