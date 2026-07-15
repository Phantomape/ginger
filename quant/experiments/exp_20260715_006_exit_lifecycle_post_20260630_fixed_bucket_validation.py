"""exp-20260715-006: fixed-bucket exit-lifecycle forward validation.

Observed-only alpha attribution on exit-lifecycle rows that settled after the
2026-06-30 cutoff.  This intentionally reuses the complete, unchanged
evaluation policy from exp-20260701-012 and changes no strategy behavior.
"""

from __future__ import annotations

import exp_20260701_012_exit_lifecycle_new_settled_advisory_outcome_refresh as prior


EXPERIMENT_ID = "exp-20260715-006"
SLUG = "exit_lifecycle_post_20260630_fixed_bucket_validation"
RUNNER = f"quant/experiments/exp_20260715_006_{SLUG}.py"
PRIOR_CUTOFF_AS_OF = "2026-06-30"


prior.EXPERIMENT_ID = EXPERIMENT_ID
prior.SLUG = SLUG
prior.RUNNER = RUNNER
prior.RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
prior.OWNER = "alpha-explore"

prior.DATA_DIR = prior.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
prior.OUT_JSON = prior.DATA_DIR / f"exp_20260715_006_{SLUG}.json"
prior.LOG_JSON = prior.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
prior.CARD_MD = prior.REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
prior.MANIFEST_JSON = prior.REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
prior.TICKET_JSON = prior.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

prior.PRIOR_CUTOFF_AS_OF = PRIOR_CUTOFF_AS_OF
prior.HYPOTHESIS = (
    "Observed-only alpha: exit-lifecycle shadow rows newly settled after "
    "2026-06-30 should preserve the unchanged high-urgency and hard-stop "
    "next-5d adverse-return separation versus no-advisory rows."
)
prior.TRIAL_VARIANT_ID = "post_20260630_new_settled_rows_fixed_bucket_v1"
prior.CHANGED_VARIABLE = "exit_lifecycle_post_20260630_new_settled_fixed_bucket_validation_v1"
prior.NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260701-012",
    "exp-20260623-011",
    "exp-20260623-016",
    "exp-20260630-020",
]
prior.NEW_EVIDENCE_TYPE = "materially_more_settled_forward_shadow_exit_rows"
prior.NEW_EVIDENCE_AXIS = (
    "Materially more settled forward rows: exit_lifecycle h5 increased from "
    "320 at exp-20260701-012 to 482 (+162, +50.63%); this test uses only the "
    "fresh post-2026-06-30 cohort with identical buckets, horizon, and "
    "acceptance checks."
)
prior.CAUSAL_COMPONENTS = [
    "new post-2026-06-30 settled production rows",
    "unchanged advisory severity buckets",
    "fixed next-open to five-session-close settlement",
    "no strategy behavior change",
]
prior.ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260715_006_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
    "docs/alpha-optimization-playbook.md",
]
prior.CONFIG = {
    **prior.base.CONFIG,
    "prior_cutoff_as_of": PRIOR_CUTOFF_AS_OF,
    "cohort_rule": "as_of_date > prior_cutoff_as_of",
}


_build_payload = prior.build_payload


def build_payload() -> dict:
    """Build the inherited fixed-policy payload and correct cohort handoff text."""
    payload = _build_payload()
    payload["post_run_reflection"]["forbidden_near_neighbor_retry"] = (
        "Do not re-slice this same post-2026-06-30 cohort by adjacent exit "
        "lifecycle labels, urgency wording, target, trailing-stop, time-stop, "
        "MFE/giveback, or response-function retunes. A valid retry needs a "
        "new data source, a genuinely new gate shape, or another material "
        "increase in settled forward rows beyond this cohort."
    )
    payload["post_run_reflection"]["new_evidence_required"] = (
        "A new data source or gate shape, or another material increase in "
        "closed production exit-lifecycle rows beyond this cohort, plus "
        "slot-reuse/winner-collateral accounting before policy promotion."
    )
    payload["related_files"] = [
        RUNNER,
        prior.repo_rel(prior.SOURCE_DIR),
        prior.repo_rel(prior.BASELINE_RESULT),
        "experiments/logs/exp-20260701-012.json",
        "experiments/logs/exp-20260623-011.json",
        "experiments/logs/exp-20260623-016.json",
        "experiments/logs/exp-20260630-020.json",
        "docs/alpha-optimization-playbook.md",
    ]
    return payload


prior.build_payload = build_payload

_build_manifest = prior.build_manifest


def build_manifest(payload: dict) -> dict:
    """Include the frozen-family handoff update in the revision manifest."""
    manifest = _build_manifest(payload)
    playbook = prior.REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
    manifest["files"][prior.repo_rel(playbook)] = {
        "exists": playbook.exists(),
        "sha256": prior.base.sha256(playbook),
    }
    return manifest


prior.build_manifest = build_manifest


if __name__ == "__main__":
    raise SystemExit(prior.main())
