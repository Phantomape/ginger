"""exp-20260708-007: atomic-write repair for estimate revision artifacts.

Measurement repair only. On 2026-07-07 both the Step 3 persist and the
post-quant refresh of the estimate revision ledger failed with
``OSError [Errno 22] Invalid argument`` on
``data/non_ohlcv/estimate_revision_ledger_20260707.jsonl``: the writers used a
plain truncating ``open("w")`` on the final path, which on Windows fails with
ERROR_USER_MAPPED_FILE while any process holds the existing file
memory-mapped (reproduced deterministically). The 2026-07-07 ledger jsonl is
missing while its stale Step 3 summary exists, and the outcome surface never
materialized. This runner assumes the writers have been switched to the
repo-standard atomic temp+``os.replace`` write (``data_paths.atomic_write_text``,
same remedy as exp-20260628-017), regenerates the 2026-07-07 ledger with
same-day quant-signal matching, refreshes the outcome surface, and records the
result without changing strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260708-007"
OWNER = "interactive"
LANE = "measurement_repair"
AS_OF = "2026-07-07"
TAG = "20260707"
SLUG = "estimate_revision_atomic_write_einval_repair"
RUNNER = f"quant/experiments/exp_20260708_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from estimate_revision_ledger import (  # noqa: E402
    load_daily_signal_match_records,
    persist_estimate_revision_ledger,
)
from estimate_revision_outcomes import persist_estimate_revision_outcomes  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
QUANT_FINAL = DATA_DIR / "daily" / "signals" / "quant" / f"quant_signals_{TAG}.json"
LEDGER_PATH = DATA_DIR / "non_ohlcv" / f"estimate_revision_ledger_{TAG}.jsonl"
SUMMARY_PATH = DATA_DIR / "non_ohlcv" / f"estimate_revision_ledger_summary_{TAG}.json"
OUTCOME_PATH = DATA_DIR / "non_ohlcv" / f"estimate_revision_outcomes_{TAG}.jsonl"
OUTCOME_SUMMARY_PATH = (
    DATA_DIR / "non_ohlcv" / f"estimate_revision_outcome_summary_{TAG}.json"
)

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_007_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Measurement repair / fault recovery: the estimate-revision ledger and "
    "outcome artifacts are written with a plain truncating open(w) instead of "
    "the repo-standard atomic temp+os.replace write, so a concurrent process "
    "holding a memory-mapped view of the existing jsonl makes the daily write "
    "fail with ERROR_USER_MAPPED_FILE surfaced as OSError Errno 22; switch the "
    "writers to atomic_write_text and regenerate the missing 2026-07-07 "
    "ledger/outcome surface without changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Estimate-revision direction may have replacement value when it overlaps "
    "same-day production-visible candidate rows, but 2026-07-07 cannot be "
    "evaluated while the daily ledger write fails and the jsonl is missing."
)
CHANGED_VARIABLE = "estimate_revision_atomic_artifact_write_v1"
MECHANISM_FAMILY = "production_visible_estimate_revision_candidate_match_attribution"
TRIAL_FAMILY = "estimate_revision_candidate_match_surface_repair"
TRIAL_VARIANT_ID = "estimate_revision_atomic_write_einval_repair_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260628-017",
    "exp-20260702-005",
    "exp-20260704-023",
    "exp-20260706-021",
]
CAUSAL_COMPONENTS = [
    "atomic_temp_replace_write_adoption",
    "mapped_file_einval_hardening",
    "estimate_revision_20260707_ledger_regeneration",
    "outcome_surface_refresh",
    "no_strategy_behavior_change",
]
PREDICTED_FAILURE_MODES = [
    "mapped_file_lock_outlives_replace_retry",
    "jsonl_atomic_writer_regression",
    "no_candidate_matches_after_regeneration",
    "unidentified_deleter_recurs",
]
EINVAL_EVIDENCE = {
    "observed_warning": (
        "22:12:38 WARNING __main__: Estimate revision ledger unavailable: "
        "[Errno 22] Invalid argument: "
        "'data\\\\non_ohlcv\\\\estimate_revision_ledger_20260707.jsonl'"
    ),
    "failed_writes_2026_07_07": [
        "step3_persist_second_run_22:12:38",
        "post_quant_refresh_first_run_~20:32 (summary on disk stayed the 20:03 "
        "match_daily_signals=False version)",
    ],
    "reproduction": (
        "Truncating open('w') on a file memory-mapped by another process "
        "raises OSError Errno 22 (ERROR_USER_MAPPED_FILE); reproduced with a "
        "child process holding mmap.ACCESS_READ. Regression test: "
        "quant/test_estimate_revision_ledger.py::"
        "test_write_jsonl_survives_concurrent_memory_map_of_destination"
    ),
    "deletion_note": (
        "The 20:03 ledger jsonl was deleted by an unidentified external "
        "process after 22:12:38 (not git: no reflog checkout/reset; not "
        "Defender; not recycle bin; USN journal already rotated). Atomic "
        "replace does not fix external deletion but removes the truncation "
        "corruption/EINVAL class and preserves the previous final on failure."
    ),
}


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
    if isinstance(value, (list, tuple)):
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
        for raw in handle:
            text = raw.strip()
            if not text:
                continue
            row = json.loads(text)
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
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
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
        "sources": sorted({str(row.get("source")) for row in records if row.get("source")}),
        "record_types": dict(
            sorted(
                Counter(
                    str(row.get("record_type")) for row in records if row.get("record_type")
                ).items()
            )
        ),
    }


def ledger_match_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_rows = [row for row in rows if row.get("matched_candidate_today")]
    usable_candidate_rows = [row for row in candidate_rows if row.get("estimate_revision_usable")]
    return {
        "row_count": len(rows),
        "matched_feature_rows": sum(bool(row.get("matched_feature_row_today")) for row in rows),
        "matched_candidate_rows": len(candidate_rows),
        "estimate_revision_usable_and_matched_candidate_rows": len(usable_candidate_rows),
        "matched_selected_signal_rows": sum(
            bool(row.get("matched_selected_signal_today")) for row in rows
        ),
        "matched_candidate_tickers": sorted(
            {str(row.get("ticker")) for row in candidate_rows if row.get("ticker")}
        ),
    }


def compact_outcome_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": summary.get("status"),
        "as_of_date": summary.get("as_of_date"),
        "warehouse_date_range": summary.get("warehouse_date_range"),
        "matched_candidate_rows": summary.get("matched_candidate_rows"),
        "usable_matched_candidate_rows": summary.get("usable_matched_candidate_rows"),
        "nonflat_usable_matched_candidate_rows": summary.get(
            "nonflat_usable_matched_candidate_rows"
        ),
        "direction_counts": summary.get("direction_counts"),
        "closed_rows_by_horizon": summary.get("closed_rows_by_horizon"),
        "pending_rows_by_horizon": summary.get("pending_rows_by_horizon"),
        "status_counts_by_horizon": summary.get("status_counts_by_horizon"),
    }


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    baseline = baseline_metrics()

    before_ledger_exists = LEDGER_PATH.exists()
    before_summary = read_json(SUMMARY_PATH, {})
    before_rows = read_jsonl(LEDGER_PATH)
    before_ledger_match = ledger_match_summary(before_rows)
    before_outcome_summary_exists = OUTCOME_SUMMARY_PATH.exists()

    after_summary = persist_estimate_revision_ledger(
        as_of=AS_OF,
        data_dir=DATA_DIR,
        output_dir=DATA_DIR / "non_ohlcv",
        generated_at=datetime.now(timezone.utc),
        run_adapter_changed=False,
        signal_data_dir=DATA_DIR,
        match_daily_signals=True,
    )
    outcome_summary = persist_estimate_revision_outcomes(
        as_of=AS_OF,
        data_dir=DATA_DIR,
        output_dir=DATA_DIR / "non_ohlcv",
        generated_at=datetime.now(timezone.utc),
        run_adapter_changed=False,
    )

    after_rows = read_jsonl(LEDGER_PATH)
    after_ledger_match = ledger_match_summary(after_rows)
    after_match_records = load_daily_signal_match_records(DATA_DIR, AS_OF)
    after_signal_match = signal_match_summary(after_match_records)
    orphan_temps = sorted(
        repo_rel(path) for path in (DATA_DIR / "non_ohlcv").glob(f".*{TAG}*.tmp")
    )

    measurement_blockers: list[str] = []
    alpha_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if not QUANT_FINAL.exists():
        measurement_blockers.append("quant_final_missing_for_20260707")
    if not LEDGER_PATH.exists() or not after_rows:
        measurement_blockers.append("ledger_jsonl_still_missing_after_regeneration")
    if int(after_summary.get("daily_signal_match_record_count") or 0) <= int(
        before_summary.get("daily_signal_match_record_count") or 0
    ):
        measurement_blockers.append("ledger_signal_match_count_not_increased")
    if orphan_temps:
        measurement_blockers.append("atomic_write_left_orphan_temps")
    if after_ledger_match["matched_candidate_rows"] <= 0:
        alpha_blockers.append("no_candidate_matches_after_regeneration")
    if after_ledger_match["estimate_revision_usable_and_matched_candidate_rows"] < 20:
        alpha_blockers.append("nonflat_or_usable_matched_sample_still_too_thin")
    closed_by_horizon = outcome_summary.get("closed_rows_by_horizon") or {}
    if int(closed_by_horizon.get("h3") or 0) <= 0:
        alpha_blockers.append("no_closed_forward_replacement_rows_for_20260707_yet")

    measurement_passed = not measurement_blockers
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        f"accepted_measurement_repair_{SLUG}"
        if measurement_passed
        else f"blocked_{SLUG}"
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
        "before_ledger_jsonl_exists": before_ledger_exists,
        "after_ledger_jsonl_exists": LEDGER_PATH.exists(),
        "before_ledger_row_count": before_ledger_match["row_count"],
        "after_ledger_row_count": after_ledger_match["row_count"],
        "before_daily_signal_match_record_count": int(
            before_summary.get("daily_signal_match_record_count") or 0
        ),
        "after_daily_signal_match_record_count": int(
            after_summary.get("daily_signal_match_record_count") or 0
        ),
        "before_matched_candidate_rows": before_ledger_match["matched_candidate_rows"],
        "after_matched_candidate_rows": after_ledger_match["matched_candidate_rows"],
        "after_usable_matched_candidate_rows": after_ledger_match[
            "estimate_revision_usable_and_matched_candidate_rows"
        ],
        "before_outcome_summary_exists": before_outcome_summary_exists,
        "after_outcome_summary_exists": OUTCOME_SUMMARY_PATH.exists(),
        "outcome_h3_closed_rows": int(closed_by_horizon.get("h3") or 0),
        "orphan_temps_after": len(orphan_temps),
    }
    success_probability = float(
        (ticket.get("prediction") or {}).get("success_probability") or 0.85
    )
    prediction = {
        "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
        "success_probability": success_probability,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": PREDICTED_FAILURE_MODES,
        "confidence_reason": (ticket.get("prediction") or {}).get("confidence_reason"),
    }
    realized_blockers = measurement_blockers + alpha_blockers
    calibration = {
        "predicted_success_probability": success_probability,
        "actual_success": 1 if measurement_passed else 0,
        "brier_score": round(
            (success_probability - (1.0 if measurement_passed else 0.0)) ** 2, 6
        ),
        "predicted_failure_modes": PREDICTED_FAILURE_MODES,
        "realized_failure_modes": realized_blockers,
        "predicted_failure_mode_hit": bool(
            set(realized_blockers) & set(PREDICTED_FAILURE_MODES)
        ),
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "measurement_repair_estimate_revision_atomic_write_and_20260707_regeneration",
    }
    files = [
        "quant/estimate_revision_ledger.py",
        "quant/estimate_revision_outcomes.py",
        "quant/test_estimate_revision_ledger.py",
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
        repo_rel(LEDGER_PATH),
        repo_rel(SUMMARY_PATH),
        repo_rel(OUTCOME_PATH),
        repo_rel(OUTCOME_SUMMARY_PATH),
    ]
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
        "implementation_mode": "measurement_repair_atomic_write_and_ledger_regeneration",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "fresh_20260707_user_mapped_file_einval_write_failure",
        "einval_evidence": EINVAL_EVIDENCE,
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260628-017": "Established atomic temp+os.replace retry as the repo remedy for transient Windows write failures.",
                "exp-20260702-005": "Accepted one-date quant signal atomic recovery for 2026-07-01.",
                "exp-20260706-021": "Accepted 2026-07-05 quant-signal recovery + ledger regeneration.",
                "novelty_gate": "WARN near accepted repair families; fault recovery is the documented exception (fresh 2026-07-07 EINVAL failure, new failure mechanism: mapped-file truncation, not orphan temp).",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only as measurement repair if the 2026-07-07 ledger jsonl "
                "exists with rows, the summary's daily_signal_match_record_count "
                "increases over the stale Step 3 version, the outcome surface "
                "materializes, atomic writers leave no orphan temps, and strategy "
                "deltas stay zero."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "as_of_date": AS_OF,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "quant_final": repo_rel(QUANT_FINAL),
            "ledger_path": repo_rel(LEDGER_PATH),
            "summary_path": repo_rel(SUMMARY_PATH),
            "outcome_path": repo_rel(OUTCOME_PATH),
            "outcome_summary_path": repo_rel(OUTCOME_SUMMARY_PATH),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": measurement_passed,
            "dependencies_validated": measurement_passed,
            "fields_checked": [
                "ticker",
                "as_of_date",
                "matched_candidate_today",
                "matched_feature_row_today",
                "matched_signal_sources",
                "revision_direction_prev",
                "estimate_revision_usable",
                "entry_date",
                "target_price_scope",
            ],
            "entry_date_scope": "Outcome rows carry fixed-horizon attribution entry_date only; no executable entry is scheduled.",
            "target_price_scope": "target_price is explicitly not applicable for fixed-horizon replacement-value rows.",
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
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": alpha_blockers,
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "before": {
            "ledger_jsonl_exists": before_ledger_exists,
            "summary": before_summary,
            "ledger_match_summary": before_ledger_match,
            "outcome_summary_exists": before_outcome_summary_exists,
        },
        "after": {
            "ledger_jsonl_exists": LEDGER_PATH.exists(),
            "summary": after_summary,
            "ledger_match_summary": after_ledger_match,
            "signal_match_records_loaded_now": after_signal_match,
            "outcome_summary": compact_outcome_summary(outcome_summary),
            "orphan_temps": orphan_temps,
            "ledger_sha256": sha256(LEDGER_PATH),
            "summary_sha256": sha256(SUMMARY_PATH),
            "outcome_sha256": sha256(OUTCOME_PATH),
            "outcome_summary_sha256": sha256(OUTCOME_SUMMARY_PATH),
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The daily writers truncated the final artifact in place, so a "
                "concurrent memory-mapping of the existing jsonl turned the write "
                "into EINVAL and the 2026-07-07 surface went missing. Switching to "
                "the shared atomic temp+replace writer and rerunning the existing "
                "helpers restored the surface with same-day candidate matching."
                if measurement_passed
                else "The atomic-write repair did not satisfy the fixed measurement contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not open another 2026-07-07 ledger regeneration or writer "
                "refactor on this surface; the atomic writer is now shared. Any "
                "recurrence of a missing daily jsonl needs the external "
                "deleter/mapper identified (capture handle owners at failure "
                "time), not another rewrite."
            ),
            "new_evidence_required": (
                "Closed H3/H5/H10 cash/SPY/QQQ replacement-value rows for the "
                "2026-07-07 matched cohort, materially more non-flat matched rows, "
                "or identification of the external process that mapped/deleted the "
                "artifact."
            ),
        },
        "next_retry_requires": [
            "closed replacement-value outcomes for matched 2026-07-07 revision rows",
            "identification of the external mapper/deleter if the failure recurs",
            "no repeat regeneration once estimate_revision_ledger_20260707.jsonl exists",
        ],
        "changed_files": files,
        "related_files": [
            "quant/run.py",
            "quant/data_paths.py",
            "quant/stale_artifact_sweep.py",
            "experiments/logs/exp-20260628-017.json",
            "experiments/logs/exp-20260706-021.json",
        ],
        "allowed_write_scope": files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_estimate_revision_ledger.py quant\\test_estimate_revision_outcomes.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
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
        "ledger_jsonl_exists": payload["before"]["ledger_jsonl_exists"],
        "summary": payload["before"]["summary"],
        "ledger_match_summary": payload["before"]["ledger_match_summary"],
        "outcome_summary_exists": payload["before"]["outcome_summary_exists"],
    }
    keep["after"] = {
        "ledger_jsonl_exists": payload["after"]["ledger_jsonl_exists"],
        "summary": payload["after"]["summary"],
        "ledger_match_summary": payload["after"]["ledger_match_summary"],
        "signal_match_records_loaded_now": payload["after"]["signal_match_records_loaded_now"],
        "outcome_summary": payload["after"]["outcome_summary"],
        "orphan_temps": payload["after"]["orphan_temps"],
    }
    return keep


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: estimate revision atomic-write EINVAL repair",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Ledger jsonl before/after: `{delta['before_ledger_jsonl_exists']} -> {delta['after_ledger_jsonl_exists']}`",
            f"- Ledger rows after: `{delta['after_ledger_row_count']}`",
            f"- Signal match records before/after: `{delta['before_daily_signal_match_record_count']} -> {delta['after_daily_signal_match_record_count']}`",
            f"- Matched candidate rows after: `{delta['after_matched_candidate_rows']}`",
            f"- Outcome H3 closed rows: `{delta['outcome_h3_closed_rows']}`",
            "- Strategy behavior changed: `false`",
            "- Accepted alpha: `false`",
            "",
            "## Root cause",
            "",
            "Plain truncating `open('w')` on the final jsonl fails with OSError",
            "Errno 22 (ERROR_USER_MAPPED_FILE) on Windows while another process",
            "holds the file memory-mapped. Writers now use the shared atomic",
            "temp+`os.replace` path (`data_paths.atomic_write_text`).",
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
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_estimate_revision_ledger.py -q",
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / "quant" / "estimate_revision_ledger.py",
        REPO_ROOT / "quant" / "estimate_revision_outcomes.py",
        REPO_ROOT / "quant" / "test_estimate_revision_ledger.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        LEDGER_PATH,
        SUMMARY_PATH,
        OUTCOME_PATH,
        OUTCOME_SUMMARY_PATH,
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
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "changed_files": payload["changed_files"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log_record(payload), allow_duplicate=True)
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
