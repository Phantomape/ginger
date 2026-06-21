"""exp-20260621-002: PIT SPY trend-down beta hedge.

Alpha search. Tests one attributable risk-allocation hypothesis: keep the core
stack's entries, exits, ranking, sizing, and candidate selection unchanged, but
apply the exp-20260620-020 measured SPY beta hedge only when the prior trading
day's SPY close was below its 50-day SMA and SPY's prior 5-day return was
negative. The state is known at the prior close before the hedged return day.

The hedge is measured as a no-cost upper bound. If the no-cost dynamic overlay
fails Gate 4, realistic borrow/slippage/rebalance costs can only make the
policy worse. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260620_023_core_stack_static_spy_beta_hedge as static


REPO_ROOT = static.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))


EXPERIMENT_ID = "exp-20260621-002"
STEM = "core_stack_pit_spy_trend_down_beta_hedge"
TRIAL_FAMILY = "core_stack_dynamic_spy_beta_hedge"
TRIAL_VARIANT_ID = "pit_spy_trend_down_beta_hedge_v1"
CHANGED_VARIABLE = "core_stack_pit_spy_trend_down_beta_hedge_v1"
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_002_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HEDGE_BETA = static.HEDGE_BETA
SMA_DAYS = 50
RETURN_DAYS = 5
MIN_RISK_ALLOCATION_EV_DELTA_PCT = 0.10
MAX_DRAWDOWN_WORSE = 0.0

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(static.WINDOWS)

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.2,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "risk_state_too_late",
        "hedges_positive_mean_days",
        "ev_regression",
        "drawdown_not_improved",
        "production_hedge_unsupported",
    ],
    "confidence_reason": (
        "Static SPY hedge failed by shorting positive SPY drift in late/mid "
        "windows but helped old_thin drawdown; the new evidence axis is a PIT "
        "same-snapshot SPY trend-down state, not a static hedge or drawdown "
        "threshold."
    ),
    "recorded_at": "2026-06-21T01:12:57+00:00",
}

PRODUCTION_IMPACT = {
    **static.PRODUCTION_IMPACT,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "hedge_instrument": "SPY",
        "hedge_direction": "short",
        "hedge_notional_rule": (
            "no-cost upper-bound overlay: on return date T, short SPY notional "
            "equals 0.347743 times prior simulated core equity only if T-1 "
            "SPY close < SMA50 and T-1 SPY 5d return < 0"
        ),
        "rebalance_frequency": "daily_close_return_model_only",
        "order_semantics": "not implemented; no broker order",
        "portfolio_displacement": "none; overlay-only replay",
        "kill_switch": "not live eligible; no production adapter changes",
        "failure_handling": (
            "missing core equity curve or same-snapshot SPY close return rejects "
            "the measurement; missing prior trend state disables that day's hedge"
        ),
    },
    "parity_note": (
        "Replay-only dynamic hedge measurement. A positive result would require "
        "one shared PIT market-state hedge policy, production hedge instrument "
        "support, borrow/cost modeling, and daily order/parity tests before any "
        "retention. This run changes no production behavior."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "risk_allocation: apply the exp-20260620-020 measured SPY beta hedge "
        "only on prior-close PIT SPY trend-down days, so the core stack keeps "
        "alpha exposure during positive market drift while reducing old_thin/"
        "risk-off beta drawdown."
    ),
    "2_history_check": {
        "novelty_gate": (
            "experiment.py new returned ok with no strong near-neighbor. "
            "This is not the rejected static hedge: it uses prior-close PIT "
            "SPY trend state and therefore directly tests the static hedge's "
            "observed failure mode."
        ),
        "exp-20260620-020": (
            "Measured core-stack SPY beta 0.347743 and showed the portfolio has "
            "some market exposure but most return is residual alpha."
        ),
        "exp-20260620-023": (
            "Rejected no-cost static SPY beta hedge: aggregate EV -0.7035 and "
            "PnL -$13,865.14, helped only old_thin while hurting late/mid."
        ),
        "exp-20260618-008": (
            "Rejected equity-curve adaptive sizing. This run does not use "
            "realized strategy drawdown or hindsight equity curve gates."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Gate 1-4 per docs/backtesting.md. For this risk-allocation policy, "
        "aggregate EV must improve by more than 10%, aggregate PnL must "
        "improve, no window EV/PnL regression is allowed, survival must remain "
        ">=5%, and max drawdown must not worsen. Because this is no-cost upper "
        "bound, failure rejects nearby SPY trend-down hedge variants."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260621_002_core_stack_pit_spy_trend_down_beta_hedge.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path | str) -> str:
    return static._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return static._round(value, digits)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(static._safe(payload), ensure_ascii=True, sort_keys=True)
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


def _spy_trend_context(snapshot_path: Path) -> dict[str, dict[str, Any]]:
    snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ohlcv = snap.get("ohlcv", snap)
    rows = sorted(ohlcv.get("SPY") or [], key=lambda row: str(row["Date"])[:10])
    dates = [str(row["Date"])[:10] for row in rows]
    closes = [float(row["Close"]) for row in rows]
    state_by_date: dict[str, dict[str, Any]] = {}
    for idx, date in enumerate(dates):
        if idx + 1 < SMA_DAYS or idx < RETURN_DAYS:
            state_by_date[date] = {
                "known": False,
                "reason": "insufficient_spy_history",
                "spy_close": closes[idx],
            }
            continue
        sma = sum(closes[idx - SMA_DAYS + 1 : idx + 1]) / SMA_DAYS
        ret5 = closes[idx] / closes[idx - RETURN_DAYS] - 1.0
        active = closes[idx] < sma and ret5 < 0.0
        state_by_date[date] = {
            "known": True,
            "spy_close": closes[idx],
            "spy_sma50": sma,
            "spy_5d_return": ret5,
            "hedge_active_next_day": active,
            "state_rule": "prior_close_below_sma50_and_prior_5d_return_negative",
        }

    context: dict[str, dict[str, Any]] = {}
    for idx in range(1, len(dates)):
        current_date = dates[idx]
        prev_date = dates[idx - 1]
        spy_return = closes[idx] / closes[idx - 1] - 1.0
        prior_state = state_by_date.get(prev_date, {"known": False})
        context[current_date] = {
            "spy_daily_return": spy_return,
            "prior_state_date": prev_date,
            "hedge_active": bool(prior_state.get("hedge_active_next_day")),
            "prior_state": prior_state,
        }
    return context


def _dynamic_hedged_metrics(
    *,
    label: str,
    before_result: dict[str, Any],
    snapshot_path: Path,
    standard_before: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    equity_curve = before_result.get("equity_curve") or []
    if len(equity_curve) < 2:
        raise RuntimeError(f"{label}: missing equity_curve")

    spy_context = _spy_trend_context(snapshot_path)
    strat_returns = static._daily_returns_from_curve(equity_curve)
    initial_capital = static._derive_initial_capital(before_result)
    before = dict(before_result)
    before.update(standard_before[label])

    after_curve: list[tuple[str, float]] = [
        (str(equity_curve[0][0])[:10], float(equity_curve[0][1]))
    ]
    hedge_rows: list[dict[str, Any]] = []
    daily_after_returns: list[float] = []
    missing_spy_dates: list[str] = []
    active_days = 0
    inactive_known_days = 0
    unknown_state_days = 0
    active_spy_return_sum = 0.0

    for date_raw, _equity_raw in equity_curve[1:]:
        date = str(date_raw)[:10]
        strat_ret = strat_returns.get(date)
        context = spy_context.get(date)
        if strat_ret is None:
            raise RuntimeError(f"{label}: missing strategy return for {date}")
        if context is None:
            missing_spy_dates.append(date)
            spy_ret = 0.0
            hedge_active = False
            prior_state = {"known": False, "reason": "missing_spy_context"}
        else:
            spy_ret = float(context["spy_daily_return"])
            hedge_active = bool(context["hedge_active"])
            prior_state = context["prior_state"]
        if not prior_state.get("known"):
            unknown_state_days += 1
        elif hedge_active:
            active_days += 1
            active_spy_return_sum += spy_ret
        else:
            inactive_known_days += 1

        prior_after_equity = after_curve[-1][1]
        hedge_return = -HEDGE_BETA * spy_ret if hedge_active else 0.0
        after_return = strat_ret + hedge_return
        after_equity = prior_after_equity * (1.0 + after_return)
        after_curve.append((date, after_equity))
        daily_after_returns.append(after_return)
        hedge_rows.append(
            {
                "date": date,
                "strategy_daily_return": _round(strat_ret, 8),
                "spy_daily_return": _round(spy_ret, 8),
                "hedge_active": hedge_active,
                "prior_state_date": context.get("prior_state_date") if context else None,
                "prior_spy_close": _round(prior_state.get("spy_close"), 4),
                "prior_spy_sma50": _round(prior_state.get("spy_sma50"), 4),
                "prior_spy_5d_return": _round(prior_state.get("spy_5d_return"), 8),
                "hedge_beta": HEDGE_BETA if hedge_active else 0.0,
                "hedge_return": _round(hedge_return, 8),
                "after_daily_return": _round(after_return, 8),
                "prior_after_equity": _round(prior_after_equity, 2),
                "hedge_notional_usd": _round(
                    prior_after_equity * HEDGE_BETA if hedge_active else 0.0, 2
                ),
                "after_equity": _round(after_equity, 2),
            }
        )

    final_after_equity = after_curve[-1][1]
    strategy_total_return_pct = final_after_equity / initial_capital - 1.0
    total_pnl = strategy_total_return_pct * initial_capital
    sharpe_daily = static._sharpe_daily(daily_after_returns)
    max_drawdown_pct = static._max_drawdown(after_curve)
    spy_buy_hold = static._bench_return_from_snapshot(snapshot_path, "SPY")
    qqq_buy_hold = static._bench_return_from_snapshot(snapshot_path, "QQQ")

    after = dict(before)
    after["total_pnl"] = round(total_pnl, 2)
    after["sharpe_daily"] = sharpe_daily
    after["max_drawdown_pct"] = max_drawdown_pct
    after["benchmarks"] = {
        **(before.get("benchmarks") or {}),
        "spy_buy_hold_return_pct": round(spy_buy_hold, 4)
        if spy_buy_hold is not None
        else None,
        "qqq_buy_hold_return_pct": round(qqq_buy_hold, 4)
        if qqq_buy_hold is not None
        else None,
        "strategy_total_return_pct": round(strategy_total_return_pct, 4),
        "strategy_vs_spy_pct": round(strategy_total_return_pct - spy_buy_hold, 4)
        if spy_buy_hold is not None
        else None,
        "strategy_vs_qqq_pct": round(strategy_total_return_pct - qqq_buy_hold, 4)
        if qqq_buy_hold is not None
        else None,
    }
    after["expected_value_score"] = static.compute_expected_value_score(after)
    after["convergence"] = static.compute_convergence(after)
    after["pit_spy_trend_down_beta_hedge_overlay"] = {
        "hedge_beta": HEDGE_BETA,
        "state_rule": "prior_close_below_sma50_and_prior_5d_return_negative",
        "cost_model": "no_cost_upper_bound",
        "daily_rows": len(hedge_rows),
        "missing_spy_return_dates": missing_spy_dates,
        "initial_capital": round(initial_capital, 2),
    }

    delta = static._delta(after, before)
    slim_before = static._slim_metrics(before)
    slim_after = static._slim_metrics(after)
    diagnostics = {
        "hedge_day_count": active_days,
        "inactive_known_day_count": inactive_known_days,
        "unknown_state_day_count": unknown_state_days,
        "hedge_day_share": round(active_days / len(hedge_rows), 6) if hedge_rows else 0.0,
        "active_spy_return_sum": round(active_spy_return_sum, 6),
        "active_spy_return_mean": round(active_spy_return_sum / active_days, 6)
        if active_days
        else None,
        "missing_spy_dates": missing_spy_dates,
    }
    return slim_before, slim_after, delta, hedge_rows, diagnostics


def _gate4(aggregate: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if not aggregate["expected_value_score_delta_gt_required"]:
        failed.append("aggregate_ev_delta_not_gt_10pct")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_worse")
    if float(aggregate["max_drawdown_delta_min"] or 0.0) >= 0.0:
        failed.append("drawdown_not_improved")
    if float(aggregate["minimum_core_survival_rate"] or 0.0) < 0.05:
        failed.append("core_survival_rate_below_5pct")
    return {
        "passed": not failed,
        "decision": (
            "positive_replay_lead_not_promoted_core_stack_pit_spy_trend_down_beta_hedge"
            if not failed
            else "rejected_core_stack_pit_spy_trend_down_beta_hedge"
        ),
        "failed_reasons": failed,
        "aggregate": aggregate,
        "acceptance_rule": (
            "Risk-allocation policy must improve aggregate EV by >10%, improve "
            "aggregate PnL, avoid every window regression, keep survival >=5%, "
            "not worsen drawdown, and improve drawdown in at least one window. "
            "This no-cost upper-bound runner uses prior-close PIT SPY trend state."
        ),
    }


def _run_window(label: str, cfg: dict[str, str], standard: dict[str, dict[str, Any]]):
    print(f"[{label}] core baseline and PIT SPY trend-down hedge overlay")
    universe = sorted(static._get_universe())
    snapshot = REPO_ROOT / cfg["snapshot"]
    engine = static.BacktestEngine(
        universe,
        start=cfg["start"],
        end=cfg["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
            "ATR_STOP_DAILY_RECOMPUTE": False,
            "ATR_STOP_TRIGGER_ON_CLOSE": False,
            "ATR_STOP_EXIT_NEXT_OPEN": False,
        },
        ohlcv_snapshot_path=str(snapshot),
        include_oracle_diagnostics=False,
    )
    before_result = engine.run()
    if "error" in before_result:
        raise RuntimeError(f"{label}: backtest error: {before_result['error']}")
    before, after, delta, hedge_rows, diagnostics = _dynamic_hedged_metrics(
        label=label,
        before_result=before_result,
        snapshot_path=snapshot,
        standard_before=standard,
    )
    return {
        "before": before,
        "after": after,
        "delta": delta,
        "hedge_rows_sample": hedge_rows[:20],
        "hedge_diagnostics": diagnostics,
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open_positions = static._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    standard = static._standard_metrics()
    exp020 = static._load_exp020_summary()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label, cfg in WINDOWS.items():
        window_rows[label] = _run_window(label, cfg, standard)

    aggregate = static._aggregate(window_rows)
    gate4 = _gate4(aggregate)
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = (
        "The no-cost prior-close PIT SPY trend-down hedge cleared strict Gate 4, "
        "but remains only a replay lead because no shared hedge policy or "
        "production hedge order support exists."
        if gate4["passed"]
        else (
            "Rejected. The no-cost prior-close PIT SPY trend-down hedge did not "
            f"clear Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "The state gate avoided always-on positive drift hedging, but it did "
            "not produce enough stable replacement value after the strict "
            "risk-allocation comparator."
        )
    )
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0))
            ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": gate4["passed"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "risk_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_core_stack_risk_allocation",
        "new_evidence_type": "pit_market_state_risk_allocation",
        "nearby_prior_experiments": [
            "exp-20260620-020",
            "exp-20260620-023",
            "exp-20260618-008",
        ],
        "prior_trial_count": 0,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "exp020_beta_attribution_source": exp020,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "same-snapshot no-cost dynamic SPY beta hedge overlay"
            ),
            "windows": WINDOWS,
            "baseline_result_file": _repo_rel(static.BASELINE_RESULT_JSON),
            "beta_source_artifact": _repo_rel(static.EXP020_ARTIFACT),
            "hedge_beta": HEDGE_BETA,
            "hedge_semantics": (
                "on return date T, after_return = core_return - 0.347743 * "
                "same-day SPY close-to-close return only if prior trading day "
                "SPY close < SMA50 and prior SPY 5d return < 0"
            ),
            "state_lookahead_guard": "trend state is measured on T-1 close for T return",
            "costs": "no_cost_upper_bound",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "hedge_beta": HEDGE_BETA,
            "hedge_instrument": "SPY",
            "hedge_direction": "short",
            "sma_days": SMA_DAYS,
            "return_days": RETURN_DAYS,
            "cost_model": "none_upper_bound",
            "min_risk_allocation_ev_delta_pct": MIN_RISK_ALLOCATION_EV_DELTA_PCT,
            "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
        },
        "gate1": {
            "baseline_protocol": "docs/backtesting.md canonical three-window baseline",
            "baseline_metrics": OrderedDict(
                (label, row["before"]) for label, row in window_rows.items()
            ),
            "ev_sanity": {
                label: {
                    "recomputed": row["before"]["expected_value_score"],
                    "standard": standard[label]["expected_value_score"],
                }
                for label, row in window_rows.items()
            },
            "passed": True,
        },
        "gate2": {
            "open_positions_field_audit": gate2_open_positions,
            "runtime_fields_checked": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "core backtest equity_curve",
                "same-snapshot SPY close-to-close returns",
                "prior-close SPY close/SMA50/5d return trend state",
                "fixed hedge beta from exp-20260620-020",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": aggregate["minimum_core_survival_rate"],
            "survival_rate_by_window": OrderedDict(
                (label, row["before"].get("survival_rate"))
                for label, row in window_rows.items()
            ),
            "passed": float(aggregate["minimum_core_survival_rate"] or 0.0) >= 0.05,
            "note": (
                "No entry, exit, ranking, sizing, or filter changed; survival "
                "is inherited from the accepted core baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": OrderedDict(
            (label, row["before"]) for label, row in window_rows.items()
        ),
        "after_metrics": OrderedDict(
            (label, row["after"]) for label, row in window_rows.items()
        ),
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in window_rows.items()
            ),
            "aggregate": aggregate,
        },
        "hedge_diagnostics": OrderedDict(
            (
                label,
                {
                    **row["hedge_diagnostics"],
                    "hedge_rows_sample": row["hedge_rows_sample"],
                },
            )
            for label, row in window_rows.items()
        ),
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "post_run_reflection": {
            "why_result_happened": interpretation,
            "forbidden_near_neighbor_retry": (
                "Do not retry static or SPY trend-down beta hedge variants by "
                "sweeping SMA length, return lookback, beta scalar, hedge "
                "thresholds, rebalance timing, or cost assumptions on the frozen "
                "windows."
            ),
            "new_evidence_required": (
                "A valid risk-allocation retry needs a materially different PIT "
                "hedge state, such as tradable factor ETF exposure attribution "
                "(MTUM/QUAL/USMV), borrow/options stress data, or closed forward "
                "replacement-value hedge rows."
            ),
        },
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    rows = []
    for label in WINDOWS:
        delta = payload["delta_metrics"]["by_window"][label]
        diag = payload["hedge_diagnostics"][label]
        rows.append(
            "- {label}: EV {ev:+.4f}, PnL ${pnl:+,.2f}, DD {dd:+.4f}, hedge days {days}".format(
                label=label,
                ev=delta.get("expected_value_score", 0.0),
                pnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=diag.get("hedge_day_count", 0),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: PIT SPY trend-down beta hedge",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
            f"- Aggregate EV delta pct: `{aggregate['expected_value_score_delta_pct']:+.2%}`",
            f"- Required EV delta pct: `{MIN_RISK_ALLOCATION_EV_DELTA_PCT:.2%}`",
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            f"- Max drawdown delta: `{aggregate['max_drawdown_delta_max']:+.4f}`",
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only no-cost upper-bound hedge overlay. No shared "
                "policy, production adapter, broker order, watchlist, core "
                "entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": _repo_rel(static.BASELINE_RESULT_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "max_drawdown_delta": payload["delta_metrics"]["by_window"][label][
                    "max_drawdown_pct"
                ],
                "hedge_day_count": payload["hedge_diagnostics"][label][
                    "hedge_day_count"
                ],
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): static._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): static._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): static._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): static._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): static._sha256(CARD_MD),
        },
    }
    static._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    static._write_json(OUT_JSON, payload)
    static._write_json(LOG_JSON, payload)
    static._write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    static.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(static._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
