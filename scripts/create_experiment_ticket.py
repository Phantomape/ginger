"""Create a proposed multi-agent experiment ticket."""

from experiment_registry import (
    add_common_registry_arg,
    create_ticket,
    load_registry,
    parse_csv,
    parse_windows,
    print_json,
    save_registry,
)


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    add_common_registry_arg(parser)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--change-type", required=True)
    parser.add_argument("--single-causal-variable", required=True)
    parser.add_argument("--baseline-result-file")
    parser.add_argument("--allowed-write-scope", default="")
    parser.add_argument("--must-not-touch", default="")
    parser.add_argument("--locked-variables", default="")
    parser.add_argument(
        "--window",
        action="append",
        default=[],
        help="Evaluation window as START:END. May be repeated.",
    )
    parser.add_argument("--acceptance-rule")
    parser.add_argument("--owner")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    ticket = create_ticket(
        registry,
        lane=args.lane,
        hypothesis=args.hypothesis,
        change_type=args.change_type,
        single_causal_variable=args.single_causal_variable,
        baseline_result_file=args.baseline_result_file,
        allowed_write_scope=parse_csv(args.allowed_write_scope),
        must_not_touch=parse_csv(args.must_not_touch),
        locked_variables=parse_csv(args.locked_variables),
        evaluation_windows=parse_windows(args.window),
        acceptance_rule=args.acceptance_rule,
        owner=args.owner,
    )
    save_registry(registry, args.registry)
    print_json(ticket)


if __name__ == "__main__":
    main()
