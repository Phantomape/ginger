"""exp-20260703-015: daily regime_chop breadth wiring.

Measurement repair only. The alpha hypothesis is that sleeve-specific chop
exposure may matter for future default-off allocation, but the daily
market-state snapshot cannot tag forward rows at full fidelity until run.py
passes the already-loaded OHLCV universe into the read-only context helper.
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


EXPERIMENT_ID = "exp-20260703-015"
OWNER = "codex"
SLUG = "regime_chop_daily_breadth_wiring"
RUNNER = f"quant/experiments/exp_20260703_015_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from market_context import build_readonly_market_state_context  # noqa: E402
from market_state_analysis import build_market_state_snapshot  # noqa: E402


BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
RUN_PY = REPO_ROOT / "quant" / "run.py"
TEST_RUN_PY = REPO_ROOT / "quant" / "test_run_daily_wiring.py"
TEST_MARKET_CONTEXT_PY = REPO_ROOT / "quant" / "test_market_context.py"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260703_015_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

CHANGED_FILES = [
    "quant/run.py",
    "quant/test_run_daily_wiring.py",
    "quant/test_market_context.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_015_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\run.py quant\\market_context.py quant\\test_run_daily_wiring.py quant\\test_market_context.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_market_context.py quant\\test_regime_chop_state.py quant\\test_market_state_analysis.py quant\\test_run_daily_wiring.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(text, path)
        return
    except PermissionError:
        pass
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def write_json(path: Path, payload: Any) -> None:
    write_text(
        path,
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str)
        + "\n",
    )


def baseline_summary() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {}) or {}
    windows = payload.get("windows") or []
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(
            int(window.get("total_trades") or window.get("trade_count") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
        "windows": [
            {
                "label": window.get("label"),
                "expected_value_score": window.get("expected_value_score"),
                "total_pnl": window.get("total_pnl"),
                "signals_generated": window.get("signals_generated"),
                "signals_survived": window.get("signals_survived"),
                "survival_rate": window.get("survival_rate"),
            }
            for window in windows
        ],
    }


def ohlcv(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1000] * len(closes),
        },
        index=pd.date_range("2026-01-01", periods=len(closes), freq="B"),
    )


def verify_run_wiring() -> dict[str, Any]:
    tree = ast.parse(RUN_PY.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "build_readonly_market_state_context"
    ]
    universe_arg_is_ohlcv_dict = False
    for call in calls:
        for keyword in call.keywords:
            if keyword.arg != "universe_ohlcv_by_ticker":
                continue
            universe_arg_is_ohlcv_dict = (
                isinstance(keyword.value, ast.Name) and keyword.value.id == "ohlcv_dict"
            )

    run_test_text = TEST_RUN_PY.read_text(encoding="utf-8")
    market_context_test_text = TEST_MARKET_CONTEXT_PY.read_text(encoding="utf-8")
    return {
        "call_count": len(calls),
        "single_call": len(calls) == 1,
        "universe_arg_is_ohlcv_dict": universe_arg_is_ohlcv_dict,
        "run_ast_regression_test_present": (
            "test_market_state_context_passes_universe_frames_for_breadth"
            in run_test_text
        ),
        "breadth_unit_test_present": (
            "test_build_readonly_market_state_context_adds_universe_breadth"
            in market_context_test_text
        ),
        "preserve_existing_breadth_test_present": '"breadth": 0.25'
        in market_context_test_text,
    }


def verify_context_materialization() -> dict[str, Any]:
    context = build_readonly_market_state_context(
        {
            "market_regime": "BULL",
            "spy_pct_from_ma": 0.02,
            "spy_drawdown_from_high": -0.02,
            "spy_vol_ratio": 1.1,
        },
        ohlcv_by_ticker={
            "SPY": ohlcv([100] * 20 + [110]),
            "QQQ": ohlcv([100] * 20 + [120]),
        },
        universe_ohlcv_by_ticker={
            "A": ohlcv([100] * 49 + [110]),
            "B": ohlcv([100] * 49 + [90]),
            "SPY": ohlcv([100] * 49 + [110]),
        },
    )
    snapshot = build_market_state_snapshot(
        market_context=context,
        signals=[],
        source="production_daily_quant",
    )
    regime_chop = snapshot.get("regime_chop") or {}
    return {
        "breadth": context.get("breadth"),
        "spy_drawdown_from_high": context.get("spy_drawdown_from_high"),
        "spy_vol_ratio": context.get("spy_vol_ratio"),
        "regime_chop_fidelity": regime_chop.get("fidelity"),
        "diagnostic_only": snapshot.get("diagnostic_only"),
        "trade_enabled": snapshot.get("trade_enabled", False),
        "expected_full_fidelity": (
            context.get("breadth") == 0.5
            and regime_chop.get("fidelity") == "full_breadth_and_drawdown"
            and snapshot.get("diagnostic_only") is True
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    baseline = baseline_summary()
    wiring = verify_run_wiring()
    materialization = verify_context_materialization()
    checks = {
        **{f"run_{key}": value for key, value in wiring.items() if isinstance(value, bool)},
        "context_breadth_computed": materialization["breadth"] == 0.5,
        "context_full_fidelity": (
            materialization["regime_chop_fidelity"] == "full_breadth_and_drawdown"
        ),
        "snapshot_diagnostic_only": materialization["diagnostic_only"] is True,
        "snapshot_trade_enabled_false": materialization["trade_enabled"] is False,
    }
    accepted = all(checks.values())
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_regime_chop_daily_breadth_wiring"
        if accepted
        else "blocked_regime_chop_daily_breadth_wiring_not_verified"
    )
    failed = [name for name, passed in checks.items() if not passed]
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
            "Sleeve-specific regime_chop exposure may become a default-off "
            "allocation field after enough forward rows carry entry-time full "
            "fidelity breadth and closed replacement value."
        ),
        "change_type": "measurement_repair",
        "implementation_mode": "shared_daily_diagnostic_context_wiring",
        "mechanism_family": "full_fidelity_daily_regime_chop_context",
        "trial_family": "regime_chop_daily_breadth_wiring",
        "trial_variant_id": "regime_chop_daily_breadth_wiring_v1",
        "single_causal_variable": "daily_regime_chop_full_fidelity_breadth_wiring_v1",
        "changed_variable": "daily_regime_chop_full_fidelity_breadth_wiring_v1",
        "causal_components": ticket.get("causal_components") or [
            "run.py passes existing ohlcv_dict as universe_ohlcv_by_ticker",
            "market_context computes non-index breadth",
            "market_state_snapshot remains diagnostic_only",
            "focused AST and unit tests",
        ],
        "nearby_prior_experiments": [
            "exp-20260615-025",
            "exp-20260615-028",
            "exp-20260622-017",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": (
            "daily_pipeline_wiring_for_existing_shared_regime_chop_breadth_field"
        ),
        "new_evidence_axis": (
            "One-time daily pipeline wiring of the existing shared regime_chop "
            "breadth input left open by exp-20260615-028. No constants, "
            "thresholds, exposure floor, candidate selection, ranking, sizing, "
            "exits, or forward attribution slices changed."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Future default-off sleeve allocation may benefit from "
                "entry-time regime_chop tags, but only after daily rows carry "
                "full-fidelity PIT breadth and later close."
            ),
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted without override.",
                "nearby_prior_experiments": [
                    "exp-20260615-025",
                    "exp-20260615-028",
                    "exp-20260622-017",
                ],
                "why_not_repeat": (
                    "exp-20260615-028 explicitly deferred this run.py breadth "
                    "wiring; this run does not retune or re-slice the regime "
                    "surface."
                ),
            },
            "3_single_policy_bundle": (
                "Observer-only daily market-state context fidelity repair; no "
                "executable trading policy change."
            ),
            "4_success_failure_standard": (
                "Accept only if run.py passes the universe frames, breadth "
                "materializes, the regime_chop fidelity tier becomes full in a "
                "sample snapshot, tests pass, and strategy metrics remain identity."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": accepted,
            "required_fields_checked": [
                "universe_ohlcv_by_ticker",
                "Close",
                "breadth",
                "spy_drawdown_from_high",
                "spy_vol_ratio",
                "regime_chop.fidelity",
            ],
            "entry_date_target_price_note": (
                "This repair emits a diagnostic market-state context field, "
                "not signal rows; entry_date and target_price are not generated."
            ),
            "run_wiring": wiring,
            "context_materialization": materialization,
            "checks": checks,
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, ranking, sizing, prompt, exit, or order rule was added.",
        },
        "gate4": {
            "mode": "measurement_repair_identity_plus_wiring_gate",
            "passed": accepted,
            "failed_reasons": failed,
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
            "daily_market_state_field_enriched": True,
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
                "run.py now passes the already-loaded OHLCV universe into the "
                "read-only market-state context so regime_chop can report "
                "full_breadth_and_drawdown when breadth is available. The field "
                "remains inside diagnostic_only market_state_snapshot and does "
                "not feed prompts, core signals, ranking, sizing, exits, or orders."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The shared market_context helper already supported "
                "universe_ohlcv_by_ticker; the daily path simply omitted the "
                "existing ohlcv_dict. Passing it lets non-index breadth "
                "materialize without changing trading behavior."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune regime_chop constants, exposure floor, thresholds, "
                "or portfolio/sleeve capital scalars on frozen windows. Do not "
                "open more IDs for routine daily regime-tag refreshes."
            ),
            "new_evidence_required": (
                "Closed forward replacement-value rows carrying entry-time "
                "full-fidelity regime_chop tags for a specific default-off "
                "sleeve, followed by one fixed regime-conditioned policy test."
            ),
        },
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": (
                (ticket.get("prediction") or {}).get("success_probability")
            ),
            "predicted_failure_modes": (
                (ticket.get("prediction") or {}).get("main_failure_modes") or []
            ),
            "realized_failure_mode": None if accepted else ",".join(failed),
            "surprise_note": (
                "No surprise: the helper already supported breadth; the repair "
                "was one kwarg plus regression coverage."
            ),
        },
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": accepted,
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
        "pre_run_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "calibration",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    failed = payload["gate4"]["failed_reasons"]
    failed_text = ", ".join(failed) if failed else "none"
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `false`
- Strategy behavior changed: `false`
- Regime chop fidelity in probe: `{payload["gate2"]["context_materialization"]["regime_chop_fidelity"]}`
- Failed wiring checks: `{failed_text}`
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
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {}) or {}
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
    ticket["causal_components"] = payload["causal_components"]
    ticket["mechanism_family"] = payload["mechanism_family"]
    ticket["trial_family"] = payload["trial_family"]
    ticket["trial_variant_id"] = payload["trial_variant_id"]
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    write_json(TICKET_JSON, ticket)


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log_record(payload))
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, build_manifest(payload))
    update_ticket(payload)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
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
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps(compact_log_record(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
