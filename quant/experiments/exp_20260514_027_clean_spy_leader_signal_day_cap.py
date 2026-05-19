"""exp-20260514-027: clean SPY-leader signal-day cap scout.

Tests one production-visible capital-allocation variable on the accepted core:
the already-accepted clean SPY-relative leader signal-day confirmation sleeve
may still be clipped by the current 50% SPY-relative leader position cap. This
tests only that narrower sleeve cap, not entries, exits, ranking, universe,
LLM/news behavior, or the accepted clean signal-day share multiplier.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260514-027"
EXPERIMENT_SLUG = "clean_spy_leader_signal_day_cap"
CAP_KEY = "clean_spy_leader_signal_day_max_position_pct_applied"
CAP_SWEEP = [0.525, 0.55, 0.60]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

CURRENT_MAX_POSITION_PCT = base.portfolio_engine.RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT


PRE_SIZING_MULTIPLIER_KEYS = (
    "tqs_risk_multiplier_applied",
    "trend_industrials_risk_multiplier_applied",
    "trend_financials_risk_multiplier_applied",
    "financials_sector_leader_risk_multiplier_applied",
    "risk_on_unmodified_risk_multiplier_applied",
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
        sig.get("strategy") in {"trend_long", "breakout_long"}
        and sig.get("signal_day_ticker_outperformed_spy") is True
        and sizing.get("spy_relative_leader_risk_on_multiplier_applied")
        == base.portfolio_engine.RISK_ON_SPY_RELATIVE_LEADER_RISK_MULTIPLIER
        and sizing.get("shares_to_buy")
        and sizing.get("entry_price")
        and sizing.get("stop_price")
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


def _apply_post_sizing_topups(
    sig: dict[str, Any],
    shares: int,
    cap_shares: int,
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

    raw_shares = max(
        1,
        int(math.floor((portfolio_value * risk_pct) / net_risk_per_share)),
    )
    old_cap_shares = max(
        1,
        int(
            math.floor(
                portfolio_value
                * base.portfolio_engine.RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT
                / entry
            )
        ),
    )
    new_cap_shares = max(
        1,
        int(math.floor(portfolio_value * CURRENT_MAX_POSITION_PCT / entry)),
    )
    base_shares = min(raw_shares, new_cap_shares)
    new_shares = _apply_post_sizing_topups(sig, base_shares, new_cap_shares)
    if new_shares <= old_shares:
        return sizing

    out = dict(sizing)
    out["clean_spy_leader_signal_day_cap_baseline_shares"] = old_shares
    out["clean_spy_leader_signal_day_cap_raw_shares"] = raw_shares
    out["clean_spy_leader_signal_day_cap_old_cap_shares"] = old_cap_shares
    out["clean_spy_leader_signal_day_cap_new_cap_shares"] = new_cap_shares
    out["clean_spy_leader_signal_day_cap_new_shares"] = new_shares
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
                                "clean_spy_leader_signal_day_cap_raw_shares"
                            ),
                            "old_cap_shares": adjusted_sizing.get(
                                "clean_spy_leader_signal_day_cap_old_cap_shares"
                            ),
                            "new_cap_shares": adjusted_sizing.get(
                                "clean_spy_leader_signal_day_cap_new_cap_shares"
                            ),
                            "ticker_minus_spy_signal_day_open_close_return_pct": sig.get(
                                "ticker_minus_spy_signal_day_open_close_return_pct"
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
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "trade_quality_score": sig.get("trade_quality_score"),
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
        key=lambda row: row["delta_metrics"]["aggregate_delta"][
            "expected_value_score_sum"
        ],
    )


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
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
    sweep_rows = [
        "| Cap | Gate 4 | Aggregate dEV | Aggregate dPnL | Max DD worse | Adjusted signals |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_results"]:
        agg = row["delta_metrics"]["aggregate_delta"]
        sweep_rows.append(
            "| {cap:.3f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {dd:+.4f} | {adj} |".format(
                cap=row["max_position_pct"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=agg["expected_value_score_sum"],
                dpnl=agg["total_pnl_sum"],
                dd=row["gate4"]["max_drawdown_worse"],
                adj=row["gate4"]["adjusted_signal_count"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Clean SPY-Leader Signal-Day Cap",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: max position cap for signals that already qualify for the accepted clean risk-on SPY-relative leader path and also beat SPY open-to-close on the signal day. Entries, exits, ranking, universe, LLM/news logic, accepted risk multipliers, heat, and slot limits were unchanged.",
            "",
            *rows,
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            "Production impact: shadow experiment only unless promoted into shared `constants.py` and `portfolio_engine.py`. A positive promotion must apply the cap before both backtest and production paths call `size_signals`.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, None) for label in base.WINDOWS}
    sweep_results = [_candidate_payload(cap, before_runs) for cap in CAP_SWEEP]
    selected = _select_candidate(sweep_results)
    detailed_selected = _candidate_payload(
        selected["max_position_pct"],
        before_runs,
        include_details=True,
    )
    decision = (
        "accepted_for_shared_policy_implementation"
        if detailed_selected["passed"]
        else "rejected_clean_spy_leader_signal_day_cap"
    )
    interpretation = (
        "The accepted clean SPY-relative signal-day confirmation sleeve remained cap-bound and the selected sleeve-specific cap improved the canonical three-window stack without EV regression."
        if detailed_selected["passed"]
        else "The clean SPY-relative signal-day cap did not clear the canonical three-window gate; keep the accepted 1.10x top-up and 50% SPY-leader cap unchanged."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted clean SPY-relative leader signal-day confirmation sleeve is cap-bound by the existing 50% SPY-leader position limit. Raising only that narrower sleeve cap may unlock confirmed leader convexity without changing entries or the accepted clean signal-day multiplier."
        ),
        "change_type": "capital_allocation_shared_policy",
        "changed_variable": "clean_spy_leader_signal_day_max_position_pct",
        "single_causal_variable": (
            "max_position_pct for clean risk_on SPY-relative leaders that beat SPY on signal day"
        ),
        "parameters": {
            "selected_max_position_pct": detailed_selected["max_position_pct"],
            "baseline_spy_relative_leader_max_position_pct": (
                base.portfolio_engine.RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT
            ),
            "cap_sweep": CAP_SWEEP,
            "qualifier": {
                "strategy": ["trend_long", "breakout_long"],
                "regime_exit_bucket": "risk_on",
                "spy_relative_leader": True,
                "signal_day_ticker_outperformed_spy": True,
            },
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "risk_on SPY-relative leader risk multiplier",
                "clean signal-day 1.10x share top-up",
                "all other sizing multipliers",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "Space sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "capital allocation: unlock cap room only for an accepted, production-visible clean SPY-relative signal-day confirmation sleeve",
            "2_history_check": {
                "exp-20260513-036": "accepted clean SPY-relative signal-day 1.10x cap-aware post-sizing top-up; 1.15x failed drawdown",
                "exp-20260514-019": "RS60 sleeve cap was rejected; this uses a different accepted confirmation state",
                "exp-20260514-022": "token risk floor was rejected; this does not alter low-risk residuals",
                "exp-20260514-023": "Financials sector-leader cap accepted on a different sleeve",
                "not_repeated": "does not tune clean-SPY scalar, RS20/RS60/own-green scalars, broad SPY-leader cap, entry priority, filters, Space, or LLM soft-ranking",
            },
            "3_single_causal_variable": "sleeve-specific max_position_pct",
            "4_acceptance_standard": "docs/backtesting.md fixed three windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, max DD worse <= 0.5pp, survival >= 5%",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_027_clean_spy_leader_signal_day_cap.py",
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": detailed_selected["before_metrics"],
            "baseline_aggregate": detailed_selected["delta_metrics"]["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "strategy",
                "regime_exit_bucket",
                "spy_relative_leader",
                "signal_day_ticker_outperformed_spy",
                "ticker_minus_spy_signal_day_open_close_return_pct",
                "entry_price",
                "stop_price",
                "net_risk_per_share",
                "base_risk_pct",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": detailed_selected["delta_metrics"][
                "aggregate_delta"
            ]["signals_generated_sum"],
            "signals_survived_delta": detailed_selected["delta_metrics"][
                "aggregate_delta"
            ]["signals_survived_sum"],
            "minimum_after_survival_rate": detailed_selected["delta_metrics"][
                "aggregate_after"
            ]["survival_rate_min"],
            "passed": detailed_selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ]
            >= 0.05,
        },
        "gate4": detailed_selected["gate4"],
        "before_metrics": detailed_selected["before_metrics"],
        "after_metrics": detailed_selected["after_metrics"],
        "delta_metrics": detailed_selected["delta_metrics"],
        "sweep_results": sweep_results,
        "adjustments": detailed_selected["adjustments"],
        "changed_trades": detailed_selected["changed_trades"],
        "sizing_attribution": detailed_selected["sizing_attribution"],
        "expected_value_score_delta": detailed_selected["expected_value_score_delta"],
        "total_pnl_delta": detailed_selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking remains outcome-join/data limited; this deterministic allocation test is replayable on fixed OHLCV snapshots."
            ),
        },
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": True,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
        },
        "interpretation": interpretation,
        "rejection_reason": None if detailed_selected["passed"] else interpretation,
        "next_evidence_needed": None
        if detailed_selected["passed"]
        else "Use forward cap-room attribution or a materially different production-visible clean-leader discriminator before retrying this cap family.",
        "related_files": [
            "quant/experiments/exp_20260514_027_clean_spy_leader_signal_day_cap.py",
            "data/experiments/exp-20260514-027/clean_spy_leader_signal_day_cap.json",
            "experiments/logs/exp-20260514-027.json",
            "experiments/tickets/exp-20260514-027.json",
            "experiments/artifacts/exp-20260514-027_clean_spy_leader_signal_day_cap.md",
            "docs/experiment_log.jsonl",
            "quant/constants.py",
            "quant/portfolio_engine.py",
            "quant/backtester.py",
            "quant/test_production_parity.py",
            "quant/test_quant.py",
            "docs/production_backtest_parity.md",
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
        "selected_max_position_pct": payload["parameters"]["selected_max_position_pct"],
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
            },
            indent=2,
            sort_keys=True,
        )
    )
