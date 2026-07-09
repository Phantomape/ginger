"""exp-20260702-005: recover 2026-07-01 quant signal final artifact.

Measurement repair only. The 2026-07-01 estimate-revision ledger was built
while same-day quant signals existed only as an atomic temp file, so candidate
matching reported no loaded signal artifacts. This runner validates the temp
file, restores the canonical final quant signal artifact, reruns the accepted
estimate-revision ledger helper, and records before/after evidence without
changing strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260702-005"
OWNER = "alpha-explore"
LANE = "measurement_repair"
AS_OF = "2026-07-01"
TAG = "20260701"
SLUG = "estimate_revision_20260701_quant_signal_recovery"
RUNNER = f"quant/experiments/exp_20260702_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
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
QUANT_DIR = REPO_ROOT / "data" / "daily" / "signals" / "quant"
QUANT_FINAL = QUANT_DIR / f"quant_signals_{TAG}.json"
QUANT_TMP_GLOB = f".quant_signals_{TAG}.json.*.tmp"
LEDGER_PATH = REPO_ROOT / "data" / "non_ohlcv" / f"estimate_revision_ledger_{TAG}.jsonl"
SUMMARY_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / f"estimate_revision_ledger_summary_{TAG}.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260702_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: the 2026-07-01 estimate-revision candidate-match surface "
    "cannot evaluate same-day quant-signal overlap because quant_signals_20260701 "
    "only exists as a stranded atomic temp file; recover the final artifact and "
    "rerun the ledger to create replayable candidate-match evidence without "
    "changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Estimate-revision direction may have replacement value when it overlaps "
    "same-day production-visible candidate rows, but 2026-07-01 cannot be "
    "evaluated until the same-day quant signal artifact is canonical and the "
    "ledger can load it."
)
CHANGED_VARIABLE = "estimate_revision_20260701_quant_signal_atomic_recovery_v1"
MECHANISM_FAMILY = "production_visible_estimate_revision_candidate_match_attribution"
TRIAL_FAMILY = "estimate_revision_candidate_match_surface_repair"
TRIAL_VARIANT_ID = "estimate_revision_20260701_quant_signal_recovery_v1"
NEW_EVIDENCE_TYPE = "new_daily_quant_signal_artifact_recovery"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-021",
    "exp-20260630-022",
    "exp-20260701-006",
]
CAUSAL_COMPONENTS = [
    "atomic_temp_validation",
    "quant_signal_final_recovery",
    "estimate_revision_ledger_rerun",
    "no_strategy_behavior_change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_005_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "data/daily/signals/quant/quant_signals_20260701.json",
    "data/non_ohlcv/estimate_revision_ledger_20260701.jsonl",
    "data/non_ohlcv/estimate_revision_ledger_summary_20260701.json",
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


def read_json_with_text(path: Path) -> tuple[Any | None, str | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text), None, text
    except (OSError, json.JSONDecodeError) as exc:
        return None, repr(exc), None


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


def canonical_json(value: Any) -> str:
    return json.dumps(safe(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


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


def summarize_quant_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"top_level_type": type(payload).__name__, "valid_shape": False}
    list_counts: dict[str, int] = {}
    ticker_counts: Counter[str] = Counter()
    for key in (
        "signals",
        "pilot_signals",
        "heat_blocked_signals",
        "heat_blocked_pilot_signals",
    ):
        rows = payload.get(key)
        if isinstance(rows, list):
            list_counts[key] = len(rows)
            ticker_counts.update(
                str(row.get("ticker") or row.get("symbol")).upper()
                for row in rows
                if isinstance(row, dict) and (row.get("ticker") or row.get("symbol"))
            )
    for parent_key, child_keys in (
        ("entry_execution_plan", ("deferred_breakout_signals", "slot_sliced_signals")),
        ("pilot_entry_execution_plan", ("pilot_slot_sliced_signals", "tradeable_pilot_signals")),
    ):
        parent = payload.get(parent_key)
        if not isinstance(parent, dict):
            continue
        for child_key in child_keys:
            rows = parent.get(child_key)
            if isinstance(rows, list):
                list_counts[f"{parent_key}.{child_key}"] = len(rows)
                ticker_counts.update(
                    str(row.get("ticker") or row.get("symbol")).upper()
                    for row in rows
                    if isinstance(row, dict) and (row.get("ticker") or row.get("symbol"))
                )
    return {
        "top_level_type": "dict",
        "valid_shape": True,
        "top_level_keys": sorted(payload.keys())[:80],
        "list_counts": list_counts,
        "candidate_like_row_count": sum(list_counts.values()),
        "ticker_count": len(ticker_counts),
        "top_tickers": dict(ticker_counts.most_common(20)),
        "date_fields": {
            key: payload.get(key)
            for key in ("date", "as_of_date", "generated_at", "timestamp")
            if key in payload
        },
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
    usable_candidate_rows = [
        row for row in candidate_rows if row.get("estimate_revision_usable")
    ]
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
                "matched_signal_records": row.get("matched_signal_records"),
            }
            for row in candidate_rows[:12]
        ],
    }


def discover_quant_temp() -> tuple[Path | None, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    candidates = sorted(QUANT_DIR.glob(QUANT_TMP_GLOB))
    valid_by_hash: dict[str, list[Path]] = {}
    for path in candidates:
        payload, error, _ = read_json_with_text(path)
        payload_hash = None
        if error is None:
            payload_hash = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
            valid_by_hash.setdefault(payload_hash, []).append(path)
        records.append(
            {
                "path": repo_rel(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
                "sha256": sha256(path),
                "canonical_payload_sha256": payload_hash,
                "json_valid": error is None,
                "json_error": error,
                "payload_summary": summarize_quant_payload(payload),
            }
        )
    if len(candidates) == 1:
        return candidates[0], records
    if len(valid_by_hash) == 1 and sum(len(v) for v in valid_by_hash.values()) == len(candidates):
        return min(candidates, key=lambda item: item.stat().st_mtime), records
    return None, records


def recover_quant_final(tmp_path: Path | None, tmp_payload: Any, tmp_text: str | None) -> dict[str, Any]:
    final_exists_before = QUANT_FINAL.exists()
    final_payload_before = read_json(QUANT_FINAL, None) if final_exists_before else None
    conflict = (
        final_exists_before
        and tmp_payload is not None
        and canonical_json(final_payload_before) != canonical_json(tmp_payload)
    )
    status = "not_recovered"
    exception_text = None
    if conflict:
        status = "final_artifact_already_conflicts"
    elif final_exists_before:
        status = "final_already_exists_same_payload"
    elif tmp_path is not None and tmp_text is not None:
        try:
            atomic_write_text(tmp_text, QUANT_FINAL)
            status = "recovered_from_valid_atomic_tmp_atomic_write"
        except PermissionError as exc:
            exception_text = repr(exc)
            shutil.copyfile(tmp_path, QUANT_FINAL)
            status = "recovered_from_valid_atomic_tmp_copy_fallback"

    final_payload_after = read_json(QUANT_FINAL, None) if QUANT_FINAL.exists() else None
    payload_matches_after = (
        tmp_payload is not None
        and final_payload_after is not None
        and canonical_json(final_payload_after) == canonical_json(tmp_payload)
    )
    return {
        "tmp_path": repo_rel(tmp_path) if tmp_path else None,
        "final_path": repo_rel(QUANT_FINAL),
        "final_exists_before": final_exists_before,
        "final_exists_after": QUANT_FINAL.exists(),
        "final_sha256_before": sha256(QUANT_FINAL) if final_exists_before else None,
        "final_sha256_after": sha256(QUANT_FINAL),
        "tmp_sha256": sha256(tmp_path) if tmp_path else None,
        "recovery_status": status,
        "conflict": conflict,
        "write_exception": exception_text,
        "final_payload_matches_tmp_after": payload_matches_after,
        "recovered": status.startswith("recovered_from_valid_atomic_tmp"),
    }


def build_calibration(
    prediction: dict[str, Any],
    measurement_passed: bool,
    blockers: list[str],
) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    return {
        "predicted_success_probability": probability,
        "actual_success": 1 if measurement_passed else 0,
        "brier_score": round((probability - (1.0 if measurement_passed else 0.0)) ** 2, 6),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": blockers,
        "predicted_failure_modes_hit": [
            mode
            for mode in prediction.get("main_failure_modes") or []
            if mode in blockers
            or (mode == "temp_file_invalid" and "quant_temp_invalid" in blockers)
            or (
                mode == "no_candidate_matches_after_recovery"
                and "no_matched_candidate_rows_after_rerun" in blockers
            )
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    prediction = ticket.get("prediction") if isinstance(ticket.get("prediction"), dict) else {}
    baseline = baseline_metrics()

    before_summary = read_json(SUMMARY_PATH, {})
    before_rows = read_jsonl(LEDGER_PATH)
    before_match_records = load_daily_signal_match_records(REPO_ROOT / "data", AS_OF)

    tmp_path, tmp_records = discover_quant_temp()
    tmp_payload: Any = None
    tmp_error: str | None = None
    tmp_text: str | None = None
    if tmp_path is None:
        tmp_error = "ambiguous_or_missing_quant_signal_temp" if tmp_records else "missing_quant_signal_temp"
    else:
        tmp_payload, tmp_error, tmp_text = read_json_with_text(tmp_path)

    temp_valid = tmp_error is None and isinstance(tmp_payload, dict) and tmp_text is not None
    recovery = recover_quant_final(
        tmp_path if temp_valid else None,
        tmp_payload if temp_valid else None,
        tmp_text if temp_valid else None,
    )

    after_summary = persist_estimate_revision_ledger(
        as_of=AS_OF,
        data_dir=REPO_ROOT / "data",
        output_dir=REPO_ROOT / "data" / "non_ohlcv",
        generated_at=datetime.now(timezone.utc),
        run_adapter_changed=False,
        signal_data_dir=REPO_ROOT / "data",
        match_daily_signals=True,
    )
    after_rows = read_jsonl(LEDGER_PATH)
    after_match_records = load_daily_signal_match_records(REPO_ROOT / "data", AS_OF)

    before_ledger_match = ledger_match_summary(before_rows)
    after_ledger_match = ledger_match_summary(after_rows)
    before_signal_match = signal_match_summary(before_match_records)
    after_signal_match = signal_match_summary(after_match_records)

    blockers: list[str] = []
    alpha_blockers: list[str] = []
    if not BASELINE_RESULT.exists():
        blockers.append("baseline_missing")
    if tmp_path is None:
        blockers.append(tmp_error or "missing_quant_signal_temp")
    if tmp_error is not None:
        blockers.append("quant_temp_invalid")
    if not temp_valid:
        blockers.append("quant_temp_not_valid_json_object")
    if recovery["conflict"]:
        blockers.append("final_artifact_already_conflicts")
    if not recovery["final_exists_after"]:
        blockers.append("quant_final_missing_after_recovery")
    if temp_valid and not recovery["final_payload_matches_tmp_after"]:
        blockers.append("quant_final_not_equivalent_to_temp_after_recovery")
    if after_signal_match["record_count"] <= 0:
        blockers.append("no_daily_signal_match_records_after_recovery")
    if int(after_summary.get("daily_signal_match_record_count") or 0) <= int(
        before_summary.get("daily_signal_match_record_count") or 0
    ):
        blockers.append("daily_signal_match_record_count_not_increased")
    if after_ledger_match["matched_candidate_rows"] <= 0:
        alpha_blockers.append("no_matched_candidate_rows_after_rerun")
    if after_ledger_match["estimate_revision_usable_and_matched_candidate_rows"] <= 0:
        alpha_blockers.append("no_usable_matched_candidate_rows_after_rerun")

    measurement_passed = not blockers
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        "accepted_measurement_repair_estimate_revision_20260701_quant_signal_recovery"
        if measurement_passed
        else "blocked_estimate_revision_20260701_quant_signal_recovery"
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
        "quant_final_created": recovery["recovered"],
        "before_daily_signal_match_record_count": int(
            before_summary.get("daily_signal_match_record_count") or 0
        ),
        "after_daily_signal_match_record_count": int(
            after_summary.get("daily_signal_match_record_count") or 0
        ),
        "daily_signal_match_record_count_delta": int(
            after_summary.get("daily_signal_match_record_count") or 0
        )
        - int(before_summary.get("daily_signal_match_record_count") or 0),
        "before_matched_feature_rows": before_ledger_match["matched_feature_rows"],
        "after_matched_feature_rows": after_ledger_match["matched_feature_rows"],
        "before_matched_candidate_rows": before_ledger_match["matched_candidate_rows"],
        "after_matched_candidate_rows": after_ledger_match["matched_candidate_rows"],
        "matched_candidate_rows_delta": after_ledger_match["matched_candidate_rows"]
        - before_ledger_match["matched_candidate_rows"],
        "after_usable_matched_candidate_rows": after_ledger_match[
            "estimate_revision_usable_and_matched_candidate_rows"
        ],
        "after_matched_selected_signal_rows": after_ledger_match[
            "matched_selected_signal_rows"
        ],
    }

    production_impact = after_summary.get("production_impact") if isinstance(after_summary, dict) else {}
    production_impact = {
        **(production_impact if isinstance(production_impact, dict) else {}),
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
        "scope": "experiment_scoped_measurement_repair_only",
    }

    calibration = build_calibration(prediction, measurement_passed, blockers + alpha_blockers)
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
        "implementation_mode": "measurement_repair_quant_signal_atomic_recovery",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260630-021": (
                    "Accepted measurement repair for 2026-06-29 ledger ordering "
                    "after same-day quant signals landed."
                ),
                "exp-20260630-022": (
                    "Accepted hot outcome ledger for the 2026-06-29 matched rows."
                ),
                "exp-20260701-006": (
                    "Accepted h1 settlement refresh for the same 2026-06-29 matched rows."
                ),
                "novelty_gate": ticket.get("novelty"),
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only as measurement repair if the quant temp is a valid JSON "
                "object, any final artifact is equivalent or restored from the temp, "
                "the estimate-revision helper loads same-day signal match records, "
                "the ledger is rebuilt, and strategy deltas remain zero."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "as_of_date": AS_OF,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "quant_final": repo_rel(QUANT_FINAL),
            "quant_tmp_glob": repo_rel(QUANT_DIR / QUANT_TMP_GLOB),
            "ledger_path": repo_rel(LEDGER_PATH),
            "summary_path": repo_rel(SUMMARY_PATH),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": measurement_passed,
            "dependencies_validated": bool(temp_valid and recovery["final_exists_after"]),
            "fields_checked": [
                "ticker",
                "as_of_date",
                "matched_candidate_today",
                "matched_feature_row_today",
                "matched_signal_sources",
                "revision_direction_prev",
                "estimate_revision_usable",
                "entry_date_scope",
                "target_price_scope",
            ],
            "quant_temp_candidates": tmp_records,
            "quant_recovery": recovery,
            "before_signal_match_records_loaded_now": before_signal_match,
            "after_signal_match_records_loaded_now": after_signal_match,
            "entry_date_scope": "No executable entry is scheduled; ledger rows are forward attribution inputs.",
            "target_price_scope": "No target exit is scheduled; target_price is not consumed by this repair.",
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
                "closed_forward_replacement_values_absent_for_20260701_rows",
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
            "summary_path": repo_rel(SUMMARY_PATH),
            "ledger_path": repo_rel(LEDGER_PATH),
            "summary": before_summary,
            "ledger_match_summary": before_ledger_match,
            "signal_match_records_loaded_now": before_signal_match,
            "ledger_sha256": sha256(LEDGER_PATH),
            "summary_sha256": sha256(SUMMARY_PATH),
        },
        "after": {
            "summary_path": repo_rel(SUMMARY_PATH),
            "ledger_path": repo_rel(LEDGER_PATH),
            "summary": after_summary,
            "ledger_match_summary": after_ledger_match,
            "signal_match_records_loaded_now": after_signal_match,
            "ledger_sha256": sha256(LEDGER_PATH),
            "summary_sha256": sha256(SUMMARY_PATH),
        },
        "quant_recovery_audit": {
            "temp_candidates": tmp_records,
            "selected_temp_payload_summary": summarize_quant_payload(tmp_payload),
            "recovery": recovery,
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The 2026-07-01 estimate-revision ledger had run before the same-day "
                "quant signal artifact was finalized. Restoring the canonical final "
                "file allowed the existing ledger helper to load same-day signal "
                "records and replace the no-daily-artifact gap with explicit "
                "feature/candidate match state."
                if measurement_passed
                else "The atomic recovery path did not satisfy the fixed measurement contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not run estimate-revision thresholds, direction gates, top-N, "
                "hold, notional, response curves, or observed-only slices from the "
                "2026-07-01 rows until forward replacement outcomes close."
            ),
            "new_evidence_required": (
                "Next alpha-compliant revision work needs closed cash/SPY/QQQ "
                "replacement-value outcomes for matched rows, materially more "
                "selected/current non-flat matches, or a different unsaturated PIT "
                "expectation source."
            ),
        },
        "next_retry_requires": [
            "closed replacement-value outcomes for any matched 2026-07-01 revision rows",
            "materially more selected/current non-flat estimate-revision matches",
            "do not rerun this recovery after the final quant artifact exists",
        ],
        "changed_files": ALLOWED_WRITE_SCOPE,
        "related_files": [
            "quant/estimate_revision_ledger.py",
            "scripts/run_estimate_revision_forward_ledger.py",
            "quant/experiments/exp_20260630_021_estimate_revision_post_quant_signal_match_rerun.py",
            "quant/experiments/exp_20260701_006_estimate_revision_20260629_h1_outcome_refresh.py",
            "experiments/logs/exp-20260630-021.json",
            "experiments/logs/exp-20260630-022.json",
            "experiments/logs/exp-20260701-006.json",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
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
    keep["quant_recovery_audit"] = {
        **payload["quant_recovery_audit"],
        "temp_candidates": payload["quant_recovery_audit"]["temp_candidates"][:5],
    }
    return keep


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: estimate revision 2026-07-01 quant signal recovery",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Quant final created: `{delta['quant_final_created']}`",
            f"- Signal match records before/after: `{delta['before_daily_signal_match_record_count']} -> {delta['after_daily_signal_match_record_count']}`",
            f"- Matched candidate rows before/after: `{delta['before_matched_candidate_rows']} -> {delta['after_matched_candidate_rows']}`",
            f"- Usable matched candidate rows after: `{delta['after_usable_matched_candidate_rows']}`",
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
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
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
        QUANT_FINAL,
        LEDGER_PATH,
        SUMMARY_PATH,
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
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
