"""exp-20260516-011: trend Industrials zero-risk replacement.

Tests one replay-only alpha variable on the accepted core stack:
restore a small nonzero risk multiplier to already-qualified
`trend_long` / Industrials signals that production currently zeroes out.

This is not a production policy change. A positive result would still need the
same scalar moved through shared `constants.py` / `portfolio_engine.py`, focused
parity tests, and the canonical three-window rerun before live behavior changes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260516-011"
EXPERIMENT_SLUG = "trend_industrials_zero_risk_replacement"
MULTIPLIER_KEY = "trend_industrials_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [0.10, 0.25, 0.50]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
TARGET_STRATEGY = "trend_long"
TARGET_SECTOR = "Industrials"
CURRENT_RISK_MULTIPLIER = 0.0
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


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    return original


def _target_signal(sig: dict[str, Any]) -> bool:
    return (
        sig.get("strategy") == TARGET_STRATEGY
        and sig.get("sector") == TARGET_SECTOR
    )


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        previous_multiplier = base.portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER
        base.portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER = (
            CURRENT_RISK_MULTIPLIER
        )
        try:
            sized = original(signals, portfolio_value, risk_pct=risk_pct)
        finally:
            base.portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER = (
                previous_multiplier
            )

        for sig in sized:
            if not _target_signal(sig):
                continue
            sizing = sig.get("sizing") or {}
            applied = sizing.get(MULTIPLIER_KEY)
            base.ADJUSTMENTS.append(
                {
                    "ticker": sig.get("ticker"),
                    "strategy": sig.get("strategy"),
                    "sector": sig.get("sector"),
                    "risk_multiplier": applied,
                    "shares_to_buy": sizing.get("shares_to_buy"),
                    "risk_pct": sizing.get("risk_pct"),
                    "position_value_usd": sizing.get("position_value_usd"),
                    "max_position_pct_applied": sizing.get(
                        "max_position_pct_applied"
                    ),
                    "trade_quality_score": sig.get("trade_quality_score"),
                    "confidence_score": sig.get("confidence_score"),
                    "regime_exit_bucket": sig.get("regime_exit_bucket"),
                    "regime_exit_score": sig.get("regime_exit_score"),
                    "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
                    "core_confirmed_quality_state": sig.get(
                        "core_confirmed_quality_state"
                    ),
                    "green_decel_quality_nonconsumer_state": sig.get(
                        "green_decel_quality_nonconsumer_state"
                    ),
                    "signal_day_ticker_green_candle": sig.get(
                        "signal_day_ticker_green_candle"
                    ),
                    "price_vs_200ma_extension_state": sig.get(
                        "price_vs_200ma_extension_state"
                    ),
                }
            )
        return sized

    return wrapped


def _candidate_payload(
    multiplier: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    global CURRENT_RISK_MULTIPLIER
    CURRENT_RISK_MULTIPLIER = multiplier

    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in base.WINDOWS:
        variant = base._run_window(label, variant=True)
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
    adjusted_count = sum(len(rows) for rows in adjustments.values())
    entered_count = sum(
        1
        for rows in adjustments.values()
        for row in rows
        if int(row.get("shares_to_buy") or 0) > 0
    )
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    drawdown_guardrail_passed = (
        max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and adjusted_count > 0
        and entered_count > 0
        and drawdown_guardrail_passed
    )
    return {
        "risk_multiplier": multiplier,
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
            "entered_signal_count": entered_count,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "adjustments": adjustments,
        "changed_trades": changed_trades,
        "sizing_attribution": sizing_attribution,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row["passed"]]
    pool = passed if passed else candidates
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
            "risk_multiplier": row["risk_multiplier"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
            "entered_signal_count": row["gate4"]["entered_signal_count"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            "drawdown_guardrail_passed": row["gate4"]["drawdown_guardrail_passed"],
        }
        for row in candidates
    ]


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Signals | Entered | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.2f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {entered} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                entered=row["entered_signal_count"],
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Survival | Signals | Entered |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows = payload["adjustments"][label]
        entered = sum(1 for row in rows if int(row.get("shares_to_buy") or 0) > 0)
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {adj} | {entered} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                adj=len(rows),
                entered=entered,
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Trend Industrials Zero-Risk Replacement",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: replay-only nonzero value for `TREND_INDUSTRIALS_RISK_MULTIPLIER` on existing `trend_long` / Industrials signals. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and the separate `breakout_long` Industrials gap rule were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected multiplier: `{payload['parameters']['selected_risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. Positive promotion requires changing the shared constant or policy, adding focused parity tests, and rerunning the canonical three-window backtest before live behavior changes.",
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
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_trend_industrials_zero_risk_replacement"
    )
    interpretation = (
        "Restoring a small trend Industrials risk multiplier cleared the canonical three-window scout and requires shared-policy promotion work before production use."
        if passed
        else "Restoring trend Industrials risk did not clear the canonical three-window gate; the current zero-risk rule remains the safer production default on these frozen windows."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The fixed zero-risk rule for `trend_long` Industrials may be "
            "over-killing currently high-quality industrial trend candidates; a "
            "small nonzero risk scalar could recover replacement value without "
            "opening the separate Industrials breakout-gap pocket."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "trend_industrials_risk_multiplier",
        "single_causal_variable": (
            "replay-only scalar for existing `trend_long` / Industrials signals"
        ),
        "parameters": {
            "target_strategy": TARGET_STRATEGY,
            "target_sector": TARGET_SECTOR,
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all non-Industrials sizing multipliers",
                "breakout Industrials gap multiplier",
                "portfolio heat",
                "LLM/news replay",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: `trend_long` Industrials may be overly zeroed "
                "after the current accepted core stack."
            ),
            "2_history_check": {
                "current_constant": (
                    "`TREND_INDUSTRIALS_RISK_MULTIPLIER` is 0.0 in shared sizing; "
                    "this run only tests whether a conservative nonzero restore "
                    "has replacement value."
                ),
                "candidate_pool_limits": (
                    "Recent Space/second-order pool expansions were sample/noise "
                    "limited; this keeps the core candidate set fixed."
                ),
                "llm_soft_ranking": (
                    "LLM soft-ranking attribution remains insufficient, so this "
                    "deterministic replay avoids that data bottleneck."
                ),
                "green_decel_core": (
                    "The newest accepted core edge is a small allocation state, "
                    "so this tests another existing allocation kill-switch rather "
                    "than a new filter or lifecycle rule."
                ),
            },
            "3_single_causal_variable": (
                "Only the `trend_long` Industrials risk scalar changes; the "
                "separate breakout Industrials gap scalar stays fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL "
                "positive, at least two EV-improved windows, no EV-regressed "
                "windows, survival >= 5%, nonzero adjusted/entered signals, "
                "and max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_011_trend_industrials_zero_risk_replacement.py"
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
            "baseline_artifact": (
                "data/experiments/exp-20260516-009/"
                "green_decel_quality_nonconsumer_risk.json"
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "risk_engine strategy",
                "risk_engine sector",
                "portfolio_engine TREND_INDUSTRIALS_RISK_MULTIPLIER",
                "portfolio_engine trend_industrials_risk_multiplier_applied",
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
                "LLM ranking/news semantics were not changed; this deterministic "
                "allocation scout avoids the known soft-ranking data limitation."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, change the shared constant/policy, add focused "
                "production/backtest parity tests, and rerun all three canonical "
                "windows before production use."
            ),
        },
        "why_not_other_changes": (
            "This run avoids the LLM/SEC field bottleneck and avoids another "
            "candidate-pool expansion because recent pool extensions were "
            "sample-limited or noisy. It changes one existing core allocation "
            "kill-switch instead."
        ),
        "known_risks": [
            "The cohort may still be too sparse to promote even if aggregate EV is positive.",
            "Any accepted result would require a shared policy change; this scout is replay-only.",
            "Existing zero-risk Industrials evidence may have come from older residual audits not fully represented by current candidates.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": (
            None
            if passed
            else "Do not retry nearby Industrials trend risk scalars on these frozen windows without a new production-visible discriminator or forward Industrials replacement-value evidence."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_011_trend_industrials_zero_risk_replacement.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
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
                "selected_risk_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "max_drawdown_worse": result["gate4"]["max_drawdown_worse"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "entered_signal_count": result["gate4"]["entered_signal_count"],
                "sweep_summary": result["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
