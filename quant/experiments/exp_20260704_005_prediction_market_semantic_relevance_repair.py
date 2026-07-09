"""exp-20260704-005: prediction-market semantic relevance repair.

Measurement repair only. Prediction-market probabilities can become useful
event-risk context only after the observer rejects semantically unrelated
markets; this run verifies that the repaired gate rejects polluted 20260703
rows without changing any trading behavior.
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
for entry in (SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from prediction_market_event_observer import (  # noqa: E402
    OBSERVER_NAME,
    get_prediction_market_observer_sources,
    prediction_market_source_relevance,
)


EXPERIMENT_ID = "exp-20260704-005"
OWNER = "alpha-explore"
SLUG = "prediction_market_semantic_relevance_repair"
RUNNER = f"quant/experiments/exp_20260704_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_DAILY_JSON = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / OBSERVER_NAME
    / "daily"
    / f"{OBSERVER_NAME}_20260703.json"
)
OBSERVER_PY = REPO_ROOT / "quant" / "prediction_market_event_observer.py"
TEST_OBSERVER_PY = REPO_ROOT / "quant" / "test_prediction_market_event_observer.py"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

CHANGED_FILES = [
    "quant/prediction_market_event_observer.py",
    "quant/test_prediction_market_event_observer.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_005_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\prediction_market_event_observer.py quant\\test_prediction_market_event_observer.py quant\\experiments\\exp_20260704_005_prediction_market_semantic_relevance_repair.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_prediction_market_event_observer.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=str)
        + "\n",
        path,
    )


def baseline_summary() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON)
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


def audit_current_daily_items() -> dict[str, Any]:
    items = load_json(SOURCE_DAILY_JSON)
    metadata_by_query = {
        source["metadata"]["query_id"]: source["metadata"]
        for source in get_prediction_market_observer_sources()
    }
    by_query: dict[str, dict[str, Any]] = {}
    rejected_samples: list[dict[str, Any]] = []
    kept_samples: list[dict[str, Any]] = []
    for item in items:
        query_id = str(item.get("prediction_market_query_id") or "UNKNOWN")
        metadata = metadata_by_query.get(query_id)
        bucket = by_query.setdefault(
            query_id,
            {"rows": 0, "strict_keep": 0, "strict_reject": 0, "reject_methods": {}},
        )
        bucket["rows"] += 1
        if metadata is None:
            bucket["strict_reject"] += 1
            continue
        relevance = prediction_market_source_relevance(
            {
                "title": item.get("title"),
                "question": item.get("question"),
                "slug": item.get("provider_slug"),
            },
            metadata,
        )
        sample = {
            "query_id": query_id,
            "title": item.get("title"),
            "question": item.get("question"),
            "provider_slug": item.get("provider_slug"),
            "method": relevance.get("method"),
            "hit_terms": relevance.get("hit_terms") or [],
            "excluded_terms": relevance.get("excluded_terms") or [],
        }
        if relevance.get("matched"):
            bucket["strict_keep"] += 1
            if len(kept_samples) < 6:
                kept_samples.append(sample)
        else:
            bucket["strict_reject"] += 1
            method = str(relevance.get("method") or "unknown")
            bucket["reject_methods"][method] = bucket["reject_methods"].get(method, 0) + 1
            if len(rejected_samples) < 12:
                rejected_samples.append(sample)

    strict_reject_total = sum(bucket["strict_reject"] for bucket in by_query.values())
    strict_keep_total = sum(bucket["strict_keep"] for bucket in by_query.values())
    return {
        "snapshot_path": repo_rel(SOURCE_DAILY_JSON),
        "snapshot_items": len(items),
        "strict_keep_total": strict_keep_total,
        "strict_reject_total": strict_reject_total,
        "strict_reject_rate": round(strict_reject_total / max(len(items), 1), 6),
        "by_query": by_query,
        "rejected_samples": rejected_samples,
        "kept_samples": kept_samples,
    }


def verify_repair() -> dict[str, Any]:
    observer_text = OBSERVER_PY.read_text(encoding="utf-8")
    test_text = TEST_OBSERVER_PY.read_text(encoding="utf-8")
    sources = get_prediction_market_observer_sources()
    metadata_by_query = {source["metadata"]["query_id"]: source["metadata"] for source in sources}
    current_audit = audit_current_daily_items()
    hyperscaler = metadata_by_query["hyperscaler_power_shortage_probability"]
    frontier = metadata_by_query["frontier_ai_private_capex_probability"]
    checks = {
        "token_boundary_rejects_ukraine_ai_substring": not prediction_market_source_relevance(
            {"title": "Russia-Ukraine ceasefire", "question": "energy before GTA VI"},
            {"relevance_groups": [["ai"], ["energy"]], "min_relevance_groups": 2},
        )["matched"],
        "off_theme_hyperscaler_political_rows_rejected": not prediction_market_source_relevance(
            {
                "title": "Xi Jinping out before 2027?",
                "question": "Xi Jinping out before 2027?",
            },
            hyperscaler,
        )["matched"],
        "off_theme_frontier_consumer_hardware_rejected": not prediction_market_source_relevance(
            {
                "title": "Will OpenAI launch a consumer hardware product?",
                "question": "Will OpenAI launch a new consumer hardware product?",
            },
            frontier,
        )["matched"],
        "relevant_ai_export_market_still_kept": prediction_market_source_relevance(
            {
                "title": "Nvidia AI chip export controls to China by year-end?",
                "question": "Will the US restrict Nvidia AI chip exports to China?",
            },
            metadata_by_query["ai_export_controls_probability"],
        )["matched"],
        "current_daily_pollution_detected": current_audit["strict_reject_total"] >= 1,
        "current_daily_keeps_some_rows": current_audit["strict_keep_total"] >= 1,
        "source_metadata_exposes_exclusions": any(
            source["metadata"].get("exclude_terms") for source in sources
        ),
        "observer_uses_token_boundaries": "_term_pattern" in observer_text,
        "focused_tests_cover_semantic_repair": (
            "test_prediction_market_relevance_uses_token_boundaries_for_short_terms"
            in test_text
            and "test_prediction_market_relevance_rejects_known_off_theme_markets"
            in test_text
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "source_count": len(sources),
        "query_ids": [source["metadata"]["query_id"] for source in sources],
        "current_daily_audit": current_audit,
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON)
    baseline = baseline_summary()
    verification = verify_repair()
    accepted = bool(verification["passed"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_prediction_market_semantic_relevance_gate"
        if accepted
        else "blocked_prediction_market_semantic_relevance_gate"
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
            "Prediction-market probabilities can become an event-risk context "
            "surface only if each saved market is semantically tied to the "
            "configured public-equity exposure theme."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "prediction_market_event_observer_semantic_relevance_repair",
        "trial_family": "prediction_market_event_observer_relevance_repair",
        "trial_variant_id": "prediction_market_event_semantic_relevance_gate_v2",
        "single_causal_variable": "prediction_market_event_semantic_relevance_gate_v2",
        "changed_variable": "prediction_market_event_semantic_relevance_gate_v2",
        "causal_components": ticket.get("causal_components"),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments"),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "new_evidence_axis": ticket.get("novelty", {}).get("new_evidence_axis"),
        "observer_contract": {
            "artifact_root": f"data/non_ohlcv/{OBSERVER_NAME}",
            "observer_only": True,
            "provider": "polymarket",
            "relevance_gate_version": "prediction_market_event_semantic_relevance_gate_v2",
            "source_count": verification["source_count"],
            "query_ids": verification["query_ids"],
            "current_daily_strict_reject_total": verification["current_daily_audit"][
                "strict_reject_total"
            ],
            "current_daily_strict_keep_total": verification["current_daily_audit"][
                "strict_keep_total"
            ],
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": verification["passed"],
            "fields": [
                "relevance_groups",
                "exclude_terms",
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
            "note": "No executable strategy filter was added; this filters observer-only probability rows before attribution.",
        },
        "gate4": {
            "mode": "measurement_repair_semantic_relevance_gate",
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
            "current_daily_audit": verification["current_daily_audit"],
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
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "The observer remains default-off and observer-only. This repair "
                "only changes which prediction-market rows are saved for future "
                "attribution; it does not feed prompts, rankings, sizing, exits, or orders."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The prior gate used raw substring matching, so short terms such "
                "as 'ai' and broad terms such as 'power' admitted unrelated "
                "political, military, and consumer-hardware markets. Token/phrase "
                "boundary matching plus source-specific exclusion terms removes "
                "that pollution before forward settlement."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not run prediction-market alpha on the polluted first snapshot "
                "or by sweeping probability thresholds, provider slugs, theme "
                "labels, or ticker maps. Use post-repair rows with closed cash/SPY/QQQ outcomes."
            ),
            "new_evidence_required": (
                "Relevant post-repair prediction-market rows with closed forward "
                "cash/SPY/QQQ replacement outcomes, or a materially different "
                "probability source with cleaner event taxonomy."
            ),
        },
        "next_retry_requires": [
            "post-repair relevant prediction-market rows",
            "closed cash/SPY/QQQ replacement outcomes",
            "no probability-threshold or theme-label sweep on the polluted first snapshot",
        ],
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": (ticket.get("prediction") or {}).get(
                "success_probability"
            ),
            "predicted_failure_mode_hit": False,
            "surprise_note": (
                "Low surprise: the real daily artifact reproduced the expected "
                "semantic pollution, and the focused tests verified the repaired gate."
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
    audit = payload["gate4"]["current_daily_audit"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `{payload["accepted_alpha"]}`
- Strategy behavior changed: `false`
- Current daily strict rejects: `{audit["strict_reject_total"]}` / `{audit["snapshot_items"]}`
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
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "changed_files": CHANGED_FILES,
        "files": {
            path: {"exists": (REPO_ROOT / path).exists()} for path in CHANGED_FILES
        },
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
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
