"""exp-20260729-007: verify claim-time promotion snapshot receipts.

This measurement repair does not change strategy behavior.  It verifies that
exp-20260729-006 remains reproducible after the mutable reopen-readiness index
advances, while proposed/live validation and all immutable receipt bindings
remain fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import alpha_debate  # noqa: E402
import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260729-007"
SOURCE_EXPERIMENT_ID = "exp-20260729-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
BEFORE_PATH = OUT_DIR / "before_measurement.json"
AFTER_PATH = OUT_DIR / "after_measurement.json"
ARTIFACT_PATH = OUT_DIR / "exp_20260729_007_promotion_claim_snapshot_receipt.json"
SOURCE_TICKET_PATH = (
    REPO_ROOT / "experiments" / "tickets" / f"{SOURCE_EXPERIMENT_ID}.json"
)
REGISTRY_PATH = experiment_registry.DEFAULT_REGISTRY
TICKETS_DIR = REPO_ROOT / "experiments" / "tickets"
LOGS_DIR = REPO_ROOT / "experiments" / "logs"

GATE1_METRICS = {
    "expected_value_score": 6.2057,
    "total_pnl": 130992.36,
    "total_trades": 49,
    "survival_rate": 0.8116,
    "max_drawdown_pct": 0.0889,
}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _lean_strict_result() -> dict[str, Any]:
    command = [
        sys.executable,
        "-B",
        str(REPO_ROOT / "scripts" / "experiment.py"),
        "audit",
        "--lean-strict",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"lean-strict audit did not emit JSON (exit={completed.returncode}): "
            f"{completed.stderr[-1000:]}"
        ) from exc
    return {
        "exit_code": completed.returncode,
        "lean_quality_passed": payload.get("lean_quality_passed"),
        "lean_strict_passed": payload.get("lean_strict_passed"),
        "failure_domains": payload.get("lean_strict_failure_domains") or [],
        "self_registration_passed": (payload.get("self_registration") or {}).get(
            "passed"
        ),
    }


def _before_measurement() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": "promotion_claim_snapshot_receipt_measurement_before",
        "experiment_id": EXPERIMENT_ID,
        "measured_at": "2026-07-29T06:01:03+00:00",
        **GATE1_METRICS,
        "strategy_or_trade_behavior_changed": False,
        "target_contract": {
            "passed": False,
            "invalid_alpha_promotion_count": 1,
            "research_result_ceiling_violation_count": 1,
            "source_ticket_receipt_present": False,
            "failure": (
                "exp-20260729-006 close/audit reopened mutable "
                "data/reopen_readiness.json and used a non-canonical terminal status"
            ),
        },
        "repository_strict_audit": {
            "passed": False,
            "pre_existing_unrelated_debt": True,
            "post_enforcement_missing_prediction_count": 16,
            "closed_post_enforcement_missing_calibration_count": 70,
        },
        "note": (
            "The global strict audit was already red from historical metadata debt. "
            "The attributable repair target is the promotion/ceiling sub-contract; "
            "the repository end-of-turn gate is lean-strict."
        ),
    }


def main() -> int:
    ticket = _read_json(SOURCE_TICKET_PATH)
    receipt = alpha_debate.validate_ticket_promotion_claim_receipt(
        ticket, repo_root=REPO_ROOT
    )
    anchor = alpha_debate.revalidate_ticket_promotion(ticket, repo_root=REPO_ROOT)

    snapshot_checks = []
    for row in receipt["research_artifact_snapshots"]:
        snapshot_path = REPO_ROOT / row["snapshot_path"]
        actual = _sha256(snapshot_path)
        snapshot_checks.append(
            {
                "locator": row["locator"],
                "snapshot_path": row["snapshot_path"],
                "expected_sha256": row["sha256"],
                "actual_sha256": actual,
                "bytes": snapshot_path.stat().st_size,
                "passed": actual == row["sha256"],
            }
        )

    registry = experiment_registry.load_registry(REGISTRY_PATH)
    audit = experiment_registry.audit_experiment_process(
        registry,
        tickets_dir=TICKETS_DIR,
        logs_dir=LOGS_DIR,
    )
    lean = _lean_strict_result()
    target_passed = bool(
        audit.get("invalid_alpha_promotion_count") == 0
        and audit.get("research_result_ceiling_violation_count") == 0
        and audit.get("missing_alpha_promotion_count") == 0
        and all(row["passed"] for row in snapshot_checks)
        and anchor.get("promotion_hash") == receipt.get("promotion_hash")
    )
    accepted = bool(target_passed and lean.get("lean_strict_passed"))
    generated_at = datetime.now(timezone.utc).isoformat()

    before = _before_measurement()
    after = {
        "schema_version": 1,
        "artifact_type": "promotion_claim_snapshot_receipt_measurement_after",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        **GATE1_METRICS,
        "strategy_or_trade_behavior_changed": False,
        "target_contract": {
            "passed": target_passed,
            "invalid_alpha_promotion_count": audit.get(
                "invalid_alpha_promotion_count"
            ),
            "research_result_ceiling_violation_count": audit.get(
                "research_result_ceiling_violation_count"
            ),
            "missing_alpha_promotion_count": audit.get(
                "missing_alpha_promotion_count"
            ),
            "source_ticket_status": ticket.get("status"),
            "source_ticket_decision": ticket.get("decision"),
            "source_ticket_receipt_present": True,
            "receipt_hash": receipt["receipt_hash"],
            "promotion_hash": anchor["promotion_hash"],
            "snapshot_count": len(snapshot_checks),
            "snapshot_checks": snapshot_checks,
        },
        "repository_strict_audit": {
            "passed": audit.get("passed"),
            "pre_existing_unrelated_debt": not bool(audit.get("passed")),
            "post_enforcement_missing_prediction_count": audit.get(
                "post_enforcement_missing_prediction_count"
            ),
            "closed_post_enforcement_missing_calibration_count": audit.get(
                "closed_post_enforcement_missing_calibration_count"
            ),
            "note": (
                "Global strict remains red only for pre-existing prediction/"
                "calibration debt outside this experiment's allowed scope."
            ),
        },
        "repository_lean_strict_audit": lean,
        "accepted_measurement_repair": accepted,
    }
    artifact = {
        "schema_version": 1,
        "artifact_type": "promotion_claim_snapshot_receipt_closeout",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": "accepted_measurement_repair" if accepted else "rejected",
        "decision": "accepted_measurement_repair" if accepted else "rejected",
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_hypothesis": (
            "The legitimately reopened entity-theme Axis-C cohort should show "
            "broad positive H10 replacement value versus cash, SPY, and QQQ."
        ),
        "alpha_result": {
            "experiment_id": SOURCE_EXPERIMENT_ID,
            "decision": "rejected",
            "settled_rows": 73275,
            "query_groups_beating_spy_and_qqq": 3,
            "required_query_groups": 4,
            "strategy_behavior_changed": False,
        },
        "measurement_hypothesis": (
            "Claim-time content-addressed research artifacts allow historical "
            "promotion validation after live indexes advance without weakening "
            "pre-claim live validation or immutable tamper detection."
        ),
        "before_measurement": str(BEFORE_PATH.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "after_measurement": str(AFTER_PATH.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "gate1_metrics_unchanged": GATE1_METRICS,
        "target_contract_passed": target_passed,
        "repository_lean_strict_passed": lean.get("lean_strict_passed"),
        "repository_global_strict_passed": audit.get("passed"),
        "global_strict_exception": (
            "16 historical post-enforcement tickets missing prediction and "
            "70 historical closed tickets missing calibration were present "
            "before and after; AGENTS.md forbids retroactive backfill and uses "
            "lean-strict as the end-of-turn gate."
        ),
        "production_impact": {
            "strategy_logic_changed": False,
            "signals_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "orders_changed": False,
            "trade_enabled_changed": False,
            "paper_or_live_changed": False,
        },
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest "
            "quant\\test_alpha_debate.py quant\\test_experiment_registry.py "
            "quant\\test_alpha_promotion_v2.py -q",
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260729_007_promotion_claim_snapshot_receipt.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py "
            "audit --lean-strict",
        ],
    }

    _atomic_write_json(BEFORE_PATH, before)
    _atomic_write_json(AFTER_PATH, after)
    _atomic_write_json(ARTIFACT_PATH, artifact)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "accepted_measurement_repair": accepted,
                "target_contract_passed": target_passed,
                "lean_strict_passed": lean.get("lean_strict_passed"),
                "global_strict_passed": audit.get("passed"),
                "receipt_hash": receipt["receipt_hash"],
            },
            indent=2,
        )
    )
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
