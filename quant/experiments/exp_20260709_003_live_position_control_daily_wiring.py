"""exp-20260709-003: live position-control daily wiring.

Measurement repair only. The prior experiment built a read-only live
position-control ledger, but it still had to be run manually. This runner
records the daily run.py wiring that refreshes that state after the report is
saved and exposes a compact summary in quant_signals.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

EXPERIMENT_ID = "exp-20260709-003"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "live_position_control_daily_wiring"
RUNNER = f"quant/experiments/exp_20260709_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT, REPO_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import run as run_module  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from live_position_control_ledger import latest_report_path  # noqa: E402


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_003_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: accepted/default-off alpha cannot safely add live risk if "
    "the live position-control ledger is only a manual experiment artifact; "
    "wire the existing read-only state into the daily run so OK-to-add blockers "
    "are refreshed every run without changing orders."
)
ALPHA_HYPOTHESIS = (
    "Before promoting any accepted/default-off alpha toward live risk, current "
    "open positions must have a machine-checkable control state that can veto "
    "new risk capacity when stops, targets, or EXIT NOW controls are stale, "
    "manual-only, missing, or breached."
)
CHANGED_VARIABLE = "live_position_control_daily_wiring_v1"
MECHANISM_FAMILY = "production_live_risk_control_parity"
TRIAL_FAMILY = "live_position_control_daily_wiring"
TRIAL_VARIANT_ID = "run_py_post_report_refresh_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260709-001", "exp-20260706-019"]
CAUSAL_COMPONENTS = [
    "daily_report_save_path",
    "live_position_control_ledger_helper",
    "run_py_post_report_refresh",
    "quant_signals_observe_only_summary",
    "no_order_change",
]
CHANGED_FILES = [
    "quant/run.py",
    "quant/test_run_daily_wiring.py",
    RUNNER,
    "data/live_pilot/position_control/ledger.jsonl",
    "data/live_pilot/position_control/state.json",
    "data/experiments/exp-20260709-003/exp_20260709_003_live_position_control_daily_wiring.json",
    "experiments/logs/exp-20260709-003.json",
    "experiments/cards/exp-20260709-003.md",
    "experiments/manifests/exp-20260709-003.json",
    "experiments/tickets/exp-20260709-003.json",
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
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def run_command(args: list[str], timeout: int = 600, env: dict[str, str] | None = None) -> dict[str, Any]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    proc = subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        env=run_env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    return {
        "command": " ".join(args),
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "tail": output[-10:],
    }


def run_syntax_compile(paths: list[str]) -> dict[str, Any]:
    failures = []
    for rel_path in paths:
        path = REPO_ROOT / rel_path
        try:
            compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
        except Exception as exc:  # pragma: no cover - surfaced in artifact.
            failures.append({"path": rel_path, "error": str(exc)})
    return {
        "command": "in-process compile() syntax check",
        "returncode": 0 if not failures else 1,
        "passed": not failures,
        "tail": failures[-10:],
    }


def run_tests() -> dict[str, Any]:
    python = str(REPO_ROOT / ".venv" / "Scripts" / "python.exe")
    return {
        "syntax_compile": run_syntax_compile(
            [
                "quant/run.py",
                "quant/test_run_daily_wiring.py",
                "quant/live_position_control_ledger.py",
            ]
        ),
        "run_daily_wiring": run_command(
            [python, "-B", "-m", "pytest", "quant/test_run_daily_wiring.py", "-q"]
        ),
        "live_position_control": run_command(
            [
                python,
                "-B",
                "-m",
                "pytest",
                "quant/test_live_position_control_ledger.py",
                "-q",
            ]
        ),
    }


def run_daily_wiring_smoke(today_iso: str) -> dict[str, Any]:
    report_path = latest_report_path()
    trend_signals: dict[str, Any] = {}
    summary = run_module._refresh_live_position_control_after_report(
        today_iso,
        trend_signals,
        report_path=str(report_path) if report_path else None,
    )
    return {
        "report_path": repo_rel(report_path) if report_path else None,
        "summary": summary,
        "trend_signals_has_summary": trend_signals.get("live_position_control") is summary,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    now = utc_now()
    today_iso = now[:10]
    baseline = baseline_metrics()
    tests = run_tests()
    smoke = run_daily_wiring_smoke(today_iso)
    summary = smoke["summary"]
    production_impact = summary.get("production_impact") or {}
    all_tests_passed = all(row.get("passed") for row in tests.values())
    expected_false_flags = [
        "alters_signal_generation",
        "alters_candidate_ranking",
        "alters_sizing",
        "alters_orders",
    ]
    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if not all_tests_passed:
        measurement_blockers.append("focused_tests_failed")
    if summary.get("status") not in {"ok", "positions_unavailable", "missing_report"}:
        measurement_blockers.append(f"unexpected_refresh_status:{summary.get('status')}")
    if not smoke.get("trend_signals_has_summary"):
        measurement_blockers.append("trend_signals_summary_not_visible")
    for flag in expected_false_flags:
        if production_impact.get(flag) is not False:
            measurement_blockers.append(f"production_impact_{flag}_not_false")
    if production_impact.get("scope") != "live_position_control_daily_refreshed":
        measurement_blockers.append("production_impact_scope_not_refreshed")

    accepted = not measurement_blockers
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_live_position_control_daily_wiring"
        if accepted
        else "blocked_live_position_control_daily_wiring"
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
    before_metrics = {
        **baseline,
        "measurement_contract": {
            "run_py_live_position_control_daily_wiring": False,
            "quant_signals_observe_only_summary": False,
            "default_off_no_order_impact": True,
        },
    }
    after_metrics = {
        **baseline,
        "measurement_contract": {
            "run_py_live_position_control_daily_wiring": True,
            "quant_signals_observe_only_summary": True,
            "default_off_no_order_impact": True,
        },
    }
    delta_metrics = {
        **strategy_delta,
        "refresh_status": summary.get("status"),
        "ok_to_add_reported": summary.get("ok_to_add_reported"),
        "ok_to_add_control_pass": summary.get("ok_to_add_control_pass"),
        "entry_slots_reported": summary.get("entry_slots_reported"),
        "position_rows": summary.get("position_rows"),
        "rows_appended": summary.get("rows_appended"),
        "rows_total": summary.get("rows_total"),
        "exit_now_count": summary.get("exit_now_count"),
        "manual_order_instruction_count": summary.get("manual_order_instruction_count"),
        "all_tests_passed": all_tests_passed,
    }
    prediction = ticket.get("prediction") or {
        "recorded_at": ticket.get("created_at") or now,
        "success_probability": 0.78,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "confidence_reason": (
            "The read-only helper was accepted in exp-20260709-001 and run.py "
            "already has failure-tolerant daily surface wiring patterns."
        ),
        "main_failure_modes": [
            "daily_report_path_unavailable",
            "report_parser_format_drift",
            "run_py_import_contract_mismatch",
            "snapshot_visibility_missing",
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
        "actual_decision": decision,
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
        "implementation_mode": "run_py_daily_measurement_wiring",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "routine_materialization_pipeline_wiring",
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
                "daily_report_save_path",
                "live_position_control_ledger.build_position_control_ledger",
                "quant_signals.live_position_control",
                "production_impact.alters_orders",
            ],
            "entry_date_scope": "Existing ledger parses open_positions; no signal-generation changes.",
            "target_price_scope": "Existing ledger parses open_positions/report targets; no target policy changes.",
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
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "daily_wiring_smoke": smoke,
        "tests": tests,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "observe_only_no_orders_no_ranking_no_sizing": True,
            "summary_production_impact": production_impact,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The existing ledger helper already returned an idempotent state. "
                "The daily report save path gives run.py a deterministic input, "
                "and the hook can expose the same OK-to-add control result in "
                "trend_signals/quant_signals without touching trading behavior."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not spend another ID on live position-control daily refresh "
                "plumbing. The next valid live-risk control work needs broker-"
                "confirmed resting-order inventory or realized exit-drift evidence."
            ),
            "new_evidence_required": (
                "Broker-confirmed open order inventory, closed-trade exit drift, "
                "or a materially different live control surface."
            ),
        },
        "next_retry_requires": [
            "broker-confirmed resting order inventory",
            "closed-trade exit-drift reconciliation",
            "a concrete release checklist if this state becomes a hard live gate",
        ],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "related_files": [
            "quant/run.py",
            "quant/live_position_control_ledger.py",
            "data/live_pilot/position_control/state.json",
            "data/live_pilot/position_control/ledger.jsonl",
            "data/daily/reports/report_20260707.txt",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_run_daily_wiring.py -q",
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
    delta = payload["delta_metrics"]
    smoke = payload["daily_wiring_smoke"]
    blockers = ", ".join(smoke["summary"].get("ok_to_add_control_blockers") or [])
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: live position-control daily wiring",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Hook status: `{delta['refresh_status']}`",
            f"- Report path: `{smoke.get('report_path')}`",
            f"- Control OK-to-add: `{delta['ok_to_add_control_pass']}`",
            f"- Entry slots reported: `{delta['entry_slots_reported']}`",
            f"- Control blockers: `{blockers}`",
            f"- Rows appended: `{delta['rows_appended']}`",
            f"- Tests passed: `{delta['all_tests_passed']}`",
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
    paths = [REPO_ROOT / path for path in CHANGED_FILES]
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
            "daily_wiring_smoke": payload["daily_wiring_smoke"],
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
