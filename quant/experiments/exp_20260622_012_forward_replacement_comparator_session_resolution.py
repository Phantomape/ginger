"""exp-20260622-012: repair comparator session resolution for forward rows.

Measurement repair. Some closed paper rows recorded non-session entry dates
from pre-guard daily paper behavior, and several already-stamped rows kept a
``missing_comparator_bars`` status after fresher SPY/QQQ bars became available.
This runner refreshes only the forward replacement-value measurement surface.

Reproduce:
    .venv/Scripts/python.exe -B quant/experiments/exp_20260622_012_forward_replacement_comparator_session_resolution.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import forward_replacement_value as frv  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260622-012"
LANE = "measurement_repair"
ASOF_DATE = "2026-06-22"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SLEEVES_ROOT = REPO_ROOT / "data" / "paper_sleeves"
FORWARD_ARTIFACT = SLEEVES_ROOT / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260622_012_forward_replacement_comparator_session_resolution.json"
ARCHIVE_JSONL = OUT_DIR / "forward_replacement_value_pre_resolution.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_text_with_replace_fallback(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{EXPERIMENT_ID}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    try:
        tmp_path.replace(path)
    except PermissionError:
        path.write_text(text, encoding="utf-8")
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _runner_atomic_write_json(
    obj: Any,
    filepath: str | Path,
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
    default: Any = None,
) -> None:
    text = json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, default=default)
    _write_text_with_replace_fallback(Path(filepath), text)


def _runner_write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    _write_text_with_replace_fallback(Path(path), text)


def _append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    seen = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                seen.add(json.loads(line).get("experiment_id"))
            except json.JSONDecodeError:
                continue
    if record["experiment_id"] in seen:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _missing_comparator_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("status") == "missing_comparator_bars"
        or row.get("replacement_value_vs_spy_usd") is None
        or row.get("replacement_value_vs_qqq_usd") is None
    ]


def _artifact_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    state_records, skipped_missing = frv.current_state_replacement_records(SLEEVES_ROOT)
    state_keys = {frv.replacement_artifact_key(row) for row in state_records}
    artifact_keys = {frv.replacement_artifact_key(row) for row in rows}
    missing_rows = _missing_comparator_rows(rows)
    return {
        "artifact_rows": len(rows),
        "state_replacement_rows": len(state_records),
        "rows_by_status": dict(Counter(str(row.get("status") or "unknown") for row in rows)),
        "missing_comparator_bar_rows": len(missing_rows),
        "missing_comparator_bar_rows_by_sleeve": dict(
            Counter(str(row.get("sleeve_key") or "unknown") for row in missing_rows)
        ),
        "skipped_closed_rows_missing_replacement": len(skipped_missing),
        "rows_not_in_current_state": [
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
        ],
        "state_rows_missing_artifact": [
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
        ],
        "missing_rows": [
            {
                "sleeve_key": row.get("sleeve_key"),
                "decision_id": row.get("decision_id"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "status": row.get("status"),
            }
            for row in missing_rows
        ],
    }


def _baseline_summary() -> dict[str, Any]:
    data = _load_json(BASELINE_PATH)
    windows = data.get("windows") or []
    return {
        "path": _repo_rel(BASELINE_PATH),
        "aggregate_expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "aggregate_total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in windows),
        "total_trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
    }


def _resolved_detail(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details = []
    for row in rows:
        comparators = row.get("comparator_detail") or {}
        details.append(
            {
                "sleeve_key": row.get("sleeve_key"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "status": row.get("status"),
                "spy_detail": comparators.get("SPY"),
                "qqq_detail": comparators.get("QQQ"),
                "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
                "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
            }
        )
    return details


def _write_card(log_record: dict[str, Any], artifact_rel: str) -> None:
    CARD_MD.write_text(
        "\n".join(
            [
                "---",
                f'experiment_id: "{EXPERIMENT_ID}"',
                'status: "accepted"',
                f'lane: "{LANE}"',
                'change_type: "identity_or_measurement_repair"',
                'changed_variable: "forward_replacement_value_comparator_session_resolution_v1"',
                "---",
                "",
                f"# Experiment Card: {EXPERIMENT_ID}",
                "",
                "## Summary",
                "",
                log_record["change_summary"],
                "",
                "## Decision",
                "",
                f"- Decision: `{log_record['decision']}`",
                f"- Artifact: `{artifact_rel}`",
                "- Strategy impact: none; this only repairs forward replacement-value measurement.",
                "",
                "## Result",
                "",
                (
                    f"- Missing comparator rows: "
                    f"{log_record['before_metrics']['missing_comparator_bar_rows']} -> "
                    f"{log_record['after_metrics']['missing_comparator_bar_rows']}"
                ),
                f"- Rows refreshed: `{log_record['delta_metrics']['rows_refreshed']}`",
                f"- Baseline EV/PnL unchanged: `{log_record['after_metrics']['aggregate_expected_value_score']}` / `${log_record['after_metrics']['aggregate_total_pnl']}`",
                "",
                "## Reflection",
                "",
                f"- Why: {log_record['post_run_reflection']['why_result_happened']}",
                f"- Do not retry: {log_record['post_run_reflection']['forbidden_near_neighbor_retry']}",
                f"- Next evidence: {log_record['post_run_reflection']['new_evidence_required']}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _update_ticket(decision: str, timestamp: str, artifact_rel: str) -> None:
    ticket = _load_json(TICKET_JSON)
    ticket["status"] = "accepted"
    ticket["completed_at"] = timestamp
    ticket["result"] = {
        "decision": decision,
        "artifact": artifact_rel,
        "log": _repo_rel(LOG_JSON),
        "measurement_repair": True,
    }
    _write_json(TICKET_JSON, ticket)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prediction = (_load_json(TICKET_JSON).get("prediction") or {})
    before_rows = _load_jsonl(FORWARD_ARTIFACT)
    before_audit = _artifact_audit(before_rows)
    if FORWARD_ARTIFACT.exists():
        ARCHIVE_JSONL.write_text(FORWARD_ARTIFACT.read_text(encoding="utf-8"), encoding="utf-8")

    frv.atomic_write_json = _runner_atomic_write_json
    frv._write_jsonl = _runner_write_jsonl
    enrichment = frv.enrich_all_sleeve_states(
        ASOF_DATE,
        sleeves_root=SLEEVES_ROOT,
        artifact_path=FORWARD_ARTIFACT,
    )
    after_rows = _load_jsonl(FORWARD_ARTIFACT)
    after_audit = _artifact_audit(after_rows)
    baseline = _baseline_summary()
    before_missing_keys = {
        frv.replacement_artifact_key(row) for row in before_audit["missing_rows"]
    }
    repaired_rows = [
        row
        for row in after_rows
        if frv.replacement_artifact_key(row) in before_missing_keys
        and row.get("status") == "enriched"
        and row.get("replacement_value_vs_spy_usd") is not None
        and row.get("replacement_value_vs_qqq_usd") is not None
    ]
    success = (
        after_audit["missing_comparator_bar_rows"] == 0
        and not after_audit["rows_not_in_current_state"]
        and not after_audit["state_rows_missing_artifact"]
        and after_audit["skipped_closed_rows_missing_replacement"] == 0
        and (len(repaired_rows) == len(before_missing_keys) or not before_missing_keys)
    )
    decision = (
        "accepted_measurement_repair_forward_replacement_comparator_session_resolution"
        if success
        else "blocked_forward_replacement_comparator_session_resolution_incomplete"
    )
    timestamp = _utc_now()
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted" if success else "blocked",
        "lane": LANE,
        "decision": decision,
        "hypothesis": (
            "Repair forward replacement-value comparator enrichment so closed paper rows with "
            "non-session entry dates resolve to executable SPY/QQQ comparator bars instead of "
            "blocking activation readiness."
        ),
        "alpha_hypothesis_supported_by_repair": (
            "Accepted default-off paper helpers may now be closer to activation-readiness "
            "assessment, but only if their closed rows are comparable against cash, SPY, and QQQ."
        ),
        "before_audit": before_audit,
        "enrichment_summary": enrichment,
        "after_audit": after_audit,
        "repaired_rows": _resolved_detail(repaired_rows),
        "baseline_gate_summary": {
            "gate_1_baseline": baseline,
            "gate_2_required_fields": {
                "entry_date": "resolved to comparator executable session when row records a non-session fill",
                "target_price": "not used by this measurement repair",
                "replacement_value_vs_spy_usd": "present after repair",
                "replacement_value_vs_qqq_usd": "present after repair",
            },
            "gate_3_survival": "unchanged; no strategy filter or candidate selection changed",
            "gate_4_policy_result": "unchanged by construction; no buy/sell/ranking/sizing behavior changed",
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
                "Shared forward replacement-value enrichment changed only the measurement "
                "of already-closed paper rows. No sleeve admission, entry, exit, rank, sizing, "
                "or order behavior changed."
            ),
        },
    }
    artifact["calibration"] = {
        "actual_decision": decision,
        "actual_success": 1 if success else 0,
        "predicted_success_probability": prediction.get("success_probability"),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "predicted_failure_mode_hit": False if success else True,
        "realized_failure_mode": None if success else "state_artifact_reconciliation_or_missing_bars",
        "surprise_note": (
            "The repair refreshed all previously blocked comparator rows; local overlay-aware "
            "SPY/QQQ bars plus non-session prior-session resolution were sufficient."
            if success
            else "The repair did not fully eliminate missing comparator rows or state/artifact drift."
        ),
    }
    artifact["post_run_reflection"] = {
        "why_result_happened": (
            "The blocker was not alpha weakness; it was measurement idempotency plus old "
            "non-session paper entry dates. Existing rows stamped as missing_comparator_bars "
            "were skipped by later enrichment passes, so fresh SPY/QQQ bars could not repair them."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not rerun generic forward replacement refreshes unless the artifact again has "
            "missing comparator rows or state/artifact drift. Do not treat this repair as "
            "activation evidence by itself."
        ),
        "new_evidence_required": (
            "Run a forward readiness audit over the now-enriched artifact and require enough "
            "closed rows per source family with positive replacement value versus cash, SPY, "
            "and QQQ before any activation-envelope experiment."
        ),
    }
    artifact["related_files"] = [
        "quant/forward_replacement_value.py",
        "quant/test_forward_replacement_value.py",
        "quant/experiments/exp_20260622_012_forward_replacement_comparator_session_resolution.py",
        "data/paper_sleeves/forward_replacement_value.jsonl",
        "data/paper_sleeves/fundamental_growth_rs/state.json",
        "data/paper_sleeves/sec_governance/state.json",
        "data/paper_sleeves/sec_leadership/state.json",
        "data/paper_sleeves/sec_negative/state.json",
        "data/experiments/exp-20260622-012/forward_replacement_value_pre_resolution.jsonl",
    ]
    artifact["tests"] = [
        ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_forward_replacement_value.py",
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260622_012_forward_replacement_comparator_session_resolution.py",
        ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
    ]
    _write_json(OUT_JSON, artifact)

    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted" if success else "blocked",
        "lane": LANE,
        "decision": decision,
        "hypothesis": artifact["hypothesis"],
        "change_summary": (
            "Forward replacement-value enrichment now refreshes missing-comparator rows "
            "and resolves non-session comparator dates to nearby executable SPY/QQQ bars."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "forward_replacement_value_readiness_audit",
        "trial_family": "default_off_forward_replacement_value_activation_readiness",
        "trial_variant_id": "comparator_session_resolution_v1",
        "changed_variable": "forward_replacement_value_comparator_session_resolution_v1",
        "causal_components": [
            "refresh missing_comparator_bars rows",
            "resolve non-session comparator dates",
            "rebuild current-state forward replacement artifact",
        ],
        "prediction": prediction,
        "calibration": artifact["calibration"],
        "before_metrics": {
            **baseline,
            "artifact_rows": before_audit["artifact_rows"],
            "missing_comparator_bar_rows": before_audit["missing_comparator_bar_rows"],
            "skipped_closed_rows_missing_replacement": before_audit[
                "skipped_closed_rows_missing_replacement"
            ],
            "rows_by_status": before_audit["rows_by_status"],
        },
        "after_metrics": {
            **baseline,
            "artifact_rows": after_audit["artifact_rows"],
            "missing_comparator_bar_rows": after_audit["missing_comparator_bar_rows"],
            "skipped_closed_rows_missing_replacement": after_audit[
                "skipped_closed_rows_missing_replacement"
            ],
            "rows_by_status": after_audit["rows_by_status"],
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "artifact_rows": after_audit["artifact_rows"] - before_audit["artifact_rows"],
            "missing_comparator_bar_rows": after_audit["missing_comparator_bar_rows"]
            - before_audit["missing_comparator_bar_rows"],
            "rows_refreshed": len(repaired_rows),
        },
        "production_impact": artifact["production_impact"],
        "post_run_reflection": artifact["post_run_reflection"],
        "related_files": artifact["related_files"],
        "notes": (
            "Gate 4 strategy backtests were not rerun because no strategy behavior changed. "
            "Baseline metrics are recorded and unchanged; this is a measurement repair."
        ),
    }
    _write_json(LOG_JSON, log_record)
    _append_jsonl_once(EXPERIMENT_LOG, log_record)
    artifact_rel = _repo_rel(OUT_JSON)
    _write_card(log_record, artifact_rel)
    _update_ticket(decision, timestamp, artifact_rel)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=prediction,
        result={
            "decision": decision,
            "artifact": artifact_rel,
            "log": _repo_rel(LOG_JSON),
            "archive": _repo_rel(ARCHIVE_JSONL),
            "before_missing_comparator_bar_rows": before_audit["missing_comparator_bar_rows"],
            "after_missing_comparator_bar_rows": after_audit["missing_comparator_bar_rows"],
            "rows_refreshed": len(repaired_rows),
            "accepted": success,
        },
        status="accepted" if success else "blocked",
        fields={
            "change_type": "identity_or_measurement_repair",
            "mechanism_family": "forward_replacement_value_readiness_audit",
            "trial_family": "default_off_forward_replacement_value_activation_readiness",
            "trial_variant_id": "comparator_session_resolution_v1",
            "single_causal_variable": "forward_replacement_value_comparator_session_resolution_v1",
            "decision": decision,
        },
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "before_missing_comparator_bar_rows": before_audit[
                    "missing_comparator_bar_rows"
                ],
                "after_missing_comparator_bar_rows": after_audit[
                    "missing_comparator_bar_rows"
                ],
                "rows_refreshed": len(repaired_rows),
                "status": "accepted" if success else "blocked",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
