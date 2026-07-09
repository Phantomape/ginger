"""exp-20260707-016: daily-equity replay for the rank-13 portfolio-lane candidate.

This consumes the observed-only ranking from exp-20260706-022. It does not
retune the peer earnings reaction source from exp-20260529-010 and does
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

base.EXPERIMENT_ID = "exp-20260707-016"
base.STEM = "peer_earnings_reaction_daily_equity_overlay"
base.STATUS_POSITIVE = (
    "observed_only_positive_peer_earnings_reaction_daily_equity_lead_not_activation_ready"
)
base.STATUS_REJECTED = (
    "observed_only_rejected_peer_earnings_reaction_daily_equity_overlay"
)
base.DECISION_POSITIVE = (
    "observed_only_positive_peer_earnings_reaction_daily_equity_overlay"
)
base.DECISION_REJECTED = (
    "observed_only_rejected_peer_earnings_reaction_daily_equity_overlay"
)

base.TRIAL_VARIANT_ID = "peer_earnings_reaction_transfer_rank13_10pct_daily_equity_overlay_v1"
base.CHANGED_VARIABLE = "peer_earnings_reaction_transfer_rank13_portfolio_daily_equity_overlay_v1"
base.MECHANISM_FAMILY = "portfolio_covariance_lane"
base.CHANGE_TYPE = "risk_allocation"
base.NEW_EVIDENCE_TYPE = "new_ranked_source_artifact_for_daily_mark_to_market_overlay"
base.NEW_EVIDENCE_AXIS = (
    "New source artifact for the existing daily mark-to-market portfolio overlay gate: "
    "consume exp-20260706-022 rank-13 peer_earnings_reaction_transfer rows from "
    "exp-20260529-010. Prior daily-equity overlays consumed ranks 1-10 and rank 12; "
    "rank 11 volatility term-structure remains skipped as a volatility near-neighbor. "
    "This does not retune overlay weight, source thresholds, top-N, hold days, "
    "cooldown, notional, or correlation cutoffs."
)

base.OUT_DIR = base.REPO_ROOT / "data" / "experiments" / base.EXPERIMENT_ID
base.OUT_JSON = base.OUT_DIR / f"exp_20260707_016_{base.STEM}.json"
base.LOG_JSON = base.REPO_ROOT / "experiments" / "logs" / f"{base.EXPERIMENT_ID}.json"
base.TICKET_JSON = base.REPO_ROOT / "experiments" / "tickets" / f"{base.EXPERIMENT_ID}.json"
base.CARD_MD = base.REPO_ROOT / "experiments" / "cards" / f"{base.EXPERIMENT_ID}.md"
base.MANIFEST_JSON = (
    base.REPO_ROOT / "experiments" / "manifests" / f"{base.EXPERIMENT_ID}.json"
)

base.TARGET_SOURCE_ARTIFACT = (
    "data/experiments/exp-20260529-010/"
    "exp_20260529_010_peer_earnings_reaction_transfer.json"
)

base.PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "daily_equity_window_ev_regression",
        "daily_equity_window_pnl_regression",
        "proxy_edge_disappears",
        "peer_earnings_relation_underperforms_accepted_peer_shock",
    ],
    "confidence_reason": (
        "exp-20260706-022 ranked peer earnings reaction transfer thirteenth with "
        "positive exit-cashflow proxy delta and negative core cashflow correlation, "
        "but the original peer-earnings candidate-pool source was rejected and "
        "recent portfolio daily-MTM overlays mostly failed on window stability; "
        "this tests only the allowed daily-equity replay gate with a new ranked "
        "source artifact."
    ),
    "recorded_at": "2026-07-07T16:03:59+00:00",
}

base.HYPOTHESIS = (
    "Portfolio lane: the exp-20260706-022 rank-13 peer earnings reaction transfer "
    "rejected source may add value as a fixed 10 percent paper overlay when "
    "replayed with true daily mark-to-market equity, without retuning the source "
    "or overlay weight."
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

base.RUNNER = f"quant/experiments/exp_20260707_016_{base.STEM}.py"
base.RUNNER_COMMAND = f".\\.venv\\Scripts\\python.exe -B {base.RUNNER}"
base.RUNNER_WINDOWS = f"quant\\experiments\\exp_20260707_016_{base.STEM}.py"
base.CHANGED_FILES = [
    base.RUNNER,
    f"data/experiments/{base.EXPERIMENT_ID}/exp_20260707_016_{base.STEM}.json",
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
            if row.get("experiment_id") == "exp-20260529-010":
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
            "Next unconsumed ranked family after fixed-asset-turnover, sector-breadth, "
            "deferred-revenue, FINRA short-pressure, purchase-obligation, receivables "
            "DSO, industry breadth-repair, volatility-curve relief, gap-hold core-flow, "
            "and distribution-pressure low-beta daily-equity overlay probes. Rank-11 "
            "volatility term-structure relief remains skipped as adjacent to the "
            "recent volatility-curve relief family."
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
                "exp-20260707-015",
                "exp-20260529-010",
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
            "The peer earnings reaction transfer source from exp-20260529-010 was "
            "consumed from the exp-20260706-022 portfolio ranking and replayed as "
            "daily mark-to-market equity. The result is judged on aggregate daily "
            "EV, drawdown drift, and window stability, not on peer-earnings source "
            "thresholds or notional retunes."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not rerun this peer earnings reaction transfer portfolio overlay by "
            "changing overlay weight, issuer or peer reaction thresholds, industry "
            "relation filters, top-N, hold days, cooldown, notional, correlation "
            "cutoffs, or source filters. A legal retry needs materially new ranked "
            "candidate families, fresh closed forward replacement-value rows for "
            "this unchanged source, or a shared paper helper / activation-envelope "
            "experiment."
        ),
        "new_evidence_required": (
            "A shared default-off helper or activation-envelope Gate 1-4 that "
            "implements a fixed portfolio lane, materially new ranked candidate "
            "families with replayable daily-equity paths, or fresh closed forward "
            "replacement-value rows for the unchanged peer earnings reaction source."
        ),
    }
    payload["next_retry_requires"] = [
        "shared default-off helper or activation-envelope Gate 1-4",
        "materially new portfolio-ranked candidate families",
        "materially more closed peer-earnings relation forward replacement-value rows",
        "no overlay-weight, issuer-reaction, peer-reaction, industry-relation, top-N, hold-day, source-filter, or correlation retune",
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
