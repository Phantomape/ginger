"""exp-20260630-001: daily news text sanitation contract.

Measurement repair only. The experiment audits daily clean-news and
clean-trade-news archives for replayable text-quality metadata and leaves every
entry, exit, ranking, sizing, risk, paper, live, and backtest behavior
unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260630-001"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "daily_news_text_sanitation_contract"
RUNNER = f"quant/experiments/exp_20260630_001_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "daily_news_text_sanitation_contract_v1"
TRIAL_FAMILY = "daily_news_text_sanitation_contract"
TRIAL_VARIANT_ID = "daily_news_text_sanitation_contract_v1"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_measurement_repair"
CHANGE_TYPE = "identity_or_measurement_repair"
NEW_EVIDENCE_TYPE = "daily_news_archive_text_quality_contract"

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
for path in (SCRIPTS_DIR, QUANT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from daily_news_text_sanitation import build_daily_news_sanitation_audit  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NEWS_ROOT = REPO_ROOT / "data" / "daily" / "news"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALPHA_HYPOTHESIS = (
    "LLM/news event scoring can only become a production-replayable alpha input "
    "if daily clean-news text quality and ticker/entity provenance are audited "
    "before prompts or event labels consume the feed."
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
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
        "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=0.0,
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    before = baseline_metrics()
    audit = build_daily_news_sanitation_audit(NEWS_ROOT)
    repair_passed = bool(
        before.get("loaded")
        and audit["file_count"] > 0
        and audit["items"] > 0
        and audit["all_hash_fields_present"]
        and (audit["changed_items"] > 0 or audit["flagged_items"] > 0)
    )
    after = dict(before)
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
        "daily_news_files_audited": audit["file_count"],
        "daily_news_items_audited": audit["items"],
        "daily_news_flagged_items": audit["flagged_items"],
        "daily_news_changed_items": audit["changed_items"],
        "ignored_temp_file_count": audit["ignored_temp_file_count"],
    }
    predicted = ticket.get("prediction") or {}
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted_measurement_repair" if repair_passed else "blocked",
        "decision": (
            "accepted_measurement_repair_daily_news_text_sanitation_contract"
            if repair_passed
            else "blocked_daily_news_text_sanitation_contract"
        ),
        "accepted": repair_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": repair_passed,
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket.get("hypothesis") or ALPHA_HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "daily_news_llm_event_scoring_measurement_contract",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "daily clean-news archive scanner",
            "daily clean-trade-news archive scanner",
            "deterministic item-level text sanitation hashes",
            "ticker/entity provenance audit",
            "dot-temp residue exclusion",
            "focused unit tests",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": ["exp-20260629-012", "exp-20260616-027"],
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
            "realized_failure_mode": None if repair_passed else "daily_news_audit_failed",
            "surprise_level": "low" if repair_passed else "medium",
        },
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "daily_news_audit": audit,
        "gate1": {
            "passed": bool(before.get("loaded")),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": bool(audit["items"] > 0 and audit["all_hash_fields_present"]),
            "runtime_fields_checked": [
                "daily.clean_news[].title",
                "daily.clean_news[].summary",
                "daily.clean_news[].tickers",
                "daily.clean_trade_news[].title",
                "daily.clean_trade_news[].summary",
                "daily.clean_trade_news[].tier",
                "text_sanitation.pre_sanitize_hash",
                "text_sanitation.post_sanitize_hash",
                "text_sanitation.ticker_entity_status",
                "entry_date_not_applicable_no_strategy_rule_change",
                "target_price_not_applicable_no_strategy_rule_change",
            ],
            "field_status": {
                "file_count": audit["file_count"],
                "items": audit["items"],
                "all_hash_fields_present": audit["all_hash_fields_present"],
                "hash_fields_missing": audit["hash_fields_missing"],
                "ignored_temp_file_count": audit["ignored_temp_file_count"],
            },
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": (
                "No signal, filter, ranking, sizing, exit, risk budget, or order rule changed."
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
                "accepted_measurement_repair_daily_news_text_sanitation_contract"
                if repair_passed
                else "blocked_daily_news_text_sanitation_contract"
            ),
            "before_after_strategy_delta": delta,
            "failed_reasons": []
            if repair_passed
            else ["daily_news_files_missing_or_hash_contract_failed"],
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
            "daily_news_archives_rewritten": False,
            "daily_news_prompt_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "live_ready": False,
            "parity_note": (
                "Read-only helper and experiment artifact only. No daily news file, "
                "EOD signal, backtest, paper sleeve, live order, or strategy policy path changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Final daily clean-news archives contain enough rows to audit, and the "
                "text contract found deterministic quality/provenance risks including "
                "HTML unescaping, mojibake-suspect strings, and metadata-only ticker matches."
            ),
            "anti_repeat": (
                "Do not retune LLM prompts or trade decisions from sanitation flags alone. "
                "A future alpha needs a structured event label or closed replacement-value "
                "outcomes tied to these daily news rows."
            ),
            "next_step": (
                "Wire this contract into a daily event-scoring observation ledger only if "
                "the ledger records PIT labels and later cash/SPY/QQQ outcomes."
            ),
        },
        "next_retry_requires": [
            "a PIT daily news structured-event label with actor/object/relation/magnitude/provenance",
            "or closed replacement-value outcomes joined to daily news event rows",
        ],
        "changed_files": [
            "quant/daily_news_text_sanitation.py",
            "quant/test_daily_news_text_sanitation.py",
            RUNNER,
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_daily_news_text_sanitation.py -q",
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
        "audit_summary": {
            key: payload["daily_news_audit"][key]
            for key in [
                "rule_version",
                "file_count",
                "file_count_by_kind",
                "ignored_temp_file_count",
                "items",
                "changed_items",
                "flagged_items",
                "flag_counts",
                "status_counts",
                "ticker_entity_status_counts",
                "date_range",
            ]
        },
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
    audit = payload["daily_news_audit"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} daily news text sanitation contract",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            (
                f"- Scope: `{audit['file_count']}` final daily news files, "
                f"`{audit['items']}` items, `{audit['flagged_items']}` flagged, "
                f"`{audit['changed_items']}` changed."
            ),
            "- Production impact: read-only helper and artifact; no orders, ranking, sizing, exits, prompts, or source news files changed.",
            "- Next: require PIT structured labels or closed replacement-value outcomes before any LLM/news alpha response.",
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
        REPO_ROOT / "quant" / "daily_news_text_sanitation.py",
        REPO_ROOT / "quant" / "test_daily_news_text_sanitation.py",
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
        "audit_summary": compact_log(payload)["audit_summary"],
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
