"""exp-20260515-011: SLV trend near-high cap scout.

Tests one production-visible capital-allocation variable on the accepted core:
already-qualified SLV trend signals inside the Commodity near-52-week-high
sleeve may deserve more cap room than the broad Commodity cap, and different
cap room than the existing GLD/IAU gold sleeve. This does not change entries,
exits, ranking, universe, LLM/news behavior, targets, heat, slots, or the raw
Commodity near-high risk multiplier.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260515-011"
EXPERIMENT_SLUG = "silver_trend_near_high_cap"
CAP_KEY = "trend_silver_near_high_max_position_pct_applied"
CAP_SWEEP = [0.575, 0.60, 0.625, 0.65]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
SILVER_TICKERS = {"SLV"}

CURRENT_MAX_POSITION_PCT = 0.60


PRE_SIZING_MULTIPLIER_KEYS = (
    "tqs_risk_multiplier_applied",
    "trend_industrials_risk_multiplier_applied",
    "trend_financials_risk_multiplier_applied",
    "financials_sector_leader_risk_multiplier_applied",
    "risk_on_unmodified_risk_multiplier_applied",
    "spy_relative_leader_risk_on_multiplier_applied",
    "trend_mid_sector_dispersion_risk_multiplier_applied",
    "trend_tech_tight_gap_risk_multiplier_applied",
    "trend_tech_gap_risk_multiplier_applied",
    "trend_tech_near_high_risk_multiplier_applied",
    "trend_tech_dte_risk_multiplier_applied",
    "breakout_industrials_gap_risk_multiplier_applied",
    "breakout_comms_near_high_risk_multiplier_applied",
    "breakout_comms_gap_risk_multiplier_applied",
    "breakout_financials_dte_risk_multiplier_applied",
    "breakout_tech_dte_risk_multiplier_applied",
    "breakout_healthcare_dte_risk_multiplier_applied",
    "trend_healthcare_dte_risk_multiplier_applied",
    "trend_consumer_near_high_dte_risk_multiplier_applied",
    "trend_commodities_near_high_risk_multiplier_applied",
)


def _is_target_sleeve(sig: dict[str, Any], sizing: dict[str, Any]) -> bool:
    pct_from_high = (sig.get("conditions_met") or {}).get("pct_from_52w_high")
    return bool(
        sig.get("ticker") in SILVER_TICKERS
        and sig.get("strategy") == "trend_long"
        and sig.get("sector") == "Commodities"
        and isinstance(pct_from_high, (int, float))
        and pct_from_high
        >= base.portfolio_engine.TREND_COMMODITIES_NEAR_HIGH_MAX_PULLBACK
        and sizing.get("trend_commodities_near_high_risk_multiplier_applied")
        == base.portfolio_engine.TREND_COMMODITIES_NEAR_HIGH_RISK_MULTIPLIER
        and sizing.get("shares_to_buy")
        and sizing.get("entry_price")
        and sizing.get("net_risk_per_share")
        and sizing.get("base_risk_pct") is not None
    )


def _pre_sizing_risk_pct(sizing: dict[str, Any]) -> float | None:
    risk_pct = sizing.get("base_risk_pct")
    if not isinstance(risk_pct, (int, float)):
        return None
    out = float(risk_pct)
    for key in PRE_SIZING_MULTIPLIER_KEYS:
        value = sizing.get(key)
        if isinstance(value, (int, float)):
            out *= float(value)
    return out


def _resize_with_cap(
    sizing: dict[str, Any],
    portfolio_value: float,
) -> dict[str, Any]:
    old_shares = int(sizing.get("shares_to_buy") or 0)
    entry = float(sizing.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    risk_pct = _pre_sizing_risk_pct(sizing)
    if old_shares <= 0 or entry <= 0 or net_risk_per_share <= 0 or risk_pct is None:
        return sizing

    old_cap_pct = float(
        sizing.get("max_position_pct_applied")
        or base.portfolio_engine.TREND_COMMODITIES_NEAR_HIGH_MAX_POSITION_PCT
    )
    new_cap_pct = max(old_cap_pct, CURRENT_MAX_POSITION_PCT)
    if new_cap_pct <= old_cap_pct:
        return sizing

    raw_shares = max(
        1,
        int(math.floor((portfolio_value * risk_pct) / net_risk_per_share)),
    )
    old_cap_shares = max(1, int(math.floor(portfolio_value * old_cap_pct / entry)))
    new_cap_shares = max(1, int(math.floor(portfolio_value * new_cap_pct / entry)))
    new_shares = min(raw_shares, new_cap_shares)
    if new_shares <= old_shares:
        return sizing

    out = dict(sizing)
    out["trend_silver_near_high_cap_baseline_shares"] = old_shares
    out["trend_silver_near_high_cap_raw_shares"] = raw_shares
    out["trend_silver_near_high_cap_old_cap_pct"] = old_cap_pct
    out["trend_silver_near_high_cap_new_cap_pct"] = new_cap_pct
    out["trend_silver_near_high_cap_old_cap_shares"] = old_cap_shares
    out["trend_silver_near_high_cap_new_cap_shares"] = new_cap_shares
    out["trend_silver_near_high_cap_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (
        (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
    )
    out["max_position_pct_applied"] = new_cap_pct
    out[CAP_KEY] = CURRENT_MAX_POSITION_PCT
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
            if _is_target_sleeve(sig, sizing):
                adjusted_sizing = _resize_with_cap(sizing, portfolio_value)
                if adjusted_sizing is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "max_position_pct": CURRENT_MAX_POSITION_PCT,
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "raw_shares": adjusted_sizing.get(
                                "trend_silver_near_high_cap_raw_shares"
                            ),
                            "old_cap_pct": adjusted_sizing.get(
                                "trend_silver_near_high_cap_old_cap_pct"
                            ),
                            "new_cap_pct": adjusted_sizing.get(
                                "trend_silver_near_high_cap_new_cap_pct"
                            ),
                            "old_cap_shares": adjusted_sizing.get(
                                "trend_silver_near_high_cap_old_cap_shares"
                            ),
                            "new_cap_shares": adjusted_sizing.get(
                                "trend_silver_near_high_cap_new_cap_shares"
                            ),
                            "pct_from_52w_high": sig.get("pct_from_52w_high"),
                            "conditions_pct_from_52w_high": (
                                sig.get("conditions_met") or {}
                            ).get("pct_from_52w_high"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "signal_day_ticker_outperformed_spy": sig.get(
                                "signal_day_ticker_outperformed_spy"
                            ),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "rs60_top_quintile_state": sig.get(
                                "rs60_top_quintile_state"
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _run_window(label: str, max_position_pct: float | None) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = base.get_universe()
    original_size = base.portfolio_engine.size_signals
    original_multiplier_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS

    global CURRENT_MAX_POSITION_PCT
    previous_cap = CURRENT_MAX_POSITION_PCT
    base.ADJUSTMENTS = []

    if max_position_pct is not None:
        CURRENT_MAX_POSITION_PCT = max_position_pct
        base.portfolio_engine.size_signals = _make_size_wrapper(original_size)
        if CAP_KEY not in base.backtester_module.SIZING_MULTIPLIER_KEYS:
            base.backtester_module.SIZING_MULTIPLIER_KEYS = (
                *base.backtester_module.SIZING_MULTIPLIER_KEYS,
                CAP_KEY,
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
        base.portfolio_engine.size_signals = original_size
        base.backtester_module.SIZING_MULTIPLIER_KEYS = original_multiplier_keys
        CURRENT_MAX_POSITION_PCT = previous_cap

    if result.get("error"):
        kind = "baseline" if max_position_pct is None else str(max_position_pct)
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
    cap: float,
    before_runs: dict[str, dict[str, Any]],
    *,
    include_details: bool = False,
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_runs = {label: _run_window(label, cap) for label in base.WINDOWS}
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
        "max_position_pct": cap,
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
                    CAP_KEY
                ),
                "trade": after_runs[label]["sizing_rule_trade_attribution"].get(
                    CAP_KEY
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
    return [
        {
            "max_position_pct": row["max_position_pct"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
        }
        for row in candidates
    ]


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {cap:.3f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
                cap=row["max_position_pct"],
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
            f"# {EXPERIMENT_ID} Silver Trend Near-High Cap",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: max position cap for already-qualified `SLV` `trend_long` signals in the accepted `Commodities` near-52-week-high sleeve. Entries, exits, ranking, universe, LLM/news logic, target width, raw Commodity multiplier, heat, and slots were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected cap: `{payload['parameters']['selected_max_position_pct']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: shadow scout only unless promoted into shared `constants.py`, `portfolio_engine.py`, backtest attribution, and focused parity tests.",
        ]
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
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, None) for label in base.WINDOWS}
    sweep_results = [_candidate_payload(cap, before_runs) for cap in CAP_SWEEP]
    selected_summary = _select_candidate(sweep_results)
    selected = _candidate_payload(
        selected_summary["max_position_pct"],
        before_runs,
        include_details=True,
    )
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_silver_trend_near_high_cap"
    )
    interpretation = (
        "SLV near-high trend entries were cap-bound and the selected cap improved the canonical three-window stack without EV regression."
        if selected["passed"]
        else "SLV near-high trend cap expansion did not clear the canonical three-window Gate 4 stability test."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "SLV has been one of the strongest surviving Commodity trend winners, "
            "but it is not covered by the accepted GLD/IAU gold cap. Raising only "
            "the cap for already-qualified SLV trend near-high entries may unlock "
            "winner convexity without expanding the candidate pool or retuning "
            "Commodity-wide risk."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": "max_position_pct_for_slv_trend_near_high_sleeve",
        "single_causal_variable": (
            "max_position_pct for SLV trend_long Commodities signals with pct_from_52w_high >= -0.03"
        ),
        "parameters": {
            "cap_sweep": CAP_SWEEP,
            "baseline_broad_commodity_cap": (
                base.portfolio_engine.TREND_COMMODITIES_NEAR_HIGH_MAX_POSITION_PCT
            ),
            "baseline_gold_cap": base.portfolio_engine.TREND_GOLD_NEAR_HIGH_MAX_POSITION_PCT,
            "baseline_clean_spy_cap_only_leader_cap": (
                base.portfolio_engine.CLEAN_SPY_CAP_ONLY_LEADER_MAX_POSITION_PCT
            ),
            "selected_max_position_pct": selected["max_position_pct"],
            "target_sleeve": {
                "ticker": sorted(SILVER_TICKERS),
                "strategy": "trend_long",
                "sector": "Commodities",
                "pct_from_52w_high_min": (
                    base.portfolio_engine.TREND_COMMODITIES_NEAR_HIGH_MAX_PULLBACK
                ),
            },
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "raw Commodity near-high risk multiplier",
                "gold GLD/IAU cap",
                "all other sizing multipliers",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "Space sleeves",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260514-018": (
                    "Accepted the broad Commodity trend near-high cap; this run tests only SLV-specific cap room after that promotion."
                ),
                "exp-20260508-016": (
                    "Precious-metal target replay warned against broad SLV target extension; this run changes initial cap only, not target width."
                ),
                "exp-20260505-013": (
                    "Rejected broad Commodity state risk retune; this run avoids Commodity-wide size and isolates a single ticker sleeve."
                ),
                "exp-20260515-008": (
                    "Accepted clean-SPY cap-only leader cap; this run tests whether SLV needs its own cap above generic leader/Commodity caps."
                ),
            },
            "why_not_llm_or_space": (
                "LLM soft-ranking remains candidate-replay/data limited, and nearby Space allocation retunes were rejected; this run uses deterministic production-visible fields."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: already-qualified SLV Commodity trend near-high entries may deserve ticker-specific cap room"
            ),
            "2_history_check": (
                "No prior SLV-specific cap experiment found; prior Commodity-wide, target-width, and Space retunes are different variables."
            ),
            "3_single_causal_variable": "SLV trend-near-high max_position_pct only",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max DD worse <= 0.5pp, nonzero adjustments"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_011_silver_trend_near_high_cap.py"
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
                "portfolio_engine ticker",
                "portfolio_engine strategy",
                "portfolio_engine sector",
                "portfolio_engine conditions_met.pct_from_52w_high",
                "portfolio_engine sizing entry_price",
                "portfolio_engine sizing net_risk_per_share",
                "portfolio_engine sizing base_risk_pct",
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
        "sweep_summary": _sweep_summary(sweep_results),
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample/data limited; this run deliberately chose a deterministic allocation alpha instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted for trading, add a shared SLV cap constant and cap branch in portfolio_engine.size_signals, include the attribution key in backtester.py, and add focused production/backtest parity tests before live orders change."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "decision_reason": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            "Promote only through shared sizing code and parity tests."
            if selected["passed"]
            else "Do not retry nearby SLV cap values without new forward cap-room evidence or a distinct SLV quality discriminator."
        ),
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    payload["artifact_markdown"] = _markdown(payload)
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
                "selected_max_position_pct": result["parameters"][
                    "selected_max_position_pct"
                ],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "sweep_summary": result["sweep_summary"],
                "production_impact": result["production_impact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
