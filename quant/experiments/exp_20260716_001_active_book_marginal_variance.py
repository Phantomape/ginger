"""Gate 1-4 replay for a requested-risk marginal-variance overlay.

The fixed policy runs after the unchanged candidate selector and before the
unchanged execution-date cash admission.  It scales only requested opening
shares; released cash is allowed to flow through the native chronological
backtest, so later fills and add-ons can change endogenously.
"""

from __future__ import annotations

import inspect
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for entry in (str(QUANT), str(EXPERIMENTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import active_book_marginal_variance as policy  # noqa: E402
import backtester as bt  # noqa: E402
import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402


EXPERIMENT_ID = "exp-20260716-001"
PROTOCOL_ID = "cash_feasible_active_book_marginal_variance_v1"
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
SUMMARY_PATH = EXP_DIR / "active_book_marginal_variance.json"
BEFORE_PATH = EXP_DIR / "before.json"
AFTER_PATH = EXP_DIR / "after.json"
ACTIVE_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
FROZEN_INPUTS = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260712-015"
    / "frozen_behavior_inputs.json"
)
SCALAR_KEY = "active_book_marginal_variance_scalar"
EV_GROWTH_FLOOR = 0.10
MAX_DRAWDOWN_DRIFT = 0.005
MIN_TOUCHED_EXECUTED = 9
MIN_TOUCHED_WINDOWS = 2


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _price(frame: Any, day: Any, field: str = "Close") -> float | None:
    try:
        row = frame.loc[day]
        value = row[field]
        if hasattr(value, "iloc"):
            value = value.iloc[-1]
        return _number(value)
    except (KeyError, IndexError, TypeError, AttributeError):
        return None


def _runtime_context() -> dict[str, Any]:
    """Read the exact BacktestEngine.run decision-time locals."""
    required = ("today", "positions", "ohlcv_all", "all_dates", "equity")
    for frame_info in inspect.stack():
        values = frame_info.frame.f_locals
        if all(name in values for name in required):
            return {name: values[name] for name in required}
    raise RuntimeError("could not resolve BacktestEngine.run decision context")


def _returns_through_signal_day(
    frame: Any,
    today: Any,
    all_dates: list[Any],
) -> tuple[dict[str, float] | None, dict[str, Any]]:
    sessions = [day for day in all_dates if day <= today]
    if len(sessions) < policy.LOOKBACK_RETURNS + 1:
        return None, {
            "status": "insufficient_market_sessions",
            "session_count": len(sessions),
        }
    required = sessions[-(policy.LOOKBACK_RETURNS + 1):]
    closes: list[float] = []
    missing: list[str] = []
    for day in required:
        close = _price(frame, day)
        if close is None or close <= 0:
            missing.append(str(day)[:10])
        else:
            closes.append(close)
    if missing or len(closes) != len(required):
        return None, {
            "status": "nonconsecutive_ticker_sessions",
            "missing_sessions": missing,
            "required_start": str(required[0])[:10],
            "required_end": str(required[-1])[:10],
        }
    returns = {
        str(required[index])[:10]: closes[index] / closes[index - 1] - 1.0
        for index in range(1, len(required))
    }
    return returns, {
        "status": "complete",
        "close_count": len(closes),
        "return_count": len(returns),
        "aligned_start": str(required[1])[:10],
        "aligned_end": str(required[-1])[:10],
        "asof_boundary_passed": required[-1] == today,
    }


def _future_fill_date(frame: Any, today: Any, all_dates: list[Any]) -> str | None:
    for day in [value for value in all_dates if value > today][:3]:
        if day in frame.index:
            return str(day)[:10]
    return None


def _candidate_requested_notional(signal: dict[str, Any]) -> float | None:
    sizing = signal.get("sizing") or {}
    shares = _number(sizing.get("shares_to_buy"))
    entry = _number(sizing.get("entry_price"))
    if entry is None:
        entry = _number(signal.get("entry_price"))
    if shares is None or shares <= 0 or entry is None or entry <= 0:
        return None
    return shares * entry


def _fallback(status: str, **details: Any) -> dict[str, Any]:
    return {
        "status": status,
        "scalar": 1.0,
        "lookback_returns": policy.LOOKBACK_RETURNS,
        **details,
    }


def _evaluate_signal(signal: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    today = context["today"]
    positions = context["positions"]
    ohlcv_all = context["ohlcv_all"]
    all_dates = context["all_dates"]
    ticker = str(signal.get("ticker") or "").upper()
    candidate_frame = ohlcv_all.get(ticker)
    candidate_notional = _candidate_requested_notional(signal)
    if candidate_frame is None or candidate_notional is None:
        evaluation = _fallback("runner_missing_candidate_input")
        history = {"status": "missing"}
        active_payload: list[dict[str, Any]] = []
        future_positions: list[str] = []
    else:
        candidate_returns, history = _returns_through_signal_day(
            candidate_frame, today, all_dates
        )
        active_payload = []
        future_positions = []
        active_history_failures: list[dict[str, Any]] = []
        for position in positions:
            position_ticker = str(getattr(position, "ticker", "") or "").upper()
            entry_date = getattr(position, "entry_date", None)
            if entry_date is not None and entry_date > today:
                future_positions.append(position_ticker)
                continue
            frame = ohlcv_all.get(position_ticker)
            if frame is None:
                active_history_failures.append(
                    {"ticker": position_ticker, "status": "missing_frame"}
                )
                continue
            position_returns, position_history = _returns_through_signal_day(
                frame, today, all_dates
            )
            close = _price(frame, today)
            shares = _number(getattr(position, "shares", None))
            if position_returns is None or close is None or shares is None or shares <= 0:
                active_history_failures.append(
                    {"ticker": position_ticker, **position_history}
                )
                continue
            active_payload.append(
                {
                    "ticker": position_ticker,
                    "notional_usd": shares * close,
                    "returns_by_date": position_returns,
                }
            )
        if candidate_returns is None:
            evaluation = _fallback("runner_incomplete_candidate_history")
        elif active_history_failures:
            evaluation = _fallback(
                "runner_incomplete_active_history",
                active_history_failures=active_history_failures,
            )
        else:
            evaluation = policy.evaluate_active_book_marginal_variance(
                candidate_returns,
                candidate_notional,
                active_payload,
                lookback=policy.LOOKBACK_RETURNS,
            )

    sizing = signal.get("sizing") or {}
    scaled_sizing, share_audit = policy.apply_scalar_to_sizing(
        sizing, float(evaluation.get("scalar", 1.0))
    )
    signal["sizing"] = scaled_sizing
    expected_fill = (
        _future_fill_date(candidate_frame, today, all_dates)
        if candidate_frame is not None
        else None
    )
    active_notionals = [row["notional_usd"] for row in active_payload]
    active_total = sum(active_notionals)
    active_shares = [value / active_total for value in active_notionals] if active_total else []
    return {
        "signal_date": str(today)[:10],
        "expected_fill_date": expected_fill,
        "signal_contract": {
            "entry_date": expected_fill,
            "target_price": signal.get("target_price"),
            "entry_date_present": expected_fill is not None,
            "target_price_present": (
                _number(signal.get("target_price")) is not None
                and float(signal["target_price"]) > 0
            ),
        },
        "ticker": ticker,
        "strategy": signal.get("strategy"),
        "decision_point": "post_selection_pre_cash_admission_requested_risk",
        "candidate_requested_notional_usd": candidate_notional,
        "active_book_tickers": [row["ticker"] for row in active_payload],
        "active_book_notionals_usd": active_notionals,
        "active_book_notional_usd": active_total,
        "active_book_single_name_share": max(active_shares) if active_shares else 0.0,
        "active_book_hhi": sum(value * value for value in active_shares),
        "future_dated_positions_excluded": future_positions,
        "candidate_history": history,
        "evaluation": evaluation,
        "share_audit": share_audit,
        "material_share_change": (
            share_audit.get("scaled_shares") != share_audit.get("baseline_shares")
        ),
    }


def _make_plan_wrapper(
    original: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]],
    state: dict[str, Any],
) -> Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]:
    def wrapped(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        selected, plan = original(*args, **kwargs)
        if selected:
            context = _runtime_context()
            for signal in selected:
                state["annotations"].append(_evaluate_signal(signal, context))
        return selected, plan

    return wrapped


def _load_frozen() -> dict[str, Any]:
    payload = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    if payload.get("behavior_sha256") != gate1._stable_hash(payload.get("behavior")):
        raise RuntimeError("frozen behavior input hash mismatch")
    return payload


def _run_after(
    spec: dict[str, str], frozen: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    state: dict[str, Any] = {"annotations": []}
    original_plan = bt.plan_entry_candidates
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    bt.plan_entry_candidates = _make_plan_wrapper(original_plan, state)
    if SCALAR_KEY not in original_keys:
        bt.SIZING_MULTIPLIER_KEYS = (*original_keys, SCALAR_KEY)
    try:
        result, identity = gate1._run_window(spec, frozen)
    finally:
        bt.plan_entry_candidates = original_plan
        bt.SIZING_MULTIPLIER_KEYS = original_keys
    state["patch_restored"] = (
        bt.plan_entry_candidates is original_plan
        and bt.SIZING_MULTIPLIER_KEYS == original_keys
    )
    return result, identity, state


def _cash_summary(result: dict[str, Any]) -> dict[str, Any]:
    ledger = result.get("cash_ledger") or {}
    keys = (
        "enforced",
        "initial_cash",
        "min_cash",
        "min_cash_date",
        "negative_cash_event_count",
        "scaled_entry_count",
        "skipped_entry_count",
        "scaled_addon_count",
        "skipped_addon_count",
        "ending_cash",
        "core_realized_pnl",
        "cash_conservation_error",
        "cash_conservation_passed",
    )
    return {key: ledger.get(key) for key in keys}


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "max_drawdown_pct",
        "worst_trade_pct",
        "tail_loss_share",
        "win_rate",
        "total_trades",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    )
    return {key: result.get(key) for key in keys}


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key in set(before) | set(after):
        left = _number(before.get(key))
        right = _number(after.get(key))
        output[key] = right - left if left is not None and right is not None else None
    return output


def _positive_concentration(result: dict[str, Any]) -> dict[str, Any]:
    pnl_by_ticker: dict[str, float] = defaultdict(float)
    for trade in result.get("trades") or []:
        pnl_by_ticker[str(trade.get("ticker") or "").upper()] += float(
            trade.get("pnl") or 0.0
        )
    positives = sorted((value for value in pnl_by_ticker.values() if value > 0), reverse=True)
    total = sum(positives)
    shares = [value / total for value in positives] if total else []
    return {
        "positive_pnl_usd": total,
        "positive_ticker_count": len(positives),
        "single_share": max(shares) if shares else None,
        "top5_share": sum(shares[:5]) if shares else None,
        "hhi": sum(value * value for value in shares) if shares else None,
    }


def _first_divergence(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    left = before.get("trades") or []
    right = after.get("trades") or []
    for index in range(max(len(left), len(right))):
        before_row = left[index] if index < len(left) else None
        after_row = right[index] if index < len(right) else None
        if before_row != after_row:
            return {
                "index": index,
                "before": before_row,
                "after": after_row,
            }
    return {"index": None, "before": None, "after": None}


def _touched_executed(
    before: dict[str, Any],
    after: dict[str, Any],
    annotations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    material = {
        (row.get("ticker"), row.get("expected_fill_date")): row
        for row in annotations
        if row.get("material_share_change")
    }
    before_trades = {
        (
            str(trade.get("ticker") or "").upper(),
            str(trade.get("entry_date") or "")[:10],
        ): trade
        for trade in before.get("trades") or []
    }
    touched: list[dict[str, Any]] = []
    for trade in after.get("trades") or []:
        key = (str(trade.get("ticker") or "").upper(), str(trade.get("entry_date") or "")[:10])
        baseline_trade = before_trades.get(key)
        baseline_shares = baseline_trade.get("shares") if baseline_trade else None
        if key in material and trade.get("shares") != baseline_shares:
            touched.append(
                {
                    "ticker": key[0],
                    "entry_date": key[1],
                    "pnl": trade.get("pnl"),
                    "shares": trade.get("shares"),
                    "baseline_shares": baseline_shares,
                    "requested_scalar": material[key]["share_audit"].get(
                        "requested_scalar"
                    ),
                    "realized_scalar": material[key]["share_audit"].get(
                        "realized_scalar"
                    ),
                }
            )
    return touched


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": sum(float(row["expected_value_score"]) for row in rows),
        "total_pnl": sum(float(row["total_pnl"]) for row in rows),
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in rows),
        "survival_rate": min(float(row["survival_rate"]) for row in rows),
        "trade_count": sum(int(row["total_trades"]) for row in rows),
    }


def _runtime_signal_contract(window_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    annotations = [
        row
        for window in window_reports.values()
        for row in window.get("annotations") or []
    ]
    executable = [row for row in annotations if row.get("expected_fill_date") is not None]
    missing_entry_date = [
        f"{row.get('ticker')}:{row.get('signal_date')}"
        for row in executable
        if not (row.get("signal_contract") or {}).get("entry_date_present")
    ]
    missing_target_price = [
        f"{row.get('ticker')}:{row.get('signal_date')}"
        for row in executable
        if not (row.get("signal_contract") or {}).get("target_price_present")
    ]
    annotation_keys = {
        (str(row.get("ticker") or "").upper(), str(row.get("expected_fill_date") or "")[:10])
        for row in executable
    }
    trade_rows = [
        trade
        for window in window_reports.values()
        for trade in window.get("after_trades") or []
    ]
    missing_trade_entry_date = [
        str(row.get("ticker") or "") for row in trade_rows if not row.get("entry_date")
    ]
    unmatched_trade_contract = [
        f"{str(row.get('ticker') or '').upper()}:{str(row.get('entry_date') or '')[:10]}"
        for row in trade_rows
        if (
            str(row.get("ticker") or "").upper(),
            str(row.get("entry_date") or "")[:10],
        )
        not in annotation_keys
    ]
    return {
        "source": "actual patched backtest plan annotations and executed trade rows",
        "selected_annotation_count": len(annotations),
        "executable_annotation_count": len(executable),
        "end_of_window_nonexecutable_count": len(annotations) - len(executable),
        "executed_trade_count": len(trade_rows),
        "missing_entry_date_annotations": missing_entry_date,
        "missing_target_price_annotations": missing_target_price,
        "missing_trade_entry_date_tickers": missing_trade_entry_date,
        "unmatched_trade_contract": unmatched_trade_contract,
        "passed": bool(executable) and not (
            missing_entry_date
            or missing_target_price
            or missing_trade_entry_date
            or unmatched_trade_contract
        ),
    }


def main() -> int:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    frozen = _load_frozen()
    reference = json.loads(ACTIVE_BASELINE.read_text(encoding="utf-8"))
    reference_windows = {row["label"]: row for row in reference["windows"]}
    before_results: dict[str, dict[str, Any]] = {}
    after_results: dict[str, dict[str, Any]] = {}
    window_reports: dict[str, dict[str, Any]] = {}

    for spec in gate1.WINDOWS:
        label = spec["label"]
        print(f"[{label}] unpatched cash-feasible baseline replay ...", flush=True)
        before, before_identity = gate1._run_window(spec, frozen)
        ref = reference_windows[label]
        reference_checks = {
            "expected_value_score": before.get("expected_value_score") == ref.get("expected_value_score"),
            "total_pnl": before.get("total_pnl") == ref.get("total_pnl"),
            "sharpe_daily": before.get("sharpe_daily") == ref.get("sharpe_daily"),
            "max_drawdown_pct": before.get("max_drawdown_pct") == ref.get("max_drawdown_pct"),
            "trade_count": before.get("total_trades") == ref.get("trade_count"),
            "signals_generated": before.get("signals_generated") == ref.get("signals_generated"),
            "signals_survived": before.get("signals_survived") == ref.get("signals_survived"),
            "survival_rate": before.get("survival_rate") == ref.get("survival_rate"),
            "trade_rows_sha256": before_identity.get("trade_rows_sha256") == ref.get("trade_rows_sha256"),
            "daily_return_series_sha256": before_identity.get("daily_return_series_sha256") == ref.get("daily_return_series_sha256"),
            "sharpe_inference_contract": before_identity.get("sharpe_inference_contract_passed") is True,
            "cash_ledger": _cash_summary(before) == ref.get("cash_ledger"),
        }
        if not all(reference_checks.values()):
            raise RuntimeError(f"{label}: active Gate-1 identity mismatch: {reference_checks}")

        print(f"[{label}] marginal-variance replay ...", flush=True)
        after, after_identity, state = _run_after(spec, frozen)
        if not state["patch_restored"]:
            raise RuntimeError(f"{label}: monkeypatch was not restored")
        cash = _cash_summary(after)
        min_cash = _number(cash.get("min_cash"))
        conservation_error = _number(cash.get("cash_conservation_error"))
        cash_passed = (
            cash.get("enforced") is True
            and cash.get("negative_cash_event_count") == 0
            and min_cash is not None
            and min_cash >= 0
            and cash.get("cash_conservation_passed") is True
            and conservation_error is not None
            and abs(conservation_error) < 1e-9
        )
        annotations = state["annotations"]
        boundary_passed = all(
            row.get("candidate_history", {}).get("status") != "complete"
            or (
                row["candidate_history"].get("asof_boundary_passed") is True
                and row["candidate_history"].get("return_count") == policy.LOOKBACK_RETURNS
                and row["candidate_history"].get("aligned_end") == row.get("signal_date")
            )
            for row in annotations
        )
        touched = _touched_executed(before, after, annotations)
        before_metrics = _metrics(before)
        after_metrics = _metrics(after)
        window_reports[label] = {
            "window": dict(spec),
            "reference_checks": reference_checks,
            "before": before_metrics,
            "after": after_metrics,
            "delta": _delta(after_metrics, before_metrics),
            "before_identity": before_identity,
            "after_identity": after_identity,
            "after_trades": after.get("trades") or [],
            "cash": cash,
            "cash_passed": cash_passed,
            "candidate_asof_boundary_passed": boundary_passed,
            "annotations": annotations,
            "annotation_count": len(annotations),
            "material_annotation_count": sum(
                1 for row in annotations if row.get("material_share_change")
            ),
            "touched_executed_trades": touched,
            "touched_executed_count": len(touched),
            "first_trade_divergence": _first_divergence(before, after),
            "before_cash_admission_events": (before.get("cash_ledger") or {}).get("admission_events") or [],
            "after_cash_admission_events": (after.get("cash_ledger") or {}).get("admission_events") or [],
            "before_positive_concentration": _positive_concentration(before),
            "after_positive_concentration": _positive_concentration(after),
        }
        before_results[label] = before
        after_results[label] = after
        gate1._atomic_write_json(
            EXP_DIR / f"before_{label}.json",
            gate1._persistable_backtest_result(before),
        )
        gate1._atomic_write_json(
            EXP_DIR / f"after_{label}.json",
            gate1._persistable_backtest_result(after),
        )

    before_aggregate = _aggregate([_metrics(before_results[spec["label"]]) for spec in gate1.WINDOWS])
    after_aggregate = _aggregate([_metrics(after_results[spec["label"]]) for spec in gate1.WINDOWS])
    aggregate_delta = _delta(after_aggregate, before_aggregate)
    touched_total = sum(row["touched_executed_count"] for row in window_reports.values())
    touched_windows = sum(row["touched_executed_count"] > 0 for row in window_reports.values())
    improved_windows = sum(row["delta"]["expected_value_score"] > 0 for row in window_reports.values())
    regressed_windows = sum(row["delta"]["expected_value_score"] < 0 for row in window_reports.values())

    concentration_checks: dict[str, Any] = {}
    for label, row in window_reports.items():
        before_c = row["before_positive_concentration"]
        after_c = row["after_positive_concentration"]
        checks = {}
        for key, cap in (("single_share", 0.50), ("top5_share", 0.60), ("hhi", 0.35)):
            before_value = before_c.get(key)
            after_value = after_c.get(key)
            checks[key] = (
                after_value is not None
                and before_value is not None
                and after_value <= cap + 1e-12
                and after_value <= before_value + 1e-12
            )
        concentration_checks[label] = {**checks, "passed": all(checks.values())}

    runtime_signal_contract = _runtime_signal_contract(window_reports)

    gates = {
        "gate1_exact_active_cash_baseline": all(
            all(row["reference_checks"].values()) for row in window_reports.values()
        ),
        "gate2_pit_and_signal_contract": runtime_signal_contract["passed"] and all(
            row["candidate_asof_boundary_passed"] for row in window_reports.values()
        ),
        "gate3_survival": all(
            float(row["after"]["survival_rate"]) >= 0.05 for row in window_reports.values()
        ),
        "aggregate_ev_gt_10pct": after_aggregate["expected_value_score"] > before_aggregate["expected_value_score"] * (1.0 + EV_GROWTH_FLOOR),
        "aggregate_pnl_delta_nonnegative": after_aggregate["total_pnl"] >= before_aggregate["total_pnl"],
        "no_window_ev_regression": regressed_windows == 0,
        "at_least_two_ev_improved_windows": improved_windows >= 2,
        "drawdown_guard": all(
            float(row["after"]["max_drawdown_pct"]) <= float(row["before"]["max_drawdown_pct"]) + MAX_DRAWDOWN_DRIFT
            for row in window_reports.values()
        ),
        "cash_integrity": all(row["cash_passed"] for row in window_reports.values()),
        "materiality": touched_total >= MIN_TOUCHED_EXECUTED and touched_windows >= MIN_TOUCHED_WINDOWS,
        "positive_pnl_concentration_not_worse": all(
            row["passed"] for row in concentration_checks.values()
        ),
    }
    gate4_passed = all(gates.values())
    before_measurement = {
        **before_aggregate,
        "windows": {label: row["before"] for label, row in window_reports.items()},
    }
    after_measurement = {
        **after_aggregate,
        "windows": {label: row["after"] for label, row in window_reports.items()},
    }
    gate1._atomic_write_json(BEFORE_PATH, before_measurement)
    gate1._atomic_write_json(AFTER_PATH, after_measurement)

    summary = {
        "schema": "active_book_marginal_variance_gate4_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis_clock": "signal-day close after exits; requested shares scaled before unchanged next-open cash admission",
        "policy": {
            "lookback_returns": policy.LOOKBACK_RETURNS,
            "covariance": "raw simple close returns on the last 60 consecutive market sessions through signal day",
            "positive_cross_only": "net active-book cross term C<=0 leaves scalar at 1",
            "formula": "C>0: (-C + sqrt(C^2 + 4*S^2)) / (2*S)",
            "same_day_candidates": "all see the same pre-entry active book",
            "cash_path": "native chronological admission; no re-ranking, refill scan, or post-hoc PnL adjustment",
            "addon_path": "unchanged addon rule naturally uses the reduced original-share base",
        },
        "baseline": str(ACTIVE_BASELINE.relative_to(ROOT)).replace("\\", "/"),
        "before": before_aggregate,
        "after": after_aggregate,
        "delta": aggregate_delta,
        "windows": window_reports,
        "touched_executed_total": touched_total,
        "touched_window_count": touched_windows,
        "ev_improved_windows": improved_windows,
        "ev_regressed_windows": regressed_windows,
        "concentration_checks": concentration_checks,
        "runtime_signal_contract": runtime_signal_contract,
        "gates": gates,
        "gate4_passed": gate4_passed,
        "decision": "accepted_default_off" if gate4_passed else "rejected",
        "dsr": {
            "status": "not_computable",
            "reason": "no complete aligned selection panel was predeclared; DSR is Gate 5, not Gate 1-4",
        },
        "fingerprint_caveat": "reservation classifier misrouted this true active-book covariance risk-allocation surface to companyfacts_ratio/candidate_pool_top1_10d; novelty was manually checked against covariance neighbors",
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "trade_enabled": False,
            "live_ready": False,
            "orders_changed": False,
        },
        "reproduction": ".\\.venv\\Scripts\\python.exe -u -B quant\\experiments\\exp_20260716_001_active_book_marginal_variance.py",
    }
    gate1._atomic_write_json(SUMMARY_PATH, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "before": before_aggregate,
        "after": after_aggregate,
        "delta": aggregate_delta,
        "touched_executed_total": touched_total,
        "gates": gates,
        "summary": str(SUMMARY_PATH.relative_to(ROOT)).replace("\\", "/"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
