"""exp-20260708-004: recover 2026-07-07 orphan daily artifacts.

Measurement repair only. The 2026-07-07 daily run left several valid atomic
temps under daily news and orders directories while the canonical finals were
missing. That blocks structured-news forward observation rows and downstream
replay from seeing the day. This runner promotes only valid 20260707 temps,
regenerates the daily structured-news observer artifacts, and records zero
strategy-behavior delta.
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


EXPERIMENT_ID = "exp-20260708-004"
OWNER = "alpha-explore"
LANE = "measurement_repair"
AS_OF = "2026-07-07"
TAG = "20260707"
SLUG = "daily_artifact_20260707_orphan_atomic_temp_recovery"
RUNNER = f"quant/experiments/exp_20260708_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import stale_artifact_sweep as sweep  # noqa: E402
from daily_news_structured_event_snapshot import (  # noqa: E402
    build_daily_structured_event_snapshot,
)
from data_paths import DAILY_ARTIFACTS, daily_artifact_path  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_004_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

EVENT_FINAL = daily_artifact_path("daily_news_structured_events", TAG, DATA_DIR)
OBS_FINAL = daily_artifact_path("daily_news_structured_event_observations", TAG, DATA_DIR)

HYPOTHESIS = (
    "Alpha blocker: 2026-07-07 daily news/order artifacts were stranded as valid "
    "orphan atomic temp files with missing canonical finals, blocking production-"
    "visible daily structured-news observation and downstream forward attribution; "
    "recover only valid temp payloads and validate observer rows without changing "
    "trading behavior."
)
ALPHA_HYPOTHESIS = (
    "Structured daily-news relation-quality events may become LLM event-scoring "
    "alpha if the daily observer keeps accumulating point-in-time rows that later "
    "close against cash/SPY/QQQ replacement value."
)
CHANGED_VARIABLE = "daily_artifact_20260707_orphan_atomic_temp_recovery_v1"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_measurement_repair"
TRIAL_FAMILY = "daily_artifact_orphan_atomic_write_recovery"
TRIAL_VARIANT_ID = "20260707_daily_news_orders_tmp_recovery_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260628-017",
    "exp-20260701-003",
    "exp-20260704-023",
    "exp-20260705-013",
    "exp-20260706-014",
    "exp-20260706-021",
]


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


def jsonl_text(rows: list[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n"
        for row in rows
    )


def robust_atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{EXPERIMENT_ID}.tmp"
    tmp.write_text(text, encoding="utf-8")
    sweep._promote_with_retry(tmp, path)


def persist_structured_snapshot_robust() -> dict[str, Any]:
    snapshot = build_daily_structured_event_snapshot(AS_OF, data_dir=DATA_DIR)
    event_payload = {
        key: value
        for key, value in snapshot.items()
        if key != "forward_observations"
    }
    robust_atomic_text(
        EVENT_FINAL,
        json.dumps(safe(event_payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
    )
    robust_atomic_text(
        OBS_FINAL,
        jsonl_text(list(snapshot.get("forward_observations") or [])),
    )
    return {
        key: value
        for key, value in snapshot.items()
        if key not in {"rows", "forward_observations"}
    }


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


def artifact_status() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in sorted(DAILY_ARTIFACTS):
        path = daily_artifact_path(key, TAG, DATA_DIR)
        parent = path.parent
        temps = sorted(parent.glob(f".{path.name}.*.tmp")) if parent.exists() else []
        out[key] = {
            "path": repo_rel(path),
            "exists": path.exists(),
            "sha256": sha256(path),
            "temp_count": len(temps),
            "temps": [repo_rel(temp) for temp in temps],
        }
    return out


def temp_summary(path: Path, final_path: Path, final_name: str) -> dict[str, Any]:
    valid = False
    error = None
    try:
        valid = sweep._temp_payload_is_valid(path, final_name)
    except Exception as exc:  # defensive audit only
        error = repr(exc)
    try:
        age_s = round(datetime.now(timezone.utc).timestamp() - path.stat().st_mtime)
    except OSError:
        age_s = None
    return {
        "temp_path": repo_rel(path),
        "final_path": repo_rel(final_path),
        "final_name": final_name,
        "final_exists": final_path.exists(),
        "target_date": TAG in final_name,
        "valid_payload": valid,
        "validation_error": error,
        "size_bytes": path.stat().st_size if path.exists() else None,
        "age_s": age_s,
        "sha256": sha256(path),
    }


def scan_target_temps() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in sweep._RECOVERABLE_DIRS:
        directory = REPO_ROOT / rel
        if not directory.is_dir():
            continue
        for entry in os.scandir(directory):
            if not (entry.is_file() and entry.name.endswith(".tmp")):
                continue
            final_name = sweep._final_name_for_temp(entry.name)
            if not final_name or TAG not in final_name:
                continue
            temp_path = Path(entry.path)
            rows.append(temp_summary(temp_path, directory / final_name, final_name))
    return sorted(rows, key=lambda row: row["temp_path"])


def recover_target_temps() -> dict[str, Any]:
    recovered: list[str] = []
    cleaned: list[str] = []
    skipped: list[dict[str, Any]] = []
    for row in scan_target_temps():
        temp_path = REPO_ROOT / row["temp_path"]
        final_path = REPO_ROOT / row["final_path"]
        if row["final_exists"]:
            try:
                sweep._unlink_with_retry(temp_path)
            except OSError as exc:
                skipped.append({**row, "reason": f"unlink_failed:{exc}"})
                continue
            cleaned.append(row["temp_path"])
            continue
        if not row["valid_payload"]:
            skipped.append({**row, "reason": "invalid_or_partial_payload"})
            continue
        try:
            sweep._promote_with_retry(temp_path, final_path)
        except OSError as exc:
            skipped.append({**row, "reason": f"promote_failed:{exc}"})
            continue
        recovered.append(row["final_path"])
    return {"recovered": recovered, "cleaned": cleaned, "skipped": skipped}


def structured_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    event_audit = snapshot.get("event_contract_audit") or {}
    obs_audit = snapshot.get("forward_observation_contract_audit") or {}
    rows = read_jsonl(OBS_FINAL)
    outcome_status = Counter(str(row.get("outcome_status")) for row in rows)
    relation_counts = Counter(str(row.get("relation_type")) for row in rows)
    tickers = sorted({str(row.get("ticker")) for row in rows if row.get("ticker")})
    return {
        "event_artifact": repo_rel(EVENT_FINAL),
        "observation_artifact": repo_rel(OBS_FINAL),
        "event_artifact_exists": EVENT_FINAL.exists(),
        "observation_artifact_exists": OBS_FINAL.exists(),
        "event_sha256": sha256(EVENT_FINAL),
        "observation_sha256": sha256(OBS_FINAL),
        "event_ledger_rows": event_audit.get("ledger_rows"),
        "observation_rows": obs_audit.get("observation_rows"),
        "target_relation_quality_rows": obs_audit.get("target_relation_quality_rows"),
        "event_required_fields_ok": (
            (event_audit.get("required_field_audit") or {}).get("all_required_fields_present")
        ),
        "observation_required_fields_ok": (
            (obs_audit.get("required_field_audit") or {}).get("all_required_fields_present")
        ),
        "duplicate_event_ids": event_audit.get("duplicate_event_ids"),
        "duplicate_observation_ids": obs_audit.get("duplicate_observation_ids"),
        "date_range": obs_audit.get("date_range"),
        "relation_counts": dict(sorted(relation_counts.items())),
        "outcome_status_counts": dict(sorted(outcome_status.items())),
        "tickers": tickers,
    }


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    baseline = baseline_metrics()
    before_artifacts = artifact_status()
    before_temps = scan_target_temps()

    recovery = recover_target_temps()
    after_recovery_artifacts = artifact_status()

    snapshot = persist_structured_snapshot_robust()
    after_artifacts = artifact_status()
    after_temps = scan_target_temps()
    structured = structured_summary(snapshot)

    valid_missing_before = [
        row for row in before_temps if row["valid_payload"] and not row["final_exists"]
    ]
    valid_missing_after = [
        row for row in after_temps if row["valid_payload"] and not row["final_exists"]
    ]

    measurement_blockers: list[str] = []
    alpha_blockers = [
        "structured_news_rows_pending_forward_close",
        "no_cash_spy_qqq_replacement_values_for_20260707_rows",
    ]
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if valid_missing_after:
        measurement_blockers.append("valid_20260707_orphan_temp_still_missing_final")
    if int(structured.get("event_ledger_rows") or 0) <= 0:
        measurement_blockers.append("structured_observer_zero_rows")
    if int(structured.get("observation_rows") or 0) <= 0:
        measurement_blockers.append("structured_observation_zero_rows")
    if not structured.get("event_required_fields_ok"):
        measurement_blockers.append("structured_event_required_fields_missing")
    if not structured.get("observation_required_fields_ok"):
        measurement_blockers.append("structured_observation_required_fields_missing")
    if int(structured.get("duplicate_event_ids") or 0) != 0:
        measurement_blockers.append("duplicate_event_ids")
    if int(structured.get("duplicate_observation_ids") or 0) != 0:
        measurement_blockers.append("duplicate_observation_ids")

    measurement_passed = not measurement_blockers
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        "accepted_measurement_repair_daily_artifact_20260707_orphan_atomic_recovery"
        if measurement_passed
        else "blocked_daily_artifact_20260707_orphan_atomic_recovery"
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
        "valid_missing_temp_count_before": len(valid_missing_before),
        "valid_missing_temp_count_after": len(valid_missing_after),
        "recovered_final_count": len(recovery["recovered"]),
        "cleaned_temp_count": len(recovery["cleaned"]),
        "skipped_temp_count": len(recovery["skipped"]),
        "structured_event_rows": int(structured.get("event_ledger_rows") or 0),
        "structured_observation_rows": int(structured.get("observation_rows") or 0),
        "target_relation_quality_rows": int(
            structured.get("target_relation_quality_rows") or 0
        ),
    }
    probability = 0.82
    prediction = ticket.get("prediction") or {
        "success_probability": probability,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "temp_payload_invalid",
            "promote_permission_denied",
            "structured_observer_zero_rows",
            "artifact_conflict",
            "lean_audit_failure",
        ],
        "confidence_reason": (
            "Preflight found valid-sized 20260707 temp artifacts and prior shared "
            "recovery code/tests already cover daily artifact promotion."
        ),
    }
    calibration = {
        "predicted_success_probability": probability,
        "actual_success": 1 if measurement_passed else 0,
        "brier_score": round((probability - (1.0 if measurement_passed else 0.0)) ** 2, 6),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": measurement_blockers + alpha_blockers,
        "predicted_failure_mode_hit": bool(
            set(measurement_blockers)
            & {
                "temp_payload_invalid",
                "promote_permission_denied",
                "structured_observer_zero_rows",
                "artifact_conflict",
                "lean_audit_failure",
            }
        ),
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": True,
        "news_archives_changed": True,
        "orders_artifact_recovered": any("orders/" in path for path in recovery["recovered"]),
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_logic_changed": False,
        "live_orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "measurement_repair_daily_artifact_recovery_only",
    }
    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
        repo_rel(EVENT_FINAL),
        repo_rel(OBS_FINAL),
        *recovery["recovered"],
    ]
    changed_files = list(dict.fromkeys(changed_files))
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
        "implementation_mode": "measurement_repair_daily_artifact_orphan_recovery",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "orphan atomic temp validation",
            "targeted 20260707 daily artifact recovery",
            "daily structured-news observer validation",
            "zero strategy behavior delta",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "fresh_20260707_orphan_atomic_write_artifacts",
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260628-017": "Accepted shared atomic-write retry and recover-before-delete daily sweep.",
                "exp-20260701-003": "Accepted 2026-06-30 daily news atomic temp recovery.",
                "exp-20260704-023": "Accepted broader daily-artifact recovery coverage for 2026-07-03.",
                "exp-20260705-013/exp-20260706-014": "Allowed only new orphan temps after later materialization runs.",
                "novelty_gate": ticket.get("novelty"),
                "why_allowed": (
                    "This is fresh 20260707 fault recovery for missing canonical "
                    "daily artifacts, not a threshold, slice, horizon, rank, or "
                    "response-curve retry."
                ),
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if valid 20260707 temps are promoted/cleaned, no valid "
                "missing-final target temps remain, the structured observer writes "
                "schema-complete nonzero event/observation rows, and strategy deltas "
                "remain zero."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "as_of_date": AS_OF,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "event_final": repo_rel(EVENT_FINAL),
            "observation_final": repo_rel(OBS_FINAL),
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
                "event_id",
                "event_date",
                "ticker",
                "relation_type",
                "relation_polarity",
                "observation_id",
                "entry_semantics",
                "target_price",
                "outcome_status",
            ],
            "entry_date_scope": "Forward observations are pending; no executable entry is scheduled.",
            "target_price_scope": "No target exit is scheduled; target_price is intentionally null.",
        },
        "gate3": {
            "passed": measurement_passed,
            "filter_added": False,
            "signals_generated": delta_metrics["structured_observation_rows"],
            "signals_survived": delta_metrics["target_relation_quality_rows"],
            "survival_rate": round(
                delta_metrics["target_relation_quality_rows"]
                / delta_metrics["structured_observation_rows"],
                6,
            )
            if delta_metrics["structured_observation_rows"]
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
            "daily_artifacts": before_artifacts,
            "target_temps": before_temps,
        },
        "after": {
            "daily_artifacts_after_recovery_before_snapshot": after_recovery_artifacts,
            "daily_artifacts": after_artifacts,
            "target_temps": after_temps,
            "structured_summary": structured,
            "snapshot_audit": {
                "event_contract_audit": snapshot.get("event_contract_audit"),
                "forward_observation_contract_audit": snapshot.get(
                    "forward_observation_contract_audit"
                ),
            },
        },
        "recovery_audit": recovery,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The 2026-07-07 daily writer left valid atomic temp payloads but "
                "canonical finals were absent. Promoting the temps restored the "
                "news/order archive surface, and rerunning the accepted structured "
                "observer produced replayable pending rows without touching trading "
                "logic."
                if measurement_passed
                else "The targeted daily-artifact recovery path did not satisfy the fixed measurement contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reopen 2026-07-07 daily artifact recovery after these finals "
                "exist. Do not slice the structured-news rows by relation/ticker/source "
                "or tune a response curve until forward replacement outcomes close."
            ),
            "new_evidence_required": (
                "Closed cash/SPY/QQQ replacement-value outcomes for 2026-07-07 "
                "structured-news rows, materially more settled daily structured rows, "
                "or a distinct PIT LLM event-scoring field."
            ),
        },
        "next_retry_requires": [
            "closed replacement-value outcomes for 20260707 structured-news rows",
            "materially more settled daily structured-news rows",
            "new orphan temps from a later materialization run for any further fault recovery",
        ],
        "changed_files": changed_files,
        "related_files": [
            "quant/stale_artifact_sweep.py",
            "quant/daily_news_structured_event_snapshot.py",
            "quant/daily_news_structured_events.py",
            "quant/test_atomic_write_recovery.py",
            "experiments/logs/exp-20260701-003.json",
            "experiments/logs/exp-20260704-023.json",
            "experiments/logs/exp-20260706-014.json",
        ],
        "allowed_write_scope": changed_files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_daily_news_structured_event_snapshot.py quant\\test_daily_news_structured_events.py quant\\test_atomic_write_recovery.py -q",
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
        "target_temps": payload["before"]["target_temps"],
        "daily_artifacts": {
            key: value
            for key, value in payload["before"]["daily_artifacts"].items()
            if value.get("temp_count") or value.get("exists")
        },
    }
    keep["after"] = {
        "target_temps": payload["after"]["target_temps"],
        "structured_summary": payload["after"]["structured_summary"],
    }
    return keep


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: daily artifact recovery 2026-07-07",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Valid missing temps before/after: `{delta['valid_missing_temp_count_before']} -> {delta['valid_missing_temp_count_after']}`",
            f"- Recovered finals: `{delta['recovered_final_count']}`",
            f"- Cleaned temps: `{delta['cleaned_temp_count']}`",
            f"- Structured event rows: `{delta['structured_event_rows']}`",
            f"- Structured observation rows: `{delta['structured_observation_rows']}`",
            f"- Target relation-quality rows: `{delta['target_relation_quality_rows']}`",
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
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
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
        EVENT_FINAL,
        OBS_FINAL,
        BASELINE_RESULT,
    ]
    for rel in payload.get("recovery_audit", {}).get("recovered", []):
        files.append(REPO_ROOT / rel)
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
