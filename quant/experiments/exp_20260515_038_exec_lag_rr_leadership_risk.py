"""Experiment 038: cap-aware risk top-up for high exec-lag adjusted R:R.

This scout keeps the accepted production stack unchanged and tests one
allocation variable: whether signals in the same-day top quartile of
``exec_lag_adj_net_rr`` deserve a small sizing top-up.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260513_031_signal_day_range_compression_risk as sweep
import portfolio_engine


EXPERIMENT_ID = "exp-20260515-038"
EXPERIMENT_SLUG = "exec_lag_rr_leadership_risk"
MULTIPLIER_KEY = "exec_lag_rr_leadership_risk_multiplier_applied"

RR_TOP_FRACTION = 0.25
EXCLUDED_SECTORS = {"ETF", "Commodities"}
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _is_finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _is_candidate(signal: dict[str, Any]) -> bool:
    strategy = str(signal.get("strategy") or "").lower()
    sector = signal.get("sector")
    return (
        sector not in EXCLUDED_SECTORS
        and strategy in {"trend_long", "breakout_long"}
        and _is_finite(signal.get("exec_lag_adj_net_rr"))
    )


def _top_fraction_cutoff(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(0, math.ceil(len(sorted_values) * (1.0 - fraction)) - 1)
    return sorted_values[index]


def _make_compute_features_wrapper(
    original_compute_features: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    return original_compute_features


def _make_enrich_wrapper(
    original_enrich_signals: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapper(signals: list[dict[str, Any]], *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        enriched = original_enrich_signals(signals, *args, **kwargs)
        rr_values = [float(sig["exec_lag_adj_net_rr"]) for sig in enriched if _is_candidate(sig)]
        cutoff = _top_fraction_cutoff(rr_values, RR_TOP_FRACTION)

        for sig in enriched:
            rr_value = sig.get("exec_lag_adj_net_rr")
            state = bool(
                cutoff is not None
                and _is_candidate(sig)
                and float(rr_value) >= cutoff
            )
            sig["exec_lag_rr_leadership_cutoff"] = cutoff
            sig["exec_lag_rr_leadership_state"] = state
        return enriched

    return wrapper


def _scale_sizing(
    sizing: dict[str, Any],
    multiplier: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing

    entry_price = sizing.get("entry_price")
    if not _is_finite(entry_price) or float(entry_price) <= 0:
        return sizing

    net_risk_per_share = sizing.get("net_risk_per_share")
    if not _is_finite(net_risk_per_share) or float(net_risk_per_share) <= 0:
        return sizing

    cap_pct = float(sizing.get("max_position_pct_applied") or portfolio_engine.MAX_POSITION_PCT)
    cap_shares = int(math.floor(portfolio_value * cap_pct / float(entry_price)))
    target_shares = max(shares, int(math.floor(shares * multiplier)))
    target_shares = min(target_shares, cap_shares)

    if target_shares <= shares:
        return sizing

    risk_amount = target_shares * float(net_risk_per_share)
    position_value = target_shares * float(entry_price)
    out = dict(sizing)
    out["shares_to_buy"] = target_shares
    out["position_value_usd"] = round(position_value, 2)
    out["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4) if portfolio_value else 0.0
    out["risk_amount_usd"] = round(risk_amount, 2)
    out["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    out["exec_lag_rr_leadership_baseline_shares"] = shares
    out["exec_lag_rr_leadership_desired_shares"] = max(
        shares,
        int(math.floor(shares * multiplier)),
    )
    out["exec_lag_rr_leadership_cap_shares"] = cap_shares
    out["exec_lag_rr_leadership_new_shares"] = target_shares
    out[MULTIPLIER_KEY] = round(multiplier, 6)
    return out


def _make_size_wrapper(
    original_size_signals: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapper(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        *args: Any,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        sized = original_size_signals(signals, portfolio_value, *args, **kwargs)
        adjusted: list[dict[str, Any]] = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if not sig.get("exec_lag_rr_leadership_state"):
                adjusted.append(sig)
                continue

            new_sizing = _scale_sizing(sizing, sweep.CURRENT_RISK_MULTIPLIER, portfolio_value)
            if new_sizing is not sizing:
                base.ADJUSTMENTS.append(
                    {
                        "ticker": sig.get("ticker"),
                        "strategy": sig.get("strategy"),
                        "sector": sig.get("sector"),
                        "exec_lag_adj_net_rr": sig.get("exec_lag_adj_net_rr"),
                        "exec_lag_rr_leadership_cutoff": sig.get("exec_lag_rr_leadership_cutoff"),
                        "baseline_shares": sizing.get("shares_to_buy"),
                        "new_shares": new_sizing.get("shares_to_buy"),
                        "baseline_position_value": sizing.get("position_value_usd"),
                        "new_position_value": new_sizing.get("position_value_usd"),
                        "cap_shares": new_sizing.get("exec_lag_rr_leadership_cap_shares"),
                        "core_confirmed_quality_state": sig.get("core_confirmed_quality_state"),
                        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
                        "price_vs_200ma_extension_state": sig.get("price_vs_200ma_extension_state"),
                        "trade_quality_score": sig.get("trade_quality_score"),
                        "market_regime": sig.get("market_regime"),
                    }
                )
                sig = {**sig, "sizing": new_sizing}
            adjusted.append(sig)
        return adjusted

    return wrapper


def _markdown(payload: dict[str, Any]) -> str:
    selected = payload["selected_candidate"]
    lines = [
        f"# {EXPERIMENT_ID} {EXPERIMENT_SLUG}",
        "",
        f"- hypothesis: {payload['hypothesis']}",
        "- change_type: alpha_search",
        "- changed_variable: exec_lag_rr_leadership_risk_multiplier",
        f"- decision: {payload['decision']}",
        f"- selected_multiplier: {selected['risk_multiplier']}",
        f"- aggregate_ev_delta: {selected['aggregate_delta']['expected_value_score_sum']}",
        f"- aggregate_pnl_delta: {selected['aggregate_delta']['total_pnl_sum']}",
        f"- rejection_reason: {payload.get('rejection_reason')}",
        "",
        "## Three-window metrics",
        "",
        "| window | before_ev | after_ev | ev_delta | before_pnl | after_pnl | pnl_delta | after_max_dd | adjusted_signals |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = selected["before"][label]
        after = selected["after"][label]
        delta = selected["delta"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | {bpnl:.2f} | {apnl:.2f} | {dpnl:.2f} | {dd:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=after["max_drawdown_pct"],
                adj=len(payload["adjustments"][label]),
            )
        )

    lines.extend(
        [
            "",
            "## Gate answers",
            "",
            f"- prior_similar_experiment: {payload['prior_similar_experiment']}",
            f"- one_causal_variable: {payload['one_causal_variable']}",
            f"- acceptance_criteria: {payload['acceptance_criteria']}",
            f"- reproducibility: {payload['reproducibility']}",
            "",
            "## Production impact",
            "",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(payload['production_impact']['shared_policy_changed']).lower()}",
            f"  backtester_adapter_changed: {str(payload['production_impact']['backtester_adapter_changed']).lower()}",
            f"  run_adapter_changed: {str(payload['production_impact']['run_adapter_changed']).lower()}",
            f"  replay_only: {str(payload['production_impact']['replay_only']).lower()}",
            f"  parity_test_added: {str(payload['production_impact']['parity_test_added']).lower()}",
            "```",
        ]
    )
    return "\n".join(lines)


def _configure_modules() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = _make_compute_features_wrapper
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown

    sweep.EXPERIMENT_ID = EXPERIMENT_ID
    sweep.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    sweep.MULTIPLIER_KEY = MULTIPLIER_KEY
    sweep.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    sweep.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL


def run() -> dict[str, Any]:
    _configure_modules()
    gate2 = base._audit_open_positions()
    before_runs = {label: base._run_window(label, variant=False) for label in base.WINDOWS}
    candidates = [sweep._candidate_payload(multiplier, before_runs) for multiplier in RISK_MULTIPLIER_SWEEP]
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

    if selected["passed"]:
        decision = "accepted_for_shared_policy_implementation"
        rejection_reason = None
        interpretation = (
            "High exec-lag-adjusted R:R leadership cleared the three-window scout; promotion still requires shared production/backtest policy."
        )
    else:
        decision = "rejected"
        rejection_reason = selected.get("rejection_reason") or "failed_three_window_gate4"
        interpretation = (
            "High exec-lag-adjusted R:R leadership did not clear the canonical three-window gate; do not promote this allocation state."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "experiment_slug": EXPERIMENT_SLUG,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": decision,
        "hypothesis": (
            "Within the accepted fixed candidate stack, trend/breakout signals in the same-day top quartile "
            "of exec_lag_adj_net_rr carry cleaner asymmetric payoff and can support a small cap-aware risk top-up."
        ),
        "change_type": "alpha_search",
        "changed_variable": "exec_lag_rr_leadership_risk_multiplier",
        "parameters": {
            "rr_top_fraction": RR_TOP_FRACTION,
            "excluded_sectors": sorted(EXCLUDED_SECTORS),
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md",
            "windows": base.WINDOWS,
            "command_template": ".\\.venv\\Scripts\\python.exe quant\\backtester.py --start <START> --end <END> --ohlcv-snapshot <SNAPSHOT>",
        },
        "gate1_baseline": selected["before_metrics"],
        "gate2_field_audit": gate2,
        "gate3_survival_rates": {
            label: {
                "before": selected["before_metrics"][label].get("survival_rate"),
                "after": selected["after_metrics"][label].get("survival_rate"),
                "signals_generated_after": selected["after_metrics"][label].get("signals_generated"),
                "signals_survived_after": selected["after_metrics"][label].get("signals_survived"),
            }
            for label in base.WINDOWS
        },
        "gate4_result": {
            "passes": selected["passed"],
            "selected_candidate": selected_candidate,
            "sweep_summary": sweep._sweep_summary(candidates),
        },
        "gate4": selected["gate4"],
        "baseline_metrics": selected["delta_metrics"]["aggregate_before"],
        "after_metrics": selected["delta_metrics"]["aggregate_after"],
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "selected_candidate": selected_candidate,
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "sweep_summary": sweep._sweep_summary(candidates),
        "prior_similar_experiment": (
            "No prior log hit for exec_lag_adj_net_rr top-quartile allocation. Recent failed adjacent ideas were "
            "sector thrust, candidate-pool expansion, mature satcom/Space admissions, and simple momentum/quality scalar overlays."
        ),
        "one_causal_variable": (
            "Only the cap-aware risk multiplier for same-day top-quartile exec_lag_adj_net_rr trend/breakout stock signals changes."
        ),
        "acceptance_criteria": (
            "Follow docs/backtesting.md three-window protocol; require positive aggregate EV/PnL, no EV regression by window, "
            "min survival_rate >= 5%, nonzero adjusted signals, and max_drawdown no worse by more than 0.5 percentage points."
        ),
        "reproducibility": (
            "This file, experiments artifacts, and docs/experiment_log.jsonl contain the parameters, windows, and before/after metrics."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "why_not_other_changes": (
            "LLM soft-ranking and SEC/Form 4 semantics remain data-limited; recent candidate expansion and sector-thrust tests failed; "
            "this tests a production-visible allocation signal without changing entries, exits, or filters."
        ),
        "known_risks": [
            "exec_lag_adj_net_rr may overlap with existing target/ATR geometry rather than add independent alpha.",
            "Top-quartile state can be sample-sensitive in thin windows.",
            "Replay-only scout must be promoted into shared policy before any positive result is tradable.",
        ],
        "decision": decision,
        "interpretation": interpretation,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, avoid simple exec_lag_adj_net_rr sizing and search for a different drawdown discriminator. "
            "If accepted, implement the state and sizing in shared production/backtest policy and rerun all three windows."
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
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "selected_multiplier": result["parameters"]["selected_multiplier"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
