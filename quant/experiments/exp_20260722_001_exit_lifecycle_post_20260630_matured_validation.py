"""exp-20260722-001: matured fixed-bucket exit-lifecycle validation.

Observed-only alpha attribution on the now-mature cohort of exit-lifecycle
rows that settled after the 2026-06-30 cutoff. This reuses the complete,
unchanged exp-20260715-006 / exp-20260701-012 policy and changes no strategy
behavior.
"""

from __future__ import annotations

import exp_20260701_012_exit_lifecycle_new_settled_advisory_outcome_refresh as prior


EXPERIMENT_ID = "exp-20260722-001"
SLUG = "exit_lifecycle_post_20260630_matured_validation"
RUNNER = f"quant/experiments/exp_20260722_001_{SLUG}.py"
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
prior.OWNER = "codex-alpha-automation"

prior.DATA_DIR = prior.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
prior.OUT_JSON = prior.DATA_DIR / f"exp_20260722_001_{SLUG}.json"
prior.LOG_JSON = prior.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
prior.CARD_MD = prior.REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
prior.MANIFEST_JSON = prior.REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
prior.TICKET_JSON = prior.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

prior.BASELINE_RESULT = BASELINE_RESULT
prior.base.BASELINE_RESULT = BASELINE_RESULT
prior.PRIOR_CUTOFF_AS_OF = PRIOR_CUTOFF_AS_OF
prior.HYPOTHESIS = (
    "Observed-only alpha under the unchanged exp-20260715-006 policy: the "
    "now-mature post-2026-06-30 exit-lifecycle cohort should preserve "
    "high-urgency and hard-stop next-five-session adverse-return separation "
    "versus no-advisory rows."
)
prior.TRIAL_VARIANT_ID = "post_20260630_reopen_threshold_matured_v1"
prior.CHANGED_VARIABLE = "exit_lifecycle_post_20260630_new_settled_fixed_bucket_validation_v1"
prior.NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260715-006",
    "exp-20260710-016",
    "exp-20260701-012",
    "exp-20260623-011",
]
prior.NEW_EVIDENCE_TYPE = "recorded_reopen_threshold_met_by_new_settled_forward_rows"
prior.NEW_EVIDENCE_AXIS = (
    "The recorded park condition has now been met for the first time: "
    "data/reopen_readiness.json generated 2026-07-22T04:08:36Z reports the "
    "fixed post-2026-06-30 cohort at 141 settled, 20 advisory, and 14 "
    "hard-stop rows versus the declared reopen thresholds 101/20/8; no "
    "threshold, bucket, horizon, source, or response is changed."
)
prior.CAUSAL_COMPONENTS = [
    "newly settled post-2026-06-30 production rows",
    "unchanged advisory severity buckets",
    "fixed next-open to five-session-close settlement",
    "no strategy behavior change",
]
prior.ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260722_001_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
prior.CONFIG = {
    **prior.base.CONFIG,
    "prior_cutoff_as_of": PRIOR_CUTOFF_AS_OF,
    "cohort_rule": "as_of_date > prior_cutoff_as_of",
}


_build_payload = prior.build_payload


def build_payload() -> dict:
    """Build the inherited fixed-policy payload for the matured cohort."""
    payload = _build_payload()
    payload["post_run_reflection"]["forbidden_near_neighbor_retry"] = (
        "Do not re-slice this same post-2026-06-30 cohort by adjacent exit "
        "lifecycle labels, urgency wording, target, trailing-stop, time-stop, "
        "MFE/giveback, or response-function retunes. A valid retry needs a "
        "new data source, a genuinely new gate shape, or another material "
        "increase in settled forward rows beyond this matured cohort."
    )
    payload["post_run_reflection"]["new_evidence_required"] = (
        "A new data source or gate shape; otherwise do not reopen until the "
        "same post-2026-06-30 cohort reaches at least 212 settled rows, 30 "
        "advisory rows, and 21 hard-stop rows (at least +50% from 141/20/14). "
        "Any policy promotion also requires slot-reuse/winner-collateral "
        "accounting and a shared default-off helper."
    )
    payload["synthesis_pass"] = {
        "baseline_universe": [
            "47-name frozen cash-feasible core universe",
            "current portfolio: DDOG, DINO, HOOD, MUU, NFLX, RKLB, SNXX, SPY, UNH; META observation",
            "cash plus SPY/QQQ replacement benchmarks",
        ],
        "opportunity_cost_winner": (
            "exp-20260715-010 remains the active strategy baseline; for this "
            "exit attribution the comparators are continue-hold versus "
            "next-open exit into cash, SPY, or QQQ"
        ),
        "evidence_surfaces_used": [
            "price and active cash-feasible baseline",
            "exit-lifecycle forward ledger and H5 warehouse outcomes",
            "borrow positioning audit",
            "event and research-digest audit",
            "flow/options availability audit",
            "current portfolio exposure",
            "reopen-readiness ledger",
        ],
        "evidence_surfaces_missing": [
            "authorized old_thin borrow fee plus availability/utilization",
            "107 USPTO weekly XML vintages plus effective-dated issuer mapping",
            "exit slot-reuse and winner-collateral accounting",
            "canonical historical PIT exit-lifecycle replay",
        ],
        "hypothesis_candidates": [
            {
                "hypothesis": "Fixed exp-20260712-013 borrow stress excludes the next fresh-core entry.",
                "baseline": "unchanged cash-feasible entry policy",
                "treatment": "fixed fee/availability admission gate",
                "horizon": "three standard windows",
                "replacement_value": "admitted entry versus excluded entry retained as cash/SPY/QQQ",
                "falsifier": "no authorized old_thin availability data or fewer than five touches per window",
                "disposition": "parked",
            },
            {
                "hypothesis": "First/new CPC-family patent grants identify commercialization acceleration.",
                "baseline": "same-date tradable core universe",
                "treatment": "default-off issuer-week patent observer",
                "horizon": "three standard windows",
                "replacement_value": "patent-ranked candidate versus baseline candidate/cash",
                "falsifier": "any window below 20 issuer-weeks or 10 tickers, top1 above 30%, or non-PIT mapping",
                "disposition": "parked",
            },
            {
                "hypothesis": prior.HYPOTHESIS,
                "baseline": "no-advisory settled rows under the unchanged fixed bucket policy",
                "treatment": "high-urgency and hard-stop settled rows",
                "horizon": "next open through fifth session close",
                "replacement_value": "continue-hold loss and cash/SPY/QQQ replacement value",
                "falsifier": "fixed mean/median, monotonicity, date-support, or concentration checks fail",
                "disposition": "selected",
            },
        ],
        "selected_hypothesis": prior.HYPOTHESIS,
        "economic_mechanism": (
            "Position-specific path deterioration can make an advisory exit "
            "avoid the next five sessions of loss while releasing scarce capital."
        ),
        "falsifier": (
            "High-urgency and hard-stop mean/median returns are not worse than "
            "no-advisory, severity is not monotonic across dates, or adverse "
            "PnL is too concentrated."
        ),
        "evidence_grade": "observed_only",
        "next_machine_action": (
            "Run this claimed fixed-policy validation once; never promote an "
            "exit rule without slot-reuse/winner-collateral evidence and a "
            "shared default-off helper."
        ),
        "research_refs": [],
        "research_digest_disposition": (
            "The latest fresh digest entries were already dispositioned in "
            "the canonical ledger before this run; none supplies the missing "
            "borrow authorization, USPTO vintages, or exit counterfactual."
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
        "experiments/logs/exp-20260715-006.json",
        "experiments/logs/exp-20260710-016.json",
        "experiments/logs/exp-20260701-012.json",
        "experiments/logs/exp-20260623-011.json",
    ]
    return payload


prior.build_payload = build_payload


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
