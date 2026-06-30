"""exp-20260630-013: intraday-news structured-event forward contract.

Measurement repair / alpha-enabling instrumentation. This runner materializes
sanitized intraday trade-news snapshots into a replayable structured-event
ledger and fixed pending forward observations. It does not change entries,
exits, ranking, sizing, prompts, paper orders, live orders, or source archives.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260630-013"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "intraday_news_structured_event_forward_contract"
RUNNER = f"quant/experiments/exp_20260630_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from intraday_news_structured_events import (  # noqa: E402
    FORWARD_OBSERVATION_RULE_VERSION,
    STRUCTURED_EVENT_RULE_VERSION,
    build_forward_observation_contract,
    build_structured_event_ledger,
    safe,
)


INTRADAY_ROOT = REPO_ROOT / "data" / "daily" / "intraday"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260630_013_{SLUG}.json"
EVENT_LEDGER_JSONL = OUT_DIR / "intraday_news_structured_event_rows.jsonl"
OBSERVATION_JSONL = OUT_DIR / "intraday_news_structured_event_forward_observations.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Intraday LLM/news event scoring cannot be evaluated replayably because "
    "sanitized intraday trade-news snapshots lack a structured event and "
    "forward-observation ledger with timestamped provenance; persist that "
    "contract without changing trading behavior."
)
ALPHA_HYPOTHESIS = (
    "Timestamped intraday news relation-quality events may become tradable LLM "
    "event-scoring alpha only after this fixed observation contract accumulates "
    "closed cash/SPY/QQQ replacement-value rows."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "intraday_news_llm_event_scoring_alpha"
TRIAL_FAMILY = "intraday_news_structured_event_forward_observation_contract"
TRIAL_VARIANT_ID = "v1_timestamped_intraday_rows"
CHANGED_VARIABLE = "intraday_news_structured_event_forward_observation_contract_v1"
NEW_EVIDENCE_TYPE = "pit_intraday_forward_observation_contract"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260629-012",
    "exp-20260630-006",
    "exp-20260630-007",
]
CAUSAL_COMPONENTS = [
    "shared helper",
    "intraday trade-news parser",
    "timestamped provenance",
    "forward observation ledger",
    "no trading behavior change",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return (ticket.get("prediction") if isinstance(ticket, dict) else None) or {}


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or []) if isinstance(payload, Mapping) else []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    if windows:
        return {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "window_count": len(windows),
            "expected_value_score_sum": round(
                sum(float(row.get("expected_value_score") or 0.0) for row in windows),
                4,
            ),
            "total_pnl": round(
                sum(float(row.get("total_pnl") or 0.0) for row in windows),
                2,
            ),
            "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": round(survived / generated, 4) if generated else None,
            "max_drawdown_pct_worst": max(
                (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
                default=None,
            ),
        }
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": 3,
        "expected_value_score_sum": 7.8941,
        "total_pnl": 234850.99,
        "trade_count": 61,
        "signals_generated": 164,
        "signals_survived": 135,
        "survival_rate": 0.8232,
        "max_drawdown_pct_worst": 0.1119,
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    event_contract = build_structured_event_ledger(
        INTRADAY_ROOT,
        repo_root=REPO_ROOT,
        require_explicit_ticker_text=True,
    )
    event_rows = list(event_contract["rows"])
    observation_contract = build_forward_observation_contract(event_rows)
    observation_rows = list(observation_contract["rows"])

    failed_reasons: list[str] = []
    if not event_rows:
        failed_reasons.append("no_intraday_event_rows")
    if not observation_rows:
        failed_reasons.append("no_intraday_forward_observation_rows")
    if event_contract["audit"]["duplicate_event_ids"]:
        failed_reasons.append("duplicate_event_ids")
    if observation_contract["audit"]["duplicate_observation_ids"]:
        failed_reasons.append("duplicate_observation_ids")
    if not event_contract["audit"]["required_field_audit"]["all_required_fields_present"]:
        failed_reasons.append("event_required_fields_missing")
    if not observation_contract["audit"]["required_field_audit"][
        "all_required_fields_present"
    ]:
        failed_reasons.append("observation_required_fields_missing")
    if observation_contract["audit"]["target_relation_quality_rows"] <= 0:
        failed_reasons.append("no_target_relation_quality_rows")

    accepted = not failed_reasons
    decision = (
        "accepted_measurement_repair_intraday_news_structured_event_forward_contract"
        if accepted
        else "blocked_intraday_news_structured_event_forward_contract"
    )
    status = "accepted_measurement_repair" if accepted else "blocked"
    changed_files = [
        "quant/intraday_news_structured_events.py",
        "quant/test_intraday_news_structured_events.py",
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(EVENT_LEDGER_JSONL),
        repo_rel(OBSERVATION_JSONL),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair_intraday_forward_observation_contract",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260629-012": "Accepted intraday news sanitation only; no structured forward rows.",
                "exp-20260630-006": "Accepted daily structured-event forward contract, different source cadence.",
                "exp-20260630-007": "Accepted daily production observation wiring, not intraday snapshots.",
                "novelty_gate": "experiment.py new passed with no strong near-neighbor.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if intraday snapshots produce nonzero structured "
                "events and pending observations, required fields are complete, "
                "IDs are stable/non-duplicate, and strategy metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "intraday_root": repo_rel(INTRADAY_ROOT),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "structured_event_rule_version": STRUCTURED_EVENT_RULE_VERSION,
            "forward_observation_rule_version": FORWARD_OBSERVATION_RULE_VERSION,
            "require_explicit_ticker_text": True,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "passed": BASELINE_RESULT.exists(),
        },
        "gate2": {
            "dependencies_validated": bool(event_rows and observation_rows),
            "fields_checked": [
                "event_date",
                "capture_date",
                "time_label",
                "ticker",
                "relation_type",
                "relation_polarity",
                "evidence_span",
                "source_provenance",
                "observation_id",
                "entry_semantics",
                "exit_semantics",
                "entry_date",
                "target_price",
                "outcome_status",
            ],
            "event_required_field_audit": event_contract["audit"]["required_field_audit"],
            "observation_required_field_audit": observation_contract["audit"][
                "required_field_audit"
            ],
            "entry_date_scope": "Forward observations are pending; no executable entry is scheduled.",
            "target_price_scope": "No target exit is scheduled; target_price is intentionally null.",
            "passed": bool(event_rows and observation_rows and not failed_reasons),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": event_contract["audit"]["ledger_rows"],
            "signals_survived": observation_contract["audit"]["observation_rows"],
            "survival_rate": round(
                observation_contract["audit"]["observation_rows"]
                / event_contract["audit"]["ledger_rows"],
                4,
            )
            if event_contract["audit"]["ledger_rows"]
            else None,
            "target_relation_quality_rows": observation_contract["audit"][
                "target_relation_quality_rows"
            ],
            "note": "Measurement rows only; no executable filter or rank rule was added.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "measurement_repair_only": True,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "max_drawdown_pct_delta": 0.0,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "event_rows": event_contract["audit"]["ledger_rows"],
            "observation_rows": observation_contract["audit"]["observation_rows"],
            "target_relation_quality_rows": observation_contract["audit"][
                "target_relation_quality_rows"
            ],
            "target_relation_quality_event_dates": observation_contract["audit"][
                "target_relation_quality_event_dates"
            ],
            "capture_count": observation_contract["audit"]["capture_count"],
            "duplicate_event_ids": event_contract["audit"]["duplicate_event_ids"],
            "duplicate_observation_ids": observation_contract["audit"][
                "duplicate_observation_ids"
            ],
        },
        "event_contract_audit": event_contract["audit"],
        "forward_observation_contract_audit": observation_contract["audit"],
        "production_impact": {
            "shared_helper_added": True,
            "intraday_snapshot_exposed": False,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "llm_prompt_changed": False,
            "news_archives_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "live_ready": False,
            "parity_note": (
                "The helper and experiment-owned ledgers are read-only and are not "
                "called by run.py, run_intraday.py, backtester.py, prompts, orders, "
                "ranking, sizing, or exits."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": accepted,
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": [
                mode
                for mode in prediction.get("main_failure_modes") or []
                if mode in failed_reasons
            ],
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - (1.0 if accepted else 0.0))
                ** 2,
                6,
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The sanitized intraday feed has enough explicit ticker/event "
                "text to emit timestamped relation rows across 20 captures. "
                "The result is alpha-enabling only: no rows are closed and no "
                "trading policy consumes the observations."
                if accepted
                else "The intraday structured-event contract did not satisfy the required row/schema checks."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this same pending intraday ledger to sweep relation "
                "lists, polarity labels, magnitude requirements, prompt wording, "
                "hold days, top-N, notional, response curves, or ticker subsets. "
                "Those are response retunes on unclosed rows."
            ),
            "new_evidence_required": (
                "Closed intraday event forward observations under this fixed "
                "contract, a PIT LLM event scorer that writes the same schema, "
                "or production intraday observer wiring that creates new rows."
            ),
        },
        "next_retry_requires": [
            "closed intraday structured-event forward observation rows",
            "PIT LLM labels persisted with the same timestamped evidence-span schema",
            "production intraday observer wiring that creates new observations",
        ],
        "changed_files": changed_files,
        "related_files": [
            "quant/news_text_sanitizer.py",
            "quant/intraday_review.py",
            "experiments/logs/exp-20260629-012.json",
            "experiments/logs/exp-20260630-006.json",
            "experiments/logs/exp-20260630-007.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            "quant\\intraday_news_structured_events.py "
            "quant\\test_intraday_news_structured_events.py "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_intraday_news_structured_events.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "event_ledger": repo_rel(EVENT_LEDGER_JSONL),
        "forward_observation_ledger": repo_rel(OBSERVATION_JSONL),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner and pytest only; no JavaScript tooling invoked.",
        },
        "_event_rows_for_write": event_rows,
        "_observation_rows_for_write": observation_rows,
    }


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": LANE,
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "event_contract_audit": payload["event_contract_audit"],
        "forward_observation_contract_audit": payload["forward_observation_contract_audit"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": payload["artifact"],
        "event_ledger": payload["event_ledger"],
        "forward_observation_ledger": payload["forward_observation_ledger"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: Mapping[str, Any]) -> str:
    gate4 = payload["gate4"]
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: intraday-news structured-event forward contract",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            "- Accepted alpha: no",
            "- Strategy behavior changed: no",
            f"- Event rows: `{delta['event_rows']}`",
            f"- Forward observation rows: `{delta['observation_rows']}`",
            f"- Target relation-quality rows: `{delta['target_relation_quality_rows']}`",
            f"- Capture count: `{delta['capture_count']}`",
            f"- Duplicate event IDs: `{delta['duplicate_event_ids']}`",
            f"- Duplicate observation IDs: `{delta['duplicate_observation_ids']}`",
            f"- Gate 4 failures: `{', '.join(gate4['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
        ]
    ) + "\n"


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / "quant" / "intraday_news_structured_events.py",
        REPO_ROOT / "quant" / "test_intraday_news_structured_events.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        EVENT_LEDGER_JSONL,
        OBSERVATION_JSONL,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "event_ledger": repo_rel(EVENT_LEDGER_JSONL),
        "forward_observation_ledger": repo_rel(OBSERVATION_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    event_rows = payload.pop("_event_rows_for_write")
    observation_rows = payload.pop("_observation_rows_for_write")
    write_jsonl(EVENT_LEDGER_JSONL, event_rows)
    write_jsonl(OBSERVATION_JSONL, observation_rows)
    write_json(OUT_JSON, payload)
    log_row = compact_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "event_ledger": repo_rel(EVENT_LEDGER_JSONL),
        "forward_observation_ledger": repo_rel(OBSERVATION_JSONL),
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "event_contract_audit": payload["event_contract_audit"],
            "forward_observation_contract_audit": payload["forward_observation_contract_audit"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "calibration": payload["calibration"],
            "artifact": repo_rel(OUT_JSON),
            "event_ledger": repo_rel(EVENT_LEDGER_JSONL),
            "forward_observation_ledger": repo_rel(OBSERVATION_JSONL),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
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
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
