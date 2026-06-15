"""exp-20260615-022: selected-taxonomy Companyfacts demand acceleration.

Alpha search. This tests one decision hypothesis: the directionally positive
raw Companyfacts deferred-revenue/RPO demand signal from exp-20260615-017 may
be cleaner if only economically stable obligation groups are admitted:
RPO and current contract-customer liability. Total and noncurrent deferred
revenue groups are excluded so the replay does not mix different demand
durations under one score.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. Replay-only positives
are leads until a shared selected-Companyfacts/daily helper reproduces them.
No JavaScript is used.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import exp_20260615_017_deferred_revenue_demand_acceleration as previous


EXPERIMENT_ID = "exp-20260615-022"
STEM = "selected_taxonomy_companyfacts_demand"
TRIAL_FAMILY = "deferred_revenue_demand_acceleration_candidate_pool"
TRIAL_VARIANT_ID = "selected_taxonomy_companyfacts_demand_obligation_top1_next_open_10d_v1"
CHANGED_VARIABLE = "selected_taxonomy_companyfacts_demand_obligation_acceleration_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

DEMAND_CONCEPT_GROUPS = {
    "rpo": ("RevenueRemainingPerformanceObligation",),
    "contract_liability_current": (
        "ContractWithCustomerLiabilityCurrent",
        "DeferredRevenueCurrent",
        "DeferredRevenueAndCreditsCurrent",
    ),
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "late_strong_regression",
        "concept_taxonomy_too_sparse",
        "accepted_distribution_ev_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "exp-20260615-017 showed real demand-obligation signal strength with "
        "+0.4288 EV and +12317.53 PnL but failed late_strong EV and the "
        "accepted distribution EV comparator. This test is lower probability "
        "but materially different because it prevents raw Companyfacts concept "
        "mixing across RPO, total, current, and noncurrent liability groups "
        "while keeping the proven price confirmation and execution envelope "
        "fixed."
    ),
    "recorded_at": "2026-06-15T18:12:04+00:00",
}

PRODUCTION_IMPACT = {
    **deepcopy(previous.PRODUCTION_IMPACT),
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "demand_taxonomy_policy": "rpo_or_current_contract_liability_only",
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper and selected "
        "Companyfacts daily surface compute the same RPO/current-liability "
        "taxonomy gate, liquid SPY-relative confirmation, cooldown, next-open "
        "paper entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: taxonomy-cleaned SEC Companyfacts demand-obligation "
        "acceleration, restricted to RPO and current customer contract "
        "liabilities, may keep the positive paid/contracted-demand signal from "
        "exp-20260615-017 while removing late-window noise from total and "
        "noncurrent obligation concepts."
    ),
    "2_history_check": {
        "exp-20260615-017": (
            "Raw deferred-revenue/RPO demand acceleration was directionally "
            "positive, aggregate EV +0.4288 and PnL +$12,317.53, but rejected "
            "for late_strong EV regression and accepted-distribution EV miss. "
            "This run changes concept taxonomy only, not execution, hold, "
            "notional, cooldown, or price confirmation thresholds."
        ),
        "exp-20260615-012/013": (
            "SEC order/backlog text and quantified backlog text were too sparse "
            "or non-incremental. This run uses numeric XBRL facts, not text "
            "regex expansion."
        ),
        "exp-20260615-016": (
            "Operating leverage acceleration was rejected on old_thin/drawdown. "
            "This run tests pre-revenue obligations, not margin expansion."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution comparators must be beaten. Replay-only positives are "
        "leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260615_022_selected_taxonomy_companyfacts_demand.py"
    ),
}


_ORIGINAL_PATCH_PAYLOAD = previous._patch_payload


def _patch_payload(payload: dict) -> dict:
    payload = _ORIGINAL_PATCH_PAYLOAD(payload)
    failed = ", ".join(payload["gate4"].get("failed_reasons") or [])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_companyfacts_demand_candidate_pool",
            "new_evidence_type": "cleaner_cross_industry_companyfacts_demand_taxonomy",
            "nearby_prior_experiments": [
                "exp-20260615-017",
                "exp-20260615-012",
                "exp-20260615-013",
                "exp-20260615-016",
            ],
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "demand_taxonomy_policy": {
                "rule_version": RULE_VERSION,
                "included_concept_groups": sorted(DEMAND_CONCEPT_GROUPS),
                "included_concepts": {
                    key: list(value) for key, value in DEMAND_CONCEPT_GROUPS.items()
                },
                "excluded_prior_groups": [
                    "contract_liability_total",
                    "contract_liability_noncurrent",
                ],
                "reason": (
                    "RPO and current customer liabilities are the most stable "
                    "cross-industry proxies for contracted near-to-medium-term "
                    "demand; total and noncurrent balances mix durations and "
                    "were likely a source of late-window noise."
                ),
            },
        }
    )
    if payload["gate4"]["passed"]:
        payload["interpretation"] = (
            "The selected-taxonomy Companyfacts demand-obligation source cleared "
            "the numeric replay screen, but remains only a replay lead because "
            "no selected daily Companyfacts surface or shared helper was "
            "promoted."
        )
    else:
        payload["interpretation"] = (
            "The selected-taxonomy Companyfacts demand-obligation source did "
            f"not clear Gate 4 (failed: {failed or 'none'}). It is not "
            "retained or promoted."
        )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The taxonomy-cleaned obligation surface either remained too sparse "
            "or still did not create enough window-stable replacement value "
            "after costs, next-open execution, and accepted-comparator checks."
            if not payload["gate4"]["passed"]
            else (
                "The cleaner taxonomy suggests demand-obligation facts can add "
                "replacement value when concept duration is controlled, but it "
                "still needs shared daily/backtest parity before retention."
            )
        ),
        "realized_failure_mode": failed or "numeric_gate4_passed_but_not_promoted",
        "forbidden_near_neighbor_retry": (
            "Do not retry deferred-revenue/RPO demand by sweeping demand-growth, "
            "demand/revenue, fact age, prior gap, RS/close/volume, top-N, hold, "
            "cooldown, or notional thresholds on these frozen windows."
        ),
        "new_evidence_required": (
            "A valid follow-up needs a selected PIT Companyfacts daily demand "
            "surface, structured contract-economics text linked to the same "
            "ticker/date, or closed forward replacement-value rows."
        ),
    }
    return payload


def _apply_overrides() -> None:
    previous.__file__ = __file__
    previous.EXPERIMENT_ID = EXPERIMENT_ID
    previous.STEM = STEM
    previous.TRIAL_FAMILY = TRIAL_FAMILY
    previous.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    previous.CHANGED_VARIABLE = CHANGED_VARIABLE
    previous.RULE_VERSION = RULE_VERSION
    previous.OWNER = OWNER
    previous.OUT_DIR = OUT_DIR
    previous.OUT_JSON = OUT_JSON
    previous.LOG_JSON = LOG_JSON
    previous.TICKET_JSON = TICKET_JSON
    previous.CARD_MD = CARD_MD
    previous.MANIFEST_JSON = MANIFEST_JSON
    previous.EXPERIMENT_LOG = EXPERIMENT_LOG
    previous.REGISTRY_JSON = REGISTRY_JSON
    previous.DEMAND_CONCEPT_GROUPS = DEMAND_CONCEPT_GROUPS
    previous.PREDICTION = PREDICTION
    previous.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    previous.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    previous._patch_payload = _patch_payload
    previous._RAW_ROWS_CACHE.clear()


def main() -> None:
    _apply_overrides()
    previous.main()


if __name__ == "__main__":
    main()
