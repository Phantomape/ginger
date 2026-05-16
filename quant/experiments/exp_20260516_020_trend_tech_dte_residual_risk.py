"""exp-20260516-020: Technology trend DTE residual risk sweep.

Tests one production-visible risk-allocation variable on the accepted core
stack: the existing Technology trend 44-64 DTE risk multiplier. This is a
replay scout only; no production-default strategy behavior changes unless a
separate shared-policy promotion is made and revalidated.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260516-020"
EXPERIMENT_SLUG = "trend_tech_dte_residual_risk"
MULTIPLIER_KEY = "trend_tech_dte_risk_multiplier_applied"
BASELINE_RISK_MULTIPLIER = 0.25
RISK_MULTIPLIER_SWEEP = [0.0, 0.125, BASELINE_RISK_MULTIPLIER]
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
CURRENT_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER


def _is_trend_tech_dte_state(sig: dict[str, Any]) -> bool:
    days_to_earnings = sig.get("days_to_earnings")
    return (
        sig.get("strategy") == "trend_long"
        and sig.get("sector") == "Technology"
        and isinstance(days_to_earnings, (int, float))
        and base.portfolio_engine.TREND_TECH_DTE_MIN
        <= days_to_earnings
        <= base.portfolio_engine.TREND_TECH_DTE_MAX
    )


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        old_multiplier = base.portfolio_engine.TREND_TECH_DTE_RISK_MULTIPLIER
        base.portfolio_engine.TREND_TECH_DTE_RISK_MULTIPLIER = (
            CURRENT_RISK_MULTIPLIER
        )
        try:
            sized = original(signals, portfolio_value, risk_pct=risk_pct)
        finally:
            base.portfolio_engine.TREND_TECH_DTE_RISK_MULTIPLIER = old_multiplier

        for sig in sized:
            if not _is_trend_tech_dte_state(sig):
                continue
            sizing = sig.get("sizing") or {}
            if not sizing:
                continue
            base.ADJUSTMENTS.append(
                {
                    "ticker": sig.get("ticker"),
                    "strategy": sig.get("strategy"),
                    "sector": sig.get("sector"),
                    "days_to_earnings": sig.get("days_to_earnings"),
                    "gap_vulnerability_pct": sig.get("gap_vulnerability_pct"),
                    "pct_from_52w_high": (sig.get("conditions_met") or {}).get(
                        "pct_from_52w_high"
                    ),
                    "shares_to_buy": sizing.get("shares_to_buy"),
                    "risk_pct": sizing.get("risk_pct"),
                    "risk_amount_usd": sizing.get("risk_amount_usd"),
                    "trade_quality_score": sig.get("trade_quality_score"),
                    "regime_exit_bucket": sig.get("regime_exit_bucket"),
                    "regime_exit_score": sig.get("regime_exit_score"),
                    "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
                    "rs60_entry_state_top_quintile": sig.get(
                        "rs60_entry_state_top_quintile"
                    ),
                    "price_vs_200ma_extension_state": sig.get(
                        "price_vs_200ma_extension_state"
                    ),
                    MULTIPLIER_KEY: sizing.get(MULTIPLIER_KEY),
                }
            )
        return sized

    return wrapped


def _apply_gate4_guards(candidate: dict[str, Any]) -> dict[str, Any]:
    max_drawdown_worse = max(
        float(delta.get("max_drawdown_pct") or 0.0)
        for delta in candidate["delta_metrics"]["by_window"].values()
    )
    affected_windows = [
        label for label, rows in candidate["adjustments"].items() if rows
    ]
    sample_guard_passed = (
        candidate["gate4"]["affected_signal_count"] >= MIN_AFFECTED_SIGNAL_COUNT
        and len(affected_windows) >= MIN_AFFECTED_WINDOW_COUNT
    )
    drawdown_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    candidate["gate4"]["affected_windows"] = affected_windows
    candidate["gate4"]["minimum_affected_signal_count"] = MIN_AFFECTED_SIGNAL_COUNT
    candidate["gate4"]["minimum_affected_window_count"] = MIN_AFFECTED_WINDOW_COUNT
    candidate["gate4"]["sample_guard_passed"] = sample_guard_passed
    candidate["gate4"]["max_drawdown_worse"] = round(max_drawdown_worse, 6)
    candidate["gate4"]["max_drawdown_worse_guardrail"] = (
        MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    candidate["gate4"]["drawdown_guardrail_passed"] = drawdown_passed
    candidate["passed"] = (
        bool(candidate["passed"])
        and sample_guard_passed
        and drawdown_passed
        and not candidate["is_identity_control"]
    )
    candidate["gate4"]["passed"] = candidate["passed"]
    return candidate


def _candidate_payload(
    multiplier: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in base.WINDOWS:
        variant = _run_window_with_multiplier(label, multiplier)
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
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
    affected_count = sum(len(rows) for rows in adjustments.values())
    is_identity = math.isclose(multiplier, BASELINE_RISK_MULTIPLIER)
    passed = (
        not is_identity
        and aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and affected_count > 0
    )
    return _apply_gate4_guards(
        {
            "risk_multiplier": multiplier,
            "is_identity_control": is_identity,
            "passed": passed,
            "before_metrics": before_metrics,
            "after_metrics": after_metrics,
            "delta_metrics": {
                "by_window": by_window_delta,
                "aggregate_before": aggregate_before,
                "aggregate_after": aggregate_after,
                "aggregate_delta": aggregate_delta,
            },
            "gate4": {
                "passed": passed,
                "improved_windows": improved,
                "regressed_windows": regressed,
                "affected_signal_count": affected_count,
            },
            "adjustments": adjustments,
            "changed_trades": changed_trades,
            "sizing_attribution": sizing_attribution,
            "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
            "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        }
    )


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    non_identity = [row for row in candidates if not row["is_identity_control"]]
    passed = [row for row in non_identity if row["passed"]]
    pool = passed if passed else non_identity
    return max(
        pool,
        key=lambda row: (
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
            -float(row["gate4"].get("max_drawdown_worse") or 0.0),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in candidates:
        rows.append(
            {
                "risk_multiplier": row["risk_multiplier"],
                "is_identity_control": row["is_identity_control"],
                "passed": row["passed"],
                "expected_value_score_delta": row["expected_value_score_delta"],
                "total_pnl_delta": row["total_pnl_delta"],
                "improved_windows": row["gate4"]["improved_windows"],
                "regressed_windows": row["gate4"]["regressed_windows"],
                "affected_signal_count": row["gate4"]["affected_signal_count"],
                "affected_windows": row["gate4"]["affected_windows"],
                "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
                "sample_guard_passed": row["gate4"]["sample_guard_passed"],
                "drawdown_guardrail_passed": row["gate4"][
                    "drawdown_guardrail_passed"
                ],
            }
        )
    return rows


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.3f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                control="yes" if row["is_identity_control"] else "no",
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                affected=row["affected_signal_count"],
                windows=", ".join(row["affected_windows"]) or "-",
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {affected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                affected=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Technology Trend DTE Residual Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: the existing `TREND_TECH_DTE_RISK_MULTIPLIER` for `trend_long` Technology signals with 44-64 `days_to_earnings`. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.",
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
            "Production impact: replay-only scout. A positive promotion must change the shared `TREND_TECH_DTE_RISK_MULTIPLIER` constant, rerun the canonical three-window backtest, and confirm the same policy is used by both `backtester.py` and `run.py` before live/default behavior changes.",
        ]
    )


def _configure_modules() -> None:
    base.WINDOWS = WINDOWS
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = lambda original: original
    base._make_enrich_wrapper = lambda original: original
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown


def _run_window_with_multiplier(
    label: str,
    multiplier: float,
) -> dict[str, Any]:
    global CURRENT_RISK_MULTIPLIER
    CURRENT_RISK_MULTIPLIER = multiplier
    return base._run_window(label, variant=True)


def run() -> dict[str, Any]:
    _configure_modules()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: _run_window_with_multiplier(label, BASELINE_RISK_MULTIPLIER)
        for label in base.WINDOWS
    }
    candidates = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)

    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_trend_tech_dte_residual_risk"
    )
    interpretation = (
        "Technology trend DTE residual risk cleared the canonical three-window scout and requires shared constant promotion plus rerun before production use."
        if selected["passed"]
        else "Technology trend DTE residual risk did not clear the canonical three-window gate; keep the accepted 0.25x sleeve unchanged."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "After the accepted core allocation stack, the existing Technology "
            "trend 44-64 DTE sleeve may still be a negative residual pocket. "
            "Reducing only that production-visible multiplier can test whether "
            "scarce risk should move away from pre-earnings Technology trends "
            "without changing the candidate pool or adding a new filter."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "trend_tech_dte_risk_multiplier",
        "single_causal_variable": (
            "Existing Technology trend 44-64 days-to-earnings risk multiplier"
        ),
        "parameters": {
            "state_definition": {
                "strategy": "trend_long",
                "sector": "Technology",
                "days_to_earnings_min": base.portfolio_engine.TREND_TECH_DTE_MIN,
                "days_to_earnings_max": base.portfolio_engine.TREND_TECH_DTE_MAX,
            },
            "baseline_risk_multiplier": BASELINE_RISK_MULTIPLIER,
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers except selected multiplier",
                "portfolio heat",
                "slot planning",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation on an existing production-visible Technology "
                "trend DTE state; this fits the playbook's preference for fixed "
                "candidate-set allocation over LLM soft-ranking or noisy pool growth"
            ),
            "2_history_check": {
                "compound severe haircut skips": (
                    "exp-20260505-012 and exp-20260507-009 failed; this run "
                    "does not skip all compound haircuts and changes only one "
                    "existing DTE multiplier"
                ),
                "accepted current sleeve": (
                    "the 44-64 DTE 0.25x sleeve is already shared policy; this "
                    "sweep is required before any scalar change"
                ),
                "recent alternatives": (
                    "Space peer-state retries failed and LLM/SEC soft-ranking "
                    "branches remain attribution-limited, so this run uses a "
                    "deterministic production field"
                ),
            },
            "3_single_causal_variable": (
                "trend_tech_dte_risk_multiplier, with state definition fixed"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL "
                "positive, at least two EV-improved windows, no EV-regressed "
                "windows, survival >= 5%, at least three affected signals across "
                "at least two windows, and max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260516_020_trend_tech_dte_residual_risk.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "risk_engine sector",
                "risk_engine strategy",
                "risk_engine days_to_earnings",
                "portfolio_engine TREND_TECH_DTE_RISK_MULTIPLIER",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": selected["delta_metrics"]["aggregate_delta"][
                "signals_generated_sum"
            ],
            "signals_survived_delta": selected["delta_metrics"]["aggregate_delta"][
                "signals_survived_sum"
            ],
            "minimum_after_survival_rate": selected["delta_metrics"][
                "aggregate_after"
            ]["survival_rate_min"],
            "passed": selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ]
            >= 0.05,
        },
        "gate4": selected["gate4"],
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "sweep_summary": _sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking and SEC semantic branches remain data-limited; "
                "this deterministic allocation state avoids those blockers."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, change the shared constant used by both "
                "backtester.py and run.py adapters, add focused parity coverage "
                "if needed, and rerun all three canonical windows."
            ),
        },
        "why_not_other_changes": (
            "This avoids LLM/SEC branches because PIT semantic attribution is "
            "still insufficient, avoids Space/event-sleeve retunes because the "
            "latest peer-state variants failed, and avoids broad candidate-pool "
            "expansion because recent breadth additions added noise."
        ),
        "known_risks": [
            "The affected cohort is intentionally small and could be a frozen-window artifact.",
            "The current 0.25x sleeve was previously accepted, so promotion requires clean multi-window evidence.",
            "A positive replay scout is not production-tradable until the shared constant is changed and rerun.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else "Do not retry nearby Technology trend DTE scalar changes on these frozen windows; use a broader orthogonal production-visible discriminator or forward evidence."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_020_trend_tech_dte_residual_risk.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> dict[str, Any]:
    result = run()
    base.persist(result)
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
                "affected_signal_count": result["gate4"]["affected_signal_count"],
                "affected_windows": result["gate4"]["affected_windows"],
            },
            indent=2,
            sort_keys=True,
        )
    )
