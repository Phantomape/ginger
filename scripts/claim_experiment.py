"""Claim an experiment ticket and check active conflicts."""

from experiment_registry import (
    add_common_registry_arg,
    claim_experiment_decontended,
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

    # registry-decontention step 2: per-id ticket lock, no global registry lock.
    ticket, conflicts = claim_experiment_decontended(
        args.registry,
        args.experiment_id,
        args.owner,
        force=args.force,
        timeout_seconds=args.lock_timeout_seconds,
    )
    if conflicts:
        print_json({"claimed": False, "ticket": ticket, "conflicts": conflicts})
        sys.exit(2)
    print_json({"claimed": True, "ticket": ticket, "conflicts": []})


if __name__ == "__main__":
    main()
