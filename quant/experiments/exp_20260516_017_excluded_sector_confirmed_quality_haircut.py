"""exp-20260516-017: excluded-sector confirmed-quality haircut scout.

Tests one production-visible risk-allocation state on the accepted core stack:
already-qualified Consumer Discretionary / Communication Services
trend/breakout signals that also carry the accepted core_confirmed_quality_state.
This is a replay scout only; it changes no production-default entries, exits,
ranking, universe, LLM, or news behavior.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260516_016_consumer_confirmed_quality_haircut as scout


EXPERIMENT_ID = "exp-20260516-017"
EXPERIMENT_SLUG = "excluded_sector_confirmed_quality_haircut"
MULTIPLIER_KEY = "excluded_sector_confirmed_quality_haircut_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [0.95, 0.90, 0.85, 0.75]
EXCLUDED_SECTORS = {"Consumer Discretionary", "Communication Services"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_ADJUSTED_SIGNAL_COUNT = 3
MIN_ADJUSTED_WINDOW_COUNT = 2
WINDOWS = scout.WINDOWS


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        for sig in enriched:
            state = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sig.get("sector") in EXCLUDED_SECTORS
                and sig.get("core_confirmed_quality_state") is True
            )
            sig["excluded_sector_confirmed_quality_state"] = state
            # Reuse the existing scout size wrapper without changing its mechanics.
            sig["consumer_confirmed_quality_state"] = state
        return enriched

    return wrapped


def _configure_modules() -> None:
    scout.EXPERIMENT_ID = EXPERIMENT_ID
    scout.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    scout.MULTIPLIER_KEY = MULTIPLIER_KEY
    scout.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    scout.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    scout.MIN_ADJUSTED_SIGNAL_COUNT = MIN_ADJUSTED_SIGNAL_COUNT
    scout.MIN_ADJUSTED_WINDOW_COUNT = MIN_ADJUSTED_WINDOW_COUNT
    scout.WINDOWS = WINDOWS
    scout._make_enrich_wrapper = _make_enrich_wrapper
    base.WINDOWS = WINDOWS
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = lambda original: original
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = scout._make_size_wrapper
    base._markdown = _markdown


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Windows | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.2f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {windows} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                windows=", ".join(row["adjusted_windows"]) or "-",
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |",
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
            f"# {EXPERIMENT_ID} Excluded-Sector Confirmed-Quality Haircut",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing haircut for existing Consumer Discretionary / Communication Services `trend_long` / `breakout_long` signals that already have `core_confirmed_quality_state=true`. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.",
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
            "Production impact: replay-only scout. A positive promotion must move the same state and sizing helper into shared `risk_engine.py` / `portfolio_engine.py`, add attribution-key parity, and rerun the canonical three-window backtest before any production behavior changes.",
        ]
    )


def run() -> dict[str, Any]:
    _configure_modules()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: base._run_window(label, variant=False) for label in base.WINDOWS
    }
    candidates = [
        scout._candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = scout._select_candidate(candidates)

    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_excluded_sector_confirmed_quality_haircut"
    )
    interpretation = (
        "Excluded-sector confirmed-quality haircut cleared the canonical three-window scout and requires shared policy implementation before production use."
        if selected["passed"]
        else "Excluded-sector confirmed-quality haircut did not clear the canonical three-window gate; do not weaken the accepted confirmed-quality top-up for this sector group on frozen windows."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The newest accepted green-deceleration quality rule excluded "
            "Consumer Discretionary and Communication Services. If those "
            "consumer/platform sectors are also lower-quality recipients of the "
            "accepted core_confirmed_quality top-up, a modest post-sizing haircut "
            "should improve EV without changing the candidate set."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "excluded_sector_confirmed_quality_haircut_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing haircut multiplier for Consumer Discretionary "
            "or Communication Services trend/breakout signals with "
            "core_confirmed_quality_state=True"
        ),
        "parameters": {
            "state_definition": {
                "sectors": sorted(EXCLUDED_SECTORS),
                "strategies": ["trend_long", "breakout_long"],
                "core_confirmed_quality_state": True,
            },
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_adjusted_signal_count": MIN_ADJUSTED_SIGNAL_COUNT,
            "minimum_adjusted_window_count": MIN_ADJUSTED_WINDOW_COUNT,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers except selected post-sizing haircut",
                "portfolio heat",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation on accepted core candidates; fits the playbook's "
                "preference for production-visible allocation states on the fixed "
                "candidate set and avoids data-limited LLM/SEC branches"
            ),
            "2_history_check": {
                "exp-20260516-016": (
                    "Consumer-only confirmed-quality haircut was directionally "
                    "positive but failed the sample guard with only two adjusted "
                    "signals; this tests the broader green-deceleration excluded "
                    "sector group, not another nearby scalar on the same cohort"
                ),
                "exp-20260516-009": (
                    "green-deceleration quality top-up accepted a non-consumer, "
                    "non-communication sector restriction; this run tests whether "
                    "that sector-quality clue also applies to the accepted confirmed-quality top-up"
                ),
                "LLM soft-ranking": (
                    "LLM attribution remains sample/data-limited, so this run uses "
                    "deterministic fields already present in prompt-independent production code"
                ),
            },
            "3_single_causal_variable": (
                "excluded_sector_confirmed_quality_haircut_multiplier with fixed state definition"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
                "at least three adjusted signals across at least two windows, and max "
                "drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260516_017_excluded_sector_confirmed_quality_haircut.py"
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
                "risk_engine core_confirmed_quality_state",
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
                "If accepted, implement the exact state in shared risk/sizing "
                "policy, expose the attribution key in both adapters, add focused "
                "parity tests, and rerun all three canonical windows."
            ),
        },
        "why_not_other_changes": (
            "This avoids LLM/SEC branches because PIT semantic attribution is "
            "still insufficient, avoids Space/event-sleeve retunes because recent "
            "positives are default-off and sample constrained, avoids broad ticker "
            "pool growth, and avoids nearby accepted scalar retunes without a new "
            "sector-quality discriminator."
        ),
        "known_risks": [
            "The state may still be sector-specific overfit if adjusted trades remain sparse.",
            "It directly weakens part of an accepted top-up, so promotion needs stronger evidence than a tiny aggregate lift.",
            "A positive replay scout is not production-tradable until shared policy and parity tests exist.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else "Do not retry nearby excluded-sector confirmed-quality haircuts on these frozen windows; future work needs a broader production-visible risk state or forward evidence."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_017_excluded_sector_confirmed_quality_haircut.py",
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
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "adjusted_windows": result["gate4"]["adjusted_windows"],
            },
            indent=2,
            sort_keys=True,
        )
    )
