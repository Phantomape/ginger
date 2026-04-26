"""List experiment tickets in the registry."""

from experiment_registry import add_common_registry_arg, iter_experiments, load_registry


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    add_common_registry_arg(parser)
    parser.add_argument("--status")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    experiments = iter_experiments(registry)
    if args.status:
        experiments = [e for e in experiments if e.get("status") == args.status]

    if not experiments:
        print("(no experiments)")
        return

    header = f"{'ID':<18} {'STATUS':<12} {'LANE':<18} {'OWNER':<16} HYPOTHESIS"
    print(header)
    print("-" * len(header))
    for exp in experiments:
        hypothesis = (exp.get("hypothesis") or "").replace("\n", " ")
        if len(hypothesis) > 80:
            hypothesis = hypothesis[:77] + "..."
        print(
            f"{exp.get('experiment_id',''):<18} "
            f"{exp.get('status',''):<12} "
            f"{exp.get('lane',''):<18} "
            f"{str(exp.get('owner') or '-'):<16} "
            f"{hypothesis}"
        )


if __name__ == "__main__":
    main()
