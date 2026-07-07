"""exp-20260706-025: daily-equity replay for the deferred-revenue portfolio lane.

This consumes the observed-only ranking from exp-20260706-022. It deliberately
does not retune the deferred-revenue source from exp-20260615-022. The tested
decision hypothesis is whether the second-ranked rejected source still looks
portfolio-useful when its trades are replayed as daily mark-to-market equity
instead of exit-date terminal cashflows.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260706_023_portfolio_daily_equity_overlay.py"
)


def load_base_runner() -> Any:
    spec = importlib.util.spec_from_file_location(
        "exp_20260706_023_portfolio_daily_equity_overlay",
        BASE_RUNNER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load base runner from {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_base_runner()

base.EXPERIMENT_ID = "exp-20260706-025"
base.STEM = "portfolio_daily_equity_deferred_revenue_overlay"
base.STATUS_POSITIVE = (
    "observed_only_positive_deferred_revenue_daily_equity_lead_not_activation_ready"
)
base.STATUS_REJECTED = "observed_only_rejected_deferred_revenue_daily_equity_overlay"
base.DECISION_POSITIVE = (
    "observed_only_positive_deferred_revenue_demand_acceleration_daily_equity_overlay"
)
base.DECISION_REJECTED = (
    "observed_only_rejected_deferred_revenue_demand_acceleration_daily_equity_overlay"
)

base.TRIAL_VARIANT_ID = (
    "deferred_revenue_demand_acceleration_10pct_daily_equity_overlay_v1"
)
base.CHANGED_VARIABLE = (
    "deferred_revenue_demand_acceleration_ranked_portfolio_daily_equity_overlay_v1"
)
base.NEW_EVIDENCE_TYPE = "new_ranked_candidate_family_daily_mtm_overlay"
base.NEW_EVIDENCE_AXIS = (
    "Materially new ranked candidate family from exp-20260706-022: "
    "deferred_revenue_demand_acceleration_candidate_pool has not been consumed "
    "by the daily-MTM overlay lane; this uses the fixed recorded ranking and "
    "source artifact with no overlay-weight, threshold, top-N, hold-day, "
    "cooldown, notional, or correlation retune."
)

base.OUT_DIR = base.REPO_ROOT / "data" / "experiments" / base.EXPERIMENT_ID
base.OUT_JSON = base.OUT_DIR / f"exp_20260706_025_{base.STEM}.json"
base.LOG_JSON = base.REPO_ROOT / "experiments" / "logs" / f"{base.EXPERIMENT_ID}.json"
base.TICKET_JSON = (
    base.REPO_ROOT / "experiments" / "tickets" / f"{base.EXPERIMENT_ID}.json"
)
base.CARD_MD = base.REPO_ROOT / "experiments" / "cards" / f"{base.EXPERIMENT_ID}.md"
base.MANIFEST_JSON = (
    base.REPO_ROOT / "experiments" / "manifests" / f"{base.EXPERIMENT_ID}.json"
)

base.TARGET_SOURCE_ARTIFACT = (
    "data/experiments/exp-20260615-022/"
    "exp_20260615_022_selected_taxonomy_companyfacts_demand.json"
)

base.PREDICTION = {
    "success_probability": 0.27,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 1000.0,
    "main_failure_modes": [
        "daily_equity_window_regression",
        "old_thin_regression",
        "proxy_edge_disappears",
        "missing_ohlcv_path",
    ],
    "confidence_reason": (
        "exp-20260706-022 ranked deferred revenue second on exit-cashflow "
        "portfolio delta, but the two prior daily-MTM overlay attempts showed "
        "that proxy edge can disappear and window regression is likely."
    ),
    "recorded_at": "2026-07-06T23:06:21+00:00",
}

base.HYPOTHESIS = (
    "Portfolio lane: the exp-20260706-022 second-ranked deferred-revenue "
    "demand-acceleration candidate family may add value as a fixed 10 percent "
    "paper overlay when replayed with true daily mark-to-market equity, without "
    "retuning the source or overlay weight."
)
base.ALPHA_HYPOTHESIS = (
    "capital_allocation / risk_allocation: a rejected candidate source can be "
    "portfolio-useful if a small fixed overlay improves aggregate daily-equity "
    "EV while drawdown and window stability remain acceptable."
)
base.CAUSAL_COMPONENTS = [
    "consume exp-20260706-022 ranking",
    "daily mark-to-market equity replay",
    "accepted core equity comparison",
    "no source threshold retune",
    "no strategy behavior change",
]

base.RUNNER = f"quant/experiments/exp_20260706_025_{base.STEM}.py"
base.RUNNER_COMMAND = f".\\.venv\\Scripts\\python.exe -B {base.RUNNER}"
base.RUNNER_WINDOWS = f"quant\\experiments\\exp_20260706_025_{base.STEM}.py"
base.CHANGED_FILES = [
    base.RUNNER,
    f"data/experiments/{base.EXPERIMENT_ID}/exp_20260706_025_{base.STEM}.json",
    f"experiments/cards/{base.EXPERIMENT_ID}.md",
    f"experiments/manifests/{base.EXPERIMENT_ID}.json",
    f"experiments/logs/{base.EXPERIMENT_ID}.json",
    f"experiments/tickets/{base.EXPERIMENT_ID}.json",
    "docs/" + "experiment_" + "registry.json",
]


def source_ranking_audit() -> dict[str, Any]:
    payload = base.read_json(base.REPO_ROOT / base.SOURCE_RANKING_ARTIFACT, {})
    ranking = payload.get("candidate_ranking") if isinstance(payload, dict) else []
    target_row = None
    if isinstance(ranking, list):
        for idx, row in enumerate(ranking, start=1):
            if isinstance(row, dict) and row.get("experiment_id") == "exp-20260615-022":
                target_row = {**row, "rank": idx}
                break
    return {
        "source_artifact": base.SOURCE_RANKING_ARTIFACT,
        "loaded": isinstance(payload, dict) and bool(payload),
        "target_candidate": "exp-20260615-022",
        "target_candidate_rank": target_row.get("rank") if target_row else None,
        "target_candidate_family": target_row.get("family") if target_row else None,
        "target_candidate_core_correlation_exit_cashflow": (
            target_row.get("core_correlation_exit_cashflow") if target_row else None
        ),
        "target_candidate_proxy_delta": (
            target_row.get("portfolio_delta_proxy") if target_row else None
        ),
        "reason_selected": (
            "Second-ranked candidate in the exp-20260706-022 portfolio ranking "
            "after exp-20260706-023 consumed the top fixed-asset-turnover row."
        ),
    }


base.source_ranking_audit = source_ranking_audit


def patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload.get("gate4", {})
    failure_reasons = gate4.get("failed_reasons") if isinstance(gate4, dict) else []
    positive = not failure_reasons
    payload.update(
        {
            "nearby_prior_experiments": [
                "exp-20260706-022",
                "exp-20260706-023",
                "exp-20260706-024",
                "exp-20260615-022",
            ],
            "implementation_mode": "observed_only_daily_equity_replay_no_strategy_change",
            "new_evidence_axis": base.NEW_EVIDENCE_AXIS,
            "new_evidence_type": base.NEW_EVIDENCE_TYPE,
            "decision": base.DECISION_POSITIVE if positive else base.DECISION_REJECTED,
            "status": base.STATUS_POSITIVE if positive else base.STATUS_REJECTED,
            "changed_files": base.CHANGED_FILES,
            "related_files": [
                base.SOURCE_RANKING_ARTIFACT,
                base.TARGET_SOURCE_ARTIFACT,
                base.BASELINE_RESULT_FILE,
                *base.CORE_WINDOW_BASELINES.values(),
                base.WAREHOUSE_SQLITE,
            ],
        }
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The deferred-revenue demand-acceleration candidate from "
            "exp-20260615-022 was consumed from the exp-20260706-022 portfolio "
            "ranking and replayed as daily mark-to-market equity. The result is "
            "judged on aggregate daily EV, drawdown drift, and window stability, "
            "not on deferred-revenue source threshold or notional retunes."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not rerun this deferred-revenue portfolio overlay by changing "
            "overlay weight, demand-growth thresholds, taxonomy, hold days, "
            "top-N, correlation cutoffs, or source filters. A legal retry needs "
            "materially new ranked candidate families, a new data source, or a "
            "shared paper helper / activation-envelope experiment."
        ),
        "new_evidence_required": (
            "A shared default-off helper or activation-envelope Gate 1-4 that "
            "implements a fixed portfolio lane, or materially new ranked "
            "candidate families with replayable daily-equity paths."
        ),
    }
    payload["next_retry_requires"] = [
        "shared default-off helper or activation-envelope Gate 1-4",
        "materially new portfolio-ranked candidate families or a new data source",
        "no overlay-weight, threshold, top-N, hold-day, taxonomy, or correlation retune",
    ]
    if not positive:
        payload["rejection_reason"] = (
            "Daily mark-to-market replay failed the predeclared portfolio-lane gate: "
            + ", ".join(failure_reasons)
        )
    payload["calibration"] = {
        **payload.get("calibration", {}),
        "actual_decision": payload["decision"],
        "actual_success": 1 if positive else 0,
        "predicted_success_probability": base.PREDICTION["success_probability"],
        "predicted_failure_modes": base.PREDICTION["main_failure_modes"],
        "realized_failure_modes": failure_reasons,
        "predicted_failure_mode_hit": bool(
            set(base.PREDICTION["main_failure_modes"]) & set(failure_reasons)
        ),
    }
    payload["gate1"]["source_ranking_audit"] = source_ranking_audit()
    return payload


def main() -> int:
    base.OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = patch_payload(base.build_result())
    base.persist(payload)
    print(
        getattr(base.json, "dumps")(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_delta": payload["aggregate_daily_equity"][
                    "delta_metrics_daily_mtm_proxy"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": base.repo_rel(base.OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
