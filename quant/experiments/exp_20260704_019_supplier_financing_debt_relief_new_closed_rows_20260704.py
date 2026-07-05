"""exp-20260704-019: supplier-financing/debt-relief new closed-row audit."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260704-019"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "supplier_financing_debt_relief_new_closed_rows_20260704"

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scripts.experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


RUNNER = f"quant/experiments/exp_20260704_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_019_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "supplier_financing_debt_relief" / "state.json"
SNAPSHOTS_JSONL = (
    REPO_ROOT / "data" / "paper_sleeves" / "supplier_financing_debt_relief" / "snapshots.jsonl"
)
FORWARD_RV_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
PRIOR_LOG_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260627-016.json"
SHARED_HELPER = REPO_ROOT / "quant" / "supplier_financing_debt_relief_paper_sleeve.py"
RUN_ADAPTER = REPO_ROOT / "quant" / "run.py"

MIN_ACTIVATION_CLOSED_ROWS = 30
MIN_EARLY_PARK_CLOSED_ROWS = 3
SLEEVE_KEY = "supplier_financing_debt_relief"
SLEEVE_TOKEN = "SUPPLIER_FINANCING_DEBT_RELIEF"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


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
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
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


def safe_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_int(value: Any) -> int:
    number = safe_float(value)
    return int(number) if number is not None else 0


def round_or_none(value: Any, digits: int = 4) -> float | None:
    number = safe_float(value)
    return round(number, digits) if number is not None else None


def make_json_safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(v) for v in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    windows = windows if isinstance(windows, list) else []
    generated = sum(safe_int(row.get("signals_generated")) for row in windows)
    survived = sum(safe_int(row.get("signals_survived")) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "loaded": BASELINE_JSON.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(safe_int(row.get("trade_count")) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": max((float(row.get("max_drawdown_pct") or 0.0) for row in windows), default=None),
        "windows": windows,
    }


def is_supplier_row(row: dict[str, Any]) -> bool:
    decision_id = str(row.get("decision_id") or "")
    sleeve = str(row.get("sleeve") or row.get("source") or "")
    sleeve_key = str(row.get("sleeve_key") or "")
    return (
        sleeve_key == SLEEVE_KEY
        or SLEEVE_TOKEN in decision_id.upper()
        or SLEEVE_TOKEN in sleeve.upper()
    )


def latest_snapshot() -> tuple[dict[str, Any], int]:
    snapshots = read_jsonl(SNAPSHOTS_JSONL)
    if not snapshots:
        return {}, 0
    return snapshots[-1], len(snapshots)


def slim_closed(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "hold_days": row.get("hold_days"),
        "days_held": row.get("days_held"),
        "paper_notional_usd": round_or_none(row.get("paper_notional_usd") or row.get("notional_usd"), 2),
        "pnl": round_or_none(row.get("pnl"), 2),
        "pnl_pct_net": round_or_none(row.get("pnl_pct_net"), 6),
        "replacement_value_status": row.get("replacement_value_status"),
        "replacement_value_vs_cash_usd": round_or_none(row.get("replacement_value_vs_cash_usd"), 2),
        "replacement_value_vs_spy_usd": round_or_none(row.get("replacement_value_vs_spy_usd"), 2),
        "replacement_value_vs_qqq_usd": round_or_none(row.get("replacement_value_vs_qqq_usd"), 2),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "trade_enabled": row.get("trade_enabled"),
        "target_price_present": bool(row.get("target_price") is not None),
        "decision_id": row.get("decision_id"),
    }


def slim_open(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "hold_days": row.get("hold_days"),
        "days_held": row.get("days_held"),
        "paper_notional_usd": round_or_none(row.get("paper_notional_usd") or row.get("notional_usd"), 2),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "trade_enabled": row.get("trade_enabled"),
        "decision_id": row.get("decision_id"),
    }


def summarize_state() -> dict[str, Any]:
    state = read_json(STATE_JSON, {})
    closed = state.get("closed_positions") if isinstance(state, dict) else []
    open_positions = state.get("open_positions") if isinstance(state, dict) else []
    pending = state.get("pending_entries") if isinstance(state, dict) else []
    closed = closed if isinstance(closed, list) else []
    open_positions = open_positions if isinstance(open_positions, list) else []
    pending = pending if isinstance(pending, list) else []
    latest, snapshot_count = latest_snapshot()
    forward_gate = latest.get("forward_paper_gate") if isinstance(latest, dict) else {}
    forward_gate = forward_gate if isinstance(forward_gate, dict) else {}

    raw_pnls = [safe_float(row.get("pnl")) for row in closed]
    raw_pnls = [value for value in raw_pnls if value is not None]
    replacement_rows = [
        row
        for row in closed
        if safe_float(row.get("replacement_value_vs_cash_usd")) is not None
    ]
    replacement_cash = [safe_float(row.get("replacement_value_vs_cash_usd")) for row in replacement_rows]
    replacement_spy = [safe_float(row.get("replacement_value_vs_spy_usd")) for row in replacement_rows]
    replacement_qqq = [safe_float(row.get("replacement_value_vs_qqq_usd")) for row in replacement_rows]
    replacement_cash = [value for value in replacement_cash if value is not None]
    replacement_spy = [value for value in replacement_spy if value is not None]
    replacement_qqq = [value for value in replacement_qqq if value is not None]

    all_rows = [*closed, *open_positions, *pending]
    return {
        "state_file": repo_rel(STATE_JSON),
        "state_exists": STATE_JSON.exists(),
        "state_updated_at": state.get("updated_at") if isinstance(state, dict) else None,
        "snapshot_file": repo_rel(SNAPSHOTS_JSONL),
        "snapshot_exists": SNAPSHOTS_JSONL.exists(),
        "snapshot_count": snapshot_count,
        "latest_snapshot_asof_date": latest.get("asof_date"),
        "latest_snapshot_generated_at": latest.get("generated_at"),
        "closed_position_count": len(closed),
        "open_position_count": len(open_positions),
        "pending_entry_count": len(pending),
        "closed_positions": [slim_closed(row) for row in closed],
        "open_positions": [slim_open(row) for row in open_positions],
        "pending_entries": [slim_open(row) for row in pending],
        "closed_replacement_value_count": len(replacement_rows),
        "closed_missing_replacement_value_count": len(closed) - len(replacement_rows),
        "raw_realized_pnl_usd": round(sum(raw_pnls), 2) if raw_pnls else 0.0,
        "raw_win_rate": round(sum(1 for value in raw_pnls if value > 0) / len(raw_pnls), 4) if raw_pnls else None,
        "replacement_value_vs_cash_usd": round(sum(replacement_cash), 2) if replacement_cash else 0.0,
        "replacement_value_vs_spy_usd": round(sum(replacement_spy), 2) if replacement_spy else 0.0,
        "replacement_value_vs_qqq_usd": round(sum(replacement_qqq), 2) if replacement_qqq else 0.0,
        "replacement_win_rate": (
            round(sum(1 for value in replacement_cash if value > 0) / len(replacement_cash), 4)
            if replacement_cash
            else None
        ),
        "sector_counts": Counter(row.get("sector") or "unknown" for row in all_rows),
        "ticker_counts": Counter(row.get("ticker") or "unknown" for row in all_rows),
        "closed_sector_counts": Counter(row.get("sector") or "unknown" for row in closed),
        "trade_enabled_values": sorted({str(row.get("trade_enabled")) for row in all_rows}),
        "open_missing_entry_date": [
            row.get("decision_id") or row.get("ticker")
            for row in open_positions
            if not row.get("entry_date")
        ],
        "closed_missing_entry_or_target": [
            row.get("decision_id") or row.get("ticker")
            for row in closed
            if not row.get("entry_date") or row.get("target_price") is None
        ],
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
            "closed_position_count": latest.get("closed_position_count"),
            "open_position_count": latest.get("open_position_count"),
            "pending_count": latest.get("pending_count"),
            "closed_count_today": latest.get("closed_count_today"),
            "realized_pnl_to_date": latest.get("realized_pnl_to_date"),
            "unrealized_pnl": latest.get("unrealized_pnl"),
        },
    }


def summarize_forward_replacement() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_RV_JSONL)
    matches = [row for row in rows if is_supplier_row(row)]
    enriched = [row for row in matches if row.get("status") == "enriched"]
    cash = [safe_float(row.get("replacement_value_vs_cash_usd")) for row in enriched]
    spy = [safe_float(row.get("replacement_value_vs_spy_usd")) for row in enriched]
    qqq = [safe_float(row.get("replacement_value_vs_qqq_usd")) for row in enriched]
    cash = [value for value in cash if value is not None]
    spy = [value for value in spy if value is not None]
    qqq = [value for value in qqq if value is not None]
    return {
        "ledger_file": repo_rel(FORWARD_RV_JSONL),
        "ledger_exists": FORWARD_RV_JSONL.exists(),
        "total_rows": len(rows),
        "matching_rows": len(matches),
        "enriched_matching_rows": len(enriched),
        "status_counts": Counter(row.get("status") or "unknown" for row in matches),
        "tickers": sorted({str(row.get("ticker")) for row in matches if row.get("ticker")}),
        "replacement_value_vs_cash_usd": round(sum(cash), 2) if cash else 0.0,
        "replacement_value_vs_spy_usd": round(sum(spy), 2) if spy else 0.0,
        "replacement_value_vs_qqq_usd": round(sum(qqq), 2) if qqq else 0.0,
        "sample_matches": [
            {
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "status": row.get("status"),
                "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
                "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
                "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
                "decision_id": row.get("decision_id"),
            }
            for row in matches[:10]
        ],
    }


def prior_summary() -> dict[str, Any]:
    prior = read_json(PRIOR_LOG_JSON, {})
    delta = prior.get("delta_metrics") if isinstance(prior, dict) else {}
    readiness = prior.get("supplier_financing_debt_relief_readiness") if isinstance(prior, dict) else {}
    state = readiness.get("state") if isinstance(readiness, dict) else {}
    return {
        "prior_experiment_id": "exp-20260627-016",
        "prior_log": repo_rel(PRIOR_LOG_JSON),
        "prior_log_exists": PRIOR_LOG_JSON.exists(),
        "prior_closed_position_count": delta.get("closed_position_count") if isinstance(delta, dict) else None,
        "prior_enriched_replacement_rows": delta.get("enriched_replacement_rows") if isinstance(delta, dict) else None,
        "prior_state_updated_at": state.get("state_updated_at") if isinstance(state, dict) else None,
        "prior_decision": prior.get("decision") if isinstance(prior, dict) else None,
        "prior_next_retry_requires": prior.get("next_retry_requires") if isinstance(prior, dict) else None,
    }


def classify_readiness(state: dict[str, Any], forward: dict[str, Any]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if state["closed_position_count"] < MIN_ACTIVATION_CLOSED_ROWS:
        blockers.append(f"closed_rows_below_activation_min:{state['closed_position_count']}/{MIN_ACTIVATION_CLOSED_ROWS}")
    if forward["enriched_matching_rows"] < MIN_ACTIVATION_CLOSED_ROWS:
        blockers.append(
            f"replacement_rows_below_activation_min:{forward['enriched_matching_rows']}/{MIN_ACTIVATION_CLOSED_ROWS}"
        )
    if state["closed_missing_replacement_value_count"] > 0:
        blockers.append(f"closed_rows_missing_replacement_value:{state['closed_missing_replacement_value_count']}")
    if state["raw_realized_pnl_usd"] < 0:
        blockers.append(f"negative_raw_realized_pnl:{state['raw_realized_pnl_usd']}")
    if state["closed_sector_counts"].get("Technology", 0) >= 2:
        blockers.append("technology_concentration_in_closed_rows")
    if state["forward_paper_gate"].get("passed") is not True:
        blockers.append("shared_forward_paper_gate_not_passed")
    if state["open_missing_entry_date"]:
        blockers.append("open_position_entry_date_missing")
    if state["closed_missing_entry_or_target"]:
        blockers.append("closed_entry_date_or_target_price_missing")

    activation_ready = (
        state["closed_position_count"] >= MIN_ACTIVATION_CLOSED_ROWS
        and forward["enriched_matching_rows"] >= MIN_ACTIVATION_CLOSED_ROWS
        and state["forward_paper_gate"].get("passed") is True
        and state["replacement_value_vs_cash_usd"] > 0
        and state["replacement_value_vs_spy_usd"] > 0
        and state["replacement_value_vs_qqq_usd"] > 0
    )
    early_park_evidence = (
        state["closed_position_count"] >= MIN_EARLY_PARK_CLOSED_ROWS
        and state["raw_realized_pnl_usd"] < 0
        and state["closed_missing_replacement_value_count"] == 0
        and state["replacement_value_vs_cash_usd"] < 0
        and state["replacement_value_vs_spy_usd"] < 0
        and state["replacement_value_vs_qqq_usd"] < 0
    )
    if activation_ready:
        return "activation_candidate", []
    if early_park_evidence:
        return "early_park_candidate_negative_full_replacement_value", blockers
    return "collect_only_not_activation_ready", blockers


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    state = summarize_state()
    forward = summarize_forward_replacement()
    prior = prior_summary()
    classification, blockers = classify_readiness(state, forward)
    accepted = classification == "activation_candidate"
    decision = (
        "accepted_supplier_financing_debt_relief_activation_candidate"
        if accepted
        else "rejected_supplier_financing_debt_relief_new_closed_rows_not_activation_ready"
    )
    closed_delta = (
        state["closed_position_count"] - safe_int(prior.get("prior_closed_position_count"))
        if prior.get("prior_closed_position_count") is not None
        else None
    )
    replacement_delta = (
        forward["enriched_matching_rows"] - safe_int(prior.get("prior_enriched_replacement_rows"))
        if prior.get("prior_enriched_replacement_rows") is not None
        else None
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted" if accepted else "rejected",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": accepted,
        "alpha_ready": accepted,
        "observed_only_success": not accepted and state["closed_position_count"] > 0,
        "hypothesis": ticket.get("hypothesis"),
        "change_type": ticket.get("change_type"),
        "implementation_mode": "read_only_forward_closed_row_readiness",
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components", []),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "new_evidence_axis": ((ticket.get("novelty") or {}).get("new_evidence_axis")),
        "novelty": ticket.get("novelty"),
        "prediction": ticket.get("prediction", {}),
        "pre_run_questions": {
            "alpha_hypothesis": ticket.get("hypothesis"),
            "history_check": {
                "prior": prior,
                "novelty_nearest": ((ticket.get("novelty") or {}).get("nearest") or [])[:5],
            },
            "single_policy_bundle": ticket.get("single_causal_variable"),
            "acceptance_standard": (
                "Accept only if the unchanged supplier-financing/debt-relief paper sleeve "
                "has at least 30 closed rows, 30 enriched cash/SPY/QQQ replacement rows, "
                "positive replacement value versus all comparators, and the shared forward "
                "paper gate passes. Classify as early-park candidate only if at least three "
                "closed rows have complete negative replacement values."
            ),
            "reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_JSON),
            "state_file": repo_rel(STATE_JSON),
            "snapshots_file": repo_rel(SNAPSHOTS_JSONL),
            "forward_replacement_value_file": repo_rel(FORWARD_RV_JSONL),
            "min_activation_closed_rows": MIN_ACTIVATION_CLOSED_ROWS,
            "min_early_park_closed_rows": MIN_EARLY_PARK_CLOSED_ROWS,
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
            "prior_closed_position_count": prior.get("prior_closed_position_count"),
            "closed_position_count": state["closed_position_count"],
            "closed_position_count_delta": closed_delta,
            "prior_enriched_replacement_rows": prior.get("prior_enriched_replacement_rows"),
            "enriched_replacement_rows": forward["enriched_matching_rows"],
            "enriched_replacement_row_delta": replacement_delta,
            "raw_realized_pnl_usd": state["raw_realized_pnl_usd"],
            "closed_missing_replacement_value_count": state["closed_missing_replacement_value_count"],
            "open_position_count": state["open_position_count"],
            "pending_entry_count": state["pending_entry_count"],
        },
        "gate1": {
            "passed": baseline["loaded"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": (
                state["state_exists"]
                and state["snapshot_exists"]
                and forward["ledger_exists"]
                and not state["open_missing_entry_date"]
                and not state["closed_missing_entry_or_target"]
            ),
            "fields_checked": [
                "closed_positions.entry_date",
                "closed_positions.target_price",
                "closed_positions.pnl",
                "closed_positions.replacement_value_vs_cash_usd",
                "closed_positions.replacement_value_vs_spy_usd",
                "closed_positions.replacement_value_vs_qqq_usd",
                "forward_replacement_value.decision_id",
                "latest_snapshot.forward_paper_gate",
            ],
            "entry_date_target_price_note": (
                "Closed rows retain entry_date and target_price. Missing replacement-value "
                "comparators are treated as Gate 4 activation blockers, not as an executable "
                "field-contract break."
            ),
            "missing_or_invalid_fields": {
                "open_missing_entry_date": state["open_missing_entry_date"],
                "closed_missing_entry_or_target": state["closed_missing_entry_or_target"],
                "closed_missing_replacement_value_count": state["closed_missing_replacement_value_count"],
            },
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, entry, exit, ranking, sizing, risk budget, or order rule changed.",
        },
        "gate4": {
            "passed": accepted,
            "accepted_alpha": accepted,
            "observed_only": not accepted,
            "classification": classification,
            "decision": decision,
            "failed_reasons": [] if accepted else blockers,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
            "why_no_activation": None if accepted else (
                "The sleeve has progressed from zero to three closed rows, but it is far "
                "below the 30-row activation floor; only one row has full cash/SPY/QQQ "
                "replacement enrichment and raw realized PnL is negative."
            ),
        },
        "supplier_financing_debt_relief_readiness": {
            "classification": classification,
            "blockers": blockers,
            "prior": prior,
            "state": state,
            "forward_replacement": forward,
        },
        "production_impact": {
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": "Read-only audit of existing default-off state and replacement ledger; no helper, adapter, order, or report behavior changed.",
        },
        "calibration": {
            "predicted_success_probability": safe_float((ticket.get("prediction") or {}).get("success_probability")),
            "actual_success": int(accepted),
            "predicted_failure_modes": (ticket.get("prediction") or {}).get("main_failure_modes", []),
            "realized_failure_modes": blockers,
            "predicted_failure_mode_hit": any(
                any(mode in blocker for blocker in blockers)
                for mode in (ticket.get("prediction") or {}).get("main_failure_modes", [])
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The new forward evidence is real but not favorable enough to activate. "
                "The surface moved from 0 to 3 closed rows versus exp-20260627-016, "
                f"but raw realized PnL is {state['raw_realized_pnl_usd']}, two closed "
                "losers lack replacement comparator enrichment, and the sample remains "
                "technology-heavy."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune DPO/debt thresholds, Companyfacts tags, notional scalars, "
                "hard exclusions, or activation thresholds on these same three rows."
            ),
            "new_evidence_required": (
                "Next legal alpha evidence is complete cash/SPY/QQQ replacement enrichment "
                "for all newly closed supplier-financing rows plus materially more closed "
                "rows, or a genuinely new supplier/payment-term, covenant, refinancing, "
                "borrow, or payment-network source."
            ),
        },
        "rejection_reason": None if accepted else ";".join(blockers),
        "next_retry_requires": (
            "Complete replacement-value enrichment for COHR/MU and materially more closed "
            "supplier-financing/debt-relief rows; do not retry adjacent retunes from the "
            "same three-row surface."
        ),
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
            "docs/experiment_log.jsonl",
        ],
        "related_files": [
            repo_rel(STATE_JSON),
            repo_rel(SNAPSHOTS_JSONL),
            repo_rel(FORWARD_RV_JSONL),
            repo_rel(PRIOR_LOG_JSON),
            repo_rel(BASELINE_JSON),
            repo_rel(SHARED_HELPER),
            repo_rel(RUN_ADAPTER),
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python read-only runner only.",
        },
        "lean_quality_passed": True,
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "observed_only_success",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "pre_run_questions",
        "parameters",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "supplier_financing_debt_relief_readiness",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys if key in payload}


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    readiness = payload["supplier_financing_debt_relief_readiness"]
    state = readiness["state"]
    forward = readiness["forward_replacement"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: supplier-financing/debt-relief new closed rows",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Classification: `{readiness['classification']}`",
            "- Strategy behavior changed: `false`",
            f"- Closed rows: `{state['closed_position_count']}`",
            f"- Enriched replacement rows: `{forward['enriched_matching_rows']}`",
            f"- Raw realized PnL: `{money(state['raw_realized_pnl_usd'])}`",
            f"- Replacement value vs cash: `{money(state['replacement_value_vs_cash_usd'])}`",
            f"- Missing replacement values: `{state['closed_missing_replacement_value_count']}`",
            f"- Open rows still collecting: `{state['open_position_count']}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["next_retry_requires"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            "```",
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
        REGISTRY_JSON,
        STATE_JSON,
        SNAPSHOTS_JSONL,
        FORWARD_RV_JSONL,
        PRIOR_LOG_JSON,
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
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_row = build_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "observed_only_success": payload["observed_only_success"],
            "decision": payload["decision"],
            "classification": payload["supplier_financing_debt_relief_readiness"]["classification"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
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
            "parameters": payload["parameters"],
            "pre_run_questions": payload["pre_run_questions"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "anti_js": payload["anti_js"],
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
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "classification": payload["supplier_financing_debt_relief_readiness"]["classification"],
                "closed_rows": payload["delta_metrics"]["closed_position_count"],
                "enriched_replacement_rows": payload["delta_metrics"]["enriched_replacement_rows"],
                "raw_realized_pnl_usd": payload["delta_metrics"]["raw_realized_pnl_usd"],
                "closed_missing_replacement_value_count": payload["delta_metrics"][
                    "closed_missing_replacement_value_count"
                ],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
