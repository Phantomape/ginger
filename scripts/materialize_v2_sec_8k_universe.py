"""Freeze, materialize, or verify the research-only V2 SEC 8-K universe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.v2_sec_8k_universe import (  # noqa: E402
    freeze_sec_8k_source_bundle,
    publish_sec_8k_materialization,
    validate_persisted_sec_8k_materialization,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    freeze = commands.add_parser(
        "freeze", help="Download and freeze the official SEC source bundle."
    )
    freeze.add_argument("--output-dir", type=Path, required=True)
    freeze.add_argument("--form-date", required=True, help="SEC index date as YYYYMMDD.")
    freeze.add_argument(
        "--user-agent",
        required=True,
        help="Declared SEC User-Agent with application and contact information.",
    )

    for name, help_text in (
        ("materialize", "Append the universe ledger and publish its immutable envelope."),
        ("verify", "Re-read and validate an already-published materialization."),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--source-dir", type=Path, required=True)
        command.add_argument("--ledger-path", type=Path, required=True)
        command.add_argument("--envelope-path", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if args.command == "freeze":
        result = freeze_sec_8k_source_bundle(
            args.output_dir,
            args.form_date,
            args.user_agent,
        )
    elif args.command == "materialize":
        result = publish_sec_8k_materialization(
            args.source_dir,
            args.ledger_path,
            args.envelope_path,
        )
    else:
        result = validate_persisted_sec_8k_materialization(
            args.source_dir,
            args.ledger_path,
            args.envelope_path,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
