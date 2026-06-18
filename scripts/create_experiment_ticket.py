"""Create a proposed multi-agent experiment ticket."""

import json
import os
import sys
from pathlib import Path

from experiment_registry import (
    add_common_registry_arg,
    normalize_prediction,
    parse_csv,
    parse_windows,
    print_json,
    reserve_experiment,
)

ALPHA_LANES = {"alpha_search", "alpha_discovery", "universe_scout"}


def _novelty_check(args):
    """Advisory near-neighbor check at reservation time. Fails safe.

    Warn-only by default: prints the fingerprint and nearest frozen/explored
    families to stderr (stdout stays clean JSON). Becomes a soft gate when
    --enforce-novelty or env GINGER_NOVELTY_GATE is set: an alpha-lane
    near-neighbor is blocked unless --novelty-override with --new-evidence-axis
    is supplied. Any import/lookup failure silently skips the check so it can
    never break a reservation.
    """
    try:
        import check_experiment_novelty as cen
        import experiment_fingerprint as efp
    except Exception:
        return None
    try:
        fingerprint = efp.infer_fingerprint(
            args.hypothesis or "",
            args.single_causal_variable or "",
            args.trial_family or "",
            args.mechanism_family or "",
            args.file_slug or "",
        )
        result = cen.check(fingerprint)
    except Exception:
        return None

    enforce = bool(args.enforce_novelty) or os.environ.get(
        "GINGER_NOVELTY_GATE", ""
    ).strip().lower() in {"1", "block", "true", "yes"}
    alpha_lane = args.lane in ALPHA_LANES
    nearest = result.get("nearest") or []

    print(
        "[novelty] fingerprint:"
        f" source={fingerprint['data_source']} gate={fingerprint['gate_shape']}"
        f" tags={','.join(fingerprint['field_tags'][:10])}",
        file=sys.stderr,
    )
    if result.get("warn"):
        print(
            f"[novelty] WARN near-neighbor of a frozen/explored family"
            f" (threshold {result['warn_threshold']}):",
            file=sys.stderr,
        )
        for n in nearest[:3]:
            print(
                f"[novelty]   {n['score']:.3f} [{n['status']}] {n['family_key']}"
                f" (trials={n['trials']}, accept={n['accept_rate']})",
                file=sys.stderr,
            )
    else:
        print("[novelty] ok: no strong near-neighbor.", file=sys.stderr)

    out = {
        "fingerprint": fingerprint,
        "warn": bool(result.get("warn")),
        "warn_threshold": result.get("warn_threshold"),
        "nearest": nearest[:5],
        "blocking_matches": result.get("blocking_matches") or [],
        "new_evidence_axis": (args.new_evidence_axis or "").strip() or None,
        "override": bool(args.novelty_override),
        "enforced": enforce,
    }

    if result.get("warn") and enforce and alpha_lane:
        if not (args.novelty_override and (args.new_evidence_axis or "").strip()):
            raise SystemExit(
                "novelty gate blocked this reservation: it is a near-neighbor of a "
                "frozen/explored family. Re-run with --novelty-override and "
                '--new-evidence-axis "<what is genuinely new>" if justified, or '
                "pick a different decision hypothesis. See docs/frozen_families.jsonl."
            )
        print(
            f"[novelty] override accepted; new_evidence_axis={out['new_evidence_axis']}",
            file=sys.stderr,
        )
    return out


def _attach_novelty(ticket, novelty):
    """Best-effort: record the novelty result on the created ticket for audit."""
    if not isinstance(ticket, dict) or not novelty:
        return
    path = ticket.get("ticket_file")
    if not path:
        return
    try:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        data["novelty"] = novelty
        p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        ticket["novelty"] = novelty
    except Exception:
        pass


def main(description=__doc__):
    import argparse

    parser = argparse.ArgumentParser(description=description)
    add_common_registry_arg(parser)
    parser.add_argument(
        "--experiment-id",
        help=(
            "Optional explicit ID to reserve. If omitted, the next collision-safe "
            "ID is allocated from all known identity sources."
        ),
    )
    parser.add_argument("--lane", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--change-type", required=True)
    parser.add_argument(
        "--single-causal-variable",
        "--decision-variable",
        dest="single_causal_variable",
        required=True,
        help=(
            "Single attributable decision hypothesis or fixed policy bundle "
            "under test. The old --single-causal-variable name is kept for "
            "compatibility; --decision-variable is preferred."
        ),
    )
    parser.add_argument(
        "--causal-components",
        default="",
        help=(
            "Comma-separated fixed components inside a predeclared policy "
            "bundle. Components are not individually accepted unless later "
            "ablated."
        ),
    )
    parser.add_argument("--mechanism-family")
    parser.add_argument("--trial-family")
    parser.add_argument("--trial-variant-id")
    parser.add_argument("--changed-variable")
    parser.add_argument("--prior-trial-count", type=int, default=0)
    parser.add_argument("--nearby-prior-experiments", default="")
    parser.add_argument(
        "--multiple-testing-risk-bucket",
        choices=["minimal", "low", "moderate", "high"],
        default="minimal",
    )
    parser.add_argument("--new-evidence-type", default="not_declared")
    parser.add_argument("--baseline-result-file")
    parser.add_argument("--allowed-write-scope", default="")
    parser.add_argument(
        "--file-slug",
        help=(
            "Optional short slug for auto-generated runner/artifact names. "
            "Defaults to a slug from --single-causal-variable."
        ),
    )
    parser.add_argument(
        "--exclusive-scope-ok",
        action="store_true",
        help="Allow broad directory scopes such as data/ or quant/.",
    )
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
    parser.add_argument(
        "--success-probability",
        type=float,
        help="Pre-run probability that Gate 4 or the ticket acceptance rule will pass, from 0 to 1.",
    )
    parser.add_argument(
        "--expected-ev-delta",
        type=float,
        help="Pre-run expected aggregate expected_value_score delta.",
    )
    parser.add_argument(
        "--expected-pnl-delta",
        type=float,
        help="Pre-run expected aggregate PnL delta in dollars.",
    )
    parser.add_argument(
        "--main-failure-modes",
        default="",
        help="Comma-separated pre-run failure modes to audit after the result.",
    )
    parser.add_argument(
        "--confidence-reason",
        help="Short reason for the pre-run confidence estimate.",
    )
    parser.add_argument(
        "--new-evidence-axis",
        default="",
        help=(
            "What is genuinely new versus prior/frozen families (new data source, "
            "a field no prior family used, a new gate shape, or forward rows). "
            "Required to override a near-neighbor warning under --enforce-novelty."
        ),
    )
    parser.add_argument(
        "--novelty-override",
        action="store_true",
        help="Proceed despite a near-neighbor warning (records the override).",
    )
    parser.add_argument(
        "--enforce-novelty",
        action="store_true",
        help=(
            "Block reservation of an alpha-lane near-neighbor unless "
            "--novelty-override with --new-evidence-axis is given. Also enabled "
            "by env GINGER_NOVELTY_GATE in {1,block,true}. Default is warn-only."
        ),
    )
    args = parser.parse_args()

    novelty = _novelty_check(args)

    prediction = normalize_prediction(
        success_probability=args.success_probability,
        expected_ev_delta=args.expected_ev_delta,
        expected_pnl_delta=args.expected_pnl_delta,
        main_failure_modes=parse_csv(args.main_failure_modes),
        confidence_reason=args.confidence_reason,
    )

    # registry-decontention step 1: reserve via the lock-free O_EXCL ticket path
    # (the heavy id-collision scan no longer runs under the global registry lock).
    ticket = reserve_experiment(
        args.registry,
        experiment_id=args.experiment_id,
        lane=args.lane,
        hypothesis=args.hypothesis,
        change_type=args.change_type,
        single_causal_variable=args.single_causal_variable,
        causal_components=parse_csv(args.causal_components),
        mechanism_family=args.mechanism_family,
        trial_family=args.trial_family,
        trial_variant_id=args.trial_variant_id,
        changed_variable=args.changed_variable,
        prior_trial_count=args.prior_trial_count,
        nearby_prior_experiments=parse_csv(args.nearby_prior_experiments),
        multiple_testing_risk_bucket=args.multiple_testing_risk_bucket,
        new_evidence_type=args.new_evidence_type,
        baseline_result_file=args.baseline_result_file,
        allowed_write_scope=parse_csv(args.allowed_write_scope),
        must_not_touch=parse_csv(args.must_not_touch),
        locked_variables=parse_csv(args.locked_variables),
        evaluation_windows=parse_windows(args.window),
        acceptance_rule=args.acceptance_rule,
        owner=args.owner,
        file_slug=args.file_slug,
        exclusive_scope_ok=args.exclusive_scope_ok,
        prediction=prediction,
        timeout_seconds=args.lock_timeout_seconds,
    )
    _attach_novelty(ticket, novelty)
    print_json(ticket)


if __name__ == "__main__":
    main()
