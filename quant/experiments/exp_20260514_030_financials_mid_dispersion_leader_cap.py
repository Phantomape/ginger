"""exp-20260514-030: Financials mid-dispersion leader cap scout.

Tests one production-visible allocation variable on the accepted core:
Financials trend sector-leaders already have a 50% sleeve cap. This checks
whether the narrower intersection with the existing mid-sector-dispersion state
deserves incremental cap room. It is shadow-only unless Gate 4 passes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260514-030"
EXPERIMENT_SLUG = "financials_mid_dispersion_leader_cap"
CAP_KEY = "trend_financials_mid_dispersion_leader_max_position_pct_applied"
CAP_SWEEP = [0.525, 0.55]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

CURRENT_MAX_POSITION_PCT = base.portfolio_engine.TREND_FINANCIALS_SECTOR_LEADER_MAX_POSITION_PCT

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


def _is_target_sleeve(sig: dict[str, Any], sizing: dict[str, Any]) -> bool:
    return bool(
        sig.get("strategy") == "trend_long"
        and sig.get("sector") == "Financials"
        and sig.get("financials_sector_leader") is True
        and sig.get("mid_sector_dispersion") is True
        and sizing.get("shares_to_buy")
        and sizing.get("entry_price")
        and sizing.get("net_risk_per_share")
        and sizing.get("base_risk_pct") is not None
        and sizing.get("financials_sector_leader_risk_multiplier_applied") != 1.0
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


def _apply_post_sizing_topups(
    sig: dict[str, Any],
    shares: int,
    cap_shares: int,
    sizing: dict[str, Any],
) -> int:
    if shares <= 0:
        return shares
    if (
        sig.get("rs20_entry_state_leader") is True
        and sig.get("strategy") in {"trend_long", "breakout_long"}
        and base.portfolio_engine.RS20_ENTRY_STATE_RISK_MULTIPLIER > 1.0
    ):
        shares = min(
            max(
                shares,
                int(
                    math.floor(
                        shares * base.portfolio_engine.RS20_ENTRY_STATE_RISK_MULTIPLIER
                    )
                ),
            ),
            cap_shares,
        )
    if (
        sig.get("signal_day_ticker_green_candle") is True
        and sig.get("strategy") in {"trend_long", "breakout_long"}
        and base.portfolio_engine.SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER > 1.0
    ):
        shares = min(
            max(
                shares,
                int(
                    math.floor(
                        shares
                        * base.portfolio_engine.SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER
                    )
                ),
            ),
            cap_shares,
        )
    if (
        sig.get("rs60_top_quintile_state") is True
        and sig.get("strategy") in {"trend_long", "breakout_long"}
        and base.portfolio_engine.RS60_TOP_QUINTILE_RISK_MULTIPLIER > 1.0
    ):
        shares = min(
            max(
                shares,
                int(
                    math.floor(
                        shares * base.portfolio_engine.RS60_TOP_QUINTILE_RISK_MULTIPLIER
                    )
                ),
            ),
            cap_shares,
        )
    if (
        sig.get("signal_day_ticker_outperformed_spy") is True
        and sig.get("strategy") in {"trend_long", "breakout_long"}
        and sizing.get("spy_relative_leader_risk_on_multiplier_applied")
        == base.portfolio_engine.RISK_ON_SPY_RELATIVE_LEADER_RISK_MULTIPLIER
        and base.portfolio_engine.CLEAN_SPY_LEADER_SIGNAL_DAY_RISK_MULTIPLIER > 1.0
    ):
        shares = min(
            max(
                shares,
                int(
                    math.floor(
                        shares
                        * base.portfolio_engine.CLEAN_SPY_LEADER_SIGNAL_DAY_RISK_MULTIPLIER
                    )
                ),
            ),
            cap_shares,
        )
    return shares


def _resize_with_cap(
    sig: dict[str, Any],
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
        or base.portfolio_engine.TREND_FINANCIALS_SECTOR_LEADER_MAX_POSITION_PCT
    )
    raw_shares = max(1, int(math.floor((portfolio_value * risk_pct) / net_risk_per_share)))
    old_cap_shares = max(1, int(math.floor(portfolio_value * old_cap_pct / entry)))
    new_cap_shares = max(
        1,
        int(math.floor(portfolio_value * CURRENT_MAX_POSITION_PCT / entry)),
    )
    base_shares = min(raw_shares, new_cap_shares)
    new_shares = _apply_post_sizing_topups(sig, base_shares, new_cap_shares, sizing)
    if new_shares <= old_shares:
        return sizing

    out = dict(sizing)
    out["trend_financials_mid_dispersion_leader_cap_baseline_shares"] = old_shares
    out["trend_financials_mid_dispersion_leader_cap_raw_shares"] = raw_shares
    out["trend_financials_mid_dispersion_leader_cap_old_cap_shares"] = old_cap_shares
    out["trend_financials_mid_dispersion_leader_cap_new_cap_shares"] = new_cap_shares
    out["trend_financials_mid_dispersion_leader_cap_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (
        (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
    )
    out["max_position_pct_applied"] = CURRENT_MAX_POSITION_PCT
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
                adjusted_sizing = _resize_with_cap(sig, sizing, portfolio_value)
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
                                "trend_financials_mid_dispersion_leader_cap_raw_shares"
                            ),
                            "old_cap_shares": adjusted_sizing.get(
                                "trend_financials_mid_dispersion_leader_cap_old_cap_shares"
                            ),
                            "new_cap_shares": adjusted_sizing.get(
                                "trend_financials_mid_dispersion_leader_cap_new_cap_shares"
                            ),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "mid_sector_dispersion": sig.get("mid_sector_dispersion"),
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
    out = []
    for row in candidates:
        agg = row["delta_metrics"]["aggregate_delta"]
        out.append(
            {
                "max_position_pct": row["max_position_pct"],
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
            f"# {EXPERIMENT_ID} Financials Mid-Dispersion Leader Cap",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: max position cap for the already-accepted `trend_long + Financials + financials_sector_leader=true` sleeve, restricted to signals that also carry `mid_sector_dispersion=true`. Entries, exits, ranking, universe, LLM/news logic, raw multipliers, heat, and slot limits were unchanged.",
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
        else "rejected_financials_mid_dispersion_leader_cap"
    )
    interpretation = (
        "The Financials sector-leader mid-dispersion intersection remained cap-bound and the selected cap improved the canonical three-window stack without EV regression."
        if selected["passed"]
        else "The mid-dispersion Financials leader cap increase did not improve the accepted core stack across the canonical three-window gate."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted Financials sector-leader cap may still under-allocate "
            "the strongest rotation tape cases. When Financials sector-leader "
            "trend signals also occur in the accepted mid-sector-dispersion "
            "state, incremental cap room may unlock convex winners without "
            "broad Financials cap expansion."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": "max_position_pct_for_financials_sector_leader_mid_sector_dispersion_sleeve",
        "single_causal_variable": (
            "max_position_pct for trend_long Financials sector-leader signals with mid_sector_dispersion=true"
        ),
        "parameters": {
            "cap_sweep": CAP_SWEEP,
            "baseline_financials_sector_leader_max_position_pct": (
                base.portfolio_engine.TREND_FINANCIALS_SECTOR_LEADER_MAX_POSITION_PCT
            ),
            "selected_max_position_pct": selected["max_position_pct"],
            "target_sleeve": {
                "strategy": "trend_long",
                "sector": "Financials",
                "financials_sector_leader": True,
                "mid_sector_dispersion": True,
            },
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "raw Financials risk multipliers",
                "existing Financials sector-leader cap",
                "all other sizing multipliers",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "Space sleeves",
            ],
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260514-023": (
                    "Accepted the broad Financials sector-leader cap at 50%; "
                    "this run does not retune that whole sleeve and only tests "
                    "a new production-visible mid-dispersion intersection."
                ),
                "exp-20260510-019": (
                    "Rejected/inert non-Financials mid-dispersion sector-leader "
                    "top-up; this run targets the Financials leader sleeve that "
                    "already has accepted cap-bound evidence."
                ),
                "exp-20260506-005": (
                    "Financials leader target-width retunes were rejected; this "
                    "run changes initial cap room only, not exits."
                ),
            },
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking remains production-sample limited; this "
                "deterministic allocation alpha uses existing shared fields."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: Financials sector-leaders with accepted "
                "mid-sector-dispersion confirmation may deserve more cap room"
            ),
            "2_history_check": (
                "No same or near-identical experiment found; nearest broad "
                "Financials cap was accepted at 50%, while non-Financials "
                "mid-dispersion sector-leader top-up was inert."
            ),
            "3_single_causal_variable": "sleeve-specific max_position_pct",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL "
                "positive, at least two EV-improved windows, no EV-regressed "
                "windows, survival >= 5%, max DD worse <= 0.5pp, nonzero "
                "adjustments"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_030_financials_mid_dispersion_leader_cap.py"
            ),
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three-window fixed-snapshot replay",
            "windows": base.WINDOWS,
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "strategy",
                "sector",
                "financials_sector_leader",
                "mid_sector_dispersion",
                "entry_price",
                "net_risk_per_share",
                "base_risk_pct",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta_sum": selected["delta_metrics"]["aggregate_delta"][
                "signals_generated_sum"
            ],
            "signals_survived_delta_sum": selected["delta_metrics"]["aggregate_delta"][
                "signals_survived_sum"
            ],
            "survival_rate_min_after": selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ],
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
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking data is insufficient, so this run deliberately "
                "tests deterministic capital allocation instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted for trading, add a shared constant and cap branch in "
                "portfolio_engine.size_signals, include the attribution key in "
                "backtester.py, and add focused production/backtest parity tests "
                "before live orders change."
            ),
        },
        "decision_reason": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            "Do not retry nearby Financials mid-dispersion cap values unless "
            "new forward cap-room or leader-quality evidence separates winners "
            "from cap-amplified losers."
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

    data_path = (
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
    artifact_path = (
        base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    base._write_json(data_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, payload)
    artifact_path.write_text(payload["artifact_markdown"] + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)
    return payload


if __name__ == "__main__":
    result = run()
    summary = {
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "selected_max_position_pct": result["parameters"][
            "selected_max_position_pct"
        ],
        "gate4": result["gate4"],
        "expected_value_score_delta": result["expected_value_score_delta"],
        "total_pnl_delta": result["total_pnl_delta"],
        "sweep_summary": result["sweep_summary"],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(base._safe(summary), indent=2, ensure_ascii=False, sort_keys=True))
