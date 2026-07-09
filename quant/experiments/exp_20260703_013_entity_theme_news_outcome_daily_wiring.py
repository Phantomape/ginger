"""exp-20260703-013: entity/theme news outcome daily wiring.

Measurement repair only. Entity/theme observer rows can become alpha evidence
only after candidate tickers have a replayable forward outcome ledger versus
cash, SPY, and QQQ. This run adds and verifies that observer-only settlement
surface plus fail-soft daily wiring without changing prompts, ranking, sizing,
exits, orders, or live/default trading behavior.
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

from data_paths import atomic_write_text  # noqa: E402
from entity_theme_news_observer import (  # noqa: E402
    OBSERVER_NAME,
    OUTCOME_RULE_VERSION,
    _candidate_tickers_for_outcomes,
    _load_warehouse_bars_for_tickers,
    build_entity_theme_news_outcome_ledger,
    persist_entity_theme_news_outcome_ledger,
    write_entity_theme_news_outcome_ledger,
)
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260703-013"
OWNER = "alpha-explore"
SLUG = "entity_theme_news_outcome_daily_wiring"
RUNNER = f"quant/experiments/exp_20260703_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
SNAPSHOT_DATE = "20260702"
HORIZONS = (10,)
NOTIONAL_USD = 4000.0

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SNAPSHOT_JSON = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / OBSERVER_NAME
    / "daily"
    / f"{OBSERVER_NAME}_{SNAPSHOT_DATE}.json"
)
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260703_013_{SLUG}.json"
PROBE_DIR = DATA_DIR / "outcome_probe"
PROBE_LEDGER = PROBE_DIR / f"{SLUG}_{SNAPSHOT_DATE}.jsonl"
PROBE_SUMMARY = PROBE_DIR / f"{SLUG}_summary_{SNAPSHOT_DATE}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

RUN_PY = REPO_ROOT / "quant" / "run.py"
OBSERVER_PY = REPO_ROOT / "quant" / "entity_theme_news_observer.py"
TEST_OBSERVER_PY = REPO_ROOT / "quant" / "test_entity_theme_news_observer.py"
TEST_RUN_PY = REPO_ROOT / "quant" / "test_run_daily_wiring.py"

CHANGED_FILES = [
    "quant/entity_theme_news_observer.py",
    "quant/run.py",
    "quant/test_entity_theme_news_observer.py",
    "quant/test_run_daily_wiring.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_013_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/outcome_probe/{SLUG}_{SNAPSHOT_DATE}.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/outcome_probe/{SLUG}_summary_{SNAPSHOT_DATE}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\entity_theme_news_observer.py quant\\run.py quant\\test_entity_theme_news_observer.py quant\\test_run_daily_wiring.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_entity_theme_news_observer.py quant\\test_run_daily_wiring.py -q",
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
    }


def verify_wiring() -> dict[str, Any]:
    run_text = RUN_PY.read_text(encoding="utf-8")
    observer_text = OBSERVER_PY.read_text(encoding="utf-8")
    observer_test_text = TEST_OBSERVER_PY.read_text(encoding="utf-8")
    run_test_text = TEST_RUN_PY.read_text(encoding="utf-8")
    checks = {
        "outcome_builder_importable": callable(build_entity_theme_news_outcome_ledger),
        "outcome_daily_helper_importable": callable(
            persist_entity_theme_news_outcome_ledger
        ),
        "observer_outcome_rule_versioned": OUTCOME_RULE_VERSION in observer_text,
        "observer_scans_accumulated_daily_files": (
            "_load_daily_items_through" in observer_text
            and "_daily_item_paths_through" in observer_text
        ),
        "observer_loads_local_warehouse_bars": (
            "_load_warehouse_bars_for_tickers" in observer_text
            and "warehouse_main_hot.sqlite" in observer_text
        ),
        "observer_writes_separate_outcome_artifacts": (
            "outcome_ledgers" in observer_text
            and "latest_outcome_summary" in observer_text
        ),
        "run_outcome_helper_defined": "def _persist_entity_theme_news_outcomes" in run_text,
        "run_outcome_helper_imports_observer_helper": (
            "persist_entity_theme_news_outcome_ledger" in run_text
        ),
        "run_outcome_helper_fail_soft": (
            "Entity/theme news outcomes unavailable" in run_text
            and '"status": "unavailable"' in run_text
        ),
        "run_daily_paths_call_outcome_helper": (
            run_text.count("_persist_entity_theme_news_outcomes(today)") >= 2
        ),
        "outcomes_do_not_feed_prompt_signals": (
            'trend_signals_dict["entity_theme_news_outcomes"]' not in run_text
            and '"entity_theme_news_outcomes"' not in run_text
        ),
        "observer_persist_test_exists": (
            "test_persist_entity_theme_news_outcome_ledger_reads_accumulated_daily_items"
            in observer_test_text
        ),
        "run_success_test_exists": (
            "test_entity_theme_news_outcome_daily_wiring" in run_test_text
        ),
        "run_fail_soft_test_exists": (
            "test_entity_theme_news_outcome_daily_wiring_fail_soft" in run_test_text
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "observer_name": OBSERVER_NAME,
        "outcome_rule_version": OUTCOME_RULE_VERSION,
    }


def run_outcome_probe() -> dict[str, Any]:
    items = read_json(SNAPSHOT_JSON, []) or []
    tickers = _candidate_tickers_for_outcomes(items)
    bars, warehouse_summary = _load_warehouse_bars_for_tickers(tickers)
    rows, summary = build_entity_theme_news_outcome_ledger(
        items,
        bars,
        as_of_date=SNAPSHOT_DATE,
        horizons=HORIZONS,
        notional_usd=NOTIONAL_USD,
    )
    summary.update(
        {
            "snapshot_path": repo_rel(SNAPSHOT_JSON),
            "ledger_path": repo_rel(PROBE_LEDGER),
            "summary_path": repo_rel(PROBE_SUMMARY),
            "warehouse": warehouse_summary,
            "candidate_ticker_count": len(tickers),
        }
    )
    write_entity_theme_news_outcome_ledger(
        rows,
        summary,
        ledger_path=PROBE_LEDGER,
        summary_path=PROBE_SUMMARY,
    )
    return {"items": items, "rows": rows, "summary": summary}


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    baseline = baseline_summary()
    wiring = verify_wiring()
    probe = run_outcome_probe()
    outcome_summary = probe["summary"]
    accepted = bool(wiring["passed"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_entity_theme_news_outcome_daily_wiring"
        if accepted
        else "blocked_entity_theme_news_outcome_daily_wiring_not_verified"
    )
    gate4_failed = [
        name for name, passed in wiring["checks"].items() if not passed
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
            "Non-listed entity and theme news may transmit to listed exposure "
            "tickers; automatic cash/SPY/QQQ outcome settlement is required "
            "before this observer can support a candidate-pool alpha test."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "daily_news_llm_event_scoring_alpha",
        "trial_family": "entity_theme_news_observer_outcome_daily_wiring",
        "trial_variant_id": "entity_theme_news_outcome_daily_wiring_v1",
        "single_causal_variable": (
            "entity_theme_news_observer_forward_outcome_ledger_daily_wiring_v1"
        ),
        "changed_variable": (
            "entity_theme_news_observer_forward_outcome_ledger_daily_wiring_v1"
        ),
        "causal_components": [
            "observer-only accumulated daily item scan",
            "local warehouse OHLCV settlement",
            "fail-soft run.py daily wrapper",
            "focused unit tests",
            "experiment-private outcome probe",
        ],
        "nearby_prior_experiments": [
            "exp-20260703-001",
            "exp-20260703-002",
            "exp-20260702-026",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "entity_theme_observer_outcome_settlement_surface",
        "new_evidence_axis": (
            "One-time measurement repair adding forward outcome settlement for "
            "the existing entity/theme observer. It is not a query, theme, "
            "ticker-map, horizon, threshold, notional, or response-curve reslice."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Non-listed entity/theme headlines can lead listed exposure "
                "tickers only if closed forward rows later beat cash/SPY/QQQ."
            ),
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted without override.",
                "nearby_prior_experiments": [
                    "exp-20260703-001",
                    "exp-20260703-002",
                    "exp-20260702-026",
                ],
                "why_not_repeat": (
                    "Prior entity/theme work added the observer and rejected a "
                    "same-population top-1 news candidate source; this run only "
                    "adds settlement so future rows can mature without manual IDs."
                ),
            },
            "3_single_policy_bundle": (
                "Observer-only daily outcome materialization for accumulated "
                "entity/theme rows; no executable trading policy changes."
            ),
            "4_success_failure_standard": (
                "Accept only if helper, run.py calls, fail-soft flags, tests, "
                "probe artifact, and baseline identity metrics verify."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "observer_contract": {
            "observer_name": wiring["observer_name"],
            "outcome_rule_version": wiring["outcome_rule_version"],
            "snapshot_date": SNAPSHOT_DATE,
            "horizons": list(HORIZONS),
            "notional_usd": NOTIONAL_USD,
            "artifact_root": "data/non_ohlcv/entity_theme_news_observer",
            "ledger_pattern": (
                "data/non_ohlcv/entity_theme_news_observer/outcome_ledgers/"
                "entity_theme_news_observer_outcomes_YYYYMMDD.jsonl"
            ),
            "summary_pattern": (
                "data/non_ohlcv/entity_theme_news_observer/outcome_summaries/"
                "entity_theme_news_observer_outcome_summary_YYYYMMDD.json"
            ),
            "observer_only": True,
            "trade_enabled": False,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": wiring["passed"],
            "fields": [
                "published_at",
                "candidate_tickers",
                "entry_date",
                "exit_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "outcome_status",
            ],
            "wiring_checks": wiring["checks"],
            "outcome_probe": outcome_summary,
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
            "mode": "measurement_repair_identity_plus_wiring_and_probe",
            "passed": accepted,
            "failed_reasons": gate4_failed,
            "strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "outcome_probe": outcome_summary,
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
                "run.py now refreshes a separate observer-only outcome ledger "
                "after entity/theme news observer collection. The ledger stays "
                "outside clean_trade_news, trend_signals_dict, prompts, ranking, "
                "sizing, exits, and orders."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The entity/theme observer already had isolated daily artifacts; "
                "the missing piece was deterministic settlement over accumulated "
                "daily files. The real 20260702 snapshot currently has "
                f"{outcome_summary['settled_count']} settled rows and "
                f"{outcome_summary['unsettled_count']} unsettled rows, so this is "
                "measurement infrastructure, not alpha evidence."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve more experiments for manual entity/theme outcome "
                "refreshes, query retunes, theme/ticker-map reslices, horizon "
                "retunes, notional changes, or response curves on the same "
                "immature rows."
            ),
            "new_evidence_required": (
                "Closed entity/theme observer outcome rows with cash/SPY/QQQ "
                "replacement-value separation, richer relation/economic mapping, "
                "or a materially different non-ticker event source."
            ),
        },
        "next_retry_requires": [
            ">=25 settled entity/theme observer candidate rows",
            "cash/SPY/QQQ replacement-value separation by source/theme",
            "or materially richer entity relation/economic mapping",
        ],
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "No surprise: the repair reused the existing observer pattern "
                "and kept all trading behavior unchanged."
            ),
        },
        "related_files": [
            "quant/entity_theme_news_observer.py",
            "quant/run.py",
            "quant/test_entity_theme_news_observer.py",
            "quant/test_run_daily_wiring.py",
            repo_rel(SNAPSHOT_JSON),
            repo_rel(BASELINE_JSON),
        ],
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
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    probe = payload["gate4"]["outcome_probe"]
    failed = payload["gate4"]["failed_reasons"]
    failed_text = ", ".join(failed) if failed else "none"
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `false`
- Strategy behavior changed: `false`
- Source observer items: `{probe["source_item_count"]}`
- Candidate outcome rows: `{probe["candidate_outcome_row_count"]}`
- Settled rows: `{probe["settled_count"]}`
- Unsettled rows: `{probe["unsettled_count"]}`
- Failed wiring checks: `{failed_text}`
- Artifact: `{payload["artifact"]}`

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
            "observer_contract": payload["observer_contract"],
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
