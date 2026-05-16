"""exp-20260516-026: signal-day ATR expansion top-up sweep.

Tests the opposite inference from exp-20260516-022. The prior run treated
same-day top-quartile ATR expansion as chase/exhaustion risk and haircuts
regressed all three windows. This run keeps that production-visible state fixed
and tests whether it is instead a breakout-strength allocation signal.

This is a replay scout only; no production-default strategy behavior changes
unless a separate shared-policy promotion is made and revalidated.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

import exp_20260516_022_signal_day_atr_expansion_risk as scout


EXPERIMENT_ID = "exp-20260516-026"
EXPERIMENT_SLUG = "signal_day_atr_expansion_topup"
MULTIPLIER_KEY = "signal_day_atr_expansion_topup_multiplier_applied"
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [BASELINE_RISK_MULTIPLIER, 1.0125, 1.025, 1.05, 1.075]
MAX_DRAWDOWN_WORSE_GUARDRAIL = scout.MAX_DRAWDOWN_WORSE_GUARDRAIL
MIN_AFFECTED_SIGNAL_COUNT = scout.MIN_AFFECTED_SIGNAL_COUNT
MIN_AFFECTED_WINDOW_COUNT = scout.MIN_AFFECTED_WINDOW_COUNT


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0 or scalar <= 1.0:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    cap_pct = float(
        sizing.get("max_position_pct_applied")
        or scout.base.portfolio_engine.MAX_POSITION_PCT
    )
    cap_shares = max(1, int(math.floor(portfolio_value * cap_pct / entry)))
    desired_shares = max(shares, int(math.floor(shares * scalar)))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= shares:
        return sizing

    out = dict(sizing)
    out["signal_day_atr_expansion_topup_baseline_shares"] = shares
    out["signal_day_atr_expansion_topup_desired_shares"] = desired_shares
    out["signal_day_atr_expansion_topup_cap_shares"] = cap_shares
    out["signal_day_atr_expansion_topup_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4)
        if portfolio_value
        else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (
        (net_risk_per_share * new_shares) / portfolio_value
        if portfolio_value
        else 0.0
    )
    out[MULTIPLIER_KEY] = scalar
    return out


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.4f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
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
    for label in scout.base.WINDOWS:
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
            f"# {EXPERIMENT_ID} Signal-Day ATR Expansion Top-Up",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout stock signals whose signal-day `atr_expansion` is in the same-day non-ETF/non-commodity top quartile. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.",
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
            "Production impact: replay-only scout. A positive promotion must add shared `risk_engine` ATR-expansion state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.",
        ]
    )


def _configure_scout_module() -> None:
    scout.EXPERIMENT_ID = EXPERIMENT_ID
    scout.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    scout.MULTIPLIER_KEY = MULTIPLIER_KEY
    scout.BASELINE_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
    scout.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    scout.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    scout.MIN_AFFECTED_SIGNAL_COUNT = MIN_AFFECTED_SIGNAL_COUNT
    scout.MIN_AFFECTED_WINDOW_COUNT = MIN_AFFECTED_WINDOW_COUNT
    scout.CURRENT_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
    scout._scale_sizing = _scale_sizing
    scout._markdown = _markdown
    scout._configure_modules()


def run() -> dict[str, Any]:
    _configure_scout_module()
    gate2 = scout.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: scout._run_window_with_multiplier(label, BASELINE_RISK_MULTIPLIER)
        for label in scout.base.WINDOWS
    }
    candidates = [
        scout._candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = scout._select_candidate(candidates)

    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_signal_day_atr_expansion_topup"
    )
    interpretation = (
        "Signal-day top-quartile ATR expansion top-up cleared the canonical three-window scout and requires shared risk/portfolio promotion plus rerun before production use."
        if selected["passed"]
        else "Signal-day top-quartile ATR expansion top-up did not clear the canonical three-window gate."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The failed exp-20260516-022 haircut is evidence that signal-day "
            "top-quartile ATR expansion may be a real breakout-strength state, "
            "not exhaustion. A small cap-aware top-up can improve EV on the "
            "fixed candidate set without changing entries, filters, ranking, "
            "exits, LLM/news, or candidate pool."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "signal_day_atr_expansion_topup_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing top-up multiplier for signal-day top-quartile "
            "ATR expansion trend/breakout stock signals"
        ),
        "parameters": {
            "state_definition": {
                "feature": "atr_expansion",
                "cutoff": "same-day non-ETF/non-commodity top quartile",
                "top_fraction": scout.TOP_FRACTION,
                "strategies": sorted(scout.STATE_STRATEGIES),
                "excluded_sectors": sorted(scout.EXCLUDED_SECTORS),
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
                "all existing sizing multipliers",
                "portfolio heat",
                "slot planning",
                "LLM/news replay",
                "event sleeves",
                "candidate pool",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation on a production-visible signal-day ATR expansion "
                "strength state; this follows the playbook preference for fixed "
                "candidate-set allocation and avoids LLM/SEC field limitations"
            ),
            "2_history_check": {
                "exp-20260516-022": (
                    "The same state failed as a haircut: EV and PnL regressed in "
                    "all three canonical windows, implying the state may carry "
                    "positive breakout-strength information."
                ),
                "exp-20260514-008": (
                    "Rejected broad SPY volatility-expansion haircut; this tests "
                    "ticker-level signal-day range expansion, not market-wide volatility."
                ),
                "exp-20260515-042_and_049": (
                    "Rejected close-location/gap absorption families; this uses ATR "
                    "range expansion only and does not alter entries."
                ),
                "llm_and_candidate_pool": (
                    "LLM soft-ranking/SEC fields remain attribution-limited, and recent "
                    "candidate-pool additions added noise or old-window regression."
                ),
            },
            "3_single_causal_variable": (
                "signal_day_atr_expansion_topup_multiplier with fixed top-quartile state"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
                "at least six affected signals across at least two windows, and max drawdown "
                "drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260516_026_signal_day_atr_expansion_topup.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": scout.base.WINDOWS,
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
                "feature_layer atr_expansion",
                "risk_engine sector",
                "risk_engine strategy",
                "portfolio_engine shares_to_buy",
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
        "sweep_summary": scout._sweep_summary(candidates),
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
                "If accepted, add the ATR-expansion state and sizing key in shared "
                "risk_engine.py/portfolio_engine.py paths used by both backtester.py "
                "and run.py, then rerun all three canonical windows."
            ),
        },
        "why_not_other_changes": (
            "This avoids LLM/SEC branches because PIT semantic attribution is still "
            "insufficient, avoids Space peer-state retries after zero incremental "
            "EV/PnL, avoids nearby Technology DTE scalar retries after exp-20260516-020, "
            "and avoids candidate-pool expansion because recent breadth additions added noise."
        ),
        "known_risks": [
            "ATR-expansion can be a broad momentum proxy, so excessive top-up can amplify drawdown.",
            "The top-quartile boundary is production-visible but still frozen-window selected.",
            "A positive replay scout is not production-tradable until shared risk and sizing code are promoted and rerun.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else "Do not retry nearby ATR-expansion top-up scalars on these frozen windows without a narrower production-visible discriminator or forward hold-quality evidence."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_026_signal_day_atr_expansion_topup.py",
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
    scout.base.persist(result)
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
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
