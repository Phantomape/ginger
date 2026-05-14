"""exp-20260513-107: signal-day sector-relative strength core risk allocation.

Tests one production-visible state variable on the accepted core stack:
already-qualified trend/breakout stock signals whose signal-day open-to-close
return beats their mapped sector proxy open-to-close return.

This is a cap-aware post-sizing risk top-up scout, not an entry filter,
ranking change, exit change, universe change, LLM/news change, or production
default change.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260513_031_signal_day_range_compression_risk as sweep


EXPERIMENT_ID = "exp-20260513-107"
EXPERIMENT_SLUG = "signal_day_sector_relative_strength_risk"
MULTIPLIER_KEY = "signal_day_sector_relative_strength_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.025, 1.05, 1.075, 1.10, 1.15]
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _make_compute_features_wrapper(
    original: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    def wrapped(
        ticker: str,
        ohlcv_data: Any,
        earnings_data: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        features = original(ticker, ohlcv_data, earnings_data)
        if features is None:
            return None
        features = dict(features)
        features["signal_day_open_close_return_pct"] = base._signal_day_open_close_return(
            ohlcv_data
        )
        return features

    return wrapped


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
            sector = str(sig.get("sector") or "")
            proxy = base.SECTOR_PROXY.get(sector)
            own_ret = (features_dict.get(ticker) or {}).get(
                "signal_day_open_close_return_pct"
            )
            proxy_ret = (
                (features_dict.get(proxy) or {}).get("signal_day_open_close_return_pct")
                if proxy
                else None
            )
            excess = None
            if isinstance(own_ret, (int, float)) and isinstance(proxy_ret, (int, float)):
                excess = round(float(own_ret) - float(proxy_ret), 6)
            eligible = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sector not in EXCLUDED_SECTORS
                and isinstance(excess, (int, float))
                and excess > 0.0
            )
            sig["signal_day_sector_proxy"] = proxy
            sig["signal_day_sector_proxy_open_close_return_pct"] = proxy_ret
            sig["signal_day_ticker_open_close_return_pct_shadow"] = own_ret
            sig["signal_day_ticker_minus_sector_proxy_pct"] = excess
            sig["signal_day_sector_relative_strength_state"] = bool(eligible)
        return enriched

    return wrapped


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    if entry <= 0:
        return sizing
    max_position_pct = float(sizing.get("max_position_pct_applied") or 0.40)
    cap_shares = max(1, int(math.floor(portfolio_value * max_position_pct / entry)))
    desired_shares = max(shares, int(math.floor(shares * scalar)))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= shares:
        return sizing

    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["signal_day_sector_relative_strength_baseline_shares"] = shares
    out["signal_day_sector_relative_strength_desired_shares"] = desired_shares
    out["signal_day_sector_relative_strength_cap_shares"] = cap_shares
    out["signal_day_sector_relative_strength_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (
        (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
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
            if sig.get("signal_day_sector_relative_strength_state") and sizing.get(
                "shares_to_buy"
            ):
                adjusted_sizing = _scale_sizing(
                    sizing,
                    sweep.CURRENT_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted_sizing is not sizing:
                    base.ADJUSTMENTS.append(
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
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "rs60_top_quintile_state": sig.get(
                                "rs60_top_quintile_state"
                            ),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "signal_day_ticker_outperformed_spy": sig.get(
                                "signal_day_ticker_outperformed_spy"
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _wire_shadow_policy() -> None:
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


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sweep._sweep_summary(candidates)


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.3f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
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
    for label in base.WINDOWS:
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
            f"# {EXPERIMENT_ID} Signal-Day Sector-Relative Strength Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` stock signals whose signal-day open-to-close return beats the mapped sector proxy open-to-close return. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.",
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
            "Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.",
        ]
    )


def run() -> dict[str, Any]:
    _wire_shadow_policy()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: base._run_window(label, variant=False) for label in base.WINDOWS}
    candidates = [
        sweep._candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = sweep._select_candidate(candidates)
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_signal_day_sector_relative_strength_risk"
    )
    interpretation = (
        "Signal-day sector-relative strength cleared the canonical three-window gate and should be promoted only through shared production/backtest policy."
        if passed
        else "Signal-day sector-relative strength did not clear the canonical three-window gate; do not promote this state variable on the frozen windows."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Already-qualified trend/breakout stock signals may have better follow-through when their signal-day move is idiosyncratically stronger than their mapped sector proxy, so they may deserve a small cap-aware risk top-up."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "signal_day_sector_relative_strength_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk top-up for trend/breakout stock signals whose signal-day return beats their mapped sector proxy"
        ),
        "parameters": {
            "state_definition": {
                "strategies": ["trend_long", "breakout_long"],
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
                "sector_proxy": base.SECTOR_PROXY,
                "ticker_minus_sector_proxy_required": "> 0",
            },
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "portfolio heat",
                "LLM/news replay",
                "pilot/event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "core risk allocation using production-visible signal-day ticker-vs-sector relative strength"
            ),
            "2_history_check": {
                "exp-20260512-106": (
                    "fixed adverse sector-tape haircut was rejected; this tests ticker outperformance versus its proxy, not a negative proxy threshold."
                ),
                "exp-20260512-107": (
                    "fixed positive sector-tape top-up helped only old_thin; this tests idiosyncratic ticker-vs-sector strength instead of proxy return alone."
                ),
                "exp-20260513-105": (
                    "sector leadership top-up was rejected; this tests candidate-level excess over its sector proxy, not top-ranked proxy leadership."
                ),
                "recent_rs20_rs60_own_green": (
                    "nearby ticker-RS and candle-color overlays are accepted/exhausted; this uses sector-relative signal-day excess."
                ),
                "llm_soft_ranking": (
                    "candidate-level LLM ranking data remains thin, so this run avoids LLM changes."
                ),
            },
            "3_single_causal_variable": (
                "signal_day_sector_relative_strength_risk_multiplier with fixed ticker-minus-sector-proxy > 0 state definition"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_107_signal_day_sector_relative_strength_risk.py"
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
                "feature_layer signal_day_open_close_return_pct",
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
        "llm_metrics": {"used_llm": False},
        "production_impact": {
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
            "Use forward ticker-vs-sector hold-quality attribution or a different production-visible state before retrying sector-relative signal-day overlays."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_107_signal_day_sector_relative_strength_risk.py",
            "data/experiments/exp-20260513-107/signal_day_sector_relative_strength_risk.json",
            "docs/experiments/logs/exp-20260513-107.json",
            "docs/experiments/tickets/exp-20260513-107.json",
            "docs/experiments/artifacts/exp-20260513-107_signal_day_sector_relative_strength_risk.md",
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
