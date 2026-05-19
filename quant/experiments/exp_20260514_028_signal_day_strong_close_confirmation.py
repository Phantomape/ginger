"""exp-20260514-028: signal-day strong-close confirmation scout.

Tests one production-visible allocation variable on the accepted core stack:
replace the accepted signal-day green-candle 1.05x post-sizing top-up with a
same-scalar strong-close confirmation based on where the signal day closed
inside its own high-low range.

This is a shadow experiment only unless Gate 4 passes. It does not change
entries, filters, ranking, exits, target widths, universe, LLM/news logic,
Space sleeves, heat, or slot limits.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260514-028"
EXPERIMENT_SLUG = "signal_day_strong_close_confirmation"
MULTIPLIER_KEY = "signal_day_strong_close_risk_multiplier_applied"
CLOSE_LOCATION_SWEEP = [0.70, 0.75, 0.80, 0.90]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

CURRENT_CLOSE_LOCATION_MIN = 0.75
STRONG_CLOSE_RISK_MULTIPLIER = (
    base.portfolio_engine.SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER
)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(base._safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


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
    if high <= low:
        return None
    return round((close - low) / (high - low), 6)


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
            close_location = (features_dict.get(sig.get("ticker")) or {}).get(
                "signal_day_close_location"
            )
            sig["signal_day_close_location"] = close_location
            sig["signal_day_strong_close"] = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and isinstance(close_location, (int, float))
                and close_location >= CURRENT_CLOSE_LOCATION_MIN
            )
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
    out["signal_day_strong_close_baseline_shares"] = shares
    out["signal_day_strong_close_desired_shares"] = desired_shares
    out["signal_day_strong_close_cap_shares"] = cap_shares
    out["signal_day_strong_close_new_shares"] = new_shares
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
            if sig.get("signal_day_strong_close") is True and sizing.get("shares_to_buy"):
                adjusted_sizing = _scale_sizing(
                    sizing,
                    STRONG_CLOSE_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted_sizing is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "close_location_min": CURRENT_CLOSE_LOCATION_MIN,
                            "close_location": sig.get("signal_day_close_location"),
                            "scalar": STRONG_CLOSE_RISK_MULTIPLIER,
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
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


def _run_window(label: str, close_location_min: float | None) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = base.get_universe()
    original_compute_features = base.feature_layer.compute_features
    original_enrich = base.risk_engine.enrich_signals
    original_size = base.portfolio_engine.size_signals
    original_green_multiplier = (
        base.portfolio_engine.SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER
    )
    original_multiplier_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS

    global CURRENT_CLOSE_LOCATION_MIN
    previous_close_location_min = CURRENT_CLOSE_LOCATION_MIN
    base.ADJUSTMENTS = []

    if close_location_min is not None:
        CURRENT_CLOSE_LOCATION_MIN = close_location_min
        base.feature_layer.compute_features = _make_compute_features_wrapper(
            original_compute_features
        )
        base.risk_engine.enrich_signals = _make_enrich_wrapper(original_enrich)
        base.portfolio_engine.SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER = 1.0
        base.portfolio_engine.size_signals = _make_size_wrapper(original_size)
        if MULTIPLIER_KEY not in base.backtester_module.SIZING_MULTIPLIER_KEYS:
            base.backtester_module.SIZING_MULTIPLIER_KEYS = (
                *base.backtester_module.SIZING_MULTIPLIER_KEYS,
                MULTIPLIER_KEY,
            )

    try:
        engine = base.BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(base.REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
    finally:
        base.feature_layer.compute_features = original_compute_features
        base.risk_engine.enrich_signals = original_enrich
        base.portfolio_engine.size_signals = original_size
        base.portfolio_engine.SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER = (
            original_green_multiplier
        )
        base.backtester_module.SIZING_MULTIPLIER_KEYS = original_multiplier_keys
        CURRENT_CLOSE_LOCATION_MIN = previous_close_location_min

    if result.get("error"):
        kind = "baseline" if close_location_min is None else str(close_location_min)
        raise RuntimeError(f"{label} {kind} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "adjustments": list(base.ADJUSTMENTS),
        "sizing_rule_signal_attribution": result.get("sizing_rule_signal_attribution")
        or {},
        "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution")
        or {},
    }


def _candidate_payload(
    close_location_min: float,
    before_runs: dict[str, dict[str, Any]],
    *,
    include_details: bool = False,
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_runs = {
        label: _run_window(label, close_location_min) for label in base.WINDOWS
    }
    after_metrics = {label: after_runs[label]["metrics"] for label in base.WINDOWS}
    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in base.WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    adjusted_count = sum(len(after_runs[label]["adjustments"]) for label in base.WINDOWS)
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    drawdown_guardrail_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and adjusted_count > 0
        and drawdown_guardrail_passed
    )
    return {
        "close_location_min": close_location_min,
        "passed": passed,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "adjusted_signal_count": adjusted_count,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "adjustments": {
            label: after_runs[label]["adjustments"] for label in base.WINDOWS
        }
        if include_details
        else None,
        "changed_trades": {
            label: base._changed_trades(
                before_runs[label]["trades"],
                after_runs[label]["trades"],
            )
            for label in base.WINDOWS
        }
        if include_details
        else None,
        "sizing_attribution": {
            label: {
                "signal": after_runs[label]["sizing_rule_signal_attribution"].get(
                    MULTIPLIER_KEY
                ),
                "trade": after_runs[label]["sizing_rule_trade_attribution"].get(
                    MULTIPLIER_KEY
                ),
            }
            for label in base.WINDOWS
        }
        if include_details
        else None,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row["passed"]]
    rows = passed or candidates
    return max(
        rows,
        key=lambda row: (
            1 if row["passed"] else 0,
            row["delta_metrics"]["aggregate_delta"]["expected_value_score_sum"],
            row["delta_metrics"]["aggregate_delta"]["total_pnl_sum"],
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in candidates:
        agg = row["delta_metrics"]["aggregate_delta"]
        out.append(
            {
                "close_location_min": row["close_location_min"],
                "passed": row["passed"],
                "expected_value_score_delta": agg["expected_value_score_sum"],
                "total_pnl_delta": agg["total_pnl_sum"],
                "improved_windows": row["gate4"]["improved_windows"],
                "regressed_windows": row["gate4"]["regressed_windows"],
                "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
                "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            }
        )
    return out


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Close-location min | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {thr:.2f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
                thr=row["close_location_min"],
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
            f"# {EXPERIMENT_ID} Signal-Day Strong-Close Confirmation",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: replace the accepted signal-day green-candle top-up state with a same-scalar close-location confirmation state. No entries, ranking, exits, universe, LLM/news, heat, slots, or other sizing rules changed.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected close-location min: `{payload['parameters']['selected_close_location_min']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: shadow scout only unless promoted into shared `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py`, and sizing attribution tests.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, None) for label in base.WINDOWS}
    sweep_results = [
        _candidate_payload(close_location_min, before_runs)
        for close_location_min in CLOSE_LOCATION_SWEEP
    ]
    selected_summary = _select_candidate(sweep_results)
    selected = _candidate_payload(
        selected_summary["close_location_min"],
        before_runs,
        include_details=True,
    )
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_signal_day_strong_close_confirmation"
    )
    interpretation = (
        "Signal-day close-location confirmation improved the accepted core stack versus the existing green-candle top-up and should be promoted only through shared production/backtest policy."
        if selected["passed"]
        else "Signal-day close-location confirmation did not beat the accepted green-candle top-up across the canonical three-window gate."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted signal-day own-green top-up is a blunt follow-through proxy. "
            "A signal whose close is near the top of its own high-low range may better "
            "capture intraday absorption and exclude weak green closes, improving risk "
            "allocation without changing the candidate set."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": "signal_day_confirmation_state_for_existing_1_05x_topup",
        "single_causal_variable": (
            "replace signal_day_ticker_green_candle with signal_day_close_location >= selected threshold for the existing 1.05x post-sizing top-up"
        ),
        "parameters": {
            "close_location_sweep": CLOSE_LOCATION_SWEEP,
            "selected_close_location_min": selected["close_location_min"],
            "risk_multiplier": STRONG_CLOSE_RISK_MULTIPLIER,
            "replacement_of_existing_green_topup": True,
            "state_definition": {
                "signal_day_close_location": "(close - low) / (high - low)",
                "strategies": ["trend_long", "breakout_long"],
            },
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all other sizing multipliers",
                "portfolio heat",
                "MAX_POSITIONS",
                "LLM/news replay",
                "Space sleeve",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital/risk allocation: use a stronger production-visible signal-day confirmation state on already-qualified core signals."
            ),
            "2_history_check": {
                "exp-20260513-007": (
                    "accepted signal-day own-green 1.05x top-up; this does not retune the scalar and tests a replacement state definition."
                ),
                "exp-20260513-036": (
                    "accepted clean SPY-relative signal-day outperformance top-up; this does not alter that clean-SPY path."
                ),
                "exp-20260514-014": (
                    "dual-RS interaction was rejected; this uses signal-day intraday close location, not another RS stack."
                ),
                "llm_soft_ranking": (
                    "Skipped because production-aligned LLM soft-ranking records remain too sparse for credible alpha validation."
                ),
            },
            "3_single_causal_variable": "signal-day confirmation state definition for the existing 1.05x post-sizing top-up",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 percentage points."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_028_signal_day_strong_close_confirmation.py"
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
                "feature_layer signal-day high/low/close",
                "risk_engine signal_day_close_location",
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
        "sweep_summary": _sweep_summary(sweep_results),
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking remains production-aligned sample limited; this deterministic allocation test is replayable on fixed OHLCV snapshots."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement close-location in shared feature/risk/sizing policy and add sizing attribution tests for both production and backtest paths."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": None
        if selected["passed"]
        else (
            "Do not replace the accepted green-candle top-up with close-location on these frozen windows without forward confirmation or a materially different signal-day state."
        ),
        "related_files": [
            "quant/experiments/exp_20260514_028_signal_day_strong_close_confirmation.py",
            "data/experiments/exp-20260514-028/signal_day_strong_close_confirmation.json",
            "experiments/logs/exp-20260514-028.json",
            "experiments/tickets/exp-20260514-028.json",
            "experiments/artifacts/exp-20260514-028_signal_day_strong_close_confirmation.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "selected_close_location_min": payload["parameters"][
            "selected_close_location_min"
        ],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_close_location_min": result["parameters"][
                    "selected_close_location_min"
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
