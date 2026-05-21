"""exp-20260521-018: current-stack DTE fast-target cap scout.

This alpha-search experiment tests one lifecycle variable: a target-width cap
for the DTE risk cohorts that already exist in the accepted core stack. It does
not change entries, ranking, risk scalars, portfolio heat, ticker universe, LLM,
or news behavior.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
from constants import (
    BREAKOUT_FINANCIALS_DTE_MAX,
    BREAKOUT_FINANCIALS_DTE_MIN,
    BREAKOUT_HEALTHCARE_DTE_MAX,
    BREAKOUT_HEALTHCARE_DTE_MIN,
    BREAKOUT_TECH_DTE_MAX,
    BREAKOUT_TECH_DTE_MIN,
    TREND_CONSUMER_NEAR_HIGH_DTE_MAX,
    TREND_CONSUMER_NEAR_HIGH_DTE_MIN,
    TREND_CONSUMER_NEAR_HIGH_MAX_PULLBACK,
    TREND_HEALTHCARE_DTE_MAX,
    TREND_HEALTHCARE_DTE_MIN,
    TREND_TECH_DTE_MAX,
    TREND_TECH_DTE_MIN,
)


EXPERIMENT_ID = "exp-20260521-018"
EXPERIMENT_SLUG = "current_dte_fast_target"
MULTIPLIER_KEY = "current_dte_fast_target_cap_applied"

TARGET_CAP_SWEEP: list[float | None] = [None, 3.5, 3.0, 2.5, 2.0]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_EXPECTED_VALUE_SCORE_DELTA = 0.05
MIN_TOTAL_PNL_DELTA = 1000.0
MIN_AFFECTED_SIGNAL_COUNT = 6
MIN_AFFECTED_WINDOW_COUNT = 3
MIN_TRADE_COUNT_SUM = 58

CURRENT_TARGET_ATR_MULT_CAP: float | None = None
ELIGIBLE_SIGNALS: list[dict[str, Any]] = []

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


def _make_compute_features_wrapper(
    original: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    return original


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    return original


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _is_active_dte_cohort(sig: dict[str, Any]) -> bool:
    strategy = sig.get("strategy")
    sector = sig.get("sector")
    dte = _as_float(sig.get("days_to_earnings"))
    pct_from_52w_high = _as_float(sig.get("pct_from_52w_high"))
    if dte is None:
        return False
    if (
        strategy == "trend_long"
        and sector == "Technology"
        and TREND_TECH_DTE_MIN <= dte <= TREND_TECH_DTE_MAX
    ):
        return True
    if (
        strategy == "breakout_long"
        and sector == "Financials"
        and BREAKOUT_FINANCIALS_DTE_MIN <= dte <= BREAKOUT_FINANCIALS_DTE_MAX
    ):
        return True
    if (
        strategy == "breakout_long"
        and sector == "Technology"
        and BREAKOUT_TECH_DTE_MIN <= dte <= BREAKOUT_TECH_DTE_MAX
    ):
        return True
    if (
        strategy == "breakout_long"
        and sector == "Healthcare"
        and BREAKOUT_HEALTHCARE_DTE_MIN <= dte <= BREAKOUT_HEALTHCARE_DTE_MAX
    ):
        return True
    if (
        strategy == "trend_long"
        and sector == "Healthcare"
        and TREND_HEALTHCARE_DTE_MIN <= dte <= TREND_HEALTHCARE_DTE_MAX
    ):
        return True
    if (
        strategy == "trend_long"
        and sector == "Consumer Discretionary"
        and pct_from_52w_high is not None
        and TREND_CONSUMER_NEAR_HIGH_DTE_MIN <= dte <= TREND_CONSUMER_NEAR_HIGH_DTE_MAX
        and pct_from_52w_high >= TREND_CONSUMER_NEAR_HIGH_MAX_PULLBACK
    ):
        return True
    return False


def _eligible_record(sig: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "days_to_earnings": sig.get("days_to_earnings"),
        "pct_from_52w_high": sig.get("pct_from_52w_high"),
        "entry_price": sig.get("entry_price"),
        "stop_price": sig.get("stop_price"),
        "target_price": sig.get("target_price"),
        "target_mult_used": sig.get("target_mult_used"),
        "trade_quality_score": sig.get("trade_quality_score"),
        "confidence_score": sig.get("confidence_score"),
        "regime_exit_bucket": sig.get("regime_exit_bucket"),
        "regime_exit_score": sig.get("regime_exit_score"),
        "gap_vulnerability_pct": sig.get("gap_vulnerability_pct"),
        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
        "signal_day_ticker_green_candle": sig.get("signal_day_ticker_green_candle"),
        "price_vs_200ma_extension_state": sig.get("price_vs_200ma_extension_state"),
    }


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        out: list[dict[str, Any]] = []
        for sig in enriched:
            if not _is_active_dte_cohort(sig):
                out.append(sig)
                continue

            ELIGIBLE_SIGNALS.append(_eligible_record(sig))
            baseline_mult = _as_float(sig.get("target_mult_used"))
            cap = CURRENT_TARGET_ATR_MULT_CAP
            ticker = str(sig.get("ticker") or "")
            atr = _as_float((features_dict.get(ticker) or {}).get("atr"))
            if (
                cap is None
                or atr is None
                or baseline_mult is None
                or baseline_mult <= cap
            ):
                out.append(sig)
                continue

            adjusted = base.risk_engine._retarget_signal_with_atr_mult(sig, atr, cap)
            adjusted["current_dte_fast_target_baseline_target_mult"] = baseline_mult
            adjusted[MULTIPLIER_KEY] = cap
            base.ADJUSTMENTS.append(
                {
                    **_eligible_record(sig),
                    "target_cap": cap,
                    "baseline_target_mult": baseline_mult,
                    "baseline_target_price": sig.get("target_price"),
                    "new_target_price": adjusted.get("target_price"),
                }
            )
            out.append(adjusted)
        return out

    return wrapped


def _candidate_payload(
    target_cap: float | None,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    global CURRENT_TARGET_ATR_MULT_CAP, ELIGIBLE_SIGNALS
    CURRENT_TARGET_ATR_MULT_CAP = target_cap

    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    eligible_signals: dict[str, list[dict[str, Any]]] = {}

    for label in base.WINDOWS:
        ELIGIBLE_SIGNALS = []
        variant = base._run_window(label, variant=True)
        eligible_signals[label] = list(ELIGIBLE_SIGNALS)
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        changed_trades[label] = base._changed_trades(
            before_runs[label]["trades"],
            variant["trades"],
        )

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
    adjusted_count = sum(len(rows) for rows in adjustments.values())
    affected_window_count = sum(1 for rows in adjustments.values() if rows)
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    drawdown_guardrail_passed = (
        max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    convergence_passed = all(
        bool(row.get("converged")) for row in after_metrics.values()
    )
    sample_guard_passed = (
        adjusted_count >= MIN_AFFECTED_SIGNAL_COUNT
        and affected_window_count >= MIN_AFFECTED_WINDOW_COUNT
    )
    materiality_guard_passed = (
        aggregate_delta["expected_value_score_sum"] >= MIN_EXPECTED_VALUE_SCORE_DELTA
        and aggregate_delta["total_pnl_sum"] >= MIN_TOTAL_PNL_DELTA
    )
    passed = (
        target_cap is not None
        and materiality_guard_passed
        and len(improved) >= 2
        and not regressed
        and drawdown_guardrail_passed
        and convergence_passed
        and aggregate_after["trade_count_sum"] >= MIN_TRADE_COUNT_SUM
        and aggregate_after["survival_rate_min"] >= 0.05
        and sample_guard_passed
    )
    return {
        "target_cap": target_cap,
        "is_identity_control": target_cap is None,
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
            "adjusted_signal_count": adjusted_count,
            "affected_window_count": affected_window_count,
            "min_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "min_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "sample_guard_passed": sample_guard_passed,
            "trade_count_sum_after": aggregate_after["trade_count_sum"],
            "min_trade_count_sum": MIN_TRADE_COUNT_SUM,
            "trade_count_guard_passed": (
                aggregate_after["trade_count_sum"] >= MIN_TRADE_COUNT_SUM
            ),
            "convergence_passed": convergence_passed,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
            "min_expected_value_score_delta": MIN_EXPECTED_VALUE_SCORE_DELTA,
            "min_total_pnl_delta": MIN_TOTAL_PNL_DELTA,
            "materiality_guard_passed": materiality_guard_passed,
        },
        "adjustments": adjustments,
        "changed_trades": changed_trades,
        "eligible_signals": eligible_signals,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row["passed"]]
    pool = passed if passed else [row for row in candidates if not row["is_identity_control"]]
    return max(
        pool,
        key=lambda row: (
            1 if row["passed"] else 0,
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
            -float(row["gate4"].get("max_drawdown_worse") or 0.0),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "target_cap": row["target_cap"],
            "is_identity_control": row["is_identity_control"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
            "affected_window_count": row["gate4"]["affected_window_count"],
                "trade_count_sum_after": row["gate4"]["trade_count_sum_after"],
                "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
                "drawdown_guardrail_passed": row["gate4"]["drawdown_guardrail_passed"],
                "materiality_guard_passed": row["gate4"][
                    "materiality_guard_passed"
                ],
            }
        for row in candidates
    ]


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Target cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Trades | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        target_cap = "control" if row["target_cap"] is None else f"{row['target_cap']:.2f}"
        sweep_rows.append(
            "| {cap} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {wins} | {trades} | {dd:+.4f} |".format(
                cap=target_cap,
                passed="PASS" if row["passed"] else ("CTRL" if row["is_identity_control"] else "FAIL"),
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                wins=row["affected_window_count"],
                trades=row["trade_count_sum_after"],
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Survival | Affected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Current DTE Fast Target",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap target width for existing accepted current-stack DTE risk cohorts. Entries, ranking, sizing, universe, LLM, news, heat, and stops stay locked.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected target cap: `{payload['parameters']['selected_target_cap']}`.",
            "",
            "## Selected three-window result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout unless a selected cap is promoted into shared risk policy and rerun through the canonical three-window protocol.",
        ]
    )


def run() -> dict[str, Any]:
    base.WINDOWS = WINDOWS
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = _make_compute_features_wrapper
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown

    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: base._run_window(label, variant=False) for label in base.WINDOWS
    }
    candidates = [
        _candidate_payload(target_cap, before_runs)
        for target_cap in TARGET_CAP_SWEEP
    ]
    selected = _select_candidate(candidates)
    identity = next(row for row in candidates if row["is_identity_control"])
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_current_dte_fast_target"
    )
    interpretation = (
        "The current-stack DTE fast-target cap cleared the canonical three-window scout; promote only through shared risk policy before any production-visible use."
        if passed
        else "The tested DTE fast-target cap did not clear the canonical three-window gate; do not promote target-width caps for this current-stack DTE family without a distinct new discriminator."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted current-stack DTE risk cohorts are not pure entry "
            "avoidance problems: prior diagnostics showed several trades had "
            "early profit available before exit. A target-width cap may harvest "
            "event-proximity moves before the same cohort gives back gains."
        ),
        "change_type": "exit_lifecycle_shadow",
        "changed_variable": "current_dte_fast_target_atr_mult_cap",
        "single_causal_variable": (
            "maximum ATR target multiple for existing accepted DTE risk cohorts"
        ),
        "trial_family": "current_stack_dte_fast_target_lifecycle",
        "trial_accounting": {
            "trial_family": "current_stack_dte_fast_target_lifecycle",
            "changed_variable": "current_dte_fast_target_atr_mult_cap",
            "prior_trial_count": 6,
            "nearby_prior_experiments": [
                "exp-20260505-016",
                "exp-20260516-020",
                "exp-20260517-007",
                "exp-20260520-018",
                "exp-20260520-038",
                "exp-20260520-041",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "dte_lifecycle_profit_capture_diagnostic",
        },
        "parameters": {
            "target_cap_sweep": TARGET_CAP_SWEEP,
            "selected_target_cap": selected["target_cap"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "minimum_trade_count_sum": MIN_TRADE_COUNT_SUM,
            "minimum_expected_value_score_delta": MIN_EXPECTED_VALUE_SCORE_DELTA,
            "minimum_total_pnl_delta": MIN_TOTAL_PNL_DELTA,
            "cohorts": {
                "trend_technology_dte": [TREND_TECH_DTE_MIN, TREND_TECH_DTE_MAX],
                "breakout_financials_dte": [
                    BREAKOUT_FINANCIALS_DTE_MIN,
                    BREAKOUT_FINANCIALS_DTE_MAX,
                ],
                "breakout_technology_dte": [
                    BREAKOUT_TECH_DTE_MIN,
                    BREAKOUT_TECH_DTE_MAX,
                ],
                "breakout_healthcare_dte": [
                    BREAKOUT_HEALTHCARE_DTE_MIN,
                    BREAKOUT_HEALTHCARE_DTE_MAX,
                ],
                "trend_healthcare_dte": [
                    TREND_HEALTHCARE_DTE_MIN,
                    TREND_HEALTHCARE_DTE_MAX,
                ],
                "trend_consumer_near_high_dte": [
                    TREND_CONSUMER_NEAR_HIGH_DTE_MIN,
                    TREND_CONSUMER_NEAR_HIGH_DTE_MAX,
                    TREND_CONSUMER_NEAR_HIGH_MAX_PULLBACK,
                ],
            },
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "risk allocation and sizing",
                "stop placement",
                "portfolio heat",
                "slot planning",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "exit/lifecycle alpha: existing accepted DTE risk cohorts may "
                "need faster targets rather than another entry or risk scalar."
            ),
            "2_history_check": {
                "exp-20260520-038": (
                    "Broad current-stack DTE residual risk scalar was rejected, "
                    "but it logged active DTE trades with profit available before "
                    "exit and fast-target candidate behavior."
                ),
                "exp-20260520-041": (
                    "DTE nonconfirming candle filter was rejected; this run does "
                    "not add a filter or candle gate."
                ),
                "event_scalar_family": (
                    "Recent event source/state scalars have both accepted and "
                    "failed; this experiment avoids nearby event scalar mining."
                ),
            },
            "3_single_causal_variable": (
                "Only the current-stack DTE target ATR cap changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md canonical three fixed windows; aggregate "
                "EV/PnL positive, >=2 improved windows, no regressed windows, "
                "aggregate dEV >=0.05, aggregate dPnL >=$1,000, drawdown drift "
                "<=0.5pp, trade_count_sum >=58, affected signals >=6 across all "
                "three windows, convergence pass, and survival >=5%."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260521_018_current_dte_fast_target.py"
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
            "baseline_reference": (
                "docs/backtesting.md accepted current core stack after "
                "exp-20260517-009"
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "risk_engine strategy",
                "risk_engine sector",
                "risk_engine days_to_earnings",
                "risk_engine pct_from_52w_high",
                "risk_engine atr",
                "risk_engine target_mult_used",
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
        "eligible_signals": identity["eligible_signals"],
        "sweep_summary": _sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "No LLM behavior changed; this deterministic exit-lifecycle "
                "scout deliberately avoids the LLM soft-ranking data limitation."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add the target cap to shared risk_engine policy, "
                "add focused tests, update parity docs, and rerun canonical "
                "three-window metrics before any production-visible behavior."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking and broad-market forward lanes still lack enough "
            "closed forward rows, and recent event source/state scalar work is "
            "too close to accepted/rejected neighbors. This targets the "
            "strongest non-LLM lifecycle evidence instead."
        ),
        "known_risks": [
            "Target-width caps are threshold-like and high multiple-testing risk.",
            "A faster target can reduce convexity even when it improves loss giveback.",
            "Promotion must use shared risk policy; a replay-only pass is not production parity.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": (
            None
            if passed
            else "Do not retry nearby DTE target caps without a distinct forward profit-capture discriminator or new DTE lifecycle rows."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260521_018_current_dte_fast_target.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


if __name__ == "__main__":
    result = run()
    base.persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_target_cap": result["parameters"]["selected_target_cap"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "max_drawdown_worse": result["gate4"]["max_drawdown_worse"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "sweep_summary": result["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
