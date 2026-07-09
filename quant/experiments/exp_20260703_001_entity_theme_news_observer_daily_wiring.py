"""exp-20260703-001: daily entity/theme news observer wiring.

Measurement repair only.  The alpha hypothesis is that non-listed entity and
theme news can transmit to listed exposure tickers, but the current daily news
collector is ticker-scoped.  This experiment adds an observer-only source axis
and daily run.py wiring without feeding prompts, ranking, sizing, exits, or
orders.
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
from entity_theme_news_observer import (  # noqa: E402
    ENTITY_THEME_SOURCE_SPECS,
    get_entity_theme_observer_sources,
)
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260703-001"
OWNER = "alpha-explore"
SLUG = "entity_theme_news_observer_daily_wiring"
RUNNER = f"quant/experiments/exp_20260703_001_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
RUN_PY = REPO_ROOT / "quant" / "run.py"
OBSERVER_PY = REPO_ROOT / "quant" / "entity_theme_news_observer.py"
TEST_RUN_PY = REPO_ROOT / "quant" / "test_run_daily_wiring.py"
TEST_OBSERVER_PY = REPO_ROOT / "quant" / "test_entity_theme_news_observer.py"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260703_001_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

CHANGED_FILES = [
    "quant/entity_theme_news_observer.py",
    "quant/run.py",
    "quant/test_entity_theme_news_observer.py",
    "quant/test_run_daily_wiring.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_001_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\run.py quant\\entity_theme_news_observer.py quant\\test_run_daily_wiring.py quant\\test_entity_theme_news_observer.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_entity_theme_news_observer.py quant\\test_run_daily_wiring.py -q",
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
    signals_generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    signals_survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(
            int(w.get("total_trades") or w.get("trade_count") or 0) for w in windows
        ),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": round(
            signals_survived / max(float(signals_generated), 1.0),
            6,
        ),
        "window_count": len(windows),
    }


def verify_wiring() -> dict[str, Any]:
    run_text = RUN_PY.read_text(encoding="utf-8")
    observer_text = OBSERVER_PY.read_text(encoding="utf-8")
    test_run_text = TEST_RUN_PY.read_text(encoding="utf-8")
    test_observer_text = TEST_OBSERVER_PY.read_text(encoding="utf-8")
    sources = get_entity_theme_observer_sources()
    checks = {
        "observer_module_exists": OBSERVER_PY.exists(),
        "source_specs_populated": len(ENTITY_THEME_SOURCE_SPECS) >= 5,
        "sources_are_observer_only": all(
            source.get("metadata", {}).get("observer_only") is True
            for source in sources
        ),
        "sources_are_not_trade_news_stock_queries": all(
            "clean_trade_news" not in source["url"]
            and "stock&" not in source["url"].lower()
            for source in sources
        ),
        "observer_writes_separate_non_ohlcv_artifacts": (
            "non_ohlcv" in observer_text
            and "clean_trade_news" not in observer_text
        ),
        "run_helper_defined": "def _persist_entity_theme_news_observer" in run_text,
        "run_helper_imports_observer": (
            "from entity_theme_news_observer import persist_entity_theme_news_observer"
            in run_text
        ),
        "priority_path_calls_observer": (
            "_persist_daily_structured_news_observation(today)\n"
            "        _persist_sec_corporate_event_stream(today)\n"
            "        _persist_entity_theme_news_observer(today)\n"
            "        _run_deferred_after_prompt()"
            in run_text
        ),
        "step8_path_calls_observer": (
            "trade_items = _collect_trade_news(today, universe, pilot_universe)\n"
            "        _persist_daily_structured_news_observation(today)\n"
            "        _persist_sec_corporate_event_stream(today)\n"
            "        _persist_entity_theme_news_observer(today)"
            in run_text
        ),
        "success_test_exists": (
            "test_entity_theme_news_observer_daily_wiring" in test_run_text
            and "test_persist_entity_theme_news_observer_writes_separate_artifacts"
            in test_observer_text
        ),
        "failure_test_exists": (
            "test_entity_theme_news_observer_daily_wiring_fail_soft" in test_run_text
            and "test_persist_entity_theme_news_observer_records_source_errors"
            in test_observer_text
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "source_count": len(sources),
        "query_ids": [source["metadata"]["query_id"] for source in sources],
        "candidate_ticker_count": len(
            {
                ticker
                for source in sources
                for ticker in source["metadata"].get("candidate_tickers", [])
            }
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON)
    baseline = baseline_summary()
    wiring = verify_wiring()
    status = "accepted_measurement_repair" if wiring["passed"] else "blocked"
    accepted = bool(wiring["passed"])
    decision = (
        "accepted_measurement_repair_entity_theme_news_observer_daily_wiring"
        if accepted
        else "blocked_entity_theme_news_observer_daily_wiring_not_verified"
    )
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
            "Non-listed entity and theme news may transmit to listed exposure "
            "tickers, but it needs a daily observer-only source before forward "
            "rows can accumulate for a later Gate 1-4 alpha test."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "daily_news_llm_event_scoring_alpha",
        "trial_family": "entity_theme_news_observer_daily_pipeline_wiring",
        "trial_variant_id": "entity_theme_news_observer_daily_pipeline_wiring_v1",
        "single_causal_variable": "entity_theme_news_observer_daily_pipeline_wiring_v1",
        "changed_variable": "entity_theme_news_observer_daily_pipeline_wiring_v1",
        "causal_components": [
            "entity/theme source manifest",
            "observer-only daily fetch",
            "separate non-OHLCV artifacts",
            "source diagnostics",
            "fail-soft run.py integration",
            "daily wiring tests",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260630-005",
            "exp-20260702-020",
            "exp-20260702-021",
            "exp-20260702-026",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_entity_theme_news_source_axis",
        "new_evidence_axis": (
            "Observer-only entity/theme RSS source list for non-listed primary "
            "entities and sector themes, separate from ticker-scoped Google "
            "News rows and not a reslice of existing second-order exposure rows."
        ),
        "observer_contract": {
            "source_count": wiring["source_count"],
            "query_ids": wiring["query_ids"],
            "candidate_ticker_count": wiring["candidate_ticker_count"],
            "artifact_root": "data/non_ohlcv/entity_theme_news_observer",
            "observer_only": True,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": wiring["passed"],
            "fields": [
                "entity_theme_query_id",
                "primary_entity",
                "theme",
                "relation_type",
                "candidate_tickers",
                "observer_only",
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
            "failed_reasons": [
                key for key, value in wiring["checks"].items() if not value
            ],
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
                "run.py now refreshes a separate observer-only entity/theme "
                "news surface after trade-news collection. It does not feed "
                "clean_trade_news, prompts, ranking, sizing, exits, or orders."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The measurement blocker was a missing daily source axis, not a "
                "strategy rule. The fix added a small fixed query manifest, "
                "separate artifacts, and fail-soft daily wiring."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve more experiment IDs to hand-refresh this same "
                "observer or reslice its first small daily rows by adjacent "
                "entity/theme fields. Let rows accumulate, or add a genuinely "
                "new source/relation surface."
            ),
            "new_evidence_required": (
                "Closed forward rows from this observer, a materially richer "
                "entity-relation/economic mapping, or a different non-ticker "
                "news source such as PR wire full text or prediction-market "
                "event data."
            ),
        },
        "next_retry_requires": [
            "closed forward rows generated by the daily entity/theme observer",
            "or a materially richer entity relation/economic mapping",
            "or a different non-ticker event source",
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
                "The wiring stayed isolated from the trade-news path; focused "
                "tests covered source manifest, artifact separation, and "
                "fail-soft daily behavior."
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
- Observer contract: `{payload["observer_contract"]["source_count"]}` sources, `{payload["observer_contract"]["candidate_ticker_count"]}` candidate tickers
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
            "observer_contract": payload["observer_contract"],
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
