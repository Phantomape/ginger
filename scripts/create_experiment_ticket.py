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


def classify_saturated_source_axis(axis):
    """Classify whether a saturated-source override names a legal evidence axis.

    AGENTS.md is stricter than the ordinary novelty override: once a
    ``(gate_shape, data_source)`` cell is saturated, an untried same-source field
    no longer counts as new evidence. The override must name a new data source, a
    new gate shape, or materially more closed/settled forward rows.
    """
    raw = str(axis or "").strip()
    text = raw.lower().replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    categories = []
    if any(
        phrase in text
        for phrase in (
            "new data source",
            "different data source",
            "genuinely new source",
            "new source",
            "new external source",
        )
    ):
        categories.append("new_data_source")
    if any(
        phrase in text
        for phrase in (
            "new gate shape",
            "different gate shape",
            "non scan gate shape",
            "non scan gateshape",
            "new gateshape",
        )
    ):
        categories.append("new_gate_shape")
    if any(
        phrase in text
        for phrase in (
            "materially more closed",
            "substantially more closed",
            "closed forward row",
            "closed forward rows",
            "settled forward row",
            "settled forward rows",
            "mature forward row",
            "mature forward rows",
            "matured forward row",
            "matured forward rows",
            "new forward row",
            "new forward rows",
            "forward replacement row",
            "forward replacement rows",
        )
    ):
        categories.append("materially_more_forward_rows")
    field_only_markers = (
        "field" in text
        or "tag" in text
        or "xbrl" in text
        or "concept" in text
        or "label" in text
    )
    return {
        "axis": raw or None,
        "valid": bool(categories),
        "categories": categories,
        "invalid_same_source_field_only": bool(field_only_markers and not categories),
        "rule": (
            "For saturated (gate_shape, data_source) cells, legal override axes "
            "are limited to a new data source, a new gate shape, or materially "
            "more closed/settled forward rows. Same-source new fields/tags do "
            "not qualify."
        ),
    }


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

    # Blocking is the default for alpha lanes. Precedence: explicit per-call
    # flags win, then the env switch, else block by default.
    gate_env = os.environ.get("GINGER_NOVELTY_GATE", "").strip().lower()
    if args.no_enforce_novelty:
        enforce = False
    elif args.enforce_novelty:
        enforce = True
    elif gate_env in {"off", "0", "warn", "false", "no"}:
        enforce = False
    elif gate_env in {"1", "block", "true", "yes"}:
        enforce = True
    else:
        enforce = True
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
            f"[novelty] WARN near-neighbor of a frozen/explored/prior-failed family"
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

    # Source-saturation penalty: independent of the near-neighbor gate. Each new
    # field is a distinct fingerprint so the near-neighbor gate waves it through,
    # but re-scanning a data source that history shows is dry (low accept rate
    # over enough trials) is pure token churn. Thresholds tunable via env.
    try:
        min_tr = int(os.environ.get("GINGER_SATURATION_MIN_TRIALS", "12"))
    except (TypeError, ValueError):
        min_tr = 12
    try:
        max_ar = float(os.environ.get("GINGER_SATURATION_MAX_ACCEPT", "0.05"))
    except (TypeError, ValueError):
        max_ar = 0.05
    try:
        # gate_shape for the saturation decision must come from the STRUCTURED
        # identifiers (trial_family / changed_variable / decision-variable /
        # file_slug), not the free-text hypothesis. Prose like "ranking" matches
        # the allocator gate_shape first (first-match-wins) and would silently
        # mislabel a candidate-pool scan as allocator_source, skipping the
        # saturation gate. The structured slugs reliably carry the
        # candidate_pool marker, so re-infer gate_shape from them alone.
        struct_shape = efp.infer_fingerprint(
            args.trial_family or "",
            args.changed_variable or "",
            args.single_causal_variable or "",
            args.file_slug or "",
        ).get("gate_shape")
        sat_fp = dict(fingerprint)
        if struct_shape and struct_shape != "other":
            sat_fp["gate_shape"] = struct_shape
        saturation = cen.source_saturation(
            sat_fp, min_trials=min_tr, max_accept_rate=max_ar
        )
    except Exception:
        saturation = {"applicable": False, "saturated": False}

    out = {
        "fingerprint": fingerprint,
        "warn": bool(result.get("warn")),
        "warn_threshold": result.get("warn_threshold"),
        "nearest": nearest[:5],
        "blocking_matches": result.get("blocking_matches") or [],
        "new_evidence_axis": (args.new_evidence_axis or "").strip() or None,
        "override": bool(args.novelty_override),
        "enforced": enforce,
        "source_saturation": saturation,
        "saturated_source_override": bool(getattr(args, "saturated_source_override", False)),
        "saturated_source_axis": classify_saturated_source_axis(args.new_evidence_axis),
    }

    if result.get("warn") and enforce and alpha_lane:
        if not (args.novelty_override and (args.new_evidence_axis or "").strip()):
            raise SystemExit(
                "novelty gate blocked this reservation: it is a near-neighbor of a "
                "frozen/explored or prior-failed (tried >=1x, never accepted) "
                "family. Re-run with --novelty-override and "
                '--new-evidence-axis "<what is genuinely new>" if justified, or '
                "pick a different decision hypothesis. See docs/frozen_families.jsonl."
            )
        print(
            f"[novelty] override accepted; new_evidence_axis={out['new_evidence_axis']}",
            file=sys.stderr,
        )

    if saturation.get("saturated"):
        print(
            f"[saturation] data_source '{saturation['source']}' is dry for "
            f"{saturation['gate_shape']} scans: "
            f"{saturation['accepts']}/{saturation['trials']} accepted "
            f"({100 * saturation['accept_rate']:.1f}%, threshold "
            f"{100 * saturation['max_accept_rate']:.1f}% over >= "
            f"{saturation['min_trials']} trials).",
            file=sys.stderr,
        )
    if saturation.get("saturated") and enforce and alpha_lane:
        if not (
            getattr(args, "saturated_source_override", False)
            and (args.new_evidence_axis or "").strip()
        ):
            raise SystemExit(
                "saturation gate blocked this reservation: candidate-pool scans on "
                f"data_source '{saturation['source']}' are historically dry "
                f"({saturation['accepts']}/{saturation['trials']} accepted, "
                f"{100 * saturation['accept_rate']:.1f}% over "
                f">= {saturation['min_trials']} trials). Stop swapping fields on a "
                "proven-dry source. Prefer a genuinely new data source, a new "
                "gate_shape, or materially more closed/settled forward rows. "
                "To proceed anyway, re-run with --saturated-source-override "
                'and --new-evidence-axis "<new data source | new gate shape | '
                'materially more closed forward rows>". Same-source new fields '
                "or tags do not qualify."
            )
        axis_class = out["saturated_source_axis"]
        if not axis_class["valid"]:
            raise SystemExit(
                "saturation gate blocked this reservation: the declared "
                "--new-evidence-axis does not satisfy the saturated-source hard "
                "rule. Same-source untried fields/tags/XBRL labels are not a "
                "legal override after a dry (gate_shape, data_source) cell is "
                "saturated. Name a genuinely new data source, a new gate shape, "
                "or materially more closed/settled forward rows."
            )
        print(
            f"[saturation] override accepted on dry source '{saturation['source']}'"
            f" ({100 * saturation['accept_rate']:.1f}%); "
            f"axis={out['new_evidence_axis']} "
            f"categories={','.join(axis_class['categories'])}",
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
            "Required to override a near-neighbor warning under --enforce-novelty. "
            "For saturated-source overrides, same-source new fields/tags do not "
            "qualify; name a new data source, new gate shape, or materially more "
            "closed/settled forward rows."
        ),
    )
    parser.add_argument(
        "--novelty-override",
        action="store_true",
        help="Proceed despite a near-neighbor warning (records the override).",
    )
    parser.add_argument(
        "--saturated-source-override",
        action="store_true",
        help=(
            "Proceed despite a source-saturation block (re-scanning a data source "
            "whose candidate-pool history is dry). Distinct from --novelty-override "
            "on purpose: also requires --new-evidence-axis naming a genuinely new "
            "data source, a new gate shape, or materially more closed/settled "
            "forward rows. Same-source new fields/tags are blocked."
        ),
    )
    parser.add_argument(
        "--enforce-novelty",
        action="store_true",
        help=(
            "Force the blocking novelty gate for this reservation (redundant: "
            "blocking is now the default for alpha lanes)."
        ),
    )
    parser.add_argument(
        "--no-enforce-novelty",
        action="store_true",
        help=(
            "Force warn-only for this reservation, overriding the block-by-"
            "default. Also: env GINGER_NOVELTY_GATE in {off,0,warn} disables "
            "blocking globally; {1,block,true} forces it on."
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
