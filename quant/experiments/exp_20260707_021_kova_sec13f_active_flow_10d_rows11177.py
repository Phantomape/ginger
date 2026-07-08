"""exp-20260707-021: Kova SEC13F active-flow 10d row-growth attribution.

Observed-only alpha attribution. This reopens the fixed Kova SEC13F
active-manager active-flow surface only because the hot warehouse now closes a
materially larger 10d cohort than exp-20260701-009. It does not change ranking,
sizing, exits, paper sleeves, live orders, watchlists, LLM boundaries, or daily
production behavior.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260701_009_kova_sec13f_active_flow_10d_forward_value.py"
)

EXPERIMENT_ID = "exp-20260707-021"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_active_flow_10d_rows11177"
RUNNER = f"quant/experiments/exp_20260707_021_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260707_021_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha attribution: the fixed Kova SEC13F active-manager "
    "active-flow score should continue to separate cash/SPY/QQQ 10d "
    "replacement value after hot-warehouse coverage expands from the "
    "exp-20260701-009 three-asof cohort to the materially larger nine-asof "
    "settled cohort."
)
TRIAL_VARIANT_ID = "hot_warehouse_10d_closed_forward_rows11177_v2"
CHANGED_VARIABLE = "kova_sec13f_active_flow_10d_forward_value_rows11177_v2"
SINGLE_CAUSAL_VARIABLE = CHANGED_VARIABLE
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-009",
    "exp-20260625-025",
    "exp-20260701-009",
]
NEW_EVIDENCE_AXIS = (
    "Materially more closed forward rows: exp-20260701-009 tested the fixed "
    "Kova SEC13F active-flow score on 3724 settled 10d rows across 3 as-of "
    "dates; current hot-warehouse coverage through 2026-07-06 creates 11177 "
    "settled 10d rows across 9 as-of dates (+200%), without changing SEC13F "
    "thresholds, score components, top-N, hold, notional, response curve, or "
    "strategy behavior."
)
CAUSAL_COMPONENTS = [
    "fixed PIT active-manager 13F flow score",
    "materially more closed 10d forward rows",
    "cash/SPY/QQQ replacement-value separation",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260707-021/exp_20260707_021_kova_sec13f_active_flow_10d_rows11177.json",
    "experiments/cards/exp-20260707-021.md",
    "experiments/manifests/exp-20260707-021.json",
    "experiments/tickets/exp-20260707-021.json",
    "experiments/logs/exp-20260707-021.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("exp20260701009_base", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load base runner from {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()


def configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.OWNER = OWNER
    base.SLUG = SLUG
    base.RUNNER = RUNNER
    base.RUNNER_COMMAND = RUNNER_COMMAND
    base.DATA_DIR = DATA_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.TICKET_JSON = TICKET_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.HYPOTHESIS = HYPOTHESIS
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.SINGLE_CAUSAL_VARIABLE = SINGLE_CAUSAL_VARIABLE
    base.NEARBY_PRIOR_EXPERIMENTS = NEARBY_PRIOR_EXPERIMENTS
    base.NEW_EVIDENCE_AXIS = NEW_EVIDENCE_AXIS
    base.CAUSAL_COMPONENTS = CAUSAL_COMPONENTS
    base.ALLOWED_WRITE_SCOPE = ALLOWED_WRITE_SCOPE
    base.DEFAULT_PREDICTION = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "10d_signal_decay_in_new_cohort",
            "qqq_beta_only",
            "active_flow_historical_gate4_still_blocked",
            "concentration_failed",
        ],
        "confidence_reason": (
            "exp-20260701-009 was a positive 10d observed-only lead on 3724 "
            "rows, but preflight now shows 11177 settled rows and the same "
            "fixed field may decay or reverse in the expanded cohort."
        ),
    }


def patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    primary = payload["primary_summary"]["summary"]
    failed = payload["gate4"]["failed_reasons"]
    settled = primary["settled_rows"]
    scored = primary["scored_rows"]
    asof_count = primary["scored_asof_date_count"]
    warehouse_max = payload["source_summary"]["settlement_metadata"]["price_metadata"].get(
        "warehouse_max_date"
    )

    payload["pre_run_questions"]["2_history_check"] = {
        "novelty_gate": (
            "Reservation passed with novelty and observed-only overrides because "
            "the reopen axis is materially more closed 10d forward rows, not a "
            "new same-source field or response retune."
        ),
        "exp-20260625-009": (
            "Observed-only positive 1d/3d/5d active-manager flow lead; it "
            "predeclared enough closed 10d rows as a valid retry."
        ),
        "exp-20260625-025": (
            "Placebo falsification supported the 1d/3d/5d lead, but promotion "
            "remained blocked until 10d rows or canonical fixed-window coverage."
        ),
        "exp-20260701-009": (
            "Observed-only positive 10d active-flow lead on 3724 settled rows "
            "across 3 as-of dates; this run requires materially more rows and "
            "uses the same fixed score."
        ),
    }
    payload["pre_run_questions"]["5_reproducibility"] = RUNNER_COMMAND
    payload["calibration"]["surprise_note"] = (
        "The prior 10d forward lead was fragile: once the settled cohort expanded "
        "from 3724 to 11177 rows, all cash/SPY/QQQ mean, median, and Spearman "
        "checks failed."
    )
    payload["post_run_reflection"]["why_result_happened"] = (
        "The fixed Kova SEC13F active-manager flow field did not preserve the "
        f"exp-20260701-009 10d lead on the expanded cohort: {settled} settled "
        f"10d rows, {scored} scored rows, {asof_count} as-of dates, warehouse "
        f"max date {warehouse_max}, failed checks {failed}."
    )
    payload["post_run_reflection"]["new_evidence_required"] = (
        "A valid retry needs materially more newly closed 10d rows beyond this "
        "11177-row cohort, manager-level flow from a genuinely new non-quarterly "
        "source, borrow/loan-availability cross-evidence, or canonical fixed-"
        "window PIT coverage through a shared helper that beats accepted "
        "comparators."
    )
    payload["related_files"] = [
        RUNNER,
        base.repo_rel(BASE_RUNNER),
        base.repo_rel(base.settlement.SOURCE_LEDGER_JSONL),
        base.repo_rel(base.settlement.HOT_WAREHOUSE),
        base.repo_rel(base.SETTLEMENT_RUNNER),
        base.repo_rel(base.ACTIVE_FLOW_RUNNER),
        base.repo_rel(base.BASELINE_RESULT),
        "experiments/logs/exp-20260625-009.json",
        "experiments/logs/exp-20260625-025.json",
        "experiments/logs/exp-20260701-009.json",
    ]
    return payload


def build_payload() -> dict[str, Any]:
    configure_base()
    return patch_payload(base.build_payload())


def main() -> int:
    payload = build_payload()
    # base.persist ultimately calls persist_self_registered_result(REGISTRY_JSON, ...).
    base.persist(payload)
    primary = payload["primary_summary"]["summary"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "settled_10d_rows": primary["settled_rows"],
                "scored_10d_rows": primary["scored_rows"],
                "scored_asof_dates": primary["scored_asof_date_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
