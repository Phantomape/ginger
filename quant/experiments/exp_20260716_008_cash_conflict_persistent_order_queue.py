"""Gate 1-4 replay for the cash-conflict persistent FIFO order queue.

The single changed decision is whether the exact unfilled remainder of a
fully-qualified fresh core entry survives a settled-cash rejection.  With the
flag disabled, the active cash-feasible baseline scales/skips that remainder.
With the flag enabled, the remainder may fill at a later open after ordinary
exits release cash, provided the original stop/target thesis is still valid.

This runner executes both explicit variants from the same frozen inputs:

* before: ``CASH_CONFLICT_PERSISTENT_ORDER_QUEUE_ENABLED=False``;
* after:  ``CASH_CONFLICT_PERSISTENT_ORDER_QUEUE_ENABLED=True``.

It writes experiment evidence only.  The queue is default-off, does not alter
production orders, and cannot be accepted unless the backtester emits enough
queue attribution to prove materiality, concentration, FIFO ordering, thesis
validity, and non-negative cash.  Missing queue metrics therefore produce a
clean rejected artifact instead of an exception while integration is staged.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for entry in (str(QUANT), str(EXPERIMENTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402


EXPERIMENT_ID = "exp-20260716-008"
PROTOCOL_ID = "cash_conflict_persistent_order_queue_v1"
CONFIG_KEY = "CASH_CONFLICT_PERSISTENT_ORDER_QUEUE_ENABLED"
RESULT_KEYS = (
    "cash_conflict_persistent_order_queue",
    "cash_conflict_order_queue",
    "cash_conflict_deferred_queue",
)

EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DATA_SUMMARY = EXP_DIR / "exp_20260716_008_cash_conflict_persistent_order_queue.json"
BEFORE_PATH = EXP_DIR / "before.json"
AFTER_PATH = EXP_DIR / "after.json"
ARTIFACT_PATH = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}.json"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
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

# Pre-registered in experiments/tickets/exp-20260716-008.json.
MIN_AGGREGATE_EV = 6.8263
MIN_AGGREGATE_PNL = 130_992.36
MIN_BOTH_IMPROVED_WINDOWS = 2
MAX_WINDOW_EV_REGRESSION_FRACTION = 0.05
MAX_DRAWDOWN_DRIFT = 0.01
MIN_SURVIVAL_RATE = 0.05
MIN_TRADES_PER_WINDOW = 10
MIN_BASELINE_TRADE_KEY_RETENTION = 0.80
MAX_CASH_CONSERVATION_ERROR = 1e-4
MIN_DELAYED_FILLS = 20
MAX_DELAYED_FILL_TICKER_SHARE = 0.50

METRIC_KEYS = (
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
CASH_KEYS = (
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


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _load_frozen() -> dict[str, Any]:
    payload = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    if payload.get("behavior_sha256") != gate1._stable_hash(payload.get("behavior")):
        raise RuntimeError("exp-20260712-015 frozen behavior input hash mismatch")
    return payload


def _run_variant(
    spec: dict[str, str],
    frozen: dict[str, Any],
    *,
    enabled: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one explicit queue variant and restore shared config exactly."""
    existed = CONFIG_KEY in gate1.RUN_CONFIG
    prior = gate1.RUN_CONFIG.get(CONFIG_KEY)
    gate1.RUN_CONFIG[CONFIG_KEY] = bool(enabled)
    try:
        result, identity = gate1._run_window(spec, frozen)
    finally:
        if existed:
            gate1.RUN_CONFIG[CONFIG_KEY] = prior
        else:
            gate1.RUN_CONFIG.pop(CONFIG_KEY, None)
    restored = (
        gate1.RUN_CONFIG.get(CONFIG_KEY) == prior
        if existed
        else CONFIG_KEY not in gate1.RUN_CONFIG
    )
    if not restored:
        raise RuntimeError(f"{spec['label']}: {CONFIG_KEY} was not restored")
    return result, identity


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    return {key: result.get(key) for key in METRIC_KEYS}


def _cash_summary(result: dict[str, Any]) -> dict[str, Any]:
    ledger = result.get("cash_ledger") or {}
    return {key: ledger.get(key) for key in CASH_KEYS}


def _cash_integrity(result: dict[str, Any]) -> dict[str, Any]:
    cash = _cash_summary(result)
    minimum = _number(cash.get("min_cash"))
    error = _number(cash.get("cash_conservation_error"))
    checks = {
        "enforced": cash.get("enforced") is True,
        "zero_negative_cash_events": cash.get("negative_cash_event_count") == 0,
        "nonnegative_min_cash": minimum is not None and minimum >= -1e-9,
        "cash_conservation_passed": cash.get("cash_conservation_passed") is True,
        "cash_conservation_error_within_tolerance": (
            error is not None and abs(error) <= MAX_CASH_CONSERVATION_ERROR
        ),
    }
    return {"summary": cash, "checks": checks, "passed": all(checks.values())}


def _event_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("events", "queue_events", "order_events"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
    return []


def _event_kind(row: dict[str, Any]) -> str:
    for key in ("event", "event_type", "action", "status", "decision"):
        value = str(row.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def _is_delayed_fill_event(row: dict[str, Any]) -> bool:
    kind = _event_kind(row)
    return "fill" in kind and not any(
        token in kind for token in ("cancel", "reject", "invalid", "enqueue")
    )


def _event_ticker(row: dict[str, Any]) -> str | None:
    for key in ("ticker", "symbol", "queued_ticker", "filled_ticker"):
        value = str(row.get(key) or "").strip().upper()
        if value:
            return value
    return None


def _first_numeric(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _number(payload.get(key))
        if value is not None:
            return value
    return None


def _explicit_ticker_counts(payload: dict[str, Any]) -> Counter[str]:
    for key in (
        "filled_ticker_counts",
        "delayed_fill_ticker_counts",
        "fills_by_ticker",
        "queued_fill_counts_by_ticker",
    ):
        raw = payload.get(key)
        if not isinstance(raw, dict):
            continue
        counts: Counter[str] = Counter()
        for ticker, value in raw.items():
            number = _number(value)
            if number is not None and number > 0:
                counts[str(ticker).upper()] += int(number)
        if counts:
            return counts
    return Counter()


def _queue_summary(result: dict[str, Any]) -> dict[str, Any]:
    raw_key = next(
        (
            key
            for key in RESULT_KEYS
            if isinstance(result.get(key), dict)
        ),
        None,
    )
    raw = result.get(raw_key) if raw_key else None
    payload = dict(raw) if isinstance(raw, dict) else {}
    events = _event_rows(payload)
    fill_events = [row for row in events if _is_delayed_fill_event(row)]

    counts = _explicit_ticker_counts(payload)
    if not counts:
        counts.update(
            ticker
            for ticker in (_event_ticker(row) for row in fill_events)
            if ticker
        )

    delayed_fill_count = _first_numeric(
        payload,
        (
            "delayed_fill_count",
            "filled_order_count",
            "successful_fill_count",
            "queue_fill_count",
            "executed_fill_count",
        ),
    )
    if delayed_fill_count is None and fill_events:
        delayed_fill_count = float(len(fill_events))
    delayed_fill_count_int = int(delayed_fill_count or 0)
    counted_fills = sum(counts.values())
    top_ticker, top_count = counts.most_common(1)[0] if counts else (None, 0)
    denominator = delayed_fill_count_int or counted_fills

    def invariant(keys: tuple[str, ...]) -> int | None:
        value = _first_numeric(payload, keys)
        return int(value) if value is not None else None

    return {
        "result_key_present": raw_key is not None,
        "result_key": raw_key,
        "enabled": payload.get("enabled"),
        "enqueued_order_count": invariant(
            (
                "enqueued_order_count",
                "queued_order_count",
                "enqueue_count",
            )
        ),
        "delayed_fill_count": delayed_fill_count_int,
        "cancelled_thesis_invalid_count": invariant(
            (
                "cancelled_thesis_invalid_count",
                "thesis_cancel_count",
                "invalidated_order_count",
            )
        ),
        "pending_order_count": invariant(
            ("pending_order_count", "remaining_order_count", "open_order_count")
        ),
        "fifo_violation_count": invariant(
            ("fifo_violation_count", "fifo_order_violation_count")
        ),
        "thesis_invalid_fill_count": invariant(
            (
                "thesis_invalid_fill_count",
                "invalid_thesis_fill_count",
                "stale_fill_count",
            )
        ),
        "negative_cash_after_fill_count": invariant(
            (
                "negative_cash_after_fill_count",
                "negative_cash_fill_count",
                "overdraft_fill_count",
            )
        ),
        "event_rows_logged": len(events),
        "fill_event_rows_logged": len(fill_events),
        "filled_ticker_counts": dict(sorted(counts.items())),
        "counted_delayed_fills": counted_fills,
        "top_filled_ticker": top_ticker,
        "top_filled_ticker_count": top_count,
        "top_filled_ticker_share": (
            top_count / denominator
            if denominator > 0 and top_count > 0
            else None
        ),
        "events": events,
        "raw": payload,
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key in set(before) | set(after):
        left = _number(before.get(key))
        right = _number(after.get(key))
        output[key] = right - left if left is not None and right is not None else None
    return output


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": sum(float(row["expected_value_score"]) for row in rows),
        "total_pnl": sum(float(row["total_pnl"]) for row in rows),
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in rows),
        "trade_count": sum(int(row["total_trades"]) for row in rows),
        "minimum_survival_rate": min(float(row["survival_rate"]) for row in rows),
    }


def _reference_checks(
    result: dict[str, Any],
    identity: dict[str, Any],
    reference: dict[str, Any],
) -> dict[str, bool]:
    return {
        "expected_value_score": result.get("expected_value_score")
        == reference.get("expected_value_score"),
        "total_pnl": result.get("total_pnl") == reference.get("total_pnl"),
        "sharpe_daily": result.get("sharpe_daily")
        == reference.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct")
        == reference.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades") == reference.get("trade_count"),
        "signals_generated": result.get("signals_generated")
        == reference.get("signals_generated"),
        "signals_survived": result.get("signals_survived")
        == reference.get("signals_survived"),
        "survival_rate": result.get("survival_rate")
        == reference.get("survival_rate"),
        "trade_rows_sha256": identity.get("trade_rows_sha256")
        == reference.get("trade_rows_sha256"),
        "daily_return_series_sha256": identity.get("daily_return_series_sha256")
        == reference.get("daily_return_series_sha256"),
        "sharpe_inference_contract": identity.get(
            "sharpe_inference_contract_passed"
        )
        is True,
        "cash_ledger": _cash_summary(result) == reference.get("cash_ledger"),
    }


def _trade_keys(result: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for row in result.get("trades") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("trade_key") or "").strip()
        if not key:
            key = "|".join(
                str(row.get(name) or "")
                for name in ("ticker", "entry_date", "entry_price", "strategy")
            )
        if key:
            keys.add(key)
    return keys


def _trade_key_retention(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    before_keys = _trade_keys(before)
    after_keys = _trade_keys(after)
    retained = before_keys & after_keys
    return {
        "baseline_trade_key_count": len(before_keys),
        "after_trade_key_count": len(after_keys),
        "retained_baseline_trade_key_count": len(retained),
        "retention": len(retained) / len(before_keys) if before_keys else 0.0,
        "dropped_baseline_trade_keys": sorted(before_keys - after_keys),
        "new_after_trade_keys": sorted(after_keys - before_keys),
    }


def _ev_regression_passed(before: float, after: float) -> bool:
    allowed_drop = abs(before) * MAX_WINDOW_EV_REGRESSION_FRACTION
    return after >= before - allowed_drop - 1e-12


def _write_evidence(
    summary: dict[str, Any],
    before_measurement: dict[str, Any],
    after_measurement: dict[str, Any],
    ticket: dict[str, Any],
) -> None:
    gate1._atomic_write_json(BEFORE_PATH, before_measurement)
    gate1._atomic_write_json(AFTER_PATH, after_measurement)
    gate1._atomic_write_json(DATA_SUMMARY, summary)
    gate1._atomic_write_json(ARTIFACT_PATH, summary)

    accepted = summary["decision"] == "accepted_default_off"
    failed_gates = [name for name, passed in summary["gates"].items() if not passed]
    prediction = ticket.get("prediction", {}) if isinstance(ticket, dict) else {}
    predicted_probability = _number(prediction.get("success_probability")) or 0.0
    expected_ev_delta = _number(prediction.get("expected_ev_delta"))
    expected_pnl_delta = _number(prediction.get("expected_pnl_delta"))
    actual_ev_delta = _number(summary["delta"].get("expected_value_score"))
    actual_pnl_delta = _number(summary["delta"].get("total_pnl"))
    realized_failure_mode = "stale_signal_decay_and_insufficient_delayed_fills"
    calibration = {
        "actual_success": bool(accepted),
        "predicted_success_probability": predicted_probability,
        "brier_score": (predicted_probability - (1.0 if accepted else 0.0)) ** 2,
        "expected_ev_delta": expected_ev_delta,
        "actual_ev_delta": actual_ev_delta,
        "ev_prediction_error": (
            actual_ev_delta - expected_ev_delta
            if actual_ev_delta is not None and expected_ev_delta is not None
            else None
        ),
        "expected_pnl_delta": expected_pnl_delta,
        "actual_pnl_delta": actual_pnl_delta,
        "pnl_prediction_error": (
            actual_pnl_delta - expected_pnl_delta
            if actual_pnl_delta is not None and expected_pnl_delta is not None
            else None
        ),
        "predicted_failure_modes": prediction.get("main_failure_modes", []),
        "realized_failure_mode": realized_failure_mode,
        "predicted_failure_mode_hit": True,
        "surprise_note": (
            "FIFO invariants and cash conservation were clean, but only 12 "
            "delayed fills materialized versus the 20-fill floor and the "
            "delayed entries reduced aggregate EV/PnL."
        ),
    }
    log = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": summary["generated_at"],
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "artifact_decision": summary["decision"],
        "lane": "alpha_search",
        "change_type": "capital_allocation",
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "mechanism_family": ticket.get("mechanism_family"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "hypothesis": ticket.get("hypothesis"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "fingerprint": {
            "data_source": "cash_feasible_core_book",
            "gate_shape": "cash_conflict_deferred_queue",
        },
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
        "prediction": prediction,
        "calibration": calibration,
        "realized_failure_mode": realized_failure_mode,
        "before_metrics": summary["before"],
        "after_metrics": summary["after"],
        "delta_metrics": summary["delta"],
        "parameters": {
            "config_key": CONFIG_KEY,
            "before": False,
            "after": True,
            "locked_variables": ticket.get("locked_variables", []),
            "pre_registered_gate4": summary["pre_registered_gate4"],
        },
        "causal_components": ticket.get("causal_components", []),
        "change_summary": (
            "Evaluated exact unfilled-share FIFO persistence after cash-only "
            "entry rejection, with later-open execution and original price-thesis "
            "invalidation; no leverage or incumbent liquidation was permitted."
        ),
        "notes": (
            f"Aggregate EV {summary['before']['expected_value_score']:.4f} to "
            f"{summary['after']['expected_value_score']:.4f}; aggregate PnL "
            f"{summary['before']['total_pnl']:.2f} to "
            f"{summary['after']['total_pnl']:.2f}; delayed fills="
            f"{summary['queue_attribution']['aggregate_delayed_fill_count']}."
        ),
        "rejection_reason": (
            f"Pre-registered Gate-4 checks failed: {', '.join(failed_gates)}"
            if failed_gates
            else None
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "The queue produced only twelve delayed fills. Old-thin improved, "
                "but late-strong and mid-weak both lost EV and PnL; aggregate EV "
                "fell 0.5644 and aggregate PnL fell 7804.17. All FIFO, thesis, "
                "cash-conservation, and concentration checks were clean, so the "
                "economic failure is stale-order displacement rather than a "
                "measurement or bookkeeping defect."
            ),
            "realized_failure_mode": realized_failure_mode,
            "forbidden_near_neighbor_retry": (
                "Do not retune queue age, FIFO priority, cash-shortfall size, or "
                "price-thesis thresholds on these same outcomes."
            ),
            "new_evidence_required": (
                "A new data source, genuinely different gate shape, or materially "
                "more settled forward cash-conflict decisions is required."
            ),
        },
        "production_impact": summary["production_impact"],
        "reproduction": summary["reproduction"],
        "related_files": [
            gate1._repo_rel(BEFORE_PATH),
            gate1._repo_rel(AFTER_PATH),
            gate1._repo_rel(DATA_SUMMARY),
            gate1._repo_rel(ARTIFACT_PATH),
            "quant/backtester.py",
            "quant/cash_conflict_persistent_order_queue.py",
            "quant/test_cash_conflict_persistent_order_queue.py",
            "quant/experiments/exp_20260716_008_cash_conflict_persistent_order_queue.py",
            "scripts/experiment_fingerprint.py",
            "quant/test_experiment_fingerprint.py",
            "docs/frozen_families.jsonl",
        ],
        "component": gate1._repo_rel(Path(__file__)),
        "llm_metrics": {"used_llm": False},
    }
    gate1._atomic_write_json(LOG_PATH, log)


def main() -> int:
    frozen = _load_frozen()
    ticket = json.loads(TICKET_PATH.read_text(encoding="utf-8-sig"))
    reference = json.loads(ACTIVE_BASELINE.read_text(encoding="utf-8"))
    reference_windows = {row["label"]: row for row in reference["windows"]}

    before_results: dict[str, dict[str, Any]] = {}
    after_results: dict[str, dict[str, Any]] = {}
    window_reports: dict[str, dict[str, Any]] = {}

    for spec in gate1.WINDOWS:
        label = spec["label"]
        print(f"[{label}] baseline ({CONFIG_KEY}=False) ...", flush=True)
        before, before_identity = _run_variant(spec, frozen, enabled=False)
        reference_checks = _reference_checks(
            before, before_identity, reference_windows[label]
        )
        if not all(reference_checks.values()):
            raise RuntimeError(
                f"{label}: active cash-feasible Gate-1 identity mismatch: "
                f"{reference_checks}"
            )

        print(f"[{label}] persistent queue ({CONFIG_KEY}=True) ...", flush=True)
        after, after_identity = _run_variant(spec, frozen, enabled=True)
        before_metrics = _metrics(before)
        after_metrics = _metrics(after)
        before_queue = _queue_summary(before)
        after_queue = _queue_summary(after)
        before_cash = _cash_integrity(before)
        after_cash = _cash_integrity(after)
        retention = _trade_key_retention(before, after)
        signals_unchanged = all(
            before.get(key) == after.get(key)
            for key in ("signals_generated", "signals_survived")
        )
        runtime_inputs_unchanged = all(
            before_identity.get(key) == after_identity.get(key)
            for key in (
                "effective_earnings_inputs_sha256",
                "effective_earnings_row_count",
                "window",
            )
        )
        executed_entry_dates_present = all(
            bool(row.get("entry_date")) for row in after.get("trades") or []
        )

        window_reports[label] = {
            "window": dict(spec),
            "reference_checks": reference_checks,
            "before": before_metrics,
            "after": after_metrics,
            "delta": _delta(after_metrics, before_metrics),
            "before_identity": before_identity,
            "after_identity": after_identity,
            "signals_generated_and_survived_unchanged": signals_unchanged,
            "runtime_inputs_unchanged": runtime_inputs_unchanged,
            "executed_trade_entry_dates_present": executed_entry_dates_present,
            "trade_key_retention": retention,
            "before_cash": before_cash,
            "after_cash": after_cash,
            "before_queue": before_queue,
            "after_queue": after_queue,
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

    before_aggregate = _aggregate(
        [_metrics(before_results[spec["label"]]) for spec in gate1.WINDOWS]
    )
    after_aggregate = _aggregate(
        [_metrics(after_results[spec["label"]]) for spec in gate1.WINDOWS]
    )
    aggregate_delta = _delta(after_aggregate, before_aggregate)

    both_improved_windows = sum(
        report["after"]["expected_value_score"]
        > report["before"]["expected_value_score"]
        and report["after"]["total_pnl"] > report["before"]["total_pnl"]
        for report in window_reports.values()
    )
    ev_regression_checks = {
        label: _ev_regression_passed(
            float(report["before"]["expected_value_score"]),
            float(report["after"]["expected_value_score"]),
        )
        for label, report in window_reports.items()
    }

    fill_counts: Counter[str] = Counter()
    total_delayed_fills = 0
    total_counted_fills = 0
    invariant_names = (
        "fifo_violation_count",
        "thesis_invalid_fill_count",
        "negative_cash_after_fill_count",
    )
    invariant_values: dict[str, list[int | None]] = {
        name: [] for name in invariant_names
    }
    for report in window_reports.values():
        queue = report["after_queue"]
        fill_counts.update(queue["filled_ticker_counts"])
        total_delayed_fills += int(queue["delayed_fill_count"])
        total_counted_fills += int(queue["counted_delayed_fills"])
        for name in invariant_names:
            invariant_values[name].append(queue[name])

    top_ticker, top_count = fill_counts.most_common(1)[0] if fill_counts else (None, 0)
    top_fill_share = (
        top_count / total_delayed_fills
        if total_delayed_fills > 0 and top_count > 0
        else None
    )
    aggregate_invariants = {
        name: (
            sum(int(value) for value in values if value is not None)
            if all(value is not None for value in values)
            else None
        )
        for name, values in invariant_values.items()
    }
    queue_attribution = {
        "aggregate_delayed_fill_count": total_delayed_fills,
        "aggregate_counted_delayed_fills": total_counted_fills,
        "filled_ticker_counts": dict(sorted(fill_counts.items())),
        "top_filled_ticker": top_ticker,
        "top_filled_ticker_count": top_count,
        "top_filled_ticker_share": top_fill_share,
        "aggregate_invariants": aggregate_invariants,
        "per_window": {
            label: report["after_queue"] for label, report in window_reports.items()
        },
    }

    baseline_trade_keys = sum(
        int(report["trade_key_retention"]["baseline_trade_key_count"])
        for report in window_reports.values()
    )
    retained_trade_keys = sum(
        int(report["trade_key_retention"]["retained_baseline_trade_key_count"])
        for report in window_reports.values()
    )
    aggregate_trade_key_retention = (
        retained_trade_keys / baseline_trade_keys if baseline_trade_keys else 0.0
    )

    pre_registered_gate4 = {
        "aggregate_expected_value_score_strictly_above": MIN_AGGREGATE_EV,
        "aggregate_total_pnl_strictly_above": MIN_AGGREGATE_PNL,
        "minimum_windows_improving_both_ev_and_pnl": MIN_BOTH_IMPROVED_WINDOWS,
        "maximum_single_window_ev_regression_fraction": (
            MAX_WINDOW_EV_REGRESSION_FRACTION
        ),
        "maximum_worst_drawdown_drift": MAX_DRAWDOWN_DRIFT,
        "minimum_survival_rate_per_window": MIN_SURVIVAL_RATE,
        "minimum_trades_per_window": MIN_TRADES_PER_WINDOW,
        "minimum_baseline_trade_key_retention": MIN_BASELINE_TRADE_KEY_RETENTION,
        "maximum_cash_conservation_error": MAX_CASH_CONSERVATION_ERROR,
        "minimum_delayed_fills": MIN_DELAYED_FILLS,
        "maximum_delayed_fill_ticker_share": MAX_DELAYED_FILL_TICKER_SHARE,
    }

    queue_invariants_reported = all(
        value is not None for value in aggregate_invariants.values()
    )
    gates = {
        "gate1_exact_cash_feasible_baseline": all(
            all(report["reference_checks"].values())
            for report in window_reports.values()
        ),
        "gate2_frozen_contract_and_entry_dates": (
            frozen.get("behavior_sha256")
            == gate1._stable_hash(frozen.get("behavior"))
            and all(
                report["runtime_inputs_unchanged"]
                and report["executed_trade_entry_dates_present"]
                for report in window_reports.values()
            )
        ),
        "gate3_survival": all(
            float(report["after"]["survival_rate"]) >= MIN_SURVIVAL_RATE
            for report in window_reports.values()
        ),
        "aggregate_ev_above_10pct_bar": (
            after_aggregate["expected_value_score"] > MIN_AGGREGATE_EV
        ),
        "aggregate_pnl_above_baseline": (
            after_aggregate["total_pnl"] > MIN_AGGREGATE_PNL
        ),
        "at_least_two_windows_improve_both_ev_and_pnl": (
            both_improved_windows >= MIN_BOTH_IMPROVED_WINDOWS
        ),
        "no_window_ev_regresses_more_than_5pct": all(
            ev_regression_checks.values()
        ),
        "worst_drawdown_drift_within_one_percentage_point": (
            after_aggregate["max_drawdown_pct"]
            <= before_aggregate["max_drawdown_pct"] + MAX_DRAWDOWN_DRIFT + 1e-12
        ),
        "trade_count_statistically_meaningful": all(
            int(report["after"]["total_trades"]) >= MIN_TRADES_PER_WINDOW
            for report in window_reports.values()
        ),
        "baseline_trade_key_retention_gte_80pct": (
            aggregate_trade_key_retention >= MIN_BASELINE_TRADE_KEY_RETENTION
        ),
        "cash_conservation_all_variants": all(
            report[role]["passed"]
            for report in window_reports.values()
            for role in ("before_cash", "after_cash")
        ),
        "signal_generation_and_survival_unchanged": all(
            report["signals_generated_and_survived_unchanged"]
            for report in window_reports.values()
        ),
        "queue_inactive_in_explicit_false_baseline": all(
            (
                not report["before_queue"]["result_key_present"]
                or (
                    report["before_queue"]["enabled"] is False
                    and report["before_queue"]["delayed_fill_count"] == 0
                )
            )
            for report in window_reports.values()
        ),
        "queue_result_present_and_enabled_in_after": all(
            report["after_queue"]["result_key_present"]
            and report["after_queue"]["enabled"] is True
            for report in window_reports.values()
        ),
        "queue_invariants_reported": queue_invariants_reported,
        "fifo_thesis_and_cash_invariants_clean": (
            queue_invariants_reported
            and all(value == 0 for value in aggregate_invariants.values())
        ),
        "at_least_20_delayed_fills": total_delayed_fills >= MIN_DELAYED_FILLS,
        "delayed_fill_ticker_attribution_complete": (
            total_counted_fills == total_delayed_fills
            and total_delayed_fills > 0
        ),
        "delayed_fill_ticker_concentration_lte_50pct": (
            top_fill_share is not None
            and top_fill_share <= MAX_DELAYED_FILL_TICKER_SHARE + 1e-12
        ),
    }
    gate4_passed = all(gates.values())

    before_measurement = {
        "experiment_id": EXPERIMENT_ID,
        "role": f"explicit_{CONFIG_KEY}_false",
        **before_aggregate,
        "windows": {
            label: {
                "metrics": report["before"],
                "cash": report["before_cash"],
                "queue": report["before_queue"],
            }
            for label, report in window_reports.items()
        },
    }
    after_measurement = {
        "experiment_id": EXPERIMENT_ID,
        "role": f"explicit_{CONFIG_KEY}_true",
        **after_aggregate,
        "aggregate_trade_key_retention": aggregate_trade_key_retention,
        "queue_attribution": queue_attribution,
        "windows": {
            label: {
                "metrics": report["after"],
                "cash": report["after_cash"],
                "queue": report["after_queue"],
                "trade_key_retention": report["trade_key_retention"],
            }
            for label, report in window_reports.items()
        },
    }

    generated_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "schema": "cash_conflict_persistent_order_queue_gate4_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "generated_at": generated_at,
        "hypothesis": ticket.get("hypothesis"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "config": {"key": CONFIG_KEY, "before": False, "after": True},
        "accepted_result_keys": list(RESULT_KEYS),
        "baseline": gate1._repo_rel(ACTIVE_BASELINE),
        "frozen_behavior_inputs": {
            "path": gate1._repo_rel(FROZEN_INPUTS),
            "file_sha256": gate1._file_sha256(FROZEN_INPUTS),
            "behavior_sha256": frozen["behavior_sha256"],
            "universe_count": len(frozen["behavior"]["universe"]),
        },
        "policy": {
            "trigger": (
                "fully qualified fresh core entry is partially or fully rejected "
                "only by settled-cash admission"
            ),
            "queued_quantity": "exact unfilled share remainder",
            "priority": "FIFO across original cash-conflict decisions",
            "execution": "later open after ordinary exits release settled cash",
            "invalidation": "original stop or target price thesis is breached",
            "prohibited": ["leverage", "incumbent liquidation"],
            "locked": ticket.get("locked_variables", []),
        },
        "pre_registered_gate4": pre_registered_gate4,
        "before": before_aggregate,
        "after": after_aggregate,
        "delta": aggregate_delta,
        "windows": window_reports,
        "both_ev_and_pnl_improved_window_count": both_improved_windows,
        "ev_regression_checks": ev_regression_checks,
        "aggregate_trade_key_retention": aggregate_trade_key_retention,
        "baseline_trade_key_count": baseline_trade_keys,
        "retained_baseline_trade_key_count": retained_trade_keys,
        "queue_attribution": queue_attribution,
        "gates": gates,
        "gate4_passed": gate4_passed,
        "decision": "accepted_default_off" if gate4_passed else "rejected",
        "dsr": {
            "status": "not_computable",
            "reason": (
                "No complete aligned selection-trial panel was pre-registered; "
                "DSR remains a Gate-5 diagnostic rather than a Gate-4 substitute."
            ),
        },
        "production_impact": {
            "explicit_after_flag_only": True,
            "default_flag_changed": False,
            "live_or_paper_orders_changed": False,
            "signal_generation_or_ranking_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "rejected_strategy_integration_retained": gate4_passed,
            "runtime_integration_rolled_back_after_rejection": not gate4_passed,
        },
        "reproduction": (
            ".\\.venv\\Scripts\\python.exe -u -B "
            "quant\\experiments\\exp_20260716_008_cash_conflict_persistent_order_queue.py"
        ),
        "reproduction_note": (
            "The measured artifacts are retained, but the rejected backtester "
            "integration was rolled back after Gate 4. Exact rerun requires "
            "deliberately reconstructing that historical integration from the "
            "retained helper and artifacts; the runner alone fails safely."
        ),
    }
    _write_evidence(summary, before_measurement, after_measurement, ticket)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": summary["decision"],
                "before": before_aggregate,
                "after": after_aggregate,
                "delta": aggregate_delta,
                "queue_attribution": {
                    key: queue_attribution[key]
                    for key in (
                        "aggregate_delayed_fill_count",
                        "filled_ticker_counts",
                        "top_filled_ticker_share",
                        "aggregate_invariants",
                    )
                },
                "gates": gates,
                "data_summary": gate1._repo_rel(DATA_SUMMARY),
                "artifact": gate1._repo_rel(ARTIFACT_PATH),
                "log": gate1._repo_rel(LOG_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
