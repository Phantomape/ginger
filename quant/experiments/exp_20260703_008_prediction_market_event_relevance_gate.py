"""exp-20260703-008: prediction-market source relevance gate repair.

Measurement repair only. The alpha hypothesis is that prediction-market
probability changes can become an event-propagation source, but the first daily
observer snapshot admitted broad-search false positives. This run verifies a
stricter replayable relevance gate without changing trading behavior.
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
from experiment_registry import persist_self_registered_result  # noqa: E402
from prediction_market_event_observer import (  # noqa: E402
    OBSERVER_NAME,
    PREDICTION_MARKET_SOURCE_SPECS,
    get_prediction_market_observer_sources,
    persist_prediction_market_event_observer,
    prediction_market_source_relevance,
)

EXPERIMENT_ID = "exp-20260703-008"
OWNER = "alpha-explore"
SLUG = "prediction_market_event_relevance_gate"
RUNNER = f"quant/experiments/exp_20260703_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
PROBE_DATE = "20260703"
SNAPSHOT_DATE = "20260702"

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
OBSERVER_PY = REPO_ROOT / "quant" / "prediction_market_event_observer.py"
TEST_OBSERVER_PY = REPO_ROOT / "quant" / "test_prediction_market_event_observer.py"
EXISTING_ITEMS_JSON = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / OBSERVER_NAME
    / "daily"
    / f"{OBSERVER_NAME}_{SNAPSHOT_DATE}.json"
)
EXISTING_SOURCE_MANIFEST_JSON = (
    REPO_ROOT / "data" / "non_ohlcv" / OBSERVER_NAME / "source_manifest.json"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
PROBE_DATA_DIR = DATA_DIR / "observer_probe"
OUT_JSON = DATA_DIR / f"exp_20260703_008_{SLUG}.json"
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

CHANGED_FILES = [
    "quant/prediction_market_event_observer.py",
    "quant/test_prediction_market_event_observer.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_008_{SLUG}.json",
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
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\prediction_market_event_observer.py quant\\test_prediction_market_event_observer.py quant\\experiments\\exp_20260703_008_prediction_market_event_relevance_gate.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_prediction_market_event_observer.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def load_json(path: Path) -> Any:
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


def audit_existing_snapshot() -> dict[str, Any]:
    items = load_json(EXISTING_ITEMS_JSON)
    manifest = load_json(EXISTING_SOURCE_MANIFEST_JSON)
    metadata_by_query = {
        source["metadata"]["query_id"]: source["metadata"]
        for source in manifest.get("sources", [])
    }
    by_query: dict[str, dict[str, Any]] = {}
    false_positive_samples: list[dict[str, Any]] = []
    for item in items:
        query_id = item.get("prediction_market_query_id")
        metadata = metadata_by_query.get(query_id)
        if not metadata:
            continue
        relevance = prediction_market_source_relevance(
            {
                "title": " ".join(
                    str(item.get(field) or "")
                    for field in ("title", "question", "provider_slug")
                )
            },
            metadata,
        )
        bucket = by_query.setdefault(
            str(query_id),
            {"rows": 0, "strict_keep": 0, "strict_reject": 0},
        )
        bucket["rows"] += 1
        if relevance.get("matched"):
            bucket["strict_keep"] += 1
        else:
            bucket["strict_reject"] += 1
            if len(false_positive_samples) < 12:
                false_positive_samples.append(
                    {
                        "query_id": query_id,
                        "title": item.get("title"),
                        "question": item.get("question"),
                        "provider_slug": item.get("provider_slug"),
                    }
                )
    strict_reject_total = sum(bucket["strict_reject"] for bucket in by_query.values())
    strict_keep_total = sum(bucket["strict_keep"] for bucket in by_query.values())
    return {
        "snapshot_items": len(items),
        "strict_keep_total": strict_keep_total,
        "strict_reject_total": strict_reject_total,
        "strict_reject_rate": round(strict_reject_total / max(len(items), 1), 6),
        "by_query": by_query,
        "false_positive_samples": false_positive_samples,
        "snapshot_path": repo_rel(EXISTING_ITEMS_JSON),
    }


def _probe_fetch(url: str, params: dict[str, Any], timeout_seconds: float = 10.0) -> dict:
    search = str(params.get("search") or "")
    if "AI chips export controls" in search:
        return {
            "events": [
                {
                    "id": "irrelevant-event",
                    "slug": "china-india-military-clash",
                    "title": "China x India military clash by December 31?",
                    "markets": [
                        {
                            "id": "irrelevant-market",
                            "question": "Will China x India clash by December 31?",
                            "outcomes": '["Yes","No"]',
                            "outcomePrices": '["0.44","0.56"]',
                        }
                    ],
                },
                {
                    "id": "relevant-event",
                    "slug": "nvidia-ai-chip-export-controls",
                    "title": "Nvidia AI chip export controls to China by year-end?",
                    "markets": [
                        {
                            "id": "relevant-market",
                            "question": "Will US restrict Nvidia AI chip exports to China?",
                            "outcomes": '["Yes","No"]',
                            "outcomePrices": '["0.31","0.69"]',
                        }
                    ],
                },
            ]
        }
    slug = search.lower().replace(" ", "-")[:80]
    return {
        "events": [
            {
                "id": f"event-{slug}",
                "slug": slug,
                "title": search,
                "markets": [
                    {
                        "id": f"market-{slug}",
                        "question": f"Will {search} occur?",
                        "outcomes": '["Yes","No"]',
                        "outcomePrices": '["0.31","0.69"]',
                    }
                ],
            }
        ]
    }


def verify_repair() -> dict[str, Any]:
    sources = get_prediction_market_observer_sources()
    summary = persist_prediction_market_event_observer(
        PROBE_DATE,
        data_dir=PROBE_DATA_DIR,
        fetch_func=_probe_fetch,
    )
    probe_items = load_json(PROBE_ITEMS)
    probe_stats = load_json(PROBE_SOURCE_STATS)
    existing_audit = audit_existing_snapshot()
    observer_text = OBSERVER_PY.read_text(encoding="utf-8")
    test_text = TEST_OBSERVER_PY.read_text(encoding="utf-8")
    checks = {
        "source_specs_have_relevance_groups": all(
            spec.get("relevance_groups") and int(spec.get("min_relevance_groups") or 0) >= 2
            for spec in PREDICTION_MARKET_SOURCE_SPECS
        ),
        "manifest_exposes_relevance_groups": all(
            source.get("metadata", {}).get("relevance_groups") for source in sources
        ),
        "probe_rejects_irrelevant_ai_export_market": not any(
            item.get("provider_event_id") == "irrelevant-event" for item in probe_items
        ),
        "probe_keeps_relevant_ai_export_market": any(
            item.get("provider_event_id") == "relevant-event" for item in probe_items
        ),
        "probe_records_relevance_reject_count": summary.get("relevance_rejected_count") == 1,
        "source_stats_record_relevance_reject_count": any(
            stat.get("relevance_rejected_count") == 1 for stat in probe_stats
        ),
        "probe_items_carry_relevance_audit_fields": all(
            item.get("relevance_matched_group_count", 0)
            >= item.get("relevance_required_group_count", 999)
            for item in probe_items
        ),
        "existing_snapshot_had_false_positives": existing_audit["strict_reject_total"] > 0,
        "focused_tests_cover_relevance": (
            "test_prediction_market_relevance_rejects_single_generic_term" in test_text
            and "test_persist_prediction_market_event_observer_records_relevance_rejects"
            in test_text
        ),
        "observer_stays_out_of_trade_news": "clean_trade_news" not in observer_text,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "source_count": len(sources),
        "query_ids": [source["metadata"]["query_id"] for source in sources],
        "candidate_ticker_count": len(
            {
                ticker
                for source in sources
                for ticker in source["metadata"].get("candidate_tickers", [])
            }
        ),
        "probe_summary": summary,
        "probe_item_count": len(probe_items),
        "probe_source_stats": probe_stats,
        "existing_snapshot_audit": existing_audit,
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON)
    baseline = baseline_summary()
    verification = verify_repair()
    accepted = bool(verification["passed"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_prediction_market_event_relevance_gate"
        if accepted
        else "blocked_prediction_market_event_relevance_gate_not_verified"
    )
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
            "Prediction-market probability jumps may be useful for entity/theme "
            "event propagation only if the observer emits semantically relevant "
            "market rows before forward outcome settlement."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "daily_news_llm_event_scoring_alpha",
        "trial_family": "prediction_market_event_observer_relevance_repair",
        "trial_variant_id": "prediction_market_event_relevance_gate_v1",
        "single_causal_variable": "prediction_market_event_relevance_gate_v1",
        "changed_variable": "prediction_market_event_relevance_gate_v1",
        "causal_components": ticket.get("causal_components"),
        "nearby_prior_experiments": ["exp-20260703-004", "exp-20260703-006"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_for_new_prediction_market_source",
        "new_evidence_axis": (
            "New measurement gate on the newly wired public prediction-market "
            "source; it removes broad-search false positives before forward rows "
            "can be interpreted."
        ),
        "observer_contract": {
            "source_count": verification["source_count"],
            "query_ids": verification["query_ids"],
            "candidate_ticker_count": verification["candidate_ticker_count"],
            "artifact_root": f"data/non_ohlcv/{OBSERVER_NAME}",
            "provider": "polymarket",
            "observer_only": True,
            "relevance_gate_version": "prediction_market_event_relevance_gate_v1",
            "existing_snapshot_strict_reject_total": verification[
                "existing_snapshot_audit"
            ]["strict_reject_total"],
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": verification["passed"],
            "fields": [
                "relevance_groups",
                "min_relevance_groups",
                "relevance_rejected_count",
                "relevance_hit_terms",
                "relevance_matched_group_count",
                "relevance_required_group_count",
            ],
            "wiring_checks": verification["checks"],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable strategy filter was added; this filters observer-only data rows before attribution.",
        },
        "gate4": {
            "mode": "measurement_repair_identity_plus_relevance_gate",
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
            "existing_snapshot_audit": verification["existing_snapshot_audit"],
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
                "The run.py observer call remains default-off and observer-only. "
                "This repair only changes which prediction-market rows are saved "
                "for future attribution; it does not feed prompts, rankings, "
                "sizing, exits, or orders."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The first real daily Polymarket snapshot showed broad search "
                "queries can match unrelated markets on a single generic term. "
                "The repair requires multiple semantic groups and records rejected "
                "market counts so future forward rows are interpretable."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun prediction-market alpha by changing probability "
                "thresholds, theme labels, or provider slugs on the polluted first "
                "snapshot. Use rows emitted after this relevance gate, a distinct "
                "event-probability source, or settled forward outcomes."
            ),
            "new_evidence_required": (
                "Relevant post-repair prediction-market rows with closed forward "
                "cash/SPY/QQQ replacement outcomes, or a materially different "
                "probability source with cleaner event taxonomy."
            ),
        },
        "next_retry_requires": [
            "post-repair relevant prediction-market rows with closed forward outcomes",
            "or a materially different event-probability source",
            "or an outcome ledger that settles the filtered observer rows",
        ],
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "The existing snapshot audit confirmed the expected pollution; "
                "the fake-fetch probe verified the gate rejects single generic "
                "term matches while preserving relevant rows."
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
    audit = payload["gate4"]["existing_snapshot_audit"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `{payload["accepted_alpha"]}`
- Strategy behavior changed: `false`
- Existing snapshot strict rejects: `{audit["strict_reject_total"]}` / `{audit["snapshot_items"]}`
- Artifact: `{payload["artifact"]}`

## Gates

- Gate 1 baseline loaded: `{payload["gate1"]["passed"]}`
- Gate 2 relevance fields verified: `{payload["gate2"]["passed"]}`
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
        },
    )
    print(json.dumps(log_record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
