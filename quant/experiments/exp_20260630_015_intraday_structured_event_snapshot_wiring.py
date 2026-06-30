"""exp-20260630-015: wire intraday structured-event snapshots.

Measurement repair only. This closes the production-observer wiring ticket for
the exp-20260630-013 intraday structured-news observation contract. It writes
default-off structured-event artifacts for existing intraday captures and does
not alter prompts, orders, ranking, sizing, exits, or live/default behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260630-015"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "intraday_structured_event_snapshot_wiring"
CHANGED_VARIABLE = "intraday_structured_event_snapshot_wiring_v1"
RUNNER = f"quant/experiments/exp_20260630_015_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for root in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from intraday_news_structured_event_snapshot import (  # noqa: E402
    INTRADAY_STRUCTURED_OBSERVER_RULE_VERSION,
    persist_intraday_structured_event_snapshot,
)


DATA_ROOT = REPO_ROOT / "data"
OUT_DIR = DATA_ROOT / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260630_015_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    DATA_ROOT / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "Timestamped intraday news relation-quality events may become tradable LLM "
    "event-scoring alpha only if the production intraday observer writes the "
    "fixed structured-event forward observation rows prospectively; this run "
    "wires the accepted exp-20260630-013 contract into the default-off intraday "
    "artifact path without changing trading behavior."
)
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260630-013", "exp-20260630-014"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
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


def prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return (ticket.get("prediction") if isinstance(ticket, dict) else None) or {}


def capture_time_labels() -> list[tuple[str, str]]:
    root = DATA_ROOT / "daily" / "intraday" / "news"
    labels: list[tuple[str, str]] = []
    for path in sorted(root.glob("intraday_trade_news_20260629_*.json")):
        stem = path.stem
        prefix = "intraday_trade_news_"
        if not stem.startswith(prefix):
            continue
        date_tag, time_label = stem[len(prefix) :].split("_", 1)
        labels.append((date_tag, time_label))
    return labels


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or []) if isinstance(payload, Mapping) else []
    if not windows:
        return {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "expected_value_score_sum": 7.8941,
            "total_pnl": 234850.99,
            "trade_count": 61,
        }
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
    }


def build_payload() -> dict[str, Any]:
    labels = capture_time_labels()
    snapshots = []
    event_rows = 0
    observation_rows = 0
    target_rows = 0
    failed_reasons: list[str] = []
    for date_tag, time_label in labels:
        snapshot = persist_intraday_structured_event_snapshot(date_tag, time_label, data_dir=DATA_ROOT)
        snapshots.append(snapshot)
        if snapshot.get("trade_enabled") is not False:
            failed_reasons.append(f"{date_tag}_{time_label}_trade_enabled_not_false")
        if snapshot.get("strategy_behavior_changed") is not False:
            failed_reasons.append(f"{date_tag}_{time_label}_strategy_behavior_changed")
        event_audit = snapshot.get("event_contract_audit") or {}
        observation_audit = snapshot.get("forward_observation_contract_audit") or {}
        event_rows += int(event_audit.get("selected_ledger_rows") or 0)
        observation_rows += int(observation_audit.get("observation_rows") or 0)
        target_rows += int(observation_audit.get("target_relation_quality_rows") or 0)
        if not Path(snapshot["event_artifact_path"]).exists():
            failed_reasons.append(f"{date_tag}_{time_label}_missing_event_artifact")
        if not Path(snapshot["forward_observation_artifact_path"]).exists():
            failed_reasons.append(f"{date_tag}_{time_label}_missing_observation_artifact")

    if not labels:
        failed_reasons.append("no_intraday_trade_news_captures")
    if observation_rows <= 0:
        failed_reasons.append("no_forward_observation_rows")

    accepted = not failed_reasons
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_intraday_structured_event_snapshot_wiring"
        if accepted
        else "blocked_intraday_structured_event_snapshot_wiring"
    )
    before = baseline_metrics()
    related_files = [
        "quant/intraday_news_structured_event_snapshot.py",
        "quant/run_intraday.py",
        "quant/test_intraday_news_structured_event_snapshot.py",
        "quant/test_run_intraday_wiring.py",
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
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": (
            "Intraday structured relation-quality news rows may become LLM "
            "event-scoring alpha only after this fixed default-off observer "
            "accumulates closed replacement-value outcomes."
        ),
        "change_type": "measurement_repair_intraday_forward_observation_wiring",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "intraday_news_llm_event_scoring_alpha",
        "trial_family": "intraday_structured_event_forward_observer_wiring",
        "trial_variant_id": "v1_default_off_snapshot_writes_pending_forward_rows",
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "shared snapshot helper",
            "run_intraday default-off persistence",
            "schema tests",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "production_intraday_observer_wiring_creates_new_rows",
        "prediction": prediction(),
        "parameters": {
            "rule_version": INTRADAY_STRUCTURED_OBSERVER_RULE_VERSION,
            "capture_labels": [f"{date}_{time}" for date, time in labels],
            "trade_enabled": False,
            "strategy_behavior_changed": False,
        },
        "gate1": {"passed": BASELINE_RESULT.exists(), "baseline_metrics": before},
        "gate2": {
            "passed": accepted,
            "fields_checked": [
                "event_artifact_path",
                "forward_observation_artifact_path",
                "trade_enabled",
                "strategy_behavior_changed",
                "event_contract_audit.selected_ledger_rows",
                "forward_observation_contract_audit.observation_rows",
            ],
            "entry_date_scope": "Pending forward observations only; no executable entries.",
            "target_price_scope": "Pending forward observations only; no executable target exits.",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": event_rows,
            "signals_survived": observation_rows,
            "survival_rate": round(observation_rows / event_rows, 4) if event_rows else None,
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
            },
        },
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "capture_count": len(labels),
            "event_rows": event_rows,
            "observation_rows": observation_rows,
            "target_relation_quality_rows": target_rows,
        },
        "snapshots": snapshots,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "run_intraday_adapter_changed": True,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "intraday_snapshot_exposed": True,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "llm_prompt_changed": False,
            "live_ready": False,
            "parity_test_added": True,
        },
        "calibration": {
            "predicted_success_probability": prediction().get("success_probability"),
            "actual_success": accepted,
            "predicted_failure_modes": prediction().get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "brier_score": round(
                (float(prediction().get("success_probability") or 0.0) - (1.0 if accepted else 0.0))
                ** 2,
                6,
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The accepted exp-20260630-013 contract was already reusable; "
                "the production intraday path only needed bounded default-off "
                "artifact persistence for the existing captures."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune intraday event relation lists, prompt wording, "
                "horizons, notional, or action response curves on these pending rows."
            ),
            "new_evidence_required": (
                "Closed replacement-value outcomes from this fixed observer, or "
                "a PIT LLM scorer writing the same evidence-span schema."
            ),
        },
        "next_retry_requires": [
            "closed intraday structured-event forward rows",
            "PIT LLM event scorer using the same schema",
        ],
        "related_files": related_files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest "
            "quant\\test_intraday_news_structured_event_snapshot.py "
            "quant\\test_run_intraday_wiring.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
    }


def build_card(payload: Mapping[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return (
        f"# {EXPERIMENT_ID}: intraday structured-event snapshot wiring\n\n"
        f"- Decision: `{payload['decision']}`\n"
        f"- Status: `{payload['status']}`\n"
        "- Accepted alpha: no\n"
        "- Strategy behavior changed: no\n"
        f"- Capture count: `{delta['capture_count']}`\n"
        f"- Event rows: `{delta['event_rows']}`\n"
        f"- Observation rows: `{delta['observation_rows']}`\n"
        f"- Target relation-quality rows: `{delta['target_relation_quality_rows']}`\n\n"
        "## Reflection\n\n"
        f"{payload['post_run_reflection']['why_result_happened']}\n"
    )


def manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [Path(item) if Path(item).is_absolute() else REPO_ROOT / item for item in payload["related_files"]]
    files.extend(
        Path(snapshot["event_artifact_path"]) for snapshot in payload.get("snapshots", [])
    )
    files.extend(
        Path(snapshot["forward_observation_artifact_path"])
        for snapshot in payload.get("snapshots", [])
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, manifest(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
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
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "calibration": payload["calibration"],
            "artifact": payload["artifact"],
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )


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
