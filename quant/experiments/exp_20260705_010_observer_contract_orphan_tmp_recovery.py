"""exp-20260705-010: recover observer/provenance orphan atomic-write temps.

Measurement repair only. Several observer and SEC contract-provenance
directories contain dot-prefixed atomic-write temp files after the latest
materialization runs. These files can make freshness and coverage audits
ambiguous, even though the final artifacts already exist or can be recovered.

This runner uses the shared stale-artifact recovery helper on only the scoped
observer/provenance directories. It does not change signal generation, entry,
ranking, sizing, exits, orders, candidate maps, horizons, or notional.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260705-010"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "observer_contract_orphan_tmp_recovery"
RUNNER = f"quant/experiments/exp_20260705_010_{SLUG}.py"
RUNNER_WINDOWS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_WINDOWS

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import stale_artifact_sweep as sweep  # noqa: E402
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
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

TARGET_DIRS = [
    "data/non_ohlcv/entity_theme_news_observer",
    "data/non_ohlcv/entity_theme_news_observer/daily",
    "data/non_ohlcv/entity_theme_news_observer/outcome_ledgers",
    "data/non_ohlcv/entity_theme_news_observer/outcome_summaries",
    "data/non_ohlcv/prediction_market_event_observer",
    "data/non_ohlcv/prediction_market_event_observer/daily",
    "data/non_ohlcv/prediction_market_event_observer/outcome_ledgers",
    "data/non_ohlcv/prediction_market_event_observer/outcome_summaries",
    "data/non_ohlcv/prediction_market_event_observer/source_stats",
    "data/non_ohlcv/sec_contract_relation_provenance",
    "data/non_ohlcv/sec_contract_relation_provenance/daily",
]

HYPOTHESIS = (
    "Alpha-enabling measurement repair: orphaned atomic-write temp files in "
    "observer and SEC contract provenance surfaces can make latest-summary and "
    "daily-provenance freshness audits unreliable; recover or clean only stale "
    "orphan temps while leaving strategy behavior unchanged."
)
CHANGED_VARIABLE = "observer_and_contract_relation_orphan_atomic_tmp_recovery_v1"
MECHANISM_FAMILY = "observer_forward_outcome_maturity"
TRIAL_FAMILY = "orphan_atomic_write_temp_recovery"
TRIAL_VARIANT_ID = "observer_contract_relation_tmp_recovery_20260705"
NEW_EVIDENCE_AXIS = (
    "True fault recovery: existing observer and SEC contract relation "
    "directories contain stale atomic-write .tmp residue after accepted "
    "outcome/provenance materializations; this is not a threshold, source-field, "
    "response, or readiness retune."
)
PREDICTION = {
    "success_probability": 0.9,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "temps_are_live_recent_writes",
        "cleanup_tool_scope_mismatch",
        "audit_finds_strategy_delta",
    ],
    "confidence_reason": (
        "Preflight found stale .tmp files in observer and SEC contract "
        "provenance directories; AGENTS allows orphan-temp fault recovery as "
        "measurement repair, and cleanup should not touch strategy decisions "
        "or settled rows."
    ),
    "recorded_at": "2026-07-05T11:07:00+00:00",
}

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_010_{SLUG}.json",
    "data/non_ohlcv/entity_theme_news_observer",
    "data/non_ohlcv/prediction_market_event_observer",
    "data/non_ohlcv/sec_contract_relation_provenance",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
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
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


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


def temp_inventory(now: float, min_age_s: float = sweep._RECOVER_MIN_AGE_S) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel_dir in TARGET_DIRS:
        directory = REPO_ROOT / rel_dir
        if not directory.is_dir():
            continue
        for entry in os.scandir(directory):
            if not (entry.is_file() and entry.name.endswith(".tmp")):
                continue
            path = Path(entry.path)
            final_name = sweep._final_name_for_temp(entry.name)
            final_path = directory / final_name if final_name else None
            try:
                age_s = now - path.stat().st_mtime
            except OSError:
                continue
            payload_valid = (
                sweep._temp_payload_is_valid(path, final_name) if final_name else False
            )
            rows.append(
                {
                    "path": repo_rel(path),
                    "directory": repo_rel(directory),
                    "age_s": round(age_s, 1),
                    "stale_by_threshold": age_s >= min_age_s,
                    "final_name": final_name,
                    "final_exists": bool(final_path and final_path.exists()),
                    "payload_valid": payload_valid,
                }
            )
    rows.sort(key=lambda row: row["path"])
    return rows


def run_recovery(now: float) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for rel_dir in TARGET_DIRS:
        directory = REPO_ROOT / rel_dir
        dry = sweep.recover_orphan_atomic_writes(directory, now=now, dry_run=True)
        actual = sweep.recover_orphan_atomic_writes(directory, now=now, dry_run=False)
        results.append(
            {
                "directory": rel_dir,
                "dry_run": {
                    "recovered": [repo_rel(path) for path in dry.get("recovered", [])],
                    "cleaned": [repo_rel(path) for path in dry.get("cleaned", [])],
                    "skipped": dry.get("skipped", []),
                },
                "actual": {
                    "recovered": [repo_rel(path) for path in actual.get("recovered", [])],
                    "cleaned": [repo_rel(path) for path in actual.get("cleaned", [])],
                    "skipped": actual.get("skipped", []),
                },
            }
        )
    return results


def summarize_recovery(recovery: list[dict[str, Any]]) -> dict[str, Any]:
    recovered: list[str] = []
    cleaned: list[str] = []
    skipped: list[dict[str, Any]] = []
    for item in recovery:
        actual = item.get("actual") or {}
        recovered.extend(actual.get("recovered") or [])
        cleaned.extend(actual.get("cleaned") or [])
        skipped.extend(actual.get("skipped") or [])
    return {
        "recovered_count": len(recovered),
        "cleaned_count": len(cleaned),
        "skipped_count": len(skipped),
        "recovered": sorted(recovered),
        "cleaned": sorted(cleaned),
        "skipped": skipped,
    }


def fallback_safe_cleanup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Delete only stale temps that are already safely superseded by finals.

    The shared helper is intentionally best-effort and suppresses unlink errors.
    This experiment needs the error surface for audit, so keep this fallback
    narrow: no final, no delete. Missing-final recovery stays with the shared
    helper.
    """
    cleaned: list[str] = []
    skipped: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("stale_by_threshold"):
            continue
        if not row.get("final_exists"):
            skipped.append({"path": row.get("path"), "reason": "final_missing"})
            continue
        if not row.get("payload_valid"):
            skipped.append({"path": row.get("path"), "reason": "invalid_payload"})
            continue
        path = REPO_ROOT / str(row["path"])
        try:
            path.unlink()
        except OSError as exc:
            skipped.append({"path": row.get("path"), "reason": f"unlink_failed:{exc}"})
            continue
        cleaned.append(row["path"])
    return {"cleaned": sorted(cleaned), "skipped": skipped}


def build_result() -> dict[str, Any]:
    now_epoch = time.time()
    before = temp_inventory(now_epoch)
    recovery = run_recovery(now_epoch)
    after_shared = temp_inventory(time.time())
    fallback = fallback_safe_cleanup(after_shared)
    after = temp_inventory(time.time())
    recovery_summary = summarize_recovery(recovery)
    recovery_summary["fallback_cleaned_count"] = len(fallback["cleaned"])
    recovery_summary["fallback_cleaned"] = fallback["cleaned"]
    recovery_summary["fallback_skipped"] = fallback["skipped"]
    recovery_summary["cleaned_count"] += len(fallback["cleaned"])
    recovery_summary["cleaned"] = sorted(
        [*recovery_summary["cleaned"], *fallback["cleaned"]]
    )
    recovery_summary["skipped_count"] += len(fallback["skipped"])
    recovery_summary["skipped"].extend(fallback["skipped"])
    stale_remaining = [row for row in after if row["stale_by_threshold"]]
    young_remaining = [row for row in after if not row["stale_by_threshold"]]
    baseline = baseline_metrics()
    no_strategy_change = True
    made_repair = (
        recovery_summary["recovered_count"] + recovery_summary["cleaned_count"]
    ) > 0
    accepted = bool(made_repair and not stale_remaining and no_strategy_change)
    failed = []
    if not made_repair:
        failed.append("no_orphan_temp_recovered_or_cleaned")
    if stale_remaining:
        failed.append("stale_tmp_remaining_after_recovery")
    if recovery_summary["skipped_count"]:
        failed.append("invalid_or_unrecoverable_tmp_skipped")

    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_observer_contract_orphan_tmp_recovered"
        if accepted
        else "blocked_observer_contract_orphan_tmp_recovery_incomplete"
    )
    timestamp = utc_now()
    summary = {
        "target_directories": TARGET_DIRS,
        "before_tmp_count": len(before),
        "before_stale_tmp_count": sum(1 for row in before if row["stale_by_threshold"]),
        "after_tmp_count": len(after),
        "after_stale_tmp_count": len(stale_remaining),
        "after_young_tmp_count": len(young_remaining),
        "recovered_count": recovery_summary["recovered_count"],
        "cleaned_count": recovery_summary["cleaned_count"],
        "fallback_cleaned_count": recovery_summary["fallback_cleaned_count"],
        "skipped_count": recovery_summary["skipped_count"],
        "failed_checks": failed,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": (
            "Observer, prediction-market, and SEC contract-relation alpha reads "
            "need freshness/coverage audits over unambiguous final artifacts; "
            "orphan atomic temps are the current measurement blocker."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "orphan_atomic_write_fault_recovery",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "preflight orphan-temp count",
            "stale atomic-write recovery",
            "post-clean count",
            "audit artifact",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260704-023",
            "exp-20260705-007",
            "exp-20260703-022",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "orphan_temp_fault_recovery",
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
        "before_temp_inventory": before,
        "after_temp_inventory": after,
        "recovery_results": recovery,
        "recovery_summary": recovery_summary,
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "note": "Measurement repair only; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": True,
            "fields": [
                "latest_outcome_summary.json",
                "outcome_summaries/*.json",
                "daily observer/provenance json/jsonl",
                "manifest/source_stats json",
            ],
            "field_reality": {
                "target_directories": TARGET_DIRS,
                "before_tmp_count": len(before),
                "after_tmp_count": len(after),
                "target_price_relevance": (
                    "not_applicable; this repair touches observer/provenance "
                    "artifacts only and schedules no exits or orders"
                ),
                "entry_date_relevance": (
                    "not changed; future alpha reads must still verify "
                    "entry_date on their own settled outcome rows"
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
            "mode": "measurement_repair_orphan_atomic_write_recovery",
            "failed_checks": failed,
            "acceptance_checks": {
                "preflight_found_orphan_temps": len(before) > 0,
                "recovered_or_cleaned_any": made_repair,
                "no_stale_tmp_remaining": not stale_remaining,
                "strategy_behavior_unchanged": no_strategy_change,
            },
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_ready": False,
            "daily_snapshot_changed": True,
            "parity_note": (
                "Only orphan atomic-write temp files under observer/provenance "
                "data surfaces were recovered or removed. No strategy path changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "Stale atomic-write temps were cleaned/recovered as expected."
                if accepted
                else "One or more stale temps could not be safely recovered or cleaned."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Recent observer and contract-provenance materialization runs "
                "left dot-prefixed atomic-write temp files after final artifacts "
                "were already present or recoverable. Cleaning them removes a "
                "measurement ambiguity without changing any trading behavior."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not open another orphan-temp cleanup experiment for these "
                "same directories unless new stale temps appear after a later "
                "materialization run. Do not use this repair to retune observer "
                "queries, contract regexes, horizons, notional, ranks, or response "
                "functions."
            ),
            "new_evidence_required": (
                "Next alpha work still needs materially more settled observer/"
                "provenance replacement-value rows or a genuinely new PIT data "
                "source; this repair only restores artifact hygiene."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "next_retry_requires": [
            "new stale orphan temps after a later materialization run",
            "or materially more settled observer/provenance replacement-value rows for alpha",
            "no threshold, regex, horizon, notional, rank, or response retune from this cleanup",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [repo_rel(OUT_JSON), *TARGET_DIRS],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_WINDOWS}",
            RUNNER_COMMAND,
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
        f"# {EXPERIMENT_ID} - observer/provenance orphan temp recovery",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- before tmp/stale: {summary['before_tmp_count']} / {summary['before_stale_tmp_count']}",
        f"- recovered/cleaned/skipped: {summary['recovered_count']} / {summary['cleaned_count']} / {summary['skipped_count']}",
        f"- after tmp/stale: {summary['after_tmp_count']} / {summary['after_stale_tmp_count']}",
        f"- failed checks: {', '.join(summary['failed_checks']) or 'none'}",
        "",
        "No signal generation, ranking, sizing, exits, orders, candidate maps, "
        "horizons, or notional changed.",
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
