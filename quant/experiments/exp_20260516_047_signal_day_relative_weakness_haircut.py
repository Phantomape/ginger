"""exp-20260516-047: signal-day relative weakness haircut sweep.

Tests one production-visible allocation discriminator on the accepted core
stack: already-qualified trend/breakout stock signals whose signal day is both
not green and not outperforming SPY. This is a replay scout only; no
production-default strategy behavior changes unless a separate shared-policy
promotion is made and revalidated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260516_022_signal_day_atr_expansion_risk as scout


EXPERIMENT_ID = "exp-20260516-047"
EXPERIMENT_SLUG = "signal_day_relative_weakness_haircut"
MULTIPLIER_KEY = "signal_day_relative_weakness_risk_multiplier_applied"
STATE_KEY = "signal_day_relative_weakness_state"
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [0.5, 0.65, 0.75, 0.85, 0.9, 0.95, 1.0]
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
            outperformed_spy = sig.get("signal_day_ticker_outperformed_spy") is True
            sig[STATE_KEY] = (
                sig.get("strategy") in STATE_STRATEGIES
                and sector not in EXCLUDED_SECTORS
                and not own_green
                and not outperformed_spy
            )
        return enriched

    return wrapped


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
            if sig.get(STATE_KEY) and sizing.get("shares_to_buy"):
                adjusted_sizing = scout._scale_sizing(
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
                            "ticker_minus_spy_signal_day_open_close_return_pct": sig.get(
                                "ticker_minus_spy_signal_day_open_close_return_pct"
                            ),
                            "price_vs_200ma_extension_state": sig.get(
                                "price_vs_200ma_extension_state"
                            ),
                        }
                    )
                    adjusted_sizing[MULTIPLIER_KEY] = scout.CURRENT_RISK_MULTIPLIER
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
            f"# {EXPERIMENT_ID} Signal-Day Relative Weakness Haircut",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing risk multiplier for already-qualified trend/breakout stock signals whose signal day is both not an own green candle and not SPY-outperformance. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.",
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
            "Production impact: replay-only scout. A positive promotion must add a shared `risk_engine` relative-weakness state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.",
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
        else "rejected_signal_day_relative_weakness_haircut"
    )
    interpretation = (
        "Signal-day relative weakness cleared the canonical three-window scout as a risk haircut and requires shared risk/portfolio promotion plus rerun before production use."
        if passed
        else "Signal-day relative weakness did not clear the canonical three-window gate as a standalone risk haircut."
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "The accepted core stack rewards own-green and SPY-relative "
                "leadership, but the mirror state has not been isolated on the "
                "current stack. Already-qualified trend/breakout stock signals "
                "that are neither green nor stronger than SPY on the signal day "
                "may deserve less risk without changing the candidate set."
            ),
            "change_type": "risk_allocation_shadow",
            "changed_variable": "signal_day_relative_weakness_risk_multiplier",
            "single_causal_variable": (
                "post-sizing risk multiplier for non-green and SPY-underperforming "
                "trend/breakout stock signals"
            ),
            "interpretation": interpretation,
            "rejection_reason": None if passed else interpretation,
            "next_evidence_needed": (
                None
                if passed
                else "Do not retry broad signal-day relative-weakness haircuts on these frozen windows without a materially richer discriminator such as event quality, sector-relative context, or forward hold-quality evidence."
            ),
            "why_not_other_changes": (
                "LLM soft-ranking and SEC semantics remain field/coverage-limited; "
                "candidate-pool expansion has recently added old-window noise; "
                "nearby ATR-expansion/compression states failed sample or EV gates. "
                "This tests one production-visible mirror of accepted green/SPY "
                "leadership sizing, with the candidate set fixed."
            ),
            "anti_js": "No JavaScript was used.",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "related_files": [
                "quant/experiments/exp_20260516_047_signal_day_relative_weakness_haircut.py",
                f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
                f"docs/experiments/logs/{EXPERIMENT_ID}.json",
                f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
                f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
                "docs/experiment_log.jsonl",
            ],
        }
    )
    payload["parameters"].update(
        {
            "state_definition": {
                "own_green_required": False,
                "spy_outperformance_required": False,
                "strategies": sorted(STATE_STRATEGIES),
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
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
            "risk allocation on production-visible signal-day relative weakness; "
            "this follows the playbook preference for fixed-candidate allocation"
        ),
        "2_history_check": {
            "accepted_green_spy_leadership": (
                "Own-green and SPY-relative leadership top-ups are accepted on "
                "the current shared stack; this tests the opposite weak signal-day "
                "state as a haircut, not another top-up retune."
            ),
            "exp-20260512-106_107": (
                "Sector-proxy same-day tape scalars failed or were underpowered; "
                "this uses own candle plus SPY-relative weakness, not sector tape."
            ),
            "exp-20260515-049": (
                "Gap absorption / close-location failed; this uses existing "
                "production signal-day relative fields only."
            ),
            "exp-20260516-046": (
                "ATR-compression was sample-limited; this avoids that sparse state."
            ),
        },
        "3_single_causal_variable": (
            "signal_day_relative_weakness_risk_multiplier with fixed weak-state definition"
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
            "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
            "at least six affected signals across at least two windows, and max drawdown "
            "drift <= 0.5 pp."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe "
            "quant\\experiments\\exp_20260516_047_signal_day_relative_weakness_haircut.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "risk_engine signal_day_ticker_green_candle",
        "risk_engine signal_day_ticker_outperformed_spy",
        "risk_engine ticker_minus_spy_signal_day_open_close_return_pct",
        "risk_engine sector",
        "risk_engine strategy",
        "portfolio_engine shares_to_buy",
    ]
    payload["production_impact"].update(
        {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add the relative-weakness state and sizing key in "
                "shared risk_engine.py/portfolio_engine.py paths used by both "
                "backtester.py and run.py, then rerun all three canonical windows."
            ),
        }
    )
    payload["known_risks"] = [
        "A stock can be red and SPY-underperforming during a healthy pullback before continuation.",
        "This broad mirror state may overlap with already-haircut weak sectors or tickers.",
        "A positive replay scout is not production-tradable until shared risk and sizing code are promoted and rerun.",
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
                "selected_multiplier": result["parameters"]["selected_risk_multiplier"],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
