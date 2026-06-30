"""exp-20260629-012: intraday news text sanitation contract.

Measurement repair only. The experiment adds replayable text-quality metadata
for intraday news passed to LLM prompts and leaves entries, exits, ranking,
sizing, risk budgets, paper orders, live orders, and backtest behavior unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260629-012"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "intraday_news_text_sanitation_contract"
RUNNER = f"quant/experiments/exp_20260629_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "intraday_news_text_sanitation_contract_v1"
TRIAL_FAMILY = "intraday_news_text_sanitation_contract"
TRIAL_VARIANT_ID = "mojibake_hidden_text_ticker_match_v1"
MECHANISM_FAMILY = "llm_event_scoring_measurement_repair"
CHANGE_TYPE = "llm_event_data_quality_repair"
NEW_EVIDENCE_TYPE = "new_llm_news_data_quality_axis"

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
for path in (SCRIPTS_DIR, QUANT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from news_text_sanitizer import annotate_news_items, build_news_sanitation_summary  # noqa: E402


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SAMPLE_NEWS = (
    REPO_ROOT
    / "data"
    / "daily"
    / "intraday"
    / "news"
    / "intraday_trade_news_20260629_1302ET.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALPHA_HYPOTHESIS = (
    "LLM event scoring can only become a production-replayable alpha input if "
    "intraday news text quality, hidden text, and ticker/entity provenance are "
    "audited before prompts consume the feed."
)
REGISTERED_HYPOTHESIS = (
    "LLM/news event scoring cannot be trusted if intraday trade news text with "
    "unexpanded HTML entities, hidden/control characters, mojibake, or "
    "ticker/entity mismatches is passed to prompts without a replayable "
    "sanitation audit; add a read-only intraday news sanitation contract that "
    "logs these risks without changing orders."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
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


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") or []
    return {
        "loaded": bool(windows),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "windows": [
            {
                "label": row.get("label"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
            }
            for row in windows
        ],
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 6
        ),
        "total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows), 2
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(
            int(row.get("signals_generated") or 0) for row in windows
        ),
        "signals_survived": sum(
            int(row.get("signals_survived") or 0) for row in windows
        ),
    }


def latest_trade_news_path() -> Path | None:
    if SAMPLE_NEWS.exists():
        return SAMPLE_NEWS
    candidates = sorted(
        (REPO_ROOT / "data" / "daily" / "intraday" / "news").glob(
            "intraday_trade_news_*.json"
        )
    )
    return candidates[-1] if candidates else None


def sample_audit() -> dict[str, Any]:
    sample_path = latest_trade_news_path()
    rows = read_json(sample_path, []) if sample_path else []
    if not isinstance(rows, list):
        rows = []
    annotated = annotate_news_items(rows)
    summary = build_news_sanitation_summary(annotated)
    examples = []
    for item in annotated:
        audit = item.get("text_sanitation") or {}
        if audit.get("flags"):
            examples.append(
                {
                    "title": str(item.get("title") or "")[:140],
                    "tickers": item.get("tickers") or [],
                    "status": audit.get("status"),
                    "flags": audit.get("flags") or [],
                    "ticker_entity_match": audit.get("ticker_entity_match") or {},
                }
            )
        if len(examples) >= 5:
            break
    hash_fields_present = all(
        (item.get("text_sanitation") or {}).get("pre_sanitize_hash")
        and (item.get("text_sanitation") or {}).get("post_sanitize_hash")
        for item in annotated
    )
    return {
        "sample_path": repo_rel(sample_path) if sample_path else None,
        "sample_exists": bool(sample_path and sample_path.exists()),
        "input_rows": len(rows),
        "summary": summary,
        "hash_fields_present": hash_fields_present,
        "annotated_examples": examples,
        "annotated_items_preview": annotated[:3],
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    before = baseline_metrics()
    audit = sample_audit()
    summary = audit["summary"]
    repair_passed = bool(
        before.get("loaded")
        and audit["sample_exists"]
        and audit["input_rows"] > 0
        and audit["hash_fields_present"]
        and (summary.get("changed_items", 0) > 0 or summary.get("flagged_items", 0) > 0)
    )
    after = dict(before)
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
        "intraday_news_items_audited": audit["input_rows"],
        "intraday_news_flagged_items": summary.get("flagged_items", 0),
        "intraday_news_changed_items": summary.get("changed_items", 0),
    }
    predicted = ticket.get("prediction") or {}
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted_measurement_repair" if repair_passed else "blocked",
        "decision": (
            "accepted_measurement_repair_intraday_news_text_sanitation_contract"
            if repair_passed
            else "blocked_intraday_news_text_sanitation_contract"
        ),
        "accepted": repair_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": repair_passed,
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": REGISTERED_HYPOTHESIS,
        "pre_run_hypothesis_note": (
            "The initial console read suggested mojibake in titles; file-level "
            "UTF-8 inspection showed correct Unicode titles and unexpanded HTML "
            "entities in summaries. The contract still covers mojibake/hidden "
            "text if it appears in future runs."
        ),
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "intraday_news_llm_prompt_measurement_contract",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "shared news text sanitizer",
            "raw and trade intraday news item annotations",
            "data_quality.news_text_sanitation summary",
            "LLM prompt exposure of text-quality risks",
            "focused unit tests",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments") or [],
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": predicted,
        "calibration": {
            "predicted_success_probability": predicted.get("success_probability"),
            "expected_ev_delta": predicted.get("expected_ev_delta"),
            "expected_pnl_delta": predicted.get("expected_pnl_delta"),
            "actual_success": 1 if repair_passed else 0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": predicted.get("main_failure_modes") or [],
            "realized_failure_mode": None if repair_passed else "sample_audit_failed",
            "surprise_level": "low" if repair_passed else "medium",
        },
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "sample_audit": audit,
        "gate1": {
            "passed": bool(before.get("loaded")),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": bool(audit["hash_fields_present"] and audit["input_rows"] > 0),
            "runtime_fields_checked": [
                "news.trade_items[].title",
                "news.trade_items[].summary",
                "news.trade_items[].tickers",
                "news.trade_items[].text_sanitation.pre_sanitize_hash",
                "news.trade_items[].text_sanitation.post_sanitize_hash",
                "data_quality.news_text_sanitation",
                "entry_date_not_applicable_no_strategy_rule_change",
                "target_price_not_applicable_no_strategy_rule_change",
            ],
            "field_status": {
                "sample_exists": audit["sample_exists"],
                "input_rows": audit["input_rows"],
                "hash_fields_present": audit["hash_fields_present"],
            "flagged_items": summary.get("flagged_items", 0),
            "changed_items": summary.get("changed_items", 0),
        },
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": (
                "No signal, filter, ranking, sizing, exit, risk budget, or order "
                "rule changed."
            ),
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": {
            "passed": repair_passed,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "decision": (
                "accepted_measurement_repair_intraday_news_text_sanitation_contract"
                if repair_passed
                else "blocked_intraday_news_text_sanitation_contract"
            ),
            "before_after_strategy_delta": delta,
            "failed_reasons": []
            if repair_passed
            else ["sample_missing_or_no_text_quality_signal_detected"],
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "shared_policy_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "intraday_advisory_prompt_changed": True,
            "intraday_advisory_snapshot_changed": True,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Intraday advisory artifacts only. No EOD signal, backtest, paper "
                "sleeve, live order, or shared strategy policy path consumes this."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The current intraday trade-news sample contains unexpanded "
                "HTML entities in summaries that were previously invisible to "
                "data_quality and LLM prompt context; the sanitizer records "
                "them with deterministic hashes while preserving original news "
                "fields. A file-level check corrected the initial terminal "
                "display impression of title mojibake."
            ),
            "anti_repeat": (
                "Do not retune prompts or trade decisions from this sample alone; "
                "next alpha work needs closed forward rows or a new LLM event "
                "scoring label with replayable outcomes."
            ),
            "next_step": (
                "Let future intraday runs accumulate sanitized news snapshots, "
                "then evaluate whether flagged LLM-news items explain advisory "
                "quality or forward replacement value."
            ),
        },
        "next_retry_requires": [
            "materially more closed intraday advisory forward rows",
            "or a new PIT LLM event label tied to replacement-value outcomes",
        ],
        "changed_files": [
            "quant/news_text_sanitizer.py",
            "quant/run_intraday.py",
            "quant/intraday_review.py",
            "quant/test_intraday_news_sanitizer.py",
            "quant/test_intraday_review.py",
            RUNNER,
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_intraday_news_sanitizer.py quant\\test_intraday_review.py -q",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "delta_metrics": payload["delta_metrics"],
        "sample_summary": payload["sample_audit"]["summary"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
    }


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["sample_audit"]["summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} intraday news text sanitation contract",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            (
                f"- Sample: `{payload['sample_audit']['input_rows']}` items, "
                f"`{summary.get('flagged_items', 0)}` flagged, "
                f"`{summary.get('changed_items', 0)}` changed."
            ),
            "- Production impact: intraday advisory prompt/snapshot metadata only; no orders, ranking, sizing, or exits changed.",
            "- Next: accumulate sanitized intraday rows before testing any LLM-event scoring alpha.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "news_text_sanitizer.py",
        REPO_ROOT / "quant" / "run_intraday.py",
        REPO_ROOT / "quant" / "intraday_review.py",
        REPO_ROOT / "quant" / "test_intraday_news_sanitizer.py",
        REPO_ROOT / "quant" / "test_intraday_review.py",
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "delta_metrics": payload["delta_metrics"],
        "sample_summary": payload["sample_audit"]["summary"],
        "gate2": payload["gate2"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
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
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "next_retry_requires",
            "changed_files",
            "reproduction_commands",
            "calibration",
        ]
        if key in payload
    }
    fields.update(
        {
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload.get("prediction") or {},
        result=result,
        status=payload["status"],
        fields=fields,
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
