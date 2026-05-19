"""exp-20260517-011: overstacked generic boost haircut sweep.

Tests one production-visible allocation discriminator on the accepted core
stack: already-qualified stock signals that receive both generic risk-on and
SPY-relative leader boosts, but lack own-green and RS20 internal confirmation.

This is replay-only. A positive result must be promoted through shared
``risk_engine.py`` / ``portfolio_engine.py`` policy plus parity tests before
production behavior changes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260516_022_signal_day_atr_expansion_risk as scout


EXPERIMENT_ID = "exp-20260517-011"
EXPERIMENT_SLUG = "overstacked_generic_boost_haircut"
MULTIPLIER_KEY = "overstacked_generic_boost_haircut_multiplier_applied"
STATE_KEY = "overstacked_generic_boost_no_internal_confirmation_state"
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [0.25, 0.5, 0.75, 0.9, 1.0]
STATE_STRATEGIES = {"trend_long", "breakout_long"}
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 6
MIN_AFFECTED_WINDOW_COUNT = 2


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
            sector = sig.get("sector")
            own_green = sig.get("signal_day_ticker_green_candle") is True
            rs20_leader = sig.get("rs20_entry_state_leader") is True
            sig[STATE_KEY] = (
                sig.get("strategy") in STATE_STRATEGIES
                and sector not in EXCLUDED_SECTORS
                and not own_green
                and not rs20_leader
            )
        return enriched

    return wrapped


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0 or scalar >= 1.0:
        return sizing
    new_shares = max(1, int(math.floor(shares * scalar)))
    if new_shares >= shares:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["overstacked_generic_boost_baseline_shares"] = shares
    out["overstacked_generic_boost_new_shares"] = new_shares
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


def _generic_double_boost(sizing: dict[str, Any]) -> bool:
    return (
        float(sizing.get("risk_on_unmodified_risk_multiplier_applied") or 1.0) > 1.0
        and float(sizing.get("spy_relative_leader_risk_on_multiplier_applied") or 1.0)
        > 1.0
    )


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
            if (
                sig.get(STATE_KEY)
                and sizing.get("shares_to_buy")
                and _generic_double_boost(sizing)
            ):
                adjusted_sizing = _scale_sizing(
                    sizing,
                    scout.CURRENT_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted_sizing is not sizing:
                    scout.base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "scalar": scout.CURRENT_RISK_MULTIPLIER,
                            "risk_on_unmodified_risk_multiplier": sizing.get(
                                "risk_on_unmodified_risk_multiplier_applied"
                            ),
                            "spy_relative_leader_risk_on_multiplier": sizing.get(
                                "spy_relative_leader_risk_on_multiplier_applied"
                            ),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "rs60_top_quintile_state": sig.get(
                                "rs60_top_quintile_state"
                            ),
                            "core_confirmed_quality_state": sig.get(
                                "core_confirmed_quality_state"
                            ),
                            "green_decel_quality_nonconsumer_state": sig.get(
                                "green_decel_quality_nonconsumer_state"
                            ),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "signal_day_ticker_outperformed_spy": sig.get(
                                "signal_day_ticker_outperformed_spy"
                            ),
                            "ticker_minus_spy_signal_day_open_close_return_pct": sig.get(
                                "ticker_minus_spy_signal_day_open_close_return_pct"
                            ),
                            "price_vs_200ma_extension_state": sig.get(
                                "price_vs_200ma_extension_state"
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.3f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
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
            f"# {EXPERIMENT_ID} Overstacked Generic Boost Haircut",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing risk multiplier for already-qualified trend/breakout stock signals that received both generic risk-on and SPY-relative leader boosts while lacking own-green and RS20 confirmation. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.",
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
            "Production impact: replay-only scout. A positive promotion must add a shared state and sizing key in `risk_engine.py` / `portfolio_engine.py`, then rerun the canonical three-window backtest before live/default behavior changes.",
        ]
    )


def _configure_modules() -> None:
    scout.EXPERIMENT_ID = EXPERIMENT_ID
    scout.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    scout.MULTIPLIER_KEY = MULTIPLIER_KEY
    scout.STATE_KEY = STATE_KEY
    scout.BASELINE_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
    scout.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    scout.STATE_STRATEGIES = STATE_STRATEGIES
    scout.EXCLUDED_SECTORS = EXCLUDED_SECTORS
    scout.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    scout.MIN_AFFECTED_SIGNAL_COUNT = MIN_AFFECTED_SIGNAL_COUNT
    scout.MIN_AFFECTED_WINDOW_COUNT = MIN_AFFECTED_WINDOW_COUNT
    scout.CURRENT_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
    scout._make_enrich_wrapper = _make_enrich_wrapper
    scout._make_size_wrapper = _make_size_wrapper
    scout._markdown = _markdown


def _rewrite_payload(payload: dict[str, Any]) -> dict[str, Any]:
    passed = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_overstacked_generic_boost_haircut"
    )
    interpretation = (
        "The overstacked generic-boost no-confirmation state cleared Gate 4 and requires shared policy promotion plus rerun before production use."
        if passed
        else "The overstacked generic-boost no-confirmation state did not clear the canonical three-window gate."
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Recent accepted core improvements mostly allocate more capital to "
                "already-qualified signals. The residual loss cluster suggests the "
                "opposite risk: some names receive both generic risk-on and "
                "SPY-relative leader boosts without internal confirmation from an "
                "own-green signal day or RS20 leadership. A bounded haircut may "
                "reduce overstacked generic allocation while keeping the candidate "
                "set fixed."
            ),
            "change_type": "risk_allocation_shadow",
            "changed_variable": "overstacked_generic_boost_haircut_multiplier",
            "single_causal_variable": (
                "post-sizing risk multiplier for trend/breakout stock signals with "
                "risk_on_unmodified > 1, spy_relative_leader > 1, no own-green, "
                "and no RS20 entry-state leadership"
            ),
            "interpretation": interpretation,
            "rejection_reason": None if passed else interpretation,
            "next_evidence_needed": (
                None
                if passed
                else "Do not retry generic-boost haircuts without a materially different production-visible confirmation field or forward loss-cluster evidence."
            ),
            "why_not_other_changes": (
                "LLM/SEC soft-ranking remains field and coverage limited, candidate "
                "pool expansion has recently added old-window noise, event rotation "
                "should mature forward/trade-adapter evidence rather than another "
                "same-sample scalar, and nearby slot/ATR/RS/green mirror branches "
                "are logged as exhausted or rejected."
            ),
            "anti_js": "No JavaScript was used.",
            "related_files": [
                "quant/experiments/exp_20260517_011_overstacked_generic_boost_haircut.py",
                f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
                f"experiments/logs/{EXPERIMENT_ID}.json",
                f"experiments/tickets/{EXPERIMENT_ID}.json",
                f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
                "docs/experiment_log.jsonl",
            ],
        }
    )
    payload["parameters"].update(
        {
            "state_definition": {
                "strategies": sorted(STATE_STRATEGIES),
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
                "requires_risk_on_unmodified_multiplier_gt_1": True,
                "requires_spy_relative_leader_multiplier_gt_1": True,
                "requires_own_green": False,
                "requires_rs20_entry_state_leader": False,
            },
            "baseline_risk_multiplier": BASELINE_RISK_MULTIPLIER,
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "risk allocation on a production-visible overstacked generic-boost "
            "state; this fits the playbook preference for fixed-candidate allocation"
        ),
        "2_history_check": {
            "exp-20260516-047": (
                "Rejected broad non-green and SPY-underperforming mirror haircut; "
                "this is different because it targets SPY-relative leaders that "
                "were boosted by the existing generic risk-on stack but lack "
                "own-green/RS20 internal confirmation."
            ),
            "exp-20260517-005_006_008_009": (
                "Adjacent slot top-ups were exhausted except the accepted stock-only "
                "ample-slot rank-1 rule; this run does not touch slot routing."
            ),
            "exp-20260517-010": (
                "Event rotation remains the strongest paper lane, but playbook says "
                "its next step is forward/trade-adapter maturation rather than "
                "another same-sample notional sweep."
            ),
        },
        "3_single_causal_variable": (
            "overstacked_generic_boost_haircut_multiplier with fixed state definition"
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
            "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
            "at least six affected signals across at least two windows, and max drawdown "
            "drift <= 0.5 pp."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe "
            "quant\\experiments\\exp_20260517_011_overstacked_generic_boost_haircut.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "risk_engine signal_day_ticker_green_candle",
        "risk_engine rs20_entry_state_leader",
        "risk_engine sector",
        "risk_engine strategy",
        "portfolio_engine risk_on_unmodified_risk_multiplier_applied",
        "portfolio_engine spy_relative_leader_risk_on_multiplier_applied",
        "portfolio_engine shares_to_buy",
    ]
    payload["llm_metrics"] = {
        "used_llm": False,
        "blocker_relation": (
            "LLM soft-ranking and SEC semantic fields remain sparse for current "
            "three-window alpha judgment; this deterministic allocation state "
            "does not depend on them."
        ),
    }
    payload["production_impact"].update(
        {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add the state and sizing key in shared "
                "risk_engine.py/portfolio_engine.py paths used by both "
                "backtester.py and run.py, then rerun all three canonical windows."
            ),
        }
    )
    payload["known_risks"] = [
        "Some SPY-relative leaders can recover without own-green or RS20 confirmation.",
        "The state intentionally touches generic allocation stack interactions, so attribution must stay narrow.",
        "A positive replay scout is not production-tradable until shared policy is promoted and rerun.",
    ]
    return payload


def main() -> dict[str, Any]:
    _configure_modules()
    result = scout.run()
    result = _rewrite_payload(result)
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
                "selected_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
