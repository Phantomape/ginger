"""exp-20260516-009: green-deceleration quality non-consumer risk.

Tests one production-visible allocation state on the accepted core stack:
already-qualified trend/breakout signals with own signal-day green confirmation,
positive but decelerating 10d-vs-20d momentum, trade_quality_score >= 0.95, and
not in Consumer Discretionary / Communication Services. This is a replay scout
only; it changes no production-default entries, exits, ranking, universe, LLM,
or news behavior.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260513_013_green_momentum_acceleration_risk as scaffold


EXPERIMENT_ID = "exp-20260516-009"
EXPERIMENT_SLUG = "green_decel_quality_nonconsumer_risk"
MULTIPLIER_KEY = "green_decel_quality_nonconsumer_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_TRADE_QUALITY_SCORE = 0.95
EXCLUDED_SECTORS = {"Communication Services", "Consumer Discretionary"}
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


def _is_positive_deceleration(mom10: Any, mom20: Any) -> bool:
    return (
        isinstance(mom10, (int, float))
        and isinstance(mom20, (int, float))
        and mom10 > 0
        and mom20 > 0
        and mom10 < mom20
    )


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
            ticker = str(sig.get("ticker") or "")
            features = features_dict.get(ticker) or {}
            mom10 = features.get("momentum_10d_pct")
            mom20 = features.get("momentum_20d_pct")
            tqs = sig.get("trade_quality_score")
            sector = sig.get("sector")
            state = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sig.get("signal_day_ticker_green_candle") is True
                and _is_positive_deceleration(mom10, mom20)
                and isinstance(tqs, (int, float))
                and tqs >= MIN_TRADE_QUALITY_SCORE
                and sector not in EXCLUDED_SECTORS
            )
            sig["momentum_10d_pct"] = mom10
            sig["momentum_20d_pct"] = mom20
            sig["momentum_deceleration_spread_pct"] = (
                round(mom10 - mom20, 6)
                if isinstance(mom10, (int, float))
                and isinstance(mom20, (int, float))
                else None
            )
            sig["green_momentum_acceleration_state"] = state
            sig["green_decel_quality_nonconsumer_state"] = state
        return enriched

    return wrapped


def _apply_drawdown_guard(candidate: dict[str, Any]) -> dict[str, Any]:
    max_drawdown_worse = max(
        float(delta.get("max_drawdown_pct") or 0.0)
        for delta in candidate["delta_metrics"]["by_window"].values()
    )
    drawdown_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    candidate["gate4"]["max_drawdown_worse"] = round(max_drawdown_worse, 6)
    candidate["gate4"]["max_drawdown_worse_guardrail"] = (
        MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    candidate["gate4"]["drawdown_guardrail_passed"] = drawdown_passed
    candidate["passed"] = bool(candidate["passed"]) and drawdown_passed
    candidate["gate4"]["passed"] = candidate["passed"]
    return candidate


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row["passed"]]
    pool = passed if passed else candidates
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
                "passed": row["passed"],
                "expected_value_score_delta": row["expected_value_score_delta"],
                "total_pnl_delta": row["total_pnl_delta"],
                "improved_windows": row["gate4"]["improved_windows"],
                "regressed_windows": row["gate4"]["regressed_windows"],
                "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
                "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
                "drawdown_guardrail_passed": row["gate4"][
                    "drawdown_guardrail_passed"
                ],
            }
        )
    return rows


def _markdown(payload: dict[str, Any]) -> str:
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
            f"# {EXPERIMENT_ID} Green Deceleration Quality Non-Consumer Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing top-up for existing `trend_long` / `breakout_long` signals with own signal-day green confirmation, positive but decelerating 10d-vs-20d momentum, `trade_quality_score >= 0.95`, and sector outside Consumer Discretionary / Communication Services. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.",
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


def _configure_modules() -> None:
    base.WINDOWS = WINDOWS
    scaffold.EXPERIMENT_ID = EXPERIMENT_ID
    scaffold.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    scaffold.MULTIPLIER_KEY = MULTIPLIER_KEY
    scaffold.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    scaffold._make_compute_features_wrapper = lambda original: original
    scaffold._make_enrich_wrapper = _make_enrich_wrapper
    scaffold._markdown = _markdown

    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = lambda original: original
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = scaffold._make_size_wrapper
    base._markdown = _markdown


def run() -> dict[str, Any]:
    _configure_modules()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: base._run_window(label, variant=False) for label in base.WINDOWS
    }
    candidates = [
        _apply_drawdown_guard(scaffold._candidate_payload(multiplier, before_runs))
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)

    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_green_decel_quality_nonconsumer_risk"
    )
    interpretation = (
        "Green-deceleration high-quality non-consumer allocation cleared the canonical three-window scout and requires shared policy implementation before production use."
        if selected["passed"]
        else "Green-deceleration high-quality non-consumer allocation did not clear the canonical three-window gate; do not promote this cohort without a stronger production-visible discriminator."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The prior current-stack green momentum-deceleration top-up had positive "
            "aggregate EV but failed the drawdown guardrail. Restricting the state "
            "to high-quality non-consumer/non-communication candidates may keep the "
            "mature trend-continuation edge while avoiding the old-window fragility "
            "seen in consumer and communication names."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "green_decel_quality_nonconsumer_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk top-up for trend/breakout signals with "
            "own-green confirmation, positive 10d/20d momentum deceleration, "
            "trade_quality_score >= 0.95, and non-consumer/non-communication sector"
        ),
        "parameters": {
            "state_definition": {
                "strategies": ["trend_long", "breakout_long"],
                "signal_day_ticker_green_candle": True,
                "momentum_10d_pct": "> 0",
                "momentum_20d_pct": "> 0",
                "deceleration_condition": "momentum_10d_pct < momentum_20d_pct",
                "trade_quality_score_min": MIN_TRADE_QUALITY_SCORE,
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
            },
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "portfolio heat",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "core risk allocation using production-visible own-green, "
                "positive momentum deceleration, setup quality, and sector risk"
            ),
            "2_history_check": {
                "exp-20260516-004": (
                    "Current-stack broad green momentum deceleration improved "
                    "aggregate EV/PnL but failed drawdown; this run adds the "
                    "quality/sector discriminator instead of retrying a nearby scalar."
                ),
                "exp-20260515-045": (
                    "Simple reversal green confirmation was positive aggregate but "
                    "old-window fragile; this run avoids prior-day reversal logic."
                ),
                "exp-20260515-042": (
                    "Simple close-location risk top-up failed; this run uses "
                    "multi-day momentum state plus TQS and sector scope."
                ),
                "SEC/LLM branches": (
                    "Fresh PIT SEC directional fields and LLM soft-ranking "
                    "attribution remain insufficient, so this run avoids those data limits."
                ),
            },
            "3_single_causal_variable": (
                "green_decel_quality_nonconsumer_risk_multiplier with fixed cohort definition"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
                "nonzero adjusted signals, and max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260516_009_green_decel_quality_nonconsumer_risk.py"
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
                "feature_layer momentum_10d_pct",
                "feature_layer momentum_20d_pct",
                "risk_engine signal_day_ticker_green_candle",
                "risk_engine trade_quality_score",
                "risk_engine sector",
                "portfolio_engine max_position_pct_applied",
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
                "this deterministic OHLCV/risk allocation state avoids those blockers."
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
            "This avoids LLM/SEC branches because their PIT semantic fields are "
            "still insufficient, avoids Space because recent follow-ons are "
            "sample-limited, avoids candidate-pool expansion because recent "
            "second-order and Space breadth additions added noise, and avoids "
            "nearby accepted cap/scalar retunes without a new state variable."
        ),
        "known_risks": [
            "The sector exclusion may still be too sample-specific for promotion.",
            "The state overlaps accepted own-green and confirmed-quality helpers.",
            "A positive replay scout is not production-tradable until shared policy and parity tests exist.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else "Do not retry nearby green-deceleration scalars on these frozen windows; future work needs a genuinely different drawdown or catalyst-quality field."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_009_green_decel_quality_nonconsumer_risk.py",
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
    payload = main()
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "selected_risk_multiplier": payload["parameters"][
                    "selected_risk_multiplier"
                ],
                "expected_value_score_delta": payload[
                    "expected_value_score_delta"
                ],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4_passed": payload["gate4"]["passed"],
                "improved_windows": payload["gate4"]["improved_windows"],
                "regressed_windows": payload["gate4"]["regressed_windows"],
                "max_drawdown_worse": payload["gate4"]["max_drawdown_worse"],
                "adjusted_signal_count": payload["gate4"]["adjusted_signal_count"],
                "sweep_summary": payload["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
