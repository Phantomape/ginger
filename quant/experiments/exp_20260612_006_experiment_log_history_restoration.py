"""exp-20260612-006: restore the full experiment-log history from the LFS object.

Measurement repair. docs/experiment_log.jsonl was pointerized in the
2026-06-05 LFS incident; daily closeouts kept appending to the pointer, so the
canonical history visible to tools (meta research engine, alpha memory packs,
audits) silently dropped from 1526 records to 199. Restored the archived
157MB LFS object from the local cache, merged the 199 appended rows
(exact-line dedupe, 1725 total), re-tracked the oversized file on LFS (it
exceeds GitHub's 100MB hard limit), and removed the pointer guard's size
short-circuit so pointer/append hybrids are caught.

Reproduce verification:
    .venv/Scripts/python.exe -B quant/experiments/exp_20260612_006_experiment_log_history_restoration.py
"""

from __future__ import annotations

import datetime
import json
import sys
from datetime import timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from experiment_registry import persist_self_registered_result
from test_no_lfs_pointer_data_files import _pointer_files

EXPERIMENT_ID = "exp-20260612-006"
LANE = "measurement_repair"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260612_006_experiment_log_history_restoration.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / (EXPERIMENT_ID + ".json")
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / (EXPERIMENT_ID + ".json")
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _verify() -> dict:
    ids = []
    for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.append(json.loads(line).get("experiment_id"))
    attrs = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    guard_text = (REPO_ROOT / "quant" / "test_no_lfs_pointer_data_files.py").read_text(encoding="utf-8")
    return {
        "log_records": len(ids),
        "first_record": ids[0] if ids else None,
        "last_record": ids[-1] if ids else None,
        "all_lines_parse": True,
        "no_pointer_hybrids_on_guarded_surfaces": not _pointer_files(),
        "oversized_lfs_rule_present": "docs/experiment_log.jsonl filter=lfs" in attrs,
        "guard_size_shortcircuit_removed": "MAX_POINTER_SIZE" not in guard_text,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = _verify()
    passed = (
        checks["log_records"] >= 1700
        and checks["no_pointer_hybrids_on_guarded_surfaces"]
        and checks["oversized_lfs_rule_present"]
        and checks["guard_size_shortcircuit_removed"]
    )
    status = "accepted" if passed else "blocked"
    decision = (
        "accepted_measurement_repair_experiment_log_history_restoration"
        if passed
        else "blocked_experiment_log_restoration_incomplete"
    )
    prediction = json.loads(TICKET_JSON.read_text(encoding="utf-8")).get("prediction") or {}
    predicted = float(prediction.get("success_probability") or 0.0)
    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "lane": LANE,
        "decision": decision,
        "hypothesis": (
            "docs/experiment_log.jsonl was pointerized in the 2026-06-05 LFS "
            "incident and has been a pointer-plus-appends hybrid ever since, so "
            "the canonical experiment history visible to tools dropped from "
            "1526 records to 199; restoring the archived LFS object, merging "
            "the appended rows, keeping the oversized file on LFS, and closing "
            "the hybrid-file blind spot in the pointer guard repairs the "
            "history surface."
        ),
        "change_summary": (
            "Restored the 157MB full-history object from .git/lfs/objects "
            "(1526 records), merged the 199 rows appended since 2026-06-05 "
            "(exact-line dedupe, 1725 total, every line parses), re-added the "
            "LFS rule for this over-100MB file, and removed the pointer "
            "guard's size short-circuit so pointer/append hybrids are flagged."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "data_accumulation_integrity",
        "trial_family": "identity_or_measurement_repair",
        "trial_variant_id": "experiment_log_history_restoration_v1",
        "changed_variable": "experiment_log_history_restoration_and_hybrid_guard",
        "causal_components": [
            "lfs object restore",
            "append merge",
            "gitattributes oversized exception",
            "guard blind spot fix",
        ],
        "prior_trial_count": 0,
        "nearby_prior_experiments": ["exp-20260611-027"],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "measurement_surface_repair",
        "component": "docs/experiment_log.jsonl + quant/test_no_lfs_pointer_data_files.py",
        "verification": checks,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": 1 if passed else 0,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - (1 if passed else 0)) ** 2, 4),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_mode": None if passed else "restoration_incomplete",
            "predicted_failure_mode_hit": False,
            "surprise_note": (
                "The hybrid survived three weeks of daily reads because every "
                "consumer skips unparseable lines; the guard added in "
                "exp-20260611-027 missed it because of the pointer-size "
                "short-circuit, which is exactly the blind spot now removed."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "default_off_attribution_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "parity_note": (
                "History-surface restoration only: meta research priors, "
                "alpha memory packs, and audits regain the full 1725-record "
                "history. No trading or replay behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Append-only JSONL files mask pointerization: writers append "
                "happily after the pointer header and line-tolerant readers "
                "skip it, so the file looks alive while almost all history is "
                "gone. Only a head-bytes check catches the hybrid state."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not de-LFS files above GitHub's 100MB hard limit; do not "
                "reintroduce size-based short-circuits into the pointer guard."
            ),
            "new_evidence_required": (
                "If the log approaches a size where LFS round-trips hurt, "
                "split it via an explicit archived-segment scheme with reader "
                "support, not by truncation."
            ),
        },
        "next_retry_requires": ["log size growth requiring an archived-segment scheme"],
        "related_files": [
            "docs/experiment_log.jsonl",
            ".gitattributes",
            "quant/test_no_lfs_pointer_data_files.py",
            "quant/experiments/exp_20260612_006_experiment_log_history_restoration.py",
            "data/experiments/exp-20260612-006/hybrid_before_restore.jsonl",
        ],
        "notes": (
            "Verified by re-runnable checks in this runner; the pre-restore "
            "hybrid is archived in the experiment directory."
        ),
    }
    OUT_JSON.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    existing = set()
    for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                existing.add(json.loads(line).get("experiment_id"))
            except json.JSONDecodeError:
                continue
    if EXPERIMENT_ID not in existing:
        with EXPERIMENT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + chr(10))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=prediction,
        result={
            "decision": decision,
            "artifact": "data/experiments/exp-20260612-006/exp_20260612_006_experiment_log_history_restoration.json",
            "log": "experiments/logs/exp-20260612-006.json",
            "log_records_after": checks["log_records"],
            "accepted": passed,
        },
        status=status,
        fields={
            "change_type": "identity_or_measurement_repair",
            "mechanism_family": "data_accumulation_integrity",
            "trial_family": "identity_or_measurement_repair",
            "trial_variant_id": "experiment_log_history_restoration_v1",
            "single_causal_variable": "experiment_log_history_restoration_and_hybrid_guard",
            "decision": decision,
        },
    )
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": decision, "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
