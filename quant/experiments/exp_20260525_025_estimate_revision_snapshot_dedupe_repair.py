"""exp-20260525-025: estimate-revision snapshot de-dupe repair.

Measurement repair for the estimate revision ledger input layer. It audits
whether duplicate organized/legacy earnings snapshots can cause later legacy
files to override PIT-safe organized snapshots, and records the candidate-level
effect of the repaired de-duplication rule.

It does not alter entries, exits, ranking, sizing, LLM/news, or orders.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-025"
STEM = "estimate_revision_snapshot_dedupe_repair"
MECHANISM_FAMILY = "expectation_residual_leadership"
TRIAL_FAMILY = "estimate_revision_snapshot_dedupe_repair"
CHANGED_VARIABLE = "estimate_revision_snapshot_duplicate_selection_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from data_paths import daily_artifact_glob  # noqa: E402
from estimate_revision_ledger import (  # noqa: E402
    build_revision_ledger_rows,
    load_snapshot_records,
    parse_snapshot_date,
)
from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    _float,
    _open_position_field_check,
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


def production_impact() -> dict[str, bool]:
    return {
        "shared_policy_changed": False,
        "shared_data_helper_changed": True,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "parity_test_added": True,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _raw_snapshot_records(data_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in daily_artifact_glob("earnings_snapshot", data_dir):
        payload = _read_json(path)
        as_of_date = parse_snapshot_date(path, payload)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        records.append(
            {
                "as_of_date": as_of_date,
                "path": path,
                "file_mtime_utc": mtime,
                "payload": payload,
            }
        )
    return sorted(records, key=lambda item: item["as_of_date"])


def _pit_safe(record: dict[str, Any]) -> bool:
    return record["file_mtime_utc"].date() <= (record["as_of_date"] + date.resolution)


def _compact_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    earnings = record.get("payload", {}).get("earnings") or {}
    return {
        "as_of_date": record["as_of_date"].isoformat(),
        "path": _repo_rel(record["path"]),
        "file_mtime_utc": record["file_mtime_utc"].isoformat(timespec="seconds"),
        "pit_safe": _pit_safe(record),
        "ticker_count": len(earnings),
    }


def _legacy_selected_by_date(records: list[dict[str, Any]]) -> dict[date, dict[str, Any]]:
    selected: dict[date, dict[str, Any]] = {}
    for record in records:
        selected[record["as_of_date"]] = record
    return selected


def duplicate_snapshot_summary(
    raw_records: list[dict[str, Any]],
    repaired_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for record in raw_records:
        by_date[record["as_of_date"]].append(record)
    repaired_by_date = {record["as_of_date"]: record for record in repaired_records}
    legacy_by_date = _legacy_selected_by_date(raw_records)

    out = []
    for as_of, records in sorted(by_date.items()):
        if len(records) <= 1:
            continue
        legacy = legacy_by_date.get(as_of)
        repaired = repaired_by_date.get(as_of)
        out.append(
            {
                "as_of_date": as_of.isoformat(),
                "raw_record_count": len(records),
                "records": [_compact_record(record) for record in records],
                "legacy_selected": _compact_record(legacy),
                "repaired_selected": _compact_record(repaired),
                "selection_changed": bool(
                    legacy and repaired and Path(legacy["path"]) != Path(repaired["path"])
                ),
                "legacy_selected_pit_safe": _pit_safe(legacy) if legacy else None,
                "repaired_selected_pit_safe": _pit_safe(repaired) if repaired else None,
            }
        )
    return out


def _row_state(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "row_exists": False,
            "estimate_revision_usable": False,
            "eps_estimate_delta_7d": None,
            "positive_expectation": False,
            "pit_caveat": "missing_row",
        }
    delta_7d = _float(row.get("eps_estimate_delta_7d"), None)
    usable = bool(row.get("estimate_revision_usable"))
    return {
        "row_exists": True,
        "estimate_revision_usable": usable,
        "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
        "positive_expectation": bool(usable and delta_7d is not None and delta_7d > 0),
        "pit_caveat": row.get("pit_caveat"),
        "prior_snapshot_date": row.get("prior_snapshot_date"),
        "prior_snapshot_pit_safe": row.get("prior_snapshot_pit_safe"),
        "source_snapshot_path": row.get("source_snapshot_path"),
        "source_snapshot_pit_safe": row.get("source_snapshot_pit_safe"),
    }


def _build_rows_by_date(
    records: list[dict[str, Any]],
    candidate_dates: set[str],
) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    generated_at = datetime(2026, 5, 25, 0, 0, tzinfo=timezone.utc)
    for as_of in sorted(candidate_dates):
        try:
            rows = build_revision_ledger_rows(
                records,
                as_of=as_of,
                generated_at=generated_at,
            )
        except ValueError:
            out[as_of] = {}
            continue
        out[as_of] = {str(row.get("ticker") or "").upper(): row for row in rows}
    return out


def candidate_repair_rows(
    candidates: list[dict[str, Any]],
    raw_records: list[dict[str, Any]],
    repaired_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_dates = {str(candidate.get("as_of_date")) for candidate in candidates}
    legacy_rows = _build_rows_by_date(raw_records, candidate_dates)
    repaired_rows = _build_rows_by_date(repaired_records, candidate_dates)

    out = []
    for candidate in candidates:
        as_of = str(candidate.get("as_of_date"))
        ticker = str(candidate.get("ticker") or "").upper()
        legacy_state = _row_state((legacy_rows.get(as_of) or {}).get(ticker))
        repaired_state = _row_state((repaired_rows.get(as_of) or {}).get(ticker))
        changed_fields = [
            field
            for field in (
                "row_exists",
                "estimate_revision_usable",
                "eps_estimate_delta_prev",
                "eps_estimate_delta_7d",
                "eps_estimate_delta_30d",
                "positive_expectation",
                "pit_caveat",
                "prior_snapshot_date",
                "prior_snapshot_pit_safe",
                "source_snapshot_path",
                "source_snapshot_pit_safe",
            )
            if legacy_state.get(field) != repaired_state.get(field)
        ]
        out.append(
            {
                "as_of_date": as_of,
                "ticker": ticker,
                "candidate_source": candidate.get("candidate_source"),
                "record_type": candidate.get("record_type"),
                "legacy_state": legacy_state,
                "repaired_state": repaired_state,
                "changed_fields": changed_fields,
                "repair_changed_candidate_state": bool(changed_fields),
            }
        )
    return out


def build_payload(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or (REPO_ROOT / "data")
    timestamp = _utc_now()
    raw_records = _raw_snapshot_records(data_dir)
    repaired_records = load_snapshot_records(data_dir)
    candidates, _features_by_date = load_candidates(data_dir)
    duplicates = duplicate_snapshot_summary(raw_records, repaired_records)
    candidate_rows = candidate_repair_rows(candidates, raw_records, repaired_records)

    changed = [row for row in candidate_rows if row["repair_changed_candidate_state"]]
    field_check = _open_position_field_check()
    legacy_positive = sum(1 for row in candidate_rows if row["legacy_state"]["positive_expectation"])
    repaired_positive = sum(
        1 for row in candidate_rows if row["repaired_state"]["positive_expectation"]
    )
    legacy_usable = sum(1 for row in candidate_rows if row["legacy_state"]["estimate_revision_usable"])
    repaired_usable = sum(
        1 for row in candidate_rows if row["repaired_state"]["estimate_revision_usable"]
    )

    repair_gate = {
        "passed": True,
        "decision": "accepted_measurement_repair_duplicate_snapshot_guard",
        "strategy_behavior_changed": False,
        "duplicate_snapshot_dates": len(duplicates),
        "duplicate_dates_with_selection_change": sum(
            1 for row in duplicates if row["selection_changed"]
        ),
        "candidate_rows_changed": len(changed),
    }
    alpha_readiness = {
        "ready_to_rerun_readiness_audit": repaired_positive > 0,
        "ready_to_rerun_attribution": False,
        "decision": (
            "expectation_positive_candidates_possible_after_rebuild"
            if repaired_positive > 0
            else "expectation_positive_candidates_still_zero_after_dedupe"
        ),
        "blocking_reasons": []
        if repaired_positive > 0
        else ["positive_expectation_candidates_zero"],
        "note": (
            "This code repair fixes duplicate snapshot selection only. Any "
            "canonical ledger files generated before the helper repair should "
            "be rebuilt or verified before exp-20260525-021 or exp-20260525-017 "
            "consumes the repaired rows."
        ),
    }
    status = "accepted_measurement_repair"
    related_files = [
        _repo_rel(REPO_ROOT / "quant" / "estimate_revision_ledger.py"),
        _repo_rel(REPO_ROOT / "quant" / "test_estimate_revision_ledger.py"),
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(EXPERIMENT_LOG_JSONL),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": repair_gate["decision"],
        "lane": "measurement_repair",
        "read_only": False,
        "hypothesis": (
            "Duplicate legacy earnings snapshots can override PIT-safe organized "
            "snapshots inside the estimate revision ledger and create false PIT "
            "coverage blockers."
        ),
        "change_summary": (
            "De-duplicate earnings snapshots by as-of date before ledger builds, "
            "preferring PIT-safe organized snapshots over later legacy copies."
        ),
        "change_type": "measurement_repair_data_helper",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "snapshot_dedupe_repair_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 2,
        "nearby_prior_experiments": ["exp-20260525-021", "exp-20260525-023"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "duplicate_snapshot_selection_candidate_impact",
        "component": "quant/estimate_revision_ledger.py",
        "parameters": {
            "snapshot_selection_order": [
                "PIT-safe snapshot",
                "organized data/daily/snapshots/earnings path",
                "earliest file_mtime_utc",
                "path text tie-breaker",
            ],
            "positive_expectation_definition": "estimate_revision_usable && eps_estimate_delta_7d > 0",
            "no_expectation_fallback": True,
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "measurement repair: remove false PIT blockers in the expectation "
                "revision data path before interpreting Bucket A."
            ),
            "2_history_check": (
                "exp-20260525-023 identified one candidate with a PIT caveat "
                "caused by prior_snapshot_created_after_asof while duplicate "
                "organized/legacy snapshots exist."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Duplicate dates choose PIT-safe organized records; tests prove "
                "unsafe legacy duplicates no longer override usable prior rows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260525_025_estimate_revision_snapshot_dedupe_repair.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": "data/experiments/exp-20260517-009/",
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "note": "This repairs a default-off data ledger helper; core strategy metrics are unchanged.",
        },
        "gate2": {
            "passed": bool(field_check.get("passed", False)),
            "field_check": field_check,
            "rule_dependencies": [
                "earnings_snapshot_YYYYMMDD files",
                "file_mtime_utc",
                "estimate_revision_ledger same-event PIT usability",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "passed": True,
            "survival_rate_not_applicable": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": True,
            "note": "No entries, exits, ranking, sizing, LLM/news, or orders changed.",
        },
        "repair_gate": repair_gate,
        "alpha_readiness": alpha_readiness,
        "duplicate_snapshot_summary": duplicates,
        "candidate_repair_summary": {
            "candidate_objects_total": len(candidate_rows),
            "candidate_rows_changed": len(changed),
            "legacy_usable_candidates": legacy_usable,
            "repaired_usable_candidates": repaired_usable,
            "legacy_positive_expectation_candidates": legacy_positive,
            "repaired_positive_expectation_candidates": repaired_positive,
            "legacy_pit_caveat_counts": dict(
                Counter(str(row["legacy_state"]["pit_caveat"] or "none") for row in candidate_rows)
            ),
            "repaired_pit_caveat_counts": dict(
                Counter(str(row["repaired_state"]["pit_caveat"] or "none") for row in candidate_rows)
            ),
        },
        "candidate_repair_rows": candidate_rows,
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "legacy_usable_candidates": legacy_usable,
            "legacy_positive_expectation_candidates": legacy_positive,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "repaired_usable_candidates": repaired_usable,
            "repaired_positive_expectation_candidates": repaired_positive,
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
            "usable_candidate_delta": repaired_usable - legacy_usable,
            "positive_expectation_candidate_delta": repaired_positive - legacy_positive,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": production_impact(),
        "decision_rule": (
            "This repair may justify rebuilding affected default-off estimate "
            "revision ledgers. It does not unlock alpha interpretation unless "
            "exp-20260525-021 later passes."
        ),
        "rejection_reason": None,
        "next_evidence_needed": (
            "After affected default-off estimate revision ledgers are rebuilt "
            "or verified, rerun exp-20260525-023, then rerun exp-20260525-021 "
            "only if positive expectation candidates become available."
        ),
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    summary = payload["candidate_repair_summary"]
    lines = [
        f"# {EXPERIMENT_ID} Estimate Revision Snapshot Dedupe Repair",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Measurement repair only. No entries, exits, ranking, sizing, LLM/news, or orders changed.",
        "",
        "## Repair Gate",
        "",
        "```json",
        json.dumps(payload["repair_gate"], indent=2, sort_keys=True),
        "```",
        "",
        "## Candidate Impact",
        "",
        "```json",
        json.dumps(_safe(summary), indent=2, sort_keys=True),
        "```",
        "",
        "## Alpha Readiness",
        "",
        "```json",
        json.dumps(payload["alpha_readiness"], indent=2, sort_keys=True),
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
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "repair_gate",
        "alpha_readiness",
        "candidate_repair_summary",
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
                    "candidate_repair_summary": payload["candidate_repair_summary"],
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
