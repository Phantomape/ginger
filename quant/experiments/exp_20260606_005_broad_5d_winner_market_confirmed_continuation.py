"""exp-20260606-005: market-confirmed broad 5-day winner continuation.

Replay-only alpha search. This follows the rejected exp-20260606-004 broad
5-day winner-continuation source, but admits candidates only when the signal
date has positive SPY 5-day tape and the candidate has positive 20-day trend.

The only alpha variable is the production-visible market-confirmation state.
Ticker pool, top-bucket construction, next-open entry, hold, notional,
cooldown, core-overlap controls, LLM/news behavior, and production code stay
unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260606_004_broad_5d_winner_continuation_candidate_pool as previous
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260606-005"
STEM = "broad_5d_winner_market_confirmed_continuation"
TRIAL_FAMILY = "broad_full_liquid_5d_winner_market_confirmed_continuation_candidate_pool"
TRIAL_VARIANT_ID = "spy5_positive_candidate_ret20_positive_v1"
CHANGED_VARIABLE = "broad_5d_winner_spy5_positive_candidate_ret20_positive_state_v1"
RULE_VERSION = "broad_5d_winner_market_confirmed_continuation_v1"

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_SPY_RET5 = 0.0
MIN_CANDIDATE_RET20 = 0.0

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "old_thin_regression",
        "drawdown_drift_too_high",
        "not_incremental_over_ret20",
        "window_regression",
    ],
    "confidence_reason": (
        "exp-20260606-004 had broad sample and positive aggregate EV/PnL but "
        "failed old_thin and drawdown; a market-confirmed continuation state is "
        "production-visible and directly targets that failure without changing "
        "ETF/Companyfacts/SEC/FINRA frozen families."
    ),
    "recorded_at": "2026-06-06T03:07:37Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same broad "
        "warehouse all-windows-full-liquid stock universe, SPY 5-day market "
        "confirmation state, candidate 20-day trend state, 5-day SPY-relative "
        "rank, next-open paper entry, 10-trading-day exit, costs, cooldown, and "
        "core-overlap controls in both replay and daily production before any "
        "report queue, paper ledger, candidate priority, sizing, watchlist, or "
        "order surface could change."
    ),
}

BASE_CANDIDATE_ROWS = previous._candidate_rows_for_window
BASE_GATE4 = previous._gate4
BASE_BUILD_PAYLOAD = previous._build_payload


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, contexts, scan = BASE_CANDIDATE_ROWS(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    contexts_by_date = {str(row.get("date")): row for row in contexts if isinstance(row, dict)}
    kept: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()
    for candidate in candidates:
        context = contexts_by_date.get(str(candidate.get("date")))
        spy_ret5 = framework._round((context or {}).get("spy_ret5"), 10)
        candidate_ret20 = framework._round(candidate.get("candidate_ret20"), 10)
        if spy_ret5 is None:
            rejects["missing_spy_ret5_context"] += 1
            continue
        if spy_ret5 <= MIN_SPY_RET5:
            rejects["spy_5d_not_positive"] += 1
            continue
        if candidate_ret20 is None:
            rejects["missing_candidate_ret20"] += 1
            continue
        if candidate_ret20 <= MIN_CANDIDATE_RET20:
            rejects["candidate_ret20_not_positive"] += 1
            continue
        row = dict(candidate)
        row.update(
            {
                "source": STEM,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "market_confirmation_state": "spy5_positive_candidate_ret20_positive",
                "market_confirmation_rule_version": RULE_VERSION,
                "spy_5d_return": spy_ret5,
                "candidate_20d_return": candidate_ret20,
            }
        )
        kept.append(row)
    scan = dict(scan)
    scan["market_confirmation_reject_counts"] = dict(sorted(rejects.items()))
    scan["market_confirmation_kept_candidates"] = len(kept)
    scan["market_confirmation_rule_version"] = RULE_VERSION
    return kept, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_broad_5d_market_confirmed_continuation"
        if gate["passed"]
        else "rejected_broad_5d_market_confirmed_continuation_candidate_pool"
    )
    return gate


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Broad 5-day winner continuation may become production-executable "
                "only when the signal-date SPY 5-day tape is positive and the "
                "candidate's own 20-day trend is positive, reducing old-window "
                "momentum crash risk without changing the ticker pool, hold, "
                "notional, cooldown, or ranking source."
            ),
            "change_type": "default_off_broad_market_confirmed_continuation_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "short_formation_continuation_market_state",
            "new_evidence_type": "materially_new_production_visible_market_confirmation_state",
            "nearby_prior_experiments": [
                "exp-20260606-004",
                "exp-20260605-033",
                "exp-20260602-015",
                "exp-20260605-013",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that the broad 5-day winner "
                "lead is still not incremental over ordinary medium-term "
                "momentum or carries old-window crash/giveback risk even when "
                "the market tape agrees. Do not respond by retuning top-N, "
                "hold days, notional, SPY threshold, or ret20 threshold on the "
                "same frozen sample."
            ),
            "next_evidence_needed": (
                "A retry needs a materially new PIT state field such as "
                "breadth/changepoint persistence, cost-adjusted replacement "
                "rows, or forward replacement-value evidence; do not simply "
                "retune broad OHLCV momentum thresholds on these windows."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "market_confirmation_state": "spy5_positive_candidate_ret20_positive",
            "min_spy_5d_return": MIN_SPY_RET5,
            "min_candidate_20d_return": MIN_CANDIDATE_RET20,
            "single_causal_variable": CHANGED_VARIABLE,
            "locked_from_exp_20260606_004": [
                "all_windows_full_liquid_common_stock_proxy",
                "formation_days",
                "top_bucket_fraction",
                "top_bucket_ranking",
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
            "entry/candidate_pool: broad 5-day winners continue only in a "
            "positive SPY 5-day tape and with positive candidate 20-day trend; "
            "this is a production-visible market-confirmation state, not a "
            "new ticker/noise expansion."
        ),
        "2_history_check": {
            "exp-20260606-004": (
                "Rejected: aggregate EV +1.9754 and PnL +$25,210.26, but "
                "old_thin EV/PnL regressed and max drawdown worsened +7.63pp."
            ),
            "exp-20260605-033": (
                "Rejected pressure-resilience candidate pool; broad pressure "
                "reversal/resilience did not clear any window."
            ),
            "exp-20260602-015": (
                "Rejected RS acceleration: good mid_weak but late_strong and "
                "old_thin regressed with drawdown damage."
            ),
            "exp-20260605-013": (
                "Rejected low-beta residual momentum: aggregate EV positive, "
                "but PnL and two windows regressed."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_success_failure_criteria": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_005_broad_5d_winner_market_confirmed_continuation.py"
        ),
    }
    payload["gate_questions"] = payload["pre_run_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The market-confirmed 5-day winner-continuation candidate pool cleared "
        "Gate 4 as a replay-only/default-off lead, but no production surface "
        "was promoted."
        if payload["gate4"]["passed"]
        else (
            "The market-confirmed 5-day winner-continuation candidate pool did "
            "not clear Gate 4; do not promote or locally retune this broad "
            "OHLCV momentum family on the frozen windows."
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
