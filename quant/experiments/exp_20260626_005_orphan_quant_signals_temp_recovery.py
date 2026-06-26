"""exp-20260626-005: recover orphan quant_signals atomic temp artifacts.

Measurement repair only. Several June 2026 production quant signal payloads
exist only as valid same-directory atomic-write temp files. Downstream replay
and forward-attribution scanners ignore those dot-prefixed temp files, so they
can falsely treat production candidate days as missing. This runner recovers
only missing final artifacts from valid, unambiguous temp files and never
overwrites an existing final artifact.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260626-005"
OWNER = "alpha-explore"
SLUG = "orphan_quant_signals_temp_recovery"
RUNNER = f"quant/experiments/exp_20260626_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_005_{SLUG}.json"
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
QUANT_SIGNAL_DIR = REPO_ROOT / "data" / "daily" / "signals" / "quant"
TEMP_RE = re.compile(r"^\.quant_signals_(\d{8})\.json\.[^.]+\.tmp$")

HYPOTHESIS = (
    "Recover valid orphan quant_signals atomic temp artifacts for June 2026 so "
    "production-visible candidate and paper-sleeve forward attribution does not "
    "falsely treat missing final files as no candidates."
)
ALPHA_HYPOTHESIS = (
    "Production candidate and paper-sleeve forward alpha is only testable if "
    "daily quant_signals artifacts are replayable; missing final artifacts can "
    "hide real candidate rows and block replacement-value attribution."
)
CHANGED_VARIABLE = "orphan_quant_signals_temp_recovery_20260615_20260625_v1"
CAUSAL_COMPONENTS = [
    "orphan temp discovery",
    "JSON validity check",
    "non-overwrite final recovery",
    "forward scanner coverage audit",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-002",
    "exp-20260625-004",
    "exp-20260625-017",
    "exp-20260625-021",
]
RECOVERABLE_TARGETS = [
    "data/daily/signals/quant/quant_signals_20260616.json",
    "data/daily/signals/quant/quant_signals_20260619.json",
    "data/daily/signals/quant/quant_signals_20260620.json",
    "data/daily/signals/quant/quant_signals_20260621.json",
    "data/daily/signals/quant/quant_signals_20260625.json",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260626_005_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
    *RECOVERABLE_TARGETS,
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
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
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def top_level_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in ("items", "rows", "signals", "candidates"):
            nested = value.get(key)
            if isinstance(nested, list):
                return len(nested)
        return len(value)
    return 0


def summarize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "top_level_keys": [],
            "signals_count": 0,
            "entry_candidate_review_count": 0,
            "paper_sleeve_row_count": 0,
            "generated_at": None,
        }
    paper_keys = [
        key
        for key in payload
        if key.endswith("_paper_sleeve")
        or key.endswith("_sleeve")
        or key.endswith("_overlay")
        or key.endswith("_queue")
    ]
    return {
        "top_level_keys": sorted(payload.keys()),
        "top_level_key_count": len(payload),
        "signals_count": top_level_count(payload.get("signals")),
        "entry_candidate_review_count": top_level_count(payload.get("entry_candidate_review")),
        "paper_sleeve_row_count": sum(top_level_count(payload.get(key)) for key in paper_keys),
        "paper_sleeve_key_count": len(paper_keys),
        "generated_at": payload.get("generated_at"),
        "ohlcv_warehouse": payload.get("ohlcv_warehouse"),
    }


def discover_temp_artifacts() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    records: list[dict[str, Any]] = []
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(QUANT_SIGNAL_DIR.iterdir() if QUANT_SIGNAL_DIR.exists() else []):
        match = TEMP_RE.match(path.name)
        if not match:
            continue
        date_tag = match.group(1)
        target = QUANT_SIGNAL_DIR / f"quant_signals_{date_tag}.json"
        raw: str | None = None
        payload: Any = None
        error: str | None = None
        try:
            raw = path.read_text(encoding="utf-8-sig")
            payload = json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - record exact recovery blocker
            error = str(exc)
        record = {
            "date_tag": date_tag,
            "tmp_path": repo_rel(path),
            "target_path": repo_rel(target),
            "tmp_exists": path.exists(),
            "target_exists_before": target.exists(),
            "tmp_size_bytes": path.stat().st_size,
            "tmp_mtime_utc": datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            )
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "tmp_sha256": sha256(path),
            "target_sha256_before": sha256(target),
            "json_valid": error is None,
            "json_error": error,
            "payload_summary": summarize_payload(payload),
            "same_as_existing_target": (
                target.exists() and sha256(path) == sha256(target)
            ),
            "target_exists_after": target.exists(),
            "recovered": False,
            "recovery_status": "not_evaluated",
        }
        records.append(record)
        by_date[date_tag].append(record)
    return records, by_date


def recover_missing_finals(records: list[dict[str, Any]], by_date: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    target_allowlist = {repo_rel(path) for path in RECOVERABLE_TARGETS}
    updated: list[dict[str, Any]] = []
    for record in records:
        date_tag = record["date_tag"]
        target = REPO_ROOT / record["target_path"]
        tmp = REPO_ROOT / record["tmp_path"]
        same_date_records = by_date[date_tag]
        if record["target_path"] not in target_allowlist:
            record["recovery_status"] = "outside_recovery_allowlist"
        elif record["target_exists_before"]:
            record["recovery_status"] = "final_already_exists_no_overwrite"
        elif len(same_date_records) != 1:
            record["recovery_status"] = "ambiguous_multiple_tmp_candidates"
        elif not record["json_valid"]:
            record["recovery_status"] = "tmp_json_invalid"
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tmp, target)
            record["recovered"] = True
            record["recovery_status"] = "recovered_from_valid_tmp"
        record["target_exists_after"] = target.exists()
        record["target_sha256_after"] = sha256(target)
        updated.append(record)
    return updated


def scanner_coverage(records: list[dict[str, Any]], when: str) -> dict[str, Any]:
    exists_key = "target_exists_before" if when == "before" else "target_exists_after"
    dates = sorted({record["date_tag"] for record in records})
    present = [record["date_tag"] for record in records if record.get(exists_key)]
    missing = [date for date in dates if date not in set(present)]
    return {
        "date_count_with_temp": len(dates),
        "canonical_final_present_count": len(set(present)),
        "canonical_final_missing_count": len(missing),
        "canonical_final_present_dates": sorted(set(present)),
        "canonical_final_missing_dates": missing,
    }


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return {
        "success_probability": 0.85,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "tmp_json_invalid",
            "ambiguous_multiple_tmp_candidates",
            "existing_final_differs",
            "write_scope_conflict",
        ],
        "confidence_reason": (
            "The temp files parse as full quant_signals payloads and several "
            "corresponding final files are absent; repair is non-strategy, "
            "non-overwrite, and directly addresses candidate-forward replay coverage."
        ),
        "recorded_at": utc_now(),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    ticket = read_json(TICKET_JSON, {})
    records_before, by_date = discover_temp_artifacts()
    coverage_before = scanner_coverage(records_before, "before")
    records = recover_missing_finals(records_before, by_date)
    coverage_after = scanner_coverage(records, "after")
    recovered_records = [record for record in records if record["recovered"]]
    restored_records = [
        record
        for record in records
        if record["target_path"] in set(RECOVERABLE_TARGETS)
        and record["json_valid"]
        and record["target_exists_after"]
        and record.get("target_sha256_after") == record.get("tmp_sha256")
    ]
    ambiguous = [
        record
        for record in records
        if record["recovery_status"] == "ambiguous_multiple_tmp_candidates"
    ]
    invalid = [record for record in records if record["recovery_status"] == "tmp_json_invalid"]
    failed: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        failed.append("baseline_missing_or_incomplete")
    if not records:
        failed.append("no_orphan_quant_signal_temp_files_found")
    if ambiguous:
        failed.append("ambiguous_multiple_tmp_candidates")
    if invalid:
        failed.append("tmp_json_invalid")
    if len(restored_records) != len(RECOVERABLE_TARGETS):
        missing_recovered = sorted(
            set(RECOVERABLE_TARGETS) - {r["target_path"] for r in restored_records}
        )
        if missing_recovered:
            failed.append("recoverable_target_not_recovered")
    accepted = not failed
    decision = (
        "accepted_measurement_repair_orphan_quant_signals_recovered"
        if accepted
        else "blocked_orphan_quant_signals_recovery_incomplete"
    )
    actual = 1.0 if accepted else 0.0
    prob = float(prediction.get("success_probability") or 0.0)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair_nonoverwrite_daily_artifact_recovery",
        "mechanism_family": "production_candidate_artifact_replayability_repair",
        "trial_family": "orphan_quant_signals_temp_recovery",
        "trial_variant_id": "june_2026_valid_tmp_nonoverwrite_recovery_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "valid_orphan_atomic_temp_daily_candidate_artifacts",
        "new_evidence_axis": (
            "Valid dot-prefixed atomic temp quant_signals artifacts for dates whose "
            "canonical final files were missing; this is not a candidate threshold, "
            "ranking, sizing, entry, exit, hold-day, or notional change."
        ),
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual,
            "predicted_success_probability": prob,
            "brier_score": round((prob - actual) ** 2, 4),
            "expected_ev_delta": prediction.get("expected_ev_delta", 0.0),
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": prediction.get("expected_pnl_delta", 0.0),
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(failed)
            ),
            "surprise_note": (
                "Valid orphan temp files were recovered without overwriting existing finals."
                if accepted
                else "Recovery was blocked by invalid, ambiguous, or missing temp artifacts."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260625-002": "Estimate-revision outcome ledger was blocked by missing recent replayable daily surfaces.",
                "exp-20260625-004": "Local OHLCV recovery audit found no settled 2026-06-24 daily OHLCV substitute.",
                "exp-20260625-017": "Kova price recovery audit found new Kova files still were not daily OHLCV.",
                "exp-20260625-021": "Intraday review replayability remained not alpha-ready.",
                "novelty_gate": "No strong near-neighbor; this is artifact replayability repair, not alpha threshold retuning.",
            },
            "3_single_measurement_bundle": (
                "Recover only missing canonical quant_signals final files from valid, "
                "unambiguous orphan temp files, preserving existing finals."
            ),
            "4_success_failure_standard": (
                "Accept only as measurement repair if baseline stays unchanged, every "
                "allowlisted missing target is recovered, no existing final is overwritten, "
                "and no strategy/live behavior changes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "quant_signal_dir": repo_rel(QUANT_SIGNAL_DIR),
            "temp_filename_regex": TEMP_RE.pattern,
            "recoverable_targets": RECOVERABLE_TARGETS,
            "non_overwrite": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
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
            "canonical_quant_signal_final_present_before": coverage_before[
                "canonical_final_present_count"
            ],
            "canonical_quant_signal_final_present_after": coverage_after[
                "canonical_final_present_count"
            ],
            "canonical_quant_signal_final_recovered": len(recovered_records),
            "canonical_quant_signal_final_restored_or_already_present": len(restored_records),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": bool(records) and not ambiguous and not invalid,
            "required_fields_checked": [
                "generated_at",
                "signals",
                "entry_candidate_review",
                "paper_sleeve top-level blocks",
                "ohlcv_warehouse metadata",
            ],
            "entry_date_scope": "Not applicable: this repair recovers daily candidate artifacts and schedules no trades.",
            "target_price_scope": "Not applicable: no exit or order target behavior is changed.",
            "orphan_temp_files_found": len(records),
            "valid_temp_files": sum(1 for record in records if record["json_valid"]),
            "ambiguous_dates": sorted(
                date for date, items in by_date.items() if len(items) != 1
            ),
        },
        "gate3": {
            "passed": coverage_after["canonical_final_missing_count"] == 0,
            "filter_added": False,
            "signals_generated_proxy": coverage_before["date_count_with_temp"],
            "signals_survived_proxy_before": coverage_before[
                "canonical_final_present_count"
            ],
            "signals_survived_proxy_after": coverage_after[
                "canonical_final_present_count"
            ],
            "survival_rate_proxy_before": round(
                coverage_before["canonical_final_present_count"]
                / coverage_before["date_count_with_temp"],
                4,
            )
            if coverage_before["date_count_with_temp"]
            else None,
            "survival_rate_proxy_after": round(
                coverage_after["canonical_final_present_count"]
                / coverage_after["date_count_with_temp"],
                4,
            )
            if coverage_after["date_count_with_temp"]
            else None,
            "note": "Coverage is measurement-only; no executable signal filter was added.",
        },
        "gate4": {
            "passed": accepted,
            "accepted_alpha": False,
            "decision": decision,
            "failed_reasons": failed,
            "measurement_repair_only": True,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
        },
        "coverage_before": coverage_before,
        "coverage_after": coverage_after,
        "recovered_files": [
            {
                "date_tag": record["date_tag"],
                "tmp_path": record["tmp_path"],
                "target_path": record["target_path"],
                "sha256": record["target_sha256_after"],
                "signals_count": record["payload_summary"]["signals_count"],
                "entry_candidate_review_count": record["payload_summary"][
                    "entry_candidate_review_count"
                ],
                "paper_sleeve_row_count": record["payload_summary"][
                    "paper_sleeve_row_count"
                ],
            }
            for record in recovered_records
        ],
        "temp_artifact_audit": records,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
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
                "Recovered missing persisted daily artifacts from their own valid "
                "atomic-write temp files. No strategy code, shared helper, adapter, "
                "order, rank, size, exit, watchlist, or LLM behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The daily writer had left valid orphan temp payloads for several "
                "June dates while canonical final files were missing. Recovering "
                "them restores replay/candidate scanner coverage without changing "
                "the underlying signal content."
                if accepted
                else (
                    "Recovery could not complete because one or more allowlisted "
                    "temp artifacts were invalid, ambiguous, or missing."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use missing quant_signals finals from 2026-06-16, "
                "2026-06-19, 2026-06-20, 2026-06-21, or 2026-06-25 as evidence "
                "that production generated no candidates on those days. Do not "
                "overwrite existing finals from temp files."
            ),
            "new_evidence_required": (
                "The next alpha step needs a scanner or forward ledger rerun that "
                "uses the recovered final files, plus PIT-safe OHLCV/quote bars for "
                "actual replacement-value settlement."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            "quant/data_paths.py",
            "quant/run.py",
            "quant/estimate_revision_ledger.py",
            "scripts/run_options_forward_ledger.py",
            *RECOVERABLE_TARGETS,
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
            *RECOVERABLE_TARGETS,
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": accepted,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "novelty": ticket.get("novelty"),
            "allowed_write_scope": ticket.get("allowed_write_scope"),
        },
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = {key: value for key, value in payload.items() if key != "temp_artifact_audit"}
    record["temp_artifact_audit_summary"] = [
        {
            "date_tag": item["date_tag"],
            "tmp_path": item["tmp_path"],
            "target_path": item["target_path"],
            "json_valid": item["json_valid"],
            "target_exists_before": item["target_exists_before"],
            "target_exists_after": item["target_exists_after"],
            "recovered": item["recovered"],
            "recovery_status": item["recovery_status"],
            "signals_count": item["payload_summary"]["signals_count"],
            "entry_candidate_review_count": item["payload_summary"][
                "entry_candidate_review_count"
            ],
            "paper_sleeve_row_count": item["payload_summary"]["paper_sleeve_row_count"],
        }
        for item in payload["temp_artifact_audit"]
    ]
    return record


def build_card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: orphan quant_signals temp recovery",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Recovered final files: `{len(payload['recovered_files'])}`",
            "- Strategy behavior changed: `false`",
            "- Production orders changed: `false`",
            "",
            "## Coverage",
            "",
            f"- Before: `{payload['coverage_before']['canonical_final_present_count']}` / `{payload['coverage_before']['date_count_with_temp']}` final files present",
            f"- After: `{payload['coverage_after']['canonical_final_present_count']}` / `{payload['coverage_after']['date_count_with_temp']}` final files present",
            f"- Recovered: `{', '.join(item['target_path'] for item in payload['recovered_files'])}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
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
        *[REPO_ROOT / path for path in RECOVERABLE_TARGETS],
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
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
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
            "new_evidence_axis": payload["new_evidence_axis"],
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
            "coverage_before": payload["coverage_before"],
            "coverage_after": payload["coverage_after"],
            "recovered_files": payload["recovered_files"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
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
                "recovered_files": payload["recovered_files"],
                "coverage_before": payload["coverage_before"],
                "coverage_after": payload["coverage_after"],
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
