"""Judge before/after backtest JSON files and optionally update a ticket."""

from experiment_registry import (
    add_common_registry_arg,
    build_log_draft,
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
        "--log-draft",
        action="store_true",
        help="Emit an experiment_log.jsonl-compatible draft row.",
    )
    args = parser.parse_args()

    registry = load_registry(args.registry)
    experiment = get_experiment(registry, args.experiment_id)
    if not experiment:
        raise SystemExit(f"unknown experiment_id: {args.experiment_id}")

    judgement = judge_results(args.before, args.after)
    if args.write_registry:
        update_result(registry, args.experiment_id, judgement, args.before, args.after)
        save_registry(registry, args.registry)

    if args.log_draft:
        print_json(build_log_draft(experiment, judgement, args.before, args.after))
    else:
        print_json(judgement)


if __name__ == "__main__":
    main()
