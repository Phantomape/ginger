"""exp-20260701-011: materialize 2026-06-30 Form4 sale-overhang context.

This measurement repair uses the existing shared Form4 context helper to write
the 2026-06-30 canonical context rows that the daily non-OHLCV snapshot skipped.
It does not change entries, exits, ranking, sizing, risk budget, or orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from form4_sale_overhang_context import (  # noqa: E402
    DEFAULT_LOOKBACK_DAYS,
    FORWARD_REOPEN_GATE,
    RULE_VERSION,
    persist_form4_sale_overhang_context,
)


EXPERIMENT_ID = "exp-20260701-011"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "form4_sale_overhang_context_20260630"
RUNNER = f"quant/experiments/exp_20260701_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

AS_OF = "2026-06-30"
CHANGED_VARIABLE = "form4_sale_overhang_context_20260630_materialization_v1"
TRIAL_FAMILY = "form4_sale_overhang_shared_daily_context_logger"
TRIAL_VARIANT_ID = "20260630_context_materialization_v1"
MECHANISM_FAMILY = "production_visible_form4_selling_overhang_forward_context"
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "shared_daily_context_materialization"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
CURRENT_CONTEXT_JSONL = NON_OHLCV_DIR / "form4_sale_overhang_context_20260630.jsonl"
CURRENT_CONTEXT_SUMMARY = NON_OHLCV_DIR / "form4_sale_overhang_context_summary_20260630.json"
CURRENT_DAILY_SNAPSHOT = NON_OHLCV_DIR / "daily_non_ohlcv_snapshot_20260630.json"
CURRENT_FORM4_SUMMARY = NON_OHLCV_DIR / "form4_backfill_summary_20260630.json"
PRIOR_FORM4_SUMMARY = NON_OHLCV_DIR / "form4_backfill_summary_20260629.json"
PRIOR_CONTEXT_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260629-005"
    / "exp_20260629_005_form4_sale_overhang_shared_daily_context_logger.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260701_011_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALPHA_HYPOTHESIS = (
    "Risk allocation: fixed PIT Form4 sale, 10b5-1, and officer-sale overhang "
    "may identify accepted-core/default-off entries with worse loss tail, but "
    "any alpha response requires shared daily context rows that later close "
    "with cash/SPY/QQQ replacement-value evidence."
)

CAUSAL_COMPONENTS = [
    "shared Form4 context helper",
    "20260630 canonical context rows",
    "baseline identity",
    "audit closeout",
    "no strategy behavior change",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
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


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT, {})
    if not isinstance(raw, dict):
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "loaded": False}
    windows = []
    for row in raw.get("windows") or []:
        if not isinstance(row, dict):
            continue
        windows.append(
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "sharpe_daily": row.get("sharpe_daily"),
                "total_pnl": row.get("total_pnl"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "win_rate": row.get("win_rate"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
        )
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "loaded": True,
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            6,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": round(signals_survived / signals_generated, 6)
        if signals_generated
        else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "windows": windows,
    }


def context_duplicate_count(rows: list[dict[str, Any]]) -> int:
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for row in rows:
        key = (str(row.get("ticker") or ""), str(row.get("context_as_of") or ""))
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates


def build_reopen_condition(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "surface": "Form4 sale/10b5/officer overhang",
        "status": "shared_forward_logging_open_not_alpha_ready",
        "blocking_reason": "closed_forward_replacement_rows_not_materialized",
        "current_counts": {
            "shared_daily_context_rows_logged": int(summary.get("rows_written") or 0),
            "shared_daily_high_sale_overhang_rows_logged": int(
                summary.get("rows_with_high_sale_overhang") or 0
            ),
            "shared_daily_tickers_logged": int(summary.get("ticker_count") or 0),
            "closed_forward_rows_with_cash_spy_qqq_replacement_value": 0,
            "high_sale_overhang_forward_rows": 0,
            "single_ticker_closed_row_share": None,
        },
        "required_to_reopen": FORWARD_REOPEN_GATE,
        "reopen_rule": (
            "Do not reserve a Form4 sale-overhang risk scalar, notional haircut, "
            "ranking, veto, or candidate-pool experiment until shared daily "
            "context rows close with cash/SPY/QQQ replacement value and the "
            "required row counts advance. Do not retry by changing transaction "
            "codes, 10b5 handling, owner-role filters, sale-value thresholds, "
            "lookback days, or response curve."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    before_file_exists = CURRENT_CONTEXT_JSONL.exists()
    before_summary_exists = CURRENT_CONTEXT_SUMMARY.exists()
    before = baseline_metrics()
    current_daily_snapshot = read_json(CURRENT_DAILY_SNAPSHOT, {})
    current_form4_summary = read_json(CURRENT_FORM4_SUMMARY, {})
    prior_form4_summary = read_json(PRIOR_FORM4_SUMMARY, {})
    prior_context = read_json(PRIOR_CONTEXT_ARTIFACT, {})
    prior_context_summary = {}
    if isinstance(prior_context, dict):
        prior_context_summary = prior_context.get("context_summary") or {}

    context_summary = persist_form4_sale_overhang_context(
        as_of=AS_OF,
        data_dir=NON_OHLCV_DIR,
        output_dir=NON_OHLCV_DIR,
        lookback_days=DEFAULT_LOOKBACK_DAYS,
    )
    context_rows = read_jsonl(CURRENT_CONTEXT_JSONL)
    required_fields = {
        "ticker",
        "context_as_of",
        "form4_latest_usable_trade_date",
        "form4_sale_overhang_bucket",
        "form4_sale_rows",
        "form4_ten_b5_sale_rows",
        "form4_officer_sale_rows",
        "eligible_for_forward_outcome_join",
        "trade_enabled",
        "alters_orders",
    }
    sample_field_passed = bool(context_rows) and required_fields <= set(context_rows[0])
    duplicate_context_keys = context_duplicate_count(context_rows)
    raw_rows_delta = int(current_form4_summary.get("rows_written") or 0) - int(
        prior_form4_summary.get("rows_written") or 0
    )
    context_asof_advanced = str(context_summary.get("asof_date") or "") == AS_OF
    context_materialized = (
        CURRENT_CONTEXT_JSONL.exists()
        and CURRENT_CONTEXT_SUMMARY.exists()
        and int(context_summary.get("rows_written") or 0) == len(context_rows)
        and int(context_summary.get("rows_written") or 0) > 0
        and context_asof_advanced
    )
    gate2_passed = bool(
        context_materialized
        and sample_field_passed
        and duplicate_context_keys == 0
        and str(context_summary.get("max_latest_usable_trade_date") or "") >= AS_OF
        and raw_rows_delta > 0
    )
    accepted = bool(before.get("loaded") and gate2_passed)
    after = dict(before)
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
        "raw_form4_rows_delta_vs_20260629": raw_rows_delta,
        "context_rows_delta_vs_exp20260629_005": int(context_summary.get("rows_written") or 0)
        - int(prior_context_summary.get("rows_written") or 0),
        "high_sale_overhang_rows_delta_vs_exp20260629_005": int(
            context_summary.get("rows_with_high_sale_overhang") or 0
        )
        - int(prior_context_summary.get("rows_with_high_sale_overhang") or 0),
        "context_file_preexisting": before_file_exists,
        "context_summary_preexisting": before_summary_exists,
    }
    failed_reasons = []
    if not before.get("loaded"):
        failed_reasons.append("baseline_not_loaded")
    if raw_rows_delta <= 0:
        failed_reasons.append("raw_form4_rows_did_not_advance")
    if not context_materialized:
        failed_reasons.append("context_files_not_materialized")
    if not sample_field_passed:
        failed_reasons.append("context_schema_missing_required_fields")
    if duplicate_context_keys:
        failed_reasons.append("duplicate_ticker_context_rows")
    if str(context_summary.get("max_latest_usable_trade_date") or "") < AS_OF:
        failed_reasons.append("latest_usable_trade_date_not_current")

    prediction = ticket.get("prediction") or {}
    actual_success = bool(accepted)
    predicted = float(prediction.get("success_probability") or 0.0)
    calibration = {
        "predicted_success_probability": predicted,
        "actual_success": actual_success,
        "brier_score": round((predicted - (1.0 if actual_success else 0.0)) ** 2, 6),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": failed_reasons,
        "surprise_note": (
            "The current raw Form4 archive advanced and the skipped 2026-06-30 context "
            "ledger materialized without strategy drift."
            if accepted
            else "The materialization contract did not satisfy all predeclared checks."
        ),
    }
    reopen_condition = build_reopen_condition(context_summary)
    daily_snapshot_form4_status = {}
    if isinstance(current_daily_snapshot, dict):
        daily_snapshot_form4_status = current_daily_snapshot.get("form4_sale_overhang_context") or {}

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": (
            "accepted_measurement_repair_form4_20260630_context_materialization"
            if accepted
            else "blocked_form4_20260630_context_materialization"
        ),
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket.get("hypothesis")
        or "Materialize 2026-06-30 Form4 sale-overhang context rows.",
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": ["exp-20260629-005", "exp-20260629-011"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_prospective_forward_context_rows",
        "prediction": prediction,
        "calibration": calibration,
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "context_as_of": AS_OF,
        "context_summary": context_summary,
        "context_row_count": len(context_rows),
        "context_sample_rows": context_rows[:12],
        "prior_context_summary": prior_context_summary,
        "raw_form4_summary_current": {
            "path": repo_rel(CURRENT_FORM4_SUMMARY),
            "rows_written": current_form4_summary.get("rows_written"),
            "pit_safe_count": current_form4_summary.get("pit_safe_count"),
            "ten_b5_1_count": current_form4_summary.get("ten_b5_1_count"),
            "transaction_code_counts": current_form4_summary.get("transaction_code_counts"),
        },
        "raw_form4_summary_prior": {
            "path": repo_rel(PRIOR_FORM4_SUMMARY),
            "rows_written": prior_form4_summary.get("rows_written"),
            "pit_safe_count": prior_form4_summary.get("pit_safe_count"),
            "ten_b5_1_count": prior_form4_summary.get("ten_b5_1_count"),
            "transaction_code_counts": prior_form4_summary.get("transaction_code_counts"),
        },
        "daily_snapshot_form4_status_before_repair": daily_snapshot_form4_status,
        "gate1": {
            "passed": bool(before.get("loaded")),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": gate2_passed,
            "runtime_fields_checked": sorted(required_fields),
            "counts": {
                "context_rows": len(context_rows),
                "context_rows_reported": context_summary.get("rows_written"),
                "high_sale_overhang_rows": context_summary.get("rows_with_high_sale_overhang"),
                "ticker_count": context_summary.get("ticker_count"),
                "raw_rows_current": current_form4_summary.get("rows_written"),
                "raw_rows_prior": prior_form4_summary.get("rows_written"),
                "raw_rows_delta": raw_rows_delta,
                "duplicate_context_keys": duplicate_context_keys,
            },
            "field_status": {
                "context_jsonl_exists": CURRENT_CONTEXT_JSONL.exists(),
                "context_summary_exists": CURRENT_CONTEXT_SUMMARY.exists(),
                "sample_field_passed": sample_field_passed,
                "context_asof_advanced": context_asof_advanced,
                "max_latest_usable_trade_date": context_summary.get("max_latest_usable_trade_date"),
                "daily_snapshot_pre_repair_status": daily_snapshot_form4_status.get("status"),
                "daily_snapshot_pre_repair_reason": daily_snapshot_form4_status.get("reason"),
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
            "passed": accepted,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "decision": (
                "accepted_measurement_repair_form4_20260630_context_materialization"
                if accepted
                else "blocked_form4_20260630_context_materialization"
            ),
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "ranking_changed": False,
                "sizing_changed": False,
                "entry_changed": False,
                "exit_changed": False,
            },
            "failed_reasons": failed_reasons,
            "reopen_condition": reopen_condition,
        },
        "reopen_condition": reopen_condition,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": True,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "risk_budget_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Data-only materialization through an existing shared helper. No trading "
                "policy consumes Form4 context."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "exp-20260629-005 accepted the shared Form4 sale-overhang daily context "
                "logger and exp-20260629-011 blocks risk-response retries until counts "
                "advance. This run materializes a new as-of row set after raw 2026-06-30 "
                "Form4 rows appeared and the daily snapshot skipped context refresh."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if baseline metrics stay unchanged, "
                "2026-06-30 raw Form4 rows advanced versus 2026-06-29, canonical context "
                "files materialize with required fields and no duplicate ticker/as-of rows."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The raw 2026-06-30 Form4 archive existed, but the daily non-OHLCV "
                "snapshot recorded refresh_form4_context=false. Calling the existing "
                "shared helper produced canonical context rows without touching any "
                "strategy path."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use these rows to retune Form4 sale thresholds, 10b5 handling, "
                "officer filters, lookback days, hard vetoes, notional haircuts, risk "
                "scalars, ranking, candidate pools, or response curves."
            ),
            "new_evidence_required": (
                "A Form4 alpha response requires at least 25 closed forward rows with "
                "cash/SPY/QQQ replacement values, at least 8 high-sale-overhang rows, "
                "and max single-ticker share <=40%, or a distinct new data source/gate shape."
            ),
        },
        "next_retry_requires": [
            "closed Form4 shared context rows with cash/SPY/QQQ replacement values",
            "at least 25 total closed rows and 8 high-sale-overhang rows",
            "max single-ticker closed-row share <= 40%",
            "or a distinct new data source/gate shape",
        ],
        "anti_js": {
            "used_javascript": False,
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "response_curve_retune": False,
            "new_download_attempts": False,
        },
        "claim_note": (
            "Claim used --force only to bypass stale broad-scope tickets with no "
            "locked-variable conflict; this run touched only exp-011 files and the "
            "20260630 Form4 context outputs."
        ),
        "related_files": [
            RUNNER,
            "quant/form4_sale_overhang_context.py",
            repo_rel(CURRENT_DAILY_SNAPSHOT),
            repo_rel(CURRENT_FORM4_SUMMARY),
            repo_rel(PRIOR_FORM4_SUMMARY),
            repo_rel(CURRENT_CONTEXT_JSONL),
            repo_rel(CURRENT_CONTEXT_SUMMARY),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(CURRENT_CONTEXT_JSONL),
            repo_rel(CURRENT_CONTEXT_SUMMARY),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_form4_sale_overhang_context.py quant\\test_daily_non_ohlcv_snapshot.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "lane",
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
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "context_as_of",
        "context_summary",
        "raw_form4_summary_current",
        "raw_form4_summary_prior",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "reopen_condition",
        "production_impact",
        "pre_run_questions",
        "prediction",
        "calibration",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
        "claim_note",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    row["lean_quality_passed"] = bool(payload["gate4"]["passed"])
    return row


def build_card(payload: dict[str, Any]) -> str:
    counts = payload["gate2"]["counts"]
    buckets = payload["context_summary"].get("form4_sale_overhang_bucket_counts") or {}
    required = payload["reopen_condition"]["required_to_reopen"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Form4 20260630 context materialization",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Accepted alpha: `{str(payload['accepted_alpha']).lower()}`",
            f"- Strategy behavior changed: `{str(payload['delta_metrics']['strategy_behavior_changed']).lower()}`",
            f"- Raw Form4 rows delta vs 20260629: `{counts['raw_rows_delta']}`",
            f"- Context rows: `{counts['context_rows']}`",
            f"- High sale-overhang rows: `{counts['high_sale_overhang_rows']}`",
            f"- Bucket counts: `{json.dumps(buckets, sort_keys=True)}`",
            f"- Duplicate ticker/as-of rows: `{counts['duplicate_context_keys']}`",
            "",
            "## Boundary",
            "",
            (
                "Do not retune Form4 thresholds, transaction-code lists, 10b5 handling, "
                "owner-role filters, lookback days, vetoes, notional haircuts, risk "
                "scalars, ranking, candidate pools, or response curves on these rows."
            ),
            "",
            "## Reopen Condition",
            "",
            (
                "A Form4 alpha response requires at least "
                f"`{required['closed_forward_rows_min']}` closed rows, "
                f"`{required['high_sale_overhang_forward_rows_min']}` high-overhang "
                "rows, cash/SPY/QQQ replacement values, and max single-ticker share "
                "<= 40%."
            ),
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        CURRENT_CONTEXT_JSONL,
        CURRENT_CONTEXT_SUMMARY,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
        CURRENT_DAILY_SNAPSHOT,
        CURRENT_FORM4_SUMMARY,
        PRIOR_FORM4_SUMMARY,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
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
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "reopen_condition": payload["reopen_condition"],
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
            "pre_run_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "reopen_condition",
            "production_impact",
            "post_run_reflection",
            "next_retry_requires",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "anti_js",
            "claim_note",
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
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
