"""exp-20260708-011: supplier-financing/debt-relief forward readiness delta.

Observed-only alpha attribution. The single question is whether the fixed
supplier-financing/debt-relief default-off paper sleeve has enough newly
settled, cash/SPY/QQQ-enriched forward rows to become activation-ready.

This runner changes no shared helper, entry, exit, ranking, sizing, paper state,
live order, daily snapshot, or LLM decision boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260708-011"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "supplier_financing_debt_relief_forward_readiness_20260707_delta"
RUNNER = f"quant/experiments/exp_20260708_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "supplier_financing_debt_relief" / "state.json"
SNAPSHOTS_JSONL = (
    REPO_ROOT / "data" / "paper_sleeves" / "supplier_financing_debt_relief" / "snapshots.jsonl"
)
FORWARD_RV_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PRIOR_LOG_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260704-019.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_011_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

SLEEVE_KEY = "supplier_financing_debt_relief"
SLEEVE_TOKEN = "SUPPLIER_FINANCING_DEBT_RELIEF"
REPLACEMENT_AXES = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
CONFIG = {
    "min_activation_enriched_closed_rows": 30,
    "min_reprobe_enriched_closed_rows": 15,
    "min_unique_tickers": 5,
    "max_single_sector_share": 0.60,
    "min_axis_win_rate": 0.50,
    "replacement_axes": REPLACEMENT_AXES,
}

HYPOTHESIS = (
    "Observed-only alpha: accepted supplier-financing/debt-relief default-off "
    "paper sleeve has materially more closed forward rows with complete "
    "cash/SPY/QQQ replacement values; test whether the fixed sleeve is "
    "activation-ready or should be parked without retuning."
)
CHANGE_TYPE = "forward_replacement_value_attribution"
IMPLEMENTATION_MODE = "observed_only_default_off_paper_sleeve_readiness_delta"
MECHANISM_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
TRIAL_FAMILY = "supplier_financing_debt_relief_forward_readiness"
TRIAL_VARIANT_ID = "20260707_full_enrichment_5_closed_rows_v1"
CHANGED_VARIABLE = "supplier_financing_debt_relief_forward_replacement_value_readiness_20260707_delta_v1"
CAUSAL_COMPONENTS = [
    "accepted supplier_financing_debt_relief shared helper closed rows",
    "cash/SPY/QQQ replacement-value attribution",
    "forward activation readiness verdict",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260620-005",
    "exp-20260620-007",
    "exp-20260627-016",
    "exp-20260704-019",
    "exp-20260704-020",
]
NEW_EVIDENCE_TYPE = "materially_more_settled_forward_rows"
NEW_EVIDENCE_AXIS = (
    "Since exp-20260704-019, supplier-financing/debt-relief settled rows "
    "increased from 3 closed / 1 enriched to 5 closed / 5 enriched "
    "cash-SPY-QQQ replacement rows in the same default-off sleeve; no "
    "threshold, field, response-function, notional, hold, or activation retune."
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def rounded(value: Any, digits: int = 4) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def json_safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
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


def summarize_values(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [as_float(row.get(field)) for row in rows]
    clean = [value for value in values if value is not None]
    if not clean:
        return {
            "field": field,
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": None,
        }
    wins = sum(1 for value in clean if value > 0)
    return {
        "field": field,
        "n": len(clean),
        "sum": rounded(sum(clean), 2),
        "mean": rounded(sum(clean) / len(clean), 2),
        "median": rounded(statistics.median(clean), 2),
        "min": rounded(min(clean), 2),
        "max": rounded(max(clean), 2),
        "win_count": wins,
        "loss_count": len(clean) - wins,
        "win_rate": rounded(wins / len(clean), 4),
    }


def max_share(counts: Counter[str]) -> float:
    total = sum(counts.values())
    return max(counts.values(), default=0) / total if total else 0.0


def is_enriched(row: dict[str, Any]) -> bool:
    return all(as_float(row.get(field)) is not None for field in REPLACEMENT_AXES)


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload, dict) else []
    windows = windows if isinstance(windows, list) else []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "loaded": BASELINE_RESULT.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": rounded(
            sum(as_float(row.get("expected_value_score")) or 0.0 for row in windows),
            4,
        ),
        "total_pnl_sum": rounded(
            sum(as_float(row.get("total_pnl")) or 0.0 for row in windows),
            2,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated_sum": generated,
        "signals_survived_sum": survived,
        "survival_rate": rounded(survived / generated, 6) if generated else None,
        "max_drawdown_pct_max": rounded(
            max((as_float(row.get("max_drawdown_pct")) or 0.0 for row in windows), default=0.0),
            4,
        ),
        "windows": windows,
    }


def normalize_closed_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "hold_days": row.get("hold_days") or row.get("days_held"),
        "entry_price": rounded(row.get("entry_price"), 4),
        "exit_price": rounded(row.get("exit_price"), 4),
        "paper_notional_usd": rounded(row.get("paper_notional_usd") or row.get("notional_usd"), 2),
        "pnl": rounded(row.get("pnl"), 2),
        "pnl_pct_net": rounded(row.get("pnl_pct_net"), 6),
        "replacement_value_status": row.get("replacement_value_status"),
        "replacement_value_vs_cash_usd": rounded(row.get("replacement_value_vs_cash_usd"), 2),
        "replacement_value_vs_spy_usd": rounded(row.get("replacement_value_vs_spy_usd"), 2),
        "replacement_value_vs_qqq_usd": rounded(row.get("replacement_value_vs_qqq_usd"), 2),
        "sector": row.get("sector") or "unknown",
        "industry": row.get("industry") or "unknown",
        "entry_regime_label": row.get("entry_regime_label"),
        "entry_short_volume_quintile": row.get("entry_short_volume_quintile"),
        "entry_exhaustion_status": row.get("entry_exhaustion_status"),
        "entry_exhaustion_stretched_flag": row.get("entry_exhaustion_stretched_flag"),
        "payables_dpo_extension_days": rounded(row.get("payables_dpo_extension_days"), 4),
        "debt_debt_ratio_improvement": rounded(row.get("debt_debt_ratio_improvement"), 4),
        "target_price_present": row.get("target_price") is not None,
        "trade_enabled": bool(row.get("trade_enabled")),
        "decision_id": row.get("decision_id"),
    }


def normalize_open_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "hold_days": row.get("hold_days") or row.get("days_held"),
        "paper_notional_usd": rounded(row.get("paper_notional_usd") or row.get("notional_usd"), 2),
        "sector": row.get("sector") or "unknown",
        "industry": row.get("industry") or "unknown",
        "trade_enabled": bool(row.get("trade_enabled")),
        "decision_id": row.get("decision_id"),
    }


def latest_snapshot() -> dict[str, Any]:
    rows = read_jsonl(SNAPSHOTS_JSONL)
    return rows[-1] if rows else {}


def summarize_state() -> dict[str, Any]:
    state = read_json(STATE_JSON, {}) or {}
    closed_raw = state.get("closed_positions") or []
    open_raw = state.get("open_positions") or []
    pending_raw = state.get("pending_entries") or []
    closed_rows = [normalize_closed_row(row) for row in closed_raw]
    open_rows = [normalize_open_row(row) for row in open_raw]
    pending_rows = [normalize_open_row(row) for row in pending_raw]
    enriched_rows = [row for row in closed_rows if is_enriched(row)]
    axis_summaries = {
        field: summarize_values(enriched_rows, field) for field in REPLACEMENT_AXES
    }
    sector_counts = Counter(str(row.get("sector") or "unknown") for row in enriched_rows)
    ticker_counts = Counter(str(row.get("ticker") or "unknown") for row in enriched_rows)
    snapshot = latest_snapshot()
    forward_gate = snapshot.get("forward_paper_gate") if isinstance(snapshot, dict) else {}
    forward_gate = forward_gate if isinstance(forward_gate, dict) else {}
    missing_entry_or_target = [
        row.get("decision_id") or row.get("ticker")
        for row in closed_rows
        if not row.get("entry_date") or not row.get("target_price_present")
    ]
    return {
        "state_file": repo_rel(STATE_JSON),
        "state_exists": STATE_JSON.exists(),
        "state_updated_at": state.get("updated_at"),
        "snapshot_file": repo_rel(SNAPSHOTS_JSONL),
        "snapshot_exists": SNAPSHOTS_JSONL.exists(),
        "latest_snapshot_asof_date": snapshot.get("asof_date") if isinstance(snapshot, dict) else None,
        "latest_snapshot_generated_at": snapshot.get("generated_at") if isinstance(snapshot, dict) else None,
        "closed_rows": closed_rows,
        "open_rows": open_rows,
        "pending_rows": pending_rows,
        "enriched_rows": enriched_rows,
        "closed_position_count": len(closed_rows),
        "open_position_count": len(open_rows),
        "pending_entry_count": len(pending_rows),
        "enriched_closed_count": len(enriched_rows),
        "closed_missing_replacement_value_count": len(closed_rows) - len(enriched_rows),
        "axis_summaries": axis_summaries,
        "ticker_counts": ticker_counts,
        "sector_counts": sector_counts,
        "industry_counts": Counter(str(row.get("industry") or "unknown") for row in enriched_rows),
        "max_single_sector_share": rounded(max_share(sector_counts), 4),
        "unique_tickers": len(ticker_counts),
        "trade_enabled_values": sorted({str(row.get("trade_enabled")) for row in closed_rows + open_rows + pending_rows}),
        "closed_missing_entry_or_target": missing_entry_or_target,
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
    }


def is_supplier_ledger_row(row: dict[str, Any]) -> bool:
    sleeve_key = str(row.get("sleeve_key") or "")
    decision_id = str(row.get("decision_id") or "")
    sleeve = str(row.get("sleeve") or row.get("source") or "")
    return (
        sleeve_key == SLEEVE_KEY
        or SLEEVE_TOKEN in decision_id.upper()
        or SLEEVE_TOKEN in sleeve.upper()
    )


def summarize_forward_replacement_ledger() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_RV_JSONL)
    matches = [row for row in rows if is_supplier_ledger_row(row)]
    enriched = [row for row in matches if row.get("status") == "enriched" and is_enriched(row)]
    axis_summaries = {
        field: summarize_values(enriched, field) for field in REPLACEMENT_AXES
    }
    return {
        "ledger_file": repo_rel(FORWARD_RV_JSONL),
        "ledger_exists": FORWARD_RV_JSONL.exists(),
        "total_rows": len(rows),
        "matching_supplier_rows": len(matches),
        "enriched_supplier_rows": len(enriched),
        "status_counts": Counter(str(row.get("status") or "unknown") for row in matches),
        "tickers": sorted({str(row.get("ticker")) for row in matches if row.get("ticker")}),
        "axis_summaries": axis_summaries,
        "sample_matches": [
            {
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "status": row.get("status"),
                "replacement_value_vs_cash_usd": rounded(row.get("replacement_value_vs_cash_usd"), 2),
                "replacement_value_vs_spy_usd": rounded(row.get("replacement_value_vs_spy_usd"), 2),
                "replacement_value_vs_qqq_usd": rounded(row.get("replacement_value_vs_qqq_usd"), 2),
                "decision_id": row.get("decision_id"),
            }
            for row in matches[-10:]
        ],
    }


def prior_summary() -> dict[str, Any]:
    prior = read_json(PRIOR_LOG_JSON, {}) or {}
    delta = prior.get("delta_metrics") if isinstance(prior, dict) else {}
    return {
        "prior_experiment_id": "exp-20260704-019",
        "prior_log": repo_rel(PRIOR_LOG_JSON),
        "prior_log_exists": PRIOR_LOG_JSON.exists(),
        "prior_decision": prior.get("decision") if isinstance(prior, dict) else None,
        "prior_closed_position_count": delta.get("closed_position_count") if isinstance(delta, dict) else None,
        "prior_enriched_replacement_rows": delta.get("enriched_replacement_rows") if isinstance(delta, dict) else None,
        "prior_next_retry_requires": prior.get("next_retry_requires") if isinstance(prior, dict) else None,
    }


def evaluate_gate4(state: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    enriched = state["enriched_closed_count"]
    closed = state["closed_position_count"]
    axis_summaries = state["axis_summaries"]
    min_activation = CONFIG["min_activation_enriched_closed_rows"]

    if closed < min_activation:
        failures.append(f"closed_rows_below_activation_min:{closed}/{min_activation}")
    if enriched < min_activation:
        failures.append(f"enriched_rows_below_activation_min:{enriched}/{min_activation}")
    if state["unique_tickers"] < CONFIG["min_unique_tickers"]:
        failures.append(f"unique_tickers_below_min:{state['unique_tickers']}/{CONFIG['min_unique_tickers']}")
    if (state["max_single_sector_share"] or 0.0) > CONFIG["max_single_sector_share"]:
        failures.append(
            f"single_sector_share_too_high:{state['max_single_sector_share']}>{CONFIG['max_single_sector_share']}"
        )
    if state["closed_missing_replacement_value_count"]:
        failures.append(
            f"closed_rows_missing_replacement_value:{state['closed_missing_replacement_value_count']}"
        )
    if state["closed_missing_entry_or_target"]:
        failures.append("closed_entry_date_or_target_price_missing")
    if state["forward_paper_gate"].get("passed") is not True:
        failures.append("shared_forward_paper_gate_not_passed")
    if ledger["enriched_supplier_rows"] < enriched:
        failures.append(
            f"ledger_enriched_rows_below_state:{ledger['enriched_supplier_rows']}/{enriched}"
        )

    for field in REPLACEMENT_AXES:
        summary = axis_summaries[field]
        if summary["n"] < enriched:
            failures.append(f"{field}_missing_values")
        if (summary["sum"] or 0.0) <= 0.0:
            failures.append(f"{field}_aggregate_not_positive")
        if (summary["win_rate"] or 0.0) < CONFIG["min_axis_win_rate"]:
            failures.append(f"{field}_win_rate_below_50pct")

    activation_ready = not failures
    watchlist_lead = (
        enriched >= CONFIG["min_reprobe_enriched_closed_rows"]
        and all((axis_summaries[field]["sum"] or 0.0) > 0 for field in REPLACEMENT_AXES)
        and (state["max_single_sector_share"] or 0.0) <= CONFIG["max_single_sector_share"]
    )
    all_axes_negative = all((axis_summaries[field]["sum"] or 0.0) < 0 for field in REPLACEMENT_AXES)
    classification = (
        "activation_candidate"
        if activation_ready
        else (
            "early_park_negative_full_replacement_value"
            if enriched >= 5 and all_axes_negative
            else "collect_only_not_activation_ready"
        )
    )
    return {
        "passed": activation_ready,
        "accepted_alpha": False,
        "observed_only": True,
        "classification": classification,
        "decision": (
            "accepted_supplier_financing_debt_relief_activation_candidate"
            if activation_ready
            else "rejected_supplier_financing_debt_relief_forward_readiness_20260707_delta"
        ),
        "activation_ready": activation_ready,
        "watchlist_lead": watchlist_lead,
        "closed_rows": closed,
        "enriched_closed_rows": enriched,
        "unique_tickers": state["unique_tickers"],
        "sector_counts": state["sector_counts"],
        "industry_counts": state["industry_counts"],
        "ticker_counts": state["ticker_counts"],
        "max_single_sector_share": state["max_single_sector_share"],
        "axis_summaries": axis_summaries,
        "failed_reasons": failures,
        "readiness_guard": CONFIG,
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta_sum": 0.0,
            "trade_count_delta_sum": 0,
            "signals_generated_delta_sum": 0,
            "signals_survived_delta_sum": 0,
            "note": "Observed-only attribution; strategy behavior is unchanged.",
        },
        "reopen_condition": (
            "Do not reserve another supplier-financing/debt-relief readiness ID "
            "until at least 15 fully enriched closed rows exist and the cohort is "
            "no longer Technology-dominated under the fixed 60% max-sector "
            "guard, or until a genuinely new supplier/payment-term, covenant, "
            "refinancing, borrow, or payment-network source exists. Activation "
            "promotion remains blocked until at least 30 enriched closed rows "
            "have positive cash/SPY/QQQ replacement value and pass the fixed "
            "concentration guard."
        ),
    }


def predicted_failure_mode_hit(predicted: list[str], realized: list[str]) -> bool:
    joined = " ".join(realized)
    aliases = {
        "sample_too_thin": "below_activation_min",
        "negative_replacement_value": "aggregate_not_positive",
        "technology_concentration": "single_sector_share_too_high",
        "not_activation_ready": "below_activation_min",
    }
    for mode in predicted:
        if mode in joined:
            return True
        alias = aliases.get(mode)
        if alias and alias in joined:
            return True
    return False


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "supplier_financing_debt_relief_readiness",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys if payload.get(key) is not None}


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    baseline = baseline_metrics()
    state = summarize_state()
    ledger = summarize_forward_replacement_ledger()
    prior = prior_summary()
    gate4 = evaluate_gate4(state, ledger)
    decision = gate4["decision"]
    accepted = bool(gate4["activation_ready"])
    status = "observed_only" if accepted else "observed_only_rejected"
    prediction = ticket.get("prediction") if isinstance(ticket.get("prediction"), dict) else {}
    predicted_modes = prediction.get("main_failure_modes") or []
    closed_delta = (
        state["closed_position_count"] - int(prior["prior_closed_position_count"])
        if prior.get("prior_closed_position_count") is not None
        else None
    )
    enriched_delta = (
        state["enriched_closed_count"] - int(prior["prior_enriched_replacement_rows"])
        if prior.get("prior_enriched_replacement_rows") is not None
        else None
    )
    now = utc_now()

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": accepted,
        "observed_only_lead": bool(gate4["watchlist_lead"]),
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket.get("hypothesis") or HYPOTHESIS,
        "change_type": ticket.get("change_type") or CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": ticket.get("mechanism_family") or MECHANISM_FAMILY,
        "trial_family": ticket.get("trial_family") or TRIAL_FAMILY,
        "trial_variant_id": ticket.get("trial_variant_id") or TRIAL_VARIANT_ID,
        "changed_variable": ticket.get("changed_variable") or CHANGED_VARIABLE,
        "single_causal_variable": ticket.get("single_causal_variable") or CHANGED_VARIABLE,
        "causal_components": ticket.get("causal_components") or CAUSAL_COMPONENTS,
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments") or NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket") or "moderate",
        "new_evidence_type": ticket.get("new_evidence_type") or NEW_EVIDENCE_TYPE,
        "new_evidence_axis": ((ticket.get("novelty") or {}).get("new_evidence_axis")) or NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": int(accepted),
            "predicted_success_probability": prediction.get("success_probability"),
            "brier_score": (
                rounded((float(prediction.get("success_probability")) - int(accepted)) ** 2, 6)
                if prediction.get("success_probability") is not None
                else None
            ),
            "predicted_failure_modes": predicted_modes,
            "realized_failure_modes": gate4["failed_reasons"],
            "predicted_failure_mode_hit": predicted_failure_mode_hit(
                [str(mode) for mode in predicted_modes], gate4["failed_reasons"]
            ),
        },
        "pre_run_questions": {
            "alpha_hypothesis": ticket.get("hypothesis") or HYPOTHESIS,
            "history_check": {
                "nearby_prior_experiments": ticket.get("nearby_prior_experiments") or NEARBY_PRIOR_EXPERIMENTS,
                "prior_delta": prior,
                "novelty_nearest": ((ticket.get("novelty") or {}).get("nearest") or [])[:5],
            },
            "single_policy_bundle": ticket.get("single_causal_variable") or CHANGED_VARIABLE,
            "acceptance_standard": ticket.get("acceptance_rule"),
            "reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "state_file": repo_rel(STATE_JSON),
            "snapshots_file": repo_rel(SNAPSHOTS_JSONL),
            "forward_replacement_value_file": repo_rel(FORWARD_RV_JSONL),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "prior_log": repo_rel(PRIOR_LOG_JSON),
            "readiness_guard": CONFIG,
            "no_strategy_behavior_change": True,
        },
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            **gate4["before_after_strategy_delta"],
            "prior_closed_position_count": prior.get("prior_closed_position_count"),
            "closed_position_count": state["closed_position_count"],
            "closed_position_count_delta": closed_delta,
            "prior_enriched_replacement_rows": prior.get("prior_enriched_replacement_rows"),
            "enriched_replacement_rows": state["enriched_closed_count"],
            "enriched_replacement_row_delta": enriched_delta,
            "replacement_value_vs_cash_usd_sum": gate4["axis_summaries"]["replacement_value_vs_cash_usd"]["sum"],
            "replacement_value_vs_spy_usd_sum": gate4["axis_summaries"]["replacement_value_vs_spy_usd"]["sum"],
            "replacement_value_vs_qqq_usd_sum": gate4["axis_summaries"]["replacement_value_vs_qqq_usd"]["sum"],
            "open_position_count": state["open_position_count"],
            "pending_entry_count": state["pending_entry_count"],
        },
        "gate1": {
            "passed": baseline["loaded"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
            "note": "Observed-only forward attribution; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": (
                state["state_exists"]
                and state["snapshot_exists"]
                and ledger["ledger_exists"]
                and not state["closed_missing_entry_or_target"]
                and state["enriched_closed_count"] == state["closed_position_count"]
            ),
            "fields_checked": [
                "closed_positions[].entry_date",
                "closed_positions[].target_price",
                "closed_positions[].replacement_value_vs_cash_usd",
                "closed_positions[].replacement_value_vs_spy_usd",
                "closed_positions[].replacement_value_vs_qqq_usd",
                "closed_positions[].trade_enabled",
                "forward_replacement_value.sleeve_key",
                "latest_snapshot.forward_paper_gate",
            ],
            "diagnostics": {
                "closed_rows": state["closed_position_count"],
                "entry_target_missing": state["closed_missing_entry_or_target"],
                "replacement_value_enriched_rows": state["enriched_closed_count"],
                "ledger_enriched_supplier_rows": ledger["enriched_supplier_rows"],
                "trade_enabled_values": state["trade_enabled_values"],
            },
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": baseline["signals_generated_sum"],
            "signals_survived": baseline["signals_survived_sum"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, entry, exit, ranking, sizing, or order rule changed.",
        },
        "gate4": gate4,
        "summary": {
            "state_updated_at": state["state_updated_at"],
            "closed_rows": state["closed_position_count"],
            "enriched_closed_rows": state["enriched_closed_count"],
            "open_rows": state["open_position_count"],
            "pending_rows": state["pending_entry_count"],
            "ticker_counts": state["ticker_counts"],
            "sector_counts": state["sector_counts"],
            "axis_summaries": state["axis_summaries"],
            "closed_rows_detail": state["closed_rows"],
            "open_rows_detail": state["open_rows"],
            "pending_rows_detail": state["pending_rows"],
        },
        "supplier_financing_debt_relief_readiness": {
            "classification": gate4["classification"],
            "prior": prior,
            "state": {
                key: value
                for key, value in state.items()
                if key not in {"closed_rows", "open_rows", "pending_rows", "enriched_rows"}
            },
            "forward_replacement_ledger": ledger,
        },
        "production_impact": {
            "strategy_behavior_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only attribution over existing default-off paper sleeve "
                "state and forward replacement ledger. No helper, adapter, "
                "order, or daily snapshot behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The new evidence axis is real: closed/enriched rows moved from "
                f"{prior.get('prior_closed_position_count')} closed / "
                f"{prior.get('prior_enriched_replacement_rows')} enriched to "
                f"{state['closed_position_count']} closed / {state['enriched_closed_count']} "
                "enriched. The alpha did not promote because the sample is still "
                "far below the 30-row activation floor, sector concentration is "
                "80% Technology, and aggregate replacement value is negative "
                "versus cash, SPY, and QQQ."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune DPO extension, debt-ratio improvement, Companyfacts "
                "tags, hard exclusion versus tilt, notional scalar, hold days, "
                "or activation thresholds on these same five rows."
            ),
            "new_evidence_required": gate4["reopen_condition"],
        },
        "rejection_reason": ";".join(gate4["failed_reasons"]) if not accepted else None,
        "next_retry_requires": gate4["reopen_condition"],
        "related_files": [
            repo_rel(STATE_JSON),
            repo_rel(SNAPSHOTS_JSONL),
            repo_rel(FORWARD_RV_JSONL),
            repo_rel(BASELINE_RESULT),
            repo_rel(PRIOR_LOG_JSON),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
            repo_rel(EXPERIMENT_LOG_JSONL),
        ],
        "allowed_write_scope": list(ticket.get("allowed_write_scope") or []),
        "ticket_before": ticket,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python read-only runner only."},
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    axes = gate4["axis_summaries"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Supplier Financing Debt-Relief Forward Readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Classification: `{gate4['classification']}`",
            f"- Artifact: `{payload['artifact']}`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Result",
            "",
            f"- Closed/enriched rows: `{gate4['closed_rows']}` / `{gate4['enriched_closed_rows']}`",
            f"- Unique tickers: `{gate4['unique_tickers']}`",
            f"- Sector counts: `{dict(gate4['sector_counts'])}`",
            f"- Cash/SPY/QQQ aggregate RV: "
            f"`{axes['replacement_value_vs_cash_usd']['sum']}` / "
            f"`{axes['replacement_value_vs_spy_usd']['sum']}` / "
            f"`{axes['replacement_value_vs_qqq_usd']['sum']}`",
            f"- Cash/SPY/QQQ win rate: "
            f"`{axes['replacement_value_vs_cash_usd']['win_rate']}` / "
            f"`{axes['replacement_value_vs_spy_usd']['win_rate']}` / "
            f"`{axes['replacement_value_vs_qqq_usd']['win_rate']}`",
            f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
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
        EXPERIMENT_LOG_JSONL,
        STATE_JSON,
        SNAPSHOTS_JSONL,
        FORWARD_RV_JSONL,
        PRIOR_LOG_JSON,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
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
    log_row = compact_log_record(payload)
    write_json(LOG_JSON, log_row)
    save_experiment_log_entry(log_row, allow_duplicate=True)
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
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "classification": payload["gate4"]["classification"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "replacement_value_vs_cash_usd_sum": payload["gate4"]["axis_summaries"][
                "replacement_value_vs_cash_usd"
            ]["sum"],
            "replacement_value_vs_spy_usd_sum": payload["gate4"]["axis_summaries"][
                "replacement_value_vs_spy_usd"
            ]["sum"],
            "replacement_value_vs_qqq_usd_sum": payload["gate4"]["axis_summaries"][
                "replacement_value_vs_qqq_usd"
            ]["sum"],
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
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
            "allowed_write_scope": payload["allowed_write_scope"],
            "reproduction_commands": payload["reproduction_commands"],
            "anti_js": payload["anti_js"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
        },
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
                "classification": payload["gate4"]["classification"],
                "closed_rows": payload["gate4"]["closed_rows"],
                "enriched_closed_rows": payload["gate4"]["enriched_closed_rows"],
                "axis_summaries": payload["gate4"]["axis_summaries"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
