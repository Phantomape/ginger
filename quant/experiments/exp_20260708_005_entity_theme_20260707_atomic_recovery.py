"""exp-20260708-005: recover the 20260707 entity/theme observer daily file.

Measurement repair only. The 20260707 outcome ledger exists, but it was built
from daily observer files through 20260706 because the 20260707 daily item
artifact was left as a valid atomic-write temp without a final file. This
runner promotes only that missing daily item file, records a recovered daily
summary, and refreshes the existing outcome ledger with the restored input.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260708-005"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "entity_theme_20260707_atomic_recovery"
DATE_TAG = "20260707"
DATE_ISO = "2026-07-07"
RUNNER = f"quant/experiments/exp_20260708_005_{SLUG}.py"
RUNNER_WINDOWS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_WINDOWS

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT, REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import stale_artifact_sweep as sweep  # noqa: E402
from entity_theme_news_observer import (  # noqa: E402
    persist_entity_theme_news_outcome_ledger,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OBSERVER_ROOT = REPO_ROOT / "data" / "non_ohlcv" / "entity_theme_news_observer"
DAILY_DIR = OBSERVER_ROOT / "daily"
FINAL_DAILY = DAILY_DIR / f"entity_theme_news_observer_{DATE_TAG}.json"
TEMP_GLOB = f".entity_theme_news_observer_{DATE_TAG}.json.*.tmp"
LATEST_SUMMARY = OBSERVER_ROOT / "latest_summary.json"
LATEST_OUTCOME_SUMMARY = OBSERVER_ROOT / "latest_outcome_summary.json"
OUTCOME_SUMMARY = (
    OBSERVER_ROOT
    / "outcome_summaries"
    / f"entity_theme_news_observer_outcome_summary_{DATE_TAG}.json"
)
OUTCOME_LEDGER = (
    OBSERVER_ROOT
    / "outcome_ledgers"
    / f"entity_theme_news_observer_outcomes_{DATE_TAG}.jsonl"
)
SOURCE_MANIFEST = OBSERVER_ROOT / "source_manifest.json"
SOURCE_STATS = (
    OBSERVER_ROOT
    / "source_stats"
    / f"entity_theme_news_observer_source_stats_{DATE_TAG}.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Entity/theme observer 2026-07-07 daily final is missing while a same-date "
    "atomic temp and outcome files exist, causing the latest daily summary to "
    "remain stuck on 2026-07-06 and excluding one forward-row collection day "
    "from the observer contract."
)
ALPHA_HYPOTHESIS = (
    "Forward entity/theme news rows can only become usable alpha evidence after "
    "daily observer files and outcome ledgers agree on the same collected dates; "
    "this run repairs one missing observer file, not a trading policy."
)
CHANGED_VARIABLE = "entity_theme_news_observer_20260707_atomic_recovery_v1"
MECHANISM_FAMILY = "observer_forward_row_collection_repair"
TRIAL_FAMILY = "entity_theme_news_observer_atomic_recovery"
TRIAL_VARIANT_ID = "entity_theme_news_observer_20260707_daily_temp_recovery_v1"
NEARBY_PRIORS = [
    "exp-20260703-001",
    "exp-20260705-006",
    "exp-20260705-007",
    "exp-20260706-014",
    "exp-20260707-013",
]
NEW_EVIDENCE_AXIS = (
    "Fault recovery: current 2026-07-07 entity_theme observer daily final is "
    "absent while a same-date atomic temp exists; this is not a source/theme/"
    "threshold reslice and directly blocks forward-row collection for that "
    "observer date."
)
PREDICTION = {
    "success_probability": 0.75,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "temp_invalid_json",
        "temp_not_same_contract",
        "summary_refresh_missing",
        "outcome_refresh_no_delta",
    ],
    "confidence_reason": (
        "A same-date temp exists with plausible size and outcome files exist, "
        "while the final daily observer file is missing and latest_summary still "
        "reports 20260706."
    ),
    "recorded_at": "2026-07-08T04:16:06+00:00",
}

CHANGED_FILES = [
    RUNNER,
    f"data/non_ohlcv/entity_theme_news_observer/daily/entity_theme_news_observer_{DATE_TAG}.json",
    "data/non_ohlcv/entity_theme_news_observer/latest_summary.json",
    "data/non_ohlcv/entity_theme_news_observer/latest_outcome_summary.json",
    f"data/non_ohlcv/entity_theme_news_observer/outcome_summaries/entity_theme_news_observer_outcome_summary_{DATE_TAG}.json",
    f"data/non_ohlcv/entity_theme_news_observer/outcome_ledgers/entity_theme_news_observer_outcomes_{DATE_TAG}.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260708_005_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


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


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {})
    raw_windows = payload.get("windows") or payload.get("window_results") or []
    windows = list(raw_windows.values()) if isinstance(raw_windows, dict) else list(raw_windows)
    generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    drawdowns = [
        float(w.get("max_drawdown_pct"))
        for w in windows
        if w.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "loaded": BASELINE_PATH.exists(),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "window_count": len(windows),
    }


def observer_file_state() -> dict[str, Any]:
    temps = sorted(DAILY_DIR.glob(TEMP_GLOB), key=lambda path: path.name)
    latest = read_json(LATEST_SUMMARY, {})
    outcome = read_json(OUTCOME_SUMMARY, {})
    return {
        "final_exists": FINAL_DAILY.exists(),
        "final_path": repo_rel(FINAL_DAILY),
        "final_sha256": sha256(FINAL_DAILY) if FINAL_DAILY.exists() else None,
        "temp_count": len(temps),
        "temps": [
            {
                "path": repo_rel(path),
                "length": path.stat().st_size if path.exists() else None,
                "sha256": sha256(path),
            }
            for path in temps
        ],
        "latest_summary_date": latest.get("date"),
        "latest_summary_status": latest.get("status"),
        "latest_summary_unique_item_count": latest.get("unique_item_count"),
        "latest_summary_source_stats_exists": SOURCE_STATS.exists(),
        "outcome_daily_item_file_count": outcome.get("daily_item_file_count"),
        "outcome_source_item_count": outcome.get("source_item_count"),
        "outcome_candidate_rows": outcome.get("candidate_outcome_row_count"),
        "outcome_settled_count": outcome.get("settled_count"),
        "outcome_unsettled_count": outcome.get("unsettled_count"),
    }


def validate_temp(path: Path) -> tuple[bool, list[dict[str, Any]], dict[str, Any]]:
    final_name = sweep._final_name_for_temp(path.name)
    valid_payload = bool(final_name) and sweep._temp_payload_is_valid(path, final_name)
    if not valid_payload:
        return False, [], {"reason": "invalid_or_partial_payload", "final_name": final_name}
    payload = read_json(path, [])
    if not isinstance(payload, list) or not payload:
        return False, [], {"reason": "payload_not_nonempty_list", "final_name": final_name}
    bad_rows = [
        idx
        for idx, item in enumerate(payload[:50])
        if not isinstance(item, dict)
        or item.get("observer_name") != "entity_theme_news_observer"
        or item.get("observer_only") is not True
    ]
    source_ids = sorted(
        {
            str(item.get("entity_theme_query_id"))
            for item in payload
            if isinstance(item, dict) and item.get("entity_theme_query_id")
        }
    )
    validation = {
        "final_name": final_name,
        "item_count": len(payload),
        "sampled_bad_row_indexes": bad_rows,
        "source_id_count": len(source_ids),
        "source_ids": source_ids,
        "sha256": sha256(path),
    }
    return not bad_rows and final_name == FINAL_DAILY.name, payload, validation


def recover_daily_final() -> dict[str, Any]:
    temps = sorted(DAILY_DIR.glob(TEMP_GLOB), key=lambda path: path.name)
    if FINAL_DAILY.exists():
        payload = read_json(FINAL_DAILY, [])
        return {
            "action": "already_present",
            "recovered": False,
            "valid_temp": False,
            "item_count": len(payload) if isinstance(payload, list) else None,
            "selected_temp": None,
            "error": None,
        }
    if len(temps) != 1:
        return {
            "action": "blocked",
            "recovered": False,
            "valid_temp": False,
            "item_count": None,
            "selected_temp": None,
            "error": f"expected_one_temp_found_{len(temps)}",
        }

    temp = temps[0]
    valid, items, validation = validate_temp(temp)
    if not valid:
        return {
            "action": "blocked",
            "recovered": False,
            "valid_temp": False,
            "item_count": len(items),
            "selected_temp": repo_rel(temp),
            "validation": validation,
            "error": "temp_validation_failed",
        }

    before_hash = sha256(temp)
    try:
        sweep._promote_with_retry(temp, FINAL_DAILY)
    except OSError as exc:
        return {
            "action": "blocked",
            "recovered": False,
            "valid_temp": True,
            "item_count": len(items),
            "selected_temp": repo_rel(temp),
            "validation": validation,
            "error": f"promote_failed:{exc}",
        }
    after_hash = sha256(FINAL_DAILY)
    return {
        "action": "promoted_temp_to_final",
        "recovered": FINAL_DAILY.exists() and after_hash == before_hash,
        "valid_temp": True,
        "item_count": len(items),
        "selected_temp": repo_rel(temp),
        "final_path": repo_rel(FINAL_DAILY),
        "validation": validation,
        "sha256_before": before_hash,
        "sha256_after": after_hash,
        "error": None,
    }


def write_recovered_latest_summary(item_count: int) -> dict[str, Any]:
    manifest = read_json(SOURCE_MANIFEST, {})
    sources = manifest.get("sources") if isinstance(manifest, dict) else []
    summary = {
        "schema_version": 1,
        "observer_name": "entity_theme_news_observer",
        "status": "recovered_from_atomic_temp",
        "date": DATE_TAG,
        "source_count": len(sources) if isinstance(sources, list) else None,
        "source_error_count": None,
        "raw_item_count": item_count,
        "unique_item_count": item_count,
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "items_path": str(FINAL_DAILY),
        "source_stats_path": str(SOURCE_STATS),
        "source_stats_exists": SOURCE_STATS.exists(),
        "source_manifest_path": str(SOURCE_MANIFEST),
        "recovery_experiment_id": EXPERIMENT_ID,
        "recovery_note": (
            "Daily item final was restored from a valid atomic temp. Same-date "
            "source_stats were not present, so source_error_count is left null."
        ),
    }
    write_json(LATEST_SUMMARY, summary)
    return summary


def refresh_outcome() -> tuple[dict[str, Any], str | None]:
    try:
        return persist_entity_theme_news_outcome_ledger(DATE_TAG), None
    except Exception as exc:  # pragma: no cover - artifact safety path
        return {"status": "error", "error": str(exc)}, str(exc)


def build_result() -> dict[str, Any]:
    before_state = observer_file_state()
    before_latest = read_json(LATEST_SUMMARY, {})
    before_outcome = read_json(OUTCOME_SUMMARY, {})
    recovery = recover_daily_final()

    recovered_summary = {}
    if FINAL_DAILY.exists() and recovery.get("item_count"):
        recovered_summary = write_recovered_latest_summary(int(recovery["item_count"]))

    after_outcome, outcome_error = refresh_outcome() if FINAL_DAILY.exists() else ({}, "daily_final_missing")
    after_state = observer_file_state()
    baseline = baseline_metrics()

    daily_files = after_outcome.get("daily_item_files") if isinstance(after_outcome, dict) else []
    daily_file_dates = [
        item.get("date")
        for item in daily_files
        if isinstance(item, dict) and item.get("date")
    ]
    expected_count = (before_outcome.get("daily_item_file_count") or 0) + (
        0 if before_state["final_exists"] else 1
    )
    no_strategy_change = (
        recovered_summary.get("trade_enabled") is False
        and recovered_summary.get("strategy_behavior_changed") is False
        and after_outcome.get("trade_enabled") is False
        and after_outcome.get("strategy_behavior_changed") is False
    )

    failed: list[str] = []
    if not recovery.get("recovered") and recovery.get("action") != "already_present":
        failed.append("daily_final_not_recovered")
    if not FINAL_DAILY.exists():
        failed.append("daily_final_missing_after_recovery")
    if recovered_summary.get("date") != DATE_TAG:
        failed.append("latest_summary_not_recovered_date")
    if outcome_error:
        failed.append("outcome_refresh_failed")
    if DATE_ISO not in daily_file_dates:
        failed.append("outcome_missing_20260707_daily_file")
    if after_outcome.get("daily_item_file_count") != expected_count:
        failed.append("outcome_daily_file_count_not_incremented")
    if (after_outcome.get("source_item_count") or 0) <= (
        before_outcome.get("source_item_count") or 0
    ):
        failed.append("outcome_source_items_not_increased")
    if not no_strategy_change:
        failed.append("strategy_or_trade_flag_changed")

    accepted = not failed
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_entity_theme_20260707_daily_recovered"
        if accepted
        else "blocked_entity_theme_20260707_daily_recovery_incomplete"
    )
    summary = {
        "before_final_exists": before_state["final_exists"],
        "before_temp_count": before_state["temp_count"],
        "recovered": recovery.get("recovered"),
        "recovery_action": recovery.get("action"),
        "recovered_item_count": recovery.get("item_count"),
        "after_final_exists": after_state["final_exists"],
        "latest_summary_date_before": before_latest.get("date"),
        "latest_summary_date_after": recovered_summary.get("date"),
        "latest_summary_status_after": recovered_summary.get("status"),
        "outcome_daily_item_file_count_before": before_outcome.get(
            "daily_item_file_count"
        ),
        "outcome_daily_item_file_count_after": after_outcome.get(
            "daily_item_file_count"
        ),
        "outcome_source_item_count_before": before_outcome.get("source_item_count"),
        "outcome_source_item_count_after": after_outcome.get("source_item_count"),
        "outcome_candidate_rows_before": before_outcome.get(
            "candidate_outcome_row_count"
        ),
        "outcome_candidate_rows_after": after_outcome.get("candidate_outcome_row_count"),
        "outcome_settled_count_before": before_outcome.get("settled_count"),
        "outcome_settled_count_after": after_outcome.get("settled_count"),
        "failed_checks": failed,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "lane": LANE,
        "change_type": "observer_forward_row_fault_recovery",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "validate exact 20260707 entity-theme observer temp",
            "promote temp to missing daily final",
            "write recovered latest daily summary",
            "refresh same-date outcome ledger through restored daily file",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "fault_recovery_missing_current_daily_observer_final",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "summary": summary,
        "before_state": before_state,
        "after_state": after_state,
        "recovery": recovery,
        "recovered_latest_summary": recovered_summary,
        "before_outcome_summary": before_outcome,
        "after_outcome_summary": after_outcome,
        "gate1": {
            "passed": True,
            "baseline_artifacts": {
                "latest_summary": repo_rel(LATEST_SUMMARY),
                "outcome_summary": repo_rel(OUTCOME_SUMMARY),
                "canonical_strategy_baseline": baseline,
            },
            "note": "Measurement repair only; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": FINAL_DAILY.exists(),
            "fields": [
                "daily observer item final",
                "latest_summary.date",
                "daily_item_files",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "field_reality": {
                "final_daily_file": repo_rel(FINAL_DAILY),
                "final_daily_exists": FINAL_DAILY.exists(),
                "latest_summary": repo_rel(LATEST_SUMMARY),
                "source_stats_same_date_exists": SOURCE_STATS.exists(),
                "target_price_relevance": (
                    "not_applicable_observer_fixed_horizon; this ledger schedules "
                    "no orders or production exits"
                ),
                "entry_date_relevance": (
                    "outcome rows are observer attribution rows; future alpha "
                    "reads must verify entry/open rows on settled outcomes"
                ),
            },
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, rank, size, exit, or order policy changed.",
        },
        "gate4": {
            "passed": accepted,
            "mode": "measurement_repair_missing_daily_observer_atomic_recovery",
            "failed_checks": failed,
            "acceptance_checks": {
                "valid_temp_recovered": bool(recovery.get("recovered")),
                "latest_summary_updated_to_20260707": (
                    recovered_summary.get("date") == DATE_TAG
                ),
                "outcome_includes_20260707_daily_file": DATE_ISO in daily_file_dates,
                "outcome_source_items_increased": (
                    (after_outcome.get("source_item_count") or 0)
                    > (before_outcome.get("source_item_count") or 0)
                ),
                "strategy_and_trade_flags_unchanged": no_strategy_change,
            },
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "Restored an observer-only daily artifact and refreshed its "
                "observer outcome ledger. No production trading path changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "predicted_failure_mode_hit": None if accepted else ";".join(failed),
            "surprise_note": (
                "The same-date temp was valid and outcome rows increased after "
                "including the recovered daily file."
                if accepted
                else "Recovery did not fully restore daily/outcome consistency."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The observer daily item write left a valid temp but no final "
                "file, while downstream outcome materialization continued from "
                "the previous daily files. Promoting the exact same-date temp "
                "restored the missing collection day without touching any "
                "strategy policy."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not open another entity/theme source-bundle, theme, query, "
                "ticker, horizon, notional, rank, or response retry from this "
                "artifact repair. A future recovery ID needs a new missing-final "
                "fault or a shared helper fix; alpha work still needs legal new "
                "settled replacement-value evidence."
            ),
            "new_evidence_required": (
                "Next alpha-compliant entity/theme work needs at least +50% new "
                "settled cash/SPY/QQQ replacement-value rows versus the last "
                "13799-row probe, or a genuinely new PIT entity-relation source."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "next_retry_requires": [
            "new missing-final observer artifact fault",
            "or shared helper recovery wiring for non_ohlcv observer dirs",
            "or materially more settled entity/theme replacement-value rows for alpha",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [
            repo_rel(FINAL_DAILY),
            repo_rel(LATEST_SUMMARY),
            repo_rel(OUTCOME_SUMMARY),
            repo_rel(LATEST_OUTCOME_SUMMARY),
            repo_rel(OUT_JSON),
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_WINDOWS}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_entity_theme_news_observer.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": None,
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "decision",
        "hypothesis",
        "alpha_hypothesis",
        "lane",
        "change_type",
        "changed_variable",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# {EXPERIMENT_ID} - entity/theme 20260707 atomic recovery",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- daily final existed before/after: {summary['before_final_exists']} -> {summary['after_final_exists']}",
        f"- temp count before: {summary['before_temp_count']}",
        f"- recovered item count: {summary['recovered_item_count']}",
        f"- latest summary date/status: {summary['latest_summary_date_after']} / {summary['latest_summary_status_after']}",
        (
            "- outcome daily files/source items: "
            f"{summary['outcome_daily_item_file_count_before']} -> "
            f"{summary['outcome_daily_item_file_count_after']} / "
            f"{summary['outcome_source_item_count_before']} -> "
            f"{summary['outcome_source_item_count_after']}"
        ),
        f"- failed checks: {', '.join(summary['failed_checks']) or 'none'}",
        "",
        "No signal generation, ranking, sizing, exits, orders, source bundle, "
        "horizon, notional, or LLM decision boundary changed.",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "files": CHANGED_FILES,
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))

    ticket = read_json(TICKET_JSON, {})
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["summary"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "summary": payload["summary"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
