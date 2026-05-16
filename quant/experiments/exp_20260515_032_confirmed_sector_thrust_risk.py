"""exp-20260515-032: confirmed sector-thrust core allocation scout.

This tests one interaction state on the accepted core stack:
already-qualified core confirmed-quality signals that also sit in the
signal-day top quartile for ticker-minus-sector-proxy thrust.

It keeps entries, exits, ranking, universe, filters, targets, heat, slots,
LLM/news behavior, and existing sizing rules fixed.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260515_030_current_stack_sector_relative_thrust_risk as prior


EXPERIMENT_ID = "exp-20260515-032"
EXPERIMENT_SLUG = "confirmed_sector_thrust_risk"
MULTIPLIER_KEY = "confirmed_sector_thrust_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            eligible = (
                sig.get("core_confirmed_quality_state") is True
                and sig.get("signal_day_sector_relative_thrust_state") is True
                and sizing.get("shares_to_buy")
            )
            if eligible:
                adjusted_sizing = prior._scale_sizing(
                    sizing,
                    prior.sweep.CURRENT_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted_sizing is not sizing:
                    prior.base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "sector_proxy": sig.get("signal_day_sector_proxy"),
                            "ticker_open_close_return_pct": sig.get(
                                "signal_day_ticker_open_close_return_pct_shadow"
                            ),
                            "sector_proxy_open_close_return_pct": sig.get(
                                "signal_day_sector_proxy_open_close_return_pct"
                            ),
                            "ticker_minus_sector_proxy_pct": sig.get(
                                "signal_day_ticker_minus_sector_proxy_pct"
                            ),
                            "thrust_cutoff": sig.get(
                                "signal_day_sector_relative_thrust_cutoff"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "rs60_top_quintile_state": sig.get(
                                "rs60_top_quintile_state"
                            ),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "signal_day_ticker_outperformed_spy": sig.get(
                                "signal_day_ticker_outperformed_spy"
                            ),
                            "core_confirmed_quality_state": sig.get(
                                "core_confirmed_quality_state"
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _risk_distribution(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {
            "worst_trade_pct": row.get("worst_trade_pct"),
            "max_consecutive_losses": row.get("max_consecutive_losses"),
            "tail_loss_share": row.get("tail_loss_share"),
        }
        for label, row in metrics.items()
    }


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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.base.WINDOWS:
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
            f"# {EXPERIMENT_ID} Confirmed Sector-Thrust Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` non-ETF/non-commodity stock signals that satisfy both `core_confirmed_quality_state=true` and same-day top-quartile ticker-minus-sector-proxy thrust. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.",
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
            "Production impact: replay-only scout. A positive promotion would require shared feature/risk/sizing implementation, attribution keys, and parity tests before production behavior changes.",
        ]
    )


def _configure_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.MULTIPLIER_KEY = MULTIPLIER_KEY
    prior.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    prior.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    prior.sweep.EXPERIMENT_ID = EXPERIMENT_ID
    prior.sweep.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.sweep.MULTIPLIER_KEY = MULTIPLIER_KEY
    prior.sweep.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    prior.sweep.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    prior._make_size_wrapper = _make_size_wrapper
    prior._markdown = _markdown


def run() -> dict[str, Any]:
    _configure_prior()
    payload = prior.run()
    passed = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_confirmed_sector_thrust_risk"
    )
    interpretation = (
        "Confirmed sector-thrust cleared the canonical three-window gate; promote only through shared production/backtest policy."
        if passed
        else "Confirmed sector-thrust did not clear the canonical three-window gate; do not promote this interaction state on the frozen windows."
    )

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Top-quartile signal-day ticker-vs-sector thrust alone was directionally useful but old-window fragile. "
                "Restricting it to the accepted core confirmed-quality state may isolate true idiosyncratic leadership without expanding the candidate set."
            ),
            "change_type": "risk_allocation_shadow",
            "changed_variable": "confirmed_sector_thrust_risk_multiplier",
            "single_causal_variable": (
                "cap-aware post-sizing risk top-up for core confirmed-quality signals whose signal-day ticker-minus-sector-proxy return is in the same-day top quartile"
            ),
            "parameters": {
                "state_definition": {
                    "strategies": ["trend_long", "breakout_long"],
                    "excluded_sectors": sorted(prior.EXCLUDED_SECTORS),
                    "sector_proxy": prior.base.SECTOR_PROXY,
                    "ticker_minus_sector_proxy": (
                        "top 25% of feature-complete non-ETF/non-commodity stocks on the signal day"
                    ),
                    "requires_positive_excess": True,
                    "requires_core_confirmed_quality_state": True,
                    "core_confirmed_quality_state": (
                        "trade_quality_score >= 0.95, rs20_entry_state_leader=true, signal_day_ticker_green_candle=true"
                    ),
                },
                "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
                "selected_risk_multiplier": payload["parameters"][
                    "selected_risk_multiplier"
                ],
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
                "similar_prior_results": {
                    "exp-20260515-030": (
                        "Rejected top-quartile sector-relative thrust by itself: aggregate EV +0.0104 at 1.025x, but old_thin regressed."
                    ),
                    "exp-20260515-028": (
                        "Accepted core confirmed-quality at 1.075x; nearby larger scalars failed drawdown, so this run tests a new interaction state and starts at 1.0125x."
                    ),
                    "exp-20260513-018": (
                        "Earlier confirmed-quality stack was rejected until the current stack made 1.075x viable; this run does not retry a broad confirmed-quality scalar."
                    ),
                    "exp-20260512-106/107": (
                        "Sector-tape positive/adverse variants failed or were underpowered; this requires ticker-specific thrust versus sector proxy."
                    ),
                },
                "why_this_branch": (
                    "The playbook prioritizes fixed-candidate allocation states and says nearby cap/scalar, Space expansion, and LLM soft-ranking are low-quality next steps. "
                    "This adds one production-visible interaction state using already logged fields."
                ),
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "core risk allocation: confirmed-quality signals with top-quartile ticker-vs-sector thrust may deserve a small extra allocation."
                ),
                "2_history_check": (
                    "Similar ingredients exist but this exact interaction was not found: exp030 sector thrust failed old_thin; exp028 confirmed quality is accepted but larger nearby scalars failed drawdown."
                ),
                "3_single_causal_variable": (
                    "confirmed_sector_thrust_risk_multiplier with fixed state definition"
                ),
                "4_acceptance_standard": (
                    "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 pp, nonzero adjustments."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_032_confirmed_sector_thrust_risk.py"
                ),
            },
            "gate2": {
                "open_positions": payload["gate2"]["open_positions"],
                "runtime_fields": [
                    "operator_inputs/open_positions.json entry_date",
                    "operator_inputs/open_positions.json target_price",
                    "risk_engine core_confirmed_quality_state",
                    "risk_engine rs20_entry_state_leader",
                    "risk_engine signal_day_ticker_green_candle",
                    "feature_layer signal_day_open_close_return_pct",
                    "risk_engine sector",
                    "risk_engine signal_day_ticker_minus_sector_proxy_pct",
                    "portfolio_engine max_position_pct_applied",
                ],
                "passed": payload["gate2"]["passed"],
            },
            "risk_distribution": {
                "before": _risk_distribution(payload["before_metrics"]),
                "after": _risk_distribution(payload["after_metrics"]),
            },
            "llm_metrics": {"used_llm": False},
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "promotion_requirement_if_accepted": (
                    "Implement confirmed sector-thrust fields and sizing top-up in shared feature/risk/portfolio modules called by both run.py and backtester.py; add attribution keys and focused parity tests before live/default behavior changes."
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
                "Use forward confirmed sector-thrust attribution or a different production-visible state before retrying this interaction."
            ),
            "related_files": [
                "quant/experiments/exp_20260515_032_confirmed_sector_thrust_risk.py",
                f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
                f"docs/experiments/logs/{EXPERIMENT_ID}.json",
                f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
                f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
                "docs/experiment_log.jsonl",
            ],
            "why_not_other_changes": (
                "LLM soft-ranking remains attribution-limited, Space mature-satcom expansion just failed, and nearby clean-SPY/price-extension/confirmed-quality scalars are exhausted. "
                "This run keeps the core candidate set fixed and tests one new production-visible allocation interaction."
            ),
        }
    )
    payload["artifact_markdown"] = _markdown(payload)
    return payload


if __name__ == "__main__":
    result = run()
    prior.base.persist(result)
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
                "sweep_summary": result["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
