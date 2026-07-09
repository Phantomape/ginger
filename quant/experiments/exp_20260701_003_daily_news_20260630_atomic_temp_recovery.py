"""exp-20260701-003: recover 2026-06-30 daily-news atomic temp input.

Measurement repair / alpha-enabling instrumentation. The 2026-06-30 clean
trade-news archive exists only as a valid atomic-write temp file, so the daily
structured-news observer sees no canonical input and emits zero rows. This
runner recovers the missing final input, rebuilds the read-only structured
event and forward-observation artifacts through the accepted shared helper,
and records that no trading behavior changed.
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
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260701-003"
OWNER = "alpha-explore"
LANE = "measurement_repair"
DATE_TAG = "20260630"
ISO_DATE = "2026-06-30"
SLUG = "daily_news_20260630_atomic_temp_recovery"
RUNNER = f"quant/experiments/exp_20260701_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from daily_news_structured_event_snapshot import (  # noqa: E402
    DAILY_STRUCTURED_OBSERVER_RULE_VERSION,
    build_daily_structured_event_snapshot,
)
from data_paths import DATA_ROOT, atomic_write_text  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
CLEAN_TRADE_DIR = DATA_ROOT / "daily" / "news" / "trade"
CLEAN_FINAL = CLEAN_TRADE_DIR / f"clean_trade_news_{DATE_TAG}.json"
CLEAN_TMP_GLOB = f".clean_trade_news_{DATE_TAG}.json.*.tmp"
STRUCTURED_DIR = DATA_ROOT / "daily" / "news" / "structured"
STRUCTURED_EVENT_FINAL = STRUCTURED_DIR / f"daily_news_structured_events_{DATE_TAG}.json"
STRUCTURED_OBSERVATION_FINAL = (
    STRUCTURED_DIR / f"daily_news_structured_event_observations_{DATE_TAG}.jsonl"
)
STRUCTURED_TMP_GLOB = f".daily_news_structured_events_{DATE_TAG}.json.*.tmp"
WRITE_FALLBACKS: list[dict[str, Any]] = []

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260701_003_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: structured daily-news relation-quality may become LLM "
    "event-scoring alpha, but the 2026-06-30 clean_trade_news final artifact is "
    "missing while a valid atomic temp exists, causing the daily structured "
    "observer to emit zero rows; recover and validate the fixed observer rows "
    "without changing trading behavior."
)
ALPHA_HYPOTHESIS = (
    "Structured daily-news relation-quality events may become tradable LLM "
    "event-scoring alpha if the production daily observer keeps accumulating "
    "PIT rows that can later close against cash/SPY/QQQ replacement value."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_measurement_repair"
TRIAL_FAMILY = "daily_news_structured_event_atomic_recovery"
TRIAL_VARIANT_ID = "20260630_clean_trade_news_tmp_recovery_v1"
CHANGED_VARIABLE = "daily_news_20260630_atomic_temp_recovery_structured_observer_v1"
NEW_EVIDENCE_TYPE = "production_daily_forward_observation_rows_recovered_from_atomic_temp"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-001",
    "exp-20260630-006",
    "exp-20260630-007",
    "exp-20260630-019",
]
CAUSAL_COMPONENTS = [
    "atomic temp recovery",
    "structured event helper",
    "daily observation artifact schema",
    "no strategy behavior change",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
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
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        safe(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def write_json(path: Path, payload: Any) -> None:
    write_text(
        path,
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
    )


def write_text(path: Path, text: str) -> None:
    try:
        atomic_write_text(text, path)
    except PermissionError as exc:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        WRITE_FALLBACKS.append(
            {
                "path": repo_rel(path),
                "exception": repr(exc),
                "fallback": "direct_write_after_atomic_rename_denied",
            }
        )


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_json_with_error(path: Path) -> tuple[Any | None, str | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text), None, text
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc), None


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_jsonl_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def jsonl_text(rows: Iterable[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n"
        for row in rows
    )


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return (ticket.get("prediction") if isinstance(ticket, Mapping) else None) or {}


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or []) if isinstance(payload, Mapping) else []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
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
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
    }


def summarize_clean_payload(payload: Any) -> dict[str, Any]:
    rows = payload if isinstance(payload, list) else []
    source_counts = Counter(str(row.get("source") or "") for row in rows if isinstance(row, Mapping))
    ticker_counts: Counter[str] = Counter()
    explicit_ticker_items = 0
    for row in rows:
        tickers = row.get("tickers") if isinstance(row, Mapping) else None
        if isinstance(tickers, list) and tickers:
            explicit_ticker_items += 1
            ticker_counts.update(str(ticker) for ticker in tickers)
    return {
        "top_level_type": type(payload).__name__,
        "row_count": len(rows),
        "explicit_ticker_items": explicit_ticker_items,
        "source_counts": dict(source_counts.most_common(10)),
        "ticker_top20": dict(ticker_counts.most_common(20)),
        "sample_titles": [
            str(row.get("title") or "")[:180]
            for row in rows[:5]
            if isinstance(row, Mapping)
        ],
    }


def summarize_structured_temp(path: Path) -> dict[str, Any]:
    payload, error, _ = read_json_with_error(path)
    if error or not isinstance(payload, Mapping):
        return {
            "path": repo_rel(path),
            "exists": path.exists(),
            "json_valid": error is None,
            "json_error": error,
        }
    event_audit = payload.get("event_contract_audit") or {}
    obs_audit = payload.get("forward_observation_contract_audit") or {}
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "json_valid": True,
        "file_count": event_audit.get("file_count"),
        "ignored_temp_file_count": event_audit.get("ignored_temp_file_count"),
        "raw_items": event_audit.get("raw_items"),
        "ledger_rows": event_audit.get("ledger_rows"),
        "observation_rows": obs_audit.get("observation_rows"),
        "target_relation_quality_rows": obs_audit.get("target_relation_quality_rows"),
    }


def discover_clean_temp() -> tuple[Path | None, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    paths = sorted(CLEAN_TRADE_DIR.glob(CLEAN_TMP_GLOB))
    equivalent_groups: dict[str, list[Path]] = {}
    for path in paths:
        payload, error, _ = read_json_with_error(path)
        payload_key = canonical_json(payload) if error is None else None
        payload_hash = (
            hashlib.sha256(payload_key.encode("utf-8")).hexdigest()
            if payload_key is not None
            else None
        )
        if payload_key is not None:
            equivalent_groups.setdefault(payload_key, []).append(path)
        records.append(
            {
                "path": repo_rel(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
                "sha256": sha256_file(path),
                "canonical_payload_sha256": payload_hash,
                "json_valid": error is None,
                "json_error": error,
                "payload_summary": summarize_clean_payload(payload),
            }
        )
    if len(paths) == 1:
        return paths[0], records
    if len(equivalent_groups) == 1 and len(next(iter(equivalent_groups.values()))) == len(paths):
        selected = min(paths, key=lambda item: item.stat().st_mtime)
        return selected, records
    return None, records


def recover_clean_final(
    tmp_path: Path | None,
    tmp_payload: Any,
    tmp_text: str | None,
) -> dict[str, Any]:
    final_exists_before = CLEAN_FINAL.exists()
    final_payload_before = read_json(CLEAN_FINAL, None) if final_exists_before else None
    conflict = (
        final_exists_before
        and tmp_payload is not None
        and canonical_json(final_payload_before) != canonical_json(tmp_payload)
    )
    status = "not_recovered"
    write_exception: str | None = None
    if conflict:
        status = "final_artifact_already_conflicts"
    elif final_exists_before:
        status = "final_already_exists_same_payload"
    elif tmp_path and tmp_text is not None:
        try:
            atomic_write_text(tmp_text, CLEAN_FINAL)
            status = "recovered_from_valid_atomic_tmp_atomic_write"
        except PermissionError as exc:
            write_exception = repr(exc)
            shutil.copyfile(tmp_path, CLEAN_FINAL)
            status = "recovered_from_valid_atomic_tmp_copy_fallback"

    final_payload_after = read_json(CLEAN_FINAL, None) if CLEAN_FINAL.exists() else None
    payload_matches_after = (
        tmp_payload is not None
        and final_payload_after is not None
        and canonical_json(final_payload_after) == canonical_json(tmp_payload)
    )

    return {
        "date_tag": DATE_TAG,
        "tmp_path": repo_rel(tmp_path) if tmp_path else None,
        "final_path": repo_rel(CLEAN_FINAL),
        "final_exists_before": final_exists_before,
        "final_exists_after": CLEAN_FINAL.exists(),
        "final_sha256_before": sha256_file(CLEAN_FINAL) if final_exists_before else None,
        "final_sha256_after": sha256_file(CLEAN_FINAL),
        "tmp_sha256": sha256_file(tmp_path) if tmp_path else None,
        "recovery_status": status,
        "conflict": conflict,
        "write_exception": write_exception,
        "final_payload_matches_tmp_after": payload_matches_after,
        "recovered": status.startswith("recovered_from_valid_atomic_tmp"),
    }


def event_ids(snapshot: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("event_id"))
        for row in snapshot.get("rows") or []
        if isinstance(row, Mapping) and row.get("event_id")
    ]


def observation_ids(snapshot: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("observation_id"))
        for row in snapshot.get("forward_observations") or []
        if isinstance(row, Mapping) and row.get("observation_id")
    ]


def write_structured_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    event_path = Path(str(snapshot.get("event_artifact_path") or STRUCTURED_EVENT_FINAL))
    observation_path = Path(
        str(snapshot.get("forward_observation_artifact_path") or STRUCTURED_OBSERVATION_FINAL)
    )
    event_payload = {
        key: value
        for key, value in snapshot.items()
        if key != "forward_observations"
    }
    write_json(event_path, event_payload)
    write_text(observation_path, jsonl_text(snapshot.get("forward_observations") or []))
    return {
        "event_artifact_path": repo_rel(event_path),
        "observation_artifact_path": repo_rel(observation_path),
        "event_artifact_exists": event_path.exists(),
        "observation_artifact_exists": observation_path.exists(),
        "event_artifact_sha256": sha256_file(event_path),
        "observation_artifact_sha256": sha256_file(observation_path),
        "observation_jsonl_rows": count_jsonl_rows(observation_path),
        "paths_match_expected": (
            event_path.resolve() == STRUCTURED_EVENT_FINAL.resolve()
            and observation_path.resolve() == STRUCTURED_OBSERVATION_FINAL.resolve()
        ),
    }


def build_snapshot_after_recovery() -> tuple[dict[str, Any], dict[str, Any], str | None]:
    try:
        snapshot = build_daily_structured_event_snapshot(DATE_TAG, data_dir=DATA_ROOT)
        write_audit = write_structured_snapshot(snapshot)
        second_snapshot = build_daily_structured_event_snapshot(DATE_TAG, data_dir=DATA_ROOT)
        write_audit["event_ids_stable"] = event_ids(snapshot) == event_ids(second_snapshot)
        write_audit["observation_ids_stable"] = observation_ids(snapshot) == observation_ids(second_snapshot)
        return snapshot, write_audit, None
    except Exception as exc:  # noqa: BLE001 - experiment artifact records blocker.
        return {}, {"exception": repr(exc)}, repr(exc)


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    tmp_path, tmp_records = discover_clean_temp()
    tmp_payload: Any = None
    tmp_error: str | None = None
    tmp_text: str | None = None
    if tmp_path is None:
        tmp_error = (
            "ambiguous_or_missing_clean_trade_news_temp"
            if tmp_records
            else "missing_clean_trade_news_temp"
        )
    else:
        tmp_payload, tmp_error, tmp_text = read_json_with_error(tmp_path)

    before_structured_temps = [
        summarize_structured_temp(path) for path in sorted(STRUCTURED_DIR.glob(STRUCTURED_TMP_GLOB))
    ]
    clean_payload_valid = (
        tmp_error is None
        and isinstance(tmp_payload, list)
        and len(tmp_payload) > 0
        and tmp_text is not None
    )
    recovery = recover_clean_final(
        tmp_path if clean_payload_valid else None,
        tmp_payload if clean_payload_valid else None,
        tmp_text if clean_payload_valid else None,
    )
    snapshot, write_audit, snapshot_error = build_snapshot_after_recovery()

    event_audit = snapshot.get("event_contract_audit") or {}
    obs_audit = snapshot.get("forward_observation_contract_audit") or {}
    event_field_audit = event_audit.get("required_field_audit") or {}
    obs_field_audit = obs_audit.get("required_field_audit") or {}
    event_rows = list(snapshot.get("rows") or [])
    observation_rows = list(snapshot.get("forward_observations") or [])
    failed_reasons: list[str] = []
    if not BASELINE_RESULT.exists():
        failed_reasons.append("baseline_missing")
    if tmp_path is None:
        failed_reasons.append(tmp_error or "missing_clean_trade_news_temp")
    if tmp_error is not None:
        failed_reasons.append("temp_json_incomplete")
    if not clean_payload_valid:
        failed_reasons.append("clean_temp_not_nonempty_json_array")
    if recovery["conflict"]:
        failed_reasons.append("final_artifact_already_conflicts")
    if not recovery["final_exists_after"]:
        failed_reasons.append("final_clean_trade_news_missing_after_recovery")
    if clean_payload_valid and not recovery["final_payload_matches_tmp_after"]:
        failed_reasons.append("final_payload_not_equivalent_to_temp_after_recovery")
    if snapshot_error:
        failed_reasons.append("structured_helper_exception")
    if int(event_audit.get("ledger_rows") or 0) <= 0:
        failed_reasons.append("structured_helper_still_zero_rows")
    if int(obs_audit.get("observation_rows") or 0) <= 0:
        failed_reasons.append("structured_observer_still_zero_rows")
    if int(obs_audit.get("observation_rows") or 0) != int(event_audit.get("ledger_rows") or 0):
        failed_reasons.append("observation_row_count_mismatch")
    if int(obs_audit.get("target_relation_quality_rows") or 0) <= 0:
        failed_reasons.append("no_target_relation_quality_rows")
    if int(event_audit.get("duplicate_event_ids") or 0) > 0:
        failed_reasons.append("duplicate_event_ids")
    if int(obs_audit.get("duplicate_observation_ids") or 0) > 0:
        failed_reasons.append("duplicate_observation_ids")
    if event_field_audit and not event_field_audit.get("all_required_fields_present"):
        failed_reasons.append("event_required_fields_missing")
    if obs_field_audit and not obs_field_audit.get("all_required_fields_present"):
        failed_reasons.append("observation_required_fields_missing")
    if not write_audit.get("paths_match_expected"):
        failed_reasons.append("daily_artifact_path_mismatch")
    if not write_audit.get("event_artifact_exists"):
        failed_reasons.append("event_artifact_not_written")
    if not write_audit.get("observation_artifact_exists"):
        failed_reasons.append("observation_artifact_not_written")
    if write_audit.get("observation_jsonl_rows") != int(obs_audit.get("observation_rows") or 0):
        failed_reasons.append("observation_jsonl_row_count_mismatch")
    if not write_audit.get("event_ids_stable") or not write_audit.get("observation_ids_stable"):
        failed_reasons.append("structured_id_instability")

    accepted = not failed_reasons
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_daily_news_20260630_atomic_temp_recovery"
        if accepted
        else "blocked_daily_news_20260630_atomic_temp_recovery"
    )
    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(LOG_JSON),
        repo_rel(REGISTRY_JSON),
        repo_rel(CLEAN_FINAL),
        repo_rel(STRUCTURED_EVENT_FINAL),
        repo_rel(STRUCTURED_OBSERVATION_FINAL),
    ]
    delta_metrics = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "max_drawdown_pct_delta": 0.0,
        "clean_trade_news_final_created": recovery["recovered"],
        "clean_trade_news_rows_after": summarize_clean_payload(read_json(CLEAN_FINAL, [])).get("row_count"),
        "previous_structured_tmp_ledger_rows": [
            row.get("ledger_rows") for row in before_structured_temps
        ],
        "previous_structured_tmp_observation_rows": [
            row.get("observation_rows") for row in before_structured_temps
        ],
        "after_event_rows": int(event_audit.get("ledger_rows") or 0),
        "after_observation_rows": int(obs_audit.get("observation_rows") or 0),
        "after_target_relation_quality_rows": int(
            obs_audit.get("target_relation_quality_rows") or 0
        ),
        "after_event_date_count": int(event_audit.get("event_date_count") or 0),
        "after_ticker_count": int(obs_audit.get("target_relation_quality_tickers") or 0),
        "after_source_file_count": int(event_audit.get("file_count") or 0),
        "after_raw_items": int(event_audit.get("raw_items") or 0),
        "after_explicit_ticker_items": int(event_audit.get("explicit_ticker_items") or 0),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair_daily_news_atomic_temp_recovery",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260630-005": (
                    "Observed-only positive relation-quality lead; not promoted "
                    "because coverage was forward-only."
                ),
                "exp-20260630-006": (
                    "Accepted shared structured-event forward observation contract."
                ),
                "exp-20260630-007": (
                    "Accepted daily observer wiring; latest clean artifact then "
                    "produced rows."
                ),
                "exp-20260630-019": (
                    "Accepted intraday structured-event deltas; not a daily "
                    "clean_trade_news recovery."
                ),
                "novelty_gate": (
                    "Reservation passed without override; this is a missing-input "
                    "repair that creates new PIT observation rows, not a reslice."
                ),
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if the clean_trade_news temp is a nonempty valid JSON "
                "array, any existing final is equivalent, the final input is present "
                "after recovery, the accepted daily observer writes nonzero schema-"
                "complete event/observation rows, IDs are stable, and strategy "
                "metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "date_tag": DATE_TAG,
            "iso_date": ISO_DATE,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "clean_trade_news_final": repo_rel(CLEAN_FINAL),
            "clean_trade_news_tmp_glob": repo_rel(CLEAN_TRADE_DIR / CLEAN_TMP_GLOB),
            "structured_event_artifact": repo_rel(STRUCTURED_EVENT_FINAL),
            "structured_observation_artifact": repo_rel(STRUCTURED_OBSERVATION_FINAL),
            "observer_rule_version": DAILY_STRUCTURED_OBSERVER_RULE_VERSION,
            "data_dir": repo_rel(DATA_ROOT),
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": accepted,
            "dependencies_validated": bool(clean_payload_valid and snapshot),
            "fields_checked": [
                "source",
                "title",
                "summary",
                "published_at",
                "tickers",
                "event_date",
                "ticker",
                "relation_type",
                "relation_polarity",
                "evidence_span",
                "source_provenance",
                "observation_id",
                "entry_semantics",
                "exit_semantics",
                "entry_date",
                "target_price",
                "outcome_status",
            ],
            "clean_temp_candidates": tmp_records,
            "clean_final_recovery": recovery,
            "event_required_field_audit": event_field_audit,
            "observation_required_field_audit": obs_field_audit,
            "entry_date_scope": "Forward observations are pending; no executable entry is scheduled.",
            "target_price_scope": "No target exit is scheduled; target_price is intentionally null.",
            "artifact_write_audit": write_audit,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": int(event_audit.get("ledger_rows") or 0),
            "signals_survived": int(obs_audit.get("observation_rows") or 0),
            "survival_rate": round(
                int(obs_audit.get("observation_rows") or 0)
                / int(event_audit.get("ledger_rows") or 1),
                4,
            )
            if int(event_audit.get("ledger_rows") or 0)
            else None,
            "target_relation_quality_rows": int(
                obs_audit.get("target_relation_quality_rows") or 0
            ),
            "note": "Measurement rows only; no executable filter or rank rule was added.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "measurement_repair_only": True,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "max_drawdown_pct_delta": 0.0,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "daily_input_recovery_audit": {
            "clean_temp_candidates": tmp_records,
            "clean_payload_summary": summarize_clean_payload(tmp_payload),
            "before_structured_temp_artifacts": before_structured_temps,
            "recovery": recovery,
        },
        "daily_structured_snapshot_audit": {
            "event_contract_audit": event_audit,
            "forward_observation_contract_audit": obs_audit,
            "artifact_write_audit": write_audit,
            "sample_event_rows": event_rows[:8],
            "sample_observation_rows": observation_rows[:8],
        },
        "production_impact": {
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_exposed": accepted,
            "shared_policy_changed": False,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "llm_prompt_changed": False,
            "news_archives_changed": True,
            "live_ready": False,
            "parity_note": (
                "This runner restores a missing finalized daily news input from a "
                "valid atomic temp and writes separate read-only observer artifacts. "
                "It is not attached to prompts, quant_signals, orders, ranking, "
                "sizing, or exits."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": accepted,
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": [
                mode
                for mode in prediction.get("main_failure_modes") or []
                if mode in failed_reasons
                or (
                    mode == "structured_helper_still_zero_rows"
                    and (
                        "structured_helper_still_zero_rows" in failed_reasons
                        or "structured_observer_still_zero_rows" in failed_reasons
                    )
                )
            ],
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - (1.0 if accepted else 0.0))
                ** 2,
                6,
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The zero-row 2026-06-30 daily structured-news snapshot was caused "
                "by a missing finalized clean_trade_news input while a valid temp "
                "file sat in the same directory. Restoring the final input let the "
                "existing shared observer produce schema-complete PIT rows without "
                "touching trading behavior."
                if accepted
                else "The recovery path did not satisfy the fixed daily observer contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reopen this same date for another atomic-temp readiness "
                "audit after the final artifacts exist. Do not slice these new rows "
                "by relation, ticker, source, or response curve until there are "
                "closed forward outcomes."
            ),
            "new_evidence_required": (
                "Next alpha work requires closed cash/SPY/QQQ replacement-value "
                "outcomes for these and later daily structured observations, or a "
                "new PIT LLM event scorer that writes this same evidence schema."
            ),
        },
        "next_retry_requires": [
            "closed structured-news forward outcomes for 2026-06-30 or later rows",
            "additional daily observation rows from subsequent production days",
            "PIT LLM labels persisted with the same evidence-span schema",
        ],
        "changed_files": changed_files,
        "related_files": [
            "quant/daily_news_text_sanitation.py",
            "quant/daily_news_structured_events.py",
            "quant/daily_news_structured_event_snapshot.py",
            "quant/test_daily_news_structured_event_snapshot.py",
            "experiments/logs/exp-20260630-005.json",
            "experiments/logs/exp-20260630-006.json",
            "experiments/logs/exp-20260630-007.json",
            "experiments/logs/exp-20260630-019.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_daily_news_structured_event_snapshot.py quant\\test_daily_news_structured_events.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "event_artifact": repo_rel(STRUCTURED_EVENT_FINAL),
        "forward_observation_artifact": repo_rel(STRUCTURED_OBSERVATION_FINAL),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner, py_compile, pytest, and experiment audit only.",
        },
    }


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "lane",
        "owner",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "daily_input_recovery_audit",
        "daily_structured_snapshot_audit",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "artifact",
        "log",
        "event_artifact",
        "forward_observation_artifact",
        "anti_js",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: Mapping[str, Any]) -> str:
    delta = payload["delta_metrics"]
    gate4 = payload["gate4"]
    recovery = payload["daily_input_recovery_audit"]["recovery"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: daily news 2026-06-30 atomic temp recovery",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            "- Accepted alpha: no",
            "- Strategy behavior changed: no",
            f"- Clean recovery: `{recovery['recovery_status']}`",
            f"- Event rows after recovery: `{delta['after_event_rows']}`",
            f"- Observation rows after recovery: `{delta['after_observation_rows']}`",
            f"- Target relation-quality rows: `{delta['after_target_relation_quality_rows']}`",
            f"- Gate 4 failures: `{', '.join(gate4['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
        ]
    ) + "\n"


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        CLEAN_FINAL,
        STRUCTURED_EVENT_FINAL,
        STRUCTURED_OBSERVATION_FINAL,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: Mapping[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "event_artifact": repo_rel(STRUCTURED_EVENT_FINAL),
        "forward_observation_artifact": repo_rel(STRUCTURED_OBSERVATION_FINAL),
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "daily_input_recovery_audit": payload["daily_input_recovery_audit"],
            "daily_structured_snapshot_audit": payload["daily_structured_snapshot_audit"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "calibration": payload["calibration"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "event_artifact": repo_rel(STRUCTURED_EVENT_FINAL),
            "forward_observation_artifact": repo_rel(STRUCTURED_OBSERVATION_FINAL),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
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
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
