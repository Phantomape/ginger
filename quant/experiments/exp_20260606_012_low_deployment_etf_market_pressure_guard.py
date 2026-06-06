"""exp-20260606-012: low-deployment ETF market-pressure guard.

Alpha-search replay only. This tests one production-visible risk boundary for
the accepted default-off low-deployment ETF cash substitute: do not open a new
equity ETF paper entry when SPY or QQQ is simultaneously in high 20-day
realized volatility, 20-day drawdown, and negative 5-day return pressure.

The ETF candidate set, trend/momentum selector, next-open entry, 10-trading-day
close exit, notional, core strategy, LLM/news paths, and live order behavior are
locked. GLD/SLV candidates are not blocked by this equity pressure guard. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import exp_20260606_011_low_deployment_etf_loss_streak_kill_switch as scaffold
from data_layer import get_universe
from low_deployment_etf_overlay import (
    _core_active_count_by_date,
    _core_deployment_context,
    _normalise_ohlcv_rows,
    _replay_trade_from_candidate,
    _select_candidate,
    replay_low_deployment_etf_cash_substitute_trades,
)


base = scaffold.base
shadow = scaffold.shadow
overlay_helper = scaffold.overlay_helper
sleeve = scaffold.sleeve

EXPERIMENT_ID = "exp-20260606-012"
STEM = "low_deployment_etf_market_pressure_guard"
TRIAL_FAMILY = "low_deployment_etf_cash_substitute_market_pressure_guard"
TRIAL_VARIANT_ID = "low_deployment_etf_market_pressure_volatility_guard_v1"
CHANGED_VARIABLE = "low_deployment_etf_market_pressure_volatility_guard_v1"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_012_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"exp_20260606_012_{STEM}_aggregate_before.json"
AFTER_JSON = OUT_DIR / f"exp_20260606_012_{STEM}_aggregate_after.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

PRESSURE_LOOKBACK_DAYS = 20
PRESSURE_RET_DAYS = 5
PRESSURE_MIN_VOL20 = 0.018
PRESSURE_MIN_DRAWDOWN20 = -0.035
PRESSURE_MIN_RET5 = -0.01
PRESSURE_INDEX_TICKERS = ("SPY", "QQQ")
EQUITY_ETF_TICKERS = {"QQQ", "SPY", "IWM"}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_etf_comparator_not_beaten",
        "window_regression",
        "profitable_stress_entries_cut",
        "trade_count_too_low",
    ],
    "confidence_reason": (
        "The playbook calls for activation risk controls around the accepted "
        "low-deployment ETF adapter, but nearby loss-streak and older "
        "volatility-cap attempts warn that simple guards can cut profitable "
        "recovery exposure."
    ),
    "recorded_at": "2026-06-06T10:05:57Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "experiment_only_default_off_paper_market_pressure_guard_candidate",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "No production code is changed in this experiment. If the fixed "
        "market-pressure rule were positive, promotion would require adding "
        "the same SPY/QQQ pressure guard to the shared default-off "
        "low_deployment_etf_overlay helper and replay parity tests before any "
        "production-visible retention."
    ),
}


def _repo_rel(path: Path | str) -> str:
    return scaffold._repo_rel(path)


def _safe(payload: Any) -> Any:
    return scaffold._safe(payload)


def _round(value: Any, digits: int = 6) -> float | None:
    return scaffold._round(value, digits)


def _write_json(path: Path, payload: Any) -> None:
    scaffold._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    scaffold._write_text(path, text)


def _sha256(path: Path) -> str | None:
    return scaffold._sha256(path)


def _overlay_config() -> dict[str, Any]:
    return scaffold._overlay_config()


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
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


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def _pressure_for_index(rows: list[dict[str, Any]], as_of: str) -> dict[str, Any]:
    date_to_index = {str(row.get("date"))[:10]: idx for idx, row in enumerate(rows)}
    idx = date_to_index.get(str(as_of)[:10])
    if idx is None:
        return {"available": False, "reason": "missing_as_of_date"}
    if idx < PRESSURE_LOOKBACK_DAYS or idx < PRESSURE_RET_DAYS:
        return {"available": False, "reason": "insufficient_history"}

    closes = [_positive_float(row.get("close")) for row in rows]
    if closes[idx] is None:
        return {"available": False, "reason": "missing_signal_close"}

    returns: list[float] = []
    for ret_idx in range(idx - PRESSURE_LOOKBACK_DAYS + 1, idx + 1):
        prior_close = closes[ret_idx - 1]
        current_close = closes[ret_idx]
        if prior_close is None or current_close is None:
            return {"available": False, "reason": "missing_vol_window_close"}
        returns.append(float(current_close) / float(prior_close) - 1.0)
    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / len(returns)
    vol20 = math.sqrt(variance)

    drawdown_window = closes[idx - PRESSURE_LOOKBACK_DAYS + 1 : idx + 1]
    if any(value is None for value in drawdown_window):
        return {"available": False, "reason": "missing_drawdown_window_close"}
    peak_close = max(float(value) for value in drawdown_window if value is not None)
    drawdown20 = float(closes[idx]) / peak_close - 1.0

    ret_base = closes[idx - PRESSURE_RET_DAYS]
    if ret_base is None:
        return {"available": False, "reason": "missing_ret5_base_close"}
    ret5 = float(closes[idx]) / float(ret_base) - 1.0

    pressure = (
        vol20 >= PRESSURE_MIN_VOL20
        and drawdown20 <= PRESSURE_MIN_DRAWDOWN20
        and ret5 <= PRESSURE_MIN_RET5
    )
    return {
        "available": True,
        "pressure": pressure,
        "vol20": _round(vol20, 6),
        "drawdown20": _round(drawdown20, 6),
        "ret5": _round(ret5, 6),
        "thresholds": {
            "vol20_min": PRESSURE_MIN_VOL20,
            "drawdown20_max": PRESSURE_MIN_DRAWDOWN20,
            "ret5_max": PRESSURE_MIN_RET5,
        },
    }


def _market_pressure_state(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
) -> dict[str, Any]:
    by_index = {
        ticker: _pressure_for_index(rows_by_ticker.get(ticker) or [], as_of)
        for ticker in PRESSURE_INDEX_TICKERS
    }
    active_tickers = [
        ticker
        for ticker, state in by_index.items()
        if bool(state.get("available")) and bool(state.get("pressure"))
    ]
    return {
        "as_of": str(as_of)[:10],
        "active": bool(active_tickers),
        "active_tickers": active_tickers,
        "by_index": by_index,
    }


def _variant_overlay_trades(
    before_result: dict[str, Any],
    snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _overlay_config()
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(snapshot.get(ticker))
        for ticker in cfg["candidate_tickers"]
    }
    core_counts = _core_active_count_by_date(before_result)
    equity_dates = [str(day)[:10] for day, _ in before_result.get("equity_curve") or []]

    open_trades: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    guard_events: list[dict[str, Any]] = []
    low_deployment_day_count = 0
    selectable_day_count = 0
    market_pressure_day_count = 0

    for signal_date in equity_dates:
        open_trades = [
            trade for trade in open_trades if str(trade.get("exit_date") or "") > signal_date
        ]
        active_core_positions = int(core_counts.get(signal_date, 0))
        context = _core_deployment_context(active_core_positions, cfg)
        if not context["low_deployment_condition_passed"]:
            skipped["core_above_low_deployment_threshold"] += 1
            continue
        low_deployment_day_count += 1
        if len(open_trades) >= int(cfg["max_overlay_open_positions"]):
            skipped["overlay_position_cap_full"] += 1
            continue

        selection = _select_candidate(
            rows_by_ticker,
            as_of=signal_date,
            active_core_positions=active_core_positions,
            core_deployment_context=context,
            config=cfg,
        )
        if selection is None:
            skipped["no_etf_passing_signal_close_state"] += 1
            continue
        selectable_day_count += 1

        pressure_state = _market_pressure_state(rows_by_ticker, signal_date)
        if pressure_state["active"]:
            market_pressure_day_count += 1
        selected_ticker = str(selection.get("ticker") or "").upper()
        if pressure_state["active"] and selected_ticker in EQUITY_ETF_TICKERS:
            skipped["market_pressure_equity_etf_guard"] += 1
            guard_events.append(
                {
                    "signal_date": signal_date,
                    "selected_ticker": selected_ticker,
                    "selection": {
                        "prior_momentum20": selection.get("prior_momentum20"),
                        "prior_sma200": selection.get("prior_sma200"),
                        "signal_close": selection.get("signal_close"),
                    },
                    "market_pressure_state": pressure_state,
                }
            )
            continue

        trade = _replay_trade_from_candidate(
            rows_by_ticker=rows_by_ticker,
            candidate=selection,
            config=cfg,
        )
        if trade is None:
            skipped["missing_entry_or_exit_price"] += 1
            continue
        trade["source"] = STEM
        trade["market_pressure_guard"] = {
            "enabled": True,
            "blocked_equity_tickers": sorted(EQUITY_ETF_TICKERS),
            "pressure_index_tickers": list(PRESSURE_INDEX_TICKERS),
            "pressure_state_on_signal": pressure_state,
            "thresholds": {
                "lookback_days": PRESSURE_LOOKBACK_DAYS,
                "ret_days": PRESSURE_RET_DAYS,
                "vol20_min": PRESSURE_MIN_VOL20,
                "drawdown20_max": PRESSURE_MIN_DRAWDOWN20,
                "ret5_max": PRESSURE_MIN_RET5,
            },
        }
        trades.append(trade)
        open_trades.append(trade)

    return trades, {
        "low_deployment_day_count": low_deployment_day_count,
        "selectable_day_count_before_guard": selectable_day_count,
        "market_pressure_day_count_after_selection": market_pressure_day_count,
        "skipped": dict(skipped),
        "guard_events": guard_events,
        "pressure_index_tickers": list(PRESSURE_INDEX_TICKERS),
        "equity_etf_tickers_guarded": sorted(EQUITY_ETF_TICKERS),
        "thresholds": {
            "lookback_days": PRESSURE_LOOKBACK_DAYS,
            "ret_days": PRESSURE_RET_DAYS,
            "vol20_min": PRESSURE_MIN_VOL20,
            "drawdown20_max": PRESSURE_MIN_DRAWDOWN20,
            "ret5_max": PRESSURE_MIN_RET5,
        },
        "max_active_core_positions": int(cfg["max_active_core_positions"]),
        "max_overlay_open_positions": int(cfg["max_overlay_open_positions"]),
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return scaffold._aggregate(rows)


def _concentration(trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return scaffold._concentration(trades_by_window)


def _gate(
    *,
    aggregate: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive_vs_accepted_etf")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive_vs_accepted_etf")
    if int(aggregate["windows_ev_regressed_vs_accepted"] or 0) > 0:
        failed.append("window_ev_regression_vs_accepted_etf")
    if int(aggregate["windows_pnl_regressed_vs_accepted"] or 0) > 0:
        failed.append("window_pnl_regression_vs_accepted_etf")
    if int(aggregate["target_trade_count_sum"] or 0) < base.MIN_TARGET_TRADES:
        failed.append("target_trade_count_too_small")
    if len(aggregate["target_windows"]) < base.MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if int(aggregate.get("guarded_entry_count_sum") or 0) <= 0:
        failed.append("no_signal_coverage")
    if float(aggregate["max_drawdown_delta_max_vs_accepted"] or 0.0) > 0.0:
        failed.append("drawdown_worse_vs_accepted_etf")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration["passed"]:
        failed.append("positive_pnl_concentration_failed")
    return {
        "passed": not failed,
        "failed_reasons": failed,
        "minimum_core_survival_rate": _round(min_survival, 6),
        "aggregate": aggregate,
        "concentration": concentration,
        "comparator": "exp-20260606-001 accepted shared low-deployment ETF adapter",
        "acceptance_rule": (
            "The fixed SPY/QQQ market-pressure guard must beat the accepted "
            "ETF adapter, not merely the core baseline: positive aggregate "
            "EV/PnL vs accepted, no window EV/PnL regression, no drawdown "
            "worsening, minimum target trades/window coverage, survival >=5%, "
            "and positive PnL concentration passing."
        ),
    }


def _build_payload() -> dict[str, Any]:
    timestamp = base._utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    variant_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    accepted_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    diagnostics_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] accepted ETF comparator and market-pressure guard replay")
        before_result = shadow._run_baseline(universe, cfg)
        core_before = overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])

        accepted_trades, accepted_diagnostics = replay_low_deployment_etf_cash_substitute_trades(
            core_backtest_result=before_result,
            ohlcv_by_ticker=snapshot,
            config=_overlay_config(),
        )
        accepted_overlay = sleeve._overlay_from_paper_trades(before_result, accepted_trades)
        accepted_after = overlay_helper._metrics_with_overlay(before_result, accepted_overlay)

        variant_trades, variant_diagnostics = _variant_overlay_trades(before_result, snapshot)
        variant_overlay = sleeve._overlay_from_paper_trades(before_result, variant_trades)
        variant_after = overlay_helper._metrics_with_overlay(before_result, variant_overlay)

        before_metrics[label] = core_before
        accepted_trades_by_window[label] = accepted_trades
        variant_trades_by_window[label] = variant_trades
        diagnostics_by_window[label] = {
            "accepted": accepted_diagnostics,
            "variant": variant_diagnostics,
        }
        window_rows[label] = {
            "core_before": core_before,
            "accepted_after": accepted_after,
            "variant_after": variant_after,
            "accepted_delta_vs_core": overlay_helper._delta(accepted_after, core_before),
            "variant_delta_vs_core": overlay_helper._delta(variant_after, core_before),
            "delta_vs_accepted": overlay_helper._delta(variant_after, accepted_after),
            "accepted_target_trade_count": len(accepted_trades),
            "variant_target_trade_count": len(variant_trades),
            "accepted_ticker_trade_counts": dict(
                Counter(str(trade["ticker"]) for trade in accepted_trades)
            ),
            "variant_ticker_trade_counts": dict(
                Counter(str(trade["ticker"]) for trade in variant_trades)
            ),
            "accepted_overlay_total_pnl": accepted_overlay["overlay_total_pnl"],
            "variant_overlay_total_pnl": variant_overlay["overlay_total_pnl"],
            "accepted_trades_sample": accepted_trades[:20],
            "variant_trades_sample": variant_trades[:20],
            "diagnostics": diagnostics_by_window[label],
        }

    aggregate = _aggregate(window_rows)
    aggregate["guarded_entry_count_sum"] = sum(
        len(row["diagnostics"]["variant"]["guard_events"]) for row in window_rows.values()
    )
    concentration = _concentration(variant_trades_by_window)
    gate4 = _gate(
        aggregate=aggregate,
        before_metrics=before_metrics,
        concentration=concentration,
    )
    status = "accepted" if gate4["passed"] else "rejected"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": (
            "accepted_low_deployment_etf_market_pressure_guard"
            if gate4["passed"]
            else "rejected_low_deployment_etf_market_pressure_guard"
        ),
        "hypothesis": (
            "The accepted default-off low-deployment ETF cash substitute may "
            "be activation-safer if new equity ETF paper entries are skipped "
            "only when SPY or QQQ is in a fixed high-volatility drawdown "
            "pressure state. GLD/SLV safe-haven candidates remain eligible."
        ),
        "change_type": "default_off_paper_risk_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": {
            "exp-20260606-001": (
                "Accepted shared default-off ETF adapter: aggregate EV 7.8941 "
                "-> 10.9233, PnL $234,850.99 -> $279,157.90, all three "
                "windows improved, default-off and no live orders."
            ),
            "exp-20260606-011": (
                "Rejected low-deployment ETF prior-loss-streak kill switch; "
                "it cut profitable recovery exposure and did not beat the "
                "accepted ETF comparator."
            ),
            "exp-20260522-004": (
                "Rejected older low-deployment ETF volatility cap; this test "
                "uses market-index pressure, not selected ETF realized-vol caps."
            ),
            "exp-20260605-028": (
                "Forward readiness audit found low_deployment_etf closest to "
                "activation but still blocked by closed sample and concentration."
            ),
        },
        "multiple_testing_risk_bucket": "medium",
        "new_evidence_type": "production_visible_market_pressure_guard_on_accepted_adapter",
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": gate4["passed"],
            "failure_modes_observed": gate4["failed_reasons"],
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "comparator": "exp-20260606-001 accepted shared ETF adapter",
            "REGIME_AWARE_EXIT": True,
            "replay_llm": False,
            "replay_news": False,
        },
        "parameters": {
            "pressure_index_tickers": list(PRESSURE_INDEX_TICKERS),
            "equity_etf_tickers_guarded": sorted(EQUITY_ETF_TICKERS),
            "pressure_lookback_days": PRESSURE_LOOKBACK_DAYS,
            "pressure_ret_days": PRESSURE_RET_DAYS,
            "pressure_min_vol20": PRESSURE_MIN_VOL20,
            "pressure_min_drawdown20": PRESSURE_MIN_DRAWDOWN20,
            "pressure_min_ret5": PRESSURE_MIN_RET5,
            "base_notional_usd": base.BASE_NOTIONAL_USD,
            "hold_days": base.HOLD_DAYS,
            "max_active_core_positions": base.MAX_ACTIVE_CORE_POSITIONS,
            "max_overlay_open_positions": base.MAX_OVERLAY_OPEN_POSITIONS,
            "state_sma_days": base.STATE_SMA_DAYS,
            "state_momentum_days": base.STATE_MOMENTUM_DAYS,
            "overlay_candidates": base.OVERLAY_CANDIDATES,
            "locked_variables": [
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "ETF candidate set",
                "prior-close 20d momentum ranking",
                "positive 200d trend gate",
                "positive 20d momentum gate",
                "low-deployment threshold",
                "paper notional",
                "hold days",
                "one-open-position cap",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / capital allocation: add a fixed "
                "production-visible SPY/QQQ pressure guard to the accepted "
                "default-off ETF cash substitute so low-deployment replacement "
                "value does not add new equity ETF risk during acute broad "
                "market pressure."
            ),
            "2_history_check": {
                "exp-20260606-001": "Accepted ETF comparator and current strongest lead.",
                "exp-20260606-011": "Rejected prior-loss-streak kill switch.",
                "exp-20260522-004": "Rejected ETF volatility-cap variant.",
                "exp-20260605-028": "Forward readiness audit; activation remains blocked.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three standard windows; compare against the accepted ETF "
                "adapter. The guard must improve aggregate EV and PnL, avoid "
                "all window EV/PnL regressions, avoid drawdown worsening, "
                "retain enough trades/window coverage, pass survival and "
                "concentration checks."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260606_012_low_deployment_etf_market_pressure_guard.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "accepted_etf_comparator_metrics": {
                label: row["accepted_after"] for label, row in window_rows.items()
            },
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "core baseline trades entry_date",
                "core baseline trades exit_date",
                "ETF Date/Open/Close OHLCV",
                "SPY Date/Close OHLCV",
                "QQQ Date/Close OHLCV",
                "baseline equity_curve dates",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
            >= 0.05,
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "window_metrics": window_rows,
        "accepted_trades_by_window": accepted_trades_by_window,
        "variant_trades_by_window": variant_trades_by_window,
        "diagnostics_by_window": diagnostics_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The fixed market-pressure guard beat the accepted ETF adapter and "
            "should only be retained after shared-helper promotion and parity "
            "tests."
            if gate4["passed"]
            else "The fixed market-pressure guard did not beat the accepted ETF adapter."
        ),
        "negative_reflection": (
            "If rejected with no_signal_coverage, the fixed pressure guard did "
            "not overlap any accepted ETF paper entry in the three canonical "
            "windows, so it cannot express alpha under the current replay "
            "surface. If a looser version is considered, it must come from new "
            "forward replacement rows or a materially different free data edge; "
            "do not retune SPY/QQQ pressure thresholds on the same frozen "
            "windows."
        ),
        "next_evidence_needed": (
            "Use forward replacement rows, cash/core-capacity context, or a "
            "new free data edge to design activation controls; avoid further "
            "ETF threshold, hold, notional, or guard retunes without new evidence."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | dEV vs accepted | dPnL vs accepted | Accepted trades | Variant trades | Guarded entries |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        row = payload["window_metrics"][label]
        delta = row["delta_vs_accepted"]
        rows.append(
            f"| {label} | {delta.get('expected_value_score', 0.0):+.4f} | "
            f"${delta.get('total_pnl', 0.0):+,.2f} | "
            f"{row['accepted_target_trade_count']} | {row['variant_target_trade_count']} | "
            f"{len(row['diagnostics']['variant']['guard_events'])} |"
        )
    agg = payload["gate4"]["aggregate"]
    concentration = payload["gate4"]["concentration"]
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            'lane: "alpha_search"',
            'change_type: "default_off_paper_risk_allocation"',
            'mechanism_family: "low_deployment_etf_cash_substitute_market_pressure_guard"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            f'updated_at: "{payload["timestamp"]}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "## Three-Window Comparator Deltas",
            "",
            *rows,
            "",
            "## Aggregate Gate",
            "",
            f"- Comparator EV: `{agg['comparator_expected_value_score_sum']}`",
            f"- Variant EV: `{agg['after_expected_value_score_sum']}`",
            f"- EV delta vs accepted: `{agg['expected_value_score_delta_sum']}`",
            f"- PnL delta vs accepted: `${agg['total_pnl_delta_sum']}`",
            f"- Variant target trades: `{agg['target_trade_count_sum']}`",
            f"- Max drawdown delta vs accepted: `{agg['max_drawdown_delta_max_vs_accepted']}`",
            f"- Concentration: `{concentration}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(_safe(payload["gate4"]), indent=2, sort_keys=True),
            "```",
            "",
            "Replay-only/default-off; no production orders changed. No JavaScript was used.",
        ]
    ) + "\n"


def _build_artifact(payload: dict[str, Any]) -> str:
    agg = payload["gate4"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Low-Deployment ETF Market-Pressure Guard",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Preflight Answers",
        "",
        f"1. Hypothesis: {payload['gate_questions']['1_alpha_hypothesis']}",
        (
            "2. History: exp-20260606-001 accepted the shared ETF adapter; "
            "exp-20260606-011 rejected prior-loss-streak cooldown; "
            "exp-20260522-004 rejected ETF volatility cap; exp-20260605-028 "
            "found forward activation still blocked."
        ),
        f"3. Single variable: `{CHANGED_VARIABLE}`.",
        (
            "4. Acceptance: three canonical windows versus accepted ETF "
            "comparator; positive aggregate EV/PnL, no window regressions, "
            "no drawdown worsening, enough trades, survival/concentration pass."
        ),
        f"5. Reproduce: `{payload['gate_questions']['5_reproducibility']}`.",
        "",
        "## Aggregate vs Accepted ETF Comparator",
        "",
        f"- EV: `{agg['comparator_expected_value_score_sum']} -> "
        f"{agg['after_expected_value_score_sum']}` "
        f"({agg['expected_value_score_delta_sum']:+.4f})",
        f"- PnL: `${agg['comparator_total_pnl_sum']:,.2f} -> "
        f"${agg['after_total_pnl_sum']:,.2f}` "
        f"(${agg['total_pnl_delta_sum']:+,.2f})",
        f"- Variant trades: `{agg['target_trade_count_sum']}` "
        f"(accepted `{agg['accepted_trade_count_sum']}`)",
        f"- Max drawdown delta vs accepted: `{agg['max_drawdown_delta_max_vs_accepted']}`",
        "",
        "## Window Deltas",
        "",
        "| Window | EV delta | PnL delta | Accepted trades | Variant trades | Guarded entries |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in base.WINDOWS:
        row = payload["window_metrics"][label]
        delta = row["delta_vs_accepted"]
        lines.append(
            f"| `{label}` | {delta.get('expected_value_score', 0.0):+.4f} | "
            f"${delta.get('total_pnl', 0.0):+,.2f} | "
            f"{row['accepted_target_trade_count']} | {row['variant_target_trade_count']} | "
            f"{len(row['diagnostics']['variant']['guard_events'])} |"
        )
    lines.extend(
        [
            "",
            "## Production Boundary",
            "",
            "- Experiment-only, default-off paper replay; no production orders changed.",
            "- Positive retention would require shared-helper promotion and parity tests.",
            "- No JavaScript was used.",
            "",
            "## Reflection",
            "",
            payload["negative_reflection"]
            if payload["status"] == "rejected"
            else payload["interpretation"],
            "",
        ]
    )
    return "\n".join(lines)


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    aggregate = gate4["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": gate4["passed"],
        "mechanism_family": "low_deployment_etf_cash_substitute_market_pressure_guard",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": gate4,
        "windows": [
            {
                "label": label,
                "accepted_expected_value": payload["window_metrics"][label]["accepted_after"][
                    "expected_value_score"
                ],
                "variant_expected_value": payload["window_metrics"][label]["variant_after"][
                    "expected_value_score"
                ],
                "expected_value_delta_vs_accepted": payload["window_metrics"][label][
                    "delta_vs_accepted"
                ]["expected_value_score"],
                "strategy_total_pnl_delta_vs_accepted": payload["window_metrics"][label][
                    "delta_vs_accepted"
                ]["total_pnl"],
                "accepted_target_trade_count": payload["window_metrics"][label][
                    "accepted_target_trade_count"
                ],
                "variant_target_trade_count": payload["window_metrics"][label][
                    "variant_target_trade_count"
                ],
                "guarded_entries": len(
                    payload["window_metrics"][label]["diagnostics"]["variant"]["guard_events"]
                ),
            }
            for label in base.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }


def _judge_metric_artifacts(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    aggregate = payload["gate4"]["aggregate"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in payload["before_metrics"].values()
    )
    comparator_max_drawdown = max(
        float(row["accepted_after"].get("max_drawdown_pct") or 0.0)
        for row in payload["window_metrics"].values()
    )
    before = {
        "expected_value_score": aggregate["comparator_expected_value_score_sum"],
        "total_pnl": aggregate["comparator_total_pnl_sum"],
        "max_drawdown_pct": comparator_max_drawdown,
        "survival_rate": min_survival,
        "target_trade_count": aggregate["accepted_trade_count_sum"],
        "window_count": len(payload["before_metrics"]),
        "source": "aggregate_accepted_low_deployment_etf_comparator_three_windows",
    }
    after = {
        "expected_value_score": aggregate["after_expected_value_score_sum"],
        "total_pnl": aggregate["after_total_pnl_sum"],
        "max_drawdown_pct": comparator_max_drawdown
        + aggregate["max_drawdown_delta_max_vs_accepted"],
        "survival_rate": min_survival,
        "target_trade_count": aggregate["target_trade_count_sum"],
        "window_count": len(payload["before_metrics"]),
        "source": "aggregate_after_market_pressure_guard_variant_three_windows",
    }
    return before, after


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "owner": "alpha-search-automation",
            "claimed_at": ticket.get("claimed_at") or payload["timestamp"],
            "completed_at": payload["timestamp"],
            "allowed_write_scope": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(BEFORE_JSON),
                _repo_rel(AFTER_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(EXPERIMENT_LOG),
            ],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "artifact_md": _repo_rel(ARTIFACT_MD),
                "before": _repo_rel(BEFORE_JSON),
                "after": _repo_rel(AFTER_JSON),
                "log": _repo_rel(LOG_JSON),
                "accepted": payload["gate4"]["passed"],
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "calibration": payload["calibration"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


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
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(BEFORE_JSON): _sha256(BEFORE_JSON),
            _repo_rel(AFTER_JSON): _sha256(AFTER_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
            _repo_rel(ARTIFACT_MD): _sha256(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG): _sha256(EXPERIMENT_LOG),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    before_judge, after_judge = _judge_metric_artifacts(payload)
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, before_judge)
    _write_json(AFTER_JSON, after_judge)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _write_text(ARTIFACT_MD, _build_artifact(payload))
    _update_ticket(payload)
    _write_manifest(payload)
    _upsert_jsonl(EXPERIMENT_LOG, log_record)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
