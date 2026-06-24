"""exp-20260624-001: sleeve health versus forward replacement value.

Observed-only alpha attribution. This runner joins enriched closed forward
replacement rows to the most recent production sleeve_health row known at entry
date. It asks whether a fresh/ok sleeve surface has allocation value, while
changing no strategy, ranking, sizing, exit, ledger, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260624-001"
OWNER = "alpha-explore"
SLUG = "forward_sleeve_health_replacement_attribution"
RUNNER = f"quant/experiments/exp_20260624_001_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_001_{SLUG}.json"
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
FORWARD_REPLACEMENT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
SLEEVE_HEALTH = REPO_ROOT / "data" / "paper_sleeves" / "sleeve_health.jsonl"

HYPOTHESIS = (
    "risk_allocation/candidate_pool attribution: default-off forward replacement "
    "rows whose sleeve had a fresh ok sleeve_health status at entry should show "
    "better replacement value than rows with missing, stale, or failing health "
    "context; otherwise sleeve_health remains measurement-only and must not gate "
    "allocation."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "observed_only_attribution"
TRIAL_FAMILY = "observed_only_attribution"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = "entry_date_sleeve_health_status_vs_forward_replacement_value_v1"
NEW_EVIDENCE_TYPE = "production_visible_sleeve_health_forward_attribution"
NEW_EVIDENCE_AXIS = (
    "Production daily sleeve_health freshness/status joined point-in-time to "
    "closed forward replacement rows. This is not a sleeve activation threshold, "
    "source rank, notional, hold-day, or ETF/stock composition retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260612-004",
    "exp-20260612-010",
    "exp-20260622-013",
    "exp-20260623-028",
]
CAUSAL_COMPONENTS = [
    "read-only forward replacement rows",
    "entry-date sleeve_health join",
    "health-status cohort attribution",
    "no strategy behavior change",
]
REPLACEMENT_FIELDS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
CONFIG = {
    "min_fresh_ok_rows": 8,
    "min_comparator_rows": 8,
    "min_distinct_fresh_ok_sleeves": 2,
    "min_mean_comparator_wins": 2,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        output = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(output):
        return None
    return output


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def normalize_sleeve_key(value: str) -> str:
    out = value.lower()
    for token in (
        "_paper_sleeve",
        "_event_sleeve",
        "_stock_leadership",
        "_overlay",
        "_sleeve",
        "_paper",
    ):
        out = out.replace(token, "")
    return out


def row_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("decision_id") or ""),
            str(row.get("sleeve_key") or ""),
            str(row.get("ticker") or ""),
            str(row.get("entry_date") or ""),
            str(row.get("exit_date") or ""),
        ]
    )


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict) and prediction.get("confidence_reason"):
        return prediction
    return {
        "recorded_at": utc_now(),
        "success_probability": 0.22,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "health_rows_too_recent",
            "no_unhealthy_comparator_rows",
            "forward_rows_too_few",
            "health_status_not_predictive",
        ],
        "confidence_reason": (
            "Fallback prediction copied from the reserved hypothesis: sleeve "
            "health is production-visible but may be too recent or too uniform."
        ),
    }


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(window.get("max_drawdown_pct") or 0.0) for window in windows),
            default=None,
        ),
        "windows": windows,
    }


def load_health_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = read_jsonl(SLEEVE_HEALTH)
    rows = [
        row
        for row in raw
        if isinstance(row.get("disk_status"), dict) and str(row.get("asof_date") or "")[:10]
    ]
    rows.sort(key=lambda row: str(row.get("asof_date") or "")[:10])
    return rows, {
        "source_artifact": repo_rel(SLEEVE_HEALTH),
        "raw_rows": len(raw),
        "usable_rows": len(rows),
        "asof_min": str(rows[0].get("asof_date"))[:10] if rows else None,
        "asof_max": str(rows[-1].get("asof_date"))[:10] if rows else None,
        "rule_versions": sorted({str(row.get("rule_version") or "unknown") for row in rows}),
        "artifact_not_mutated": True,
    }


def latest_health_for_entry(
    health_rows: list[dict[str, Any]],
    entry_date: str,
) -> dict[str, Any] | None:
    chosen = None
    for row in health_rows:
        if str(row.get("asof_date") or "")[:10] <= entry_date:
            chosen = row
        else:
            break
    return chosen


def health_status_for_sleeve(
    health_row: dict[str, Any] | None,
    sleeve_key: str,
) -> dict[str, Any]:
    if health_row is None:
        return {
            "health_cohort": "missing_health",
            "health_asof_date": None,
            "disk_status": "missing_health_row",
            "staleness_sessions": None,
            "matching_build_failures": [],
        }

    disk_status = health_row.get("disk_status") or {}
    disk_entry = disk_status.get(sleeve_key)
    if disk_entry is None:
        disk_entry = disk_status.get(normalize_sleeve_key(sleeve_key))
    if not isinstance(disk_entry, dict):
        disk_entry = {"status": "missing_sleeve_disk_status", "staleness_sessions": None}

    normalized = normalize_sleeve_key(sleeve_key)
    failures = []
    for item in health_row.get("failing_builds") or []:
        item_norm = normalize_sleeve_key(str(item))
        if item_norm == normalized or item_norm.startswith(normalized) or normalized.startswith(item_norm):
            failures.append(str(item))

    disk_state = str(disk_entry.get("status") or "unknown")
    fresh = disk_state in {"fresh", "fresh_summary"} and not failures
    cohort = "fresh_ok" if fresh else "degraded_or_stale"
    return {
        "health_cohort": cohort,
        "health_asof_date": str(health_row.get("asof_date") or "")[:10],
        "disk_status": disk_state,
        "staleness_sessions": disk_entry.get("staleness_sessions"),
        "matching_build_failures": failures,
    }


def load_joined_forward_rows(
    health_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows = read_jsonl(FORWARD_REPLACEMENT)
    deduped: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        deduped[row_key(row)] = row

    usable: list[dict[str, Any]] = []
    missing_required = 0
    for row in deduped.values():
        entry_date = str(row.get("entry_date") or "")[:10]
        sleeve_key = str(row.get("sleeve_key") or "")
        ticker = str(row.get("ticker") or "").upper()
        if not entry_date or not sleeve_key or not ticker:
            missing_required += 1
            continue
        values = {field: as_float(row.get(field)) for field in REPLACEMENT_FIELDS}
        if any(value is None for value in values.values()):
            missing_required += 1
            continue
        health = health_status_for_sleeve(latest_health_for_entry(health_rows, entry_date), sleeve_key)
        usable.append(
            {
                **row,
                **values,
                **health,
                "ticker": ticker,
                "sleeve_key": sleeve_key,
                "entry_date": entry_date,
                "entry_month": entry_date[:7],
            }
        )
    usable.sort(
        key=lambda item: (
            str(item.get("health_cohort") or ""),
            str(item.get("entry_date") or ""),
            str(item.get("sleeve_key") or ""),
            str(item.get("ticker") or ""),
        )
    )
    return usable, {
        "source_artifact": repo_rel(FORWARD_REPLACEMENT),
        "raw_rows": len(raw_rows),
        "deduped_rows": len(deduped),
        "usable_rows": len(usable),
        "missing_required_rows": missing_required,
        "cohort_counts": dict(sorted(Counter(row["health_cohort"] for row in usable).items())),
        "artifact_not_mutated": True,
    }


def top_counts(rows: list[dict[str, Any]], key: str, limit: int = 10) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(key) or "unknown") for row in rows)
    denominator = len(rows) or 1
    return [
        {"key": value, "n": count, "row_share": round(count / denominator, 6)}
        for value, count in counts.most_common(limit)
    ]


def field_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [float(row[field]) for row in rows if as_float(row.get(field)) is not None]
    return {
        "sum": round(sum(values), 2) if values else 0.0,
        "mean": round_or_none(mean(values), 4),
        "median": round_or_none(median(values), 4) if values else None,
        "min": round_or_none(min(values), 4) if values else None,
        "max": round_or_none(max(values), 4) if values else None,
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6)
        if values
        else None,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "n": len(rows),
        "distinct_tickers": len({str(row.get("ticker") or "unknown") for row in rows}),
        "distinct_sleeves": len({str(row.get("sleeve_key") or "unknown") for row in rows}),
        "tickers": top_counts(rows, "ticker"),
        "sleeves": top_counts(rows, "sleeve_key"),
        "entry_months": top_counts(rows, "entry_month"),
        "disk_statuses": top_counts(rows, "disk_status"),
    }
    for field in REPLACEMENT_FIELDS:
        summary[field] = field_summary(rows, field)
    return summary


def summarize_grouped(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return {value: summarize_rows(group) for value, group in sorted(grouped.items())}


def compare_fresh_to_comparator(fresh: dict[str, Any], comparator: dict[str, Any]) -> dict[str, Any]:
    by_field: dict[str, Any] = {}
    wins = 0
    for field in REPLACEMENT_FIELDS:
        fresh_mean = fresh[field]["mean"]
        comparator_mean = comparator[field]["mean"]
        delta = None
        beats = False
        if fresh_mean is not None and comparator_mean is not None:
            delta = round(fresh_mean - comparator_mean, 4)
            beats = fresh_mean > comparator_mean
            wins += int(beats)
        by_field[field] = {
            "fresh_ok_mean": fresh_mean,
            "comparator_mean": comparator_mean,
            "fresh_minus_comparator_mean": delta,
            "fresh_beats_comparator_mean": beats,
        }
    return {"by_field": by_field, "fresh_mean_comparator_wins": wins}


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fresh_rows = [row for row in rows if row["health_cohort"] == "fresh_ok"]
    comparator_rows = [row for row in rows if row["health_cohort"] != "fresh_ok"]
    fresh_summary = summarize_rows(fresh_rows)
    comparator_summary = summarize_rows(comparator_rows)
    return {
        "all_rows": summarize_rows(rows),
        "cohorts": {
            "fresh_ok": fresh_summary,
            "not_fresh_ok": comparator_summary,
            **summarize_grouped(rows, "health_cohort"),
        },
        "fresh_ok_vs_not_fresh_ok": compare_fresh_to_comparator(
            fresh_summary,
            comparator_summary,
        ),
        "fresh_ok_by_sleeve": summarize_grouped(fresh_rows, "sleeve_key"),
        "not_fresh_ok_by_sleeve": summarize_grouped(comparator_rows, "sleeve_key"),
        "sample_rows": [
            {
                "health_cohort": row.get("health_cohort"),
                "health_asof_date": row.get("health_asof_date"),
                "disk_status": row.get("disk_status"),
                "sleeve_key": row.get("sleeve_key"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "replacement_value_vs_cash_usd": round_or_none(
                    row.get("replacement_value_vs_cash_usd"), 2
                ),
                "replacement_value_vs_spy_usd": round_or_none(
                    row.get("replacement_value_vs_spy_usd"), 2
                ),
                "replacement_value_vs_qqq_usd": round_or_none(
                    row.get("replacement_value_vs_qqq_usd"), 2
                ),
            }
            for row in rows[:20]
        ],
    }


def acceptance_checks(analysis: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    fresh = analysis["cohorts"]["fresh_ok"]
    comparator = analysis["cohorts"]["not_fresh_ok"]
    comparison = analysis["fresh_ok_vs_not_fresh_ok"]
    checks = {
        "fresh_ok_rows_passed": fresh["n"] >= CONFIG["min_fresh_ok_rows"],
        "comparator_rows_passed": comparator["n"] >= CONFIG["min_comparator_rows"],
        "fresh_ok_distinct_sleeves_passed": (
            fresh["distinct_sleeves"] >= CONFIG["min_distinct_fresh_ok_sleeves"]
        ),
        "fresh_ok_total_positive_all_comparators": all(
            fresh[field]["sum"] > 0 for field in REPLACEMENT_FIELDS
        ),
        "fresh_ok_mean_positive_all_comparators": all(
            (fresh[field]["mean"] or 0.0) > 0 for field in REPLACEMENT_FIELDS
        ),
        "fresh_ok_mean_beats_not_fresh_two_comparators": (
            comparison["fresh_mean_comparator_wins"] >= CONFIG["min_mean_comparator_wins"]
        ),
    }
    failed: list[str] = []
    if not checks["fresh_ok_rows_passed"]:
        failed.append("fresh_ok_rows_below_minimum")
    if not checks["comparator_rows_passed"]:
        failed.append("not_fresh_ok_rows_below_minimum")
    if not checks["fresh_ok_distinct_sleeves_passed"]:
        failed.append("fresh_ok_distinct_sleeves_below_minimum")
    if not checks["fresh_ok_total_positive_all_comparators"]:
        failed.append("fresh_ok_total_not_positive_all_comparators")
    if not checks["fresh_ok_mean_positive_all_comparators"]:
        failed.append("fresh_ok_mean_not_positive_all_comparators")
    if not checks["fresh_ok_mean_beats_not_fresh_two_comparators"]:
        failed.append("fresh_ok_mean_does_not_beat_not_fresh_two_comparators")
    return checks, failed


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    observed_modes = []
    if (
        "fresh_ok_rows_below_minimum" in failed
        or "not_fresh_ok_rows_below_minimum" in failed
    ):
        observed_modes.append("health_rows_too_recent")
    if "not_fresh_ok_rows_below_minimum" in failed:
        observed_modes.append("no_unhealthy_comparator_rows")
    if "fresh_ok_mean_does_not_beat_not_fresh_two_comparators" in failed:
        observed_modes.append("health_status_not_predictive")
    declared = set(prediction.get("main_failure_modes") or [])
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": int(actual),
        "brier_score": round((probability - actual) ** 2, 6),
        "failed_reasons": failed,
        "failure_modes_observed": observed_modes,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "predicted_failure_mode_hit": bool(declared & set(observed_modes)),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    health_rows, health_audit = load_health_rows()
    rows, source_audit = load_joined_forward_rows(health_rows)
    analysis = analyze(rows)
    checks, failed = acceptance_checks(analysis)
    observed_lead = not failed
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_sleeve_health_replacement_lead_not_promoted"
        if observed_lead
        else "rejected_sleeve_health_not_allocation_ready"
    )
    why = (
        "Fresh sleeve health separated positive forward replacement value, but "
        "this remains forward-only attribution and no allocation gate was promoted."
        if observed_lead
        else "Sleeve health did not clear the fixed attribution screen, most likely "
        "because the health surface starts late, has too little degraded-row "
        "variation, or does not predict replacement value."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
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
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "Reservation novelty gate reported no strong near-neighbor.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "source_saturation": "Not applicable per reservation output.",
            },
            "3_single_policy_bundle": (
                "One read-only attribution bundle: join closed forward replacement "
                "rows to most recent sleeve_health as of entry date and compare "
                "fresh_ok rows against missing/stale/failing health context."
            ),
            "4_success_failure_standard": (
                "Observed-only positive lead only if fresh_ok rows have enough sample, "
                "at least two sleeves, positive total and mean replacement value "
                "versus cash/SPY/QQQ, and fresh_ok mean beats the non-fresh cohort "
                "on at least two comparators."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_artifact": repo_rel(FORWARD_REPLACEMENT),
            "health_artifact": repo_rel(SLEEVE_HEALTH),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "config": CONFIG,
            "replacement_fields": REPLACEMENT_FIELDS,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(rows) and bool(health_rows),
            "source_audit": source_audit,
            "health_audit": health_audit,
            "fields_checked": [
                "entry_date",
                "exit_date",
                "ticker",
                "sleeve_key",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "sleeve_health.asof_date",
                "sleeve_health.disk_status",
                "sleeve_health.failing_builds",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in rows),
            "target_price_relevance": (
                "Not applicable: no executable entry, target, exit, order, or "
                "paper ledger mutation is scheduled by this observed-only attribution."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": source_audit["deduped_rows"],
            "signals_survived": source_audit["usable_rows"],
            "survival_rate": round(source_audit["usable_rows"] / source_audit["deduped_rows"], 4)
            if source_audit["deduped_rows"]
            else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": {
            "observed_only_lead": observed_lead,
            "decision": decision,
            "failed_reasons": failed,
            "acceptance_checks": checks,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Forward-only closed paper rows, not canonical fixed-window alpha evidence.",
                "No shared helper, daily adapter, rank, notional, exit, or order rule changed.",
                "Any allocation gate requires a separate shared-policy Gate 1-4 experiment.",
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
            "analysis": analysis,
            "source_audit": source_audit,
            "health_audit": health_audit,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "parity_note": "Read-only attribution over existing forward and sleeve_health artifacts.",
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing row-count gates, stale-session thresholds, "
                "cohort labels, sleeve inclusion, notional method, hold days, or "
                "activation thresholds on the same forward replacement rows."
            ),
            "new_evidence_required": (
                "Need materially more closed forward rows after sleeve_health has "
                "longer history and real degraded/failing variation, or a separate "
                "shared-policy Gate 1-4 allocation test with a predeclared health gate."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(FORWARD_REPLACEMENT),
            repo_rel(SLEEVE_HEALTH),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260612-004.json",
            "experiments/logs/exp-20260612-010.json",
            "experiments/logs/exp-20260622-013.json",
            "experiments/logs/exp-20260623-028.json",
            "docs/backtesting.md",
            "docs/production_backtest_parity.md",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
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
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "all_rows": analysis["all_rows"],
            "cohorts": analysis["cohorts"],
            "fresh_ok_vs_not_fresh_ok": analysis["fresh_ok_vs_not_fresh_ok"],
            "fresh_ok_by_sleeve": analysis["fresh_ok_by_sleeve"],
            "not_fresh_ok_by_sleeve": analysis["not_fresh_ok_by_sleeve"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "anti_js": payload["anti_js"],
    }


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    fresh = analysis["cohorts"]["fresh_ok"]
    comparator = analysis["cohorts"]["not_fresh_ok"]
    comparison = analysis["fresh_ok_vs_not_fresh_ok"]["by_field"]
    rows = [
        "| Comparator | Fresh Sum | Fresh Mean | Fresh Median | Non-Fresh Mean | Fresh-Non-Fresh Mean |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for field in REPLACEMENT_FIELDS:
        rows.append(
            "| {field} | {fresh_sum} | {fresh_mean} | {fresh_median} | {comp_mean} | {delta} |".format(
                field=field,
                fresh_sum=money(fresh[field]["sum"]),
                fresh_mean=money(fresh[field]["mean"]),
                fresh_median=money(fresh[field]["median"]),
                comp_mean=money(comparator[field]["mean"]),
                delta=money(comparison[field]["fresh_minus_comparator_mean"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: sleeve health forward replacement attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: `false`",
            "- Shared helper promoted: `false`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Cohort Summary",
            "",
            f"- Fresh ok rows: `{fresh['n']}` across `{fresh['distinct_sleeves']}` sleeves",
            f"- Non-fresh/missing rows: `{comparator['n']}` across `{comparator['distinct_sleeves']}` sleeves",
            f"- Fresh mean comparator wins: `{analysis['fresh_ok_vs_not_fresh_ok']['fresh_mean_comparator_wins']}`",
            "",
            "## Replacement Value",
            "",
            *rows,
            "",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        FORWARD_REPLACEMENT,
        SLEEVE_HEALTH,
        BASELINE_RESULT,
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
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "attribution": {
            "cohorts": payload["attribution"]["analysis"]["cohorts"],
            "fresh_ok_vs_not_fresh_ok": payload["attribution"]["analysis"][
                "fresh_ok_vs_not_fresh_ok"
            ],
        },
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
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    analysis = payload["attribution"]["analysis"]
    fresh = analysis["cohorts"]["fresh_ok"]
    comparator = analysis["cohorts"]["not_fresh_ok"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "fresh_ok_rows": fresh["n"],
                "not_fresh_ok_rows": comparator["n"],
                "fresh_cash_sum": fresh["replacement_value_vs_cash_usd"]["sum"],
                "fresh_spy_sum": fresh["replacement_value_vs_spy_usd"]["sum"],
                "fresh_qqq_sum": fresh["replacement_value_vs_qqq_usd"]["sum"],
                "fresh_mean_comparator_wins": analysis["fresh_ok_vs_not_fresh_ok"][
                    "fresh_mean_comparator_wins"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
