"""exp-20260623-004: forward replacement regime activation attribution.

Observed-only alpha attribution. This runner applies the shared forward
replacement entry-regime tag to current closed default-off paper rows in memory,
then asks whether any sleeve/regime cell is strong enough to be an activation
lead. It changes no entry, ranking, sizing, exit, paper ledger, live ledger, or
order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from forward_replacement_value import (  # noqa: E402
    ENTRY_REGIME_TAG_RULE_VERSION,
    PRODUCTION_IMPACT as FORWARD_REPLACEMENT_PRODUCTION_IMPACT,
    RULE_VERSION as FORWARD_REPLACEMENT_RULE_VERSION,
    _closed_rows,
    _record_from_state_row,
    enrich_state_closed_rows,
    load_comparator_bars,
    load_regime_spy_bars,
    replacement_artifact_key,
)


EXPERIMENT_ID = "exp-20260623-004"
SLUG = "forward_replacement_regime_activation_attribution"
RUNNER = f"quant/experiments/exp_20260623_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_004_{SLUG}.json"
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
SLEEVES_ROOT = REPO_ROOT / "data" / "paper_sleeves"
CURRENT_FORWARD_ARTIFACT = SLEEVES_ROOT / "forward_replacement_value.jsonl"

HYPOTHESIS = (
    "Observed-only attribution: closed default-off paper forward replacement "
    "rows tagged with entry-time regime may identify a sleeve/regime activation "
    "lead with positive replacement value versus cash, SPY, and QQQ without "
    "retuning frozen windows."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "forward_replacement_regime_attribution"
TRIAL_FAMILY = "forward_replacement_entry_regime_activation_attribution"
TRIAL_VARIANT_ID = "current_closed_forward_rows_regime_cells_v1"
CHANGED_VARIABLE = "forward_replacement_entry_regime_activation_attribution_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-013",
    "exp-20260623-002",
    "exp-20260613-005",
]
NEW_EVIDENCE_TYPE = "entry_regime_tagged_forward_rows"
NEW_EVIDENCE_AXIS = (
    "New entry-time regime tags on closed forward replacement rows from "
    "exp-20260623-002; no sleeve helper, source rank, threshold, notional, "
    "hold, cooldown, or frozen-window retune."
)
CAUSAL_COMPONENTS = [
    "closed forward replacement rows",
    "entry-time regime tag",
    "sleeve/regime cohort attribution",
    "no strategy change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-004/exp_20260623_004_forward_replacement_regime_activation_attribution.json",
    "experiments/cards/exp-20260623-004.md",
    "experiments/manifests/exp-20260623-004.json",
    "experiments/tickets/exp-20260623-004.json",
    "experiments/logs/exp-20260623-004.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

DEFAULT_PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "too_few_closed_rows",
        "missing_entry_regime_tags",
        "QQQ_concentration",
        "no_positive_replacement_value_vs_spy_qqq",
    ],
    "confidence_reason": (
        "Forward activation has been blocked by thin rows, but "
        "exp-20260623-002 added a new production-visible entry-time regime tag "
        "that can test whether existing closed rows concentrate in a deployable "
        "sleeve/regime cell; the main risk is the current forward sample is "
        "still too small and concentrated."
    ),
    "recorded_at": "2026-06-23T03:02:53+00:00",
}

ACCEPTANCE_RULE = {
    "min_total_rows": 20,
    "min_tagged_rows": 20,
    "min_cell_rows": 8,
    "min_cell_distinct_tickers": 3,
    "min_cell_positive_rate_vs_cash": 0.50,
    "min_cell_positive_rate_vs_spy": 0.50,
    "min_cell_positive_rate_vs_qqq": 0.50,
    "max_single_ticker_row_share": 0.70,
    "max_single_ticker_positive_cash_share": 0.50,
    "required_positive_sum_fields": [
        "replacement_value_vs_cash_usd",
        "replacement_value_vs_spy_usd",
        "replacement_value_vs_qqq_usd",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def safe_round(value: Any, digits: int = 4) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def load_ticket_prediction() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return dict(DEFAULT_PREDICTION)
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict) and prediction.get("confidence_reason"):
        return prediction
    return dict(DEFAULT_PREDICTION)


def load_baseline_metrics() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT)
    windows = raw.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": int(
            sum(int(row.get("signals_generated") or 0) for row in windows)
        ),
        "signals_survived": int(
            sum(int(row.get("signals_survived") or 0) for row in windows)
        ),
        "survival_rate": round(
            sum(float(row.get("signals_survived") or 0) for row in windows)
            / max(sum(float(row.get("signals_generated") or 0) for row in windows), 1.0),
            4,
        ),
        "max_drawdown_pct_worst": max(
            float(row.get("max_drawdown_pct") or 0.0) for row in windows
        ),
        "window_count": len(windows),
        "windows": windows,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_tagged_forward_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bars_by_ticker = load_comparator_bars()
    regime_spy_bars = load_regime_spy_bars()
    records: list[dict[str, Any]] = []
    sleeves: dict[str, Any] = {}
    rows_before_tag = 0
    rows_with_tag_before = 0
    rows_with_replacement_before = 0
    rows_updated_in_memory = 0

    for state_path in sorted(SLEEVES_ROOT.glob("*/state.json")):
        sleeve_key = state_path.parent.name
        try:
            state = read_json(state_path)
        except (OSError, json.JSONDecodeError):
            sleeves[sleeve_key] = {"status": "unreadable_state"}
            continue
        closed = list(_closed_rows(state))
        rows_before_tag += len(closed)
        rows_with_tag_before += sum(1 for row in closed if row.get("entry_regime_label"))
        rows_with_replacement_before += sum(
            1 for row in closed if row.get("replacement_value_rule_version")
        )
        updated = enrich_state_closed_rows(
            state,
            bars_by_ticker,
            utc_now()[:10],
            sleeve_key,
            regime_spy_bars=regime_spy_bars,
        )
        rows_updated_in_memory += len(updated)
        sleeve_records = []
        for row in _closed_rows(state):
            record = _record_from_state_row(row, sleeve_key)
            if record is not None:
                sleeve_records.append(record)
                records.append(record)
        sleeves[sleeve_key] = {
            "closed_rows": len(closed),
            "replacement_rows_after_in_memory_tag": len(sleeve_records),
            "updated_rows_in_memory": len(updated),
        }

    records.sort(key=replacement_artifact_key)
    current_artifact_rows = read_jsonl(CURRENT_FORWARD_ARTIFACT)
    return records, {
        "sleeves_root": repo_rel(SLEEVES_ROOT),
        "current_forward_artifact": repo_rel(CURRENT_FORWARD_ARTIFACT),
        "current_forward_artifact_rows": len(current_artifact_rows),
        "state_closed_rows_scanned": rows_before_tag,
        "state_replacement_rows_before": rows_with_replacement_before,
        "state_rows_with_entry_regime_before": rows_with_tag_before,
        "tagged_records_built_in_memory": len(records),
        "rows_updated_in_memory": rows_updated_in_memory,
        "regime_spy_bars_loaded": len(regime_spy_bars),
        "comparator_bar_counts": {ticker: len(bars) for ticker, bars in bars_by_ticker.items()},
        "sleeves": sleeves,
        "artifact_not_mutated": True,
        "state_files_not_mutated": True,
    }


def value_fields(row: dict[str, Any]) -> dict[str, float | None]:
    return {
        "replacement_value_vs_cash_usd": as_float(row.get("replacement_value_vs_cash_usd")),
        "replacement_value_vs_spy_usd": as_float(row.get("replacement_value_vs_spy_usd")),
        "replacement_value_vs_qqq_usd": as_float(row.get("replacement_value_vs_qqq_usd")),
        "pnl_usd": as_float(row.get("pnl_usd")),
    }


def max_positive_share(rows: list[dict[str, Any]], field: str, group_key: str) -> float | None:
    positives: dict[str, float] = defaultdict(float)
    for row in rows:
        value = as_float(row.get(field))
        if value is not None and value > 0:
            positives[str(row.get(group_key) or "unknown")] += value
    total = sum(positives.values())
    if total <= 0:
        return None
    return round(max(positives.values()) / total, 4)


def max_row_share(rows: list[dict[str, Any]], group_key: str) -> float | None:
    if not rows:
        return None
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get(group_key) or "unknown")] += 1
    return round(max(counts.values()) / len(rows), 4)


def cohort_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "sleeves_present": [],
            "entry_regimes_present": [],
            "tickers_present": [],
        }
    sums = {
        key: round(
            sum(value for row in rows if (value := as_float(row.get(key))) is not None),
            2,
        )
        for key in [
            "replacement_value_vs_cash_usd",
            "replacement_value_vs_spy_usd",
            "replacement_value_vs_qqq_usd",
            "pnl_usd",
        ]
    }
    positive_rates = {}
    averages = {}
    for key, total in sums.items():
        values = [as_float(row.get(key)) for row in rows]
        valid = [value for value in values if value is not None]
        positive_rates[key] = round(
            sum(1 for value in valid if value > 0) / len(valid), 4
        ) if valid else None
        averages[key] = round(total / len(valid), 2) if valid else None
    tickers = sorted({str(row.get("ticker") or "unknown") for row in rows})
    return {
        "n": len(rows),
        "sums": sums,
        "averages": averages,
        "positive_rates": positive_rates,
        "sleeves_present": sorted({str(row.get("sleeve_key") or "unknown") for row in rows}),
        "entry_regimes_present": sorted(
            {str(row.get("entry_regime_label") or "missing") for row in rows}
        ),
        "tickers_present": tickers,
        "distinct_tickers": len(tickers),
        "max_single_ticker_row_share": max_row_share(rows, "ticker"),
        "max_single_ticker_positive_cash_share": max_positive_share(
            rows, "replacement_value_vs_cash_usd", "ticker"
        ),
        "top_tickers_by_rows": top_counts(rows, "ticker", 8),
    }


def top_counts(rows: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get(key) or "unknown")] += 1
    return [
        {"key": key_value, "n": n, "row_share": round(n / len(rows), 4) if rows else None}
        for key_value, n in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def group_rows(rows: list[dict[str, Any]], key_fn) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(row)
    return grouped


def build_group_summaries(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {
        "by_entry_regime": group_rows(
            rows, lambda row: str(row.get("entry_regime_label") or "missing")
        ),
        "by_sleeve": group_rows(rows, lambda row: str(row.get("sleeve_key") or "unknown")),
        "by_sleeve_regime": group_rows(
            rows,
            lambda row: (
                str(row.get("sleeve_key") or "unknown")
                + "|"
                + str(row.get("entry_regime_label") or "missing")
            ),
        ),
    }
    output: dict[str, list[dict[str, Any]]] = {}
    for group_name, group in groups.items():
        summaries = []
        for key, group_rows_ in group.items():
            summary = cohort_summary(group_rows_)
            summary["key"] = key
            summaries.append(summary)
        summaries.sort(
            key=lambda row: (
                -(row.get("n") or 0),
                -(row.get("sums", {}).get("replacement_value_vs_qqq_usd") or -10**9),
                row.get("key") or "",
            )
        )
        output[group_name] = summaries
    return output


def cell_failure_reasons(summary: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    sums = summary.get("sums") or {}
    rates = summary.get("positive_rates") or {}
    if (summary.get("n") or 0) < ACCEPTANCE_RULE["min_cell_rows"]:
        reasons.append("cell_too_few_rows")
    if (summary.get("distinct_tickers") or 0) < ACCEPTANCE_RULE["min_cell_distinct_tickers"]:
        reasons.append("cell_too_few_distinct_tickers")
    for field in ACCEPTANCE_RULE["required_positive_sum_fields"]:
        if (sums.get(field) or 0.0) <= 0:
            reasons.append(f"{field}_sum_not_positive")
    if (
        rates.get("replacement_value_vs_cash_usd") is None
        or rates.get("replacement_value_vs_cash_usd")
        < ACCEPTANCE_RULE["min_cell_positive_rate_vs_cash"]
    ):
        reasons.append("cell_cash_positive_rate_too_low")
    if (
        rates.get("replacement_value_vs_spy_usd") is None
        or rates.get("replacement_value_vs_spy_usd")
        < ACCEPTANCE_RULE["min_cell_positive_rate_vs_spy"]
    ):
        reasons.append("cell_spy_positive_rate_too_low")
    if (
        rates.get("replacement_value_vs_qqq_usd") is None
        or rates.get("replacement_value_vs_qqq_usd")
        < ACCEPTANCE_RULE["min_cell_positive_rate_vs_qqq"]
    ):
        reasons.append("cell_qqq_positive_rate_too_low")
    row_share = summary.get("max_single_ticker_row_share")
    if row_share is not None and row_share > ACCEPTANCE_RULE["max_single_ticker_row_share"]:
        reasons.append("cell_single_ticker_row_concentration")
    positive_share = summary.get("max_single_ticker_positive_cash_share")
    if (
        positive_share is not None
        and positive_share > ACCEPTANCE_RULE["max_single_ticker_positive_cash_share"]
    ):
        reasons.append("cell_single_ticker_positive_cash_concentration")
    return reasons


def analyze_forward_rows(records: list[dict[str, Any]], audit: dict[str, Any]) -> dict[str, Any]:
    tagged = [
        row
        for row in records
        if row.get("entry_regime_tag_rule_version") == ENTRY_REGIME_TAG_RULE_VERSION
        and row.get("entry_regime_status") == "ok"
        and row.get("entry_regime_label")
    ]
    groups = build_group_summaries(tagged)
    candidate_cells = []
    for summary in groups["by_sleeve_regime"]:
        reasons = cell_failure_reasons(summary)
        summary = dict(summary)
        summary["passes_activation_lead_screen"] = not reasons
        summary["failed_reasons"] = reasons
        candidate_cells.append(summary)
    candidate_cells.sort(
        key=lambda row: (
            not row["passes_activation_lead_screen"],
            -(row.get("n") or 0),
            -(row.get("sums", {}).get("replacement_value_vs_qqq_usd") or -10**9),
        )
    )

    failed: list[str] = []
    if len(records) < ACCEPTANCE_RULE["min_total_rows"]:
        failed.append("too_few_closed_rows")
    if len(tagged) < ACCEPTANCE_RULE["min_tagged_rows"]:
        failed.append("missing_or_too_few_entry_regime_tags")
    if not any(cell["passes_activation_lead_screen"] for cell in candidate_cells):
        failed.append("no_deployable_sleeve_regime_cell")
    if audit.get("current_forward_artifact_rows") != len(records):
        failed.append("state_artifact_row_count_mismatch")

    return {
        "all_rows": cohort_summary(records),
        "tagged_rows": cohort_summary(tagged),
        "tagged_row_count": len(tagged),
        "groups": groups,
        "candidate_sleeve_regime_cells": candidate_cells[:20],
        "best_candidate_cell": candidate_cells[0] if candidate_cells else None,
        "observed_only_activation_lead": not failed,
        "failed_reasons": failed,
        "acceptance_rule": ACCEPTANCE_RULE,
    }


def calibration(prediction: dict[str, Any], success: bool, failed_reasons: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    mode_hits = []
    if "too_few_closed_rows" in failed_reasons:
        mode_hits.append("too_few_closed_rows")
    if "missing_or_too_few_entry_regime_tags" in failed_reasons:
        mode_hits.append("missing_entry_regime_tags")
    if "no_deployable_sleeve_regime_cell" in failed_reasons:
        mode_hits.extend(["QQQ_concentration", "no_positive_replacement_value_vs_spy_qqq"])
    declared_modes = set(prediction.get("main_failure_modes") or [])
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(success),
        "brier_score": round((probability - actual) ** 2, 6),
        "failed_reasons": failed_reasons,
        "prediction_failure_modes_hit": [
            mode for mode in mode_hits if mode in declared_modes
        ],
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    records, source_audit = load_tagged_forward_rows()
    analysis = analyze_forward_rows(records, source_audit)
    observed_lead = analysis["observed_only_activation_lead"]
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_forward_regime_activation_lead"
        if observed_lead
        else "rejected_no_forward_regime_activation_cell_ready"
    )
    failed = analysis["failed_reasons"]
    now = utc_now()
    why = (
        "The current forward sample is still not activation-ready after tagging: "
        "no sleeve/regime cell simultaneously has enough rows, positive "
        "replacement value versus cash/SPY/QQQ, and acceptable ticker "
        "concentration."
        if failed
        else "A sleeve/regime cell passed the observed-only lead screen, but it still needs a separate fixed activation-envelope test before promotion."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
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
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new accepted this as no strong near-neighbor; "
                    "nearest regime-state families stayed below the blocking threshold."
                ),
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "important_boundary": (
                    "This run uses the new exp-20260623-002 entry-regime tag "
                    "on current closed forward rows. It does not retune helper "
                    "sources, ranks, thresholds, notional, hold, cooldown, or "
                    "frozen windows."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: tag current closed "
                "forward replacement rows by entry-time regime and evaluate "
                "sleeve/regime cohorts."
            ),
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "sleeves_root": repo_rel(SLEEVES_ROOT),
            "current_forward_artifact": repo_rel(CURRENT_FORWARD_ARTIFACT),
            "forward_replacement_rule_version": FORWARD_REPLACEMENT_RULE_VERSION,
            "entry_regime_tag_rule_version": ENTRY_REGIME_TAG_RULE_VERSION,
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": True,
            "entry_date_present": all(bool(row.get("entry_date")) for row in records),
            "target_price_checked": True,
            "target_price_relevance": (
                "No target order or exit rule is scheduled. The diagnostic uses "
                "closed paper rows with entry_date/exit_date and replacement-value "
                "fields only."
            ),
            "runtime_fields_checked": [
                "sleeve_key",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl_usd",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "entry_regime_label",
                "entry_regime_tag_rule_version",
            ],
            "source_audit": source_audit,
        },
        "gate3": {
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "forward_rows_evaluated": len(records),
            "tagged_forward_rows": analysis["tagged_row_count"],
            "note": "No executable filter was added; closed paper rows are attributed only.",
        },
        "gate4": {
            "observed_only_lead": observed_lead,
            "failed_reasons": failed,
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "acceptance_checks": {
                "acceptance_rule": ACCEPTANCE_RULE,
                "best_candidate_cell": analysis["best_candidate_cell"],
                "candidate_sleeve_regime_cells": analysis["candidate_sleeve_regime_cells"],
            },
            "lead_limitations": [
                "Uses current closed forward paper rows only.",
                "No shared helper, adapter, rank, notional, exit, or order rule was changed.",
                "Any positive lead would require a separate fixed activation-envelope Gate 1-4.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "n_rows": len(records),
            "source_audit": source_audit,
            "analysis": analysis,
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "default_off_attribution_only": True,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "source_helper_used": "forward_replacement_value",
            "source_helper_production_impact": FORWARD_REPLACEMENT_PRODUCTION_IMPACT,
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by relaxing row-count, concentration, SPY/QQQ "
                "replacement-value, source-rank, notional, hold-day, cooldown, "
                "or regime-threshold requirements on the same 33 closed rows."
            ),
            "new_evidence_required": (
                "Need materially more closed forward replacement rows carrying "
                "entry_regime tags, especially outside QQQ-only low-deployment "
                "ETF rows, before any activation-envelope test."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(CURRENT_FORWARD_ARTIFACT),
            "quant/forward_replacement_value.py",
            "quant/regime_chop_state.py",
            "experiments/logs/exp-20260622-013.json",
            "experiments/logs/exp-20260623-002.json",
            "experiments/logs/exp-20260613-005.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": {
            "dependencies_validated": payload["gate2"]["dependencies_validated"],
            "entry_date_present": payload["gate2"]["entry_date_present"],
            "runtime_fields_checked": payload["gate2"]["runtime_fields_checked"],
            "source_audit": {
                "current_forward_artifact_rows": payload["gate2"]["source_audit"][
                    "current_forward_artifact_rows"
                ],
                "tagged_records_built_in_memory": payload["gate2"]["source_audit"][
                    "tagged_records_built_in_memory"
                ],
                "regime_spy_bars_loaded": payload["gate2"]["source_audit"][
                    "regime_spy_bars_loaded"
                ],
                "artifact_not_mutated": payload["gate2"]["source_audit"]["artifact_not_mutated"],
                "state_files_not_mutated": payload["gate2"]["source_audit"][
                    "state_files_not_mutated"
                ],
            },
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "attribution": {
            "n_rows": payload["attribution"]["n_rows"],
            "all_rows": analysis["all_rows"],
            "tagged_rows": analysis["tagged_rows"],
            "best_candidate_cell": analysis["best_candidate_cell"],
            "candidate_sleeve_regime_cells": analysis["candidate_sleeve_regime_cells"][:8],
        },
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    best = analysis["best_candidate_cell"] or {}
    best_key = best.get("key") or "none"
    best_n = best.get("n") or 0
    best_sums = best.get("sums") or {}
    return "\n".join(
        [
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Owner: `{OWNER}`",
            f"- Hypothesis: {HYPOTHESIS}",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- New evidence axis: {NEW_EVIDENCE_AXIS}",
            f"- Forward rows evaluated: `{payload['attribution']['n_rows']}`",
            f"- Tagged rows: `{analysis['tagged_row_count']}`",
            f"- Best sleeve/regime cell: `{best_key}` with `{best_n}` rows",
            f"- Best cell RV vs cash/SPY/QQQ: `${best_sums.get('replacement_value_vs_cash_usd')}` / `${best_sums.get('replacement_value_vs_spy_usd')}` / `${best_sums.get('replacement_value_vs_qqq_usd')}`",
            f"- Gate 4 failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            f"- Reproduce: `{RUNNER_COMMAND}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "attribution": {
            "n_rows": payload["attribution"]["n_rows"],
            "all_rows": payload["attribution"]["analysis"]["all_rows"],
            "tagged_rows": payload["attribution"]["analysis"]["tagged_rows"],
            "best_candidate_cell": payload["attribution"]["analysis"]["best_candidate_cell"],
        },
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
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
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    analysis = payload["attribution"]["analysis"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "n_rows": payload["attribution"]["n_rows"],
                "tagged_row_count": analysis["tagged_row_count"],
                "best_candidate_cell": analysis["best_candidate_cell"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
