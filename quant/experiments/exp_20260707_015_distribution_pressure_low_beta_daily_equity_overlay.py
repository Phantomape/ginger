"""exp-20260707-015: daily-equity replay for the rank-12 portfolio-lane candidate.

This consumes the observed-only ranking from exp-20260706-022. It does not
retune the distribution-pressure low-beta source from exp-20260611-019 and does
not change live, paper, ranking, sizing, entry, or exit behavior. The only
tested decision hypothesis is whether this ranked rejected source still looks
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

base.EXPERIMENT_ID = "exp-20260707-015"
base.STEM = "distribution_pressure_low_beta_daily_equity_overlay"
base.STATUS_POSITIVE = (
    "observed_only_positive_distribution_pressure_low_beta_daily_equity_lead_not_activation_ready"
)
base.STATUS_REJECTED = (
    "observed_only_rejected_distribution_pressure_low_beta_daily_equity_overlay"
)
base.DECISION_POSITIVE = (
    "observed_only_positive_distribution_pressure_low_beta_daily_equity_overlay"
)
base.DECISION_REJECTED = (
    "observed_only_rejected_distribution_pressure_low_beta_daily_equity_overlay"
)

base.TRIAL_VARIANT_ID = "distribution_pressure_low_beta_rank12_10pct_daily_equity_overlay_v1"
base.CHANGED_VARIABLE = "distribution_pressure_low_beta_rank12_portfolio_daily_equity_overlay_v1"
base.MECHANISM_FAMILY = "portfolio_covariance_lane"
base.CHANGE_TYPE = "risk_allocation"
base.NEW_EVIDENCE_TYPE = "new_ranked_source_artifact_for_daily_mark_to_market_overlay"
base.NEW_EVIDENCE_AXIS = (
    "New source artifact for the existing daily mark-to-market portfolio overlay gate: "
    "consume exp-20260706-022 rank-12 distribution_pressure_low_beta_defensive_leadership "
    "rows from exp-20260611-019. Rank-11 volatility term-structure is skipped as a "
    "near-neighbor to the just-tested volatility-curve relief family; prior "
    "daily-equity overlays consumed fixed-asset-turnover, sector-breadth, "
    "deferred-revenue, FINRA short-pressure, purchase-obligation, receivables DSO, "
    "industry breadth-repair, volatility-curve relief, and gap-hold core-flow. "
    "This does not retune overlay weight, source thresholds, top-N, hold days, "
    "cooldown, notional, or correlation cutoffs."
)

base.OUT_DIR = base.REPO_ROOT / "data" / "experiments" / base.EXPERIMENT_ID
base.OUT_JSON = base.OUT_DIR / f"exp_20260707_015_{base.STEM}.json"
base.LOG_JSON = base.REPO_ROOT / "experiments" / "logs" / f"{base.EXPERIMENT_ID}.json"
base.TICKET_JSON = base.REPO_ROOT / "experiments" / "tickets" / f"{base.EXPERIMENT_ID}.json"
base.CARD_MD = base.REPO_ROOT / "experiments" / "cards" / f"{base.EXPERIMENT_ID}.md"
base.MANIFEST_JSON = (
    base.REPO_ROOT / "experiments" / "manifests" / f"{base.EXPERIMENT_ID}.json"
)

base.TARGET_SOURCE_ARTIFACT = (
    "data/experiments/exp-20260611-019/"
    "exp_20260611_019_distribution_pressure_low_beta_defensive_leadership.json"
)

base.PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "daily_equity_window_ev_regression",
        "daily_equity_window_pnl_regression",
        "proxy_edge_disappears",
        "defensive_low_beta_underperforms_accepted_distribution_absorption",
    ],
    "confidence_reason": (
        "exp-20260706-022 ranked distribution-pressure low-beta defensive leadership "
        "twelfth with positive exit-cashflow proxy delta, and exp-20260611-019 had "
        "positive aggregate replay but failed champion/window checks. Confidence "
        "stays low because the recent daily-MTM overlay consumptions mostly exposed "
        "window instability."
    ),
    "recorded_at": "2026-07-07T15:10:12+00:00",
}

base.HYPOTHESIS = (
    "Portfolio lane: the exp-20260706-022 rank-12 distribution-pressure low-beta "
    "defensive leadership rejected source may add value as a fixed 10 percent "
    "paper overlay when replayed with true daily mark-to-market equity, without "
    "retuning the source or overlay weight."
)
base.ALPHA_HYPOTHESIS = (
    "capital_allocation / risk_allocation: rejected candidate sources can be "
    "portfolio-useful if a small fixed overlay improves aggregate daily-equity EV "
    "while drawdown and window stability remain acceptable."
)
base.CAUSAL_COMPONENTS = [
    "consume exp-20260706-022 ranking",
    "daily mark-to-market equity replay",
    "accepted core equity comparison",
    "no source threshold retune",
    "no strategy behavior change",
]

base.RUNNER = f"quant/experiments/exp_20260707_015_{base.STEM}.py"
base.RUNNER_COMMAND = f".\\.venv\\Scripts\\python.exe -B {base.RUNNER}"
base.RUNNER_WINDOWS = f"quant\\experiments\\exp_20260707_015_{base.STEM}.py"
base.CHANGED_FILES = [
    base.RUNNER,
    f"data/experiments/{base.EXPERIMENT_ID}/exp_20260707_015_{base.STEM}.json",
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
    skipped_row = None
    if isinstance(ranking, list):
        for idx, row in enumerate(ranking, start=1):
            if not isinstance(row, dict):
                continue
            if row.get("experiment_id") == "exp-20260609-022":
                skipped_row = {**row, "rank": idx}
            if row.get("experiment_id") == "exp-20260611-019":
                target_row = {**row, "rank": idx}
                break
    return {
        "source_artifact": base.SOURCE_RANKING_ARTIFACT,
        "loaded": isinstance(payload, dict) and bool(payload),
        "top_candidate": payload.get("summary", {}).get("top_candidate")
        if isinstance(payload, dict)
        else None,
        "target_candidate_found": target_row is not None,
        "target_candidate": target_row,
        "skipped_rank11_candidate": skipped_row,
        "reason_selected": (
            "Next unconsumed non-volatility ranked family after fixed-asset-turnover, "
            "sector-breadth, deferred-revenue, FINRA short-pressure, purchase-obligation, "
            "receivables DSO, industry breadth-repair, volatility-curve relief, and "
            "gap-hold core-flow daily-equity overlay probes. Rank-11 volatility "
            "term-structure relief is intentionally skipped as adjacent to the "
            "just-tested volatility-curve relief family."
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
                "exp-20260706-025",
                "exp-20260707-001",
                "exp-20260707-003",
                "exp-20260707-005",
                "exp-20260707-006",
                "exp-20260707-007",
                "exp-20260707-008",
                "exp-20260611-019",
            ],
            "mechanism_family": base.MECHANISM_FAMILY,
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
            "The distribution-pressure low-beta defensive leadership source from "
            "exp-20260611-019 was consumed from the exp-20260706-022 portfolio "
            "ranking and replayed as daily mark-to-market equity. The result is "
            "judged on aggregate daily EV, drawdown drift, and window stability, "
            "not on defensive-leadership source thresholds or notional retunes."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not rerun this distribution-pressure low-beta defensive leadership "
            "portfolio overlay by changing overlay weight, pressure lookback, beta "
            "or volatility cuts, confirmation thresholds, top-N, hold days, cooldown, "
            "notional, correlation cutoffs, or source filters. A legal retry needs "
            "materially new ranked candidate families, fresh closed forward "
            "replacement-value rows for this unchanged source, or a shared paper "
            "helper / activation-envelope experiment."
        ),
        "new_evidence_required": (
            "A shared default-off helper or activation-envelope Gate 1-4 that "
            "implements a fixed portfolio lane, materially new ranked candidate "
            "families with replayable daily-equity paths, or fresh closed forward "
            "replacement-value rows for the unchanged distribution-pressure low-beta "
            "source."
        ),
    }
    payload["next_retry_requires"] = [
        "shared default-off helper or activation-envelope Gate 1-4",
        "materially new portfolio-ranked candidate families",
        "materially more closed distribution-pressure low-beta forward replacement-value rows",
        "no overlay-weight, beta-cut, volatility-cut, pressure-lookback, top-N, hold-day, source-filter, or correlation retune",
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
        base.json.dumps(
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
