"""Judge before/after backtest JSON files and optionally update a ticket."""

from experiment_registry import (
    add_common_registry_arg,
    build_log_draft,
    DEFAULT_LOG,
    get_experiment,
    judge_results,
    print_json,
    rebuild_registry_from_tickets,
    save_experiment_log_entry,
    update_result_decontended,
)


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    add_common_registry_arg(parser)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument(
        "--write-registry",
        action="store_true",
        help="Persist the accepted/rejected result to the registry.",
    )
    parser.add_argument(
        "--status-override",
        choices=["accepted", "rejected", "observed_only"],
        help="Override the gate decision for measurement or analysis-only tickets.",
    )
    parser.add_argument(
        "--change-summary",
        help="Change summary to put in the experiment log draft.",
    )
    parser.add_argument(
        "--notes",
        help="Notes to put in the experiment log draft.",
    )
    parser.add_argument(
        "--log-draft",
        action="store_true",
        help="Emit an experiment_log.jsonl-compatible draft row.",
    )
    parser.add_argument(
        "--append-log",
        action="store_true",
        help="Write the generated log row to experiments/logs/<experiment_id>.json.",
    )
    parser.add_argument(
        "--log-path",
        default=str(DEFAULT_LOG),
        help="Legacy JSONL path kept for compatibility; not used by --append-log.",
    )
    parser.add_argument(
        "--allow-duplicate-log-id",
        action="store_true",
        help="Allow appending a duplicate experiment_id to the log.",
    )
    parser.add_argument(
        "--realized-failure-mode",
        help="Optional normalized failure mode to compare with the pre-run prediction.",
    )
    parser.add_argument(
        "--surprise-note",
        help="Optional short note explaining what was surprising about the result.",
    )
    parser.add_argument(
        "--allow-missing-prediction",
        action="store_true",
        help=(
            "Legacy escape hatch: allow closing an alpha/scout ticket without "
            "pre-run prediction metadata. New alpha tickets should not need this."
        ),
    )
    args = parser.parse_args()

    # Tickets are authoritative; read from them so a best-effort-stale registry
    # cache can't make a freshly-reserved id look unknown at close time.
    registry_snapshot = rebuild_registry_from_tickets(args.registry)
    experiment = get_experiment(registry_snapshot, args.experiment_id)
    if not experiment:
        raise SystemExit(f"unknown experiment_id: {args.experiment_id}")

    judgement = judge_results(args.before, args.after)
    if args.write_registry:
        # registry-decontention step 2: per-id ticket lock, no global registry lock.
        experiment = update_result_decontended(
            args.registry,
            args.experiment_id,
            judgement,
            args.before,
            args.after,
            status_override=args.status_override,
            realized_failure_mode=args.realized_failure_mode,
            surprise_note=args.surprise_note,
            allow_missing_prediction=args.allow_missing_prediction,
            timeout_seconds=args.lock_timeout_seconds,
        )

    if args.log_draft or args.append_log:
        draft = build_log_draft(
            experiment,
            judgement,
            args.before,
            args.after,
            status_override=args.status_override,
            change_summary=args.change_summary,
            notes=args.notes,
            realized_failure_mode=args.realized_failure_mode,
            surprise_note=args.surprise_note,
            allow_missing_prediction=args.allow_missing_prediction,
        )
        if args.append_log:
            save_experiment_log_entry(
                draft,
                allow_duplicate=args.allow_duplicate_log_id,
                timeout_seconds=args.lock_timeout_seconds,
            )
        print_json(draft)
    else:
        print_json(judgement)


if __name__ == "__main__":
    main()
