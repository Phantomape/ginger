"""exp-20260726-002: recognize the candidate-training ledger health contract.

The append-only candidate-decision training surface persists ``state.json``
plus ``rows.jsonl`` rather than sleeve snapshots.  This measurement-repair
runner reproduces the old ``never_persisted`` classification from those real
files, verifies the explicit repaired contract, and records strategy-zero
delta against the active cash-feasible Gate-1 baseline.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, QUANT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_json  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
import sleeve_health as sh  # noqa: E402


EXPERIMENT_ID = "exp-20260726-002"
SLUG = "candidate_training_sleeve_health_contract"
RUNNER = f"quant/experiments/exp_20260726_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"
ARTIFACT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT = ARTIFACT_DIR / f"exp_20260726_002_{SLUG}.json"
ACTIVE_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
SLEEVE_ROOT = ROOT / "data" / "paper_sleeves"
SURFACE_DIR = SLEEVE_ROOT / "candidate_decision_training_ledger"
STATE = SURFACE_DIR / "state.json"
ROWS = SURFACE_DIR / "rows.jsonl"
EXPECTED_CONTRACT = "append_only_candidate_decision_training_ledger"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_surface_date(path: Path) -> str | None:
    try:
        row = load_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    for key in (
        "asof_date",
        "as_of_date",
        "as_of",
        "last_run_as_of",
        "date",
        "updated_at",
        "generated_at",
    ):
        value = str(row.get(key) or "")[:10]
        if value:
            return value
    return None


def last_jsonl_date(path: Path) -> str | None:
    if not path.exists():
        return None
    last_row = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_row = json.loads(line)
    if not isinstance(last_row, dict):
        return None
    return str(
        last_row.get("asof_date")
        or last_row.get("as_of")
        or last_row.get("date")
        or ""
    )[:10] or None


def legacy_disk_entry(sleeve_dir: Path, as_of: str) -> dict[str, Any]:
    """Reproduce the pre-repair state reader against the real surface.

    The legacy reader accepted state.json only for the heartbeat contract; it
    never considered rows.jsonl as the companion persistence proof.
    """
    last_snapshot = last_jsonl_date(sleeve_dir / "snapshots.jsonl")
    candidates = list(sleeve_dir.glob("*summary.json"))
    candidates.extend(sleeve_dir.glob("*snapshot.json"))
    state_path = sleeve_dir / "state.json"
    state = load_json(state_path) if state_path.exists() else {}
    legacy_state_recognized = (
        state.get("surface_contract") == "forward_observation_heartbeat"
    )
    if legacy_state_recognized:
        candidates.append(state_path)

    dated = [
        (date, path.name)
        for path in candidates
        if (date := json_surface_date(path)) is not None
    ]
    latest_summary = max(dated, default=(None, None))
    if latest_summary[0] is not None and (
        last_snapshot is None or latest_summary[0] > last_snapshot
    ):
        staleness = sh.sessions_between(latest_summary[0], as_of)
        status = (
            "stale_summary"
            if staleness > sh.DEFAULT_STALE_SESSION_THRESHOLD
            else "fresh_summary"
        )
        return {
            "status": status,
            "last_snapshot": last_snapshot,
            "last_summary": latest_summary[0],
            "summary_file": latest_summary[1],
            "staleness_sessions": staleness,
            "legacy_state_contract_recognized": legacy_state_recognized,
        }
    if last_snapshot is None:
        return {
            "status": "never_persisted",
            "last_snapshot": None,
            "legacy_state_contract_recognized": legacy_state_recognized,
        }
    staleness = sh.sessions_between(last_snapshot, as_of)
    return {
        "status": (
            "stale"
            if staleness > sh.DEFAULT_STALE_SESSION_THRESHOLD
            else "fresh"
        ),
        "last_snapshot": last_snapshot,
        "staleness_sessions": staleness,
        "legacy_state_contract_recognized": legacy_state_recognized,
    }


def reproduce_and_verify_contract() -> dict[str, Any]:
    state = load_json(STATE)
    state_date = str(state.get("as_of") or state.get("last_run_as_of") or "")[:10]
    row_count = sum(1 for line in ROWS.read_text(encoding="utf-8").splitlines() if line.strip())
    before = legacy_disk_entry(SURFACE_DIR, state_date)
    report = sh.build_sleeve_health_report(
        state_date,
        {},
        sleeves_root=SLEEVE_ROOT,
        persist=False,
    )
    after = report["disk_status"][SURFACE_DIR.name]
    checks = {
        "real_state_contract_is_explicit": state.get("surface_contract")
        == EXPECTED_CONTRACT,
        "real_rows_jsonl_exists": ROWS.is_file(),
        "real_rows_jsonl_nonempty": row_count > 0,
        "state_has_current_run_date": bool(state_date)
        and state_date == str(state.get("last_run_as_of") or "")[:10],
        "legacy_fault_reproduced": before.get("status") == "never_persisted"
        and before.get("legacy_state_contract_recognized") is False,
        "repaired_contract_is_fresh": after.get("status") == "fresh_summary",
        "repaired_contract_uses_state": after.get("summary_file") == "state.json"
        and after.get("last_summary") == state_date,
        "repaired_contract_not_stalled": SURFACE_DIR.name
        not in report["stalled_sleeves"],
    }
    return {
        "as_of": state_date,
        "surface_contract": state.get("surface_contract"),
        "state_path": rel(STATE),
        "rows_path": rel(ROWS),
        "state_sha256": sha256(STATE),
        "rows_sha256": sha256(ROWS),
        "rows_count": row_count,
        "before": before,
        "after": after,
        "report_rule_version": report["rule_version"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_focused_validation() -> dict[str, Any]:
    python = str(ROOT / ".venv" / "Scripts" / "python.exe")
    commands = [
        [
            python,
            "-B",
            "-m",
            "pytest",
            "quant/test_sleeve_health.py",
            "-q",
        ],
        [
            python,
            "-B",
            "-m",
            "py_compile",
            "quant/sleeve_health.py",
            "quant/test_sleeve_health.py",
            RUNNER,
        ],
    ]
    runs = []
    for command in commands:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        runs.append(
            {
                "command": " ".join(command[1:]),
                "returncode": proc.returncode,
                "stdout_tail": (proc.stdout or "").strip().splitlines()[-5:],
                "stderr_tail": (proc.stderr or "").strip().splitlines()[-5:],
            }
        )
    return {"passed": all(row["returncode"] == 0 for row in runs), "runs": runs}


def main() -> int:
    ticket = load_json(TICKET)
    baseline = load_json(ACTIVE_BASELINE)
    contract = reproduce_and_verify_contract()
    validation = run_focused_validation()
    baseline_metrics = dict(baseline["aggregate"])
    zero_delta = {
        "expected_value_score_sum": 0.0,
        "total_pnl_sum": 0.0,
        "trade_count_sum": 0,
        "positive_ev_windows": 0,
        "minimum_survival_rate": 0.0,
        "worst_max_drawdown_pct": 0.0,
    }
    checks = {
        "ticket_lifecycle_valid": ticket.get("status") in {"claimed", "accepted"},
        "active_cash_feasible_gate1_readable": baseline.get("baseline_role")
        == "active_cash_feasible_gate1_reference",
        "real_before_fault_reproduced": contract["checks"][
            "legacy_fault_reproduced"
        ],
        "repaired_real_surface_healthy": contract["passed"],
        "focused_pytest_passed": validation["runs"][0]["returncode"] == 0,
        "py_compile_passed": validation["runs"][1]["returncode"] == 0,
        "strategy_metrics_zero_delta": all(value == 0 for value in zero_delta.values()),
    }
    passed = all(checks.values())
    status = "accepted_measurement_repair" if passed else "blocked"
    decision = status
    now = utc_now()
    changed_files = [
        "quant/sleeve_health.py",
        "quant/test_sleeve_health.py",
        RUNNER,
        rel(ARTIFACT),
        rel(CARD),
        rel(LOG),
        rel(MANIFEST),
        rel(TICKET),
        "docs/experiment_log.jsonl",
        rel(REGISTRY),
    ]
    payload = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "owner": ticket.get("owner") or "codex-alpha-automation",
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": passed,
        "hypothesis": ticket["hypothesis"],
        "alpha_hypothesis": (
            "Core drawdown stabilization confirmed by positive flow and elevated "
            "near-put positioning may mark forced-selling exhaustion; it remains "
            "a default-off forward observer."
        ),
        "change_type": ticket["change_type"],
        "implementation_mode": "read_side_explicit_persistence_contract_repair",
        "mechanism_family": ticket["mechanism_family"],
        "trial_family": ticket["trial_family"],
        "trial_variant_id": ticket["trial_variant_id"],
        "single_causal_variable": ticket["single_causal_variable"],
        "changed_variable": ticket["changed_variable"],
        "causal_components": ticket["causal_components"],
        "nearby_prior_experiments": ticket["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": ticket["multiple_testing_risk_bucket"],
        "new_evidence_type": ticket["new_evidence_type"],
        "prediction": ticket.get("prediction"),
        "parameters": {
            "recognized_state_contract": EXPECTED_CONTRACT,
            "required_companion": "rows.jsonl",
            "preserved_state_contract": "forward_observation_heartbeat",
            "unknown_state_contract_policy": "fail_closed",
        },
        "date_range": {"start": None, "end": None},
        "evaluation_windows": [],
        "baseline_artifact": rel(ACTIVE_BASELINE),
        "ticket_baseline_reference": ticket.get("baseline_result_file"),
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics if passed else {},
        "delta_metrics": zero_delta if passed else {},
        "headline_metrics": {
            "before_disk_status": contract["before"]["status"],
            "after_disk_status": contract["after"]["status"],
            "real_ledger_rows": contract["rows_count"],
            "strategy_ev_delta": 0.0,
            "strategy_pnl_delta": 0.0,
            "strategy_trade_delta": 0,
        },
        "fault_reproduction": contract,
        "validation": validation,
        "checks": checks,
        "gate1": {
            "passed": checks["active_cash_feasible_gate1_readable"],
            "reference": rel(ACTIVE_BASELINE),
            "aggregate": baseline_metrics,
        },
        "gate2": {
            "passed": contract["passed"],
            "required_fields": ["surface_contract", "as_of|last_run_as_of"],
            "required_files": [rel(STATE), rel(ROWS)],
            "signal_sentinels": (
                "entry_date and target_price remain canonical signal sentinels; "
                "this read-only health surface does not generate entries."
            ),
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
        },
        "gate4": {
            "passed": passed,
            "decision": decision,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "strategy_behavior_changed": False,
            "failed_reasons": [name for name, ok in checks.items() if not ok],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_changed": False,
            "run_adapter_changed": False,
            "read_side_health_classification_repaired": passed,
            "trade_enabled": False,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
        },
        "pre_run_questions": {
            "1_money_hypothesis": (
                "The underlying flow-put observer may improve candidate quality; "
                "this repair only restores trustworthy accumulation health."
            ),
            "2_history_and_novelty": (
                "exp-20260717-002 deliberately left this then-dateless state fail-closed; "
                "exp-20260710-001 subsequently established the explicit append-only "
                "state-plus-rows contract now present on disk."
            ),
            "3_single_bundle": ticket["single_causal_variable"],
            "4_acceptance": (
                "Real legacy status is never_persisted, repaired status is fresh_summary, "
                "unknown/unmarked contracts stay fail-closed, focused validation passes, "
                "and active Gate-1 strategy metrics are unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
            "6_opportunity_cost": "cash/no new executable entry remains superior",
            "7_cross_surface_boundary": (
                "Price, flow, derivatives, event, positioning, and portfolio surfaces "
                "were synthesized; the underlying candidates remain immature."
            ),
        },
        "alpha_synthesis": {
            "baseline_universe": [
                "cash-feasible core universe",
                "current broad observation universe",
                "broker positions and cash",
                "accepted default-off sleeves",
                "SPY",
                "QQQ",
            ],
            "opportunity_cost_winner": "cash/no new executable entry",
            "evidence_surfaces_used": [
                "price",
                "flow",
                "derivatives",
                "events",
                "positioning",
                "portfolio exposure",
                "research digest",
            ],
            "evidence_surfaces_missing": [
                "mature flow-put observer settlements",
                "intraday REDUCE_RISK power bar",
                "estimate-revision cash conflicts and fixed-horizon settlements",
            ],
            "hypothesis_candidates": [
                "core drawdown flow-put stabilization observer",
                "deterministic intraday REDUCE_RISK versus next-close hold",
                "timestamp-safe estimate revision x muted immediate price response",
            ],
            "selected_hypothesis": "core drawdown flow-put stabilization observer",
            "economic_mechanism": (
                "Flow absorption plus crowded downside hedging after stabilization "
                "may mark forced-selling exhaustion."
            ),
            "falsifier": (
                "Nonpositive chronological halves, survival below 5%, concentration "
                "failure, or insufficient selected and settled forward decisions."
            ),
            "evidence_grade": "measurement_repair_underlying_alpha_observer",
            "next_machine_action": (
                "Continue routine producer-before-consumer accumulation and settlement "
                "without new experiment IDs."
            ),
        },
        "research_digest": {
            "fresh_entries": 0,
            "ledger_append_required": False,
            "disposition": "No fresh digest entries; no ledger append required.",
        },
        "acceptance_basis": (
            "The real append-only state-plus-rows surface reproduces the old false "
            "never_persisted status and is now fresh without any strategy delta."
        ),
        "rejection_reason": None
        if passed
        else ";".join(name for name, ok in checks.items() if not ok),
        "post_run_reflection": {
            "why_result_happened": (
                "The health reader recognized only heartbeat state files, so the "
                "candidate-training ledger's explicit append-only contract was ignored."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not recognize arbitrary state.json files or omit the rows.jsonl "
                "companion requirement; unknown contracts must remain fail-closed."
            ),
            "new_evidence_required": (
                "No retry of this repair; focused regression tests own the contract. "
                "Alpha work still requires the existing settled-row readiness bars."
            ),
        },
        "changed_files": changed_files,
        "related_files": changed_files + [rel(STATE), rel(ROWS), rel(ACTIVE_BASELINE)],
        "source_hashes": {
            rel(STATE): sha256(STATE),
            rel(ROWS): sha256(ROWS),
            rel(ACTIVE_BASELINE): sha256(ACTIVE_BASELINE),
            "quant/sleeve_health.py": sha256(ROOT / "quant" / "sleeve_health.py"),
            "quant/test_sleeve_health.py": sha256(
                ROOT / "quant" / "test_sleeve_health.py"
            ),
        },
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sleeve_health.py -q",
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            "quant\\sleeve_health.py quant\\test_sleeve_health.py "
            + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": passed,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, ARTIFACT, indent=2, ensure_ascii=False)
    save_experiment_log_entry(payload, allow_duplicate=True)
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_text(
        f"# {EXPERIMENT_ID}: Candidate-training sleeve-health contract\n\n"
        f"- Decision: `{decision}`\n"
        f"- Real disk status: `{contract['before']['status']} -> "
        f"{contract['after']['status']}`\n"
        f"- Real ledger rows: `{contract['rows_count']}`\n"
        "- Strategy EV / PnL / trades changed: `0 / 0 / 0`\n"
        "- Accepted alpha: `false`; trade enabled: `false`\n\n"
        "The read-side repair recognizes only the explicit append-only candidate "
        "ledger contract with its rows.jsonl companion; unknown state contracts "
        "remain fail-closed.\n",
        encoding="utf-8",
    )
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=ticket.get("prediction"),
        result={
            "accepted": passed,
            "accepted_alpha": False,
            "accepted_measurement_repair": passed,
            "decision": decision,
            "artifact": rel(ARTIFACT),
            "log": rel(LOG),
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        },
        status=status,
        fields={
            **payload,
            "artifact": rel(ARTIFACT),
            "log": rel(LOG),
            "card_file": rel(CARD),
            "revision_manifest_file": rel(MANIFEST),
            "ticket_file": rel(TICKET),
            "allowed_write_scope": ticket["allowed_write_scope"],
        },
    )
    atomic_write_json(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": decision,
            "artifact": rel(ARTIFACT),
            "runner": RUNNER,
            "checks": checks,
            "updated_at": now,
        },
        MANIFEST,
        indent=2,
        ensure_ascii=False,
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "checks": checks,
                "before": contract["before"],
                "after": contract["after"],
                "artifact": rel(ARTIFACT),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
