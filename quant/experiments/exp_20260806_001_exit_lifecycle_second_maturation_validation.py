"""exp-20260806-001: second-maturation fixed-bucket exit-lifecycle validation.

Observed-only alpha attribution on the post-2026-06-30 exit-lifecycle cohort
after it crossed the exp-20260722-001 declared 212/30/21 reopen bar (281
settled / 40 advisory / 22 hard-stop at freeze). This reuses the complete,
unchanged exp-20260715-006 / exp-20260701-012 policy and changes no strategy
behavior.
"""

from __future__ import annotations

import math

import exp_20260701_012_exit_lifecycle_new_settled_advisory_outcome_refresh as prior


EXPERIMENT_ID = "exp-20260806-001"
SLUG = "exit_lifecycle_second_maturation_validation"
RUNNER = f"quant/experiments/exp_20260806_001_{SLUG}.py"
PRIOR_CUTOFF_AS_OF = "2026-06-30"
BASELINE_RESULT = (
    prior.REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)


prior.EXPERIMENT_ID = EXPERIMENT_ID
prior.SLUG = SLUG
prior.RUNNER = RUNNER
prior.RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
prior.OWNER = "claude-scheduled-alpha"

prior.DATA_DIR = prior.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
prior.OUT_JSON = prior.DATA_DIR / f"exp_20260806_001_{SLUG}.json"
prior.LOG_JSON = prior.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
prior.CARD_MD = prior.REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
prior.MANIFEST_JSON = prior.REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
prior.TICKET_JSON = prior.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

prior.BASELINE_RESULT = BASELINE_RESULT
prior.base.BASELINE_RESULT = BASELINE_RESULT
prior.PRIOR_CUTOFF_AS_OF = PRIOR_CUTOFF_AS_OF
prior.HYPOTHESIS = (
    "Observed-only revalidation under the unchanged exp-20260715-006 "
    "attribution policy: on the matured post-2026-06-30 exit-lifecycle cohort "
    "(281 settled rows, 40 advisory, 22 hard-stop versus the 141/20/14 cohort "
    "judged by exp-20260722-001), high-urgency and hard-stop advisory "
    "positions should show persistently worse next-open-to-five-session-close "
    "returns than no-advisory positions with negative severity monotonicity, "
    "broad date support, and single-name adverse-PnL concentration at or "
    "below 50%; no threshold, bucket, horizon, source, or response function "
    "changes."
)
prior.TRIAL_VARIANT_ID = "post_20260630_second_maturation_v1"
prior.CHANGED_VARIABLE = (
    "exit_lifecycle_post_20260630_second_maturation_fixed_bucket_validation_v1"
)
prior.NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260722-001",
    "exp-20260715-006",
    "exp-20260710-016",
    "exp-20260701-012",
    "exp-20260623-011",
]
prior.NEW_EVIDENCE_TYPE = "recorded_reopen_threshold_met_by_new_settled_forward_rows"
prior.NEW_EVIDENCE_AXIS = (
    "The exp-20260722-001 declared reopen bar has been met for the second "
    "maturation: data/reopen_readiness.json generated 2026-08-06T16:10:13Z "
    "and the frozen data/alpha_search/"
    "exit_lifecycle_reopen_readiness_20260806.json report the fixed "
    "post-2026-06-30 cohort at 281 settled, 40 advisory, and 22 hard-stop "
    "rows versus the declared thresholds 212/30/21 (+99% and +140 absolute "
    "settled rows versus the 141 judged last probe, satisfying section 2.4 "
    "axis (c)); no threshold, bucket, horizon, source, or response is "
    "changed."
)
prior.CAUSAL_COMPONENTS = [
    "newly settled post-2026-06-30 production rows through observed_date 2026-07-28: 281 settled / +99% and +140 absolute versus the 141 judged by exp-20260722-001; satisfies section 2.4 axis (c) and the declared 212/30/21 reopen bar",
    "unchanged advisory severity buckets and H5 next-open-to-five-session-close settlement and every exp-20260715-006 acceptance bar including the <=50% single-name adverse-PnL concentration cap that rejected the prior probe",
    "cohort frozen to the 20260805 outcome ledger snapshot with sha256 recorded in data/alpha_search/exit_lifecycle_reopen_readiness_20260806.json; settlement bars fail-closed on staleness since exp-20260805-004",
    "no strategy / shared-policy / order / ranking / sizing / exit-rule change; result ceiling observed_only; policy promotion would additionally require slot-reuse and winner-collateral accounting plus a shared default-off helper",
    "if rejected then redeclare the next reopen bar and sync scripts/build_reopen_readiness.py lane_exit_lifecycle_advisory in this same ticket per the 2026-07-22 reopen-threshold-sync rule",
]
prior.ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260806_001_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "scripts/build_reopen_readiness.py",
    "data/reopen_readiness.json",
]
prior.CONFIG = {
    **prior.base.CONFIG,
    "prior_cutoff_as_of": PRIOR_CUTOFF_AS_OF,
    "cohort_rule": "as_of_date > prior_cutoff_as_of",
}


def _next_bar(count: int, floor_add: int = 10) -> int:
    """Next reopen threshold: at least +50% and at least +10 absolute."""
    return max(int(math.ceil(count * 1.5)), count + floor_add)


_build_payload = prior.build_payload


def build_payload() -> dict:
    """Build the inherited fixed-policy payload for the second maturation."""
    payload = _build_payload()
    checks = payload["gate4"]["acceptance_checks"]
    settled = int(checks.get("settled_rows") or 0)
    advisory = int(checks.get("advisory_rows") or 0)
    hard = int(checks.get("hard_stop_rows") or 0)
    payload["post_run_reflection"]["forbidden_near_neighbor_retry"] = (
        "Do not re-slice this same post-2026-06-30 cohort by adjacent exit "
        "lifecycle labels, urgency wording, target, trailing-stop, time-stop, "
        "MFE/giveback, or response-function retunes, and do not re-run this "
        "identical validation on a same-week refresh of the same ledger. A "
        "valid retry needs a new data source, a genuinely new gate shape, or "
        "another material increase in settled forward rows beyond this "
        "matured cohort."
    )
    if payload["observed_only_lead"]:
        payload["post_run_reflection"]["new_evidence_required"] = (
            "The observed-only lead still promotes nothing by itself: any "
            "policy promotion requires slot-reuse/winner-collateral "
            "accounting and a shared default-off helper evaluated as its own "
            "single hypothesis against the accepted cash-feasible baseline."
        )
    else:
        payload["post_run_reflection"]["new_evidence_required"] = (
            "A new data source or gate shape; otherwise do not reopen until "
            f"the same post-2026-06-30 cohort reaches at least {_next_bar(settled)} "
            f"settled rows, {_next_bar(advisory)} advisory rows, and "
            f"{_next_bar(hard)} hard-stop rows (at least +50% and +10 absolute "
            f"from {settled}/{advisory}/{hard}). scripts/build_reopen_readiness.py "
            "lane_exit_lifecycle_advisory must be synced to these thresholds in "
            "this same ticket. Any policy promotion also requires "
            "slot-reuse/winner-collateral accounting and a shared default-off "
            "helper."
        )
    payload["synthesis_pass"] = {
        "artifact": "data/alpha_search/exit_lifecycle_reopen_synthesis_pass_20260806.json",
        "baseline_universe": [
            "core accepted-stack held positions observed by the exit-lifecycle shadow log",
            "cash plus SPY/QQQ replacement benchmarks",
        ],
        "opportunity_cost_winner": (
            "cash-plus-existing-accepted-stack: live position control blocks "
            "new entries, no other reopen lane is counter-ready, and the "
            "concurrent codex CAT PEAD lead was not_promoted at panel"
        ),
        "evidence_surfaces_used": [
            "exit-lifecycle forward outcome ledger (281 settled post-cutoff rows)",
            "canonical OHLCV warehouse (repaired exp-20260805-004, fail-closed staleness)",
            "reopen readiness surface (13 lanes, only exit_lifecycle_advisory ready)",
            "live position control snapshot (context only)",
        ],
        "evidence_surfaces_missing": [
            "slot-reuse/winner-collateral accounting",
            "entity_theme axis-c lane (91601/109913, not ready)",
            "short_volume q5 lane (16/20 with failing concentration bar)",
        ],
        "selected_hypothesis": prior.HYPOTHESIS,
        "economic_mechanism": (
            "Position-specific path deterioration: advisory-flagged positions "
            "are in adverse path states; persistent H5 separation would let a "
            "future exit policy free scarce slot capital ahead of continued "
            "deterioration."
        ),
        "falsifier": (
            "Fixed mean/median separation, severity monotonicity, date "
            "support, or the <=50% single-name adverse-PnL concentration cap "
            "fails on the frozen cohort."
        ),
        "pit_tier": "canonical_pit",
        "evidence_grade": "observed_only",
        "result_ceiling": "observed_only",
        "next_machine_action": (
            "Persist this one frozen validation; on rejection redeclare the "
            "reopen bar and sync the readiness builder in the same ticket; "
            "never promote an exit rule without slot-reuse/winner-collateral "
            "evidence and a shared default-off helper."
        ),
        "research_refs": [],
        "research_digest_disposition": (
            "digest-scan-20260806 no_fresh_entries: the digest is unchanged "
            "since 2026-07-27 and every shown entry already carries a "
            "declined status in the canonical ledger."
        ),
        "outcome_exposure_caveat": (
            "Before candidate freeze, a mis-scoped exploratory aggregation "
            "over the full ledger (including the pre-cutoff cohort already "
            "judged by exp-20260722-001) briefly computed adverse-PnL ticker "
            "shares; it was discarded, candidate selection is forced by the "
            "matured reopen counter alone, and the frozen acceptance bars "
            "leave no tunable degree of freedom."
        ),
        "fingerprint_caveat": (
            "The reservation fingerprint routed data_source=exit_lifecycle "
            "(correct population) but gate_shape=notional_scalar instead of "
            "the prior probe's 'other'; recorded per the section 2.4 "
            "over-match warning. Streak/saturation self-checks were done "
            "against the true exit_lifecycle attribution family."
        ),
    }
    payload["pre_run_questions"]["6_opportunity_cost"] = payload["synthesis_pass"][
        "opportunity_cost_winner"
    ]
    payload["pre_run_questions"]["7_cross_surface_mechanism"] = {
        "mechanism": payload["synthesis_pass"]["economic_mechanism"],
        "used": payload["synthesis_pass"]["evidence_surfaces_used"],
        "missing": payload["synthesis_pass"]["evidence_surfaces_missing"],
        "evidence_grade": payload["synthesis_pass"]["evidence_grade"],
    }
    payload["related_files"] = [
        RUNNER,
        prior.repo_rel(prior.SOURCE_DIR),
        prior.repo_rel(prior.BASELINE_RESULT),
        "data/alpha_search/exit_lifecycle_reopen_readiness_20260806.json",
        "data/alpha_search/promotions/exit_lifecycle_reopen_scout_20260806.json",
        "experiments/logs/exp-20260722-001.json",
        "experiments/logs/exp-20260715-006.json",
        "experiments/logs/exp-20260701-012.json",
        "experiments/logs/exp-20260623-011.json",
    ]
    return payload


prior.build_payload = build_payload


# The settled_forward_attribution admission boundary only permits the two
# terminal registry dispositions "observed_only" and "rejected"; keep the
# descriptive decision inside the artifact/log payload but normalize the
# registry-facing decision and status.
_orig_persist_self_registered_result = prior.persist_self_registered_result


def _normalized_persist_self_registered_result(registry, **kwargs):
    result = dict(kwargs.get("result") or {})
    lead = bool(result.get("observed_only_lead"))
    result["detailed_decision"] = result.get("decision")
    result["decision"] = "observed_only" if lead else "rejected"
    kwargs["result"] = result
    kwargs["status"] = "observed_only" if lead else "rejected"
    return _orig_persist_self_registered_result(registry, **kwargs)


prior.persist_self_registered_result = _normalized_persist_self_registered_result


# `docs/experiment_log.jsonl` is a derived view.  The inherited 2026-07-01
# runner predates the shard-only contract, so suppress its direct upsert while
# retaining canonical log-shard and registry persistence.
_upsert_jsonl = prior.upsert_jsonl


def upsert_jsonl(path, record) -> None:
    if path.resolve() == prior.EXPERIMENT_LOG.resolve():
        return
    _upsert_jsonl(path, record)


prior.upsert_jsonl = upsert_jsonl


_build_manifest = prior.build_manifest


def build_manifest(payload: dict) -> dict:
    manifest = _build_manifest(payload)
    manifest["files"].pop("docs/experiment_log.jsonl", None)
    return manifest


prior.build_manifest = build_manifest


if __name__ == "__main__":
    raise SystemExit(prior.main())
