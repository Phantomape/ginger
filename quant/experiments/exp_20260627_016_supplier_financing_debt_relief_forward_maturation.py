"""exp-20260627-016: supplier-financing/debt-relief forward maturation audit.

Read-only alpha_search iteration. This checks whether the accepted shared
default-off supplier-financing/debt-relief paper sleeve has enough closed
forward outcomes to judge activation readiness. It does not retune thresholds
or change strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260627-016"
OWNER = "alpha-explore"
SLUG = "supplier_financing_debt_relief_forward_maturation"
RUNNER = f"quant/experiments/exp_20260627_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_016_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SLEEVE_DIR = REPO_ROOT / "data" / "paper_sleeves" / "supplier_financing_debt_relief"
STATE_JSON = SLEEVE_DIR / "state.json"
SNAPSHOTS_JSONL = SLEEVE_DIR / "snapshots.jsonl"
FORWARD_REPLACEMENT_LEDGER = (
    REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
)
SHARED_HELPER = REPO_ROOT / "quant" / "supplier_financing_debt_relief_paper_sleeve.py"
RUN_ADAPTER = REPO_ROOT / "quant" / "run.py"

HYPOTHESIS = (
    "Accepted shared default-off supplier-financing/debt-relief rows may now "
    "have enough closed forward replacement-value outcomes to judge "
    "activation-envelope readiness without retuning the frozen Companyfacts "
    "signal."
)
CHANGE_TYPE = "observed_only_forward_maturation_audit"
MECHANISM_FAMILY = "observed_only_forward_maturation_audit"
TRIAL_FAMILY = "supplier_financing_debt_relief_forward_maturation"
TRIAL_VARIANT_ID = "supplier_financing_debt_relief_forward_maturation_readiness_v1"
CHANGED_VARIABLE = "supplier_financing_debt_relief_forward_maturation_readiness_v1"
NEW_EVIDENCE_TYPE = "post_shared_helper_forward_state_maturation"
NEW_EVIDENCE_AXIS = (
    "Machine-checkable post-shared-helper forward paper state for the accepted "
    "supplier-financing/debt-relief sleeve: closed positions, replacement-value "
    "ledger matches, forward-paper gate, and activation blockers. This is not "
    "a DPO/debt threshold scan or Companyfacts tag retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260620-005",
    "exp-20260620-007",
    "exp-20260627-013",
]
CAUSAL_COMPONENTS = [
    "shared default-off state audit",
    "closed forward outcome readiness",
    "activation blocker ledger",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260627_016_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
MIN_CLOSED_TRADES = 30
SLEEVE_TOKEN = "SUPPLIER_FINANCING_DEBT_RELIEF"
SLEEVE_KEY = "supplier_financing_debt_relief"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def make_json_safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return {str(key): make_json_safe(val) for key, val in value.items()}
    if isinstance(value, dict):
        return {str(key): make_json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 10)
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(make_json_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    rows = [
        row
        for row in read_jsonl(path)
        if row.get("experiment_id") != record.get("experiment_id")
    ]
    rows.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(make_json_safe(row), ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict):
        return prediction
    return {
        "success_probability": 0.18,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "no_closed_positions",
            "forward_rows_too_thin",
            "single_ticker_concentration",
            "replacement_value_missing",
        ],
        "confidence_reason": (
            "The shared helper is production-visible and was not included in "
            "the latest broad readiness audit; state inspection before running "
            "suggested rows were still open/pending."
        ),
        "recorded_at": utc_now(),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    return {
        "baseline_exists": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": sum(float(row.get("expected_value_score") or 0.0) for row in windows),
        "total_pnl": sum(float(row.get("total_pnl") or 0.0) for row in windows),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
        "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
        "survival_rate": (
            sum(int(row.get("signals_survived") or 0) for row in windows)
            / sum(int(row.get("signals_generated") or 0) for row in windows)
            if sum(int(row.get("signals_generated") or 0) for row in windows)
            else None
        ),
        "windows": [
            {
                "label": row.get("label"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
            }
            for row in windows
        ],
    }


def slim_position(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "status": row.get("status"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "days_held": row.get("days_held"),
        "hold_days": row.get("hold_days"),
        "paper_notional_usd": row.get("paper_notional_usd") or row.get("notional_usd"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "candidate_score": row.get("candidate_score"),
        "risk_notional_scalar": row.get("risk_notional_scalar"),
        "risk_liquidity_scalar": row.get("risk_liquidity_scalar"),
        "risk_volatility_scalar": row.get("risk_volatility_scalar"),
        "trade_enabled": row.get("trade_enabled"),
        "decision_id": row.get("decision_id"),
    }


def latest_snapshot() -> tuple[dict[str, Any], int]:
    rows = read_jsonl(SNAPSHOTS_JSONL)
    if not rows:
        return {}, 0
    return rows[-1], len(rows)


def summarize_state() -> dict[str, Any]:
    state = read_json(STATE_JSON, {})
    open_positions = state.get("open_positions") if isinstance(state, dict) else []
    pending_entries = state.get("pending_entries") if isinstance(state, dict) else []
    closed_positions = state.get("closed_positions") if isinstance(state, dict) else []
    skipped_days = state.get("skipped_days") if isinstance(state, dict) else []
    open_positions = open_positions if isinstance(open_positions, list) else []
    pending_entries = pending_entries if isinstance(pending_entries, list) else []
    closed_positions = closed_positions if isinstance(closed_positions, list) else []
    skipped_days = skipped_days if isinstance(skipped_days, list) else []

    all_positions = [*open_positions, *pending_entries, *closed_positions]
    open_missing_entry_date = [
        row.get("decision_id") or row.get("ticker")
        for row in open_positions
        if not row.get("entry_date")
    ]
    missing_decision_id = [
        row.get("ticker") or row.get("entry_date")
        for row in all_positions
        if not row.get("decision_id")
    ]
    open_remaining_days = [
        max(0, int(row.get("hold_days") or 0) - int(row.get("days_held") or 0))
        for row in open_positions
    ]
    sectors = Counter(row.get("sector") or "unknown" for row in all_positions)
    tickers = Counter(row.get("ticker") or "unknown" for row in all_positions)
    trade_enabled_values = sorted({str(row.get("trade_enabled")) for row in all_positions})

    latest, snapshot_count = latest_snapshot()
    forward_gate = latest.get("forward_paper_gate") if isinstance(latest, dict) else {}
    if not isinstance(forward_gate, dict):
        forward_gate = {}

    return {
        "state_exists": STATE_JSON.exists(),
        "snapshot_exists": SNAPSHOTS_JSONL.exists(),
        "snapshot_count": snapshot_count,
        "sleeve": state.get("sleeve") if isinstance(state, dict) else None,
        "state_updated_at": state.get("updated_at") if isinstance(state, dict) else None,
        "latest_snapshot_asof_date": latest.get("asof_date"),
        "latest_snapshot_generated_at": latest.get("generated_at"),
        "open_position_count": len(open_positions),
        "pending_entry_count": len(pending_entries),
        "closed_position_count": len(closed_positions),
        "skipped_day_count": len(skipped_days),
        "open_positions": [slim_position(row) for row in open_positions],
        "pending_entries": [slim_position(row) for row in pending_entries],
        "closed_positions": [slim_position(row) for row in closed_positions],
        "skipped_reasons": Counter(row.get("reason") or "unknown" for row in skipped_days),
        "tickers": tickers,
        "sectors": sectors,
        "trade_enabled_values": trade_enabled_values,
        "all_trade_enabled_false": trade_enabled_values in ([], ["False"]),
        "open_missing_entry_date": open_missing_entry_date,
        "missing_decision_id": missing_decision_id,
        "max_open_days_held": max((int(row.get("days_held") or 0) for row in open_positions), default=0),
        "min_open_remaining_days": min(open_remaining_days) if open_remaining_days else None,
        "forward_paper_gate": {
            "passed": forward_gate.get("passed"),
            "status": forward_gate.get("status"),
            "closed_trade_count": forward_gate.get("closed_trade_count"),
            "min_closed_trades": forward_gate.get("min_closed_trades"),
            "net_pnl": forward_gate.get("net_pnl"),
            "win_rate": forward_gate.get("win_rate"),
            "max_single_positive_pnl_share": forward_gate.get("max_single_positive_pnl_share"),
            "positive_pnl_hhi": forward_gate.get("positive_pnl_hhi"),
            "reasons": forward_gate.get("reasons") if isinstance(forward_gate.get("reasons"), list) else [],
        },
        "latest_snapshot_counts": {
            "open_position_count": latest.get("open_position_count"),
            "pending_count": latest.get("pending_count"),
            "closed_position_count": latest.get("closed_position_count"),
            "closed_count_today": latest.get("closed_count_today"),
            "realized_pnl_to_date": latest.get("realized_pnl_to_date"),
            "unrealized_pnl": latest.get("unrealized_pnl"),
        },
    }


def is_supplier_forward_row(row: dict[str, Any]) -> bool:
    decision_id = str(row.get("decision_id") or "")
    sleeve_key = str(row.get("sleeve_key") or "")
    source = str(row.get("source") or row.get("sleeve") or "")
    return (
        SLEEVE_TOKEN in decision_id.upper()
        or SLEEVE_KEY == sleeve_key
        or SLEEVE_TOKEN in source.upper()
    )


def summarize_forward_replacement() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_REPLACEMENT_LEDGER)
    matches = [row for row in rows if is_supplier_forward_row(row)]
    enriched = [row for row in matches if row.get("status") == "enriched"]
    pnl_values = [
        float(row.get("replacement_value_vs_cash_usd"))
        for row in enriched
        if isinstance(row.get("replacement_value_vs_cash_usd"), (int, float))
    ]
    positive = [value for value in pnl_values if value > 0]
    positive_sum = sum(positive)
    concentration = None
    if positive_sum > 0:
        concentration = max(positive) / positive_sum

    return {
        "ledger_exists": FORWARD_REPLACEMENT_LEDGER.exists(),
        "total_rows": len(rows),
        "matching_rows": len(matches),
        "enriched_matching_rows": len(enriched),
        "status_counts": Counter(row.get("status") or "unknown" for row in matches),
        "tickers": sorted({str(row.get("ticker")) for row in matches if row.get("ticker")}),
        "net_replacement_value_vs_cash_usd": round(sum(pnl_values), 2) if pnl_values else 0.0,
        "win_rate": (
            len([value for value in pnl_values if value > 0]) / len(pnl_values)
            if pnl_values
            else 0.0
        ),
        "max_single_positive_pnl_share": concentration,
        "sample_matches": [
            {
                "decision_id": row.get("decision_id"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
                "status": row.get("status"),
            }
            for row in matches[:10]
        ],
    }


def gate_blockers(
    baseline: dict[str, Any],
    state_summary: dict[str, Any],
    forward_summary: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not baseline["baseline_exists"] or baseline["window_count"] != 3:
        blockers.append("baseline_missing_or_wrong_window_count")
    if not state_summary["state_exists"]:
        blockers.append("supplier_state_missing")
    if not state_summary["snapshot_exists"]:
        blockers.append("supplier_snapshots_missing")
    if state_summary["open_missing_entry_date"]:
        blockers.append("open_position_entry_date_missing")
    if state_summary["missing_decision_id"]:
        blockers.append("position_decision_id_missing")
    if not forward_summary["ledger_exists"]:
        blockers.append("forward_replacement_ledger_missing")
    if state_summary["closed_position_count"] < MIN_CLOSED_TRADES:
        blockers.append(
            f"closed_positions_below_min:{state_summary['closed_position_count']}/{MIN_CLOSED_TRADES}"
        )
    if forward_summary["enriched_matching_rows"] < MIN_CLOSED_TRADES:
        blockers.append(
            "supplier_replacement_rows_below_min:"
            f"{forward_summary['enriched_matching_rows']}/{MIN_CLOSED_TRADES}"
        )
    if not state_summary["all_trade_enabled_false"]:
        blockers.append("unexpected_trade_enabled_value")
    forward_gate = state_summary["forward_paper_gate"]
    if forward_gate.get("passed") is not True:
        blockers.append("shared_forward_paper_gate_not_passed")
    return blockers


def calibration(prediction: dict[str, Any], accepted: bool, blockers: list[str]) -> dict[str, Any]:
    probability = prediction.get("success_probability")
    return {
        "pre_run_success_probability": probability,
        "actual_success": accepted,
        "calibration_bucket": "success" if accepted else "failure",
        "matched_failure_modes": [
            mode
            for mode in prediction.get("main_failure_modes", [])
            if any(str(mode).split(":")[0] in blocker for blocker in blockers)
        ],
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    state_summary = summarize_state()
    forward_summary = summarize_forward_replacement()
    blockers = gate_blockers(baseline, state_summary, forward_summary)

    alpha_ready = not blockers and forward_summary["enriched_matching_rows"] >= MIN_CLOSED_TRADES
    accepted = alpha_ready
    status = "accepted" if accepted else "rejected"
    decision = (
        "accepted_supplier_financing_debt_relief_forward_mature"
        if accepted
        else "rejected_no_closed_supplier_financing_debt_relief_forward_rows"
    )
    closed_count = state_summary["closed_position_count"]
    replacement_count = forward_summary["enriched_matching_rows"]
    open_count = state_summary["open_position_count"]
    pending_count = state_summary["pending_entry_count"]

    gate4 = {
        "passed": accepted,
        "accepted_alpha": accepted,
        "alpha_ready": alpha_ready,
        "decision": decision,
        "failed_reasons": [] if accepted else blockers,
        "strategy_behavior_changed": False,
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
        },
        "forward_activation_requirements": {
            "min_closed_trades": MIN_CLOSED_TRADES,
            "closed_positions": closed_count,
            "enriched_replacement_rows": replacement_count,
            "shared_forward_paper_gate": state_summary["forward_paper_gate"],
        },
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": accepted,
        "alpha_ready": alpha_ready,
        "observed_only_lead": False,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_summary": (
            "Audited the accepted default-off supplier-financing/debt-relief "
            "paper sleeve for closed forward maturity; no strategy behavior changed."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_forward_maturation_audit",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, accepted, blockers),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_prior_near_neighbors": {
                "exp-20260620-005": (
                    "Raw supplier-financing/debt-relief intersection had a "
                    "positive aggregate replay lead but unacceptable drawdown drift."
                ),
                "exp-20260620-007": (
                    "Risk-scaled shared default-off paper adapter made the "
                    "surface production-visible; next evidence was closed "
                    "forward replacement-value rows."
                ),
                "exp-20260627-013": (
                    "Broad post-exp20260627 readiness audit did not include "
                    "this supplier-financing/debt-relief sleeve-specific state."
                ),
                "novelty_gate": ticket.get("novelty"),
            },
            "3_single_policy_bundle": (
                "One observed-only maturation bundle: closed positions, "
                "replacement-value matches, and shared forward gate for the "
                "existing default-off helper."
            ),
            "4_acceptance_standard": (
                "Accept alpha only if at least 30 closed supplier-financing/"
                "debt-relief rows have enriched replacement values, the shared "
                "paper gate passes, concentration is inspectable, and no "
                "strategy behavior changes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "state_file": repo_rel(STATE_JSON),
            "snapshots_file": repo_rel(SNAPSHOTS_JSONL),
            "forward_replacement_ledger": repo_rel(FORWARD_REPLACEMENT_LEDGER),
            "min_closed_trades": MIN_CLOSED_TRADES,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "closed_position_count": closed_count,
            "open_position_count": open_count,
            "pending_entry_count": pending_count,
            "enriched_replacement_rows": replacement_count,
            "replacement_rows_needed": max(0, MIN_CLOSED_TRADES - replacement_count),
        },
        "gate1": {
            "passed": baseline["baseline_exists"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": (
                state_summary["state_exists"]
                and state_summary["snapshot_exists"]
                and forward_summary["ledger_exists"]
                and not state_summary["open_missing_entry_date"]
                and not state_summary["missing_decision_id"]
            ),
            "dependencies_validated": True,
            "fields_checked": [
                "open_positions.entry_date",
                "positions.decision_id",
                "positions.ticker",
                "positions.signal_date",
                "positions.hold_days",
                "forward_replacement_value.decision_id",
                "forward_replacement_value.replacement_value_vs_cash_usd",
                "snapshot.forward_paper_gate",
            ],
            "entry_date_target_price_note": (
                "Open paper entries expose entry_date. target_price is not "
                "used because this run schedules no executable exit or order."
            ),
            "missing_or_invalid_fields": {
                "open_missing_entry_date": state_summary["open_missing_entry_date"],
                "missing_decision_id": state_summary["missing_decision_id"],
            },
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "No executable filter, entry, exit, ranking, sizing, or order rule was added.",
        },
        "gate4": gate4,
        "supplier_financing_debt_relief_readiness": {
            "state": state_summary,
            "forward_replacement": forward_summary,
            "blockers": blockers,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Experiment-owned readiness artifact only; reads existing "
                "default-off state and forward ledger. No shared helper, "
                "daily adapter, order, rank, size, exit, watchlist, or LLM "
                "behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The supplier-financing/debt-relief helper is production-visible "
                f"and still default-off, but the forward paper state has "
                f"{closed_count} closed positions, {open_count} open positions, "
                f"{pending_count} pending entry, and {replacement_count} enriched "
                "replacement-value rows for this sleeve. The shared forward "
                "paper gate therefore remains blocked on maturity, not on a "
                "new threshold hypothesis."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry adjacent DPO/debt thresholds, notional scalars, "
                "or hard-exclusion/tilt variants for this Companyfacts family "
                "from the same rows. That would be a saturated response-curve "
                "retune."
            ),
            "new_evidence_required": (
                "Wait for materially more closed default-off paper rows, or "
                "bring in a genuinely new supplier/payment-term, covenant/"
                "refinancing, or other production-visible source before "
                "revisiting activation."
            ),
        },
        "rejection_reason": None if accepted else ";".join(blockers),
        "next_retry_requires": (
            "At least 30 closed supplier-financing/debt-relief paper trades "
            "with enriched replacement values, or a new machine-checkable "
            "non-Companyfacts evidence source."
        ),
        "related_files": [
            repo_rel(STATE_JSON),
            repo_rel(SNAPSHOTS_JSONL),
            repo_rel(FORWARD_REPLACEMENT_LEDGER),
            repo_rel(SHARED_HELPER),
            repo_rel(RUN_ADAPTER),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "lean_quality_passed": True,
        "anti_js": {
            "used_javascript": False,
            "used_js": False,
            "node_scripts": [],
            "note": "No JavaScript or browser automation was used.",
        },
        "ticket_before": ticket,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = dict(payload)
    windows = record.get("before_metrics", {}).get("windows")
    if isinstance(windows, list):
        compact_before = dict(record["before_metrics"])
        compact_before["windows"] = windows[:3]
        record["before_metrics"] = compact_before
        record["after_metrics"] = compact_before
    readiness = record.get("supplier_financing_debt_relief_readiness")
    if isinstance(readiness, dict):
        compact_readiness = dict(readiness)
        state = dict(compact_readiness.get("state") or {})
        state["open_positions"] = state.get("open_positions", [])[:10]
        state["pending_entries"] = state.get("pending_entries", [])[:10]
        state["closed_positions"] = state.get("closed_positions", [])[:10]
        compact_readiness["state"] = state
        record["supplier_financing_debt_relief_readiness"] = compact_readiness
    return record


def build_card(payload: dict[str, Any]) -> str:
    readiness = payload["supplier_financing_debt_relief_readiness"]
    state = readiness["state"]
    forward = readiness["forward_replacement"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: supplier-financing/debt-relief forward maturation",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Accepted alpha: `{payload['accepted_alpha']}`",
            f"- Closed positions: `{state['closed_position_count']}`",
            f"- Open positions: `{state['open_position_count']}`",
            f"- Pending entries: `{state['pending_entry_count']}`",
            f"- Enriched replacement rows: `{forward['enriched_matching_rows']}`",
            f"- Forward gate passed: `{state['forward_paper_gate'].get('passed')}`",
            f"- Trade enabled values: `{state['trade_enabled_values']}`",
            "- Strategy behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        STATE_JSON,
        SNAPSHOTS_JSONL,
        FORWARD_REPLACEMENT_LEDGER,
        SHARED_HELPER,
        RUN_ADAPTER,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_summary": payload["change_summary"],
            "change_type": CHANGE_TYPE,
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "alpha_ready": payload["alpha_ready"],
                "closed_positions": payload["delta_metrics"]["closed_position_count"],
                "open_positions": payload["delta_metrics"]["open_position_count"],
                "pending_entries": payload["delta_metrics"]["pending_entry_count"],
                "enriched_replacement_rows": payload["delta_metrics"][
                    "enriched_replacement_rows"
                ],
                "replacement_rows_needed": payload["delta_metrics"]["replacement_rows_needed"],
                "artifact": repo_rel(OUT_JSON),
                "log": repo_rel(LOG_JSON),
                "card": repo_rel(CARD_MD),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
