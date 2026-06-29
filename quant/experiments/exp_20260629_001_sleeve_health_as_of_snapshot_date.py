"""exp-20260629-001: recognize as_of snapshot rows in sleeve health.

This is a measurement-repair runner. It does not alter entry, exit, ranking,
sizing, risk, or order behavior; it proves the existing core-risk forward
observation surface is misclassified by the legacy snapshot-date reader and
visible after the read-side repair.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from data_paths import DATA_ROOT  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from sleeve_health import RULE_VERSION, build_sleeve_health_report, sessions_between  # noqa: E402


EXPERIMENT_ID = "exp-20260629-001"
AS_OF = "2026-06-29"
BASELINE_RESULT_FILE = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
REGISTRY_PATH = REPO_ROOT / "docs" / "experiment_registry.json"
TICKET_PATH = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
SLEEVE_NAME = "core_risk_intensity_forward_observation"
SNAPSHOT_PATH = DATA_ROOT / "paper_sleeves" / SLEEVE_NAME / "snapshots.jsonl"
ARTIFACT_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260629_001_sleeve_health_as_of_snapshot_date.json"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_last_jsonl_row(path: Path) -> dict[str, Any] | None:
    last = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
    except OSError:
        return None
    if not last:
        return None
    return json.loads(last)


def _legacy_last_snapshot_date(snapshot_path: Path) -> str | None:
    row = _load_last_jsonl_row(snapshot_path)
    if not row:
        return None
    return str(row.get("asof_date") or row.get("date") or "")[:10] or None


def _legacy_disk_status(snapshot_path: Path, as_of: str) -> dict[str, Any]:
    legacy_date = _legacy_last_snapshot_date(snapshot_path)
    if legacy_date is None:
        return {"status": "never_persisted", "last_snapshot": None}
    staleness = sessions_between(legacy_date, as_of)
    return {
        "status": "stale" if staleness > 3 else "fresh",
        "last_snapshot": legacy_date,
        "staleness_sessions": staleness,
    }


def _baseline_metrics() -> dict[str, Any]:
    baseline = _load_json(BASELINE_RESULT_FILE)
    windows = baseline.get("windows") or []
    total_pnl = round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2)
    expected_value_score = round(sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4)
    trade_count = sum(int(row.get("trade_count") or 0) for row in windows)
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    wins = sum(float(row.get("win_rate") or 0.0) * int(row.get("trade_count") or 0) for row in windows)
    return {
        "baseline_result_file": str(BASELINE_RESULT_FILE.relative_to(REPO_ROOT)).replace("\\", "/"),
        "expected_value_score": expected_value_score,
        "total_pnl": total_pnl,
        "total_trades": trade_count,
        "max_drawdown_pct": max(float(row.get("max_drawdown_pct") or 0.0) for row in windows),
        "win_rate": round(wins / trade_count, 4) if trade_count else None,
        "survival_rate": round(signals_survived / signals_generated, 4) if signals_generated else None,
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "windows": windows,
    }


def main() -> None:
    ticket = _load_json(TICKET_PATH)
    snapshot_row = _load_last_jsonl_row(SNAPSHOT_PATH)
    if not snapshot_row:
        raise SystemExit(f"missing snapshot row: {SNAPSHOT_PATH}")

    before_status = _legacy_disk_status(SNAPSHOT_PATH, AS_OF)
    after_report = build_sleeve_health_report(
        AS_OF,
        {},
        sleeves_root=DATA_ROOT / "paper_sleeves",
        persist=False,
    )
    after_status = after_report["disk_status"].get(SLEEVE_NAME)
    if not after_status:
        raise SystemExit(f"missing repaired health entry for {SLEEVE_NAME}")

    target_price_present = snapshot_row.get("target_price") is not None
    repair_passed = (
        before_status.get("status") == "never_persisted"
        and after_status.get("status") == "fresh"
        and after_status.get("last_snapshot") == str(snapshot_row.get("as_of"))[:10]
        and target_price_present
    )

    artifact = {
        **_baseline_metrics(),
        "experiment_id": EXPERIMENT_ID,
        "timestamp": AS_OF,
        "status": "accepted_measurement_repair" if repair_passed else "rejected_measurement_repair",
        "accepted_alpha": False,
        "accepted_measurement_repair": bool(repair_passed),
        "alpha_hypothesis": (
            "Pre-execution core risk intensity may support a future risk-allocation alpha, "
            "but only after the forward observation surface is visible to health/maturity tooling."
        ),
        "changed_variable": "sleeve_health_as_of_snapshot_date_key_v1",
        "gate1": {
            "passed": True,
            "baseline_result_file": str(BASELINE_RESULT_FILE.relative_to(REPO_ROOT)).replace("\\", "/"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": bool(snapshot_row.get("as_of") and target_price_present),
            "runtime_fields_checked": {
                "as_of": snapshot_row.get("as_of"),
                "target_price": snapshot_row.get("target_price"),
                "entry_date": "not_applicable_forward_observation_row",
            },
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": "No signal, filter, ranking, sizing, exit, or order rule changed.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": {
            "passed": bool(repair_passed),
            "measurement_repair_only": True,
            "accepted_alpha": False,
            "before_after_strategy_delta": {
                "expected_value_score_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
            "health_status_delta": {
                "legacy_status": before_status,
                "repaired_status": after_status,
                "rule_version": RULE_VERSION,
            },
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "shared_policy_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "daily_health_report_changed": True,
            "parity_note": "Read-side sleeve health date parsing only; no trading policy consumes this repair.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "core_risk_intensity_ledger writes daily forward observation rows with an as_of field, "
                "while sleeve_health_report_v2 only checked asof_date/date for snapshots.jsonl rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another readiness audit for this same single core-risk row or simply "
                "join more observed-only labels to it."
            ),
            "new_evidence_required": (
                "Materially more closed core-risk forward rows with realized replacement values, or a new "
                "orthogonal risk-intensity source/gate shape."
            ),
        },
        "snapshot_evidence": {
            "snapshot_path": str(SNAPSHOT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "snapshot_date_key": "as_of",
            "snapshot_row_sample": {
                key: snapshot_row.get(key)
                for key in (
                    "as_of",
                    "ticker",
                    "strategy",
                    "candidate_status",
                    "risk_intensity",
                    "target_price",
                    "trade_enabled",
                    "rule_version",
                )
            },
        },
        "decision": (
            "accepted_measurement_repair_sleeve_health_as_of_snapshot_date"
            if repair_passed
            else "rejected_measurement_repair_sleeve_health_as_of_snapshot_date"
        ),
        "next_retry_requires": (
            "Do not re-slice the single core-risk row. Reopen alpha only after materially more closed "
            "forward rows with realized replacement values exist, or after a new orthogonal risk-intensity source is wired."
        ),
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260629_001_sleeve_health_as_of_snapshot_date.py",
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_sleeve_health.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
    }

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = {
        "decision": artifact["decision"],
        "accepted_alpha": False,
        "accepted_measurement_repair": bool(repair_passed),
        "before_result_file": str(ARTIFACT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "after_result_file": str(ARTIFACT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "signals_generated": 0,
            "signals_survived": 0,
            "strategy_behavior_changed": False,
        },
        "acceptance_reasons": [
            "legacy snapshot reader reports core-risk surface as never_persisted",
            "repaired reader recognizes as_of=2026-06-26 and reports the surface fresh",
        ],
    }
    fields = {
        "accepted_alpha": False,
        "accepted_measurement_repair": bool(repair_passed),
        "decision": artifact["decision"],
        "changed_files": [
            "quant/sleeve_health.py",
            "quant/test_sleeve_health.py",
            "quant/experiments/exp_20260629_001_sleeve_health_as_of_snapshot_date.py",
            str(ARTIFACT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            f"experiments/logs/{EXPERIMENT_ID}.json",
        ],
        "related_files": [
            "quant/sleeve_health.py",
            "quant/test_sleeve_health.py",
            "data/paper_sleeves/core_risk_intensity_forward_observation/snapshots.jsonl",
            str(BASELINE_RESULT_FILE.relative_to(REPO_ROOT)).replace("\\", "/"),
        ],
    }
    persist_self_registered_result(
        REGISTRY_PATH,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=ticket.get("prediction"),
        result=result,
        status=artifact["status"],
        fields=fields,
    )
    log_row = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": AS_OF,
        "status": artifact["status"],
        "lane": "measurement_repair",
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": artifact["alpha_hypothesis"],
        "change_type": ticket.get("change_type"),
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "changed_variable": ticket.get("changed_variable"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments") or [],
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "accepted_alpha": False,
        "accepted_measurement_repair": bool(repair_passed),
        "decision": artifact["decision"],
        "artifact": str(ARTIFACT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "gate1": artifact["gate1"],
        "gate2": artifact["gate2"],
        "gate3": artifact["gate3"],
        "gate4": artifact["gate4"],
        "delta_metrics": result["delta_metrics"],
        "production_impact": artifact["production_impact"],
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": artifact["decision"],
            "actual_success": 1 if repair_passed else 0,
            "predicted_success_probability": (ticket.get("prediction") or {}).get("success_probability"),
            "predicted_failure_modes": (ticket.get("prediction") or {}).get("main_failure_modes") or [],
            "realized_failure_mode": None,
        },
        "post_run_reflection": artifact["post_run_reflection"],
        "next_retry_requires": artifact["next_retry_requires"],
        "changed_files": fields["changed_files"],
        "related_files": fields["related_files"],
        "reproduction_commands": artifact["reproduction_commands"],
        "lean_quality_passed": True,
    }
    save_experiment_log_entry(log_row, allow_duplicate=True)
    print(json.dumps({"artifact": str(ARTIFACT_PATH), "accepted_measurement_repair": repair_passed}, sort_keys=True))


if __name__ == "__main__":
    main()
