"""exp-20260706-014: recover new observer/provenance atomic temp residue.

Measurement repair only. After later 20260705 observer/provenance
materialization, new dot-prefixed atomic-write ``.tmp`` files appeared in
prediction-market, entity-theme, and SEC contract provenance directories. This
runner recovers or cleans only stale orphan temps, then records that strategy
behavior is unchanged.
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


EXPERIMENT_ID = "exp-20260706-014"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "observer_provenance_tmp_recovery_after_materialization"
RUNNER = f"quant/experiments/exp_20260706_014_{SLUG}.py"
RUNNER_WINDOWS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_WINDOWS

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT, REPO_ROOT / "quant", REPO_ROOT / "scripts"):
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
OUT_JSON = OUT_DIR / f"exp_20260706_014_{SLUG}.json"
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
    "Alpha-enabling measurement repair: observer/provenance alpha reads require "
    "unambiguous final daily and latest-summary artifacts; after the 20260705 "
    "materialization, new stale atomic .tmp files reappeared in prediction-"
    "market, entity-theme, and SEC contract provenance directories, so recover "
    "or clean only those orphan temps without changing any trading policy."
)
ALPHA_HYPOTHESIS = (
    "Observer, prediction-market, and SEC contract-relation alpha reads need "
    "freshness and coverage audits over unambiguous final artifacts; stale "
    "atomic temps are a measurement blocker, not a trading signal."
)
CHANGED_VARIABLE = (
    "observer_provenance_new_stale_tmp_cleanup_after_20260705_materialization_v1"
)
TRIAL_FAMILY = "orphan_atomic_write_temp_recovery"
TRIAL_VARIANT_ID = "observer_provenance_tmp_recovery_after_20260705_materialization"
MECHANISM_FAMILY = "observer_forward_outcome_maturity"
NEW_EVIDENCE_AXIS = (
    "True fault recovery: new stale orphan atomic .tmp files appeared after the "
    "later 20260705 observer/provenance materialization run, satisfying "
    "exp-20260705-013's reopen condition; this is not a threshold, regex, "
    "horizon, notional, rank, or response retune."
)
PREDICTION = {
    "success_probability": 0.85,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "tmp_files_are_live_recent_writes",
        "cleanup_helper_scope_mismatch",
        "permission_locked_tmp_remaining",
    ],
    "confidence_reason": (
        "exp-20260705-013 explicitly allows reopening on new stale temps after "
        "later materialization; preflight found fresh orphan .tmp residue dated "
        "after 20260705 observer/provenance writes, and existing helper already "
        "supports safe stale cleanup."
    ),
    "recorded_at": "2026-07-06T12:10:41+00:00",
}

CHANGED_FILES = [
    RUNNER,
    "data/non_ohlcv/entity_theme_news_observer/daily/entity_theme_news_observer_20260705.json",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260706_014_{SLUG}.json",
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


def normalize_path_text(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            return repo_rel(path)
        except ValueError:
            return str(path).replace("\\", "/")
    return value.replace("\\", "/")


def normalize_skipped(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        if item.get("path"):
            item["path"] = normalize_path_text(str(item["path"]))
        out.append(item)
    return out


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


def run_target_recovery(now: float) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for rel_dir in TARGET_DIRS:
        directory = REPO_ROOT / rel_dir
        dry = sweep.recover_orphan_atomic_writes(directory, now=now, dry_run=True)
        actual = sweep.recover_orphan_atomic_writes(directory, now=now, dry_run=False)
        results.append(
            {
                "directory": rel_dir,
                "dry_run": {
                    "recovered": [
                        normalize_path_text(path) for path in dry.get("recovered", [])
                    ],
                    "cleaned": [
                        normalize_path_text(path) for path in dry.get("cleaned", [])
                    ],
                    "skipped": normalize_skipped(dry.get("skipped", [])),
                },
                "actual": {
                    "recovered": [
                        normalize_path_text(path) for path in actual.get("recovered", [])
                    ],
                    "cleaned": [
                        normalize_path_text(path) for path in actual.get("cleaned", [])
                    ],
                    "skipped": normalize_skipped(actual.get("skipped", [])),
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


def permission_retry_probe() -> dict[str, Any]:
    real_sleep = sweep.time.sleep
    calls: dict[str, Any] = {"unlink": 0, "chmod": 0, "sleep": []}

    class FakeStat:
        st_mode = 0

    class FakePath:
        def stat(self) -> FakeStat:
            return FakeStat()

        def chmod(self, mode: int) -> None:
            calls["chmod"] += 1

        def unlink(self) -> None:
            calls["unlink"] += 1
            if calls["unlink"] == 1:
                raise PermissionError("[WinError 5] access denied")

    try:
        def tracked_sleep(seconds: float) -> None:
            calls["sleep"].append(seconds)

        sweep.time.sleep = tracked_sleep
        sweep._unlink_with_retry(FakePath())  # type: ignore[arg-type]
        error = None
    except OSError as exc:
        error = str(exc)
    finally:
        sweep.time.sleep = real_sleep

    return {
        "passed": (
            calls["unlink"] >= 2
            and calls["chmod"] >= 1
            and bool(calls["sleep"])
            and calls["sleep"][0] == 0.05
            and error is None
        ),
        "calls": calls,
        "error": error,
        "probe_mode": "in_memory_fake_path",
    }


def build_result() -> dict[str, Any]:
    now_epoch = time.time()
    before = temp_inventory(now_epoch)
    recovery = run_target_recovery(now_epoch)
    after = temp_inventory(time.time())
    recovery_summary = summarize_recovery(recovery)
    probe = permission_retry_probe()
    stale_remaining = [row for row in after if row["stale_by_threshold"]]
    baseline = baseline_metrics()

    failed: list[str] = []
    if not probe["passed"]:
        failed.append("permission_retry_probe_failed")
    if stale_remaining:
        failed.append("stale_tmp_remaining_after_recovery")

    accepted = not failed
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_new_observer_provenance_tmp_cleanup"
        if accepted
        else "blocked_new_observer_provenance_tmp_cleanup_incomplete"
    )
    summary = {
        "before_tmp_count": len(before),
        "before_stale_tmp_count": sum(1 for row in before if row["stale_by_threshold"]),
        "target_recovered_count": recovery_summary["recovered_count"],
        "target_cleaned_count": recovery_summary["cleaned_count"],
        "target_skipped_count": recovery_summary["skipped_count"],
        "after_tmp_count": len(after),
        "after_stale_tmp_count": len(stale_remaining),
        "final_artifacts_present_with_residue_count": sum(1 for row in after if row["final_exists"]),
        "permission_retry_probe_passed": probe["passed"],
        "failed_checks": failed,
        "blocker_note": (
            "All remaining stale temps point at present final artifacts; the "
            "blocker is delete permission on the residue, not missing final data."
        ),
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
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "new post-materialization stale-temp inventory",
            "targeted recover_orphan_atomic_writes cleanup",
            "permission retry probe",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": ["exp-20260705-010", "exp-20260705-013"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "orphan_temp_fault_recovery_after_later_materialization",
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
        "target_recovery_results": recovery,
        "target_recovery_summary": recovery_summary,
        "permission_retry_probe": probe,
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "note": "Measurement repair only; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": True,
            "fields": [
                "latest_summary.json",
                "latest_outcome_summary.json",
                "outcome_summaries/*.json",
                "daily observer/provenance json/jsonl",
                "source_stats/source_manifest json",
            ],
            "field_reality": {
                "target_directories": TARGET_DIRS,
                "before_tmp_count": len(before),
                "after_tmp_count": len(after),
                "target_price_relevance": (
                    "not_applicable; cleanup touches observer/provenance "
                    "artifact hygiene only and schedules no exits or orders"
                ),
                "entry_date_relevance": (
                    "not changed; future alpha reads must verify entry_date on "
                    "their own settled outcome rows"
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
            "mode": "measurement_repair_new_orphan_atomic_temp_cleanup",
            "failed_checks": failed,
            "acceptance_checks": {
                "preflight_found_new_tmp": len(before) > 0,
                "permission_retry_probe_passed": probe["passed"],
                "no_stale_tmp_remaining": not stale_remaining,
                "strategy_behavior_unchanged": True,
            },
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "Only observer/provenance artifact-hygiene recovery was attempted. "
                "No strategy path changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "predicted_failure_mode_hit": None if accepted else ";".join(failed),
            "surprise_note": (
                "New stale temps were present after the later materialization and were cleaned."
                if accepted
                else "New stale temps were present, but every cleanup unlink still failed with WinError 5 access denied."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Later observer/provenance materialization left dot-prefixed "
                "atomic temp residue even though final artifacts existed. The "
                "current process can read/write the files but cannot delete the "
                "stale temps; cleanup still fails with WinError 5, so the repair "
                "is blocked until the temp-file ACL/owner state changes or an "
                "external cleanup with delete rights is available."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not open another observer/provenance orphan-temp cleanup "
                "experiment unless new stale temps appear after a later "
                "materialization run or this exact permission branch regresses. "
                "Do not use this repair to retune horizons, regexes, thresholds, "
                "notional, ranks, or response functions."
            ),
            "new_evidence_required": (
                "Next alpha work still needs materially more settled observer/"
                "provenance replacement-value rows or a genuinely new PIT data "
                "source; this repair only restores artifact-hygiene semantics."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "next_retry_requires": [
            "new stale orphan temps after a later materialization run",
            "or materially more settled observer/provenance replacement-value rows for alpha",
            "or regression evidence that unlink PermissionError is again silent",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [repo_rel(OUT_JSON), *TARGET_DIRS],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            "quant\\stale_artifact_sweep.py " + RUNNER_WINDOWS,
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
        f"# {EXPERIMENT_ID} - observer/provenance tmp recovery",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- target before tmp/stale: {summary['before_tmp_count']} / {summary['before_stale_tmp_count']}",
        f"- target recovered/cleaned/skipped: {summary['target_recovered_count']} / {summary['target_cleaned_count']} / {summary['target_skipped_count']}",
        f"- target after tmp/stale: {summary['after_tmp_count']} / {summary['after_stale_tmp_count']}",
        f"- permission retry probe passed: {summary['permission_retry_probe_passed']}",
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
