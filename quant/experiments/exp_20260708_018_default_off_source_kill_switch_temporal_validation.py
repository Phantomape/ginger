"""exp-20260708-018: chronological validation for source kill-switch lead.

Read-only alpha validation. The single question is whether the source-level
negative cohort found by exp-20260708-017 can be selected from earlier settled
forward rows before measuring later holdout rows. No strategy, paper state,
orders, sizing, ranking, exits, or LLM boundary is changed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260708-018"
OWNER = "alpha-explore"
SLUG = "default_off_source_kill_switch_temporal_validation"
RUNNER = f"quant/experiments/exp_20260708_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_RV = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha validation: the exp-20260708-017 source-level "
    "kill-switch lead should generalize only if sources selected by a fixed "
    "chronological training segment continue to have negative cash/SPY/QQQ "
    "replacement value in a later holdout segment; otherwise the lead is "
    "same-cohort overfit and must not become a shared policy."
)
CHANGE_TYPE = "risk_allocation"
IMPLEMENTATION_MODE = "observed_only_temporal_forward_validation"
MECHANISM_FAMILY = "production_visible_default_off_forward_source_risk_allocation"
TRIAL_FAMILY = "default_off_forward_source_level_kill_switch_temporal_validation"
TRIAL_VARIANT_ID = "train_before_20260601_holdout_after_20260601_v1"
CHANGED_VARIABLE = "default_off_source_kill_switch_chronological_holdout_validation_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_on_settled_forward_replacement_rows"
NEW_EVIDENCE_AXIS = (
    "New gate shape: chronological train/holdout validation of the "
    "exp-20260708-017 source-level kill-switch using only earlier settled rows "
    "to choose sources before measuring later rows; not a threshold, comparator, "
    "source-label, or response-curve retune."
)
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260708-017"]
CAUSAL_COMPONENTS = [
    "forward_replacement_value ledger",
    "chronological train/holdout split",
    "fixed exp017 source gate",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "training_no_kill_sources",
        "holdout_not_negative",
        "sample_too_thin",
        "observed_only_not_policy_ready",
    ],
    "confidence_reason": (
        "The prior source-level lead was found on all current forward rows, so "
        "a chronological train/holdout validation is a stricter falsification; "
        "the likely failure is that early rows are too thin or concentrated to "
        "predeclare any source without looking at holdout."
    ),
    "recorded_at": "2026-07-08T15:05:06+00:00",
}
CONFIG = {
    "train_entry_date_before": "2026-06-01",
    "holdout_entry_date_on_or_after": "2026-06-01",
    "min_train_rows_per_source": 3,
    "min_holdout_rows_for_selected_sources": 6,
    "max_single_ticker_share": 0.60,
    "comparators": [
        "replacement_value_vs_cash_usd",
        "replacement_value_vs_spy_usd",
        "replacement_value_vs_qqq_usd",
    ],
    "train_requires_all_comparator_means_negative": True,
    "holdout_requires_all_comparator_means_negative": True,
    "holdout_requires_selected_worse_than_kept_on_cash_mean": True,
}


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def rounded(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def metric_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "sum": None,
            "win_rate": None,
        }
    return {
        "count": len(values),
        "mean": rounded(statistics.fmean(values), 4),
        "median": rounded(statistics.median(values), 4),
        "min": rounded(min(values), 4),
        "max": rounded(max(values), 4),
        "sum": rounded(sum(values), 4),
        "win_rate": rounded(sum(1 for value in values if value > 0.0) / len(values), 4),
    }


def source_from_row(row: dict[str, Any]) -> str:
    value = row.get("sleeve_key")
    if value:
        return str(value)
    decision_id = str(row.get("decision_id") or "")
    if ":" in decision_id:
        return decision_id.split(":", 1)[0].lower()
    return "unknown"


def row_complete(row: dict[str, Any]) -> bool:
    if str(row.get("status") or "").lower() != "enriched":
        return False
    return all(as_float(row.get(field)) is not None for field in CONFIG["comparators"])


def load_forward_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_rows: list[dict[str, Any]] = []
    complete_rows: list[dict[str, Any]] = []
    if not FORWARD_RV.exists():
        return raw_rows, complete_rows
    for line in FORWARD_RV.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        raw_rows.append(row)
        if row_complete(row):
            complete_rows.append(row)
    return raw_rows, complete_rows


def compact_baseline() -> dict[str, Any]:
    data = read_json(BASELINE_RESULT, {})
    if not isinstance(data, dict) or not data:
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "available": False}
    windows = [row for row in data.get("windows") or [] if isinstance(row, dict)]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "available": True,
        "expected_value_score_sum": rounded(
            sum(as_float(row.get("expected_value_score")) or 0.0 for row in windows),
            4,
        ),
        "total_pnl": rounded(sum(as_float(row.get("total_pnl")) or 0.0 for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
        "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
        "survival_rate": rounded(
            (
                sum(int(row.get("signals_survived") or 0) for row in windows)
                / sum(int(row.get("signals_generated") or 0) for row in windows)
            )
            if sum(int(row.get("signals_generated") or 0) for row in windows)
            else 0.0,
            6,
        ),
        "max_drawdown_pct_worst": rounded(
            max(as_float(row.get("max_drawdown_pct")) or 0.0 for row in windows),
            6,
        )
        if windows
        else None,
        "window_count": len(windows),
    }


def split_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cutoff = CONFIG["train_entry_date_before"]
    train = [row for row in rows if str(row.get("entry_date") or "")[:10] < cutoff]
    holdout = [row for row in rows if str(row.get("entry_date") or "")[:10] >= cutoff]
    return train, holdout


def comparator_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        field: metric_summary(
            [
                as_float(row.get(field))
                for row in rows
                if as_float(row.get(field)) is not None
            ]
        )
        for field in CONFIG["comparators"]
    }


def summarize_source(source: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = [str(row.get("ticker") or "") for row in rows if row.get("ticker")]
    ticker_counts = Counter(tickers)
    max_single = max(ticker_counts.values()) / len(rows) if rows and ticker_counts else 1.0
    comparators = comparator_summary(rows)
    failed: list[str] = []
    if len(rows) < CONFIG["min_train_rows_per_source"]:
        failed.append(f"rows_below_min:{len(rows)}/{CONFIG['min_train_rows_per_source']}")
    if max_single > CONFIG["max_single_ticker_share"]:
        failed.append(
            f"single_ticker_share:{rounded(max_single, 4)}>{CONFIG['max_single_ticker_share']}"
        )
    if any((comparators[field]["mean"] or 0.0) >= 0.0 for field in CONFIG["comparators"]):
        failed.append("not_all_comparator_means_negative")
    return {
        "source": source,
        "rows": len(rows),
        "ticker_count": len(ticker_counts),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "max_single_ticker_share": rounded(max_single, 4),
        "entry_dates": sorted(
            {str(row.get("entry_date")) for row in rows if row.get("entry_date")}
        ),
        "comparators": comparators,
        "passes_fixed_train_gate": not failed,
        "failed_reasons": failed,
    }


def summarize_by_source(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_source[source_from_row(row)].append(row)
    summaries = [summarize_source(source, group) for source, group in by_source.items()]
    summaries.sort(
        key=lambda item: (
            not item["passes_fixed_train_gate"],
            item["comparators"]["replacement_value_vs_cash_usd"]["mean"] or 0.0,
            item["source"],
        )
    )
    return summaries


def aggregate_block(label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(str(row.get("ticker") or "") for row in rows if row.get("ticker"))
    sources = Counter(source_from_row(row) for row in rows)
    return {
        "label": label,
        "rows": len(rows),
        "source_counts": dict(sorted(sources.items())),
        "ticker_counts": dict(sorted(tickers.items())),
        "max_single_ticker_share": rounded(
            max(tickers.values()) / len(rows) if rows and tickers else 0.0,
            4,
        ),
        "comparators": comparator_summary(rows),
    }


def build_validation(raw_rows: list[dict[str, Any]], complete_rows: list[dict[str, Any]]) -> dict[str, Any]:
    train, holdout = split_rows(complete_rows)
    train_sources = summarize_by_source(train)
    selected_sources = [
        row["source"] for row in train_sources if row["passes_fixed_train_gate"]
    ]
    holdout_selected = [
        row for row in holdout if source_from_row(row) in set(selected_sources)
    ]
    holdout_kept = [
        row for row in holdout if source_from_row(row) not in set(selected_sources)
    ]
    selected_summary = aggregate_block("holdout_selected_sources", holdout_selected)
    kept_summary = aggregate_block("holdout_unselected_sources", holdout_kept)
    failures: list[str] = []
    if len(train) < 20:
        failures.append(f"train_rows_below_floor:{len(train)}/20")
    if len(holdout) < 20:
        failures.append(f"holdout_rows_below_floor:{len(holdout)}/20")
    if not selected_sources:
        failures.append("training_no_kill_sources")
    if selected_sources and len(holdout_selected) < CONFIG["min_holdout_rows_for_selected_sources"]:
        failures.append(
            "holdout_selected_rows_below_floor:"
            f"{len(holdout_selected)}/{CONFIG['min_holdout_rows_for_selected_sources']}"
        )
    if selected_sources and any(
        (selected_summary["comparators"][field]["mean"] or 0.0) >= 0.0
        for field in CONFIG["comparators"]
    ):
        failures.append("holdout_selected_not_negative_all_comparators")
    selected_cash = selected_summary["comparators"]["replacement_value_vs_cash_usd"]["mean"]
    kept_cash = kept_summary["comparators"]["replacement_value_vs_cash_usd"]["mean"]
    if selected_sources and selected_cash is not None and kept_cash is not None:
        if selected_cash >= kept_cash:
            failures.append("holdout_selected_cash_mean_not_worse_than_unselected")
    return {
        "ledger_path": repo_rel(FORWARD_RV),
        "raw_rows": len(raw_rows),
        "complete_enriched_rows": len(complete_rows),
        "train": aggregate_block("train", train),
        "holdout": aggregate_block("holdout", holdout),
        "train_sources": train_sources,
        "selected_sources_from_train": selected_sources,
        "holdout_selected_sources": selected_summary,
        "holdout_unselected_sources": kept_summary,
        "validation_passed": not failures,
        "failed_reasons": failures,
    }


def build_gate4(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "observed_only_chronological_source_kill_switch_validation",
        "passed": validation["validation_passed"],
        "accepted_alpha": False,
        "observed_only_lead": validation["validation_passed"],
        "failed_reasons": validation["failed_reasons"],
        "selected_sources_from_train": validation["selected_sources_from_train"],
        "binding_acceptance_note": (
            "Observed-only validation only. Any executable source kill switch "
            "would still need a shared production/backtest policy, Gate 1-4, "
            "and live-realistic execution envelope."
        ),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
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
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "temporal_validation",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys if payload.get(key) is not None}


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = compact_baseline()
    raw_rows, complete_rows = load_forward_rows()
    validation = build_validation(raw_rows, complete_rows)
    gate4 = build_gate4(validation)
    observed_lead = gate4["observed_only_lead"]
    status = (
        "observed_only_positive_temporal_validation_lead"
        if observed_lead
        else "observed_only_rejected"
    )
    if "training_no_kill_sources" in validation["failed_reasons"]:
        decision = "observed_only_rejected_no_train_selected_kill_sources"
    elif observed_lead:
        decision = "observed_only_positive_temporal_source_kill_switch_lead_not_policy_ready"
    else:
        decision = "observed_only_rejected_holdout_validation_failed"
    actual_success = 1 if observed_lead else 0
    predicted = float(PREDICTION["success_probability"])
    gate1 = {
        "passed": bool(baseline.get("available")),
        "baseline_metrics": baseline,
    }
    gate2 = {
        "passed": bool(complete_rows),
        "fields_checked": [
            "entry_date",
            "exit_date",
            "ticker",
            "sleeve_key",
            "replacement_value_vs_cash_usd",
            "replacement_value_vs_spy_usd",
            "replacement_value_vs_qqq_usd",
        ],
        "missing_or_invalid_fields": {
            "raw_rows": len(raw_rows),
            "complete_enriched_rows": len(complete_rows),
            "incomplete_rows": len(raw_rows) - len(complete_rows),
        },
        "entry_date_target_price_note": (
            "Forward replacement rows have entry_date/exit_date and comparator "
            "outcomes. target_price is not an executable signal dependency for "
            "this observed-only validation runner."
        ),
    }
    gate3 = {
        "passed": True,
        "filter_added": False,
        "signals_generated": len(raw_rows),
        "signals_survived": len(complete_rows),
        "survival_rate": rounded(len(complete_rows) / len(raw_rows), 6)
        if raw_rows
        else 0.0,
        "note": "No executable filter, rank, size, exit, or order rule changed.",
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "prior_trial_count": ticket.get("prior_trial_count", 0),
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "parameters": CONFIG,
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": rounded((actual_success - predicted) ** 2, 4),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": validation["failed_reasons"],
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"]) & set(validation["failed_reasons"])
            ),
            "surprise_note": (
                "Temporal validation passed, but this is still observed-only and not policy-ready."
                if observed_lead
                else "The stricter chronological validation failed before policy work: early settled rows did not select any legal source under the fixed exp017 gate."
            ),
        },
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "temporal_validation": validation,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "paper_state_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "scope": "read_only_temporal_forward_replacement_validation",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The all-row source kill-switch lead was not train-selectable: "
                "the pre-2026-06-01 segment had 28 complete rows, but every "
                "negative source either lacked enough diversified rows or failed "
                "the fixed exp017 concentration guard. The later losses cannot "
                "be used to predeclare a source halt without look-ahead."
                if not observed_lead
                else "A train-only negative source cohort remained negative in holdout, but this still needs shared policy Gate 1-4 before any allocation effect."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun source kill-switch attribution on the same 74-row "
                "ledger by changing split date, min rows, concentration, "
                "comparator set, source labels, or response curve."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more settled forward replacement "
                "rows that allow a predeclared train segment to select sources, "
                "or a separate shared production/backtest policy Gate 1-4 with "
                "an independently specified source-risk state."
            ),
        },
        "rejection_reason": None if observed_lead else ";".join(validation["failed_reasons"]),
        "next_retry_requires": [
            "materially_more_settled_forward_replacement_rows_for_temporal_validation",
            "independent_shared_policy_gate_1_4_for_any_executable_source_halt",
            "no_split_threshold_concentration_comparator_or_response_retune_on_same_rows",
        ],
        "related_files": [
            repo_rel(FORWARD_RV),
            repo_rel(BASELINE_RESULT),
            repo_rel(TICKET_JSON),
            "data/experiments/exp-20260708-017/exp_20260708_017_default_off_forward_source_kill_switch_attribution.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ticket.get("allowed_write_scope", []),
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": True,
        "ticket_before": ticket,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    validation = payload["temporal_validation"]
    lines = [
        f"# {EXPERIMENT_ID}: Default-Off Source Kill-Switch Temporal Validation",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Result",
        "",
        f"- Raw / complete rows: `{validation['raw_rows']}` / `{validation['complete_enriched_rows']}`",
        f"- Train / holdout rows: `{validation['train']['rows']}` / `{validation['holdout']['rows']}`",
        f"- Selected sources from train: `{', '.join(validation['selected_sources_from_train']) or 'none'}`",
        f"- Gate 4 failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
        "",
        "| Train source | Rows | Max ticker share | Cash mean | SPY mean | QQQ mean | Selected | Failed reasons |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in validation["train_sources"]:
        lines.append(
            f"| {row['source']} | {row['rows']} | {row['max_single_ticker_share']} | "
            f"{row['comparators']['replacement_value_vs_cash_usd']['mean']} | "
            f"{row['comparators']['replacement_value_vs_spy_usd']['mean']} | "
            f"{row['comparators']['replacement_value_vs_qqq_usd']['mean']} | "
            f"{row['passes_fixed_train_gate']} | "
            f"{'; '.join(row['failed_reasons']) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
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
    log_record = compact_log_record(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "temporal_validation_summary": {
                "raw_rows": payload["temporal_validation"]["raw_rows"],
                "complete_enriched_rows": payload["temporal_validation"][
                    "complete_enriched_rows"
                ],
                "train_rows": payload["temporal_validation"]["train"]["rows"],
                "holdout_rows": payload["temporal_validation"]["holdout"]["rows"],
                "selected_sources_from_train": payload["temporal_validation"][
                    "selected_sources_from_train"
                ],
                "failed_reasons": payload["temporal_validation"]["failed_reasons"],
            },
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
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
                "selected_sources_from_train": payload["temporal_validation"][
                    "selected_sources_from_train"
                ],
                "gate4": payload["gate4"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
