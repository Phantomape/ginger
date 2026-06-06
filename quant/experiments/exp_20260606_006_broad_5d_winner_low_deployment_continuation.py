"""exp-20260606-006: low-deployment broad 5-day winner continuation.

Replay-only alpha search. This follows the rejected exp-20260606-005 broad
5-day market-confirmed winner-continuation source, but admits candidates only
when the accepted core stack is in the same low-deployment state used by the
accepted ETF cash-substitute adapter.

The only alpha variable is the production-visible low-core-deployment state.
Ticker pool, market confirmation, top-bucket construction, next-open entry,
hold, notional, cooldown, core-overlap controls, LLM/news behavior, and
production code stay unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260606_005_broad_5d_winner_market_confirmed_continuation as previous
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
from low_deployment_etf_overlay import _core_active_count_by_date, _core_deployment_context


EXPERIMENT_ID = "exp-20260606-006"
STEM = "broad_5d_winner_low_deployment_continuation"
TRIAL_FAMILY = "broad_full_liquid_5d_winner_low_deployment_continuation_candidate_pool"
TRIAL_VARIANT_ID = "low_core_deployment_market_confirmed_v1"
CHANGED_VARIABLE = "broad_5d_market_confirmed_winner_low_core_deployment_gate_v1"
RULE_VERSION = "broad_5d_winner_low_deployment_continuation_v1"

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_006_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MAX_ACTIVE_CORE_POSITIONS = 1
LOW_DEPLOYMENT_CONFIG = {
    "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
    "sleeve_slot_capacity": 1,
}

PREDICTION = {
    "success_probability": 0.26,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "drawdown_drift_too_high",
        "not_incremental_over_low_deployment_etf",
        "old_thin_regression",
    ],
    "confidence_reason": (
        "exp-20260606-005 improved EV/PnL in all windows but failed drawdown; "
        "exp-20260606-001 shows low-deployment state has replacement value, "
        "but applying it to broad stock continuation may thin the sample or "
        "keep old-window tail risk."
    ),
    "recorded_at": "2026-06-06T04:06:19Z",
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
        "warehouse full-liquid stock universe, SPY 5-day market confirmation, "
        "candidate 20-day trend state, active-core-position deployment state, "
        "5-day SPY-relative rank, next-open paper entry, 10-trading-day exit, "
        "costs, cooldown, and core-overlap controls in both replay and daily "
        "production before any report queue, paper ledger, candidate priority, "
        "sizing, watchlist, or order surface could change."
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
    active_counts = _core_active_count_by_date(before_result)
    kept: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()
    low_deployment_days = 0
    seen_dates: set[str] = set()

    for candidate in candidates:
        signal_date = str(candidate.get("date") or "")
        active_core_positions = int(active_counts.get(signal_date, 0))
        deployment_context = _core_deployment_context(
            active_core_positions,
            LOW_DEPLOYMENT_CONFIG,
        )
        if signal_date and signal_date not in seen_dates:
            seen_dates.add(signal_date)
            if deployment_context["low_deployment_condition_passed"]:
                low_deployment_days += 1
        if not deployment_context["low_deployment_condition_passed"]:
            rejects["core_above_low_deployment_threshold"] += 1
            continue
        row = dict(candidate)
        row.update(
            {
                "source": STEM,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "low_deployment_rule_version": RULE_VERSION,
                "active_core_positions_on_signal": active_core_positions,
                "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
                "low_deployment_condition_passed": True,
                "low_deployment_condition_status": deployment_context[
                    "low_deployment_condition_status"
                ],
                "core_deployment_context": deployment_context,
            }
        )
        kept.append(row)

    scan = dict(scan)
    scan["low_deployment_reject_counts"] = dict(sorted(rejects.items()))
    scan["low_deployment_kept_candidates"] = len(kept)
    scan["low_deployment_candidate_count_before_gate"] = len(candidates)
    scan["low_deployment_day_count"] = low_deployment_days
    scan["max_active_core_positions"] = MAX_ACTIVE_CORE_POSITIONS
    scan["low_deployment_rule_version"] = RULE_VERSION
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
        "positive_replay_lead_not_promoted_broad_5d_low_deployment_continuation"
        if gate["passed"]
        else "rejected_broad_5d_low_deployment_continuation_candidate_pool"
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
                "Broad 5-day market-confirmed winner continuation may only be "
                "worth paper capital when the accepted core stack is "
                "underdeployed, preserving the exp-20260606-005 continuation "
                "edge while reducing drawdown by restricting entries to "
                "low-deployment states."
            ),
            "change_type": "default_off_candidate_pool_state_gate",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "short_formation_continuation_low_deployment_state",
            "new_evidence_type": "materially_new_production_visible_deployment_state",
            "nearby_prior_experiments": [
                "exp-20260606-005",
                "exp-20260606-004",
                "exp-20260605-035",
                "exp-20260606-001",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the broad 5-day winner source remains too "
                "tail-sensitive or too thin even when limited to low core "
                "deployment. Do not respond by retuning SPY 5-day, candidate "
                "ret20, top-N, hold days, notional, or cooldown thresholds on "
                "the same frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs a materially new PIT data edge or forward "
                "replacement-value rows. Local broad OHLCV continuation retunes "
                "should stay frozen after exp-20260606-004/005/006."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "low_deployment_gate": "active_core_positions <= 1",
            "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
            "market_confirmation_state_locked_from_exp_20260606_005": (
                "spy5_positive_candidate_ret20_positive"
            ),
            "single_causal_variable": CHANGED_VARIABLE,
            "locked_from_exp_20260606_005": [
                "all_windows_full_liquid_common_stock_proxy",
                "formation_days",
                "top_bucket_fraction",
                "market_confirmation_state",
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
            "entry/candidate_pool: market-confirmed broad 5-day winners are "
            "only worth default-off paper capital when the core stack is "
            "underdeployed; this borrows the accepted idle-cash state but does "
            "not change ETF, core, live, or production behavior."
        ),
        "2_history_check": {
            "exp-20260606-005": (
                "Rejected: all three windows improved, aggregate EV +2.3453 "
                "and PnL +$36,495.37, but max drawdown drift was +2.97pp."
            ),
            "exp-20260606-004": (
                "Rejected: broad 5-day winner continuation improved aggregate "
                "EV/PnL but regressed old_thin and worsened drawdown +7.63pp."
            ),
            "exp-20260605-035": (
                "Accepted replay lead: low-deployment ETF cash substitute "
                "showed idle-cash replacement value."
            ),
            "exp-20260606-001": (
                "Accepted shared default-off adapter for the same "
                "active_core_positions <= 1 state, no live orders."
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
            "exp_20260606_006_broad_5d_winner_low_deployment_continuation.py"
        ),
    }
    payload["gate_questions"] = payload["pre_run_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The low-deployment broad winner-continuation source cleared Gate 4 as "
        "a replay-only/default-off lead, but no production surface was promoted."
        if payload["gate4"]["passed"]
        else (
            "The low-deployment broad winner-continuation source did not clear "
            "Gate 4; do not promote or locally retune this broad OHLCV "
            "momentum family on the frozen windows."
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Low-deploy days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=scan.get("low_deployment_day_count", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Broad 5D Winner Low-Deployment Continuation",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "low_deployment_day_count": payload["context_scan_by_window"][label].get(
                    "low_deployment_day_count"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }


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
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
