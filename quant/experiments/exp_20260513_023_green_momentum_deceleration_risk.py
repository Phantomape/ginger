"""exp-20260513-023: green-candle momentum-deceleration risk allocation.

Tests one production-visible state variable on the accepted core stack:
trend/breakout signals whose accepted signal-day own candle is green, whose
10-day and 20-day momentum are both positive, and whose 10-day momentum is
below 20-day momentum. This is a cap-aware post-sizing risk top-up scout, not
an entry filter, ranking change, exit change, or production default change.
"""

from __future__ import annotations

import json
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260513_013_green_momentum_acceleration_risk as scaffold


EXPERIMENT_ID = "exp-20260513-023"
EXPERIMENT_SLUG = "green_momentum_deceleration_risk"
MULTIPLIER_KEY = "green_momentum_deceleration_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.05, 1.10, 1.15, 1.20, 1.25]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _is_deceleration_state(mom10: Any, mom20: Any) -> bool:
    return (
        isinstance(mom10, (int, float))
        and isinstance(mom20, (int, float))
        and mom10 > 0
        and mom20 > 0
        and mom10 < mom20
    )


def _rewrite_payload(payload: dict[str, Any]) -> dict[str, Any]:
    selected_multiplier = payload["parameters"]["selected_risk_multiplier"]
    max_drawdown_worse = max(
        float(delta.get("max_drawdown_pct") or 0.0)
        for delta in payload["delta_metrics"]["by_window"].values()
    )
    drawdown_guardrail_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    passed = bool(payload["gate4"]["passed"]) and drawdown_guardrail_passed
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_green_momentum_deceleration_risk"
    )
    interpretation = (
        "Green-candle momentum-deceleration core risk top-up cleared the canonical three-window gate and requires shared policy implementation before production use."
        if passed
        else "Green-candle momentum-deceleration core risk top-up improved EV but did not clear the canonical three-window gate because max drawdown worsened beyond the guardrail; do not promote this state variable without a stronger discriminator."
    )

    payload["experiment_id"] = EXPERIMENT_ID
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Core trend/breakout signals with accepted signal-day green confirmation but positive, non-accelerating momentum may be less overextended than the rejected acceleration cohort and may deserve a modest cap-aware capital top-up."
    )
    payload["change_type"] = "risk_allocation_shadow"
    payload["changed_variable"] = "green_momentum_deceleration_risk_multiplier"
    payload["single_causal_variable"] = (
        "cap-aware post-sizing risk top-up for trend/breakout signals where signal_day_ticker_green_candle is true and momentum_10d_pct < momentum_20d_pct with both positive"
    )
    payload["parameters"] = {
        "state_definition": {
            "strategies": ["trend_long", "breakout_long"],
            "signal_day_ticker_green_candle": True,
            "momentum_10d_pct": "> 0",
            "momentum_20d_pct": "> 0",
            "deceleration_condition": "momentum_10d_pct < momentum_20d_pct",
        },
        "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
        "selected_risk_multiplier": selected_multiplier,
        "locked_variables": [
            "core universe",
            "entry filters",
            "candidate ranking",
            "stop and target logic",
            "all existing sizing multipliers",
            "portfolio heat",
            "LLM/news replay",
            "pilot sleeves",
        ],
    }
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "core state risk allocation using production-visible signal-day green confirmation plus positive momentum deceleration"
        ),
        "2_history_check": {
            "exp-20260513-007": (
                "accepted own-green 1.05x cap-aware top-up; remains locked as baseline, this tests a narrower non-accelerating overlay."
            ),
            "exp-20260513-013": (
                "green-candle momentum acceleration top-up improved late/mid but regressed old_thin, so this run tests the complementary mature-positive momentum state instead of retrying acceleration."
            ),
            "exp-20260512-111": (
                "broad momentum acceleration improved late/mid but regressed old_thin; this run avoids broad acceleration and keeps the accepted green-candle discriminator."
            ),
            "exp-20260513-011": (
                "ticker-vs-SPY signal-day excess margin failed drawdown guardrails; this run does not use benchmark-relative signal-day thresholds."
            ),
            "exp-20260513-020": (
                "idiosyncratic own-green while SPY red improved late only and regressed mid/old; this run does not add benchmark-red state."
            ),
            "llm_soft_ranking": "data remains thin, so this run avoids LLM soft-ranking.",
            "space_theme_scalars": "recent frozen-sample theme slicing was over-mined, so this run returns to core allocation.",
        },
        "3_single_causal_variable": (
            "green_momentum_deceleration_risk_multiplier with fixed production-visible green-plus-positive-deceleration state"
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%."
        ),
        "5_reproducibility": (
            "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_023_green_momentum_deceleration_risk.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "feature_layer momentum_10d_pct",
        "feature_layer momentum_20d_pct",
        "risk_engine signal_day_ticker_green_candle",
        "risk_engine enriched strategy",
        "portfolio_engine max_position_pct_applied",
    ]
    payload["gate4"]["passed"] = passed
    payload["gate4"]["max_drawdown_worse"] = round(max_drawdown_worse, 6)
    payload["gate4"]["max_drawdown_worse_guardrail"] = MAX_DRAWDOWN_WORSE_GUARDRAIL
    payload["gate4"]["drawdown_guardrail_passed"] = drawdown_guardrail_passed
    for row in payload["sweep_summary"]:
        if row["risk_multiplier"] == selected_multiplier:
            row["passed"] = passed
            row["max_drawdown_worse"] = round(max_drawdown_worse, 6)
            row["drawdown_guardrail_passed"] = drawdown_guardrail_passed
    payload["interpretation"] = interpretation
    payload["rejection_reason"] = None if passed else interpretation
    payload["next_evidence_needed"] = (
        None
        if passed
        else "Try a different production-visible core allocation state; do not continue the green-momentum acceleration/deceleration family without a new drawdown discriminator."
    )
    payload["related_files"] = [
        "quant/experiments/exp_20260513_023_green_momentum_deceleration_risk.py",
        "data/experiments/exp-20260513-023/green_momentum_deceleration_risk.json",
        "docs/experiments/logs/exp-20260513-023.json",
        "docs/experiments/tickets/exp-20260513-023.json",
        "docs/experiments/artifacts/exp-20260513-023_green_momentum_deceleration_risk.md",
        "docs/experiment_log.jsonl",
    ]
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals |",
        "|---:|:---:|---:|---:|---|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        dd_note = ""
        if "max_drawdown_worse" in row:
            dd_note = " (DD {dd:+.4f})".format(dd=row["max_drawdown_worse"])
        sweep_rows.append(
            "| {mult:.2f} | {passed}{dd_note} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} |".format(
                mult=row["risk_multiplier"],
                passed="PASS" if row["passed"] else "FAIL",
                dd_note=dd_note,
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
            )
        )
    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Green Momentum Deceleration Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals whose accepted signal-day own candle is green and whose 10-day momentum is below 20-day momentum, with both positive. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected multiplier: `{payload['parameters']['selected_risk_multiplier']}`.",
            f"Selected max-drawdown drift: `{payload['gate4']['max_drawdown_worse']:+.4f}` vs guardrail `{payload['gate4']['max_drawdown_worse_guardrail']:+.4f}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. Positive promotion would require shared `risk_engine` and `portfolio_engine` code plus attribution-key parity before live/default behavior changes.",
        ]
    )


def _configure_scaffold() -> None:
    scaffold.EXPERIMENT_ID = EXPERIMENT_ID
    scaffold.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    scaffold.MULTIPLIER_KEY = MULTIPLIER_KEY
    scaffold.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    scaffold._is_acceleration_state = _is_deceleration_state
    scaffold._markdown = _markdown


def _configure_persist() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._markdown = _markdown


def run() -> dict[str, Any]:
    _configure_scaffold()
    return _rewrite_payload(scaffold.run())


if __name__ == "__main__":
    result = run()
    _configure_persist()
    base.persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_risk_multiplier": result["parameters"]["selected_risk_multiplier"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "sweep_summary": result["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
