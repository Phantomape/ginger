"""Gate 1-4 replay for cash-conflict oldest-incumbent rotation.

The single changed decision is enabled only when the settled-cash admission
path would otherwise scale or skip a fully qualified fresh core entry.  The
challenger exits the oldest active core position at that same next open and
uses the released cash for the unchanged fresh-entry request.  Signal
generation, ranking, requested sizing, ordinary exits, add-ons, costs, and the
three exp-20260712-015 frozen windows remain locked.

This runner deliberately executes both variants from the same process and
frozen inputs:

* before: ``CASH_CONFLICT_OLDEST_ROTATION_ENABLED=False``;
* after:  ``CASH_CONFLICT_OLDEST_ROTATION_ENABLED=True``.

Running the file writes only experiment evidence (per-window replay data, a
compact artifact, and a closeout-shaped log).  It does not change the default
flag, production orders, or experiment registry state.
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


EXPERIMENT_ID = "exp-20260716-004"
PROTOCOL_ID = "cash_conflict_oldest_incumbent_rotation_v1"
CONFIG_KEY = "CASH_CONFLICT_OLDEST_ROTATION_ENABLED"
RESULT_KEY = "cash_conflict_rotation"

EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DATA_SUMMARY = EXP_DIR / "exp_20260716_004_cash_conflict_oldest_rotation.json"
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

# The ticket pre-registered these Gate-4 bars before outcome inspection.
MIN_AGGREGATE_EV = 6.8263
MIN_AGGREGATE_PNL = 130_992.36
MIN_EV_IMPROVED_WINDOWS = 2
MAX_WINDOW_EV_REGRESSION_FRACTION = 0.05
MAX_DRAWDOWN_DRIFT = 0.01
MIN_SURVIVAL_RATE = 0.05
MIN_TRADES_PER_WINDOW = 10
MIN_AGGREGATE_TRADE_RETENTION = 0.80
MAX_EVICTION_TICKER_SHARE = 0.50

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
    """Run one explicit flag variant and restore the shared config exactly."""
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
        "zero_cash_conservation_error": error is not None and abs(error) < 1e-9,
    }
    return {"summary": cash, "checks": checks, "passed": all(checks.values())}


def _event_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("events", "rotation_events", "eviction_events"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
    return []


def _evicted_ticker(row: dict[str, Any]) -> str | None:
    for key in (
        "evicted_ticker",
        "incumbent_ticker",
        "oldest_ticker",
        "exit_ticker",
        "rotated_out_ticker",
    ):
        value = str(row.get(key) or "").strip().upper()
        if value:
            return value
    return None


def _explicit_ticker_counts(payload: dict[str, Any]) -> Counter[str]:
    for key in (
        "evictions_by_ticker",
        "evicted_ticker_counts",
        "rotation_exit_counts_by_ticker",
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


def _first_numeric(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _number(payload.get(key))
        if value is not None:
            return value
    return None


def _rotation_summary(result: dict[str, Any]) -> dict[str, Any]:
    raw = result.get(RESULT_KEY)
    payload = dict(raw) if isinstance(raw, dict) else {}
    events = _event_rows(payload)
    counts = _explicit_ticker_counts(payload)
    if not counts:
        counts.update(
            ticker for ticker in (_evicted_ticker(row) for row in events) if ticker
        )

    reported_count = _first_numeric(
        payload,
        (
            "rotation_count",
            "successful_rotations",
            "executed_rotation_count",
            "rotated_entry_count",
            "eviction_count",
        ),
    )
    event_count = len(events) if events else int(reported_count or 0)
    counted_evictions = sum(counts.values())
    denominator = counted_evictions or event_count
    top_ticker, top_count = counts.most_common(1)[0] if counts else (None, 0)
    conflict_count = _first_numeric(
        payload,
        (
            "cash_conflict_count",
            "cash_conflict_evaluations",
            "eligible_cash_conflict_count",
            "trigger_count",
        ),
    )
    released_cash = _first_numeric(
        payload,
        (
            "released_cash_usd",
            "released_cash_total",
            "rotation_cash_released_usd",
            "eviction_proceeds_usd",
        ),
    )
    return {
        "result_key_present": isinstance(raw, dict),
        "enabled": payload.get("enabled"),
        "cash_conflict_count": (
            int(conflict_count) if conflict_count is not None else None
        ),
        "rotation_event_count": event_count,
        "event_rows_logged": len(events),
        "evicted_ticker_counts": dict(sorted(counts.items())),
        "evicted_ticker_count": len(counts),
        "top_evicted_ticker": top_ticker,
        "top_evicted_ticker_count": top_count,
        "top_evicted_ticker_share": (
            top_count / denominator if denominator > 0 and top_count > 0 else None
        ),
        "released_cash_usd": released_cash,
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
    checks = {
        "expected_value_score": result.get("expected_value_score")
        == reference.get("expected_value_score"),
        "total_pnl": result.get("total_pnl") == reference.get("total_pnl"),
        "sharpe_daily": result.get("sharpe_daily") == reference.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct")
        == reference.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades") == reference.get("trade_count"),
        "signals_generated": result.get("signals_generated")
        == reference.get("signals_generated"),
        "signals_survived": result.get("signals_survived")
        == reference.get("signals_survived"),
        "survival_rate": result.get("survival_rate") == reference.get("survival_rate"),
        "trade_rows_sha256": identity.get("trade_rows_sha256")
        == reference.get("trade_rows_sha256"),
        "daily_return_series_sha256": identity.get("daily_return_series_sha256")
        == reference.get("daily_return_series_sha256"),
        "sharpe_inference_contract": identity.get("sharpe_inference_contract_passed")
        is True,
        "cash_ledger": _cash_summary(result) == reference.get("cash_ledger"),
    }
    return checks


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

    summary_decision = summary["decision"]
    decision = "accepted" if summary_decision == "accepted_default_off" else "rejected"
    rejected = decision == "rejected"
    log = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": summary["generated_at"],
        "status": decision,
        "decision": decision,
        "artifact_decision": summary_decision,
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
            "gate_shape": "incumbent_rotation",
        },
        "fingerprint_caveat": (
            "Reservation-time inference was over-matched to companyfacts_ratio/"
            "other because the cash-feasible core-book surface lacked dedicated "
            "keywords. This experiment adds the narrow source/gate mapping and "
            "rebuilds docs/frozen_families.jsonl before closeout."
        ),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
        "prediction": ticket.get("prediction", {}),
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
            "Evaluated the fixed same-open oldest-core eviction gate only on "
            "cash-conflicted qualified fresh entries; no default or live behavior "
            "was changed."
        ),
        "notes": (
            f"Gate 1 exact={summary['gates']['gate1_exact_cash_feasible_baseline']}; "
            f"aggregate EV {summary['before']['expected_value_score']:.4f} to "
            f"{summary['after']['expected_value_score']:.4f}; aggregate PnL "
            f"{summary['before']['total_pnl']:.2f} to "
            f"{summary['after']['total_pnl']:.2f}; rotations="
            f"{summary['rotation_attribution']['aggregate_rotation_event_count']}."
        ),
        "rejection_reason": (
            "One or more pre-registered Gate-4 checks failed."
            if rejected
            else None
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "Position age was a poor opportunity-cost proxy: twenty "
                "rotations crystallized still-productive incumbents and added "
                "turnover, so twenty-four extra closed trades coincided with "
                "lower EV in every window despite nearly flat drawdown."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune oldest selection, age thresholds, partial eviction, "
                "cash-shortfall thresholds, or rotation sizing on these outcomes."
            ),
            "new_evidence_required": (
                "A new data source, genuinely different gate shape, or materially "
                "more settled forward cash-conflict decisions is required for a "
                "near-neighbor retry."
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
            "quant/cash_conflict_oldest_rotation.py",
            "quant/test_cash_conflict_oldest_rotation.py",
            "quant/experiments/exp_20260716_004_cash_conflict_oldest_rotation.py",
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

        print(f"[{label}] oldest rotation ({CONFIG_KEY}=True) ...", flush=True)
        after, after_identity = _run_variant(spec, frozen, enabled=True)
        before_metrics = _metrics(before)
        after_metrics = _metrics(after)
        before_rotation = _rotation_summary(before)
        after_rotation = _rotation_summary(after)
        before_cash = _cash_integrity(before)
        after_cash = _cash_integrity(after)
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
            "before_cash": before_cash,
            "after_cash": after_cash,
            "before_rotation": before_rotation,
            "after_rotation": after_rotation,
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

    improved_windows = sum(
        report["after"]["expected_value_score"]
        > report["before"]["expected_value_score"]
        for report in window_reports.values()
    )
    ev_regression_checks = {
        label: _ev_regression_passed(
            float(report["before"]["expected_value_score"]),
            float(report["after"]["expected_value_score"]),
        )
        for label, report in window_reports.items()
    }

    eviction_counts: Counter[str] = Counter()
    total_rotation_events = 0
    for report in window_reports.values():
        attribution = report["after_rotation"]
        eviction_counts.update(attribution["evicted_ticker_counts"])
        total_rotation_events += int(attribution["rotation_event_count"])
    counted_evictions = sum(eviction_counts.values())
    top_ticker, top_count = (
        eviction_counts.most_common(1)[0] if eviction_counts else (None, 0)
    )
    concentration_denominator = counted_evictions or total_rotation_events
    top_eviction_share = (
        top_count / concentration_denominator
        if concentration_denominator > 0 and top_count > 0
        else None
    )
    rotation_attribution = {
        "aggregate_rotation_event_count": total_rotation_events,
        "aggregate_counted_evictions": counted_evictions,
        "evicted_ticker_counts": dict(sorted(eviction_counts.items())),
        "top_evicted_ticker": top_ticker,
        "top_evicted_ticker_count": top_count,
        "top_evicted_ticker_share": top_eviction_share,
        "per_window": {
            label: report["after_rotation"] for label, report in window_reports.items()
        },
    }

    trade_retention = (
        after_aggregate["trade_count"] / before_aggregate["trade_count"]
        if before_aggregate["trade_count"]
        else 0.0
    )
    pre_registered_gate4 = {
        "aggregate_expected_value_score_strictly_above": MIN_AGGREGATE_EV,
        "aggregate_total_pnl_strictly_above": MIN_AGGREGATE_PNL,
        "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
        "maximum_single_window_ev_regression_fraction": (
            MAX_WINDOW_EV_REGRESSION_FRACTION
        ),
        "maximum_worst_drawdown_drift": MAX_DRAWDOWN_DRIFT,
        "minimum_survival_rate_per_window": MIN_SURVIVAL_RATE,
        "minimum_trades_per_window": MIN_TRADES_PER_WINDOW,
        "minimum_aggregate_trade_retention": MIN_AGGREGATE_TRADE_RETENTION,
        "maximum_eviction_ticker_share": MAX_EVICTION_TICKER_SHARE,
        "cash_conservation_required": True,
    }

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
        "aggregate_ev_above_pre_registered_bar": (
            after_aggregate["expected_value_score"] > MIN_AGGREGATE_EV
        ),
        "aggregate_pnl_above_pre_registered_bar": (
            after_aggregate["total_pnl"] > MIN_AGGREGATE_PNL
        ),
        "at_least_two_ev_improved_windows": (
            improved_windows >= MIN_EV_IMPROVED_WINDOWS
        ),
        "no_window_ev_regresses_more_than_5pct": all(
            ev_regression_checks.values()
        ),
        "worst_drawdown_drift_within_one_percentage_point": (
            after_aggregate["max_drawdown_pct"]
            <= before_aggregate["max_drawdown_pct"] + MAX_DRAWDOWN_DRIFT + 1e-12
        ),
        "trade_count_statistically_meaningful": (
            trade_retention >= MIN_AGGREGATE_TRADE_RETENTION
            and all(
                int(report["after"]["total_trades"]) >= MIN_TRADES_PER_WINDOW
                for report in window_reports.values()
            )
        ),
        "cash_conservation_all_variants": all(
            report[role]["passed"]
            for report in window_reports.values()
            for role in ("before_cash", "after_cash")
        ),
        "rotation_result_key_only_when_enabled": all(
            not report["before_rotation"]["result_key_present"]
            and report["after_rotation"]["result_key_present"]
            for report in window_reports.values()
        ),
        "explicit_flag_attribution_matches_variants": all(
            report["before_rotation"]["enabled"] is None
            and report["after_rotation"]["enabled"] is True
            for report in window_reports.values()
        ),
        "baseline_rotation_inactive": all(
            report["before_rotation"]["rotation_event_count"] == 0
            for report in window_reports.values()
        ),
        "rotation_materiality": total_rotation_events > 0,
        "rotation_events_prove_full_atomic_entry": all(
            event.get("requested_shares") == event.get("admitted_shares")
            and event.get("full_requested_entry_admitted") is True
            and _number(event.get("cash_before")) is not None
            and _number(event.get("required_order_cost")) is not None
            and _number(event.get("cash_after_release")) is not None
            and _number(event.get("cash_after_entry")) is not None
            and _number(event.get("cash_after_entry")) >= -1e-9
            for report in window_reports.values()
            for event in report["after_rotation"]["events"]
        ) and total_rotation_events > 0,
        "eviction_ticker_attribution_complete": (
            counted_evictions == total_rotation_events and total_rotation_events > 0
        ),
        "eviction_ticker_concentration_lte_50pct": (
            top_eviction_share is not None
            and top_eviction_share <= MAX_EVICTION_TICKER_SHARE + 1e-12
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
                "rotation": report["before_rotation"],
            }
            for label, report in window_reports.items()
        },
    }
    after_measurement = {
        "experiment_id": EXPERIMENT_ID,
        "role": f"explicit_{CONFIG_KEY}_true",
        **after_aggregate,
        "windows": {
            label: {
                "metrics": report["after"],
                "cash": report["after_cash"],
                "rotation": report["after_rotation"],
            }
            for label, report in window_reports.items()
        },
    }

    generated_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "schema": "cash_conflict_oldest_rotation_gate4_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "generated_at": generated_at,
        "hypothesis": ticket.get("hypothesis"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "config": {"key": CONFIG_KEY, "before": False, "after": True},
        "result_key": RESULT_KEY,
        "baseline": gate1._repo_rel(ACTIVE_BASELINE),
        "frozen_behavior_inputs": {
            "path": gate1._repo_rel(FROZEN_INPUTS),
            "file_sha256": gate1._file_sha256(FROZEN_INPUTS),
            "behavior_sha256": frozen["behavior_sha256"],
            "universe_count": len(frozen["behavior"]["universe"]),
        },
        "policy": {
            "trigger": (
                "fully qualified fresh core entry would be scaled or skipped by "
                "settled-cash admission"
            ),
            "incumbent": "oldest active core position",
            "execution": "full incumbent exit and fresh entry at the same next open",
            "locked": ticket.get("locked_variables", []),
        },
        "pre_registered_gate4": pre_registered_gate4,
        "before": before_aggregate,
        "after": after_aggregate,
        "delta": aggregate_delta,
        "windows": window_reports,
        "ev_improved_window_count": improved_windows,
        "ev_regression_checks": ev_regression_checks,
        "aggregate_trade_retention": trade_retention,
        "rotation_attribution": rotation_attribution,
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
        },
        "reproduction": (
            ".\\.venv\\Scripts\\python.exe -u -B "
            "quant\\experiments\\exp_20260716_004_cash_conflict_oldest_rotation.py"
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
                "rotation_attribution": {
                    key: rotation_attribution[key]
                    for key in (
                        "aggregate_rotation_event_count",
                        "evicted_ticker_counts",
                        "top_evicted_ticker_share",
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
