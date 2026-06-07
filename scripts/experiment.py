"""Unified Hugging Face-style experiment entrypoint.

Use this as the stable front door:

  python scripts/experiment.py new ...
  python scripts/experiment.py claim exp-... --owner agent-name
  python scripts/experiment.py close ...
  python scripts/experiment.py audit

The older scripts stay available, but this wrapper keeps the operational model
small: create the experiment object first, work under that ID, then close it
through one audited path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from experiment_registry import (
    add_common_registry_arg,
    audit_experiment_process,
    load_registry,
    print_json,
)


def _workspace_root_for_registry(registry_path):
    path = Path(registry_path)
    return path.parent.parent if path.parent.name == "docs" else path.parent


def _run_delegate(program, argv, main_func, *main_args):
    original_argv = sys.argv[:]
    sys.argv = [program, *argv]
    try:
        return main_func(*main_args)
    finally:
        sys.argv = original_argv


def _audit(argv):
    parser = argparse.ArgumentParser(
        description="Audit tickets/logs for missing prediction and calibration metadata."
    )
    add_common_registry_arg(parser)
    parser.add_argument("--tickets-dir")
    parser.add_argument("--logs-dir")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 2 when the audit finds post-enforcement alpha process gaps.",
    )
    parser.add_argument(
        "--lean",
        action="store_true",
        help=(
            "Also audit lean alpha quality: substantive confidence_reason and "
            "post-run reflection, without requiring extra accounting fields."
        ),
    )
    parser.add_argument(
        "--lean-strict",
        action="store_true",
        help=(
            "Exit with status 2 only when post-lean-enforcement quality gaps "
            "exist; implies --lean and does not block on historical metadata debt."
        ),
    )
    args = parser.parse_args(argv)

    workspace_root = _workspace_root_for_registry(args.registry)
    registry = load_registry(args.registry)
    result = audit_experiment_process(
        registry,
        tickets_dir=args.tickets_dir or workspace_root / "experiments" / "tickets",
        logs_dir=args.logs_dir or workspace_root / "experiments" / "logs",
        lean=args.lean or args.lean_strict,
    )
    print_json(result)
    if args.lean_strict and not result["lean_quality_passed"]:
        raise SystemExit(2)
    if args.strict and not result["passed"]:
        raise SystemExit(2)


def main():
    commands = {"new", "reserve", "claim", "close", "audit"}
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "command",
            choices=sorted(commands),
            help="Experiment lifecycle command.",
        )
        parser.print_help()
        return

    command = sys.argv[1]
    remainder = sys.argv[2:]
    if command not in commands:
        raise SystemExit(f"unknown command: {command}")

    if command in {"new", "reserve"}:
        from create_experiment_ticket import main as create_main

        return _run_delegate(
            "experiment.py new",
            remainder,
            create_main,
            "Reserve an experiment object before writing runners, artifacts, data, or logs.",
        )
    if command == "claim":
        from claim_experiment import main as claim_main

        return _run_delegate("experiment.py claim", remainder, claim_main)
    if command == "close":
        from judge_experiment import main as judge_main

        return _run_delegate("experiment.py close", remainder, judge_main)
    if command == "audit":
        return _audit(remainder)


if __name__ == "__main__":
    main()
