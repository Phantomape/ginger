"""exp-20260612-010: classify non-snapshot paper-sleeve health surfaces.

Measurement repair. ``sleeve_health`` used to mark any ``data/paper_sleeves/*``
directory without ``snapshots.jsonl`` as ``never_persisted``. That was correct
for dead snapshot-backed sleeves, but false for legacy/summary-only surfaces
such as ``platform_rs20_no_gap``, ``sec_10k_liquidity``, and the
``space_catalyst`` shadow ledger, all of which persist fresh summary files.

Reproduce:
    .venv/Scripts/python.exe -B quant/experiments/exp_20260612_010_sleeve_health_legacy_surface_classification.py
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from experiment_registry import persist_self_registered_result
from sleeve_health import RULE_VERSION, build_sleeve_health_report


EXPERIMENT_ID = "exp-20260612-010"
ASOF_DATE = "2026-06-11"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260612_010_sleeve_health_legacy_surface_classification.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
HEALTH_LOG = REPO_ROOT / "data" / "paper_sleeves" / "sleeve_health.jsonl"
DAILY_PAYLOAD = REPO_ROOT / "data" / "daily" / "signals" / "quant" / "quant_signals_20260611.json"


def _load_health_rows() -> list[dict]:
    rows: list[dict] = []
    if not HEALTH_LOG.exists():
        return rows
    for line in HEALTH_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("asof_date")) == ASOF_DATE:
            rows.append(row)
    return rows


def _latest_row(rows: list[dict], rule_version: str) -> dict | None:
    selected = [row for row in rows if row.get("rule_version") == rule_version]
    return selected[-1] if selected else None


def _append_jsonl(path: Path, record: dict) -> None:
    existing_ids = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing_ids.add(json.loads(line).get("experiment_id"))
            except json.JSONDecodeError:
                continue
    if record["experiment_id"] in existing_ids:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_health_rows()
    before = _latest_row(rows, "sleeve_health_report_v1") or {}
    after = _latest_row(rows, RULE_VERSION) or {}
    payload = json.loads(DAILY_PAYLOAD.read_text(encoding="utf-8"))
    recomputed = build_sleeve_health_report(ASOF_DATE, payload, persist=False)
    summary_surfaces = {
        key: recomputed["disk_status"].get(key)
        for key in ("platform_rs20_no_gap", "sec_10k_liquidity", "space_catalyst")
    }
    success = (
        RULE_VERSION == "sleeve_health_report_v2"
        and not recomputed.get("failing_builds")
        and not recomputed.get("stalled_sleeves")
        and all((value or {}).get("status") == "fresh_summary" for value in summary_surfaces.values())
    )
    decision = (
        "accepted_measurement_repair_sleeve_health_legacy_surface_classification"
        if success
        else "blocked_sleeve_health_legacy_surface_classification_incomplete"
    )
    prediction = (json.loads(TICKET_JSON.read_text(encoding="utf-8")).get("prediction") or {})
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted" if success else "blocked",
        "decision": decision,
        "asof_date": ASOF_DATE,
        "hypothesis": (
            "Legacy or non-standard paper-sleeve accumulation surfaces that "
            "persist fresh summary/shadow-ledger files should not be reported "
            "as stalled merely because they do not use snapshots.jsonl."
        ),
        "change_summary": (
            "sleeve_health_report_v2 reads summary.json and *_summary.json "
            "dates when snapshots.jsonl is absent, classifies fresh summaries "
            "as fresh_summary, preserves never_persisted for true dead dirs, "
            "and appends a v2 correction row for the 2026-06-11 health surface."
        ),
        "before_health": {
            "rule_version": before.get("rule_version"),
            "failing_builds": before.get("failing_builds") or [],
            "stalled_sleeves": before.get("stalled_sleeves") or [],
            "summary_surface_statuses": {
                key: (before.get("disk_status") or {}).get(key) for key in summary_surfaces
            },
        },
        "after_health": {
            "rule_version": after.get("rule_version"),
            "failing_builds": after.get("failing_builds") or [],
            "stalled_sleeves": after.get("stalled_sleeves") or [],
            "summary_surface_statuses": {
                key: (after.get("disk_status") or {}).get(key) for key in summary_surfaces
            },
        },
        "recomputed_health": {
            "rule_version": recomputed.get("rule_version"),
            "failing_builds": recomputed.get("failing_builds") or [],
            "stalled_sleeves": recomputed.get("stalled_sleeves") or [],
            "summary_surface_statuses": summary_surfaces,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "default_off_attribution_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "parity_note": (
                "Read-side health classification only. No sleeve state machine, "
                "candidate rule, order path, or backtest policy changed."
            ),
        },
        "tests": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sleeve_health.py"
        ],
        "accepted": success,
    }
    artifact["calibration"] = {
        "actual_decision": decision,
        "actual_success": 1 if success else 0,
        "predicted_success_probability": prediction.get("success_probability"),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_mode": None if success else "summary_surface_classification_incomplete",
        "surprise_note": (
            "The only remaining health failures were stale diagnostics from the "
            "v1 report and non-snapshot directories with fresh summary files."
        ),
    }
    artifact["post_run_reflection"] = {
        "why_result_happened": (
            "The health report assumed every paper-sleeve directory should be "
            "snapshot-backed, but several older observe-only surfaces are "
            "summary-backed by design. Reading summary dates preserves stale "
            "detection while avoiding false dead-sleeve alerts."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not silence health warnings globally; add explicit persistence "
            "shape recognition for any future non-snapshot surface."
        ),
        "new_evidence_required": (
            "A future non-snapshot surface without a dated summary file should "
            "add one rather than being excluded from health."
        ),
    }
    artifact["next_retry_requires"] = ["new non-snapshot surface without dated summary"]
    artifact["related_files"] = [
        "quant/sleeve_health.py",
        "quant/test_sleeve_health.py",
        "data/paper_sleeves/sleeve_health.jsonl",
        "quant/experiments/exp_20260612_010_sleeve_health_legacy_surface_classification.py",
    ]
    OUT_JSON.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")

    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": artifact["status"],
        "lane": "measurement_repair",
        "decision": decision,
        "hypothesis": artifact["hypothesis"],
        "change_summary": artifact["change_summary"],
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "data_accumulation_integrity",
        "trial_family": "sleeve_health_measurement_repair",
        "trial_variant_id": "sleeve_health_legacy_surface_classification_v1",
        "changed_variable": "sleeve_health_disk_status_summary_surface_classification",
        "causal_components": ["summary surface date reader", "v2 health row"],
        "before_metrics": {
            "failing_build_count": len(artifact["before_health"]["failing_builds"]),
            "stalled_sleeve_count": len(artifact["before_health"]["stalled_sleeves"]),
        },
        "after_metrics": {
            "failing_build_count": len(artifact["after_health"]["failing_builds"]),
            "stalled_sleeve_count": len(artifact["after_health"]["stalled_sleeves"]),
        },
        "delta_metrics": {
            "failing_build_count": len(artifact["after_health"]["failing_builds"])
            - len(artifact["before_health"]["failing_builds"]),
            "stalled_sleeve_count": len(artifact["after_health"]["stalled_sleeves"])
            - len(artifact["before_health"]["stalled_sleeves"]),
        },
        "production_impact": artifact["production_impact"],
        "calibration": artifact["calibration"],
        "post_run_reflection": artifact["post_run_reflection"],
        "next_retry_requires": artifact["next_retry_requires"],
        "related_files": artifact["related_files"],
        "notes": (
            "Gate 4 not run because this is read-side health classification; "
            "paper sleeve build payloads already show 0 failing builds after "
            "exp-20260611-021 and exp-20260612-002."
        ),
    }
    LOG_JSON.write_text(json.dumps(log_record, indent=2, sort_keys=True), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=prediction,
        result={
            "decision": decision,
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "failing_builds_after": artifact["after_health"]["failing_builds"],
            "stalled_sleeves_after": artifact["after_health"]["stalled_sleeves"],
            "accepted": success,
        },
        status=artifact["status"],
        fields={
            "change_type": "identity_or_measurement_repair",
            "mechanism_family": "data_accumulation_integrity",
            "trial_family": "sleeve_health_measurement_repair",
            "trial_variant_id": "sleeve_health_legacy_surface_classification_v1",
            "single_causal_variable": "sleeve_health_disk_status_summary_surface_classification",
            "decision": decision,
        },
    )
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "artifact": str(OUT_JSON),
        "failing_builds_after": artifact["after_health"]["failing_builds"],
        "stalled_sleeves_after": artifact["after_health"]["stalled_sleeves"],
    }, indent=2))


if __name__ == "__main__":
    main()
