"""exp-20260702-014: daily structured-news 2026-07-01 observation delta.

Measurement repair / alpha-enabling instrumentation. The daily structured-news
observer already produced a 2026-07-01 read-only event artifact and pending
forward-observation JSONL. This runner records that new prospective row delta
under the experiment ID, without rewriting the daily artifacts or changing any
trading behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260702-014"
OWNER = "alpha-explore"
LANE = "measurement_repair"
DATE_TAG = "20260701"
ISO_DATE = "2026-07-01"
SLUG = "daily_news_20260701_structured_event_delta"
RUNNER = f"quant/experiments/exp_20260702_014_{SLUG}.py"
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
from data_paths import DATA_ROOT, atomic_write_text  # noqa: E402
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
CLEAN_TRADE_NEWS = DATA_ROOT / "daily" / "news" / "trade" / f"clean_trade_news_{DATE_TAG}.json"
STRUCTURED_DIR = DATA_ROOT / "daily" / "news" / "structured"
STRUCTURED_EVENT_FINAL = STRUCTURED_DIR / f"daily_news_structured_events_{DATE_TAG}.json"
STRUCTURED_OBSERVATION_FINAL = (
    STRUCTURED_DIR / f"daily_news_structured_event_observations_{DATE_TAG}.jsonl"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260702_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
WRITE_FALLBACKS: list[dict[str, Any]] = []

HYPOTHESIS = (
    "Alpha blocker: the 2026-07-01 daily structured-news artifact has new PIT "
    "forward observation rows, but they need an experiment-owned delta record "
    "before structured daily-news LLM event-scoring alpha can mature against "
    "closed cash/SPY/QQQ replacement value."
)
ALPHA_HYPOTHESIS = (
    "Structured daily-news relation-quality events may become tradable LLM "
    "event-scoring alpha if the production daily observer keeps accumulating "
    "PIT rows that can later close against cash/SPY/QQQ replacement value."
)
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "measurement_repair_daily_news_forward_observation_delta"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_measurement_repair"
TRIAL_FAMILY = "daily_news_structured_event_forward_observation_delta"
TRIAL_VARIANT_ID = "20260701_pending_delta_v1"
CHANGED_VARIABLE = "daily_news_20260701_structured_event_observation_delta_v1"
NEW_EVIDENCE_TYPE = "new_daily_structured_event_pending_forward_rows"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-005",
    "exp-20260630-006",
    "exp-20260630-007",
    "exp-20260701-003",
    "exp-20260701-010",
]
CAUSAL_COMPONENTS = [
    "daily structured-news artifact audit",
    "experiment-owned pending observation delta",
    "schema and duplicate checks",
    "no strategy behavior change",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
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


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def write_text(path: Path, text: str) -> None:
    try:
        atomic_write_text(text, path)
    except PermissionError as exc:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        WRITE_FALLBACKS.append(
            {
                "path": repo_rel(path),
                "exception": repr(exc),
                "fallback": "direct_write_after_atomic_rename_denied",
            }
        )


def write_json(path: Path, payload: Any) -> None:
    write_text(
        path,
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
    )


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
        return rows
    return rows


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ticket() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return ticket if isinstance(ticket, dict) else {}


def prediction_block(ticket: Mapping[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict) and prediction:
        return dict(prediction)
    return {
        "success_probability": 0.86,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "missing_20260701_daily_structured_artifacts",
            "structured_observer_zero_rows",
            "duplicate_observation_ids",
            "schema_drift",
        ],
        "confidence_reason": (
            "Preflight found final 2026-07-01 daily structured-news artifacts "
            "with nonzero pending observation rows under the already accepted "
            "observer contract; this run should only record the row delta and "
            "zero strategy movement."
        ),
        "recorded_at": ticket.get("created_at") or utc_now(),
    }


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
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
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


def summarize_clean_payload(payload: Any) -> dict[str, Any]:
    rows = payload if isinstance(payload, list) else []
    source_counts = Counter(str(row.get("source") or "") for row in rows if isinstance(row, Mapping))
    ticker_counts: Counter[str] = Counter()
    explicit_ticker_items = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        tickers = row.get("tickers")
        if isinstance(tickers, list) and tickers:
            explicit_ticker_items += 1
            ticker_counts.update(str(ticker) for ticker in tickers)
    return {
        "top_level_type": type(payload).__name__,
        "row_count": len(rows),
        "explicit_ticker_items": explicit_ticker_items,
        "source_counts": dict(source_counts.most_common(10)),
        "ticker_top20": dict(ticker_counts.most_common(20)),
        "sample_titles": [
            str(row.get("title") or "")[:180]
            for row in rows[:5]
            if isinstance(row, Mapping)
        ],
    }


def required_field_missing_counts(
    rows: Iterable[Mapping[str, Any]],
    required_fields: Iterable[str],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for field in required_fields:
            value = row.get(field)
            if value is None or value == "" or value == {}:
                counts[field] += 1
    return dict(sorted(counts.items()))


def ids_from(rows: Iterable[Mapping[str, Any]], key: str) -> list[str]:
    return [str(row.get(key)) for row in rows if row.get(key)]


def count_duplicates(values: Iterable[str]) -> int:
    counts = Counter(values)
    return sum(1 for count in counts.values() if count > 1)


def build_in_memory_stability_audit(
    event_rows: list[dict[str, Any]],
    observation_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        snapshot = build_daily_structured_event_snapshot(DATE_TAG, data_dir=DATA_ROOT)
    except Exception as exc:  # noqa: BLE001 - experiment artifact records blocker.
        return {"passed": False, "exception": repr(exc)}
    rebuilt_events = list(snapshot.get("rows") or [])
    rebuilt_observations = list(snapshot.get("forward_observations") or [])
    event_ids = ids_from(event_rows, "event_id")
    observation_ids = ids_from(observation_rows, "observation_id")
    rebuilt_event_ids = ids_from(rebuilt_events, "event_id")
    rebuilt_observation_ids = ids_from(rebuilt_observations, "observation_id")
    return {
        "passed": event_ids == rebuilt_event_ids
        and observation_ids == rebuilt_observation_ids,
        "event_ids_match_rebuild": event_ids == rebuilt_event_ids,
        "observation_ids_match_rebuild": observation_ids == rebuilt_observation_ids,
        "rebuilt_event_rows": len(rebuilt_events),
        "rebuilt_observation_rows": len(rebuilt_observations),
        "source_artifacts_rewritten": False,
    }


def artifact_write_audit() -> dict[str, Any]:
    return {
        "clean_trade_news_path": repo_rel(CLEAN_TRADE_NEWS),
        "clean_trade_news_exists": CLEAN_TRADE_NEWS.exists(),
        "clean_trade_news_sha256": sha256_file(CLEAN_TRADE_NEWS),
        "event_artifact_path": repo_rel(STRUCTURED_EVENT_FINAL),
        "event_artifact_exists": STRUCTURED_EVENT_FINAL.exists(),
        "event_artifact_sha256": sha256_file(STRUCTURED_EVENT_FINAL),
        "observation_artifact_path": repo_rel(STRUCTURED_OBSERVATION_FINAL),
        "observation_artifact_exists": STRUCTURED_OBSERVATION_FINAL.exists(),
        "observation_artifact_sha256": sha256_file(STRUCTURED_OBSERVATION_FINAL),
        "source_artifacts_rewritten_by_runner": False,
    }


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    prediction = prediction_block(ticket)
    baseline = load_baseline_metrics()
    event_payload = read_json(STRUCTURED_EVENT_FINAL, {})
    clean_payload = read_json(CLEAN_TRADE_NEWS, [])
    event_rows = list(event_payload.get("rows") or []) if isinstance(event_payload, Mapping) else []
    observation_rows = read_jsonl(STRUCTURED_OBSERVATION_FINAL)
    event_audit = (
        event_payload.get("event_contract_audit") if isinstance(event_payload, Mapping) else {}
    ) or {}
    observation_audit = (
        event_payload.get("forward_observation_contract_audit")
        if isinstance(event_payload, Mapping)
        else {}
    ) or {}
    event_required = (
        (event_audit.get("required_field_audit") or {}).get("required_fields")
        if isinstance(event_audit, Mapping)
        else None
    ) or [
        "event_id",
        "event_date",
        "ticker",
        "relation_type",
        "relation_polarity",
        "actor",
        "object",
        "magnitude",
        "evidence_span",
        "sanitized_text_hash",
        "source_provenance",
    ]
    observation_required = (
        (observation_audit.get("required_field_audit") or {}).get("required_fields")
        if isinstance(observation_audit, Mapping)
        else None
    ) or [
        "observation_id",
        "event_id",
        "event_date",
        "ticker",
        "relation_type",
        "relation_polarity",
        "target_relation_quality",
        "entry_semantics",
        "exit_semantics",
        "unit_notional_usd",
        "outcome_status",
    ]

    event_ids = ids_from(event_rows, "event_id")
    observation_ids = ids_from(observation_rows, "observation_id")
    event_missing_counts = required_field_missing_counts(event_rows, event_required)
    observation_missing_counts = required_field_missing_counts(
        observation_rows,
        observation_required,
    )
    target_rows = [row for row in observation_rows if row.get("target_relation_quality")]
    failed_reasons: list[str] = []
    if not BASELINE_RESULT.exists():
        failed_reasons.append("baseline_missing")
    if not CLEAN_TRADE_NEWS.exists():
        failed_reasons.append("clean_trade_news_20260701_missing")
    if not STRUCTURED_EVENT_FINAL.exists():
        failed_reasons.append("daily_structured_event_artifact_missing")
    if not STRUCTURED_OBSERVATION_FINAL.exists():
        failed_reasons.append("daily_structured_observation_artifact_missing")
    if not event_rows:
        failed_reasons.append("structured_observer_zero_rows")
    if not observation_rows:
        failed_reasons.append("structured_observation_zero_rows")
    if len(event_rows) != len(observation_rows):
        failed_reasons.append("event_observation_row_count_mismatch")
    if count_duplicates(event_ids):
        failed_reasons.append("duplicate_event_ids")
    if count_duplicates(observation_ids):
        failed_reasons.append("duplicate_observation_ids")
    if event_missing_counts:
        failed_reasons.append("event_required_fields_missing")
    if observation_missing_counts:
        failed_reasons.append("observation_required_fields_missing")
    if not target_rows:
        failed_reasons.append("no_target_relation_quality_rows")

    stability = build_in_memory_stability_audit(event_rows, observation_rows)
    if not stability.get("passed"):
        failed_reasons.append("in_memory_rebuild_ids_not_stable")

    accepted = not failed_reasons
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_daily_news_20260701_structured_event_delta"
        if accepted
        else "blocked_daily_news_20260701_structured_event_delta"
    )
    event_dates = sorted({str(row.get("event_date")) for row in event_rows if row.get("event_date")})
    event_source_dates = (
        event_audit.get("source_date_counts")
        if isinstance(event_audit.get("source_date_counts"), Mapping)
        else {}
    )
    delta_metrics = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "max_drawdown_pct_delta": 0.0,
        "strategy_behavior_changed": False,
        "event_rows": len(event_rows),
        "observation_rows": len(observation_rows),
        "pending_forward_rows": sum(
            1
            for row in observation_rows
            if row.get("outcome_status") == "pending_forward_close"
        ),
        "target_relation_quality_rows": len(target_rows),
        "target_relation_quality_tickers": len(
            {str(row.get("ticker")) for row in target_rows if row.get("ticker")}
        ),
        "event_date_count": len(event_dates),
        "event_dates": event_dates,
        "source_date_counts": dict(event_source_dates),
        "relation_counts": dict(Counter(str(row.get("relation_type") or "") for row in event_rows)),
        "polarity_counts": dict(Counter(str(row.get("relation_polarity") or "") for row in event_rows)),
        "ticker_counts": dict(Counter(str(row.get("ticker") or "") for row in event_rows)),
        "magnitude_rows": sum(
            1
            for row in event_rows
            if isinstance(row.get("magnitude"), Mapping)
            and row["magnitude"].get("has_numeric_magnitude")
        ),
    }
    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(LOG_JSON),
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
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": (
            "New 2026-07-01 prospective daily structured-news pending rows under "
            "the fixed accepted observer contract; this is not a relation-list, "
            "prompt, horizon, notional, ticker, or response-curve reslice."
        ),
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260630-005": (
                    "Observed-only positive structured daily-news relation-quality "
                    "lead, not promoted because coverage is forward-only and not "
                    "canonical-window complete."
                ),
                "exp-20260630-006": "Accepted shared daily structured-event observation contract.",
                "exp-20260630-007": "Accepted daily observer wiring.",
                "exp-20260701-003": "Recovered and recorded 2026-06-30 daily structured rows.",
                "exp-20260701-010": "Recorded 2026-07-01 intraday rows, not daily rows.",
                "novelty_gate": (
                    "Reservation passed without override; nearest neighbors were "
                    "the accepted observation contracts and no parked reopen guard "
                    "blocked this new date delta."
                ),
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept as measurement repair only if existing 2026-07-01 daily "
                "structured event and observation artifacts are present, nonzero, "
                "schema-complete, duplicate-free, include at least one target "
                "relation-quality row, rebuild to stable IDs in memory, and leave "
                "strategy metrics unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "date_tag": DATE_TAG,
            "iso_date": ISO_DATE,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "clean_trade_news": repo_rel(CLEAN_TRADE_NEWS),
            "structured_event_artifact": repo_rel(STRUCTURED_EVENT_FINAL),
            "structured_observation_artifact": repo_rel(STRUCTURED_OBSERVATION_FINAL),
            "observer_rule_version": DAILY_STRUCTURED_OBSERVER_RULE_VERSION,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": accepted,
            "dependencies_validated": bool(
                CLEAN_TRADE_NEWS.exists()
                and STRUCTURED_EVENT_FINAL.exists()
                and STRUCTURED_OBSERVATION_FINAL.exists()
            ),
            "fields_checked": [
                "event_id",
                "event_date",
                "ticker",
                "relation_type",
                "relation_polarity",
                "evidence_span",
                "source_provenance",
                "observation_id",
                "target_relation_quality",
                "entry_semantics",
                "exit_semantics",
                "entry_date",
                "target_price",
                "outcome_status",
            ],
            "event_required_field_audit": {
                "required_fields": list(event_required),
                "missing_counts": event_missing_counts,
                "all_required_fields_present": not event_missing_counts,
            },
            "observation_required_field_audit": {
                "required_fields": list(observation_required),
                "missing_counts": observation_missing_counts,
                "all_required_fields_present": not observation_missing_counts,
            },
            "duplicate_event_ids": count_duplicates(event_ids),
            "duplicate_observation_ids": count_duplicates(observation_ids),
            "entry_date_scope": (
                "Forward observations are pending; entry_date is intentionally null "
                "until a future settlement/closeout pass resolves next-session open."
            ),
            "target_price_scope": "No target exit is scheduled; target_price is intentionally null.",
            "artifact_write_audit": artifact_write_audit(),
            "in_memory_rebuild_stability": stability,
        },
        "gate3": {
            "passed": bool(event_rows and observation_rows),
            "filter_added": False,
            "signals_generated": len(event_rows),
            "signals_survived": len(observation_rows),
            "survival_rate": round(len(observation_rows) / len(event_rows), 6) if event_rows else None,
            "target_relation_quality_rows": len(target_rows),
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
        "delta_metrics": delta_metrics,
        "daily_structured_snapshot_audit": {
            "clean_payload_summary": summarize_clean_payload(clean_payload),
            "event_contract_audit": event_audit,
            "forward_observation_contract_audit": observation_audit,
            "source_artifact_audit": artifact_write_audit(),
            "sample_event_rows": event_rows[:8],
            "sample_observation_rows": observation_rows[:8],
        },
        "production_impact": {
            "run_adapter_changed": False,
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
            "news_archives_changed": False,
            "live_ready": False,
            "parity_note": (
                "Experiment reads existing read-only daily structured-news artifacts "
                "and writes only experiment-owned closeout files. It is not attached "
                "to prompts, quant_signals, orders, ranking, sizing, or exits."
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
                    mode == "missing_20260701_daily_structured_artifacts"
                    and (
                        "daily_structured_event_artifact_missing" in failed_reasons
                        or "daily_structured_observation_artifact_missing" in failed_reasons
                    )
                )
                or (
                    mode == "structured_observer_zero_rows"
                    and (
                        "structured_observer_zero_rows" in failed_reasons
                        or "structured_observation_zero_rows" in failed_reasons
                    )
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
                "The production daily structured-news observer already emitted "
                "schema-complete 2026-07-01 pending rows under the fixed accepted "
                "contract. The useful output is an experiment-owned delta record, "
                "not a new rule or row slice."
                if accepted
                else "The existing daily artifacts did not satisfy the fixed observer delta contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not slice these 2026-07-01 pending daily news rows by relation, "
                "ticker, source, prompt wording, magnitude, horizon, notional, or "
                "response curve before closed replacement-value outcomes exist."
            ),
            "new_evidence_required": (
                "Closed cash/SPY/QQQ replacement-value outcomes for these and later "
                "daily structured observations, materially more prospective daily "
                "captures under the same contract, or a PIT LLM scorer that writes "
                "the same evidence-span schema."
            ),
        },
        "next_retry_requires": [
            "closed structured-news forward outcomes for 2026-07-01 or later rows",
            "materially more prospective daily captures under the fixed observer",
            "PIT LLM labels persisted with the same evidence-span schema",
        ],
        "changed_files": changed_files,
        "related_files": [
            "quant/daily_news_text_sanitation.py",
            "quant/daily_news_structured_events.py",
            "quant/daily_news_structured_event_snapshot.py",
            repo_rel(CLEAN_TRADE_NEWS),
            repo_rel(STRUCTURED_EVENT_FINAL),
            repo_rel(STRUCTURED_OBSERVATION_FINAL),
            "experiments/logs/exp-20260630-005.json",
            "experiments/logs/exp-20260630-006.json",
            "experiments/logs/exp-20260630-007.json",
            "experiments/logs/exp-20260701-003.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_daily_news_structured_event_snapshot.py quant\\test_daily_news_structured_events.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner, py_compile, pytest, and experiment audit only.",
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
        "new_evidence_axis",
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
        "daily_structured_snapshot_audit",
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
            f"# {EXPERIMENT_ID}: daily news 2026-07-01 structured-event delta",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            "- Accepted alpha: no",
            "- Strategy behavior changed: no",
            f"- Event rows: `{delta['event_rows']}`",
            f"- Pending observation rows: `{delta['pending_forward_rows']}`",
            f"- Target relation-quality rows: `{delta['target_relation_quality_rows']}`",
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
        "source_artifacts_read_only": {
            repo_rel(CLEAN_TRADE_NEWS): {
                "exists": CLEAN_TRADE_NEWS.exists(),
                "sha256": sha256_file(CLEAN_TRADE_NEWS),
            },
            repo_rel(STRUCTURED_EVENT_FINAL): {
                "exists": STRUCTURED_EVENT_FINAL.exists(),
                "sha256": sha256_file(STRUCTURED_EVENT_FINAL),
            },
            repo_rel(STRUCTURED_OBSERVATION_FINAL): {
                "exists": STRUCTURED_OBSERVATION_FINAL.exists(),
                "sha256": sha256_file(STRUCTURED_OBSERVATION_FINAL),
            },
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
        "calibration": payload["calibration"],
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
            "new_evidence_axis": payload["new_evidence_axis"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "daily_structured_snapshot_audit": payload["daily_structured_snapshot_audit"],
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
