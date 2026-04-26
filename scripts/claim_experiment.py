"""Claim an experiment ticket and check active conflicts."""

from experiment_registry import (
    add_common_registry_arg,
    claim_ticket,
    locked_registry_update,
    print_json,
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

    ticket, conflicts = locked_registry_update(
        args.registry,
        lambda registry: claim_ticket(
            registry,
            args.experiment_id,
            args.owner,
            force=args.force,
        ),
        timeout_seconds=args.lock_timeout_seconds,
    )
    if conflicts:
        print_json({"claimed": False, "ticket": ticket, "conflicts": conflicts})
        sys.exit(2)
    print_json({"claimed": True, "ticket": ticket, "conflicts": []})


if __name__ == "__main__":
    main()
