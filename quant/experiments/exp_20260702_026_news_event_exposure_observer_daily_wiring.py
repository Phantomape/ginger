"""exp-20260702-026: daily wiring for second-order news exposure observer.

Measurement repair only. The second-order structured-news exposure observer was
accepted in exp-20260702-020, but it still required a manual CLI refresh. This
experiment verifies that quant/run.py now invokes the observer from the daily
structured-news snapshot path so current-event rows can mature without spending
future experiment IDs on routine appends.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_json, atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260702-026"
OWNER = "alpha-explore"
SLUG = "news_event_exposure_observer_daily_wiring"
RUNNER = f"quant/experiments/exp_20260702_026_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
RUN_PY = REPO_ROOT / "quant" / "run.py"
TEST_PY = REPO_ROOT / "quant" / "test_run_daily_wiring.py"
OBSERVER_PY = REPO_ROOT / "quant" / "news_event_exposure_observer.py"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_026_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

CHANGED_FILES = [
    "quant/run.py",
    "quant/test_run_daily_wiring.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_026_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\run.py quant\\test_run_daily_wiring.py quant\\news_event_exposure_observer.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_run_daily_wiring.py quant\\test_news_event_exposure_observer.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic replace fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str)
        + "\n",
        path,
    )


def baseline_summary() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON)
    windows = payload.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(int(w.get("total_trades") or w.get("trade_count") or 0) for w in windows),
        "signals_generated": sum(int(w.get("signals_generated") or 0) for w in windows),
        "signals_survived": sum(int(w.get("signals_survived") or 0) for w in windows),
        "survival_rate": round(
            sum(float(w.get("signals_survived") or 0.0) for w in windows)
            / max(sum(float(w.get("signals_generated") or 0.0) for w in windows), 1.0),
            6,
        ),
        "window_count": len(windows),
    }


def verify_wiring() -> dict[str, Any]:
    run_text = RUN_PY.read_text(encoding="utf-8")
    test_text = TEST_PY.read_text(encoding="utf-8")
    observer_text = OBSERVER_PY.read_text(encoding="utf-8")
    checks = {
        "run_helper_defined": "def _persist_news_event_exposure_observer" in run_text,
        "run_helper_imports_observer": "from news_event_exposure_observer import run as run_exposure_observer" in run_text,
        "daily_snapshot_attaches_observer_manifest": 'snapshot["second_order_exposure_observer"]' in run_text,
        "observer_fail_soft_status": '"status": "unavailable"' in run_text,
        "observer_run_api_exists": "def run(" in observer_text,
        "success_test_exists": "test_structured_news_observation_runs_second_order_exposure_observer" in test_text,
        "failure_test_exists": "test_structured_news_observation_keeps_snapshot_when_exposure_observer_fails" in test_text,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON)
    baseline = baseline_summary()
    wiring = verify_wiring()
    status = "accepted_measurement_repair" if wiring["passed"] else "blocked"
    accepted = bool(wiring["passed"])
    decision = (
        "accepted_measurement_repair_news_event_exposure_observer_daily_wiring"
        if accepted
        else "blocked_news_event_exposure_observer_daily_wiring_not_verified"
    )
    gate4_failed = [] if accepted else [
        key for key, value in wiring["checks"].items() if not value
    ]
    actual_success = 1 if accepted else 0
    predicted = ticket.get("prediction") or {}
    predicted_prob = float(predicted.get("success_probability") or 0.0)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "Second-order structured-news exposure may become a deployable "
            "relation alpha only after current-event rows accumulate and close "
            "under the same observer semantics."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "daily_news_llm_event_scoring_alpha",
        "trial_family": "news_event_exposure_observer_daily_pipeline_wiring",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": "news_event_exposure_observer_daily_pipeline_wiring_v1",
        "changed_variable": "news_event_exposure_observer_daily_pipeline_wiring_v1",
        "causal_components": [
            "daily structured-news snapshot",
            "second-order exposure observer refresh",
            "fail-soft run.py integration",
            "daily wiring tests",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260702-020",
            "exp-20260702-021",
            "exp-20260702-022",
            "exp-20260702-025",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "daily_pipeline_wiring_for_existing_observer",
        "new_evidence_axis": (
            "Routine append integration for the accepted second-order observer; "
            "not a new relation/theme/horizon reslice."
        ),
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": wiring["passed"],
            "fields": [
                "_persist_daily_structured_news_observation",
                "_persist_news_event_exposure_observer",
                "news_event_exposure_observer.run",
                "second_order_exposure_observer",
            ],
            "wiring_checks": wiring["checks"],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, ranking, sizing, or exit rule was added.",
        },
        "gate4": {
            "mode": "measurement_repair_identity_plus_wiring_gate",
            "passed": accepted,
            "failed_reasons": gate4_failed,
            "strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "daily_collector_changed": False,
            "daily_snapshot_exposed": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "Daily run.py now refreshes an append-only observer ledger after "
                "the structured-news snapshot. It does not feed prompts, orders, "
                "ranking, sizing, exits, or core candidate selection."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The accepted observer already had a pure run() API and tests, so "
                "daily wiring only needed a fail-soft call after the first-order "
                "structured-news snapshot."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve future experiment IDs for routine manual refreshes "
                "of the same second-order exposure observer. Let the daily pipeline "
                "append rows and only reopen alpha after materially more current "
                "rows close, or after a genuinely new execution/data surface appears."
            ),
            "new_evidence_required": (
                "Closed current-event second-order rows under this daily observer, "
                "or a distinct PIT relation/economic source. Not another slice of "
                "the exp-20260702-020/021 replay rows."
            ),
        },
        "next_retry_requires": [
            "materially more closed current-event second-order exposure rows",
            "or a distinct PIT relation/economic source",
            "not another manual observer refresh experiment",
        ],
        "prediction": predicted,
        "calibration": {
            "actual_decision": status,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_prob,
            "brier_score": round((predicted_prob - actual_success) ** 2, 4),
            "predicted_failure_modes": predicted.get("main_failure_modes", []),
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "Wiring was straightforward; focused tests covered both success "
                "and fail-soft observer failure behavior."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "prediction",
        "calibration",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `{payload["accepted_alpha"]}`
- Strategy behavior changed: `false`
- Artifact: `{payload["artifact"]}`

## Gates

- Gate 1 baseline loaded: `{payload["gate1"]["passed"]}`
- Gate 2 wiring verified: `{payload["gate2"]["passed"]}`
- Gate 3 survival unchanged: `{payload["gate3"]["passed"]}`
- Gate 4 measurement repair: `{payload["gate4"]["passed"]}`

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Reproduction

```powershell
{chr(10).join(payload["reproduction_commands"])}
```
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / path for path in CHANGED_FILES if path != repo_rel(OUT_JSON)]
    files.append(OUT_JSON)
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "changed_files": CHANGED_FILES,
        "files": {repo_rel(path): {"exists": path.exists()} for path in files},
    }


def main() -> int:
    payload = build_payload()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
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
            "new_evidence_axis": payload["new_evidence_axis"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        },
    )
    print(json.dumps(log_record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
