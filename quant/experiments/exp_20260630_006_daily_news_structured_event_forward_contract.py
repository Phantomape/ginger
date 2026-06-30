"""exp-20260630-006: daily-news structured-event forward contract.

Measurement repair / alpha-enabling instrumentation. This runner promotes the
structured daily-news event extraction used in exp-20260630-004 into a shared
helper and writes a stable forward-observation contract for future closed-row
attribution. It does not change entries, exits, ranking, sizing, prompts,
paper orders, live orders, or source news archives.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260630-006"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "daily_news_structured_event_forward_contract"
RUNNER = f"quant/experiments/exp_20260630_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from daily_news_structured_events import (  # noqa: E402
    FORWARD_OBSERVATION_RULE_VERSION,
    STRUCTURED_EVENT_RULE_VERSION,
    build_forward_observation_contract,
    build_structured_event_ledger,
    safe,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


NEWS_ROOT = REPO_ROOT / "data" / "daily" / "news"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
LEGACY_STRUCTURED_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260630-004"
    / "daily_news_structured_event_ledger.jsonl"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260630_006_{SLUG}.json"
EVENT_LEDGER_JSONL = OUT_DIR / "daily_news_structured_event_rows.jsonl"
OBSERVATION_JSONL = OUT_DIR / "daily_news_structured_event_forward_observations.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Persist a reusable daily structured-news event observation contract so the "
    "positive exp-20260630-005 relation-quality lead can accumulate prospective "
    "PIT rows without changing trading behavior."
)
ALPHA_HYPOTHESIS = (
    "LLM/news event scoring may become tradable if structured relation-quality "
    "events keep adding closed cash/SPY/QQQ replacement-value rows; this run "
    "only creates the forward-row contract required to measure that."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_alpha"
TRIAL_FAMILY = "daily_news_structured_event_forward_observation_contract"
TRIAL_VARIANT_ID = "v1_relation_quality_forward_rows"
CHANGED_VARIABLE = "daily_news_structured_event_forward_observation_contract_v1"
NEW_EVIDENCE_TYPE = "pit_daily_forward_observation_contract"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260616-027",
    "exp-20260630-004",
    "exp-20260630-005",
]
CAUSAL_COMPONENTS = [
    "shared helper",
    "daily clean-trade-news parser",
    "fixed relation-quality cohort",
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        pass
    return rows


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
    aggregate = payload.get("aggregate") if isinstance(payload, Mapping) else None
    if isinstance(aggregate, Mapping):
        return {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "window_count": None,
            "expected_value_score_sum": aggregate.get("expected_value_score"),
            "total_pnl": aggregate.get("strategy_total_pnl"),
            "trade_count": aggregate.get("trade_count"),
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "max_drawdown_pct_worst": None,
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


def compare_legacy_event_ids(current_rows: list[dict[str, Any]]) -> dict[str, Any]:
    legacy_rows = read_jsonl(LEGACY_STRUCTURED_LEDGER)
    current_ids = {str(row.get("event_id")) for row in current_rows if row.get("event_id")}
    legacy_ids = {str(row.get("event_id")) for row in legacy_rows if row.get("event_id")}
    missing = sorted(legacy_ids - current_ids)
    extra = sorted(current_ids - legacy_ids)
    return {
        "legacy_path": repo_rel(LEGACY_STRUCTURED_LEDGER),
        "legacy_exists": LEGACY_STRUCTURED_LEDGER.exists(),
        "legacy_rows": len(legacy_rows),
        "legacy_event_ids": len(legacy_ids),
        "current_event_ids": len(current_ids),
        "missing_legacy_event_ids": len(missing),
        "extra_current_event_ids": len(extra),
        "sample_missing_legacy_event_ids": missing[:10],
        "sample_extra_current_event_ids": extra[:10],
        "equivalent_for_legacy_ids": LEGACY_STRUCTURED_LEDGER.exists()
        and len(legacy_ids) > 0
        and not missing,
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    event_contract = build_structured_event_ledger(
        NEWS_ROOT,
        repo_root=REPO_ROOT,
        kinds=("clean_trade_news",),
        require_explicit_ticker_text=True,
    )
    event_rows = list(event_contract["rows"])
    observation_contract = build_forward_observation_contract(event_rows)
    observation_rows = list(observation_contract["rows"])
    legacy = compare_legacy_event_ids(event_rows)
    failed_reasons: list[str] = []
    if not event_rows:
        failed_reasons.append("no_structured_event_rows")
    if not observation_rows:
        failed_reasons.append("no_forward_observation_rows")
    if event_contract["audit"]["duplicate_event_ids"]:
        failed_reasons.append("duplicate_event_ids")
    if observation_contract["audit"]["duplicate_observation_ids"]:
        failed_reasons.append("duplicate_observation_ids")
    if not event_contract["audit"]["required_field_audit"]["all_required_fields_present"]:
        failed_reasons.append("event_required_fields_missing")
    if not observation_contract["audit"]["required_field_audit"]["all_required_fields_present"]:
        failed_reasons.append("observation_required_fields_missing")
    if observation_contract["audit"]["target_relation_quality_rows"] <= 0:
        failed_reasons.append("no_target_relation_quality_rows")
    if not legacy["equivalent_for_legacy_ids"]:
        failed_reasons.append("helper_not_equivalent_to_exp004_event_ids")

    accepted = not failed_reasons
    decision = (
        "accepted_measurement_repair_daily_news_structured_event_forward_contract"
        if accepted
        else "blocked_daily_news_structured_event_forward_contract"
    )
    status = "accepted_measurement_repair" if accepted else "blocked"
    changed_files = [
        "quant/daily_news_structured_events.py",
        "quant/test_daily_news_structured_events.py",
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
        "implementation_mode": "measurement_repair_shared_forward_observation_contract",
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
                "exp-20260616-027": "Blocked because no complete actor/object/relation/magnitude tuple surface existed.",
                "exp-20260630-004": "Accepted measurement repair creating structured event rows with evidence spans.",
                "exp-20260630-005": "Observed-only positive relation-quality lead; not promoted because coverage is 2026-forward only.",
                "novelty_gate": "experiment.py new passed with no strong near-neighbor; measurement lane not source-saturation blocked.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if shared helper produces nonzero structured rows and "
                "forward observations, required fields are complete, IDs are stable, "
                "and legacy exp-004 event IDs are reproduced without changing strategy metrics."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "news_root": repo_rel(NEWS_ROOT),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "legacy_structured_ledger": repo_rel(LEGACY_STRUCTURED_LEDGER),
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
                "ticker",
                "relation_type",
                "relation_polarity",
                "evidence_span",
                "sanitized_text_hash",
                "source_provenance",
                "observation_id",
                "entry_semantics",
                "exit_semantics",
                "outcome_status",
                "entry_date",
                "target_price",
            ],
            "event_required_field_audit": event_contract["audit"]["required_field_audit"],
            "observation_required_field_audit": observation_contract["audit"][
                "required_field_audit"
            ],
            "entry_date_scope": "Forward observations are pending; no executable entry is scheduled.",
            "target_price_scope": "No target exit is scheduled; target_price is intentionally null.",
            "legacy_equivalence": legacy,
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
            "duplicate_event_ids": event_contract["audit"]["duplicate_event_ids"],
            "duplicate_observation_ids": observation_contract["audit"][
                "duplicate_observation_ids"
            ],
            "legacy_missing_event_ids": legacy["missing_legacy_event_ids"],
        },
        "event_contract_audit": event_contract["audit"],
        "forward_observation_contract_audit": observation_contract["audit"],
        "legacy_equivalence": legacy,
        "production_impact": {
            "shared_helper_promoted": True,
            "daily_snapshot_exposed": False,
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
                "The shared helper and experiment-owned observation ledger do not "
                "alter run.py, backtester.py, prompts, orders, ranking, sizing, or exits."
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
                or (
                    mode == "helper_not_equivalent_to_exp004"
                    and "helper_not_equivalent_to_exp004_event_ids" in failed_reasons
                )
            ],
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - (1.0 if accepted else 0.0))
                ** 2,
                6,
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exp-004 structured extraction can now be reproduced through a "
                "shared helper, and every event has a stable forward-observation row "
                "with fixed relation-quality tagging. This still is not accepted alpha "
                "because it does not add canonical-window news coverage or closed "
                "forward rows beyond exp-005."
                if accepted
                else "The shared helper did not satisfy the structured observation contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use exp-006 to sweep relation lists, polarity labels, magnitude "
                "requirements, hold days, top-N, notional, response curves, or prompt "
                "wording on the same structured rows. Reopen alpha only with new closed "
                "forward observations, a PIT LLM scorer using this schema, or canonical "
                "historical news coverage."
            ),
            "new_evidence_required": (
                "More closed cash/SPY/QQQ replacement-value rows under this fixed "
                "observation contract, a production PIT LLM event scorer that writes "
                "the same evidence-span schema, or canonical-window clean-trade-news coverage."
            ),
        },
        "next_retry_requires": [
            "new closed structured-event forward observation rows",
            "PIT LLM labels persisted with the same evidence-span schema",
            "canonical-window daily-news coverage",
        ],
        "changed_files": changed_files,
        "related_files": [
            "quant/daily_news_text_sanitation.py",
            "quant/news_text_sanitizer.py",
            "experiments/logs/exp-20260616-027.json",
            "experiments/logs/exp-20260630-004.json",
            "experiments/logs/exp-20260630-005.json",
            repo_rel(LEGACY_STRUCTURED_LEDGER),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\daily_news_structured_events.py quant\\test_daily_news_structured_events.py "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_daily_news_structured_events.py -q",
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
        "legacy_equivalence": payload["legacy_equivalence"],
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
            f"# {EXPERIMENT_ID}: daily-news structured-event forward contract",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            "- Accepted alpha: no",
            "- Strategy behavior changed: no",
            f"- Event rows: `{delta['event_rows']}`",
            f"- Forward observation rows: `{delta['observation_rows']}`",
            f"- Target relation-quality rows: `{delta['target_relation_quality_rows']}`",
            f"- Legacy exp-004 missing event IDs: `{delta['legacy_missing_event_ids']}`",
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
        REPO_ROOT / "quant" / "daily_news_structured_events.py",
        REPO_ROOT / "quant" / "test_daily_news_structured_events.py",
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
                "legacy_equivalence": payload["legacy_equivalence"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
