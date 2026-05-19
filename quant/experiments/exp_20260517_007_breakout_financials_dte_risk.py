"""exp-20260517-007: breakout Financials DTE risk scalar scout.

Tests one existing production-visible allocation variable on the accepted core
stack: the already implemented breakout_long + Financials + 8-14 DTE risk
multiplier. This is a scout only; promotion requires enough affected samples
and a shared constants change followed by the canonical three-window replay.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260517-007"
EXPERIMENT_SLUG = "breakout_financials_dte_risk"
MULTIPLIER_KEY = "breakout_financials_dte_risk_multiplier_applied"
BASELINE_RISK_MULTIPLIER = 0.25
RISK_MULTIPLIER_SWEEP = [0.0, 0.125, 0.25, 0.5]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 3
MIN_AFFECTED_WINDOW_COUNT = 2
WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}


def _set_multiplier(multiplier: float) -> float:
    original = base.portfolio_engine.BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER
    base.portfolio_engine.BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER = multiplier
    return original


def _run_window_with_multiplier(label: str, multiplier: float) -> dict[str, Any]:
    original = _set_multiplier(multiplier)
    original_windows = base.WINDOWS
    base.WINDOWS = WINDOWS
    try:
        return base._run_window(label, variant=False)
    finally:
        base.WINDOWS = original_windows
        base.portfolio_engine.BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER = original


def _rule_signal_count(sizing_attribution: dict[str, Any]) -> int:
    signal_attr = (sizing_attribution or {}).get("signal") or {}
    return int(
        signal_attr.get("signals_seen")
        or signal_attr.get("seen_count")
        or signal_attr.get("seen")
        or 0
    )


def _has_trade_changes(changed_trade_summary: dict[str, Any]) -> bool:
    for key in (
        "common_pnl_changed_count",
        "added_count",
        "removed_count",
    ):
        if int(changed_trade_summary.get(key) or 0) > 0:
            return True
    for key in ("common_changed", "common_pnl_changed", "added", "removed"):
        value = changed_trade_summary.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def _candidate_payload(
    multiplier: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in WINDOWS:
        variant = _run_window_with_multiplier(label, multiplier)
        after_metrics[label] = variant["metrics"]
        changed_trades[label] = base._changed_trades(
            before_runs[label]["trades"],
            variant["trades"],
        )
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
        }

    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    affected_windows = [
        label
        for label, rows in changed_trades.items()
        if _has_trade_changes(rows)
    ]
    affected_signal_count = sum(
        _rule_signal_count(sizing_attribution[label]) for label in WINDOWS
    )
    max_drawdown_worse = max(
        float(delta.get("max_drawdown_pct") or 0.0)
        for delta in by_window_delta.values()
    )
    is_identity_control = math.isclose(multiplier, BASELINE_RISK_MULTIPLIER)
    sample_guard_passed = (
        affected_signal_count >= MIN_AFFECTED_SIGNAL_COUNT
        and len(affected_windows) >= MIN_AFFECTED_WINDOW_COUNT
    )
    drawdown_guardrail_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    passed = (
        not is_identity_control
        and aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and sample_guard_passed
        and drawdown_guardrail_passed
    )
    return {
        "risk_multiplier": multiplier,
        "is_identity_control": is_identity_control,
        "passed": passed,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "changed_trades": changed_trades,
        "sizing_attribution": sizing_attribution,
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "affected_windows": affected_windows,
            "affected_signal_count": affected_signal_count,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "sample_guard_passed": sample_guard_passed,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in candidates if row["passed"]]
    if passing:
        return max(
            passing,
            key=lambda row: row["delta_metrics"]["aggregate_delta"][
                "expected_value_score_sum"
            ],
        )
    non_controls = [row for row in candidates if not row["is_identity_control"]]
    return max(
        non_controls,
        key=lambda row: row["delta_metrics"]["aggregate_delta"][
            "expected_value_score_sum"
        ],
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in candidates:
        agg = row["delta_metrics"]["aggregate_delta"]
        rows.append(
            {
                "risk_multiplier": row["risk_multiplier"],
                "is_identity_control": row["is_identity_control"],
                "passed": row["passed"],
                "expected_value_score_delta": agg["expected_value_score_sum"],
                "total_pnl_delta": agg["total_pnl_sum"],
                "improved_windows": row["gate4"]["improved_windows"],
                "regressed_windows": row["gate4"]["regressed_windows"],
                "affected_windows": row["gate4"]["affected_windows"],
                "affected_signal_count": row["gate4"]["affected_signal_count"],
                "sample_guard_passed": row["gate4"]["sample_guard_passed"],
                "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            }
        )
    return rows


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Sample | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|:---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.3f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {sample} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                control="yes" if row["is_identity_control"] else "no",
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                affected=row["affected_signal_count"],
                sample="PASS" if row["sample_guard_passed"] else "FAIL",
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Breakout Financials DTE Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: `BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER` for already-qualified `breakout_long` Financials signals with the existing 8-14 DTE state. Entries, candidate pool, ranking, exits, targets, LLM/news, portfolio heat, and all other sizing states were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected non-control multiplier: `{payload['parameters']['selected_risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. A positive promotion would be a shared constants-only sizing change used by both `backtester.py` and `run.py`, followed by focused attribution/parity tests.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: _run_window_with_multiplier(label, BASELINE_RISK_MULTIPLIER)
        for label in WINDOWS
    }
    candidates = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)

    passed = bool(selected["passed"])
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_breakout_financials_dte_risk"
    )
    if passed:
        interpretation = (
            "The breakout Financials 8-14 DTE sleeve cleared the three-window "
            "risk-allocation gate and should be promoted through the shared "
            "constant path before live/default use."
        )
    else:
        interpretation = (
            "Lowering the breakout Financials 8-14 DTE risk scalar did not clear "
            "the full Gate 4 sample and robustness requirements; do not promote "
            "or keep sweeping this two-row DTE pocket on frozen windows."
        )

    aggregate_after = selected["delta_metrics"]["aggregate_after"]
    aggregate_delta = selected["delta_metrics"]["aggregate_delta"]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The existing breakout_long Financials 8-14 DTE risk pocket remains "
            "negative after the accepted core allocation stack; lowering its "
            "risk multiplier may improve expected value and tail risk without "
            "changing entries, ranking, exits, or candidate pool."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "breakout_financials_dte_risk_multiplier",
        "single_causal_variable": (
            "sweep BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER while all other "
            "strategy variables remain locked"
        ),
        "parameters": {
            "baseline_risk_multiplier": BASELINE_RISK_MULTIPLIER,
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "existing_state": {
                "strategy": "breakout_long",
                "sector": "Financials",
                "days_to_earnings_min": base.portfolio_engine.BREAKOUT_FINANCIALS_DTE_MIN,
                "days_to_earnings_max": base.portfolio_engine.BREAKOUT_FINANCIALS_DTE_MAX,
            },
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all other sizing multipliers",
                "portfolio heat",
                "LLM/news replay",
                "pilot and event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: a narrow existing Financials breakout DTE "
                "risk pocket may still be over-sized"
            ),
            "2_history_check": {
                "existing_policy": (
                    "The 8-14 DTE Financials breakout sleeve already exists at "
                    "0.25x; no broad Financials cap/risk retry is being tested."
                ),
                "anti_repeat_check": (
                    "Avoids recent two-slot, LLM/SEC soft-ranking, TSM/ISRG, "
                    "and broad filter/candidate-pool retries."
                ),
            },
            "3_single_causal_variable": "breakout_financials_dte_risk_multiplier",
            "4_acceptance_standard": (
                "docs/backtesting.md fixed three windows; aggregate EV/PnL "
                "positive, at least two improved windows, no EV-regressed "
                "windows, survival >=5%, drawdown drift <=0.5pp, and affected "
                "sample >=3 signals across >=2 windows."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260517_007_breakout_financials_dte_risk.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "risk_engine sector",
                "risk_engine days_to_earnings",
                "portfolio_engine breakout Financials DTE state",
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
        "gate4": selected["gate4"],
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "sweep_summary": _sweep_summary(candidates),
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else (
            "A valid retry needs a materially different production-visible "
            "Financials breakout quality field or forward evidence; do not "
            "continue nearby DTE scalar sweeps on this two-row sample."
        ),
        "related_files": [
            "quant/experiments/exp_20260517_007_breakout_financials_dte_risk.py",
            "data/experiments/exp-20260517-007/breakout_financials_dte_risk.json",
            "experiments/logs/exp-20260517-007.json",
            "experiments/tickets/exp-20260517-007.json",
            "experiments/artifacts/exp-20260517-007_breakout_financials_dte_risk.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    repo_root = base.REPO_ROOT
    artifact_path = (
        repo_root / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = repo_root / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        repo_root / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        repo_root
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
        "artifact": str(artifact_path.relative_to(repo_root)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    base._upsert_jsonl(repo_root / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = run()
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
                "affected_signal_count": result["gate4"]["affected_signal_count"],
                "sample_guard_passed": result["gate4"]["sample_guard_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
