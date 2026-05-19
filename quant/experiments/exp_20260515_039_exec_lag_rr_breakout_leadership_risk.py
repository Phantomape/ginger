"""Experiment 039: breakout-only high exec-lag adjusted R:R allocation.

This follows the rejected exp-20260515-038 result. The broad high
``exec_lag_adj_net_rr`` state improved late/mid windows but regressed the
old_thin window through trend-heavy losers. This scout keeps the candidate set
fixed and changes one state variable: the cap-aware risk multiplier for
``breakout_long`` signals in the same-day top quartile of exec-lag-adjusted
R:R.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260513_031_signal_day_range_compression_risk as sweep
import exp_20260515_038_exec_lag_rr_leadership_risk as prior


EXPERIMENT_ID = "exp-20260515-039"
EXPERIMENT_SLUG = "exec_lag_rr_breakout_leadership_risk"
MULTIPLIER_KEY = "exec_lag_rr_breakout_leadership_risk_multiplier_applied"

RR_TOP_FRACTION = 0.25
EXCLUDED_SECTORS = {"ETF", "Commodities"}
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075, 1.10]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _is_candidate(signal: dict[str, Any]) -> bool:
    strategy = str(signal.get("strategy") or "").lower()
    sector = signal.get("sector")
    return (
        sector not in EXCLUDED_SECTORS
        and strategy == "breakout_long"
        and prior._is_finite(signal.get("exec_lag_adj_net_rr"))
    )


def _markdown(payload: dict[str, Any]) -> str:
    selected = payload["selected_candidate"]
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = selected["before"][label]
        after = selected["after"][label]
        delta = selected["delta"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:.4f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=after["max_drawdown_pct"],
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )

    sweep_rows = [
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.4f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                dd=row["max_drawdown_worse"],
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Exec-Lag R:R Breakout Leadership Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk top-up for already-qualified non-ETF/non-commodity `breakout_long` signals whose `exec_lag_adj_net_rr` is in the same-day breakout top quartile. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and existing sizing rules were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected multiplier: `{selected['risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *rows,
            "",
            "Production impact: replay-only scout. A passing result must be promoted through shared risk/sizing policy and parity tests before production-visible behavior changes.",
        ]
    )


def _risk_distribution(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {
            "worst_trade_pct": row.get("worst_trade_pct"),
            "max_consecutive_losses": row.get("max_consecutive_losses"),
            "tail_loss_share": row.get("tail_loss_share"),
        }
        for label, row in metrics.items()
    }


def _configure_modules() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.MULTIPLIER_KEY = MULTIPLIER_KEY
    prior.RR_TOP_FRACTION = RR_TOP_FRACTION
    prior.EXCLUDED_SECTORS = EXCLUDED_SECTORS
    prior.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    prior.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    prior._is_candidate = _is_candidate
    prior._markdown = _markdown
    prior._configure_modules()


def run() -> dict[str, Any]:
    _configure_modules()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: base._run_window(label, variant=False) for label in base.WINDOWS}
    candidates = [
        sweep._candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = sweep._select_candidate(candidates)
    selected_candidate = {
        "risk_multiplier": selected["risk_multiplier"],
        "aggregate_before": selected["delta_metrics"]["aggregate_before"],
        "aggregate_after": selected["delta_metrics"]["aggregate_after"],
        "aggregate_delta": selected["delta_metrics"]["aggregate_delta"],
        "before": selected["before_metrics"],
        "after": selected["after_metrics"],
        "delta": selected["delta_metrics"]["by_window"],
        "passes": selected["passed"],
        "gate4": selected["gate4"],
    }

    passed = bool(selected["passed"])
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_exec_lag_rr_breakout_leadership_risk"
    )
    interpretation = (
        "Breakout-only exec-lag R:R leadership cleared the three-window scout; promotion requires shared production/backtest policy."
        if passed
        else "Breakout-only exec-lag R:R leadership did not clear the canonical three-window gate."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "experiment_slug": EXPERIMENT_SLUG,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The broad high exec-lag-adjusted R:R allocation failed because old_thin trend signals absorbed the extra risk. "
            "Restricting the same geometric leadership concept to already-qualified breakout_long signals may preserve the late/mid upside while avoiding the old_thin trend-loss cluster."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "exec_lag_rr_breakout_leadership_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk multiplier for breakout_long signals in the same-day top quartile of exec_lag_adj_net_rr"
        ),
        "parameters": {
            "rr_top_fraction": RR_TOP_FRACTION,
            "state_definition": {
                "strategy": "breakout_long",
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
                "exec_lag_adj_net_rr": "same-day breakout top quartile",
            },
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "portfolio heat",
                "MAX_POSITIONS",
                "LLM/news replay",
                "pilot/event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "exp-20260515-038": (
                "Rejected broad top-quartile exec_lag_adj_net_rr allocation: aggregate EV/PnL positive, late/mid improved, but old_thin regressed and drawdown breached at higher scalar. This run changes the state definition to breakout-only instead of retuning the same broad scalar."
            ),
            "exp-20260513-001": (
                "Rejected breakout strong-volume scalar as immaterial; this run uses execution-lag-adjusted payoff geometry, not volume."
            ),
            "exp-20260513-027": (
                "Rejected own-green slot priority; this run does not alter ranking or slots."
            ),
            "why_not_llm_or_event": (
                "LLM soft-ranking, SEC semantics, options, Form 4, and Space branches are currently data- or sample-limited in recent records; this run uses deterministic production-visible fields on the fixed core candidate set."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: among already-qualified core breakouts, top-quartile exec-lag-adjusted R:R marks cleaner convex setups worth a small cap-aware top-up."
            ),
            "2_history_check": (
                "Broad high-R:R top-up failed in exp-20260515-038 due old_thin trend losses; volume breakout scalar was immaterial in exp-20260513-001. No breakout-only high-R:R scout was found."
            ),
            "3_single_causal_variable": (
                "exec_lag_rr_breakout_leadership_risk_multiplier with a fixed breakout-only top-quartile state"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 pp, nonzero adjustments."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_039_exec_lag_rr_breakout_leadership_risk.py"
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
                "risk_engine exec_lag_adj_net_rr",
                "risk_engine strategy",
                "risk_engine sector",
                "portfolio_engine sizing shares_to_buy",
                "portfolio_engine sizing max_position_pct_applied",
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
        "baseline_metrics": selected["delta_metrics"]["aggregate_before"],
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "selected_candidate": selected_candidate,
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "sweep_summary": sweep._sweep_summary(candidates),
        "risk_distribution": {
            "before": _risk_distribution(selected["before_metrics"]),
            "after": _risk_distribution(selected["after_metrics"]),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Recent LLM soft-ranking and event-semantics records remain data-limited; this scout used deterministic shared fields instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_accepted": (
                "Implement the state in shared risk/portfolio modules used by run.py and backtester.py; add attribution keys and focused parity tests before live/default behavior changes."
            ),
        },
        "production_impact_closeout": {
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
            "Do not retry simple exec_lag_adj_net_rr breakout-only scalars without forward breakout payoff-geometry attribution or a materially different drawdown discriminator."
        ),
        "related_files": [
            "quant/experiments/exp_20260515_039_exec_lag_rr_breakout_leadership_risk.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "This run avoids LLM soft-ranking, SEC/Form 4/options overlays, and Space/candidate-pool expansion because recent records show data, outcome, or sample limits. It also avoids another broad high-R:R scalar retry by changing the state to breakout-only."
        ),
    }
    payload["artifact_markdown"] = _markdown(payload)
    base.persist(payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_multiplier": result["parameters"]["selected_multiplier"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "max_drawdown_worse": result["gate4"]["max_drawdown_worse"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "production_impact": result["production_impact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
