"""exp-20260516-046: signal-day ATR compression risk scalar sweep.

Tests one production-visible allocation discriminator on the accepted core
stack: same-day bottom-quartile ATR expansion among non-ETF/non-commodity
stock features. This is a replay scout only; no production-default strategy
behavior changes unless a separate shared-policy promotion is made and
revalidated.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260516_022_signal_day_atr_expansion_risk as scout


EXPERIMENT_ID = "exp-20260516-046"
EXPERIMENT_SLUG = "signal_day_atr_compression_risk_scalar"
MULTIPLIER_KEY = "signal_day_atr_compression_risk_multiplier_applied"
STATE_KEY = "signal_day_atr_compression_bottom_quartile_state"
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [0.85, 0.9, 0.95, 1.0, 1.0125, 1.025, 1.05]
BOTTOM_FRACTION = 0.25
STATE_STRATEGIES = {"trend_long", "breakout_long"}
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 6
MIN_AFFECTED_WINDOW_COUNT = 2


def _atr_expansion_bottom_quartile_cutoff(
    features_dict: dict[str, dict[str, Any]],
) -> float | None:
    values: list[float] = []
    for ticker, features in (features_dict or {}).items():
        if not features:
            continue
        sector = scout.base.risk_engine.SECTOR_MAP.get(ticker, "Unknown")
        if sector in EXCLUDED_SECTORS:
            continue
        atr_expansion = features.get("atr_expansion")
        if isinstance(atr_expansion, (int, float)):
            values.append(float(atr_expansion))
    if not values:
        return None
    values.sort()
    index = min(len(values) - 1, max(0, math.ceil(len(values) * BOTTOM_FRACTION) - 1))
    return values[index]


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        cutoff = _atr_expansion_bottom_quartile_cutoff(features_dict)
        cutoff_for_log = (
            round(cutoff, 6) if isinstance(cutoff, (int, float)) else None
        )
        for sig in enriched:
            features = features_dict.get(str(sig.get("ticker") or "")) or {}
            atr_expansion = features.get("atr_expansion")
            sector = sig.get("sector")
            sig["signal_day_atr_expansion"] = atr_expansion
            sig["signal_day_atr_compression_bottom_quartile_cutoff"] = cutoff_for_log
            sig[STATE_KEY] = (
                sig.get("strategy") in STATE_STRATEGIES
                and sector not in EXCLUDED_SECTORS
                and isinstance(atr_expansion, (int, float))
                and isinstance(cutoff, (int, float))
                and float(atr_expansion) <= cutoff
            )
        return enriched

    return wrapped


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0 or math.isclose(scalar, 1.0):
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    if entry <= 0:
        return sizing
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)

    if scalar < 1.0:
        new_shares = max(1, int(math.floor(shares * scalar)))
    else:
        cap_pct = float(
            sizing.get("max_position_pct_applied")
            or scout.base.portfolio_engine.MAX_POSITION_PCT
        )
        cap_shares = max(1, int(math.floor(portfolio_value * cap_pct / entry)))
        desired_shares = max(shares, int(math.floor(shares * scalar)))
        new_shares = min(desired_shares, cap_shares)

    if new_shares == shares:
        return sizing

    out = dict(sizing)
    out["signal_day_atr_compression_baseline_shares"] = shares
    out["signal_day_atr_compression_new_shares"] = new_shares
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
                            "atr_expansion": sig.get("signal_day_atr_expansion"),
                            "atr_compression_bottom_quartile_cutoff": sig.get(
                                "signal_day_atr_compression_bottom_quartile_cutoff"
                            ),
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
            f"# {EXPERIMENT_ID} Signal-Day ATR Compression Risk Scalar",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing risk scalar for already-qualified trend/breakout stock signals whose signal-day `atr_expansion` is in the same-day non-ETF/non-commodity bottom quartile. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.",
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
            "Production impact: replay-only scout. A positive promotion must add shared `risk_engine` ATR-compression state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.",
        ]
    )


def _configure_modules() -> None:
    scout.EXPERIMENT_ID = EXPERIMENT_ID
    scout.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    scout.MULTIPLIER_KEY = MULTIPLIER_KEY
    scout.STATE_KEY = STATE_KEY
    scout.BASELINE_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
    scout.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    scout.TOP_FRACTION = BOTTOM_FRACTION
    scout.STATE_STRATEGIES = STATE_STRATEGIES
    scout.EXCLUDED_SECTORS = EXCLUDED_SECTORS
    scout.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    scout.MIN_AFFECTED_SIGNAL_COUNT = MIN_AFFECTED_SIGNAL_COUNT
    scout.MIN_AFFECTED_WINDOW_COUNT = MIN_AFFECTED_WINDOW_COUNT
    scout.CURRENT_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
    scout._make_enrich_wrapper = _make_enrich_wrapper
    scout._make_size_wrapper = _make_size_wrapper
    scout._scale_sizing = _scale_sizing
    scout._markdown = _markdown


def _rewrite_payload(payload: dict[str, Any]) -> dict[str, Any]:
    passed = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_signal_day_atr_compression_risk_scalar"
    )
    interpretation = (
        "Signal-day bottom-quartile ATR expansion cleared the canonical three-window scout as an allocation state and requires shared risk/portfolio promotion plus rerun before production use."
        if passed
        else "Signal-day bottom-quartile ATR expansion did not clear the canonical three-window gate as a standalone risk scalar."
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Recent logs show broad filters, nearby accepted scalar retunes, "
                "LLM/SEC semantic branches, and noisy candidate-pool expansion are "
                "poor next steps. A low signal-day range state may identify calmer "
                "already-qualified trend/breakout entries where sizing is too small "
                "or too large, so sweep only a cap-aware risk scalar on that fixed "
                "production-visible state."
            ),
            "change_type": "risk_allocation_shadow",
            "changed_variable": "signal_day_atr_compression_risk_multiplier",
            "single_causal_variable": (
                "post-sizing risk scalar for signal-day bottom-quartile ATR expansion "
                "trend/breakout stock signals"
            ),
            "interpretation": interpretation,
            "rejection_reason": None if passed else interpretation,
            "next_evidence_needed": (
                None
                if passed
                else "Do not retry signal-day ATR-compression scalars on these frozen windows without a materially different production-visible discriminator or forward hold-quality evidence."
            ),
            "why_not_other_changes": (
                "LLM soft-ranking and SEC semantics remain field/coverage-limited; "
                "Space/event adjacent interactions and ATR-expansion variants were "
                "recently rejected or paper-only; ticker residual scalars are now "
                "watch-only unless they cover multiple windows; broad pool expansion "
                "has added noise."
            ),
            "anti_js": "No JavaScript was used.",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "related_files": [
                "quant/experiments/exp_20260516_046_signal_day_atr_compression_risk_scalar.py",
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
                "feature": "atr_expansion",
                "cutoff": "same-day non-ETF/non-commodity bottom quartile",
                "bottom_fraction": BOTTOM_FRACTION,
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
            "risk allocation on a production-visible signal-day ATR compression "
            "state; this follows the playbook preference for fixed candidate-set "
            "allocation and avoids blocked LLM/SEC branches"
        ),
        "2_history_check": {
            "exp-20260426-045": (
                "Volatility-contraction breakout was observed as a separate shadow "
                "entry family; this keeps the candidate set fixed and tests only "
                "post-sizing on already-qualified core signals."
            ),
            "exp-20260516-022_026_027_038": (
                "Top-quartile ATR expansion haircuts/top-ups failed; this tests the "
                "opposite low-range state, not another expansion retry."
            ),
            "recent_blocked_branches": (
                "LLM/SEC semantics are still sparse, Space needs forward rows, and "
                "ticker residuals require multi-window evidence."
            ),
        },
        "3_single_causal_variable": (
            "signal_day_atr_compression_risk_multiplier with fixed bottom-quartile state"
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
            "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
            "at least six affected signals across at least two windows, and max drawdown "
            "drift <= 0.5 pp."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe "
            "quant\\experiments\\exp_20260516_046_signal_day_atr_compression_risk_scalar.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "feature_layer atr_expansion",
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
                "If accepted, add the ATR-compression state and sizing key in "
                "shared risk_engine.py/portfolio_engine.py paths used by both "
                "backtester.py and run.py, then rerun all three canonical windows."
            ),
        }
    )
    payload["known_risks"] = [
        "Bottom-quartile signal-day range can indicate constructive compression or weak participation; the sweep must decide direction.",
        "The percentile boundary is production-visible but still derived from frozen windows.",
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
