"""exp-20260630-020: high-risk gated early relative-weakness exit.

Tests one exit lifecycle hypothesis on the accepted core stack: among fresh
core positions that already fail the existing day-3 SPY-relative weakness
check, exit only those with production-known actual account risk >= 2%.

The rule uses the shared early-relative-weakness helper and keeps entries,
ranking, sizing, target/stop geometry, add-ons, LLM/news, and live/default
orders unchanged.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260630_012_close_confirmed_static_stop as replay_base


EXPERIMENT_ID = "exp-20260630-020"
OWNER = "alpha-explore"
SLUG = "high_actual_risk_early_relative_weakness_exit"
RUNNER = f"quant/experiments/exp_20260630_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = replay_base.REPO_ROOT
BASELINE_RESULT = replay_base.BASELINE_RESULT
WINDOWS = replay_base.WINDOWS
OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260630_020_{SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HIGH_ACTUAL_RISK_THRESHOLD = 0.02
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
BASE_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "REPLAY_PARTIAL_REDUCES": True,
}
VARIANT_CONFIG = {
    **BASE_CONFIG,
    "EARLY_RELATIVE_WEAKNESS_EXIT_ENABLED": True,
    "EARLY_RELATIVE_WEAKNESS_HOLDING_ROWS": 3,
    "EARLY_RELATIVE_WEAKNESS_MIN_RS_VS_SPY": -0.03,
    "EARLY_RELATIVE_WEAKNESS_REQUIRE_NEGATIVE_RETURN": True,
    "EARLY_RELATIVE_WEAKNESS_REDUCE_PCT": 100,
    "EARLY_RELATIVE_WEAKNESS_MIN_ACTUAL_RISK_PCT": HIGH_ACTUAL_RISK_THRESHOLD,
}

HYPOTHESIS = (
    "High account-risk positions that also fail the existing day-3 "
    "SPY-relative weakness check may be the actionable subset behind the "
    "exp-20260630-018 oracle-regret lead; exiting only that subset next open "
    "could reduce avoidable loss without the broad winner collateral that "
    "killed bare early-weakness exits."
)
CHANGE_TYPE = "exit_policy_shared_gate"
IMPLEMENTATION_MODE = "shared_helper_historical_replay"
MECHANISM_FAMILY = "exit_policy_oracle_diagnostic"
TRIAL_FAMILY = "high_account_risk_early_relative_weakness_exit"
TRIAL_VARIANT_ID = "actual_risk_ge_2pct_day3_rs_weak_full_exit_v1"
CHANGED_VARIABLE = "high_actual_risk_early_relative_weakness_exit_v1"
NEW_EVIDENCE_TYPE = "full_trade_oracle_denominator_account_risk_cohort"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-018",
    "exp-20260513-112",
    "exp-20260630-012",
    "exp-20260630-011",
]
CAUSAL_COMPONENTS = [
    "shared early-relative-weakness helper",
    "production-known actual_risk_pct >= 2%",
    "fixed day-3 negative return and SPY-relative weakness trigger",
    "next-session open full exit",
    "no entry ranking sizing target stop or candidate-pool change",
]


def repo_rel(path: Path | str) -> str:
    return replay_base.repo_rel(path)


def read_json(path: Path, default: Any = None) -> Any:
    return replay_base.read_json(path, default)


def write_json(path: Path, payload: Any) -> None:
    replay_base.write_json(path, payload)


def write_text(path: Path, text: str) -> None:
    replay_base.write_text(path, text)


def safe(value: Any) -> Any:
    return replay_base.safe(value)


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.24,
        "main_failure_modes": [
            "thin_subset",
            "no_changed_trades",
            "winner_collateral",
            "old_thin_regression",
            "not_incremental_vs_rejected_early_weakness",
        ],
        "confidence_reason": (
            "exp-20260630-018 found higher oracle regret in high actual-risk "
            "trades, but the ungated early-weakness rule was already rejected."
        ),
    }


def run_window(label: str, config: dict[str, Any]) -> dict[str, Any]:
    result = replay_base.run_window(label, config)
    partial_reduce = result.get("partial_reduce_attribution") or {}
    events = partial_reduce.get("events") or []
    high_risk_events = [
        row
        for row in events
        if row.get("exit_reason") == "early_relative_weakness_exit"
        and row.get("min_actual_risk_pct") == HIGH_ACTUAL_RISK_THRESHOLD
    ]
    result["high_risk_early_weakness_events"] = high_risk_events
    return result


def event_summary(after_runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    all_events = [
        row
        for run in after_runs.values()
        for row in run.get("high_risk_early_weakness_events", [])
    ]
    executed = [row for row in all_events if row.get("status") == "executed"]
    by_window = {
        label: {
            "scheduled": len(run.get("high_risk_early_weakness_events", [])),
            "executed": sum(
                1
                for row in run.get("high_risk_early_weakness_events", [])
                if row.get("status") == "executed"
            ),
        }
        for label, run in after_runs.items()
    }
    by_ticker = Counter(row.get("ticker") or "UNKNOWN" for row in executed)
    return {
        "scheduled_event_count": len(all_events),
        "executed_event_count": len(executed),
        "by_window": by_window,
        "by_ticker": dict(by_ticker.most_common()),
        "sample_events": executed[:20],
    }


def make_payload() -> dict[str, Any]:
    gate2 = replay_base.audit_open_positions()
    before_runs = {label: run_window(label, BASE_CONFIG) for label in WINDOWS}
    after_runs = {label: run_window(label, VARIANT_CONFIG) for label in WINDOWS}
    before_metrics = {label: before_runs[label]["metrics"] for label in WINDOWS}
    after_metrics = {label: after_runs[label]["metrics"] for label in WINDOWS}
    by_window_delta = {
        label: replay_base.delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = replay_base.aggregate(before_metrics)
    aggregate_after = replay_base.aggregate(after_metrics)
    aggregate_delta = replay_base.delta(aggregate_after, aggregate_before)
    changed = {
        label: replay_base.changed_trades(
            before_runs[label]["trades"],
            after_runs[label]["trades"],
        )
        for label in WINDOWS
    }
    changed_summary = replay_base.summarize_changed(changed)
    events = event_summary(after_runs)
    improved_windows = [
        label
        for label in WINDOWS
        if float(after_metrics[label].get("expected_value_score") or 0.0)
        > float(before_metrics[label].get("expected_value_score") or 0.0)
    ]
    regressed_windows = [
        label
        for label in WINDOWS
        if float(after_metrics[label].get("expected_value_score") or 0.0)
        < float(before_metrics[label].get("expected_value_score") or 0.0)
    ]
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in WINDOWS
    )
    gate4_passed = (
        float(aggregate_delta.get("expected_value_score_sum") or 0.0) > 0
        and float(aggregate_delta.get("total_pnl_sum") or 0.0) > 0
        and len(improved_windows) >= 2
        and not regressed_windows
        and aggregate_after["survival_rate_min"] >= 0.05
        and max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
        and events["executed_event_count"] > 0
    )
    failed_reasons: list[str] = []
    if float(aggregate_delta.get("expected_value_score_sum") or 0.0) <= 0:
        failed_reasons.append("aggregate_ev_not_positive")
    if float(aggregate_delta.get("total_pnl_sum") or 0.0) <= 0:
        failed_reasons.append("aggregate_pnl_not_positive")
    if len(improved_windows) < 2:
        failed_reasons.append("fewer_than_two_ev_improved_windows")
    if regressed_windows:
        failed_reasons.append("window_ev_regression")
    if aggregate_after["survival_rate_min"] < 0.05:
        failed_reasons.append("survival_below_floor")
    if max_drawdown_worse > MAX_DRAWDOWN_WORSE_GUARDRAIL:
        failed_reasons.append("drawdown_worse_than_guardrail")
    if events["executed_event_count"] <= 0:
        failed_reasons.append("no_executed_high_risk_early_weakness_exits")

    prediction = load_ticket_prediction()
    predicted_p = float(prediction.get("success_probability") or 0.0)
    decision = (
        "accepted_shared_default_off_high_risk_early_relative_weakness_exit"
        if gate4_passed
        else "rejected_high_actual_risk_early_relative_weakness_exit"
    )
    status = "accepted" if gate4_passed else "rejected"

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": replay_base.utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": gate4_passed,
        "accepted_alpha": gate4_passed,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": 1 if gate4_passed else 0,
            "predicted_success_probability": predicted_p,
            "brier_score": round(((1 if gate4_passed else 0) - predicted_p) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(failed_reasons)
            ),
            "actual_ev_delta": aggregate_delta.get("expected_value_score_sum"),
            "actual_pnl_delta": aggregate_delta.get("total_pnl_sum"),
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "before_config": BASE_CONFIG,
            "after_config": VARIANT_CONFIG,
            "high_actual_risk_threshold": HIGH_ACTUAL_RISK_THRESHOLD,
            "windows": {
                label: {**spec, "snapshot": repo_rel(spec["snapshot"])}
                for label, spec in WINDOWS.items()
            },
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "acceptance_rule": (
                "Aggregate EV and PnL positive, at least two EV-improved "
                "windows, no EV-regressed windows, survival >= 5%, max "
                "drawdown drift <= 0.5pp, and at least one executed high-risk "
                "early-weakness exit."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Exit policy: high actual-risk positions may be the subset "
                "where early relative weakness identifies avoidable regret."
            ),
            "2_history_check": {
                "novelty_gate": "experiment.py new passed without override.",
                "exp-20260630-018": (
                    "Observed-only oracle diagnostic accepted a lead: "
                    "actual_risk_pct >= 2% had higher exit regret across all windows."
                ),
                "exp-20260513-112": (
                    "Bare day-3 early relative-weakness full exit rejected; "
                    "this test adds the new production-known account-risk cohort."
                ),
                "exp-20260630-012": "Close-confirmed static stop rejected.",
                "exp-20260630-011": (
                    "Full trade-level oracle denominator materialized the "
                    "risk/regret evidence and froze adjacent stop/target retunes."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "docs/backtesting.md Gate 1-4 on the three fixed windows."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "before_metrics": before_metrics,
            "baseline_aggregate": aggregate_before,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "entry_date",
                "target_price",
                "avg_cost / entry_price",
                "actual_risk_pct",
                "ticker OHLCV through trigger close",
                "SPY OHLCV through trigger close",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_entry_filter_added": False,
            "signals_generated_delta": aggregate_delta.get("signals_generated_sum"),
            "signals_survived_delta": aggregate_delta.get("signals_survived_sum"),
            "minimum_after_survival_rate": aggregate_after["survival_rate_min"],
            "passed": aggregate_after["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": gate4_passed,
            "failed_reasons": failed_reasons,
            "improved_windows": improved_windows,
            "regressed_windows": regressed_windows,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "drawdown_guardrail_passed": (
                max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
            ),
            "high_risk_early_weakness_events": events,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
            "changed_trades": changed_summary,
        },
        "changed_trades_by_window": changed,
        "expected_value_score_delta": aggregate_delta.get("expected_value_score_sum"),
        "total_pnl_delta": aggregate_delta.get("total_pnl_sum"),
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_helper_extended": True,
            "default_strategy_behavior_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": True,
            "live_orders_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "activation_envelope": {
                "intended_notional": "same as current core position sizing if ever promoted",
                "capital_cap": "same as current core strategy if ever promoted",
                "liquidity_slippage_model": (
                    "next-session open market sell with existing backtester "
                    "slippage model"
                ),
                "portfolio_displacement": (
                    "same entries and slots; only earlier exit can free capital"
                ),
                "order_semantics": (
                    "day-3 close decision, next-session market sell for full "
                    "position when actual_risk_pct >= 2%, ticker return < 0, "
                    "and ticker return minus SPY return <= -3pp"
                ),
                "failure_handling": (
                    "if OHLCV, entry_date, SPY, or actual_risk_pct is missing, "
                    "the helper skips or rejects the action and leaves the "
                    "position untouched"
                ),
                "kill_switch": (
                    "do not promote if any canonical window EV regresses or "
                    "drawdown worsens over 0.5pp"
                ),
            },
            "parity_note": (
                "Shared helper and backtester adapter are present, but run.py "
                "does not emit this default-off action; live readiness would "
                "require explicit daily adapter wiring after a positive Gate 4."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The high-risk gate isolated a profitable subset of early "
                "relative-weakness exits."
                if gate4_passed
                else "The high-risk gate did not overcome the broad early-weakness exit weakness."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune early-weakness holding rows, SPY threshold, "
                "stop distance, target trims, or response curves on the same "
                "fixed-entry rows."
            ),
            "new_evidence_required": (
                "A legal retry needs materially more settled forward shadow-exit "
                "rows, a new pre-exit signal, or a different non-saturated data source."
            ),
        },
        "rejection_reason": None if gate4_passed else ";".join(failed_reasons),
        "next_retry_requires": [
            "settled forward shadow-exit rows for the high-risk lifecycle",
            "a new pre-exit signal beyond actual_risk_pct and SPY-relative weakness",
            "daily run.py adapter wiring only after positive Gate 4 evidence",
        ],
        "before_after_strategy_behavior_changed": True,
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
            "quant/production_parity.py",
            "quant/backtester.py",
            "quant/test_production_parity.py",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest "
            + "quant\\test_production_parity.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def make_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades d | Events |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        dlt = payload["delta_metrics"]["by_window"][label]
        event_count = payload["gate4"]["high_risk_early_weakness_events"]["by_window"][label][
            "executed"
        ]
        rows.append(
            f"| {label} | {before.get('expected_value_score')} | "
            f"{after.get('expected_value_score')} | {dlt.get('expected_value_score')} | "
            f"{before.get('total_pnl')} | {after.get('total_pnl')} | "
            f"{dlt.get('total_pnl')} | {dlt.get('max_drawdown_pct')} | "
            f"{dlt.get('trade_count')} | {event_count} |"
        )
    agg = payload["delta_metrics"]["aggregate_delta"]
    events = payload["gate4"]["high_risk_early_weakness_events"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} high actual-risk early relative weakness exit",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            HYPOTHESIS,
            "",
            *rows,
            "",
            "Aggregate delta: "
            f"EV `{agg.get('expected_value_score_sum')}`, "
            f"PnL `{agg.get('total_pnl_sum')}`, "
            f"executed events `{events.get('executed_event_count')}`, "
            f"changed trades `{payload['delta_metrics']['changed_trades']['changed_trade_count']}`.",
            "",
            "Production boundary: default behavior and live orders are unchanged. "
            "The helper is shared/default-off; live readiness would still require "
            "daily run.py adapter wiring after positive evidence.",
        ]
    ) + "\n"


def make_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REPO_ROOT / "quant" / "production_parity.py",
        REPO_ROOT / "quant" / "backtester.py",
        REPO_ROOT / "quant" / "test_production_parity.py",
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": replay_base.utc_now(),
        "files": [
            {
                "path": repo_rel(path),
                "exists": (REPO_ROOT / path if not path.is_absolute() else path).exists(),
                "sha256": replay_base.sha256(
                    REPO_ROOT / path if not path.is_absolute() else path
                ),
            }
            for path in files
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_text(CARD_MD, make_card(payload))
    write_json(MANIFEST_JSON, make_manifest(payload))
    replay_base.save_experiment_log_entry(payload, allow_duplicate=True)
    replay_base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload.get("prediction") or {},
        result=payload,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "accepted_alpha": payload["accepted_alpha"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> None:
    payload = make_payload()
    persist(payload)
    print(json.dumps(safe({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "aggregate_delta": payload["delta_metrics"]["aggregate_delta"],
        "executed_event_count": payload["gate4"]["high_risk_early_weakness_events"][
            "executed_event_count"
        ],
        "changed_trade_count": payload["delta_metrics"]["changed_trades"][
            "changed_trade_count"
        ],
        "artifact": payload["artifact"],
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
