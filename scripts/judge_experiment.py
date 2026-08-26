"""Judge before/after backtest JSON files and optionally update a ticket."""

from experiment_registry import (
    add_common_registry_arg,
    build_log_draft,
    DEFAULT_LOG,
    EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD,
    experiment_reservation_identity_required,
    experiment_log_path,
    get_experiment,
    judge_results,
    PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_CONTRACT_VERSION,
    print_json,
    registry_workspace_root,
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
        help=(
            "Legacy-only overwrite escape hatch; forbidden for future private "
            "replay scout canonical logs."
        ),
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

    disposition_contract_version = experiment.get(
        "private_replay_scout_artifact_disposition_contract_version"
    )
    post_rollout_closeout = experiment_reservation_identity_required(experiment)
    if (
        args.allow_duplicate_log_id
        and (
            post_rollout_closeout
            or disposition_contract_version
            == PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_CONTRACT_VERSION
        )
    ):
        parser.error(
            "post-rollout canonical logs are immutable; "
            "--allow-duplicate-log-id is forbidden"
        )
    if (
        args.write_registry
        and (
            post_rollout_closeout
            or disposition_contract_version
            == PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_CONTRACT_VERSION
        )
        and not args.append_log
    ):
        parser.error(
            "post-rollout closeout requires --append-log "
            "with --write-registry"
        )

    workspace_root = registry_workspace_root(args.registry)
    judgement = judge_results(args.before, args.after)
    draft = None
    if args.log_draft or args.append_log:
        # Validate the artifact and construct the complete row before making the
        # ticket terminal. This prevents a draft/root failure from stranding an
        # immutable terminal ticket without its canonical log shard.
        terminal_intent = experiment.get(
            EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD
        )
        terminal_retry = bool(
            post_rollout_closeout
            and experiment.get("status")
            in {"accepted", "rejected", "observed_only"}
            and isinstance(terminal_intent, dict)
        )
        if terminal_retry:
            draft = terminal_intent
        else:
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
                repo_root=workspace_root,
            )
        canonical_log = experiment_log_path(
            args.experiment_id, workspace_root / "experiments" / "logs"
        )
        if (
            args.append_log
            and canonical_log.exists()
            and not args.allow_duplicate_log_id
            and not terminal_retry
        ):
            raise ValueError(f"experiment log already exists: {canonical_log}")

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
            log_draft=draft,
            timeout_seconds=args.lock_timeout_seconds,
        )

    if draft is not None:
        if args.append_log:
            save_experiment_log_entry(
                draft,
                allow_duplicate=args.allow_duplicate_log_id,
                logs_dir=workspace_root / "experiments" / "logs",
                registry_path=args.registry,
                timeout_seconds=args.lock_timeout_seconds,
            )
        print_json(draft)
    else:
        print_json(judgement)


if __name__ == "__main__":
    main()
