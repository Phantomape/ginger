"""exp-20260515-042: signal-day close-location risk allocation.

Alpha search. Tests one production-visible state variable on the accepted core
stack: already-qualified trend/breakout stock signals whose signal-day close
location is in the same-day top quartile of non-ETF/non-commodity stocks.

This is a cap-aware post-sizing scout, not an entry filter, ranking change,
exit change, universe change, LLM/news change, or production default change.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260513_031_signal_day_range_compression_risk as sweep


EXPERIMENT_ID = "exp-20260515-042"
EXPERIMENT_SLUG = "signal_day_close_location_risk"
MULTIPLIER_KEY = "signal_day_close_location_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075]
CLOSE_LOCATION_TOP_FRACTION = 0.25
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _signal_day_close_location(ohlcv_data: Any) -> float | None:
    if ohlcv_data is None or len(ohlcv_data) < 1:
        return None
    row = ohlcv_data.iloc[-1]
    try:
        high = float(row["High"].item() if hasattr(row["High"], "item") else row["High"])
        low = float(row["Low"].item() if hasattr(row["Low"], "item") else row["Low"])
        close = float(
            row["Close"].item() if hasattr(row["Close"], "item") else row["Close"]
        )
    except Exception:
        return None
    day_range = high - low
    if day_range <= 0:
        return None
    return round((close - low) / day_range, 6)


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
        features["signal_day_close_location"] = _signal_day_close_location(ohlcv_data)
        return features

    return wrapped


def _close_location_cutoff(features_dict: dict[str, dict[str, Any]]) -> float | None:
    values: list[float] = []
    for ticker, features in (features_dict or {}).items():
        sector = base.risk_engine.SECTOR_MAP.get(ticker, "Unknown")
        close_location = (features or {}).get("signal_day_close_location")
        if sector in EXCLUDED_SECTORS:
            continue
        if isinstance(close_location, (int, float)) and math.isfinite(
            float(close_location)
        ):
            values.append(float(close_location))
    if not values:
        return None
    values.sort()
    index = max(
        0,
        math.ceil(len(values) * (1.0 - CLOSE_LOCATION_TOP_FRACTION)) - 1,
    )
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
        cutoff = _close_location_cutoff(features_dict)
        for sig in enriched:
            ticker = str(sig.get("ticker") or "")
            sector = str(sig.get("sector") or "")
            features = features_dict.get(ticker) or {}
            close_location = features.get("signal_day_close_location")
            eligible = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sector not in EXCLUDED_SECTORS
                and isinstance(close_location, (int, float))
                and isinstance(cutoff, (int, float))
                and float(close_location) >= float(cutoff)
            )
            sig["signal_day_close_location"] = close_location
            sig["signal_day_close_location_cutoff"] = (
                round(cutoff, 6) if isinstance(cutoff, (int, float)) else None
            )
            sig["signal_day_close_location_state"] = bool(eligible)
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
    out["signal_day_close_location_baseline_shares"] = shares
    out["signal_day_close_location_desired_shares"] = desired_shares
    out["signal_day_close_location_cap_shares"] = cap_shares
    out["signal_day_close_location_new_shares"] = new_shares
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
            if sig.get("signal_day_close_location_state") and sizing.get(
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
                            "signal_day_close_location": sig.get(
                                "signal_day_close_location"
                            ),
                            "signal_day_close_location_cutoff": sig.get(
                                "signal_day_close_location_cutoff"
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
                            "price_vs_200ma_extension_state": sig.get(
                                "price_vs_200ma_extension_state"
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
            f"# {EXPERIMENT_ID} Signal-Day Close-Location Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` non-ETF/non-commodity stock signals whose signal-day close location is in the same-day top quartile. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.",
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

    before_runs = {
        label: base._run_window(label, variant=False) for label in base.WINDOWS
    }
    candidates = [
        sweep._candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = sweep._select_candidate(candidates)
    passed = bool(selected["passed"])
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_signal_day_close_location_risk"
    )
    interpretation = (
        "Top-quartile signal-day close-location cleared the canonical three-window gate and should be promoted only through shared production/backtest policy."
        if passed
        else "Top-quartile signal-day close-location did not clear the canonical three-window gate; do not promote this state variable on the frozen windows."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted own-green candle top-up is a coarse intraday confirmation state. "
            "Among already-qualified trend/breakout stock signals, closing in the upper part "
            "of the signal-day range should better isolate constructive absorption and deserve "
            "a small cap-aware allocation top-up."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "signal_day_close_location_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk top-up for trend/breakout stock signals whose signal-day close location is in the same-day top quartile"
        ),
        "parameters": {
            "state_definition": {
                "strategies": ["trend_long", "breakout_long"],
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
                "close_location": "(Close - Low) / (High - Low)",
                "top_fraction": CLOSE_LOCATION_TOP_FRACTION,
            },
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "anti_js": "No JavaScript was used.",
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
        },
        "historical_experiment_check": {
            "exp-20260428-024": (
                "Signal-day close location was tested as an entry-cancel filter before the current accepted stack; this run is a current-stack allocation scout, not a survival-reducing filter."
            ),
            "exp-20260513-007": (
                "Own-green candle is already accepted as a coarse positive intraday state; this run tests a stronger upper-range close-location discriminator rather than a nearby scalar retry."
            ),
            "recent_avoided_branches": (
                "LLM soft-ranking remains data-limited; raw Space/candidate-pool expansion and simple R:R scalars were recently rejected or sample-limited."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "core risk allocation: signal-day top-quartile close location identifies better constructive absorption than the accepted own-green candle alone."
            ),
            "2_history_check": (
                "Close-location entry cancel was previously explored as a filter; own-green sizing is accepted; no current-stack close-location allocation scout was found."
            ),
            "3_single_causal_variable": (
                "signal_day_close_location_risk_multiplier with a fixed same-day top-quartile state definition"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, min survival >= 5%, trade_count >= 50, max DD worse <= 0.5pp, adjusted cohort nonzero."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_042_signal_day_close_location_risk.py"
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
                "feature_layer signal-day High/Low/Close from OHLCV snapshot",
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
        "risk_distribution": {
            "before": _risk_distribution(selected["before_metrics"]),
            "after": _risk_distribution(selected["after_metrics"]),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Recent records show LLM soft-ranking is attribution/data-limited, so this run used deterministic OHLCV fields."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_accepted": (
                "Implement signal-day close-location fields and sizing top-up in shared feature/risk/portfolio modules called by both run.py and backtester.py; add attribution keys and focused parity tests before live/default behavior changes."
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
            "Use forward close-location attribution or a materially different production-visible intraday-quality state before retrying close-location overlays."
        ),
        "related_files": [
            "quant/experiments/exp_20260515_042_signal_day_close_location_risk.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "This avoids LLM soft-ranking, SEC semantic field tuning, Space mature-cohort expansion, raw candidate-pool growth, and simple R:R scalars because recent logs mark those paths data-limited, rejected, or sample-thin. It keeps the core candidate set fixed and tests one production-visible allocation discriminator."
        ),
    }
    payload["artifact_markdown"] = _markdown(payload)
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
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
