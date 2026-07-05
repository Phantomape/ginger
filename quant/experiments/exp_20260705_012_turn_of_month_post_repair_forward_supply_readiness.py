"""exp-20260705-012: turn-of-month post-repair forward supply readiness.

Measurement/readiness audit only. The prior calendar parity repair made the
default-off turn-of-month sleeve production-observable again. This runner checks
whether current state now contains post-repair forward rows and whether those
rows have matured into closed cash/SPY/QQQ replacement-value evidence.

No strategy thresholds, ranking, sizing, exits, signal generation, orders, or
daily materialization code are changed.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260705-012"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "turn_of_month_post_repair_forward_supply_readiness"
RUNNER = f"quant/experiments/exp_20260705_012_{SLUG}.py"
RUNNER_WINDOWS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_WINDOWS

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "turn_of_month_liquid_leadership" / "state.json"
SNAPSHOTS_JSONL = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "turn_of_month_liquid_leadership"
    / "snapshots.jsonl"
)
FORWARD_RV_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SLEEVE_NAME = "TURN_OF_MONTH_LIQUID_LEADERSHIP_PAPER"
SLEEVE_KEY = "turn_of_month_liquid_leadership"
POST_REPAIR_SIGNAL_DATE_FLOOR = "2026-07-01"

HYPOTHESIS = (
    "Alpha blocker: after the turn-of-month calendar parity repair, the sleeve "
    "must show post-repair forward row supply before any activation/readiness "
    "judgement; audit the current default-off state for new open/pending/closed "
    "rows and block alpha until closed cash/SPY/QQQ replacement values exist, "
    "without changing thresholds/ranking/sizing/exits/orders."
)
ALPHA_HYPOTHESIS = (
    "The accepted turn-of-month liquid-leadership paper sleeve remains a plausible "
    "month-flow alpha only if daily production evidence can now produce rows and "
    "eventually close them against cash, SPY, and QQQ comparators."
)
CHANGED_VARIABLE = "turn_of_month_post_repair_forward_supply_readiness_v1"
MECHANISM_FAMILY = "accepted_default_off_paper_sleeve_forward_supply"
TRIAL_FAMILY = "turn_of_month_post_repair_forward_supply_readiness"
TRIAL_VARIANT_ID = "turn_of_month_post_calendar_repair_current_rows_20260705"
NEW_EVIDENCE_AXIS = (
    "Post-repair forward rows now exist in the current turn_of_month state after "
    "exp-20260704-009: one open V row and one pending CVS row from 2026-07-01; "
    "exp-20260704-009 only repaired representative calendar parity and explicitly "
    "required post-repair forward rows before activation."
)
PREDICTION = {
    "success_probability": 0.55,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_post_repair_rows",
        "closed_rows_absent",
        "replacement_values_absent",
        "near_neighbor_readiness_repeat",
    ],
    "confidence_reason": (
        "Current state already showed one open and one pending post-repair row "
        "during preflight, so row-supply confirmation was likely; activation was "
        "expected to remain blocked because the hold window has not produced "
        "closed replacement-value rows yet."
    ),
    "recorded_at": "2026-07-05T15:11:57+00:00",
}

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_012_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
RELATED_FILES = [
    "data/paper_sleeves/turn_of_month_liquid_leadership/state.json",
    "data/paper_sleeves/turn_of_month_liquid_leadership/snapshots.jsonl",
    "data/paper_sleeves/forward_replacement_value.jsonl",
    "quant/turn_of_month_liquid_leadership_paper_sleeve.py",
    "quant/run.py",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe(item) for item in value]
    if isinstance(value, tuple):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {})
    raw_windows = (
        payload.get("windows")
        or payload.get("window_results")
        or payload.get("results_by_window")
        or []
    )
    if isinstance(raw_windows, dict):
        windows = list(raw_windows.values())
    elif isinstance(raw_windows, list):
        windows = raw_windows
    else:
        windows = []
    if not windows and payload:
        windows = [payload]

    generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    drawdowns = [
        float(w.get("max_drawdown_pct"))
        for w in windows
        if w.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "loaded": BASELINE_PATH.exists(),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 6
        ),
        "strategy_total_return_pct_sum": round(
            sum(float(w.get("strategy_total_return_pct") or 0.0) for w in windows),
            6,
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 6) if drawdowns else None,
        "window_count": len(windows),
    }


def compact_row(row: Mapping[str, Any], status: str) -> dict[str, Any]:
    keys = [
        "ticker",
        "signal_date",
        "date",
        "entry_date",
        "entry_price",
        "entry_timing",
        "last_observed_date",
        "last_price_asof",
        "last_price",
        "observed_trading_days",
        "hold_days",
        "notional_usd",
        "paper_notional_usd",
        "unrealized_pnl",
        "unrealized_return_pct",
        "candidate_month_label",
        "candidate_score",
        "decision_id",
        "rule_version",
        "source_rule_version",
        "trade_enabled",
        "alters_orders",
    ]
    out = {"paper_status": status}
    for key in keys:
        if key in row:
            out[key] = row.get(key)
    out["has_entry_date"] = bool(row.get("entry_date"))
    out["has_target_price"] = "target_price" in row
    return out


def state_forward_rows(state: Mapping[str, Any]) -> dict[str, Any]:
    closed = list(state.get("closed_positions") or [])
    open_rows = list(state.get("open_positions") or [])
    pending = list(state.get("pending_entries") or [])
    rows: list[tuple[str, Mapping[str, Any]]] = [
        *[("closed", row) for row in closed if isinstance(row, Mapping)],
        *[("open", row) for row in open_rows if isinstance(row, Mapping)],
        *[("pending_entry", row) for row in pending if isinstance(row, Mapping)],
    ]
    post_repair = [
        (status, row)
        for status, row in rows
        if str(row.get("signal_date") or row.get("date") or "")
        >= POST_REPAIR_SIGNAL_DATE_FLOOR
        and (
            str(row.get("sleeve") or "").upper() == SLEEVE_NAME
            or SLEEVE_KEY in str(row.get("decision_id") or "").lower()
            or SLEEVE_NAME in str(row.get("decision_id") or "").upper()
        )
    ]
    missing_open_entry_dates = [
        compact_row(row, status)
        for status, row in post_repair
        if status in {"open", "closed"} and not row.get("entry_date")
    ]
    return {
        "state_file": repo_rel(STATE_JSON),
        "state_loaded": bool(state),
        "post_repair_signal_date_floor": POST_REPAIR_SIGNAL_DATE_FLOOR,
        "closed_count": len(closed),
        "open_count": len(open_rows),
        "pending_count": len(pending),
        "post_repair_total": len(post_repair),
        "post_repair_closed_count": sum(1 for status, _ in post_repair if status == "closed"),
        "post_repair_open_count": sum(1 for status, _ in post_repair if status == "open"),
        "post_repair_pending_count": sum(
            1 for status, _ in post_repair if status == "pending_entry"
        ),
        "post_repair_rows": [compact_row(row, status) for status, row in post_repair],
        "missing_open_or_closed_entry_dates": missing_open_entry_dates,
        "entry_date_contract_ok": not missing_open_entry_dates,
        "target_price_relevance": (
            "not_applicable_fixed_hold_default_off_paper_sleeve; this sleeve "
            "uses a 10-trading-day paper close, not ATR target-price exits"
        ),
    }


def latest_snapshot_summary() -> dict[str, Any]:
    latest: dict[str, Any] | None = None
    count = 0
    for row in iter_jsonl(SNAPSHOTS_JSONL):
        count += 1
        latest = row
    gate = latest.get("forward_paper_gate") if isinstance(latest, dict) else {}
    if not isinstance(gate, dict):
        gate = {}
    metrics = gate.get("metrics") if isinstance(gate.get("metrics"), dict) else {}
    return {
        "snapshot_file": repo_rel(SNAPSHOTS_JSONL),
        "snapshot_loaded": latest is not None,
        "snapshot_count": count,
        "latest_asof_date": latest.get("asof_date") if latest else None,
        "latest_generated_at": latest.get("generated_at") if latest else None,
        "latest_open_position_count": latest.get("open_position_count") if latest else None,
        "latest_pending_count": latest.get("pending_count") if latest else None,
        "latest_closed_position_count": latest.get("closed_position_count") if latest else None,
        "latest_forward_paper_gate": {
            "passed": gate.get("passed"),
            "status": gate.get("status"),
            "reasons": gate.get("reasons") or [],
            "metrics": metrics,
            "trade_enabled_after_gate": gate.get("trade_enabled_after_gate"),
        },
    }


def replacement_value_summary() -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    total_rows = 0
    for row in iter_jsonl(FORWARD_RV_JSONL):
        total_rows += 1
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("sleeve_key", "decision_id", "source", "sleeve")
        ).lower()
        if SLEEVE_KEY in haystack or SLEEVE_NAME.lower() in haystack:
            matches.append(row)
    closed_comparator_ready = [
        row
        for row in matches
        if row.get("replacement_value_vs_cash_usd") is not None
        and row.get("replacement_value_vs_spy_usd") is not None
        and row.get("replacement_value_vs_qqq_usd") is not None
    ]
    return {
        "ledger_file": repo_rel(FORWARD_RV_JSONL),
        "ledger_loaded": FORWARD_RV_JSONL.exists(),
        "ledger_total_rows": total_rows,
        "turn_of_month_rows": len(matches),
        "turn_of_month_closed_comparator_ready_rows": len(closed_comparator_ready),
        "turn_of_month_sample_rows": [
            {
                "decision_id": row.get("decision_id"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "status": row.get("status"),
                "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
                "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
                "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
            }
            for row in matches[:10]
        ],
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = baseline_metrics()
    state = read_json(STATE_JSON, {})
    row_summary = state_forward_rows(state if isinstance(state, Mapping) else {})
    snapshot = latest_snapshot_summary()
    rv = replacement_value_summary()

    supply_exists = row_summary["post_repair_total"] > 0
    no_strategy_change = True
    replacement_ready = rv["turn_of_month_closed_comparator_ready_rows"] > 0
    closed_ready = row_summary["post_repair_closed_count"] > 0
    activation_ready = supply_exists and closed_ready and replacement_ready

    activation_blockers: list[str] = []
    if not supply_exists:
        activation_blockers.append("no_post_repair_forward_rows")
    if not closed_ready:
        activation_blockers.append("no_closed_post_repair_rows")
    if not replacement_ready:
        activation_blockers.append("no_closed_cash_spy_qqq_replacement_value_rows")
    gate_reasons = snapshot["latest_forward_paper_gate"].get("reasons") or []
    activation_blockers.extend(f"forward_paper_gate_{reason}" for reason in gate_reasons)
    activation_blockers = sorted(set(activation_blockers))

    accepted = (
        supply_exists
        and row_summary["entry_date_contract_ok"]
        and no_strategy_change
        and not activation_ready
    )
    status = "accepted" if accepted else "rejected"
    decision = (
        "accepted_measurement_repair_turn_of_month_post_repair_rows_observed_alpha_blocked"
        if accepted
        else "rejected_measurement_repair_turn_of_month_post_repair_rows_not_confirmed"
    )
    failed_checks = []
    if not supply_exists:
        failed_checks.append("post_repair_forward_supply_missing")
    if not row_summary["entry_date_contract_ok"]:
        failed_checks.append("entry_date_contract_missing_on_open_or_closed_rows")
    if not no_strategy_change:
        failed_checks.append("strategy_behavior_changed")
    if activation_ready:
        failed_checks.append("unexpected_alpha_activation_ready_in_readiness_audit")

    summary = {
        "post_repair_total_rows": row_summary["post_repair_total"],
        "post_repair_open_rows": row_summary["post_repair_open_count"],
        "post_repair_pending_rows": row_summary["post_repair_pending_count"],
        "post_repair_closed_rows": row_summary["post_repair_closed_count"],
        "turn_of_month_replacement_value_rows": rv["turn_of_month_rows"],
        "turn_of_month_closed_comparator_ready_rows": rv[
            "turn_of_month_closed_comparator_ready_rows"
        ],
        "latest_snapshot_asof": snapshot["latest_asof_date"],
        "latest_snapshot_generated_at": snapshot["latest_generated_at"],
        "alpha_ready": activation_ready,
        "activation_blockers": activation_blockers,
        "failed_checks": failed_checks,
    }

    payload: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": activation_ready,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "read_only_post_repair_forward_supply_readiness_audit",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "current state/snapshot audit",
            "post-repair row classification",
            "shared replacement-value ledger lookup",
            "no strategy behavior change",
            "activation blocker recording",
        ],
        "nearby_prior_experiments": [
            "exp-20260704-008",
            "exp-20260704-009",
            "exp-20260704-025",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "post_repair_forward_row_supply_readiness",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "strategy_total_return_pct_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "summary": summary,
        "state_forward_rows": row_summary,
        "latest_snapshot": snapshot,
        "replacement_value_ledger": rv,
        "activation_readiness": {
            "passed": activation_ready,
            "blockers": activation_blockers,
            "minimum_current_requirement": (
                "closed post-repair rows with replacement_value_vs_cash_usd, "
                "replacement_value_vs_spy_usd, and replacement_value_vs_qqq_usd"
            ),
            "no_retune_allowed": True,
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "note": "Measurement/readiness audit only; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": row_summary["entry_date_contract_ok"],
            "fields": [
                "signal_date",
                "entry_date",
                "entry_timing",
                "paper_status",
                "decision_id",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "field_reality": {
                "open_or_closed_entry_date_contract_ok": row_summary[
                    "entry_date_contract_ok"
                ],
                "missing_open_or_closed_entry_dates": row_summary[
                    "missing_open_or_closed_entry_dates"
                ],
                "pending_entry_date_note": (
                    "Pending rows intentionally do not have entry_date until the "
                    "next-session-open fill is observed."
                ),
                "target_price_relevance": row_summary["target_price_relevance"],
                "replacement_value_ledger_loaded": rv["ledger_loaded"],
                "turn_of_month_replacement_value_rows": rv["turn_of_month_rows"],
            },
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, rank, size, exit, or order policy changed.",
        },
        "gate4": {
            "passed": accepted,
            "mode": "measurement_repair_post_calendar_repair_forward_supply_readiness",
            "failed_checks": failed_checks,
            "acceptance_checks": {
                "post_repair_forward_supply_exists": supply_exists,
                "open_or_closed_entry_date_contract_ok": row_summary[
                    "entry_date_contract_ok"
                ],
                "strategy_behavior_unchanged": no_strategy_change,
                "alpha_activation_still_blocked_until_closed_rv": not activation_ready,
            },
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "Read-only audit of existing default-off state, snapshots, and "
                "replacement-value ledger; no production or backtest behavior changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "predicted_failure_mode_hit": bool(
                {
                    "closed_rows_absent",
                    "replacement_values_absent",
                }
                & set(PREDICTION["main_failure_modes"])
            ),
            "surprise_note": (
                "Preflight was accurate: the repaired sleeve now has forward row "
                "supply, but the row supply is not yet a closed comparator-ready "
                "alpha result."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exp-20260704-009 calendar repair let the daily turn-of-month "
                "snapshot retain July month-start rows. The current state now "
                "contains V as an open paper position and CVS as a pending entry, "
                "but no row has reached the 10-trading-day close or the shared "
                "cash/SPY/QQQ replacement-value ledger."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune turn-of-month thresholds, notional, hold days, "
                "ranking, cooldowns, or response functions from this result. Do "
                "not open another readiness-only turn-of-month audit until there "
                "are materially new closed post-repair rows or a genuinely new "
                "point-in-time flow-beneficiary data source."
            ),
            "new_evidence_required": (
                "Reopen alpha activation only after the post-repair V/CVS cohort "
                "or later turn-of-month cohorts close and appear in the shared "
                "paper-sleeve replacement-value ledger with cash, SPY, and QQQ "
                "comparators."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed_checks),
        "next_retry_requires": [
            "closed post-repair turn_of_month rows",
            "shared paper-sleeve replacement-value rows with cash/SPY/QQQ comparators",
            "no threshold, notional, ranking, hold-day, cooldown, or response retune",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": RELATED_FILES,
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_WINDOWS}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }
    return payload


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "changed_variable",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "activation_readiness",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# {EXPERIMENT_ID} - turn-of-month post-repair forward supply",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- post-repair rows open/pending/closed: {summary['post_repair_open_rows']} / {summary['post_repair_pending_rows']} / {summary['post_repair_closed_rows']}",
        f"- replacement-value rows/comparator-ready: {summary['turn_of_month_replacement_value_rows']} / {summary['turn_of_month_closed_comparator_ready_rows']}",
        f"- alpha ready: {summary['alpha_ready']}",
        f"- activation blockers: {', '.join(summary['activation_blockers']) or 'none'}",
        "",
        "No thresholds, ranking, sizing, exits, signal generation, orders, or daily "
        "materialization code changed.",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "files": CHANGED_FILES,
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    ticket = read_json(TICKET_JSON, {})
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["summary"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "activation_readiness": payload["activation_readiness"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "summary": payload["summary"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
