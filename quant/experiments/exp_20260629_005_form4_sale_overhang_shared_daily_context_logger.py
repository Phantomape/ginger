"""exp-20260629-005: shared Form 4 sale-overhang context logger.

This measurement-repair runner verifies that the fixed PIT Form 4 sale/10b5-1/
officer-overhang fields are available through a shared daily non-OHLCV helper.
It writes only data artifacts and experiment records; no entry, exit, ranking,
sizing, risk-budget, or order behavior is changed.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
for path in (SCRIPTS_DIR, QUANT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from form4_sale_overhang_context import (  # noqa: E402
    DEFAULT_LOOKBACK_DAYS,
    FORWARD_REOPEN_GATE,
    RULE_VERSION,
    persist_form4_sale_overhang_context,
    source_file_date,
)
from daily_non_ohlcv_snapshot import persist_daily_non_ohlcv_snapshots  # noqa: E402
from backfill_non_ohlcv import ensure_non_ohlcv_coverage  # noqa: E402


EXPERIMENT_ID = "exp-20260629-005"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "form4_sale_overhang_shared_daily_context_logger"
RUNNER = f"quant/experiments/exp_20260629_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = RULE_VERSION
TRIAL_FAMILY = "form4_sale_overhang_shared_daily_context_logger"
TRIAL_VARIANT_ID = "shared_daily_non_ohlcv_context_v1"
MECHANISM_FAMILY = "production_visible_form4_selling_overhang_forward_context"
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "shared_daily_non_ohlcv_context_helper"
NEW_EVIDENCE_TYPE = "alpha_enabling_forward_context_shared_daily_surface"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
PROBE_DIR = OUT_DIR / "daily_non_ohlcv_probe"
OUT_JSON = OUT_DIR / f"exp_20260629_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALPHA_HYPOTHESIS = (
    "Risk allocation: fixed PIT Form 4 sale, 10b5-1, and officer-sale "
    "overhang may identify accepted-core/default-off entries with worse loss "
    "tail, but any alpha response requires prospectively logged shared daily "
    "context rows that later close with replacement-value evidence."
)

CAUSAL_COMPONENTS = [
    "shared Form4 sale-overhang helper",
    "daily non-OHLCV snapshot opt-in ledger",
    "backfill/catch-up opt-in hook",
    "focused helper and snapshot tests",
    "no strategy behavior change",
]

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260628-014",
    "exp-20260629-003",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
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
        if limit is not None and len(rows) >= limit:
            break
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
    if not windows:
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "loaded": True}
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
        "survival_rate": (
            round(signals_survived / signals_generated, 6) if signals_generated else None
        ),
        "max_drawdown_pct": max(float(row.get("max_drawdown_pct") or 0.0) for row in windows),
        "windows": windows,
    }


def latest_form4_source_date() -> date | None:
    days = [
        source_file_date(path)
        for path in NON_OHLCV_DIR.glob("form4_transactions_*.jsonl")
        if path.is_file()
    ]
    days = [day for day in days if day is not None]
    return max(days) if days else None


def wiring_audit() -> dict[str, Any]:
    daily_params = set(inspect.signature(persist_daily_non_ohlcv_snapshots).parameters)
    backfill_params = set(inspect.signature(ensure_non_ohlcv_coverage).parameters)
    required_daily = {"refresh_form4_context", "form4_context_lookback_days"}
    required_backfill = {"refresh_form4_context", "form4_context_lookback_days"}
    return {
        "daily_snapshot_params_present": sorted(required_daily & daily_params),
        "backfill_params_present": sorted(required_backfill & backfill_params),
        "daily_snapshot_wired": required_daily <= daily_params,
        "backfill_wired": required_backfill <= backfill_params,
    }


def build_reopen_condition(context_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "surface": "Form4 sale/10b5/officer overhang",
        "status": "shared_forward_logging_open_not_alpha_ready",
        "blocking_reason": "closed_forward_replacement_rows_not_materialized",
        "current_counts": {
            "shared_daily_context_rows_logged": int(context_summary.get("rows_written") or 0),
            "shared_daily_high_sale_overhang_rows_logged": int(
                context_summary.get("rows_with_high_sale_overhang") or 0
            ),
            "shared_daily_tickers_logged": int(context_summary.get("ticker_count") or 0),
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
    before = baseline_metrics()
    as_of = latest_form4_source_date()
    if as_of is None:
        raise RuntimeError("no local form4_transactions_YYYYMMDD.jsonl files found")

    context_summary = persist_form4_sale_overhang_context(
        as_of=as_of,
        data_dir=NON_OHLCV_DIR,
        output_dir=PROBE_DIR,
        lookback_days=DEFAULT_LOOKBACK_DAYS,
    )
    context_rows = read_jsonl(Path(context_summary["output_path"]), limit=30)
    wire = wiring_audit()
    reopen_condition = build_reopen_condition(context_summary)

    expected_fields = {
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
    sample_field_passed = bool(context_rows) and expected_fields <= set(context_rows[0])
    gate2_passed = bool(
        context_summary.get("rows_written")
        and context_summary.get("source_audit", {}).get("deduped_rows_loaded")
        and context_summary.get("daily_snapshot_wired")
        and wire["daily_snapshot_wired"]
        and wire["backfill_wired"]
        and sample_field_passed
    )
    repair_passed = bool(before.get("loaded") and gate2_passed)
    after = dict(before)
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted_measurement_repair" if repair_passed else "blocked",
        "decision": (
            "accepted_measurement_repair_form4_sale_overhang_shared_daily_context_logger"
            if repair_passed
            else "blocked_form4_sale_overhang_shared_daily_context_logger"
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
        "prediction": ticket.get("prediction") or {},
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "context_as_of": as_of.isoformat(),
        "context_summary": context_summary,
        "context_sample_rows": context_rows,
        "wiring_audit": wire,
        "reopen_condition": reopen_condition,
        "gate1": {
            "passed": bool(before.get("loaded")),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": gate2_passed,
            "runtime_fields_checked": sorted(expected_fields),
            "field_status": {
                "form4_archive": "loaded_from_daily_pit_form4_transactions_jsonl_files",
                "daily_snapshot_wiring": wire["daily_snapshot_wired"],
                "backfill_wiring": wire["backfill_wired"],
                "output_path": context_summary.get("output_path"),
                "summary_output": context_summary.get("summary_output"),
            },
            "counts": {
                "form4_rows_loaded": context_summary.get("source_audit", {}).get(
                    "deduped_rows_loaded"
                ),
                "context_rows": context_summary.get("rows_written"),
                "high_sale_overhang_rows": context_summary.get(
                    "rows_with_high_sale_overhang"
                ),
                "ticker_count": context_summary.get("ticker_count"),
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
                "accepted_measurement_repair_form4_sale_overhang_shared_daily_context_logger"
                if repair_passed
                else "blocked_form4_sale_overhang_shared_daily_context_logger"
            ),
            "before_after_strategy_delta": delta,
            "reopen_condition": reopen_condition,
            "failed_reasons": [] if repair_passed else ["shared_context_contract_not_met"],
        },
        "anti_js": {
            "used_javascript": False,
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "uses_future_form4_rows": False,
            "new_download_attempts": False,
            "response_curve_retune": False,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "shared_policy_changed": False,
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "daily_snapshot_exposed": True,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Shared daily context helper and opt-in daily/backfill wiring only. "
                "No trading policy consumes the field."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "exp-20260628-014 found a positive observed-only Form4 sale-"
                "overhang loss-tail lead, and exp-20260629-003 proved a fixed "
                "experiment-owned logger could tag current rows. This run exposes "
                "that fixed context through shared daily plumbing; it is not a "
                "threshold, role, 10b5, lookback, or response-curve retune."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if baseline metrics are "
                "unchanged, the shared helper emits PIT context rows, daily and "
                "backfill opt-in hooks exist, and production impact remains "
                "data-only."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The local Form4 archive already contains PIT usable_trade_date "
                "records, so the fixed sale-overhang summary can be written as a "
                "shared daily context ledger. That removes the production-visible "
                "logging blocker but still does not create a closed forward "
                "replacement-value sample."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry Form4 sale overhang by changing sale thresholds, "
                "transaction-code lists, 10b5 handling, owner roles, lookback days, "
                "or hard-exclusion/downweight/tilt/notional response shape on the "
                "same observed-only evidence."
            ),
            "new_evidence_required": (
                "Shared daily Form4 context rows must close with cash/SPY/QQQ "
                "replacement value: at least 25 closed rows, at least 8 high-sale-"
                "overhang rows, and max single-ticker share <=40%."
            ),
        },
        "next_retry_requires": (
            "A future Form4 alpha response requires materially advanced closed "
            "forward rows under reopen_condition or a distinct new data source/gate shape."
        ),
        "related_files": [
            RUNNER,
            "quant/form4_sale_overhang_context.py",
            "quant/daily_non_ohlcv_snapshot.py",
            "quant/backfill_non_ohlcv.py",
            "quant/test_form4_sale_overhang_context.py",
            "quant/test_daily_non_ohlcv_snapshot.py",
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(NON_OHLCV_DIR),
        ],
        "changed_files": [
            "quant/form4_sale_overhang_context.py",
            "quant/daily_non_ohlcv_snapshot.py",
            "quant/backfill_non_ohlcv.py",
            "quant/test_form4_sale_overhang_context.py",
            "quant/test_daily_non_ohlcv_snapshot.py",
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\form4_sale_overhang_context.py quant\\daily_non_ohlcv_snapshot.py quant\\backfill_non_ohlcv.py "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_form4_sale_overhang_context.py quant\\test_daily_non_ohlcv_snapshot.py",
            RUNNER_COMMAND,
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
        "wiring_audit",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "reopen_condition",
        "production_impact",
        "pre_run_questions",
        "prediction",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    row["lean_quality_passed"] = bool(payload["gate4"]["passed"])
    return row


def build_card(payload: dict[str, Any]) -> str:
    counts = payload["reopen_condition"]["current_counts"]
    required = payload["reopen_condition"]["required_to_reopen"]
    buckets = payload["context_summary"].get("form4_sale_overhang_bucket_counts") or {}
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Form4 Shared Daily Context Logger",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Context as-of: `{payload['context_as_of']}`",
            f"- Shared context rows: `{counts['shared_daily_context_rows_logged']}`",
            f"- High-overhang rows: `{counts['shared_daily_high_sale_overhang_rows_logged']}`",
            f"- Bucket counts: `{json.dumps(buckets, sort_keys=True)}`",
            f"- Daily snapshot wired: `{payload['wiring_audit']['daily_snapshot_wired']}`",
            f"- Backfill wired: `{payload['wiring_audit']['backfill_wired']}`",
            "",
            "## Reopen Condition",
            "",
            (
                "Reopen a Form4 risk response only after shared daily rows close "
                f"with at least `{required['closed_forward_rows_min']}` closed rows, "
                f"`{required['high_sale_overhang_forward_rows_min']}` high-overhang "
                "rows, cash/SPY/QQQ replacement values, and max single-ticker share "
                "<= 40%."
            ),
            "",
            "## Interpretation",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / "quant" / "form4_sale_overhang_context.py",
        REPO_ROOT / "quant" / "daily_non_ohlcv_snapshot.py",
        REPO_ROOT / "quant" / "backfill_non_ohlcv.py",
        REPO_ROOT / "quant" / "test_form4_sale_overhang_context.py",
        REPO_ROOT / "quant" / "test_daily_non_ohlcv_snapshot.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
        Path(payload["context_summary"].get("output_path") or ""),
        Path(payload["context_summary"].get("summary_output") or ""),
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
            if str(path)
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
        "summary": payload["post_run_reflection"]["why_result_happened"],
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
