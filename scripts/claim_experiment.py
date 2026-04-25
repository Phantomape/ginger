"""Claim an experiment ticket and check active conflicts."""

from experiment_registry import (
    add_common_registry_arg,
    claim_ticket,
    load_registry,
    print_json,
    save_registry,
)


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    add_common_registry_arg(parser)
    parser.add_argument("experiment_id")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    ticket, conflicts = claim_ticket(
        registry,
        args.experiment_id,
        args.owner,
        force=args.force,
    )
    if conflicts:
        print_json({"claimed": False, "ticket": ticket, "conflicts": conflicts})
        sys.exit(2)
    save_registry(registry, args.registry)
    print_json({"claimed": True, "ticket": ticket, "conflicts": []})


if __name__ == "__main__":
    main()
