"""exp-20260703-004: observer-only prediction-market event surface.

Measurement repair only. The alpha hypothesis is that public prediction-market
probability jumps can timestamp entity/theme events before ticker-scoped news
classification, but the repo did not have an append-only observer surface for
those rows. This experiment adds and verifies that surface without changing
trading behavior.
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
from prediction_market_event_observer import (  # noqa: E402
    OBSERVER_NAME,
    PREDICTION_MARKET_SOURCE_SPECS,
    get_prediction_market_observer_sources,
    persist_prediction_market_event_observer,
)

EXPERIMENT_ID = "exp-20260703-004"
OWNER = "alpha-explore"
SLUG = "prediction_market_event_observer"
RUNNER = f"quant/experiments/exp_20260703_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
PROBE_DATE = "20260703"

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OBSERVER_PY = REPO_ROOT / "quant" / "prediction_market_event_observer.py"
TEST_OBSERVER_PY = REPO_ROOT / "quant" / "test_prediction_market_event_observer.py"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
PROBE_DATA_DIR = DATA_DIR / "observer_probe"
OUT_JSON = DATA_DIR / f"exp_20260703_004_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

PROBE_ITEMS = (
    PROBE_DATA_DIR
    / "non_ohlcv"
    / OBSERVER_NAME
    / "daily"
    / f"{OBSERVER_NAME}_{PROBE_DATE}.json"
)
PROBE_SOURCE_STATS = (
    PROBE_DATA_DIR
    / "non_ohlcv"
    / OBSERVER_NAME
    / "source_stats"
    / f"{OBSERVER_NAME}_source_stats_{PROBE_DATE}.json"
)
PROBE_SOURCE_MANIFEST = (
    PROBE_DATA_DIR / "non_ohlcv" / OBSERVER_NAME / "source_manifest.json"
)
PROBE_LATEST_SUMMARY = (
    PROBE_DATA_DIR / "non_ohlcv" / OBSERVER_NAME / "latest_summary.json"
)

CHANGED_FILES = [
    "quant/prediction_market_event_observer.py",
    "quant/test_prediction_market_event_observer.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_004_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/observer_probe/non_ohlcv/{OBSERVER_NAME}/daily/{OBSERVER_NAME}_{PROBE_DATE}.json",
    f"data/experiments/{EXPERIMENT_ID}/observer_probe/non_ohlcv/{OBSERVER_NAME}/source_stats/{OBSERVER_NAME}_source_stats_{PROBE_DATE}.json",
    f"data/experiments/{EXPERIMENT_ID}/observer_probe/non_ohlcv/{OBSERVER_NAME}/source_manifest.json",
    f"data/experiments/{EXPERIMENT_ID}/observer_probe/non_ohlcv/{OBSERVER_NAME}/latest_summary.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\prediction_market_event_observer.py quant\\test_prediction_market_event_observer.py quant\\experiments\\exp_20260703_004_prediction_market_event_observer.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_prediction_market_event_observer.py -q",
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


def _probe_fetch(url: str, params: dict[str, Any], timeout_seconds: float = 10.0) -> dict:
    query = str(params.get("search") or "prediction market event")
    slug = query.lower().replace(" ", "-")[:80]
    return {
        "events": [
            {
                "id": f"event-{len(query)}-{abs(hash(query)) % 100000}",
                "slug": slug,
                "title": query,
                "markets": [
                    {
                        "id": f"market-{abs(hash((url, query))) % 100000}",
                        "question": f"Will {query} occur?",
                        "outcomes": '["Yes","No"]',
                        "outcomePrices": '["0.31","0.69"]',
                        "volume": "100000",
                        "liquidity": "25000",
                        "active": True,
                        "closed": False,
                    }
                ],
            }
        ]
    }


def verify_observer() -> dict[str, Any]:
    observer_text = OBSERVER_PY.read_text(encoding="utf-8")
    test_text = TEST_OBSERVER_PY.read_text(encoding="utf-8")
    sources = get_prediction_market_observer_sources()
    probe_summary = persist_prediction_market_event_observer(
        PROBE_DATE,
        data_dir=PROBE_DATA_DIR,
        fetch_func=_probe_fetch,
    )
    items = json.loads(PROBE_ITEMS.read_text(encoding="utf-8"))
    source_stats = json.loads(PROBE_SOURCE_STATS.read_text(encoding="utf-8"))
    checks = {
        "observer_module_exists": OBSERVER_PY.exists(),
        "source_specs_populated": len(PREDICTION_MARKET_SOURCE_SPECS) >= 5,
        "sources_are_observer_only": all(
            source.get("metadata", {}).get("observer_only") is True
            for source in sources
        ),
        "provider_is_polymarket": all(
            source.get("metadata", {}).get("provider") == "polymarket"
            for source in sources
        ),
        "candidate_tickers_present": all(
            source.get("metadata", {}).get("candidate_tickers") for source in sources
        ),
        "observer_writes_separate_non_ohlcv_artifacts": (
            "non_ohlcv" in observer_text and "clean_trade_news" not in observer_text
        ),
        "persistence_probe_wrote_artifacts": all(
            path.exists()
            for path in (
                PROBE_ITEMS,
                PROBE_SOURCE_STATS,
                PROBE_SOURCE_MANIFEST,
                PROBE_LATEST_SUMMARY,
            )
        ),
        "persistence_probe_no_source_errors": probe_summary["source_error_count"] == 0,
        "persistence_probe_item_count_matches_sources": (
            probe_summary["unique_item_count"] == len(sources)
        ),
        "persistence_probe_probabilities_present": all(
            item.get("yes_probability") is not None for item in items
        ),
        "persistence_probe_strategy_unchanged": (
            probe_summary["strategy_behavior_changed"] is False
            and probe_summary["trade_enabled"] is False
            and probe_summary["alters_orders"] is False
        ),
        "success_test_exists": (
            "test_persist_prediction_market_event_observer_writes_separate_artifacts"
            in test_text
        ),
        "failure_test_exists": (
            "test_persist_prediction_market_event_observer_records_source_errors"
            in test_text
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
        "probe_summary": probe_summary,
        "probe_item_count": len(items),
        "probe_source_stats_count": len(source_stats),
        "probe_items_sample": items[:3],
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON)
    baseline = baseline_summary()
    verification = verify_observer()
    status = "accepted_measurement_repair" if verification["passed"] else "blocked"
    accepted = bool(verification["passed"])
    decision = (
        "accepted_measurement_repair_prediction_market_event_observer_surface"
        if accepted
        else "blocked_prediction_market_event_observer_surface_not_verified"
    )
    predicted = ticket.get("prediction") or {}
    predicted_prob = predicted.get("success_probability")
    actual_success = 1 if accepted else 0
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
            "Prediction-market event probability jumps may provide earlier "
            "point-in-time timing for entity/theme event propagation into "
            "listed exposure tickers."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "daily_news_llm_event_scoring_alpha",
        "trial_family": "prediction_market_event_observer_surface",
        "trial_variant_id": "prediction_market_event_observer_surface_v1",
        "single_causal_variable": "prediction_market_event_observer_surface_v1",
        "changed_variable": "prediction_market_event_observer_surface_v1",
        "causal_components": [
            "prediction-market source manifest",
            "observer-only public market/event fetch",
            "separate non-OHLCV artifacts",
            "source diagnostics",
            "fail-soft persistence",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260703-001",
            "exp-20260702-020",
            "exp-20260702-021",
            "exp-20260702-026",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_prediction_market_event_probability_source",
        "new_evidence_axis": (
            "New source axis: public prediction-market event/market probability "
            "rows, not RSS/news keyword reslice, not SEC event field, and not "
            "the existing second-order news ledger."
        ),
        "source_reference": {
            "provider": "polymarket",
            "docs": [
                "https://docs.polymarket.com/",
                "https://docs.polymarket.com/llms.txt",
            ],
            "note": (
                "Official docs expose public event, search, and market-data "
                "interfaces; this experiment uses a fake-fetch probe and does "
                "not depend on live network availability."
            ),
        },
        "observer_contract": {
            "source_count": verification["source_count"],
            "query_ids": verification["query_ids"],
            "candidate_ticker_count": verification["candidate_ticker_count"],
            "artifact_root": f"data/non_ohlcv/{OBSERVER_NAME}",
            "observer_only": True,
            "provider": "polymarket",
            "probe_summary": verification["probe_summary"],
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": verification["passed"],
            "fields": [
                "prediction_market_query_id",
                "provider_event_id",
                "provider_market_id",
                "title",
                "question",
                "yes_probability",
                "candidate_tickers",
                "observed_at",
                "observer_only",
            ],
            "wiring_checks": verification["checks"],
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
            "mode": "measurement_repair_identity_plus_observer_probe",
            "passed": accepted,
            "failed_reasons": [
                key for key, value in verification["checks"].items() if not value
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
            "run_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_exposed": False,
            "observer_cli_available": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "The new observer is importable and has a CLI, but it is not "
                "wired into run.py and does not feed prompts, clean_trade_news, "
                "ranking, sizing, exits, or orders."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The blocker was lack of a PIT probability source surface, not "
                "a strategy rule. The fix adds a fixed source manifest, "
                "Polymarket-style payload parser, separate non-OHLCV artifacts, "
                "and fail-soft diagnostics."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another experiment to reslice the same source "
                "manifest by adjacent theme labels or one-off hand refreshes. "
                "Next evidence must be real accumulated rows, daily pipeline "
                "wiring, or a materially different event-probability source."
            ),
            "new_evidence_required": (
                "Current rows with non-null probabilities plus subsequent "
                "entity-exposure forward settlement, or a daily run.py wiring "
                "measurement repair that makes rows accumulate automatically."
            ),
        },
        "next_retry_requires": [
            "daily pipeline wiring if routine rows should accumulate automatically",
            "or enough closed forward rows to test event-probability jump value",
            "or a materially different prediction-market/probability source",
        ],
        "prediction": predicted,
        "calibration": {
            "actual_decision": status,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_prob,
            "brier_score": (
                round((float(predicted_prob) - actual_success) ** 2, 4)
                if predicted_prob is not None
                else None
            ),
            "predicted_failure_modes": predicted.get("main_failure_modes", []),
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "The isolated observer surface verified cleanly with fake-fetch "
                "payloads and left all trading behavior unchanged."
                if accepted
                else "At least one observer contract check failed; see Gate 2."
            ),
        },
        "verification": verification,
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
        "source_reference",
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
- Gate 2 observer verified: `{payload["gate2"]["passed"]}`
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
            "source_reference": payload["source_reference"],
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
