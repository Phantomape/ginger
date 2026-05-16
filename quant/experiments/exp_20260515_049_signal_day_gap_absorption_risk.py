"""exp-20260515-049: signal-day gap-absorption risk scout.

Tests one allocation variable on the accepted core stack: already-selected
trend/breakout stock signals whose signal day opened below the prior close,
recovered intraday, and ranked in the top quartile of same-day gap-absorption
strength. This is a cap-aware post-sizing top-up scout, not an entry filter.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260513_031_signal_day_range_compression_risk as sweep
import portfolio_engine


EXPERIMENT_ID = "exp-20260515-049"
EXPERIMENT_SLUG = "signal_day_gap_absorption_risk"
MULTIPLIER_KEY = "signal_day_gap_absorption_risk_multiplier_applied"

GAP_ABSORPTION_TOP_FRACTION = 0.25
EXCLUDED_SECTORS = {"ETF", "Commodities"}
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _is_finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _row_value(row: Any, key: str) -> float | None:
    try:
        value = row[key]
        if hasattr(value, "item"):
            value = value.item()
        value = float(value)
    except Exception:
        return None
    if not math.isfinite(value):
        return None
    return value


def _top_fraction_cutoff(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(0, math.ceil(len(sorted_values) * (1.0 - fraction)) - 1)
    return sorted_values[index]


def _make_compute_features_wrapper(
    original_compute_features: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    def wrapper(
        ticker: str,
        ohlcv_data: Any,
        earnings_data: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        features = original_compute_features(ticker, ohlcv_data, earnings_data)
        if features is None:
            return None
        features = dict(features)

        if ohlcv_data is None or len(ohlcv_data) < 2:
            features["signal_day_gap_pct"] = None
            features["signal_day_open_close_return_pct"] = None
            features["signal_day_close_location"] = None
            features["signal_day_gap_absorption_score"] = None
            return features

        today = ohlcv_data.iloc[-1]
        prior = ohlcv_data.iloc[-2]
        open_ = _row_value(today, "Open")
        high = _row_value(today, "High")
        low = _row_value(today, "Low")
        close = _row_value(today, "Close")
        prior_close = _row_value(prior, "Close")

        gap_pct = None
        open_close_return = None
        close_location = None
        score = None
        if (
            _is_finite(open_)
            and _is_finite(high)
            and _is_finite(low)
            and _is_finite(close)
            and _is_finite(prior_close)
            and float(open_) > 0
            and float(prior_close) > 0
        ):
            gap_pct = (float(open_) - float(prior_close)) / float(prior_close)
            open_close_return = (float(close) - float(open_)) / float(open_)
            day_range = float(high) - float(low)
            if day_range > 0:
                close_location = (float(close) - float(low)) / day_range
            if (
                gap_pct < 0
                and open_close_return > 0
                and close_location is not None
                and close_location >= 0.5
            ):
                score = (-gap_pct) + open_close_return

        features["signal_day_gap_pct"] = (
            round(gap_pct, 6) if _is_finite(gap_pct) else None
        )
        features["signal_day_open_close_return_pct"] = (
            round(open_close_return, 6)
            if _is_finite(open_close_return)
            else None
        )
        features["signal_day_close_location"] = (
            round(close_location, 6) if _is_finite(close_location) else None
        )
        features["signal_day_gap_absorption_score"] = (
            round(score, 6) if _is_finite(score) else None
        )
        return features

    return wrapper


def _gap_absorption_cutoff(features_dict: dict[str, dict[str, Any]]) -> float | None:
    values: list[float] = []
    for ticker, features in (features_dict or {}).items():
        sector = base.risk_engine.SECTOR_MAP.get(str(ticker or ""), "Unknown")
        if sector in EXCLUDED_SECTORS:
            continue
        score = (features or {}).get("signal_day_gap_absorption_score")
        if _is_finite(score):
            values.append(float(score))
    return _top_fraction_cutoff(values, GAP_ABSORPTION_TOP_FRACTION)


def _make_enrich_wrapper(
    original_enrich_signals: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapper(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        enriched = original_enrich_signals(signals, features_dict, *args, **kwargs)
        cutoff = _gap_absorption_cutoff(features_dict)
        for sig in enriched:
            ticker = str(sig.get("ticker") or "")
            features = features_dict.get(ticker) or {}
            score = features.get("signal_day_gap_absorption_score")
            state = bool(
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sig.get("sector") not in EXCLUDED_SECTORS
                and _is_finite(score)
                and _is_finite(cutoff)
                and float(score) >= float(cutoff)
            )
            sig["signal_day_gap_pct"] = features.get("signal_day_gap_pct")
            sig["signal_day_open_close_return_pct"] = features.get(
                "signal_day_open_close_return_pct"
            )
            sig["signal_day_close_location"] = features.get(
                "signal_day_close_location"
            )
            sig["signal_day_gap_absorption_score"] = score
            sig["signal_day_gap_absorption_cutoff"] = cutoff
            sig["signal_day_gap_absorption_state"] = state
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
    out["signal_day_gap_absorption_baseline_shares"] = shares
    out["signal_day_gap_absorption_desired_shares"] = desired_shares
    out["signal_day_gap_absorption_cap_shares"] = cap_shares
    out["signal_day_gap_absorption_new_shares"] = new_shares
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
            if not sig.get("signal_day_gap_absorption_state"):
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
                        "signal_day_gap_pct": sig.get("signal_day_gap_pct"),
                        "signal_day_open_close_return_pct": sig.get(
                            "signal_day_open_close_return_pct"
                        ),
                        "signal_day_close_location": sig.get(
                            "signal_day_close_location"
                        ),
                        "signal_day_gap_absorption_score": sig.get(
                            "signal_day_gap_absorption_score"
                        ),
                        "signal_day_gap_absorption_cutoff": sig.get(
                            "signal_day_gap_absorption_cutoff"
                        ),
                        "baseline_shares": sizing.get("shares_to_buy"),
                        "new_shares": new_sizing.get("shares_to_buy"),
                        "baseline_position_value": sizing.get("position_value_usd"),
                        "new_position_value": new_sizing.get("position_value_usd"),
                        "cap_shares": new_sizing.get(
                            "signal_day_gap_absorption_cap_shares"
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
            "Single variable: cap-aware post-sizing top-up for existing `trend_long` / `breakout_long` non-ETF/non-commodity stock signals in the top quartile of production-visible signal-day gap-absorption strength. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.",
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
            "Production impact: replay-only scout. A positive promotion must move the state and sizing helper into shared `feature_layer.py` / `risk_engine.py` / `portfolio_engine.py`, add attribution keys, update parity docs, and add focused tests before production behavior changes.",
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
            "Signal-day gap absorption cleared the canonical three-window scout "
            "and needs shared policy promotion before any production-visible use."
        )
    else:
        decision = "rejected_signal_day_gap_absorption_risk"
        rejection_reason = selected.get("rejection_reason") or "failed_three_window_gate4"
        interpretation = (
            "Signal-day gap absorption did not clear the canonical three-window "
            "gate; do not promote this allocation state on the frozen windows."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "After recent R:R, sector-thrust, reversal, close-location, options, "
            "and Space branches either failed or became sample-limited, the most "
            "promising core direction is a new production-visible demand state. "
            "Existing stock trend/breakout candidates that gap down but reclaim "
            "intraday in the strongest cross-sectional absorption quartile may "
            "deserve a small cap-aware allocation top-up."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "signal_day_gap_absorption_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk top-up for trend/breakout stock signals "
            "whose signal-day gap-absorption score is in the top quartile"
        ),
        "parameters": {
            "gap_absorption_top_fraction": GAP_ABSORPTION_TOP_FRACTION,
            "state_definition": (
                "gap_pct < 0, open_to_close_return > 0, close_location >= 0.5, "
                "and (-gap_pct + open_to_close_return) in the top quartile of "
                "non-ETF/non-commodity tickers on that signal day"
            ),
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
                "core risk allocation using production-visible signal-day "
                "gap-down absorption instead of another nearby scalar retry"
            ),
            "2_history_check": {
                "exp-20260515-042": (
                    "simple close-location top-up failed; this requires a "
                    "downside open gap plus intraday reclaim and cross-sectional "
                    "absorption strength"
                ),
                "exp-20260515-045": (
                    "simple prior-red/current-green reversal failed old_thin; "
                    "this tests same-day gap absorption rather than prior-day color"
                ),
                "exp-20260515-038/041/046": (
                    "R:R-only variants were old-window fragile; this uses a "
                    "different demand-state discriminator"
                ),
                "exp-20260515-099": (
                    "options overlay remains shadow-only because closed forward "
                    "outcomes are missing, so this run avoids that data limit"
                ),
                "SEC_semantics": (
                    "fresh PIT directional filing-shock fields remain missing, "
                    "so SEC retunes are invalid until richer semantics exist"
                ),
            },
            "3_single_causal_variable": (
                "signal_day_gap_absorption_risk_multiplier with a fixed state definition"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, no EV-regressed windows, "
                "survival >= 5%, nonzero adjusted signals, and max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_049_signal_day_gap_absorption_risk.py"
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
                "feature_layer signal-day Open/High/Low/Close",
                "feature_layer prior Close",
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
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM/options soft-ranking and SEC semantic branches remain "
                "data-limited; this deterministic OHLCV allocation state avoids "
                "those blockers."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement the same signal-day gap-absorption "
                "fields in shared feature/risk/sizing policy and rerun all three "
                "canonical windows before production use."
            ),
        },
        "why_not_other_changes": (
            "LLM/options soft-ranking lacks closed attribution, SEC earnings "
            "semantics lack PIT directional fields, Space is sample-limited after "
            "recent source-diversity follow-ons, and nearby core scalar branches "
            "have already failed. This tests one new deterministic allocation "
            "state instead."
        ),
        "known_risks": [
            "The top-quartile absorption state may be sparse on some dates.",
            "The state can overlap accepted signal-day green and RS20 helpers.",
            "A positive replay-only scout is not tradable until shared policy and parity tests exist.",
        ],
        "interpretation": interpretation,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, avoid nearby gap-absorption scalar retries without a "
            "different production-visible catalyst or drawdown discriminator. "
            "If accepted, promote through shared risk/sizing policy and rerun "
            "the canonical three-window backtest."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260515_049_signal_day_gap_absorption_risk.py",
            "data/experiments/exp-20260515-049/signal_day_gap_absorption_risk.json",
            "docs/experiments/logs/exp-20260515-049.json",
            "docs/experiments/tickets/exp-20260515-049.json",
            "docs/experiments/artifacts/exp-20260515-049_signal_day_gap_absorption_risk.md",
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
