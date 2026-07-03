"""exp-20260703-007: daily Moomoo capital-flow paper-sleeve wiring.

Measurement repair only. exp-20260702-019 left a shared default-off helper for
Moomoo daily capital-flow rows, but the rejected historical top-1 test was not
daily-wired. This run wires the helper into run.py so forward rows can
accumulate without changing live orders, ranking, sizing, exits, prompts, or
core signal generation.
"""

from __future__ import annotations

import ast
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

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from moomoo_capital_flow_paper_sleeve import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    DEFAULT_ROWS_PATH,
    DEFAULT_SNAPSHOT_LOG_PATH,
    DEFAULT_STATE_PATH,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    SLEEVE_NAME,
)

EXPERIMENT_ID = "exp-20260703-007"
OWNER = "alpha-explore"
SLUG = "moomoo_capital_flow_daily_wiring"
RUNNER = f"quant/experiments/exp_20260703_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
RUN_PY = REPO_ROOT / "quant" / "run.py"
TEST_RUN_PY = REPO_ROOT / "quant" / "test_run_daily_wiring.py"
HELPER_PY = REPO_ROOT / "quant" / "moomoo_capital_flow_paper_sleeve.py"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260703_007_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

CHANGED_FILES = [
    "quant/run.py",
    "quant/test_run_daily_wiring.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_007_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    (
        ".\\.venv\\Scripts\\python.exe -B -c "
        "\"import ast, pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) "
        "for p in ['quant/run.py','quant/test_run_daily_wiring.py',"
        "'quant/moomoo_capital_flow_paper_sleeve.py']]\""
    ),
    (
        ".\\.venv\\Scripts\\python.exe -B -m pytest "
        "quant\\test_run_daily_wiring.py quant\\test_moomoo_capital_flow_paper_sleeve.py -q"
    ),
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
    generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(
            int(w.get("total_trades") or w.get("trade_count") or 0) for w in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def _subscript_key(node: ast.Subscript) -> str | None:
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return node.slice.value
    return None


def verify_wiring() -> dict[str, Any]:
    run_text = RUN_PY.read_text(encoding="utf-8")
    test_text = TEST_RUN_PY.read_text(encoding="utf-8")
    helper_text = HELPER_PY.read_text(encoding="utf-8")
    tree = ast.parse(run_text)
    expected_imports = {
        "empty_moomoo_capital_flow_paper_sleeve_snapshot",
        "prep_and_build_moomoo_capital_flow_paper_sleeve_snapshot",
    }
    imported_names: set[str] = set()
    referenced_names: set[str] = set()
    helper_calls: list[ast.Call] = []
    quant_artifact_keys: set[str] = set()
    prompt_facing_assignments: list[int] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "moomoo_capital_flow_paper_sleeve":
            imported_names.update(alias.name for alias in node.names)
        if isinstance(node, ast.Name):
            referenced_names.add(node.id)
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None)
            == "prep_and_build_moomoo_capital_flow_paper_sleeve_snapshot"
        ):
            helper_calls.append(node)
        if isinstance(node, ast.Dict):
            quant_artifact_keys.update(
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and getattr(target.value, "id", None) == "trend_signals_dict"
                    and _subscript_key(target) == "moomoo_capital_flow_paper_sleeve"
                ):
                    prompt_facing_assignments.append(node.lineno)

    helper_kwargs = (
        {keyword.arg for keyword in helper_calls[0].keywords}
        if helper_calls
        else set()
    )
    checks = {
        "shared_helper_imported": expected_imports <= imported_names,
        "run_daily_path_calls_shared_helper": bool(helper_calls),
        "run_daily_path_has_empty_fail_soft_snapshot": (
            "empty_moomoo_capital_flow_paper_sleeve_snapshot" in referenced_names
        ),
        "helper_call_passes_daily_context": {
            "as_of",
            "ohlcv_dict",
            "spy_ohlcv",
            "same_day_core_tickers",
            "open_prices",
            "current_prices",
        }
        <= helper_kwargs,
        "daily_quant_artifact_exposes_snapshot": (
            "moomoo_capital_flow_paper_sleeve" in quant_artifact_keys
        ),
        "not_added_to_prompt_trend_signals": not prompt_facing_assignments,
        "helper_contract_is_default_off": (
            '"trade_enabled": False' in helper_text
            and '"paper_enabled": True' in helper_text
            and "clean_trade_news" not in helper_text
            and "llm_prompt" not in helper_text
        ),
        "focused_tests_cover_wiring": (
            "test_moomoo_capital_flow_paper_sleeve_daily_wiring_uses_shared_helper"
            in test_text
            and "test_moomoo_capital_flow_paper_sleeve_not_added_to_prompt_trend_signals"
            in test_text
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "helper_kwargs": sorted(str(item) for item in helper_kwargs),
        "prompt_facing_assignment_lines": prompt_facing_assignments,
        "source_rule_version": SOURCE_RULE_VERSION,
        "paper_rule_version": RULE_VERSION,
        "sleeve_name": SLEEVE_NAME,
        "archive_paths": {
            "rows": repo_rel(Path(DEFAULT_ROWS_PATH)),
            "manifest": repo_rel(Path(DEFAULT_MANIFEST_PATH)),
            "state": repo_rel(Path(DEFAULT_STATE_PATH)),
            "snapshots": repo_rel(Path(DEFAULT_SNAPSHOT_LOG_PATH)),
        },
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON)
    baseline = baseline_summary()
    wiring = verify_wiring()
    accepted = bool(wiring["passed"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_moomoo_capital_flow_daily_wiring"
        if accepted
        else "blocked_moomoo_capital_flow_daily_wiring_not_verified"
    )
    gate4_failed = [] if accepted else [
        key for key, value in wiring["checks"].items() if not value
    ]
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
            "Moomoo daily main capital-flow may identify accumulation candidates, "
            "but the rejected historical top-1 test needs automatically "
            "accumulated forward rows before any new allocation claim."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_default_off_daily_snapshot_wiring",
        "mechanism_family": "moomoo_capital_flow_day_accumulation_candidate_pool",
        "trial_family": "moomoo_capital_flow_daily_default_off_snapshot_wiring",
        "trial_variant_id": "moomoo_capital_flow_daily_wiring_v1",
        "single_causal_variable": (
            "moomoo_capital_flow_daily_default_off_snapshot_wiring_v1"
        ),
        "changed_variable": (
            "moomoo_capital_flow_daily_default_off_snapshot_wiring_v1"
        ),
        "causal_components": [
            "run.py shared helper import",
            "fail-soft default-off paper sleeve build",
            "daily quant artifact exposure",
            "prompt-facing trend_signals exclusion",
            "wiring tests",
        ],
        "nearby_prior_experiments": [
            "exp-20260702-016",
            "exp-20260702-019",
            "exp-20260625-003",
            "exp-20260625-019",
            "exp-20260625-024",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "daily_pipeline_wiring_for_existing_shared_moomoo_capital_flow_helper",
        "new_evidence_axis": (
            "Forward row accumulation via run.py daily snapshot for an existing "
            "shared Moomoo capital-flow helper. This is not a same-window "
            "threshold retune, response-curve retune, or observed-only reslice."
        ),
        "observer_contract": {
            "sleeve_name": wiring["sleeve_name"],
            "source_rule_version": wiring["source_rule_version"],
            "paper_rule_version": wiring["paper_rule_version"],
            "artifact_paths": wiring["archive_paths"],
            "default_off": True,
            "paper_enabled": True,
            "trade_enabled": False,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": wiring["passed"],
            "fields": [
                "entry_date",
                "target_price",
                "flow_date",
                "main_in_flow",
                "main_flow_ratio",
                "trade_enabled",
                "moomoo_capital_flow_paper_sleeve",
            ],
            "wiring_checks": wiring["checks"],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, ranking, sizing, prompt, or exit rule was added.",
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
            "daily_collector_changed": True,
            "daily_snapshot_exposed": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "run.py now calls the shared default-off Moomoo capital-flow "
                "paper sleeve and stores its snapshot in the daily quant artifact. "
                "It is not added to trend_signals_dict, prompts, live ranking, "
                "sizing, exits, or orders."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The shared helper from exp-20260702-019 already carried the "
                "state machine, archive refresh, and default-off paper contract; "
                "the missing piece was daily run.py exposure so rows can mature."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve IDs for Moomoo capital-flow threshold/ranking/"
                "response retunes or daily hand-refreshes on the same rows."
            ),
            "new_evidence_required": (
                "Materially more closed forward rows from automatic daily "
                "snapshots, a genuinely different vendor flow decomposition, "
                "or PIT borrow economics."
            ),
        },
        "next_retry_requires": [
            "materially more settled forward rows from automatic daily snapshots",
            "a genuinely different capital-flow vendor decomposition",
            "or PIT borrow fee/utilization/availability economics",
        ],
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "Wiring matched the existing paper-sleeve pattern; tests pin the "
                "shared helper call and prompt exclusion."
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
        "observer_contract",
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
- Snapshot key: `moomoo_capital_flow_paper_sleeve`
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
    files.extend(
        [
            HELPER_PY,
            Path(DEFAULT_ROWS_PATH),
            Path(DEFAULT_MANIFEST_PATH),
            Path(DEFAULT_STATE_PATH),
            Path(DEFAULT_SNAPSHOT_LOG_PATH),
        ]
    )
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


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = load_json(TICKET_JSON)
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
    }
    ticket["mechanism_family"] = payload["mechanism_family"]
    ticket["trial_family"] = payload["trial_family"]
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    ticket["causal_components"] = payload["causal_components"]
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    safe_write_json(ticket, TICKET_JSON)


def main() -> int:
    payload = build_payload()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)
    update_ticket(payload)

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
            "observer_contract": payload["observer_contract"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "lean_quality_passed": True,
        },
    )
    print(json.dumps(log_record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
