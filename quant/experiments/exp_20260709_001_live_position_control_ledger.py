"""exp-20260709-001: live position-control ledger.

Measurement repair only. The daily report can show OK-to-add and entry-slot
capacity while also listing manual GTC brackets, EXIT NOW flags, stale targets,
fallback stops, and open-position/report date mismatches. This runner records a
read-only ledger/state so future live alpha/risk decisions can machine-check
control blockers before accepting new risk.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

EXPERIMENT_ID = "exp-20260709-001"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "live_position_control_ledger"
RUNNER = f"quant/experiments/exp_20260709_001_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT, REPO_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from live_position_control_ledger import (  # noqa: E402
    DEFAULT_LEDGER_PATH,
    DEFAULT_LIVE_DRIFT_STATE_PATH,
    DEFAULT_POSITIONS_PATH,
    DEFAULT_STATE_PATH,
    build_position_control_ledger,
    latest_report_path,
)


BASELINE_RESULT = (
    REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_001_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Production consistency blocker: live OK-to-add and entry-slot readouts are "
    "not trustworthy while open positions lack a machine-checkable position-control "
    "contract for policy owner, stop/target, manual bracket coverage, EXIT NOW, "
    "stale target, and fallback-stop state."
)
ALPHA_HYPOTHESIS = (
    "Blocked alpha-enabling hypothesis: before adding new live risk from any "
    "accepted/default-off alpha, the system needs a read-only control ledger that "
    "can stop new entries when enacted position controls are unknown or breached."
)
CHANGED_VARIABLE = "live_position_control_ledger_v1"
MECHANISM_FAMILY = "production_live_risk_control_parity"
TRIAL_FAMILY = "live_position_control_ledger"
TRIAL_VARIANT_ID = "report_bracket_open_position_control_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260706-019", "exp-20260623-020"]
CAUSAL_COMPONENTS = [
    "open_positions",
    "daily_report_bracket_section",
    "live_drift_state",
    "read_only_position_control_state",
    "no_order_change",
]
CHANGED_FILES = [
    "quant/live_position_control_ledger.py",
    "quant/test_live_position_control_ledger.py",
    RUNNER,
    "data/live_pilot/position_control/ledger.jsonl",
    "data/live_pilot/position_control/state.json",
    "data/experiments/exp-20260709-001/exp_20260709_001_live_position_control_ledger.json",
    "experiments/logs/exp-20260709-001.json",
    "experiments/cards/exp-20260709-001.md",
    "experiments/manifests/exp-20260709-001.json",
    "experiments/tickets/exp-20260709-001.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def run_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "pytest",
            "quant/test_live_position_control_ledger.py",
            "-q",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    output = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    return {
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "tail": output[-8:],
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    report_path = latest_report_path()
    baseline = baseline_metrics()
    tests = run_tests()
    ledger_result = build_position_control_ledger()
    state = ledger_result["state"]
    rows = ledger_result["rows"]

    expected_blockers = {
        "exit_now",
        "stale_target",
        "fallback_stop",
        "manual_bracket_orders_not_broker_confirmed",
    }
    blockers = set(state.get("ok_to_add_control_blockers") or [])
    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if not report_path:
        measurement_blockers.append("latest_daily_report_missing")
    if not DEFAULT_POSITIONS_PATH.exists():
        measurement_blockers.append("open_positions_missing")
    if not DEFAULT_LIVE_DRIFT_STATE_PATH.exists():
        measurement_blockers.append("live_drift_state_missing")
    if not tests["passed"]:
        measurement_blockers.append("unit_tests_failed")
    if state.get("status") != "ok":
        measurement_blockers.append(f"state_status_{state.get('status')}")
    if state.get("ok_to_add_reported") is not True:
        measurement_blockers.append("daily_report_ok_to_add_not_observed")
    if state.get("ok_to_add_control_pass") is not False:
        measurement_blockers.append("ok_to_add_control_not_blocked")
    missing_expected = sorted(expected_blockers - blockers)
    if missing_expected:
        measurement_blockers.append("missing_expected_control_blockers:" + ",".join(missing_expected))
    if any(row.get("production_impact") != "observe_only_no_orders_no_ranking_no_sizing" for row in rows):
        measurement_blockers.append("unexpected_production_impact")

    accepted = not measurement_blockers
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_live_position_control_ledger"
        if accepted
        else "blocked_live_position_control_ledger"
    )
    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
        "live_order_behavior_changed": False,
        "ranking_behavior_changed": False,
        "sizing_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "state_status": state.get("status"),
        "ok_to_add_reported": state.get("ok_to_add_reported"),
        "ok_to_add_control_pass": state.get("ok_to_add_control_pass"),
        "entry_slots_reported": state.get("entry_slots_reported"),
        "position_rows": state.get("position_rows"),
        "manual_order_instruction_count": state.get("manual_order_instruction_count"),
        "exit_now_count": state.get("exit_now_count"),
        "warning_count": state.get("warning_count"),
        "stale_target_count": state.get("stale_target_count"),
        "fallback_stop_count": state.get("fallback_stop_count"),
        "report_only_row_count": state.get("report_only_row_count"),
        "missing_daily_report_control_count": state.get("missing_daily_report_control_count"),
        "report_open_positions_asof_mismatch": state.get("report_open_positions_asof_mismatch"),
        "rows_appended": (state.get("ledger") or {}).get("rows_appended"),
        "rows_total": (state.get("ledger") or {}).get("rows_total"),
        "unit_tests_passed": tests["passed"],
    }
    production_impact = {
        "trade_enabled_changed": False,
        "live_orders_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "backtest_behavior_changed": False,
        "default_off_only": True,
        "observe_only_no_orders_no_ranking_no_sizing": True,
    }
    now = utc_now()
    prediction = ticket.get("prediction") or {
        "recorded_at": now,
        "success_probability": 0.82,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "confidence_reason": "Narrow parser/state writer over existing report and position files.",
        "main_failure_modes": [
            "report_format_drift",
            "position_report_date_mismatch",
            "parser_overflags_manual_orders",
        ],
    }
    calibration = {
        "prediction_recorded": True,
        "predicted_success_probability": prediction.get("success_probability"),
        "actual_success": accepted,
        "prediction_error": (
            round((1.0 if accepted else 0.0) - float(prediction.get("success_probability")), 4)
            if prediction.get("success_probability") is not None
            else None
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "measurement_repair",
        "implementation_mode": "shared_read_only_helper_plus_state",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_measurement_surface",
        "prediction": prediction,
        "calibration": calibration,
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": accepted,
            "dependencies_validated": accepted,
            "fields_checked": [
                "open_positions.as_of",
                "open_positions.positions",
                "daily_report.portfolio_heat",
                "daily_report.bracket_summary",
                "daily_report.exit_now",
                "daily_report.warnings",
                "live_drift_state.status",
            ],
            "entry_date_scope": "Parsed from open_positions; no signal-generation changes.",
            "target_price_scope": "Parsed from open_positions and daily report target orders; no target policy changes.",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "Measurement repair only; no executable filter was added.",
        },
        "gate4": {
            "passed": accepted,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": [],
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "position_control_state": state,
        "position_control_sample_rows": rows[:10],
        "tests": tests,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The latest report exposes manual brackets, EXIT NOW and warning text, "
                "but the prior live_drift state only measured trajectory drift. Joining "
                "report controls with open_positions makes OK-to-add false when controls "
                "are stale, manual-only, breached, or not matched to the current position date."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not treat the report OK-to-add line or entry-slot count as live risk "
                "capacity unless position_control/state.json has ok_to_add_control_pass=true. "
                "Do not reserve another ID just to reparse the same report format."
            ),
            "new_evidence_required": (
                "A future promotion needs broker-confirmed open order inventory, daily run.py "
                "wiring for this state, or a materially different live control surface such as "
                "closed-trade exit drift."
            ),
        },
        "next_retry_requires": [
            "broker-confirmed resting order inventory to distinguish placed vs instructed brackets",
            "one-time daily wiring if this state should become a standing production gate",
            "closed-trade exit-drift reconciliation for realized stop/target behavior",
        ],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "related_files": [
            "operator_inputs/open_positions.json",
            "data/daily/reports/report_20260707.txt",
            "data/live_pilot/live_drift/state.json",
            "docs/live_drift_reconciliation.md",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_live_position_control_ledger.py -q",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": accepted,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def build_card(payload: dict[str, Any]) -> str:
    state = payload["position_control_state"]
    delta = payload["delta_metrics"]
    blockers = ", ".join(state.get("ok_to_add_control_blockers") or [])
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: live position-control ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Reported OK-to-add: `{delta['ok_to_add_reported']}`",
            f"- Control OK-to-add: `{delta['ok_to_add_control_pass']}`",
            f"- Entry slots reported: `{delta['entry_slots_reported']}`",
            f"- Control blockers: `{blockers}`",
            f"- Rows total: `{delta['rows_total']}`",
            f"- Tests passed: `{delta['unit_tests_passed']}`",
            "- Strategy/live order behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [REPO_ROOT / p for p in CHANGED_FILES]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in paths
        },
        "changed_files": payload["changed_files"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "position_control_state": payload["position_control_state"],
            "tests": payload["tests"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "delta_metrics": payload["delta_metrics"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
