"""exp-20260606-014: broad 5d winner exhaustion-cap continuation.

Replay-only alpha search. This follows exp-20260606-005, which showed broad
5-day winner continuation can add replacement value but failed Gate 4 because
max drawdown drift was too high. The only tested variable here is a
production-visible anti-exhaustion tail state: keep the same market-confirmed
broad winner candidate source, but only admit candidates whose signal-date
5-day return is <= 20%.

Ticker pool, top-bucket ranking, SPY confirmation, ret20 confirmation, next-open
entry, hold, notional, cooldown, core-overlap controls, LLM/news behavior, and
production code are unchanged. No JavaScript is used.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260606_005_broad_5d_winner_market_confirmed_continuation as previous


EXPERIMENT_ID = "exp-20260606-014"
STEM = "broad_5d_winner_exhaustion_cap"
TRIAL_FAMILY = "broad_5d_winner_exhaustion_capped_continuation_candidate_pool"
TRIAL_VARIANT_ID = "candidate_ret5_lte_20pct_v1"
CHANGED_VARIABLE = "broad_5d_winner_candidate_ret5_lte_20pct_tail_state_v1"
RULE_VERSION = "broad_5d_winner_exhaustion_cap_v1"

MAX_CANDIDATE_RET5 = 0.20

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_014_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_ETF_EXPERIMENT_ID = "exp-20260606-001"
ACCEPTED_ETF_AGGREGATE_EV = 10.9233
ACCEPTED_ETF_AGGREGATE_PNL = 279157.90

framework = previous.framework

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.4,
    "expected_pnl_delta": 7000.0,
    "main_failure_modes": [
        "drawdown_drift_too_high",
        "edge_removed_by_exhaustion_cap",
        "underperforms_etf_substitute",
        "window_regression",
    ],
    "confidence_reason": (
        "exp-20260606-005 had strong aggregate EV/PnL and all-window PnL but "
        "failed tail/drawdown. A signal-day ret5 exhaustion cap is known after "
        "the close, directly targets the failure, and does not add noisy tickers; "
        "broad OHLCV multiple-testing risk remains high."
    ),
    "recorded_at": "2026-06-06T12:12:02+00:00",
}

PRODUCTION_IMPACT = {
    **previous.PRODUCTION_IMPACT,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same broad "
        "warehouse all-windows-full-liquid stock universe, SPY 5-day market "
        "confirmation, candidate 20-day trend, candidate 5-day exhaustion cap, "
        "5-day SPY-relative rank, next-open paper entry, 10-trading-day exit, "
        "costs, cooldown, and core-overlap controls in replay and daily "
        "production before any report queue, paper ledger, candidate priority, "
        "sizing, watchlist, or order surface could change."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, contexts, scan = previous._candidate_rows_for_window(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    kept: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()
    for candidate in candidates:
        candidate_ret5 = candidate.get("candidate_ret5")
        try:
            ret5 = float(candidate_ret5)
        except (TypeError, ValueError):
            rejects["missing_candidate_ret5"] += 1
            continue
        if ret5 > MAX_CANDIDATE_RET5:
            rejects["candidate_ret5_above_exhaustion_cap"] += 1
            continue
        row = dict(candidate)
        row.update(
            {
                "source": STEM,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "exhaustion_cap_rule_version": RULE_VERSION,
                "max_candidate_ret5": MAX_CANDIDATE_RET5,
                "exhaustion_cap_state": "candidate_ret5_lte_20pct",
                "known_at": "after_signal_date_close_before_next_open_paper_entry",
                "uses_free_ohlcv_only": True,
                "uses_llm": False,
            }
        )
        kept.append(row)
    scan = dict(scan)
    scan["exhaustion_cap_reject_counts"] = dict(sorted(rejects.items()))
    scan["exhaustion_cap_kept_candidates"] = len(kept)
    scan["exhaustion_cap_rule_version"] = RULE_VERSION
    scan["max_candidate_ret5"] = MAX_CANDIDATE_RET5
    return kept, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = previous._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    after_ev = float(aggregate.get("after_expected_value_score_sum") or 0.0)
    after_pnl = float(aggregate.get("after_total_pnl_sum") or 0.0)
    etf_comparison = {
        "baseline_experiment_id": ACCEPTED_ETF_EXPERIMENT_ID,
        "accepted_etf_expected_value_score_sum": ACCEPTED_ETF_AGGREGATE_EV,
        "accepted_etf_total_pnl_sum": ACCEPTED_ETF_AGGREGATE_PNL,
        "after_expected_value_score_sum": round(after_ev, 6),
        "after_total_pnl_sum": round(after_pnl, 2),
        "expected_value_score_delta_vs_accepted_etf": round(
            after_ev - ACCEPTED_ETF_AGGREGATE_EV,
            6,
        ),
        "total_pnl_delta_vs_accepted_etf": round(
            after_pnl - ACCEPTED_ETF_AGGREGATE_PNL,
            2,
        ),
        "beats_accepted_etf_ev": after_ev > ACCEPTED_ETF_AGGREGATE_EV,
        "beats_accepted_etf_pnl": after_pnl > ACCEPTED_ETF_AGGREGATE_PNL,
    }
    gate["accepted_low_deployment_etf_comparison"] = etf_comparison
    failed = list(gate.get("failed_reasons") or [])
    if not etf_comparison["beats_accepted_etf_ev"]:
        failed.append("underperforms_accepted_low_deployment_etf_ev")
    if not etf_comparison["beats_accepted_etf_pnl"]:
        failed.append("underperforms_accepted_low_deployment_etf_pnl")
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_broad_5d_winner_exhaustion_cap"
        if gate["passed"]
        else "rejected_broad_5d_winner_exhaustion_cap_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = previous._build_payload()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Broad 5-day winner continuation has replacement value but fails "
                "drawdown; excluding parabolic signal-day winners with "
                "candidate_ret5 > 20% may preserve continuation while removing "
                "tail-risk exhaustion."
            ),
            "change_type": "default_off_broad_tail_state_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_tail_state_classifier",
            "new_evidence_type": (
                "production_visible_ohlcv_tail_classifier_for_existing_broad_momentum_pool"
            ),
            "nearby_prior_experiments": [
                "exp-20260606-004",
                "exp-20260606-005",
                "exp-20260606-006",
                "exp-20260606-010",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "accepted_low_deployment_etf_comparison": payload["gate4"].get(
                "accepted_low_deployment_etf_comparison"
            ),
            "negative_reflection": (
                "If rejected, the likely reason is that broad 5-day winner "
                "continuation is either still tail-heavy after removing only "
                "parabolic winners, or the cap removes too much of the edge. "
                "Do not answer by sweeping nearby ret5 caps, top-N, hold days, "
                "or notional on the same frozen sample."
            ),
            "next_evidence_needed": (
                "A retry needs a materially different tail classifier, such as "
                "realized drawdown contribution, breadth persistence, or forward "
                "replacement-value rows. Simple ret5 cap retunes are frozen."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "exhaustion_cap_state": "candidate_ret5_lte_20pct",
            "single_causal_variable": CHANGED_VARIABLE,
            "locked_from_exp_20260606_005": [
                "all_windows_full_liquid_common_stock_proxy",
                "formation_days",
                "top_bucket_fraction",
                "top_bucket_ranking",
                "SPY 5-day positive market confirmation",
                "candidate 20-day positive confirmation",
                "paper_notional_usd",
                "hold_days",
                "max_paper_trades_per_day",
                "same_ticker_cooldown_days",
                "same_ticker_core_overlap_exclusion",
                "min_price",
                "min_avg_dollar_volume_20d",
            ],
        }
    )
    payload["pre_run_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: the broad 5-day winner source may be useful "
            "only after removing signal-day parabolic winners that create tail "
            "drawdown."
        ),
        "2_history_check": {
            "exp-20260606-004": (
                "Rejected top-1 broad 5d winner: aggregate positive, but "
                "old_thin regressed and drawdown drift was too high."
            ),
            "exp-20260606-005": (
                "Rejected market-confirmed variant: EV +2.3453 and PnL "
                "+$36,495.37 with all windows positive, but max drawdown drift "
                "was +2.97pp."
            ),
            "exp-20260606-006": (
                "Rejected low-deployment continuation due insufficient "
                "deployment/sample."
            ),
            "exp-20260606-010": (
                "Rejected gap-down recovery because old_thin regressed; this "
                "run targets overheat/tail rather than recovery."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_success_failure_criteria": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard passes, and the after aggregate does "
            "not underperform the accepted low-deployment ETF substitute."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_014_broad_5d_winner_exhaustion_cap.py"
        ),
    }
    payload["gate_questions"] = payload["pre_run_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The exhaustion-capped broad winner source cleared the core three-window "
        "gate and beat the accepted ETF substitute as a replay-only lead; no "
        "production surface was promoted."
        if payload["gate4"]["passed"]
        else (
            "The exhaustion cap did not clear Gate 4; keep broad 5d winner "
            "continuation rejected and do not retune adjacent ret5 cap "
            "thresholds on these frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
