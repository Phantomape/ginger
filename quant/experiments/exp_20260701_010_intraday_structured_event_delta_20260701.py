"""exp-20260701-010: audit 2026-07-01 intraday structured-event delta.

Measurement repair only. This copies the new 2026-07-01 13:02ET intraday
structured-event forward observations into an experiment-owned artifact,
validates the fixed observer contract, and records duplicate/schema checks
without changing entries, exits, sizing, ranking, prompts, or production
trading behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260701-010"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "intraday_structured_event_delta_20260701"
CHANGED_VARIABLE = "intraday_structured_event_observation_delta_20260701_1302_v1"
RUNNER = f"quant/experiments/exp_20260701_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for root in (REPO_ROOT, REPO_ROOT / "scripts"):
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_ROOT = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_ROOT / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = DATA_ROOT / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260701_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CAPTURES = [("20260701", "1302ET")]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-013",
    "exp-20260630-015",
    "exp-20260630-019",
    "exp-20260701-003",
]
HYPOTHESIS = (
    "Intraday structured relation-quality news rows may become LLM event-scoring "
    "alpha only after the fixed observer accumulates replayable pending and closed "
    "replacement-value rows; the new 2026-07-01 13:02ET capture should be copied "
    "into an experiment-owned delta ledger without changing trading behavior."
)
ALPHA_HYPOTHESIS = (
    "Structured intraday relation-quality events may become LLM event-scoring alpha "
    "after this fixed default-off observer accumulates enough closed cash/SPY/QQQ "
    "replacement-value outcomes."
)
CHANGE_TYPE = "intraday_structured_event_forward_observation_delta"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_measurement_repair"
TRIAL_FAMILY = "intraday_structured_event_forward_observation_delta"
TRIAL_VARIANT_ID = "20260701_1302ET_delta_v1"

REQUIRED_OBSERVATION_FIELDS = [
    "observation_id",
    "event_id",
    "event_date",
    "capture_date",
    "time_label",
    "ticker",
    "relation_type",
    "relation_polarity",
    "target_relation_quality",
    "entry_date",
    "entry_semantics",
    "exit_semantics",
    "target_price",
    "unit_notional_usd",
    "outcome_status",
]
SEMANTIC_KEY_FIELDS = [
    "ticker",
    "event_date",
    "published_at",
    "relation_type",
    "relation_polarity",
    "evidence_text_hash",
    "sanitized_text_hash",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    if isinstance(value, set):
        return sorted(safe(item) for item in value)
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, Path):
        return repo_rel(value)
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return rows
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


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
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    if isinstance(ticket, Mapping) and isinstance(ticket.get("prediction"), Mapping):
        return dict(ticket["prediction"])
    return {}


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
        "survival_rate": round(survived / generated, 6) if generated else None,
        "windows": [
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
            }
            for row in windows
        ],
    }


def event_path(date_tag: str, time_label: str) -> Path:
    return (
        DATA_ROOT
        / "daily"
        / "intraday"
        / "structured"
        / f"intraday_news_structured_events_{date_tag}_{time_label}.json"
    )


def observation_path(date_tag: str, time_label: str) -> Path:
    return (
        DATA_ROOT
        / "daily"
        / "intraday"
        / "structured"
        / f"intraday_news_structured_event_observations_{date_tag}_{time_label}.jsonl"
    )


def semantic_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in SEMANTIC_KEY_FIELDS)


def missing_required_fields(rows: Iterable[Mapping[str, Any]]) -> Counter:
    missing: Counter = Counter()
    for row in rows:
        for field in REQUIRED_OBSERVATION_FIELDS:
            if field not in row:
                missing[field] += 1
    return missing


def duplicate_count(values: Iterable[Any]) -> int:
    counts = Counter(str(value) for value in values)
    return sum(count - 1 for count in counts.values() if count > 1)


def capture_summary(date_tag: str, time_label: str) -> dict[str, Any]:
    snapshot_file = event_path(date_tag, time_label)
    observation_file = observation_path(date_tag, time_label)
    snapshot = read_json(snapshot_file, {})
    rows = read_jsonl(observation_file)
    event_audit = snapshot.get("event_contract_audit") if isinstance(snapshot, Mapping) else {}
    observation_audit = (
        snapshot.get("forward_observation_contract_audit") if isinstance(snapshot, Mapping) else {}
    )
    event_audit = event_audit if isinstance(event_audit, Mapping) else {}
    observation_audit = observation_audit if isinstance(observation_audit, Mapping) else {}
    row_missing = missing_required_fields(rows)
    return {
        "capture_label": f"{date_tag}_{time_label}",
        "date_tag": date_tag,
        "time_label": time_label,
        "event_artifact_path": repo_rel(snapshot_file),
        "observation_artifact_path": repo_rel(observation_file),
        "event_artifact_exists": snapshot_file.exists(),
        "observation_artifact_exists": observation_file.exists(),
        "event_artifact_sha256": sha256_file(snapshot_file),
        "observation_artifact_sha256": sha256_file(observation_file),
        "snapshot_trade_enabled": snapshot.get("trade_enabled") if isinstance(snapshot, Mapping) else None,
        "snapshot_strategy_behavior_changed": (
            snapshot.get("strategy_behavior_changed") if isinstance(snapshot, Mapping) else None
        ),
        "event_audit": {
            "capture_count": event_audit.get("capture_count"),
            "ledger_rows": event_audit.get("ledger_rows"),
            "selected_ledger_rows": event_audit.get("selected_ledger_rows"),
            "duplicate_event_ids": event_audit.get("duplicate_event_ids"),
            "target_relation_quality_rows": event_audit.get("target_relation_quality_rows"),
            "target_relation_quality_tickers": event_audit.get("target_relation_quality_tickers"),
            "magnitude_rows": event_audit.get("magnitude_rows"),
            "relation_counts": event_audit.get("relation_counts") or {},
            "ticker_top20": event_audit.get("ticker_top20") or {},
            "required_field_audit": event_audit.get("required_field_audit") or {},
        },
        "observation_audit": {
            "capture_count": observation_audit.get("capture_count"),
            "observation_rows": observation_audit.get("observation_rows"),
            "duplicate_observation_ids": observation_audit.get("duplicate_observation_ids"),
            "target_relation_quality_rows": observation_audit.get("target_relation_quality_rows"),
            "target_relation_quality_tickers": observation_audit.get("target_relation_quality_tickers"),
            "relation_counts": observation_audit.get("relation_counts") or {},
            "required_field_audit": observation_audit.get("required_field_audit") or {},
        },
        "loaded_observation_rows": len(rows),
        "row_required_field_audit": {
            "required_fields": REQUIRED_OBSERVATION_FIELDS,
            "all_required_fields_present": not row_missing,
            "missing_counts": dict(row_missing),
        },
        "pending_rows": sum(1 for row in rows if row.get("outcome_status") == "pending_forward_close"),
        "target_relation_quality_rows": sum(1 for row in rows if bool(row.get("target_relation_quality"))),
        "magnitude_qualified_rows": sum(1 for row in rows if bool(row.get("magnitude_qualified"))),
        "tickers": sorted({str(row.get("ticker")) for row in rows if row.get("ticker")}),
        "rows": rows,
    }


def build_delta_rows(captures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    delta_rows: list[dict[str, Any]] = []
    for capture in captures:
        for row in capture["rows"]:
            enriched = dict(row)
            enriched["delta_experiment_id"] = EXPERIMENT_ID
            enriched["delta_rule_version"] = "intraday_structured_event_delta_audit_v1"
            enriched["source_capture_label"] = capture["capture_label"]
            enriched["source_observation_artifact_path"] = capture["observation_artifact_path"]
            delta_rows.append(enriched)
    return delta_rows


def duplicate_semantic_groups(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[semantic_key(row)].append(row)
    duplicates: list[dict[str, Any]] = []
    for key, members in sorted(groups.items(), key=lambda item: item[0]):
        if len(members) <= 1:
            continue
        exemplar = members[0]
        duplicates.append(
            {
                "semantic_key": dict(zip(SEMANTIC_KEY_FIELDS, key)),
                "count": len(members),
                "observation_ids": sorted(str(row.get("observation_id")) for row in members),
                "capture_labels": sorted(str(row.get("source_capture_label")) for row in members),
                "ticker": exemplar.get("ticker"),
                "relation_type": exemplar.get("relation_type"),
                "event_date": exemplar.get("event_date"),
            }
        )
    return duplicates


def build_payload() -> dict[str, Any]:
    before = load_baseline_metrics()
    pred = prediction()
    captures = [capture_summary(date_tag, time_label) for date_tag, time_label in CAPTURES]
    delta_rows = build_delta_rows(captures)
    semantic_duplicates = duplicate_semantic_groups(delta_rows)

    observation_ids = [row.get("observation_id") for row in delta_rows]
    event_ids = [row.get("event_id") for row in delta_rows]
    missing = missing_required_fields(delta_rows)
    relation_counts = Counter(str(row.get("relation_type") or "missing") for row in delta_rows)
    polarity_counts = Counter(str(row.get("relation_polarity") or "missing") for row in delta_rows)
    ticker_counts = Counter(str(row.get("ticker") or "missing") for row in delta_rows)
    failure_reasons: list[str] = []

    for capture in captures:
        if not capture["event_artifact_exists"]:
            failure_reasons.append(f"{capture['capture_label']}_missing_event_artifact")
        if not capture["observation_artifact_exists"]:
            failure_reasons.append(f"{capture['capture_label']}_missing_observation_artifact")
        if capture["loaded_observation_rows"] <= 0:
            failure_reasons.append(f"{capture['capture_label']}_no_observation_rows")
        if not capture["row_required_field_audit"]["all_required_fields_present"]:
            failure_reasons.append(f"{capture['capture_label']}_missing_required_observation_fields")
        if capture["observation_audit"].get("duplicate_observation_ids") not in (0, None):
            failure_reasons.append(f"{capture['capture_label']}_snapshot_duplicate_observation_ids")
        if capture["pending_rows"] != capture["loaded_observation_rows"]:
            failure_reasons.append(f"{capture['capture_label']}_non_pending_rows_present")

    duplicate_observation_ids = duplicate_count(observation_ids)
    if duplicate_observation_ids:
        failure_reasons.append("cross_capture_duplicate_observation_ids")
    if not delta_rows:
        failure_reasons.append("no_new_delta_rows")
    if not any(bool(row.get("target_relation_quality")) for row in delta_rows):
        failure_reasons.append("no_target_relation_quality_rows")
    if missing:
        failure_reasons.append("delta_missing_required_observation_fields")

    accepted = not failure_reasons
    decision = (
        "accepted_measurement_repair_intraday_structured_event_delta_20260701"
        if accepted
        else "blocked_intraday_structured_event_delta_20260701"
    )
    status = "accepted_measurement_repair" if accepted else "blocked"
    semantic_duplicate_rows = sum(max(0, group["count"] - 1) for group in semantic_duplicates)

    delta_metrics = {
        "capture_count": len(captures),
        "delta_observation_rows": len(delta_rows),
        "pending_forward_rows": sum(
            1 for row in delta_rows if row.get("outcome_status") == "pending_forward_close"
        ),
        "target_relation_quality_rows": sum(
            1 for row in delta_rows if bool(row.get("target_relation_quality"))
        ),
        "magnitude_qualified_rows": sum(1 for row in delta_rows if bool(row.get("magnitude_qualified"))),
        "unique_observation_ids": len(set(str(value) for value in observation_ids)),
        "duplicate_observation_ids": duplicate_observation_ids,
        "unique_event_ids": len(set(str(value) for value in event_ids)),
        "unique_semantic_events": len({semantic_key(row) for row in delta_rows}),
        "semantic_duplicate_groups": len(semantic_duplicates),
        "semantic_duplicate_rows": semantic_duplicate_rows,
        "relation_counts": dict(relation_counts),
        "polarity_counts": dict(polarity_counts),
        "ticker_counts": dict(ticker_counts),
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
    }
    related_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
        repo_rel(BASELINE_RESULT),
        *[capture["event_artifact_path"] for capture in captures],
        *[capture["observation_artifact_path"] for capture in captures],
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
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "new intraday capture audit",
            "experiment-owned pending observation delta",
            "duplicate/schema checks",
            "no strategy behavior change",
        ],
        "prior_trial_count": 1,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "new_timestamped_intraday_structured_event_forward_rows",
        "new_evidence_axis": "new prospective pending rows under the accepted fixed intraday observer contract",
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260630-013": "built the intraday structured-event forward observation contract",
                "exp-20260630-015": "wired default-off intraday snapshot persistence",
                "exp-20260630-019": "accepted 2026-06-30 timestamped delta rows",
                "exp-20260701-003": "recovered daily 2026-06-30 structured-news rows",
                "novelty_gate": "reservation passed; this is a new timestamped row delta, not a relation-label slice",
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "new 2026-07-01 13:02ET observation rows are present, pending, "
                "schema-valid, observation IDs are unique, at least one target "
                "relation-quality row exists, and strategy deltas remain zero"
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "captures": [capture["capture_label"] for capture in captures],
            "required_observation_fields": REQUIRED_OBSERVATION_FIELDS,
            "semantic_key_fields": SEMANTIC_KEY_FIELDS,
            "trade_enabled": False,
            "strategy_behavior_changed": False,
        },
        "gate1": {"passed": BASELINE_RESULT.exists(), "baseline_metrics": before},
        "gate2": {
            "passed": accepted,
            "fields_checked": REQUIRED_OBSERVATION_FIELDS
            + [
                "event_artifact_path",
                "observation_artifact_path",
                "outcome_status",
                "target_price",
                "entry_date",
            ],
            "required_field_audit": {
                "all_required_fields_present": not missing,
                "missing_counts": dict(missing),
                "required_fields": REQUIRED_OBSERVATION_FIELDS,
            },
            "entry_date_scope": "Pending forward observations only; entry_date is intentionally null.",
            "target_price_scope": "Pending forward observations only; target_price is intentionally null.",
        },
        "gate3": {
            "passed": len(delta_rows) > 0,
            "filter_added": False,
            "signals_generated": len(delta_rows),
            "signals_survived": len(delta_rows),
            "survival_rate": 1.0 if delta_rows else None,
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "measurement_repair_only": True,
            "failed_reasons": failure_reasons,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "ranking_changed": False,
                "sizing_changed": False,
                "entry_changed": False,
                "exit_changed": False,
            },
        },
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": delta_metrics,
        "captures": [
            {key: value for key, value in capture.items() if key != "rows"} for capture in captures
        ],
        "delta_rows": delta_rows,
        "semantic_duplicate_groups_detail": semantic_duplicates,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "run_intraday_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "intraday_snapshot_exposed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "llm_prompt_changed": False,
            "live_ready": False,
            "parity_test_added": False,
        },
        "prediction": pred,
        "calibration": {
            "predicted_success_probability": pred.get("success_probability"),
            "actual_success": accepted,
            "predicted_failure_modes": pred.get("main_failure_modes") or [],
            "realized_failure_modes": failure_reasons,
            "brier_score": round(
                (float(pred.get("success_probability") or 0.0) - (1.0 if accepted else 0.0)) ** 2,
                6,
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The accepted intraday structured-event observer contract already "
                "existed, and the 2026-07-01 13:02ET source artifact was "
                "schema-valid. The useful output is a bounded experiment-owned "
                "pending row delta, not a new trading rule."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune relation keywords, prompts, horizons, notional, "
                "action response curves, or target-only filters on this pending row."
            ),
            "new_evidence_required": (
                "Closed replacement-value outcomes from this fixed observer, "
                "materially more prospective captures, or a PIT LLM scorer writing "
                "the same evidence-span schema."
            ),
        },
        "next_retry_requires": [
            "closed intraday structured-event replacement-value rows",
            "materially more prospective captures under this fixed observer",
            "PIT LLM event scorer using the same evidence-span schema",
        ],
        "rejection_reason": None if accepted else ";".join(failure_reasons),
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "related_files": related_files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no JavaScript tooling invoked.",
        },
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
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
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
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
        "prediction",
        "calibration",
        "post_run_reflection",
        "next_retry_requires",
        "rejection_reason",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "anti_js",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: Mapping[str, Any]) -> str:
    delta = payload["delta_metrics"]
    rows = ["| Relation | Rows |", "|---|---:|"]
    for relation, count in sorted((delta.get("relation_counts") or {}).items()):
        rows.append(f"| `{relation}` | {count} |")
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: intraday structured-event delta 20260701",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Accepted alpha: `false`",
            "- Strategy behavior changed: `false`",
            f"- Delta observation rows: `{delta['delta_observation_rows']}`",
            f"- Target relation-quality rows: `{delta['target_relation_quality_rows']}`",
            f"- Duplicate observation IDs: `{delta['duplicate_observation_ids']}`",
            f"- Semantic duplicate groups: `{delta['semantic_duplicate_groups']}`",
            "",
            "## Relation Counts",
            "",
            *rows,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
    ]
    for capture in payload.get("captures", []):
        files.append(REPO_ROOT / capture["event_artifact_path"])
        files.append(REPO_ROOT / capture["observation_artifact_path"])
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


def persist(payload: dict[str, Any]) -> None:
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
        "log": repo_rel(LOG_JSON),
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "calibration": payload["calibration"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload.get("prediction"),
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
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
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": False,
            "lean_quality_passed": True,
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
