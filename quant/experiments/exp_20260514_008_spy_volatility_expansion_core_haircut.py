"""exp-20260514-008: SPY volatility-expansion core risk haircut.

Tests one volatility-state allocation variable after exp-20260514-006 rejected
the mirror top-up.  The state is production-visible from the same OHLCV replay:
SPY 20-trading-day realized volatility is above SPY 60-trading-day realized
volatility on the signal day.  The experiment only applies a post-sizing
haircut to already-qualified non-ETF/non-commodity trend/breakout stock signals.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260514_006_spy_volatility_contraction_core_risk as scaffold


EXPERIMENT_ID = "exp-20260514-008"
EXPERIMENT_SLUG = "spy_volatility_expansion_core_haircut"
MULTIPLIER_KEY = "spy_volatility_expansion_core_haircut_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [0.50, 0.75, 0.90]
EXCLUDED_SECTORS = {"ETF", "Commodities"}
SHORT_VOL_WINDOW = 20
LONG_VOL_WINDOW = 60
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
        if ticker == "SPY":
            features["spy_realized_vol_20d"] = scaffold._realized_volatility(
                ohlcv_data,
                SHORT_VOL_WINDOW,
            )
            features["spy_realized_vol_60d"] = scaffold._realized_volatility(
                ohlcv_data,
                LONG_VOL_WINDOW,
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
        spy_features = features_dict.get("SPY") or {}
        spy_vol20 = scaffold._as_float(spy_features.get("spy_realized_vol_20d"))
        spy_vol60 = scaffold._as_float(spy_features.get("spy_realized_vol_60d"))
        expansion = (
            spy_vol20 is not None
            and spy_vol60 is not None
            and spy_vol20 > spy_vol60
        )
        for sig in enriched:
            sector = str(sig.get("sector") or "")
            eligible = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sector not in EXCLUDED_SECTORS
                and expansion
            )
            sig["spy_realized_vol_20d"] = spy_vol20
            sig["spy_realized_vol_60d"] = spy_vol60
            sig["spy_volatility_expansion_state"] = bool(expansion)
            sig["spy_volatility_expansion_core_state"] = bool(eligible)
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
    new_shares = max(1, int(math.floor(shares * scalar)))
    if new_shares >= shares:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    if entry <= 0:
        return sizing
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["spy_volatility_expansion_baseline_shares"] = shares
    out["spy_volatility_expansion_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
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
            if (
                sig.get("spy_volatility_expansion_core_state")
                and sizing.get("shares_to_buy")
            ):
                adjusted_sizing = _scale_sizing(
                    sizing,
                    scaffold.CURRENT_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted_sizing is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "spy_realized_vol_20d": sig.get("spy_realized_vol_20d"),
                            "spy_realized_vol_60d": sig.get("spy_realized_vol_60d"),
                            "scalar": scaffold.CURRENT_RISK_MULTIPLIER,
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
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _wire_shadow_policy() -> None:
    scaffold.EXPERIMENT_ID = EXPERIMENT_ID
    scaffold.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    scaffold.MULTIPLIER_KEY = MULTIPLIER_KEY
    scaffold.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    scaffold.EXCLUDED_SECTORS = EXCLUDED_SECTORS
    scaffold.SHORT_VOL_WINDOW = SHORT_VOL_WINDOW
    scaffold.LONG_VOL_WINDOW = LONG_VOL_WINDOW
    scaffold.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = _make_compute_features_wrapper
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown


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
            f"# {EXPERIMENT_ID} SPY Volatility-Expansion Core Haircut",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing risk haircut for already-qualified `trend_long` and `breakout_long` non-ETF/non-commodity stock signals when SPY 20d realized volatility is above SPY 60d realized volatility. No entry filter, ranking, exit, target, universe, LLM, news, or portfolio heat behavior changed.",
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
            "Production impact: replay-only scout unless Gate 4 passes and the same state is promoted into shared `feature_layer.py`, `risk_engine.py`, and `portfolio_engine.py` code with parity tests.",
        ]
    )


def run() -> dict[str, Any]:
    _wire_shadow_policy()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: base._run_window(label, variant=False)
        for label in base.WINDOWS
    }
    candidates = [
        scaffold._candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected_summary = scaffold._select_candidate(candidates)
    selected = scaffold._candidate_payload(
        selected_summary["risk_multiplier"],
        before_runs,
        include_details=True,
    )
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_spy_volatility_expansion_core_haircut"
    )
    interpretation = (
        "SPY volatility expansion haircut cleared the canonical three-window gate and should be promoted only through shared production/backtest policy."
        if passed
        else "SPY 20d-above-60d volatility expansion did not clear Gate 4 as a standalone core sizing haircut."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "From the playbook volatility-state allocation backlog and the failed exp-20260514-006 contraction top-up: already-qualified trend/breakout stock signals may deserve less risk when SPY realized volatility is expanding, because follow-through quality can degrade during rising tape instability."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "spy_volatility_expansion_core_haircut_multiplier",
        "single_causal_variable": (
            "post-sizing risk haircut for non-ETF/non-commodity trend/breakout stock signals when SPY 20d realized volatility is above SPY 60d realized volatility"
        ),
        "parameters": {
            "state_definition": {
                "spy_realized_vol_short_window": SHORT_VOL_WINDOW,
                "spy_realized_vol_long_window": LONG_VOL_WINDOW,
                "condition": "spy_realized_vol_20d > spy_realized_vol_60d",
                "strategies": ["trend_long", "breakout_long"],
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
            },
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "locked_variables": [
                "core universe",
                "candidate pool",
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
        "gate_questions": {
            "1_alpha_hypothesis": (
                "volatility-state risk allocation from the playbook backlog: SPY realized-volatility expansion may weaken follow-through in already-qualified stock signals."
            ),
            "2_history_check": {
                "exp-20260514-006": (
                    "Rejected SPY volatility-contraction top-up; this tests the opposite risk-control state suggested by that rejection, not another contraction scalar."
                ),
                "breadth_thrust_allocation": (
                    "Broad-breadth trend variants in exp-20260507-007/010 were rejected; this uses realized volatility, not breadth."
                ),
                "core_recent_retunes": (
                    "Avoids RS20/RS60/clean-leader/exec-RR/sector-tape nearby retunes and does not alter Space/SEC accepted sleeves."
                ),
                "llm_soft_ranking": (
                    "Avoided because labeled forward records remain too thin for trustworthy soft-ranking alpha."
                ),
            },
            "3_single_causal_variable": (
                "spy_volatility_expansion_core_haircut_multiplier with fixed 20d-vs-60d realized-volatility state."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_008_spy_volatility_expansion_core_haircut.py"
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
                "feature_layer SPY Close series",
                "risk_engine sector",
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
        "sweep_summary": scaffold._sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement SPY realized-volatility fields and sizing haircut in shared feature/risk/portfolio modules called by both run.py and backtester.py."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else (
            "Use forward volatility-state attribution or a materially different risk-state field before retrying SPY volatility haircuts."
        ),
        "related_files": [
            "quant/experiments/exp_20260514_008_spy_volatility_expansion_core_haircut.py",
            "data/experiments/exp-20260514-008/spy_volatility_expansion_core_haircut.json",
            "experiments/logs/exp-20260514-008.json",
            "experiments/tickets/exp-20260514-008.json",
            "experiments/artifacts/exp-20260514-008_spy_volatility_expansion_core_haircut.md",
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
