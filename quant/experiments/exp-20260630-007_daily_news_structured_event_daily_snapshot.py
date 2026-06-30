"""exp-20260630-007: daily structured-news observation snapshot wiring.

Measurement repair / alpha-enabling instrumentation. This runner verifies that
the structured-news forward-observation contract from exp-20260630-006 is now
wired to the production daily path as a separate read-only artifact. It does
not write a daily artifact during the experiment; it dry-runs the latest real
clean_trade_news file and records the schema/wiring audit under the experiment
ID.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260630-007"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "daily_news_structured_event_daily_snapshot"
RUNNER = f"quant/experiments/{EXPERIMENT_ID}_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from daily_news_structured_event_snapshot import (  # noqa: E402
    DAILY_STRUCTURED_OBSERVER_RULE_VERSION,
    build_daily_structured_event_snapshot,
)
from data_paths import DAILY_ARTIFACTS, DATA_ROOT  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{EXPERIMENT_ID}_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Persist the accepted structured daily-news event forward-observation "
    "contract from the production daily path so the exp-20260630-005 LLM/news "
    "relation-quality lead can accumulate prospective PIT rows without changing "
    "trading behavior."
)
ALPHA_HYPOTHESIS = (
    "Structured LLM/news relation-quality events may become tradable alpha only "
    "if future daily runs write the same PIT observation rows that can later be "
    "closed against cash/SPY/QQQ replacement value."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_alpha"
TRIAL_FAMILY = "daily_news_structured_event_daily_observation_snapshot"
TRIAL_VARIANT_ID = "v1_production_daily_observer"
CHANGED_VARIABLE = "daily_news_structured_event_daily_observation_snapshot_v1"
NEW_EVIDENCE_TYPE = "production_daily_forward_observation_rows"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-004",
    "exp-20260630-005",
    "exp-20260630-006",
]
CAUSAL_COMPONENTS = [
    "shared helper",
    "daily artifact path",
    "run.py read-only observer",
    "artifact schema test",
    "no trading behavior change",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


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
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
    }


def latest_clean_trade_news_tag() -> str | None:
    paths = sorted((DATA_ROOT / "daily" / "news" / "trade").glob("clean_trade_news_*.json"))
    if not paths:
        return None
    return paths[-1].stem.rsplit("_", 1)[-1]


def observation_ids(snapshot: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("observation_id"))
        for row in snapshot.get("forward_observations") or []
        if row.get("observation_id")
    ]


def event_ids(snapshot: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("event_id"))
        for row in snapshot.get("rows") or []
        if row.get("event_id")
    ]


def run_adapter_wiring_audit() -> dict[str, Any]:
    run_path = REPO_ROOT / "quant" / "run.py"
    text = run_path.read_text(encoding="utf-8", errors="replace")
    return {
        "run_path": repo_rel(run_path),
        "helper_function_defined": "_persist_daily_structured_news_observation" in text,
        "helper_imports_persist_function": "persist_daily_structured_event_snapshot" in text,
        "daily_observer_call_count": text.count(
            "\n        _persist_daily_structured_news_observation(today)"
        ),
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    latest_tag = latest_clean_trade_news_tag()
    failed_reasons: list[str] = []
    snapshot: dict[str, Any] = {}
    second_snapshot: dict[str, Any] = {}
    if latest_tag is None:
        failed_reasons.append("no_clean_trade_news_archive")
    else:
        snapshot = build_daily_structured_event_snapshot(latest_tag, data_dir=DATA_ROOT)
        second_snapshot = build_daily_structured_event_snapshot(latest_tag, data_dir=DATA_ROOT)

    event_audit = snapshot.get("event_contract_audit") or {}
    obs_audit = snapshot.get("forward_observation_contract_audit") or {}
    event_field_audit = event_audit.get("required_field_audit") or {}
    obs_field_audit = obs_audit.get("required_field_audit") or {}
    artifact_keys_present = {
        "daily_news_structured_events": "daily_news_structured_events" in DAILY_ARTIFACTS,
        "daily_news_structured_event_observations": (
            "daily_news_structured_event_observations" in DAILY_ARTIFACTS
        ),
    }
    wiring = run_adapter_wiring_audit()
    ids_stable = event_ids(snapshot) == event_ids(second_snapshot) and observation_ids(
        snapshot
    ) == observation_ids(second_snapshot)

    if not all(artifact_keys_present.values()):
        failed_reasons.append("daily_artifact_keys_missing")
    if latest_tag and int(event_audit.get("ledger_rows") or 0) <= 0:
        failed_reasons.append("latest_clean_trade_news_has_no_structured_rows")
    if int(obs_audit.get("observation_rows") or 0) != int(event_audit.get("ledger_rows") or 0):
        failed_reasons.append("observation_row_count_mismatch")
    if event_field_audit and not event_field_audit.get("all_required_fields_present"):
        failed_reasons.append("event_required_fields_missing")
    if obs_field_audit and not obs_field_audit.get("all_required_fields_present"):
        failed_reasons.append("observation_required_fields_missing")
    if not ids_stable:
        failed_reasons.append("observation_id_instability")
    if not wiring["helper_function_defined"] or not wiring["helper_imports_persist_function"]:
        failed_reasons.append("run_adapter_helper_missing")
    if wiring["daily_observer_call_count"] < 2:
        failed_reasons.append("run_adapter_not_wired_to_both_news_paths")

    accepted = not failed_reasons
    decision = (
        "accepted_measurement_repair_daily_news_structured_event_daily_snapshot"
        if accepted
        else "blocked_daily_news_structured_event_daily_snapshot"
    )
    status = "accepted_measurement_repair" if accepted else "blocked"
    changed_files = [
        "quant/daily_news_structured_event_snapshot.py",
        "quant/test_daily_news_structured_event_snapshot.py",
        "quant/data_paths.py",
        "quant/run.py",
        RUNNER,
        repo_rel(OUT_JSON),
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
        "implementation_mode": "measurement_repair_daily_forward_observation_snapshot",
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
                "exp-20260630-004": "Built structured actor/object/relation/magnitude evidence rows.",
                "exp-20260630-005": "Observed-only positive relation-quality lead, not promoted due canonical coverage gap.",
                "exp-20260630-006": "Accepted shared forward-observation contract but left daily_snapshot_exposed=false.",
                "novelty_gate": "Reservation passed; this is daily production observation wiring, not a row reslice.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if daily artifact keys exist, the latest clean_trade_news "
                "dry-run emits schema-complete event/observation rows with stable IDs, "
                "and run.py calls the observer after both news collection paths."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "latest_clean_trade_news_tag": latest_tag,
            "observer_rule_version": DAILY_STRUCTURED_OBSERVER_RULE_VERSION,
            "data_dir": repo_rel(DATA_ROOT),
            "actual_daily_write_in_runner": False,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": accepted,
            "dependencies_validated": bool(latest_tag and snapshot),
            "fields_checked": [
                "event_date",
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
            "artifact_keys_present": artifact_keys_present,
            "event_required_field_audit": event_field_audit,
            "observation_required_field_audit": obs_field_audit,
            "entry_date_scope": "Forward observations are pending; no executable entry is scheduled.",
            "target_price_scope": "No target exit is scheduled; target_price is intentionally null.",
            "stable_ids": ids_stable,
            "run_adapter_wiring": wiring,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": event_audit.get("ledger_rows", 0),
            "signals_survived": obs_audit.get("observation_rows", 0),
            "survival_rate": round(
                (obs_audit.get("observation_rows", 0) or 0)
                / (event_audit.get("ledger_rows", 0) or 1),
                4,
            )
            if event_audit.get("ledger_rows")
            else None,
            "target_relation_quality_rows": obs_audit.get("target_relation_quality_rows", 0),
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
            "latest_event_rows": event_audit.get("ledger_rows", 0),
            "latest_observation_rows": obs_audit.get("observation_rows", 0),
            "latest_target_relation_quality_rows": obs_audit.get(
                "target_relation_quality_rows",
                0,
            ),
            "run_adapter_daily_observer_call_count": wiring["daily_observer_call_count"],
        },
        "dry_run_snapshot_audit": {
            "event_contract_audit": event_audit,
            "forward_observation_contract_audit": obs_audit,
            "sample_event_rows": (snapshot.get("rows") or [])[:5],
            "sample_observation_rows": (snapshot.get("forward_observations") or [])[:5],
        },
        "production_impact": {
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "daily_snapshot_exposed": True,
            "shared_policy_changed": False,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "llm_prompt_changed": False,
            "live_ready": False,
            "parity_note": (
                "run.py now writes a separate read-only structured-news observation "
                "artifact after news collection. It is not attached to the LLM prompt "
                "or quant_signals and cannot affect orders, ranking, sizing, or exits."
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
                "The accepted structured-news contract was narrow enough to wire into "
                "daily production observation as a separate artifact. The latest clean "
                "trade-news archive emits stable event and observation IDs without "
                "touching trading behavior."
                if accepted
                else "The daily structured-news observation wiring did not satisfy the contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this wiring to sweep relation lists, polarity labels, "
                "magnitude requirements, hold days, top-N, notional, response curves, "
                "or prompt wording on the same rows."
            ),
            "new_evidence_required": (
                "Let daily runs accumulate new forward observations, then close them "
                "against cash/SPY/QQQ replacement value; alternatively add a true PIT "
                "LLM scorer using the same evidence-span schema or canonical-window "
                "daily-news coverage."
            ),
        },
        "next_retry_requires": [
            "new closed structured-event daily observation rows",
            "PIT LLM labels persisted with the same evidence-span schema",
            "canonical-window daily-news coverage",
        ],
        "changed_files": changed_files,
        "related_files": [
            "quant/daily_news_structured_events.py",
            "quant/test_daily_news_structured_events.py",
            "experiments/logs/exp-20260630-004.json",
            "experiments/logs/exp-20260630-005.json",
            "experiments/logs/exp-20260630-006.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\daily_news_structured_event_snapshot.py quant\\test_daily_news_structured_event_snapshot.py quant\\run.py "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_daily_news_structured_event_snapshot.py quant\\test_daily_news_structured_events.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner and pytest only; no JavaScript tooling invoked.",
        },
    }


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "lane",
        "owner",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
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
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
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
        "changed_files",
        "related_files",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: Mapping[str, Any]) -> str:
    delta = payload["delta_metrics"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: daily structured-news observation snapshot",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            "- Accepted alpha: no",
            "- Strategy behavior changed: no",
            f"- Latest event rows: `{delta['latest_event_rows']}`",
            f"- Latest observation rows: `{delta['latest_observation_rows']}`",
            f"- Target relation-quality rows: `{delta['latest_target_relation_quality_rows']}`",
            f"- run.py observer calls: `{delta['run_adapter_daily_observer_call_count']}`",
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
        REPO_ROOT / "quant" / "daily_news_structured_event_snapshot.py",
        REPO_ROOT / "quant" / "test_daily_news_structured_event_snapshot.py",
        REPO_ROOT / "quant" / "data_paths.py",
        REPO_ROOT / "quant" / "run.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
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


def persist(payload: Mapping[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
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
            "dry_run_snapshot_audit": payload["dry_run_snapshot_audit"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "calibration": payload["calibration"],
            "artifact": repo_rel(OUT_JSON),
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
