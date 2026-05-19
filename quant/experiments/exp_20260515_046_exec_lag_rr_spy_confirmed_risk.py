"""exp-20260515-046: SPY-confirmed exec-lag R:R leadership risk scout.

This keeps the accepted production stack unchanged and tests one allocation
variable: whether already-qualified core stock signals with both high
execution-lag-adjusted R:R and signal-day SPY outperformance deserve a small
cap-aware risk top-up.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260513_031_signal_day_range_compression_risk as sweep
import portfolio_engine


EXPERIMENT_ID = "exp-20260515-046"
EXPERIMENT_SLUG = "exec_lag_rr_spy_confirmed_risk"
MULTIPLIER_KEY = "exec_lag_rr_spy_confirmed_risk_multiplier_applied"

RR_TOP_FRACTION = 0.25
EXCLUDED_SECTORS = {"ETF", "Commodities"}
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _is_finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _is_rr_candidate(signal: dict[str, Any]) -> bool:
    return (
        signal.get("strategy") in {"trend_long", "breakout_long"}
        and signal.get("sector") not in EXCLUDED_SECTORS
        and _is_finite(signal.get("exec_lag_adj_net_rr"))
    )


def _top_fraction_cutoff(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(0, math.ceil(len(sorted_values) * (1.0 - fraction)) - 1)
    return sorted_values[index]


def _make_compute_features_wrapper(
    original_compute_features: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    return original_compute_features


def _make_enrich_wrapper(
    original_enrich_signals: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapper(
        signals: list[dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        enriched = original_enrich_signals(signals, *args, **kwargs)
        rr_values = [
            float(sig["exec_lag_adj_net_rr"])
            for sig in enriched
            if _is_rr_candidate(sig)
        ]
        cutoff = _top_fraction_cutoff(rr_values, RR_TOP_FRACTION)

        for sig in enriched:
            rr_value = sig.get("exec_lag_adj_net_rr")
            state = bool(
                cutoff is not None
                and _is_rr_candidate(sig)
                and float(rr_value) >= cutoff
                and sig.get("signal_day_ticker_outperformed_spy") is True
            )
            sig["exec_lag_rr_spy_confirmed_cutoff"] = cutoff
            sig["exec_lag_rr_spy_confirmed_state"] = state
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

    cap_pct = float(
        sizing.get("max_position_pct_applied") or portfolio_engine.MAX_POSITION_PCT
    )
    cap_shares = int(math.floor(portfolio_value * cap_pct / float(entry_price)))
    desired_shares = max(shares, int(math.floor(shares * multiplier)))
    new_shares = min(desired_shares, cap_shares)

    if new_shares <= shares:
        return sizing

    risk_amount = new_shares * float(net_risk_per_share)
    position_value = new_shares * float(entry_price)
    out = dict(sizing)
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(position_value, 2)
    out["position_pct_of_portfolio"] = (
        round(position_value / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(risk_amount, 2)
    out["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    out["exec_lag_rr_spy_confirmed_baseline_shares"] = shares
    out["exec_lag_rr_spy_confirmed_desired_shares"] = desired_shares
    out["exec_lag_rr_spy_confirmed_cap_shares"] = cap_shares
    out["exec_lag_rr_spy_confirmed_new_shares"] = new_shares
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
            if not sig.get("exec_lag_rr_spy_confirmed_state"):
                adjusted.append(sig)
                continue

            new_sizing = _scale_sizing(
                sizing,
                sweep.CURRENT_RISK_MULTIPLIER,
                portfolio_value,
            )
            if new_sizing is not sizing:
                base.ADJUSTMENTS.append(
                    {
                        "ticker": sig.get("ticker"),
                        "strategy": sig.get("strategy"),
                        "sector": sig.get("sector"),
                        "exec_lag_adj_net_rr": sig.get("exec_lag_adj_net_rr"),
                        "exec_lag_rr_spy_confirmed_cutoff": sig.get(
                            "exec_lag_rr_spy_confirmed_cutoff"
                        ),
                        "ticker_minus_spy_signal_day_open_close_return_pct": sig.get(
                            "ticker_minus_spy_signal_day_open_close_return_pct"
                        ),
                        "signal_day_ticker_outperformed_spy": sig.get(
                            "signal_day_ticker_outperformed_spy"
                        ),
                        "baseline_shares": sizing.get("shares_to_buy"),
                        "new_shares": new_sizing.get("shares_to_buy"),
                        "baseline_position_value": sizing.get("position_value_usd"),
                        "new_position_value": new_sizing.get("position_value_usd"),
                        "cap_shares": new_sizing.get(
                            "exec_lag_rr_spy_confirmed_cap_shares"
                        ),
                        "core_confirmed_quality_state": sig.get(
                            "core_confirmed_quality_state"
                        ),
                        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
                        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
                        "price_vs_200ma_extension_state": sig.get(
                            "price_vs_200ma_extension_state"
                        ),
                        "trade_quality_score": sig.get("trade_quality_score"),
                        "regime_exit_bucket": sig.get("regime_exit_bucket"),
                    }
                )
                sig = {**sig, "sizing": new_sizing}
            adjusted.append(sig)
        return adjusted

    return wrapper


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sweep._sweep_summary(candidates)


def _markdown(payload: dict[str, Any]) -> str:
    selected = payload["selected_candidate"]
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
        before = selected["before"][label]
        after = selected["after"][label]
        delta = selected["delta"][label]
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
            f"# {EXPERIMENT_ID} {EXPERIMENT_SLUG}",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing top-up for `trend_long` / `breakout_long` non-ETF/non-commodity stock signals in the same-day top quartile of `exec_lag_adj_net_rr` that also outperformed SPY open-to-close on the signal day. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected multiplier: `{payload['parameters']['selected_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. A positive promotion must move the state and sizing helper into shared `risk_engine.py` / `portfolio_engine.py`, add attribution keys, update parity docs, and add focused tests before production behavior changes.",
        ]
    )


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
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: base._run_window(label, variant=False)
        for label in base.WINDOWS
    }
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

    if selected["passed"]:
        decision = "accepted_for_shared_policy_implementation"
        rejection_reason = None
        interpretation = (
            "SPY-confirmed high exec-lag-adjusted R:R leadership cleared the "
            "canonical three-window scout and needs shared policy promotion "
            "before any production-visible use."
        )
    else:
        decision = "rejected_exec_lag_rr_spy_confirmed_risk"
        rejection_reason = (
            selected.get("rejection_reason") or "failed_three_window_gate4"
        )
        interpretation = (
            "Adding signal-day SPY confirmation to high exec-lag-adjusted R:R "
            "did not clear the canonical three-window gate; do not promote this "
            "allocation state on the frozen windows."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The simple exec_lag_adj_net_rr top-quartile top-up was old-window "
            "fragile. Requiring same-day SPY-relative confirmation may isolate "
            "the high-payoff subset where asymmetric target geometry is backed "
            "by observable market-relative demand."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "exec_lag_rr_spy_confirmed_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk top-up for trend/breakout stock signals "
            "that are both top-quartile exec_lag_adj_net_rr and signal-day "
            "SPY-relative outperformers"
        ),
        "parameters": {
            "rr_top_fraction": RR_TOP_FRACTION,
            "excluded_sectors": sorted(EXCLUDED_SECTORS),
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
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "core risk allocation using high execution-lag-adjusted R:R "
                "plus production-visible signal-day SPY confirmation"
            ),
            "2_history_check": {
                "exp-20260515-038": (
                    "simple exec_lag_adj_net_rr top-quartile top-up was "
                    "directionally positive but failed because old_thin regressed"
                ),
                "exp-20260515-041": (
                    "excluding pre-haircut signals still regressed old_thin"
                ),
                "clean_spy_prior": (
                    "clean-SPY states are already accepted; this is not a nearby "
                    "cap/scalar retry because it tests R:R leadership as the "
                    "additional drawdown discriminator"
                ),
                "llm_soft_ranking": (
                    "candidate-level LLM ranking/options fields remain sample-limited, "
                    "so this run avoids LLM changes"
                ),
            },
            "3_single_causal_variable": (
                "exec_lag_rr_spy_confirmed_risk_multiplier with a fixed state definition"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, no EV-regressed windows, "
                "survival >= 5%, nonzero adjusted signals, and max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_046_exec_lag_rr_spy_confirmed_risk.py"
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
                "risk_engine signal_day_ticker_outperformed_spy",
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
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "selected_candidate": selected_candidate,
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "sweep_summary": _sweep_summary(candidates),
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "why_not_other_changes": (
            "LLM/options soft-ranking remains closed-outcome limited; recent "
            "sector-thrust, close-location, R:R-only, reversal, and candidate-pool "
            "experiments failed or were sample-thin. This tests one deterministic "
            "production-visible allocation state instead."
        ),
        "known_risks": [
            "The state may overlap with accepted clean-SPY and RS20 sizing helpers.",
            "Top-quartile R:R can still select old-window losers if relative confirmation is not strong enough.",
            "A positive result is not tradable until implemented through shared production/backtest policy.",
        ],
        "interpretation": interpretation,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, avoid further simple R:R sizing unless a genuinely new "
            "catalyst-quality or drawdown discriminator is available. If accepted, "
            "promote through shared risk/sizing policy and rerun all three windows."
        ),
        "related_files": [
            "quant/experiments/exp_20260515_046_exec_lag_rr_spy_confirmed_risk.py",
            "data/experiments/exp-20260515-046/exec_lag_rr_spy_confirmed_risk.json",
            "experiments/logs/exp-20260515-046.json",
            "experiments/tickets/exp-20260515-046.json",
            "experiments/artifacts/exp-20260515-046_exec_lag_rr_spy_confirmed_risk.md",
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
                "selected_multiplier": result["parameters"]["selected_multiplier"],
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
