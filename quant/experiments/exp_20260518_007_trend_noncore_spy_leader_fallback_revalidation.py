"""exp-20260518-007: trend non-core SPY-leader fallback revalidation.

Alpha search. Revalidates an older positive-but-rejected allocation idea on the
current accepted core stack and current Gate 4 standard: keep breakout
SPY-relative leaders unchanged, but test whether trend_long SPY-relative
leaders outside repeat-positive trend sectors should use a lower total risk
budget than the current 2.0x path.

Replay-only scout. If a variant passes, promotion must move the rule into the
shared portfolio sizing path used by both backtester.py and run.py, then rerun
the canonical three-window protocol.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260502_017_trend_spy_leader_noncore_fallback as prior
import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260518-007"
EXPERIMENT_SLUG = "trend_noncore_spy_leader_fallback_revalidation"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

BASELINE_TOTAL_MULTIPLIER = 2.0
FALLBACK_TOTAL_MULTIPLIER_SWEEP = [2.0, 1.5, 1.25, 1.0]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_TRADE_COUNT = 3
MIN_AFFECTED_WINDOW_COUNT = 2


def _round(value: Any, digits: int = 4) -> float | None:
    if value is None:
        return None
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(as_float) or math.isinf(as_float):
        return None
    return round(as_float, digits)


def _aggregate_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(row.get("expected_value_score") or 0.0 for row in metrics.values()),
            4,
        ),
        "total_pnl_sum": _round(
            sum(row.get("total_pnl") or 0.0 for row in metrics.values()),
            2,
        ),
        "trade_count_sum": int(
            sum(row.get("trade_count") or 0 for row in metrics.values())
        ),
        "min_survival_rate": _round(
            min(row.get("survival_rate") or 0.0 for row in metrics.values()),
            6,
        ),
        "max_drawdown_pct_max": _round(
            max(row.get("max_drawdown_pct") or 0.0 for row in metrics.values()),
            6,
        ),
    }


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_agg = _aggregate_metrics(before)
    after_agg = _aggregate_metrics(after)
    return {
        "before": before_agg,
        "after": after_agg,
        "expected_value_score_sum": _round(
            (after_agg["expected_value_score_sum"] or 0.0)
            - (before_agg["expected_value_score_sum"] or 0.0),
            4,
        ),
        "total_pnl_sum": _round(
            (after_agg["total_pnl_sum"] or 0.0) - (before_agg["total_pnl_sum"] or 0.0),
            2,
        ),
        "trade_count_sum": (after_agg["trade_count_sum"] or 0)
        - (before_agg["trade_count_sum"] or 0),
        "min_survival_rate": _round(
            (after_agg["min_survival_rate"] or 0.0)
            - (before_agg["min_survival_rate"] or 0.0),
            6,
        ),
        "max_drawdown_pct_max": _round(
            (after_agg["max_drawdown_pct_max"] or 0.0)
            - (before_agg["max_drawdown_pct_max"] or 0.0),
            6,
        ),
    }


def _target_trade_attribution(result: dict[str, Any]) -> dict[str, Any]:
    rows = prior._target_trade_attribution(result)
    return {
        "trade_count": rows["trade_count"],
        "wins": rows["wins"],
        "losses": rows["losses"],
        "total_pnl_usd": rows["total_pnl_usd"],
        "trades": rows["trades"],
    }


def _run_baselines() -> dict[str, dict[str, Any]]:
    return {label: prior._run_window(window) for label, window in WINDOWS.items()}


def _run_variant(multiplier: float) -> dict[str, dict[str, Any]]:
    variant = {"fallback_total_multiplier": multiplier}
    return {
        label: prior._run_window(window, variant)
        for label, window in WINDOWS.items()
    }


def _variant_payload(
    multiplier: float,
    baselines: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    is_identity = math.isclose(multiplier, BASELINE_TOTAL_MULTIPLIER)
    variant_runs = baselines if is_identity else _run_variant(multiplier)
    before_metrics = {
        label: prior._metrics(result) for label, result in baselines.items()
    }
    after_metrics = {
        label: prior._metrics(result) for label, result in variant_runs.items()
    }
    by_window_delta = {
        label: prior._delta(before_metrics[label], after_metrics[label])
        for label in WINDOWS
    }
    aggregate_delta = _aggregate_delta(before_metrics, after_metrics)
    improved = [
        label
        for label in WINDOWS
        if (by_window_delta[label].get("expected_value_score") or 0.0) > 0.0
    ]
    regressed = [
        label
        for label in WINDOWS
        if (by_window_delta[label].get("expected_value_score") or 0.0) < 0.0
    ]
    affected_before = {
        label: _target_trade_attribution(baselines[label]) for label in WINDOWS
    }
    affected_trade_count = sum(row["trade_count"] for row in affected_before.values())
    affected_window_count = sum(1 for row in affected_before.values() if row["trade_count"])
    max_drawdown_worse = max(
        float(row.get("max_drawdown_pct") or 0.0) for row in by_window_delta.values()
    )
    sample_guard_passed = (
        affected_trade_count >= MIN_AFFECTED_TRADE_COUNT
        and affected_window_count >= MIN_AFFECTED_WINDOW_COUNT
    )
    drawdown_guardrail_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    passed = (
        not is_identity
        and (aggregate_delta["expected_value_score_sum"] or 0.0) > 0.0
        and (aggregate_delta["total_pnl_sum"] or 0.0) > 0.0
        and len(improved) >= 2
        and not regressed
        and (aggregate_delta["after"]["min_survival_rate"] or 0.0) >= 0.05
        and sample_guard_passed
        and drawdown_guardrail_passed
    )
    return {
        "fallback_total_multiplier": multiplier,
        "is_identity_control": is_identity,
        "passed": passed,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_delta": aggregate_delta,
        },
        "affected_before": affected_before,
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "affected_trade_count": affected_trade_count,
            "affected_window_count": affected_window_count,
            "minimum_affected_trade_count": MIN_AFFECTED_TRADE_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "sample_guard_passed": sample_guard_passed,
            "max_drawdown_worse": _round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    non_identity = [row for row in candidates if not row["is_identity_control"]]
    passing = [row for row in non_identity if row["passed"]]
    pool = passing if passing else non_identity
    return max(
        pool,
        key=lambda row: (
            1 if row["passed"] else 0,
            float(row["expected_value_score_delta"] or 0.0),
            float(row["total_pnl_delta"] or 0.0),
            -float(row["gate4"]["max_drawdown_worse"] or 0.0),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "fallback_total_multiplier": row["fallback_total_multiplier"],
            "is_identity_control": row["is_identity_control"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "affected_trade_count": row["gate4"]["affected_trade_count"],
            "affected_window_count": row["gate4"]["affected_window_count"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            "sample_guard_passed": row["gate4"]["sample_guard_passed"],
            "drawdown_guardrail_passed": row["gate4"][
                "drawdown_guardrail_passed"
            ],
        }
        for row in candidates
    ]


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Fallback total multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected trades | Affected windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.2f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
                mult=row["fallback_total_multiplier"],
                control="yes" if row["is_identity_control"] else "no",
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                affected=row["affected_trade_count"],
                windows=row["affected_window_count"],
                dd=row["max_drawdown_worse"],
            )
        )
    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Trend Non-Core SPY-Leader Fallback Revalidation",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: total risk multiplier for already-qualified `trend_long` SPY-relative leaders outside repeat-positive trend sectors. Breakouts, entries, ranking, exits, targets, candidate pool, LLM/news, and event sleeves were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. Passing evidence requires promotion through shared `portfolio_engine.py` and parity tests before changing live/default behavior.",
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    repo_root = prior.REPO_ROOT
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
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ticket_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    ticket_path.write_text(
        json.dumps(ticket, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    base._upsert_jsonl(repo_root / "docs" / "experiment_log.jsonl", payload)


def run() -> dict[str, Any]:
    prior.WINDOWS = WINDOWS
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.OUT_DIR = prior.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    prior.OUT_JSON = prior.OUT_DIR / f"{EXPERIMENT_SLUG}.json"
    prior.LOG_JSON = (
        prior.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    )
    prior.TICKET_JSON = (
        prior.REPO_ROOT
        / "experiments"
        / "tickets"
        / f"{EXPERIMENT_ID}.json"
    )

    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baselines = _run_baselines()
    candidates = [
        _variant_payload(multiplier, baselines)
        for multiplier in FALLBACK_TOTAL_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_trend_noncore_spy_leader_fallback"
    )
    interpretation = (
        "Trend non-core SPY-relative leader fallback cleared the current three-window scout and requires shared policy promotion plus rerun before production use."
        if selected["passed"]
        else "Trend non-core SPY-relative leader fallback did not clear the current three-window gate."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted 2.0x SPY-relative leader allocation may still be too broad "
            "for trend_long signals outside repeat-positive trend sectors. Lowering "
            "only that total multiplier can reduce weak non-core trend leakage while "
            "leaving breakouts and the candidate pool unchanged."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "trend_noncore_spy_leader_total_multiplier",
        "single_causal_variable": (
            "total risk multiplier for trend_long SPY-relative leaders outside "
            "Technology, Consumer Discretionary, Communication Services, "
            "Financials, and Commodities"
        ),
        "parameters": {
            "baseline_total_multiplier": BASELINE_TOTAL_MULTIPLIER,
            "fallback_total_multiplier_sweep": FALLBACK_TOTAL_MULTIPLIER_SWEEP,
            "selected_fallback_total_multiplier": selected[
                "fallback_total_multiplier"
            ],
            "core_trend_sectors_kept_at_2x": prior.CORE_TREND_SECTORS,
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_affected_trade_count": MIN_AFFECTED_TRADE_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "breakout_long SPY-relative leader sizing",
                "stop and target logic",
                "portfolio heat",
                "slot planning",
                "LLM/news replay",
                "event sleeves",
                "candidate pool",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: trend_long non-core SPY-relative leaders may be "
                "over-allocated versus breakout leaders and core trend sectors"
            ),
            "2_history_check": {
                "exp-20260502-017": (
                    "Older stack showed +0.0901 aggregate EV and +$2,391.56 PnL "
                    "for a 1.0x fallback with 2/3 windows improved and no EV "
                    "regression, but it failed the then-stricter hard threshold."
                ),
                "recent_playbook": (
                    "Recent accepts favor fixed-candidate allocation over broad "
                    "filters. This does not change candidate eligibility or ranking."
                ),
                "why_retest": (
                    "Current core stack after exp-20260517-009 and current Gate 4 "
                    "standards allow small stable risk-reducing allocation edges."
                ),
            },
            "3_single_causal_variable": (
                "trend_noncore_spy_leader_total_multiplier; sweep values are "
                "1.5, 1.25, and 1.0 versus the 2.0 control"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL "
                "positive, at least two EV-improved windows, no EV-regressed "
                "windows, survival >= 5%, at least three affected trades across "
                "at least two windows, and max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_007_trend_noncore_spy_leader_fallback_revalidation.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_delta"][
                "before"
            ],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "portfolio_engine strategy",
                "portfolio_engine sector",
                "portfolio_engine risk_on_unmodified_risk_multiplier_applied",
                "portfolio_engine spy_relative_leader_risk_on_multiplier_applied",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_after_survival_rate": selected["delta_metrics"][
                "aggregate_delta"
            ]["after"]["min_survival_rate"],
            "passed": (
                selected["delta_metrics"]["aggregate_delta"]["after"][
                    "min_survival_rate"
                ]
                >= 0.05
            ),
        },
        "gate4": selected["gate4"],
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "affected_before": selected["affected_before"],
        "sweep_summary": _sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "No LLM behavior changed; this deterministic allocation state "
                "avoids current LLM soft-ranking data limits."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement in shared portfolio_engine.py so both "
                "backtester.py and run.py consume the same sizing branch, add "
                "focused parity tests, then rerun all three canonical windows."
            ),
        },
        "why_not_other_changes": (
            "State-surface is tail-concentration blocked, LLM soft-ranking lacks "
            "closed attribution, and recent candidate-pool expansion added noise. "
            "This tests one fixed-candidate allocation variable."
        ),
        "known_risks": [
            "The cohort is small and includes sector-specific effects.",
            "A fallback can free capital and alter replacement fills, so promotion needs shared-code rerun.",
            "This is a revalidation of an older idea, not a new broad sector filter.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else "Do not retry this fallback on frozen windows without forward non-core trend attribution or a narrower production-visible field."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260518_007_trend_noncore_spy_leader_fallback_revalidation.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> dict[str, Any]:
    result = run()
    _persist(result)
    return result


if __name__ == "__main__":
    result = main()
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
                "affected_trade_count": result["gate4"]["affected_trade_count"],
                "affected_window_count": result["gate4"]["affected_window_count"],
                "selected_fallback_total_multiplier": result["parameters"][
                    "selected_fallback_total_multiplier"
                ],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
