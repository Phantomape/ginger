"""Judge before/after backtest JSON files and optionally update a ticket."""

from experiment_registry import (
    add_common_registry_arg,
    append_log_entry,
    build_log_draft,
    DEFAULT_LOG,
    get_experiment,
    judge_results,
    load_registry,
    print_json,
    save_registry,
    update_result,
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
        help="Append the generated log row to docs/experiment_log.jsonl.",
    )
    parser.add_argument(
        "--log-path",
        default=str(DEFAULT_LOG),
        help="Path to experiment_log.jsonl.",
    )
    parser.add_argument(
        "--allow-duplicate-log-id",
        action="store_true",
        help="Allow appending a duplicate experiment_id to the log.",
    )
    args = parser.parse_args()

    registry = load_registry(args.registry)
    experiment = get_experiment(registry, args.experiment_id)
    if not experiment:
        raise SystemExit(f"unknown experiment_id: {args.experiment_id}")

    judgement = judge_results(args.before, args.after)
    if args.write_registry:
        update_result(
            registry,
            args.experiment_id,
            judgement,
            args.before,
            args.after,
            status_override=args.status_override,
        )
        save_registry(registry, args.registry)

    if args.log_draft or args.append_log:
        draft = build_log_draft(
            experiment,
            judgement,
            args.before,
            args.after,
            status_override=args.status_override,
            change_summary=args.change_summary,
            notes=args.notes,
        )
        if args.append_log:
            append_log_entry(
                args.log_path,
                draft,
                allow_duplicate=args.allow_duplicate_log_id,
            )
        print_json(draft)
    else:
        print_json(judgement)


if __name__ == "__main__":
    main()
