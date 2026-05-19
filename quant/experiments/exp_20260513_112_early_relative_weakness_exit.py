"""exp-20260513-112: early SPY-relative weakness full-exit lifecycle.

Tests one production-visible exit variable on the accepted core stack:
after the third available holding-session close, a core position that is
negative from entry and trails SPY by at least three percentage points exits at
the next session open.

This promotes the observed exp-20260513-101 loss taxonomy into a single
executable lifecycle rule. It does not change entries, ranking, candidate pool,
sizing, add-ons, LLM/news, or Space.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260513-112"
EXPERIMENT_SLUG = "early_relative_weakness_exit"
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

VARIANT_CONFIG = {
    "EARLY_RELATIVE_WEAKNESS_EXIT_ENABLED": True,
    "EARLY_RELATIVE_WEAKNESS_HOLDING_ROWS": 3,
    "EARLY_RELATIVE_WEAKNESS_MIN_RS_VS_SPY": -0.03,
    "EARLY_RELATIVE_WEAKNESS_REQUIRE_NEGATIVE_RETURN": True,
    "EARLY_RELATIVE_WEAKNESS_REDUCE_PCT": 100,
}


def _run_window(label: str, variant: bool = False) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    config = {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True}
    if variant:
        config.update(VARIANT_CONFIG)
    engine = base.BacktestEngine(
        base.get_universe(),
        start=spec["start"],
        end=spec["end"],
        config=config,
        ohlcv_snapshot_path=str(base.REPO_ROOT / spec["snapshot"]),
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{label} {'variant' if variant else 'baseline'} failed: {result['error']}")
    partial_reduce = result.get("partial_reduce_attribution") or {}
    early_events = [
        row
        for row in partial_reduce.get("events", []) or []
        if row.get("exit_reason") == "early_relative_weakness_exit"
    ]
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "partial_reduce_attribution": partial_reduce,
        "early_relative_weakness_events": early_events,
    }


def _payload() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, variant=False) for label in base.WINDOWS}
    after_runs = {label: _run_window(label, variant=True) for label in base.WINDOWS}
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics = {label: after_runs[label]["metrics"] for label in base.WINDOWS}
    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in base.WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    total_executed_events = sum(
        1
        for label in base.WINDOWS
        for event in after_runs[label]["early_relative_weakness_events"]
        if event.get("status") == "executed"
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and total_executed_events > 0
        and max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    decision = (
        "accepted_shared_policy_early_relative_weakness_exit"
        if passed
        else "rejected_early_relative_weakness_exit"
    )
    interpretation = (
        "The early relative-weakness full exit improved aggregate EV/PnL with no EV-regressed windows and drawdown drift inside guardrail."
        if passed
        else "The early relative-weakness full exit did not clear the canonical three-window Gate 4."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Fresh accepted core positions that are still negative and lag SPY by "
            "at least three percentage points after their third holding-session "
            "close have lost replacement value and should free capital at the next open."
        ),
        "change_type": "exit",
        "changed_variable": "early_relative_weakness_full_exit",
        "single_causal_variable": (
            "next-open full exit for core positions matching the exp-20260513-101 "
            "early SPY-relative underperformance family"
        ),
        "parameters": {
            **VARIANT_CONFIG,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "target and stop geometry",
                "follow-through add-ons",
                "LLM/news replay",
                "Space sleeve",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "core exit/risk allocation: early post-entry SPY-relative weakness marks decaying replacement value.",
            "2_history_check": {
                "exp-20260513-101": "observed-only taxonomy found this family concentrated losses and tail risk with no family winners.",
                "exp-20260506-007": "post-addon weakness trimming was rejected; this test is not addon-specific and acts on the whole fresh core position.",
                "exp-20260429-032": "bare SIGNAL_TARGET partial reduce was rejected; this test uses a different early relative-weakness lifecycle state.",
            },
            "3_single_causal_variable": "one fixed full-exit trigger: 3 holding rows, ticker return < 0, ticker minus SPY <= -3 percentage points.",
            "4_acceptance_standard": "docs/backtesting.md fixed three windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 percentage points.",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_112_early_relative_weakness_exit.py",
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": aggregate_before,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "position entry_date",
                "position target_price",
                "position avg_cost / entry_price",
                "ticker OHLCV through trigger close",
                "SPY OHLCV through trigger close",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": aggregate_delta["signals_generated_sum"],
            "signals_survived_delta": aggregate_delta["signals_survived_sum"],
            "minimum_after_survival_rate": aggregate_after["survival_rate_min"],
            "passed": aggregate_after["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "early_exit_executed_events": total_executed_events,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "drawdown_guardrail_passed": max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "changed_trades": {
            label: base._changed_trades(
                before_runs[label]["trades"],
                after_runs[label]["trades"],
            )
            for label in base.WINDOWS
        },
        "early_relative_weakness_events": {
            label: after_runs[label]["early_relative_weakness_events"]
            for label in base.WINDOWS
        },
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": True,
            "run_adapter_changed": passed,
            "replay_only": not passed,
            "parity_test_added": passed,
            "promotion_requirement": (
                "If accepted, keep production_parity.py as the shared policy and "
                "wire quant/run.py to emit the same next-open EXIT actions."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else "Do not retune adjacent early-weakness thresholds without forward lifecycle attribution.",
        "related_files": [
            "quant/production_parity.py",
            "quant/backtester.py",
            "quant/experiments/exp_20260513_112_early_relative_weakness_exit.py",
            "data/experiments/exp-20260513-112/early_relative_weakness_exit.json",
            "experiments/logs/exp-20260513-112.json",
            "experiments/tickets/exp-20260513-112.json",
            "experiments/artifacts/exp-20260513-112_early_relative_weakness_exit.md",
            "docs/experiment_log.jsonl",
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Exits |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        exits = sum(
            1
            for event in payload["early_relative_weakness_events"][label]
            if event.get("status") == "executed"
        )
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {exits} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                exits=exits,
            )
        )
    agg = payload["delta_metrics"]["aggregate_delta"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Early Relative-Weakness Exit",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: next-open full exit for fresh core positions with negative day-3 holding return and <= -3pp return versus SPY.",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- Expected value score delta: {agg['expected_value_score_sum']:+.4f}",
            f"- Total PnL delta: ${agg['total_pnl_sum']:+,.2f}",
            f"- Executed early exits: {payload['gate4']['early_exit_executed_events']}",
            f"- Max drawdown worse: {payload['gate4']['max_drawdown_worse']:+.4f}",
            "",
            f"Interpretation: {payload['interpretation']}",
            "",
            "Production impact: accepted only if the shared production_parity helper is wired into quant/run.py and covered by parity tests.",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = (
        base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    )
    ticket_path = (
        base.REPO_ROOT
        / "experiments"
        / "tickets"
        / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    base._upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = _payload()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "early_exit_executed_events": result["gate4"]["early_exit_executed_events"],
            },
            indent=2,
            sort_keys=True,
        )
    )
