"""exp-20260525-023: expectation revision coverage repair.

Read-only measurement repair for the expectation drift leg of the
expectation-residual leadership direction. The experiment explains why daily
candidate objects do or do not have usable PIT estimate-revision rows and 7d/30d
EPS deltas.

It does not alter signal generation, ranking, sizing, exits, LLM/news, or
orders.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-023"
STEM = "expectation_revision_coverage_repair"
MECHANISM_FAMILY = "expectation_residual_leadership"
TRIAL_FAMILY = "expectation_revision_coverage_repair"
CHANGED_VARIABLE = "expectation_revision_coverage_repair_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from data_paths import daily_artifact_glob, resolve_daily_artifact_path  # noqa: E402
from estimate_revision_ledger import parse_snapshot_date  # noqa: E402
from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    _coerce_date,
    _float,
    _open_position_field_check,
    _read_jsonl,
    _repo_rel,
    _safe,
    _utc_now,
    _write_json,
    load_candidates,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

RERUN_READINESS_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -B "
    "quant\\experiments\\exp_20260525_021_expectation_residual_readiness_audit.py"
)
RERUN_ATTRIBUTION_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -B "
    "quant\\experiments\\exp_20260525_017_expectation_residual_leadership_attribution.py"
)


def production_impact() -> dict[str, bool]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": False,
        "parity_test_added": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }


def _date_tag(value: str | date | datetime) -> str:
    return _coerce_date(value).strftime("%Y%m%d")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _ledger_path(data_dir: Path, as_of: str | date | datetime) -> Path:
    return data_dir / "non_ohlcv" / f"estimate_revision_ledger_{_date_tag(as_of)}.jsonl"


def load_ledger_rows(data_dir: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], set[str]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    dates = set()
    for path in sorted((data_dir / "non_ohlcv").glob("estimate_revision_ledger_*.jsonl")):
        tag = path.stem.rsplit("_", 1)[-1]
        try:
            dates.add(datetime.strptime(tag, "%Y%m%d").date().isoformat())
        except ValueError:
            pass
        for row in _read_jsonl(path):
            ticker = str(row.get("ticker") or "").upper()
            as_of = row.get("as_of_date")
            if ticker and as_of:
                by_key[(str(as_of), ticker)] = row
    return by_key, dates


def load_snapshot_index(data_dir: Path) -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for path in daily_artifact_glob("earnings_snapshot", data_dir):
        payload = _read_json(path)
        as_of = parse_snapshot_date(path, payload).isoformat()
        earnings = payload.get("earnings") if isinstance(payload, dict) else {}
        tickers = {
            str(ticker).upper()
            for ticker, row in (earnings or {}).items()
            if isinstance(row, dict)
        }
        snapshots[as_of] = {
            "path": _repo_rel(path),
            "ticker_count": len(tickers),
            "tickers": tickers,
            "timestamp": payload.get("timestamp"),
        }
    return snapshots


def ledger_gap_reason(
    *,
    as_of: str,
    ticker: str,
    ledger_row: dict[str, Any] | None,
    ledger_file_exists: bool,
    snapshot_info: dict[str, Any] | None,
) -> str | None:
    if ledger_row is not None:
        return None
    if not ledger_file_exists and snapshot_info is None:
        return "missing_ledger_file_and_same_day_earnings_snapshot"
    if not ledger_file_exists:
        return "missing_ledger_file_snapshot_exists"
    if snapshot_info is None:
        return "ledger_file_exists_but_same_day_snapshot_not_visible"
    if ticker not in snapshot_info.get("tickers", set()):
        return "ticker_missing_from_earnings_snapshot"
    return "ticker_present_in_snapshot_but_missing_ledger_row"


def delta_gap_reason(row: dict[str, Any] | None, field: str) -> str | None:
    if row is None:
        return "missing_ledger_row"
    if not row.get("estimate_revision_usable"):
        return f"ledger_row_not_usable:{row.get('pit_caveat') or 'unknown_pit_caveat'}"
    if row.get(field) is not None:
        return None

    days = 7 if field.endswith("_7d") else 30
    prior = row.get("prior_snapshot_date")
    as_of = row.get("as_of_date")
    if not prior:
        return f"no_prior_same_event_snapshot_for_{days}d_delta"
    try:
        day_gap = (_coerce_date(as_of) - _coerce_date(prior)).days
    except Exception:
        return f"same_event_history_missing_prior_age_for_{days}d_delta"
    if day_gap < days:
        return f"same_event_history_too_short_for_{days}d_delta"
    return f"no_snapshot_at_least_{days}d_back"


def expectation_state(row: dict[str, Any] | None) -> str:
    if row is None:
        return "missing_ledger_row"
    if not row.get("estimate_revision_usable"):
        return "ledger_row_not_usable"
    delta_7d = _float(row.get("eps_estimate_delta_7d"), None)
    if delta_7d is None:
        return "usable_ledger_missing_7d_delta"
    if delta_7d > 0:
        return "positive_expectation_ready"
    return "non_positive_eps_estimate_delta_7d"


def audit_candidate(
    candidate: dict[str, Any],
    *,
    ledger_rows: dict[tuple[str, str], dict[str, Any]],
    ledger_dates: set[str],
    snapshot_index: dict[str, dict[str, Any]],
    data_dir: Path,
) -> dict[str, Any]:
    as_of = str(candidate.get("as_of_date"))
    ticker = str(candidate.get("ticker") or "").upper()
    ledger_row = ledger_rows.get((as_of, ticker))
    ledger_file = _ledger_path(data_dir, as_of)
    snapshot_info = snapshot_index.get(as_of)
    root_cause = ledger_gap_reason(
        as_of=as_of,
        ticker=ticker,
        ledger_row=ledger_row,
        ledger_file_exists=as_of in ledger_dates or ledger_file.exists(),
        snapshot_info=snapshot_info,
    )
    delta_7d_gap = delta_gap_reason(ledger_row, "eps_estimate_delta_7d")
    delta_30d_gap = delta_gap_reason(ledger_row, "eps_estimate_delta_30d")
    return {
        "as_of_date": as_of,
        "ticker": ticker,
        "candidate_source": candidate.get("candidate_source"),
        "record_type": candidate.get("record_type"),
        "selected_signal": candidate.get("selected_signal"),
        "strategy": candidate.get("strategy"),
        "ledger_file_path": _repo_rel(ledger_file),
        "ledger_file_exists": as_of in ledger_dates or ledger_file.exists(),
        "ledger_row_exists": ledger_row is not None,
        "ledger_root_cause": root_cause,
        "snapshot_path": snapshot_info.get("path") if snapshot_info else None,
        "snapshot_exists": snapshot_info is not None,
        "snapshot_ticker_count": snapshot_info.get("ticker_count") if snapshot_info else 0,
        "ticker_in_snapshot": bool(snapshot_info and ticker in snapshot_info.get("tickers", set())),
        "estimate_revision_usable": bool(ledger_row and ledger_row.get("estimate_revision_usable")),
        "pit_caveat": ledger_row.get("pit_caveat") if ledger_row else None,
        "same_event_history_count": ledger_row.get("same_event_history_count") if ledger_row else None,
        "prior_snapshot_date": ledger_row.get("prior_snapshot_date") if ledger_row else None,
        "next_earnings_date": ledger_row.get("next_earnings_date") if ledger_row else None,
        "eps_estimate": ledger_row.get("eps_estimate") if ledger_row else None,
        "eps_estimate_delta_prev": ledger_row.get("eps_estimate_delta_prev") if ledger_row else None,
        "eps_estimate_delta_7d": ledger_row.get("eps_estimate_delta_7d") if ledger_row else None,
        "eps_estimate_delta_30d": ledger_row.get("eps_estimate_delta_30d") if ledger_row else None,
        "eps_estimate_delta_7d_gap_reason": delta_7d_gap,
        "eps_estimate_delta_30d_gap_reason": delta_30d_gap,
        "expectation_state": expectation_state(ledger_row),
        "candidate_match_gap_reason": ledger_row.get("candidate_match_gap_reason") if ledger_row else None,
    }


def build_coverage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[row["as_of_date"]].append(row)

    daily = {}
    for as_of, items in sorted(by_date.items()):
        daily[as_of] = {
            "candidate_count": len(items),
            "ledger_file_exists": any(row["ledger_file_exists"] for row in items),
            "snapshot_exists": any(row["snapshot_exists"] for row in items),
            "ledger_rows_joined": sum(1 for row in items if row["ledger_row_exists"]),
            "usable_ledger_rows": sum(1 for row in items if row["estimate_revision_usable"]),
            "eps_estimate_delta_7d_available": sum(
                1 for row in items if row["eps_estimate_delta_7d"] is not None
            ),
            "eps_estimate_delta_30d_available": sum(
                1 for row in items if row["eps_estimate_delta_30d"] is not None
            ),
            "positive_expectation_ready": sum(
                1 for row in items if row["expectation_state"] == "positive_expectation_ready"
            ),
            "ledger_root_cause_counts": dict(
                Counter(row["ledger_root_cause"] for row in items if row["ledger_root_cause"])
            ),
            "delta_7d_gap_counts": dict(
                Counter(
                    row["eps_estimate_delta_7d_gap_reason"]
                    for row in items
                    if row["eps_estimate_delta_7d_gap_reason"]
                )
            ),
        }

    unknown_reasons = [
        row
        for row in rows
        if (
            row["ledger_root_cause"] is None
            and row["eps_estimate_delta_7d_gap_reason"] is None
            and row["expectation_state"] not in {
                "positive_expectation_ready",
                "non_positive_eps_estimate_delta_7d",
            }
        )
    ]

    return {
        "candidate_objects_total": len(rows),
        "candidate_dates": sorted({row["as_of_date"] for row in rows}),
        "candidate_source_breakdown": dict(Counter(row["candidate_source"] for row in rows)),
        "record_type_breakdown": dict(Counter(row["record_type"] for row in rows)),
        "daily_coverage": daily,
        "ledger_join_coverage": {
            "ledger_rows_joined": sum(1 for row in rows if row["ledger_row_exists"]),
            "missing_ledger_rows": sum(1 for row in rows if not row["ledger_row_exists"]),
            "usable_ledger_rows": sum(1 for row in rows if row["estimate_revision_usable"]),
            "ledger_root_cause_counts": dict(
                Counter(row["ledger_root_cause"] for row in rows if row["ledger_root_cause"])
            ),
            "pit_caveat_counts": dict(
                Counter(row["pit_caveat"] for row in rows if row["pit_caveat"])
            ),
        },
        "delta_availability": {
            "eps_estimate_delta_7d_available": sum(
                1 for row in rows if row["eps_estimate_delta_7d"] is not None
            ),
            "eps_estimate_delta_30d_available": sum(
                1 for row in rows if row["eps_estimate_delta_30d"] is not None
            ),
            "eps_estimate_delta_7d_gap_counts": dict(
                Counter(
                    row["eps_estimate_delta_7d_gap_reason"]
                    for row in rows
                    if row["eps_estimate_delta_7d_gap_reason"]
                )
            ),
            "eps_estimate_delta_30d_gap_counts": dict(
                Counter(
                    row["eps_estimate_delta_30d_gap_reason"]
                    for row in rows
                    if row["eps_estimate_delta_30d_gap_reason"]
                )
            ),
        },
        "expectation_state_counts": dict(Counter(row["expectation_state"] for row in rows)),
        "positive_expectation_candidates": sum(
            1 for row in rows if row["expectation_state"] == "positive_expectation_ready"
        ),
        "unknown_reason_count": len(unknown_reasons),
        "unknown_reason_rows": unknown_reasons[:20],
    }


def evaluate_repair_gate(summary: dict[str, Any]) -> dict[str, Any]:
    passed = summary["unknown_reason_count"] == 0
    return {
        "passed": passed,
        "decision": "observed_only_data_gap_explained" if passed else "observed_only_unknown_data_gap",
        "unknown_reason_count": summary["unknown_reason_count"],
        "all_missing_reasons_explained": passed,
        "strategy_behavior_changed": False,
    }


def evaluate_alpha_readiness(summary: dict[str, Any]) -> dict[str, Any]:
    ready = summary["positive_expectation_candidates"] > 0
    reasons = []
    if not ready:
        reasons.append("positive_expectation_candidates_zero")
    return {
        "ready_to_rerun_readiness_audit": ready,
        "ready_to_rerun_attribution": False,
        "decision": "expectation_coverage_has_positive_candidates" if ready else "expectation_coverage_still_empty",
        "blocking_reasons": reasons,
        "rerun_readiness_command": RERUN_READINESS_COMMAND,
        "rerun_attribution_command": RERUN_ATTRIBUTION_COMMAND,
        "note": (
            "A positive expectation candidate is not sufficient for alpha "
            "interpretation; exp-20260525-021 must still pass Bucket A and total "
            "coverage gates before exp-20260525-017 is interpreted."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    summary = payload["coverage_summary"]
    lines = [
        f"# {EXPERIMENT_ID} Expectation Revision Coverage Repair",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Read-only measurement repair. No entries, exits, ranking, sizing, LLM/news, or orders changed.",
        "",
        "## Repair Gate",
        "",
        "```json",
        json.dumps(payload["repair_gate"], indent=2, sort_keys=True),
        "```",
        "",
        "## Alpha Readiness",
        "",
        "```json",
        json.dumps(payload["alpha_readiness"], indent=2, sort_keys=True),
        "```",
        "",
        "## Coverage Summary",
        "",
        "```json",
        json.dumps(
            {
                "candidate_objects_total": summary["candidate_objects_total"],
                "ledger_join_coverage": summary["ledger_join_coverage"],
                "delta_availability": summary["delta_availability"],
                "expectation_state_counts": summary["expectation_state_counts"],
                "positive_expectation_candidates": summary["positive_expectation_candidates"],
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "No JavaScript was used.",
        "",
    ]
    return "\n".join(lines)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_payload(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or (REPO_ROOT / "data")
    timestamp = _utc_now()
    candidates, _features_by_date = load_candidates(data_dir)
    ledger_rows, ledger_dates = load_ledger_rows(data_dir)
    snapshot_index = load_snapshot_index(data_dir)
    audit_rows = [
        audit_candidate(
            candidate,
            ledger_rows=ledger_rows,
            ledger_dates=ledger_dates,
            snapshot_index=snapshot_index,
            data_dir=data_dir,
        )
        for candidate in candidates
    ]
    coverage_summary = build_coverage_summary(audit_rows)
    repair_gate = evaluate_repair_gate(coverage_summary)
    alpha_readiness = evaluate_alpha_readiness(coverage_summary)
    field_check = _open_position_field_check()
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(EXPERIMENT_LOG_JSONL),
    ]
    status = "observed_only_data_gap" if repair_gate["passed"] else "rejected"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": repair_gate["decision"],
        "lane": "measurement_repair",
        "read_only": True,
        "hypothesis": (
            "The expectation-residual alpha path is blocked by explainable "
            "PIT estimate-revision coverage gaps rather than by a strategy "
            "result; those gaps can be classified without changing behavior."
        ),
        "change_summary": (
            "Read-only expectation revision coverage repair/audit for candidate "
            "ledger joins and 7d/30d EPS delta availability."
        ),
        "change_type": "measurement_repair_coverage_audit",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "coverage_repair_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 1,
        "nearby_prior_experiments": ["exp-20260525-017", "exp-20260525-021"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "expectation_revision_candidate_join_gap_attribution",
        "component": "quant/experiments/exp_20260525_023_expectation_revision_coverage_repair.py",
        "parameters": {
            "positive_expectation_definition": "estimate_revision_usable && eps_estimate_delta_7d > 0",
            "no_expectation_fallback": True,
            "audit_scope": [
                "candidate-to-ledger join",
                "same-day earnings snapshot presence",
                "PIT usability caveat",
                "eps_estimate_delta_7d availability",
                "eps_estimate_delta_30d availability",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            "candidate_artifacts": "data/daily/signals/quant/quant_signals_*.json",
            "estimate_revision_ledgers": "data/non_ohlcv/estimate_revision_ledger_*.jsonl",
            "earnings_snapshots": "data/daily/snapshots/earnings/earnings_snapshot_*.json and legacy data/earnings_snapshot_*.json",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "measurement repair: classify expectation-revision coverage "
                "blockers that prevent Bucket A attribution."
            ),
            "2_history_check": (
                "exp-20260525-017 and exp-20260525-021 both show Bucket A = 0 "
                "because positive expectation coverage is absent."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "All missing ledger / missing 7d-delta cases must receive a "
                "specific root cause, with strategy behavior delta = 0."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260525_023_expectation_revision_coverage_repair.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": "data/experiments/exp-20260517-009/",
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "note": "This coverage repair is read-only; no before/after core metrics are changed.",
        },
        "gate2": {
            "passed": bool(field_check.get("passed", False)),
            "field_check": field_check,
            "rule_dependencies": [
                "daily quant candidate objects",
                "estimate_revision_ledger rows by as_of_date/ticker",
                "same-day earnings snapshot artifacts",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": repair_gate["passed"],
            "note": (
                "Passing this repair gate only means coverage gaps are explained; "
                "it does not permit PEAD/ranking/sizing work until the readiness "
                "audit passes."
            ),
        },
        "repair_gate": repair_gate,
        "alpha_readiness": alpha_readiness,
        "coverage_summary": coverage_summary,
        "candidate_audit_rows": audit_rows,
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "candidate_objects_total": coverage_summary["candidate_objects_total"],
            "missing_ledger_rows": coverage_summary["ledger_join_coverage"]["missing_ledger_rows"],
            "eps_estimate_delta_7d_available": coverage_summary["delta_availability"][
                "eps_estimate_delta_7d_available"
            ],
            "positive_expectation_candidates": coverage_summary["positive_expectation_candidates"],
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": production_impact(),
        "decision_rule": (
            "Do not advance to PEAD paper sleeve, ranking score replacement, or "
            "exp-20260525-017 interpretation until exp-20260525-021 readiness "
            "gate passes."
        ),
        "rejection_reason": None
        if repair_gate["passed"]
        else "unexplained expectation revision coverage gap remains",
        "next_evidence_needed": (
            "Continue PIT earnings snapshots and estimate-revision ledgers until "
            "future candidates have usable eps_estimate_delta_7d rows; then rerun "
            "exp-20260525-021."
        ),
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "experiment_id",
        "timestamp",
        "status",
        "hypothesis",
        "change_summary",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "component",
        "parameters",
        "date_range",
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "repair_gate",
        "alpha_readiness",
        "coverage_summary",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "expected_value_score_delta",
        "llm_metrics",
        "production_impact",
        "decision",
        "decision_rule",
        "rejection_reason",
        "next_evidence_needed",
        "related_files",
        "anti_js",
    )
    return {key: payload[key] for key in keys}


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "measurement_repair",
            "owner": "codex",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": CHANGED_VARIABLE,
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(DOC_LOG),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "status": payload["status"],
                    "repair_gate": payload["repair_gate"],
                    "alpha_readiness": payload["alpha_readiness"],
                    "output": _repo_rel(OUT_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
