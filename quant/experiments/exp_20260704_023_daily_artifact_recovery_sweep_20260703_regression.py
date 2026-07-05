"""exp-20260704-023: daily artifact orphan-recovery coverage regression.

Measurement repair only. The 2026-07-03 daily run left several valid atomic
temps with missing final artifacts. The prior orphan-recovery sweep covered
signals/orders/snapshots, but not every directory in data_paths.DAILY_ARTIFACTS,
so news-derived daily artifacts could remain invisible to replay and attribution.

This runner verifies the expanded shared sweep, restores valid 2026-07-03 daily
artifacts, reruns only the estimate-revision attribution ledger, and records the
candidate-match delta. It does not change entries, exits, ranking, sizing, or
orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260704-023"
OWNER = "alpha-explore"
LANE = "measurement_repair"
AS_OF = "2026-07-03"
TAG = "20260703"
SLUG = "daily_artifact_recovery_sweep_20260703_regression"
RUNNER = f"quant/experiments/exp_20260704_023_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import stale_artifact_sweep as sweep  # noqa: E402
from data_paths import DAILY_ARTIFACTS, daily_artifact_path  # noqa: E402
from estimate_revision_ledger import (  # noqa: E402
    load_daily_signal_match_records,
    persist_estimate_revision_ledger,
)
from experiment_registry import persist_self_registered_result  # noqa: E402


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DATA_DIR = REPO_ROOT / "data"
LEDGER_PATH = DATA_DIR / "non_ohlcv" / f"estimate_revision_ledger_{TAG}.jsonl"
SUMMARY_PATH = DATA_DIR / "non_ohlcv" / f"estimate_revision_ledger_summary_{TAG}.json"
QUANT_FINAL = daily_artifact_path("quant_signals", TAG, DATA_DIR)
ORDERS_FINAL = daily_artifact_path("bracket_orders", TAG, DATA_DIR)

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_023_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: estimate-revision overlap with same-day production-visible "
    "candidate rows may have forward replacement value, but 2026-07-03 daily "
    "artifacts were stranded as valid atomic temp files with missing finals. "
    "Expand and run the shared recoverable daily-artifact sweep, then rerun only "
    "the attribution ledger so candidate matching is replayable without changing "
    "strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Estimate-revision direction may have replacement value when it overlaps "
    "same-day production-visible candidate rows; the current blocker is artifact "
    "finalization, not a trading rule."
)
CHANGED_VARIABLE = "daily_artifact_recovery_sweep_20260703_regression_v1"
MECHANISM_FAMILY = "daily_artifact_recovery_measurement_repair"
TRIAL_FAMILY = "daily_artifact_orphan_recovery_coverage"
TRIAL_VARIANT_ID = "daily_artifact_recovery_sweep_20260703_regression_v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
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


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ticket() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return ticket if isinstance(ticket, dict) else {}


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def signal_match_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "candidate_record_count": sum(1 for row in records if row.get("is_candidate_record")),
        "selected_signal_count": sum(1 for row in records if row.get("is_selected_signal")),
        "feature_row_count": sum(row.get("record_type") == "feature_row" for row in records),
        "sources": sorted({str(row.get("source")) for row in records if row.get("source")}),
        "record_types": dict(
            sorted(
                Counter(
                    str(row.get("record_type")) for row in records if row.get("record_type")
                ).items()
            )
        ),
        "candidate_tickers": sorted(
            {
                str(row.get("ticker")).upper()
                for row in records
                if row.get("is_candidate_record") and row.get("ticker")
            }
        ),
    }


def ledger_match_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_rows = [row for row in rows if row.get("matched_candidate_today")]
    usable_candidate_rows = [row for row in candidate_rows if row.get("estimate_revision_usable")]
    gap_reasons = Counter(
        str(row.get("candidate_match_gap_reason"))
        for row in rows
        if row.get("candidate_match_gap_reason")
    )
    return {
        "row_count": len(rows),
        "matched_feature_rows": sum(bool(row.get("matched_feature_row_today")) for row in rows),
        "matched_candidate_rows": len(candidate_rows),
        "estimate_revision_usable_and_matched_candidate_rows": len(usable_candidate_rows),
        "matched_selected_signal_rows": sum(
            bool(row.get("matched_selected_signal_today")) for row in rows
        ),
        "up_revision_usable_matched_candidate_rows": sum(
            row.get("revision_direction_prev") == "up" for row in usable_candidate_rows
        ),
        "down_revision_usable_matched_candidate_rows": sum(
            row.get("revision_direction_prev") == "down" for row in usable_candidate_rows
        ),
        "candidate_gap_reasons": dict(sorted(gap_reasons.items())),
        "matched_candidate_tickers": sorted(
            {str(row.get("ticker")) for row in candidate_rows if row.get("ticker")}
        ),
        "matched_candidate_sample": [
            {
                "ticker": row.get("ticker"),
                "revision_direction_prev": row.get("revision_direction_prev"),
                "estimate_revision_usable": row.get("estimate_revision_usable"),
                "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
                "matched_signal_sources": row.get("matched_signal_sources"),
                "matched_signal_record_types": row.get("matched_signal_record_types"),
                "matched_signal_strategies": row.get("matched_signal_strategies"),
            }
            for row in candidate_rows[:12]
        ],
    }


def scan_recoverable_orphans() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rel in sweep._RECOVERABLE_DIRS:
        directory = REPO_ROOT / rel
        if not directory.is_dir():
            continue
        for entry in os.scandir(directory):
            if not (entry.is_file() and entry.name.endswith(".tmp")):
                continue
            temp_path = Path(entry.path)
            final_name = sweep._final_name_for_temp(entry.name)
            if not final_name:
                continue
            final_path = directory / final_name
            try:
                age_s = round(datetime.now(timezone.utc).timestamp() - temp_path.stat().st_mtime)
            except OSError:
                age_s = None
            valid = False
            if not final_path.exists():
                valid = bool(sweep._temp_payload_is_valid(temp_path, final_name))
            rows.append(
                {
                    "directory": repo_rel(directory),
                    "temp_path": repo_rel(temp_path),
                    "final_path": repo_rel(final_path),
                    "final_name": final_name,
                    "final_exists": final_path.exists(),
                    "valid_if_missing_final": valid,
                    "target_date": TAG in final_name,
                    "age_s": age_s,
                    "size_bytes": temp_path.stat().st_size if temp_path.exists() else None,
                }
            )
    target_rows = [row for row in rows if row["target_date"]]
    return {
        "recoverable_dir_count": len(sweep._RECOVERABLE_DIRS),
        "recoverable_dirs": list(sweep._RECOVERABLE_DIRS),
        "temp_count": len(rows),
        "target_date_temp_count": len(target_rows),
        "target_date_missing_final_valid_count": sum(
            row["target_date"] and not row["final_exists"] and row["valid_if_missing_final"]
            for row in rows
        ),
        "target_date_missing_final_valid_paths": [
            row["final_path"]
            for row in rows
            if row["target_date"] and not row["final_exists"] and row["valid_if_missing_final"]
        ],
        "rows": rows,
    }


def daily_artifact_status() -> dict[str, Any]:
    status: dict[str, Any] = {}
    for key in sorted(DAILY_ARTIFACTS):
        path = daily_artifact_path(key, TAG, DATA_DIR)
        parent = path.parent
        tmp_pattern = f".{path.name}.*.tmp"
        temps = sorted(parent.glob(tmp_pattern)) if parent.exists() else []
        status[key] = {
            "path": repo_rel(path),
            "exists": path.exists(),
            "sha256": sha256(path),
            "temp_count": len(temps),
            "temps": [repo_rel(temp) for temp in temps[:10]],
        }
    return status


def run_recovery_sweep() -> dict[str, Any]:
    totals = {"recovered": [], "cleaned": [], "skipped": [], "by_directory": {}}
    for rel in sweep._RECOVERABLE_DIRS:
        result = sweep.recover_orphan_atomic_writes(REPO_ROOT / rel)
        totals["by_directory"][rel] = result
        for key in ("recovered", "cleaned", "skipped"):
            totals[key].extend(result.get(key, []))
    return totals


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    baseline = baseline_metrics()

    before_orphans = scan_recoverable_orphans()
    before_artifacts = daily_artifact_status()
    before_summary = read_json(SUMMARY_PATH, {})
    before_rows = read_jsonl(LEDGER_PATH)
    before_match_records = load_daily_signal_match_records(DATA_DIR, AS_OF)

    recovery = run_recovery_sweep()

    after_artifacts_pre_ledger = daily_artifact_status()
    after_summary = persist_estimate_revision_ledger(
        as_of=AS_OF,
        data_dir=DATA_DIR,
        output_dir=DATA_DIR / "non_ohlcv",
        generated_at=datetime.now(timezone.utc),
        run_adapter_changed=False,
        signal_data_dir=DATA_DIR,
        match_daily_signals=True,
    )
    after_rows = read_jsonl(LEDGER_PATH)
    after_match_records = load_daily_signal_match_records(DATA_DIR, AS_OF)
    after_orphans = scan_recoverable_orphans()
    after_artifacts = daily_artifact_status()

    before_ledger_match = ledger_match_summary(before_rows)
    after_ledger_match = ledger_match_summary(after_rows)
    before_signal_match = signal_match_summary(before_match_records)
    after_signal_match = signal_match_summary(after_match_records)

    target_recovered = [
        repo_rel(path)
        for path in recovery["recovered"]
        if TAG in Path(path).name
    ]
    all_recovered = [repo_rel(path) for path in recovery["recovered"]]
    target_cleaned = [
        repo_rel(path)
        for path in recovery["cleaned"]
        if TAG in Path(path).name
    ]

    blockers: list[str] = []
    alpha_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        blockers.append("baseline_missing_or_nonstandard")
    if before_orphans["target_date_missing_final_valid_count"] <= 0:
        blockers.append("no_valid_target_date_orphan_temp_before_recovery")
    if after_orphans["target_date_missing_final_valid_count"] != 0:
        blockers.append("target_date_valid_orphan_temps_still_missing_finals")
    if not QUANT_FINAL.exists():
        blockers.append("quant_signals_final_missing_after_recovery")
    if not ORDERS_FINAL.exists():
        blockers.append("bracket_orders_final_missing_after_recovery")
    if after_signal_match["record_count"] <= before_signal_match["record_count"]:
        blockers.append("daily_signal_match_records_not_increased_after_recovery")
    if int(after_summary.get("daily_signal_match_record_count") or 0) <= int(
        before_summary.get("daily_signal_match_record_count") or 0
    ):
        blockers.append("ledger_summary_signal_match_count_not_increased")
    if after_ledger_match["matched_candidate_rows"] <= 0:
        alpha_blockers.append("no_matched_candidate_rows_after_recovery")
    if after_ledger_match["estimate_revision_usable_and_matched_candidate_rows"] <= 0:
        alpha_blockers.append("no_usable_matched_candidate_rows_after_recovery")

    measurement_passed = not blockers
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        "accepted_measurement_repair_daily_artifact_recovery_sweep_20260703"
        if measurement_passed
        else "blocked_daily_artifact_recovery_sweep_20260703"
    )
    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "target_date_recovered_final_count": len(target_recovered),
        "target_date_cleaned_temp_count": len(target_cleaned),
        "before_valid_orphan_count": before_orphans["target_date_missing_final_valid_count"],
        "after_valid_orphan_count": after_orphans["target_date_missing_final_valid_count"],
        "before_signal_match_record_count": before_signal_match["record_count"],
        "after_signal_match_record_count": after_signal_match["record_count"],
        "signal_match_record_count_delta": after_signal_match["record_count"]
        - before_signal_match["record_count"],
        "before_candidate_record_count": before_signal_match["candidate_record_count"],
        "after_candidate_record_count": after_signal_match["candidate_record_count"],
        "candidate_record_count_delta": after_signal_match["candidate_record_count"]
        - before_signal_match["candidate_record_count"],
        "before_daily_signal_match_record_count": int(
            before_summary.get("daily_signal_match_record_count") or 0
        ),
        "after_daily_signal_match_record_count": int(
            after_summary.get("daily_signal_match_record_count") or 0
        ),
        "ledger_daily_signal_match_record_count_delta": int(
            after_summary.get("daily_signal_match_record_count") or 0
        )
        - int(before_summary.get("daily_signal_match_record_count") or 0),
        "before_matched_candidate_rows": before_ledger_match["matched_candidate_rows"],
        "after_matched_candidate_rows": after_ledger_match["matched_candidate_rows"],
        "matched_candidate_rows_delta": after_ledger_match["matched_candidate_rows"]
        - before_ledger_match["matched_candidate_rows"],
        "after_usable_matched_candidate_rows": after_ledger_match[
            "estimate_revision_usable_and_matched_candidate_rows"
        ],
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "measurement_repair_daily_artifact_recovery_only",
    }
    changed_files = [
        RUNNER,
        "quant/stale_artifact_sweep.py",
        "quant/test_atomic_write_recovery.py",
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
        repo_rel(LEDGER_PATH),
        repo_rel(SUMMARY_PATH),
        *all_recovered,
    ]
    changed_files = list(dict.fromkeys(changed_files))

    probability = 0.82
    calibration = {
        "predicted_success_probability": probability,
        "actual_success": 1 if measurement_passed else 0,
        "brier_score": round((probability - (1.0 if measurement_passed else 0.0)) ** 2, 6),
        "predicted_failure_modes": [
            "temp_file_invalid",
            "sweep_coverage_still_incomplete",
            "ledger_schema_drift",
            "no_candidate_matches_after_recovery",
        ],
        "realized_failure_modes": blockers + alpha_blockers,
        "predicted_failure_modes_hit": [
            mode
            for mode in [
                "temp_file_invalid",
                "sweep_coverage_still_incomplete",
                "ledger_schema_drift",
                "no_candidate_matches_after_recovery",
            ]
            if (
                mode in blockers
                or mode in alpha_blockers
                or (
                    mode == "sweep_coverage_still_incomplete"
                    and "target_date_valid_orphan_temps_still_missing_finals" in blockers
                )
                or (
                    mode == "no_candidate_matches_after_recovery"
                    and "no_matched_candidate_rows_after_recovery" in alpha_blockers
                )
            )
        ],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": measurement_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": measurement_passed,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_daily_artifact_recovery_coverage_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "recoverable_dir_coverage_matches_daily_artifacts",
            "valid_jsonl_temp_validation",
            "20260703_daily_artifact_recovery",
            "estimate_revision_ledger_rerun",
            "no_strategy_behavior_change",
        ],
        "nearby_prior_experiments": [
            "exp-20260628-017",
            "exp-20260702-005",
            "exp-20260703-010",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "fresh_20260703_orphan_atomic_write_artifacts",
        "prediction": {
            "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
            "success_probability": probability,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": calibration["predicted_failure_modes"],
            "confidence_reason": (
                "The 2026-07-03 orphan temps parse as valid daily artifacts and "
                "the repair changes only recovery coverage plus attribution ledger "
                "materialization."
            ),
        },
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260628-017": (
                    "Accepted shared atomic-write retry and recover-before-delete "
                    "daily sweep, but its recoverable dir list covered only a subset "
                    "of daily artifacts."
                ),
                "exp-20260702-005": (
                    "Accepted per-date quant signal recovery; near-neighbor retries "
                    "as estimate-revision recovery are forbidden without new evidence."
                ),
                "exp-20260703-010": (
                    "Accepted run.py post-quant refresh; future work should not open "
                    "more per-date estimate-revision artifact recoveries."
                ),
                "novelty_gate": ticket.get("novelty"),
                "why_allowed": (
                    "This is a true fresh orphan-temp fault recovery and shared sweep "
                    "coverage regression, not a revision threshold/slice retry."
                ),
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only as measurement repair if valid 2026-07-03 recoverable "
                "temps with missing finals are promoted, none remain in covered daily "
                "artifact dirs, same-day signal match records increase, and strategy "
                "deltas remain zero."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "as_of_date": AS_OF,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "quant_final": repo_rel(QUANT_FINAL),
            "orders_final": repo_rel(ORDERS_FINAL),
            "ledger_path": repo_rel(LEDGER_PATH),
            "summary_path": repo_rel(SUMMARY_PATH),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": measurement_passed,
            "dependencies_validated": measurement_passed,
            "fields_checked": [
                "daily_artifact_path",
                "atomic_temp_final_name",
                "json_payload_validity",
                "jsonl_payload_validity",
                "ticker",
                "matched_signal_sources",
                "matched_candidate_today",
                "revision_direction_prev",
                "estimate_revision_usable",
            ],
            "entry_date_scope": "No executable entry is scheduled; rows are attribution inputs.",
            "target_price_scope": "No target exit is scheduled; target_price is not consumed.",
        },
        "gate3": {
            "passed": measurement_passed,
            "filter_added": False,
            "signals_generated": int(after_summary.get("row_count") or 0),
            "signals_survived": after_ledger_match["matched_candidate_rows"],
            "survival_rate": round(
                after_ledger_match["matched_candidate_rows"]
                / int(after_summary.get("row_count") or 1),
                6,
            )
            if int(after_summary.get("row_count") or 0)
            else None,
            "note": "Measurement rows only; no executable filter, entry, rank, size, exit, or order rule was added.",
        },
        "gate4": {
            "passed": measurement_passed,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": blockers,
            "alpha_blockers": alpha_blockers
            + [
                "closed_forward_replacement_values_absent_for_20260703_revision_rows",
                "revision_alpha_requires_separate_outcome_experiment",
            ],
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "before": {
            "daily_artifacts": before_artifacts,
            "orphans": before_orphans,
            "summary_path": repo_rel(SUMMARY_PATH),
            "ledger_path": repo_rel(LEDGER_PATH),
            "summary": before_summary,
            "ledger_match_summary": before_ledger_match,
            "signal_match_records_loaded_now": before_signal_match,
            "ledger_sha256": sha256(LEDGER_PATH),
            "summary_sha256": sha256(SUMMARY_PATH),
        },
        "after": {
            "daily_artifacts_pre_ledger": after_artifacts_pre_ledger,
            "daily_artifacts": after_artifacts,
            "orphans": after_orphans,
            "summary_path": repo_rel(SUMMARY_PATH),
            "ledger_path": repo_rel(LEDGER_PATH),
            "summary": after_summary,
            "ledger_match_summary": after_ledger_match,
            "signal_match_records_loaded_now": after_signal_match,
            "ledger_sha256": sha256(LEDGER_PATH),
            "summary_sha256": sha256(SUMMARY_PATH),
        },
        "recovery_audit": {
            "target_date_recovered_finals": target_recovered,
            "target_date_cleaned_temps": target_cleaned,
            "summary": recovery,
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The shared recovery sweep had been correct for covered directories "
                "but stale relative to DAILY_ARTIFACTS. Updating the coverage made "
                "2026-07-03 replayable and restored same-day candidate matching."
                if measurement_passed
                else "The expanded daily-artifact recovery path did not satisfy the fixed measurement contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not open another per-date estimate-revision artifact recovery or "
                "07-03 revision slice after these finals exist. Next revision alpha "
                "work needs closed replacement values or a genuinely different PIT "
                "expectation source."
            ),
            "new_evidence_required": (
                "Closed cash/SPY/QQQ replacement-value outcomes for matched 2026-07-03 "
                "rows, materially more non-flat matched rows, or a different unsaturated "
                "PIT expectation source."
            ),
        },
        "next_retry_requires": [
            "closed replacement-value outcomes for matched 2026-07-03 revision rows",
            "materially more selected/current non-flat estimate-revision matches",
            "no more 2026-07-03 artifact recovery once finals exist",
        ],
        "changed_files": changed_files,
        "related_files": [
            "quant/stale_artifact_sweep.py",
            "quant/test_atomic_write_recovery.py",
            "quant/estimate_revision_ledger.py",
            "quant/run.py",
            "experiments/logs/exp-20260628-017.json",
            "experiments/logs/exp-20260702-005.json",
            "experiments/logs/exp-20260703-010.json",
        ],
        "allowed_write_scope": changed_files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\stale_artifact_sweep.py quant\\test_atomic_write_recovery.py "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_atomic_write_recovery.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": measurement_passed,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keep = dict(payload)
    keep["before"] = {
        **payload["before"],
        "daily_artifacts": "<see artifact>",
        "orphans": {
            **payload["before"]["orphans"],
            "rows": payload["before"]["orphans"]["rows"][:20],
        },
    }
    keep["after"] = {
        **payload["after"],
        "daily_artifacts": "<see artifact>",
        "daily_artifacts_pre_ledger": "<see artifact>",
        "orphans": {
            **payload["after"]["orphans"],
            "rows": payload["after"]["orphans"]["rows"][:20],
        },
    }
    keep["recovery_audit"] = {
        **payload["recovery_audit"],
        "summary": {
            "recovered": payload["recovery_audit"]["summary"]["recovered"][:25],
            "cleaned": payload["recovery_audit"]["summary"]["cleaned"][:25],
            "skipped": payload["recovery_audit"]["summary"]["skipped"][:25],
            "by_directory": "<see artifact>",
        },
    }
    return keep


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: daily artifact recovery sweep 2026-07-03",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Valid 07-03 orphans before/after: `{delta['before_valid_orphan_count']} -> {delta['after_valid_orphan_count']}`",
            f"- Recovered 07-03 finals: `{delta['target_date_recovered_final_count']}`",
            f"- Signal match records before/after: `{delta['before_signal_match_record_count']} -> {delta['after_signal_match_record_count']}`",
            f"- Candidate records before/after: `{delta['before_candidate_record_count']} -> {delta['after_candidate_record_count']}`",
            f"- Matched candidate rows before/after: `{delta['before_matched_candidate_rows']} -> {delta['after_matched_candidate_rows']}`",
            "- Strategy behavior changed: `false`",
            "- Accepted alpha: `false`",
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
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_atomic_write_recovery.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "stale_artifact_sweep.py",
        REPO_ROOT / "quant" / "test_atomic_write_recovery.py",
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        LEDGER_PATH,
        SUMMARY_PATH,
        QUANT_FINAL,
        ORDERS_FINAL,
        BASELINE_RESULT,
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
        "changed_files": payload["changed_files"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log_record(payload))
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
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
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
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
                "delta_metrics": payload["delta_metrics"],
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
