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
import os
import subprocess
import sys
from pathlib import Path

from experiment_registry import (
    add_common_registry_arg,
    audit_experiment_process,
    load_registry,
    print_json,
)
from alpha_playbook_guard import audit_repository_contract as _audit_alpha_playbook
from self_registration_guard import new_offenders as _self_register_new_offenders


def _workspace_root_for_registry(registry_path):
    path = Path(registry_path)
    return path.parent.parent if path.parent.name == "docs" else path.parent


def _sweep_stale_artifacts_quietly():
    """Best-effort: clear abandoned .tmp/.lock residue from hard-killed concurrent
    ops before running an experiment command. Never raises -- a sweep failure must
    not block lifecycle work."""
    try:
        import importlib.util

        sweep_path = Path(__file__).resolve().parents[1] / "quant" / "stale_artifact_sweep.py"
        spec = importlib.util.spec_from_file_location("stale_artifact_sweep", sweep_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.sweep_quietly()
    except Exception:
        pass


def _refresh_derived_memory_quietly():
    """Best-effort: after an experiment closes, rebuild the derived memory and
    judgment surfaces so the next agent and the novelty gate read current state.

    These surfaces are pure functions of the committed experiment logs, so they
    silently drift every time a close adds a record without a rebuild:
      - ``docs/frozen_families.jsonl``  -- novelty-gate data source; a stale copy
        makes the gate blind to recently-tried families and lets near-duplicate
        alpha experiments slip through.
      - ``docs/alpha_context_pack.md`` / ``docs/current_state_snapshot.md`` /
        ``docs/lessons/*.md`` -- the short-memory entrypoints agents read first.

    Never raises and never blocks the close: the judgment is already written by
    the time this runs. Set ``GINGER_SKIP_MEMORY_REFRESH=1`` to skip the rebuild
    when closing many experiments in a batch (rebuild once at the end instead).
    """
    if os.environ.get("GINGER_SKIP_MEMORY_REFRESH"):
        return
    scripts_dir = Path(__file__).resolve().parent
    for script in ("build_frozen_families.py", "build_alpha_memory.py"):
        try:
            proc = subprocess.run(
                [sys.executable, "-B", str(scripts_dir / script)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode != 0:
                tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
                print(
                    f"[experiment.py] derived-memory refresh: {script} exited "
                    f"{proc.returncode}; run it manually. " + " | ".join(tail),
                    file=sys.stderr,
                )
        except Exception as exc:  # never block the close on a refresh failure
            print(
                f"[experiment.py] derived-memory refresh skipped ({script}): {exc}",
                file=sys.stderr,
            )


def _run_delegate(program, argv, main_func, *main_args):
    original_argv = sys.argv[:]
    sys.argv = [program, *argv]
    try:
        return main_func(*main_args)
    finally:
        sys.argv = original_argv


def _summarize_lean_audit(result, *, lean_strict):
    """Lead with the actionable lean verdict; collapse non-blocking legacy debt.

    The full audit result interleaves legacy pre-enforcement gaps (reported only,
    never blocking per AGENTS.md) with the small set of post-enforcement items
    that actually matter, and exposes a top-level ``passed`` that can be false
    purely from historical debt. Running ``--lean``/``--lean-strict`` should not
    look like a failure when the lean gate is green, so this view shows only what
    a lean experiment is expected to act on.
    """
    def _ids(rows, limit=8):
        out = []
        for row in rows:
            if isinstance(row, dict):
                out.append(
                    row.get("experiment_id")
                    or row.get("canonical_experiment_id")
                )
            else:
                out.append(row)
        return out[:limit]

    sources = {
        # These two drive lean_quality_passed (i.e., they BLOCK --lean-strict).
        "weak_prediction_quality": result.get(
            "post_enforcement_weak_prediction_quality_examples", []
        ),
        "weak_reflection": result.get(
            "closed_post_enforcement_weak_reflection_examples", []
        ),
        # These are post-enforcement but reported-only for --lean-strict; mostly
        # already-closed tickets, so treat as visibility, not a blocker.
        "missing_prediction": result.get(
            "post_enforcement_missing_prediction_examples", []
        ),
        "missing_calibration": result.get(
            "closed_post_enforcement_missing_calibration_examples", []
        ),
    }
    quality_failure_domains = [
        key
        for key in ("weak_prediction_quality", "weak_reflection")
        if sources[key]
    ]
    playbook_contract = result.get(
        "alpha_playbook_contract", {"passed": True, "violations": []}
    )
    hard_integrity_sources = {
        "alpha_promotion_integrity": {
            "count": result.get(
                "post_hard_integrity_alpha_promotion_violation_count", 0
            ),
            "rows": result.get(
                "post_hard_integrity_alpha_promotion_violation_examples", []
            ),
        },
        "research_closeout_integrity": {
            "count": result.get(
                "post_enforcement_research_result_ceiling_violation_count", 0
            ),
            "rows": result.get(
                "post_enforcement_research_result_ceiling_violation_examples", []
            ),
        },
        "canonical_record_integrity": {
            "count": result.get("canonical_record_violation_count", 0),
            "rows": result.get("canonical_record_violation_examples", []),
        },
    }
    failure_domains = list(quality_failure_domains)
    failure_domains.extend(
        key for key, detail in hard_integrity_sources.items() if detail["count"]
    )
    if not playbook_contract.get("passed", False):
        failure_domains.append("alpha_playbook_contract")
    blocking = bool(failure_domains)
    actionable = {
        key: {"count": len(rows), "example_ids": _ids(rows)}
        for key, rows in sources.items()
        if rows
    }
    return {
        "view": "lean_summary",
        "lean_quality_passed": result.get("lean_quality_passed"),
        "hard_integrity_passed": result.get("hard_integrity_passed"),
        "lean_strict_passed": result.get("lean_strict_passed"),
        "lean_strict_would_block": bool(lean_strict and blocking),
        "blocks_lean_strict": [
            "weak_prediction_quality",
            "weak_reflection",
            "alpha_promotion_integrity",
            "research_closeout_integrity",
            "canonical_record_integrity",
            "alpha_playbook_contract",
        ],
        "lean_strict_failure_domains": failure_domains,
        "alpha_playbook_contract": playbook_contract,
        "post_enforcement_alpha_ticket_count": result.get(
            "post_enforcement_alpha_ticket_count"
        ),
        "post_enforcement_gaps": actionable,
        "hard_integrity_violations": {
            key: {"count": detail["count"], "example_ids": _ids(detail["rows"])}
            for key, detail in hard_integrity_sources.items()
            if detail["count"]
        },
        "legacy_closeout_debt": {
            "alpha_promotion_integrity": result.get(
                "legacy_hard_integrity_alpha_promotion_violation_count", 0
            ),
            "research_closeout_integrity": result.get(
                "legacy_research_result_ceiling_violation_count", 0
            ),
            "canonical_record_integrity": result.get(
                "legacy_canonical_record_violation_count", 0
            ),
            "orphan_logs": result.get("legacy_orphan_log_count", 0),
        },
        "legacy_pre_enforcement_alpha_ticket_count": result.get(
            "legacy_pre_enforcement_alpha_ticket_count"
        ),
        "note": (
            "lean_quality_passed remains the experiment prediction/reflection "
            "sub-verdict. lean_strict_passed is the end-of-turn gate and also "
            "requires post-enforcement hard closeout integrity and the alpha "
            "playbook contract. Historical closeout debt stays report-only. "
            "missing_prediction/"
            "missing_calibration are mostly already-closed tickets shown for "
            "visibility (counts capped at 25 in the report). Legacy pre-enforcement "
            "gaps are never backfilled (AGENTS.md). Run `experiment.py audit "
            "--lean --full` for the complete report."
        ),
    }


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
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "With --lean/--lean-strict, print the complete audit result instead "
            "of the lean summary (includes the legacy historical-debt lists and "
            "the top-level `passed` flag)."
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
        file_backed_registry=True,
    )
    sr_new = _self_register_new_offenders()
    result["self_registration"] = {
        "passed": not sr_new,
        "new_offenders": sr_new,
        "note": (
            "Runners writing docs/experiment_registry.json directly bypass "
            "prediction enforcement. Use experiment.py new/close or "
            "experiment_registry.persist_self_registered_result(). --strict blocks "
            "on new offenders; the pre-commit hook blocks the offending commit; "
            "--lean-strict reports them without failing the shared audit."
        ),
    }
    playbook_contract = _audit_alpha_playbook()
    result["alpha_playbook_contract"] = playbook_contract
    result["repository_contracts_passed"] = bool(playbook_contract["passed"])
    if args.lean or args.lean_strict:
        result["hard_integrity_passed"] = bool(
            not result.get(
                "post_hard_integrity_alpha_promotion_violation_count"
            )
            and not result.get(
                "post_enforcement_research_result_ceiling_violation_count"
            )
            and not result.get("canonical_record_violation_count")
        )
        result["lean_strict_passed"] = bool(
            result["lean_quality_passed"]
            and result["hard_integrity_passed"]
            and playbook_contract["passed"]
        )
    if (args.lean or args.lean_strict) and not args.full:
        summary = _summarize_lean_audit(result, lean_strict=args.lean_strict)
        summary["self_registration"] = result["self_registration"]
        print_json(summary)
    else:
        print_json(result)
    if args.lean_strict and not result["lean_strict_passed"]:
        raise SystemExit(2)
    if args.strict and (
        not result["passed"] or sr_new or not playbook_contract["passed"]
    ):
        raise SystemExit(2)


def main():
    commands = {"new", "reserve", "claim", "close", "audit", "rebuild-log"}
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

    _sweep_stale_artifacts_quietly()

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

        result = _run_delegate("experiment.py close", remainder, judge_main)
        _refresh_derived_memory_quietly()
        return result
    if command == "audit":
        return _audit(remainder)
    if command == "rebuild-log":
        from experiment_registry import rebuild_experiment_log_from_shards

        n = rebuild_experiment_log_from_shards()
        print(f"rebuilt docs/experiment_log.jsonl from {n} shard(s)")
        return


if __name__ == "__main__":
    main()
