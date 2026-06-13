"""exp-20260612-012: repair canonical forward replacement-value accumulation.

Measurement repair. After exp-20260612-001 removed seven non-session
low_deployment_etf phantom rows from sleeve state, the shared
``data/paper_sleeves/forward_replacement_value.jsonl`` artifact still retained
those rows. This runner archives the stale artifact and rebuilds it from the
current per-sleeve ``state.json`` files so activation/readiness evidence counts
the same rows as the forward paper sleeves.

Reproduce:
    .venv/Scripts/python.exe -B quant/experiments/exp_20260612_012_forward_replacement_value_current_state_repair.py
"""

from __future__ import annotations

import datetime
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import forward_replacement_value as frv  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260612-012"
LANE = "measurement_repair"
ASOF_DATE = "2026-06-11"
SLEEVES_ROOT = REPO_ROOT / "data" / "paper_sleeves"
FORWARD_ARTIFACT = SLEEVES_ROOT / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260612_012_forward_replacement_value_current_state_repair.json"
ARCHIVE_JSONL = OUT_DIR / "forward_replacement_value_pre_repair.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def _artifact_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    state_records, skipped_missing_replacement = frv.current_state_replacement_records(SLEEVES_ROOT)
    state_keys = {frv.replacement_artifact_key(row) for row in state_records}
    artifact_keys = {frv.replacement_artifact_key(row) for row in rows}
    rows_not_in_state = [
        {
            "sleeve_key": row.get("sleeve_key"),
            "decision_id": row.get("decision_id"),
            "ticker": row.get("ticker"),
            "entry_date": row.get("entry_date"),
            "exit_date": row.get("exit_date"),
            "status": row.get("status"),
        }
        for row in rows
        if frv.replacement_artifact_key(row) not in state_keys
    ]
    state_rows_missing_artifact = [
        {
            "sleeve_key": row.get("sleeve_key"),
            "decision_id": row.get("decision_id"),
            "ticker": row.get("ticker"),
            "entry_date": row.get("entry_date"),
            "exit_date": row.get("exit_date"),
            "status": row.get("status"),
        }
        for row in state_records
        if frv.replacement_artifact_key(row) not in artifact_keys
    ]
    status_by_sleeve: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        status_by_sleeve[str(row.get("sleeve_key") or "unknown")][
            str(row.get("status") or "unknown")
        ] += 1
    return {
        "rows": len(rows),
        "rows_by_sleeve": _counter_dict(Counter(str(row.get("sleeve_key") or "unknown") for row in rows)),
        "rows_by_status": _counter_dict(Counter(str(row.get("status") or "unknown") for row in rows)),
        "status_by_sleeve": {
            sleeve: _counter_dict(counter) for sleeve, counter in sorted(status_by_sleeve.items())
        },
        "state_replacement_rows": len(state_records),
        "state_rows_by_status": _counter_dict(
            Counter(str(row.get("status") or "unknown") for row in state_records)
        ),
        "rows_not_in_current_state": rows_not_in_state,
        "state_rows_missing_artifact": state_rows_missing_artifact,
        "skipped_closed_rows_missing_replacement": skipped_missing_replacement,
    }


def _money(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _latest_snapshot(path: Path) -> dict[str, Any] | None:
    latest = None
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            latest = json.loads(line)
        except json.JSONDecodeError:
            continue
    return latest


def _state_snapshot_audit() -> dict[str, Any]:
    checked: dict[str, Any] = {}
    mismatches: list[dict[str, Any]] = []
    for state_path in sorted(SLEEVES_ROOT.glob("*/state.json")):
        sleeve = state_path.parent.name
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            mismatches.append({"sleeve": sleeve, "reason": f"unreadable_state:{exc}"})
            continue
        snapshot = _latest_snapshot(state_path.parent / "snapshots.jsonl")
        if snapshot is None:
            continue
        state_closed = len(state.get("closed_positions") or [])
        state_open = len(state.get("open_positions") or [])
        state_realized = round(sum(_money(row.get("pnl")) for row in state.get("closed_positions") or []), 2)
        snapshot_closed = len(snapshot.get("closed_positions") or [])
        snapshot_open = len(snapshot.get("open_positions") or [])
        snapshot_realized = snapshot.get("realized_pnl_to_date")
        row = {
            "state_closed": state_closed,
            "snapshot_closed": snapshot_closed,
            "state_open": state_open,
            "snapshot_open": snapshot_open,
            "state_realized_pnl": state_realized,
            "snapshot_realized_pnl": snapshot_realized,
            "snapshot_asof": snapshot.get("asof_date"),
        }
        checked[sleeve] = row
        if (
            state_closed != snapshot_closed
            or state_open != snapshot_open
            or round(_money(snapshot_realized), 2) != state_realized
        ):
            mismatches.append({"sleeve": sleeve, **row})
    return {
        "sleeves_checked": len(checked),
        "mismatches": mismatches,
        "checked": checked,
    }


def _append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing.add(json.loads(line).get("experiment_id"))
            except json.JSONDecodeError:
                continue
    if record["experiment_id"] in existing:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prediction = json.loads(TICKET_JSON.read_text(encoding="utf-8")).get("prediction") or {}
    before_rows = _load_jsonl(FORWARD_ARTIFACT)
    before_audit = _artifact_audit(before_rows)
    snapshot_audit = _state_snapshot_audit()
    rebuild_summary = frv.rebuild_current_state_artifact(
        sleeves_root=SLEEVES_ROOT,
        artifact_path=FORWARD_ARTIFACT,
        archive_path=ARCHIVE_JSONL,
    )
    after_rows = _load_jsonl(FORWARD_ARTIFACT)
    after_audit = _artifact_audit(after_rows)

    stale_removed = rebuild_summary["previous_rows_not_in_current_state"]
    success = (
        before_audit["rows"] == 38
        and after_audit["rows"] == after_audit["state_replacement_rows"] == 31
        and len(stale_removed) == 7
        and {row.get("sleeve_key") for row in stale_removed} == {"low_deployment_etf"}
        and after_audit["rows_by_status"] == {"enriched": 29, "missing_comparator_bars": 2}
        and not after_audit["rows_not_in_current_state"]
        and not after_audit["state_rows_missing_artifact"]
        and not after_audit["skipped_closed_rows_missing_replacement"]
        and not snapshot_audit["mismatches"]
    )
    status = "accepted" if success else "blocked"
    decision = (
        "accepted_measurement_repair_forward_replacement_value_current_state_repair"
        if success
        else "blocked_forward_replacement_value_current_state_repair_incomplete"
    )
    timestamp = _utc_now()
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": LANE,
        "decision": decision,
        "asof_date": ASOF_DATE,
        "hypothesis": (
            "Canonical per-sleeve forward replacement-value accumulation must "
            "match current paper sleeve state after non-session phantom-row "
            "quarantine."
        ),
        "change_summary": (
            "Rebuilt data/paper_sleeves/forward_replacement_value.jsonl from "
            "current state.json replacement rows, archived the prior 38-row "
            "artifact, and removed the seven low_deployment_etf rows that "
            "exp-20260612-001 had already quarantined from state."
        ),
        "before_audit": before_audit,
        "after_audit": after_audit,
        "rebuild_summary": rebuild_summary,
        "state_snapshot_audit": {
            "sleeves_checked": snapshot_audit["sleeves_checked"],
            "mismatches": snapshot_audit["mismatches"],
        },
        "archived_artifact": _repo_rel(ARCHIVE_JSONL),
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
                "Measurement materialization only. Daily replacement-value "
                "enrichment now rewrites the canonical JSONL from current "
                "sleeve state, but no sleeve admission, fill, close, ranking, "
                "sizing, exit, or order semantics changed."
            ),
        },
        "tests": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_forward_replacement_value.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260612_012_forward_replacement_value_current_state_repair.py",
        ],
        "accepted": success,
    }
    artifact["calibration"] = {
        "actual_decision": decision,
        "actual_success": 1 if success else 0,
        "predicted_success_probability": prediction.get("success_probability"),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_mode": None if success else "forward_replacement_artifact_rebuild_incomplete",
        "surprise_note": (
            "The per-sleeve state and latest snapshots were already aligned; "
            "only the shared replacement-value JSONL still retained the "
            "quarantined low_deployment_etf rows."
        ),
    }
    artifact["post_run_reflection"] = {
        "why_result_happened": (
            "The original enrichment wrote an append-only artifact. Later "
            "measurement repair correctly removed non-session phantom rows "
            "from low_deployment_etf state, but append-only replacement "
            "evidence retained them. A current-state materialization keeps "
            "cross-sleeve forward evidence aligned with sleeve state."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not consume forward_replacement_value.jsonl as immutable "
            "history for activation decisions; use it as the current canonical "
            "state-derived evidence surface, with old versions archived inside "
            "measurement-repair experiments."
        ),
        "new_evidence_required": (
            "Future activation work should wait for more current-state closed "
            "replacement rows and should treat status=missing_comparator_bars "
            "or non_session_entry_fill rows as coverage blockers, not enriched "
            "comparator evidence."
        ),
    }
    artifact["related_files"] = [
        "quant/forward_replacement_value.py",
        "quant/test_forward_replacement_value.py",
        "data/paper_sleeves/forward_replacement_value.jsonl",
        "data/experiments/exp-20260612-012/forward_replacement_value_pre_repair.jsonl",
        "quant/experiments/exp_20260612_012_forward_replacement_value_current_state_repair.py",
    ]
    OUT_JSON.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")

    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": LANE,
        "decision": decision,
        "hypothesis": artifact["hypothesis"],
        "change_summary": artifact["change_summary"],
        "change_type": "forward_replacement_value_accumulation_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "forward_replacement_value_measurement_repair",
        "trial_family": "paper_sleeve_forward_accumulation_integrity",
        "trial_variant_id": "canonical_forward_replacement_value_current_state_v1",
        "changed_variable": "canonical_forward_replacement_value_artifact_matches_current_sleeve_state",
        "causal_components": [
            "state_vs_artifact_reconciliation",
            "current_state_materialization",
            "quarantined_row_exclusion",
        ],
        "before_metrics": {
            "artifact_rows": before_audit["rows"],
            "rows_not_in_current_state": len(before_audit["rows_not_in_current_state"]),
            "rows_by_status": before_audit["rows_by_status"],
        },
        "after_metrics": {
            "artifact_rows": after_audit["rows"],
            "rows_not_in_current_state": len(after_audit["rows_not_in_current_state"]),
            "rows_by_status": after_audit["rows_by_status"],
        },
        "delta_metrics": {
            "artifact_rows": after_audit["rows"] - before_audit["rows"],
            "rows_not_in_current_state": len(after_audit["rows_not_in_current_state"])
            - len(before_audit["rows_not_in_current_state"]),
            "quarantined_low_deployment_rows_removed": len(stale_removed),
        },
        "production_impact": artifact["production_impact"],
        "calibration": artifact["calibration"],
        "post_run_reflection": artifact["post_run_reflection"],
        "related_files": artifact["related_files"],
        "notes": (
            "Gate 4 backtests were not run because this is a measurement "
            "surface repair. Strategy behavior is unchanged; the acceptance "
            "check is state/artifact/snapshot reconciliation plus focused "
            "pytest coverage."
        ),
    }
    LOG_JSON.write_text(json.dumps(log_record, indent=2, sort_keys=True), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=prediction,
        result={
            "decision": decision,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "archive": _repo_rel(ARCHIVE_JSONL),
            "before_rows": before_audit["rows"],
            "after_rows": after_audit["rows"],
            "stale_rows_removed": len(stale_removed),
            "accepted": success,
        },
        status=status,
        fields={
            "change_type": "forward_replacement_value_accumulation_repair",
            "mechanism_family": "forward_replacement_value_measurement_repair",
            "trial_family": "paper_sleeve_forward_accumulation_integrity",
            "trial_variant_id": "canonical_forward_replacement_value_current_state_v1",
            "single_causal_variable": "canonical_forward_replacement_value_artifact_matches_current_sleeve_state",
            "decision": decision,
        },
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "before_rows": before_audit["rows"],
                "after_rows": after_audit["rows"],
                "stale_rows_removed": len(stale_removed),
                "rows_by_status": after_audit["rows_by_status"],
                "snapshot_mismatches": snapshot_audit["mismatches"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
