"""exp-20260628-016: Form 144 planned-sale/float context logger.

Alpha-enabling measurement repair. This run wires a default-off PIT Form 144
planned-sale context surface so future accepted-core/default-off forward rows
can be tagged before any risk or allocation policy is tested.
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
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import backfill_non_ohlcv  # noqa: E402
import daily_non_ohlcv_snapshot  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from form144_planned_sale_context import (  # noqa: E402
    FORWARD_REOPEN_GATE,
    OUTCOME_JOIN_SCHEMA,
    RULE_VERSION,
    entry_context_schema,
    persist_form144_planned_sale_context,
)


EXPERIMENT_ID = "exp-20260628-016"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "form144_planned_sale_context_logger"
RUNNER = f"quant/experiments/exp_20260628_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "form144_planned_sale_float_context_logger_v1"
TRIAL_FAMILY = "form144_planned_sale_float_context_logger"
TRIAL_VARIANT_ID = "pit_planned_sale_float_adv_context_v1"
MECHANISM_FAMILY = "production_visible_form144_planned_sale_forward_context"
CHANGE_TYPE = "forward_context_logger"
IMPLEMENTATION_MODE = "shared_default_off_forward_context_logger"
DECISION = "accepted_measurement_repair_form144_planned_sale_context_logger"
STATUS = "accepted_measurement_repair"

AS_OF = "2026-06-28"
LOOKBACK_DAYS = 90
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
BASELINE_RESULT = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_016_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha-enabling Form 144 planned-sale/float context logger: parse PIT "
    "Form 144 planned sale shares/value and attach as-of-entry "
    "planned-sale-to-float/ADV context to accepted-core/default-off forward "
    "rows without changing ranking, sizing, exits, or orders."
)
CAUSAL_COMPONENTS = [
    "Form144 PIT parser",
    "append-only planned-sale ledger",
    "as-of-entry context tags",
    "outcome join schema",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260612-023",
    "exp-20260613-013",
    "exp-20260616-008",
    "exp-20260628-014",
]
NEW_EVIDENCE_TYPE = "new_pit_form144_planned_sale_float_field_and_forward_context_logger"
NEW_EVIDENCE_AXIS = (
    "Form144 planned-sale/float PIT parser and forward context logger: new "
    "field surface beyond Form4 sale-overhang attribution and prior Form144 "
    "index-only candidate-pool tests."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
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
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("total_trades") or row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "sharpe_daily": row.get("sharpe_daily"),
            }
        )
    if windows:
        return {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "loaded": True,
            "window_count": len(windows),
            "expected_value_score_sum": round(
                sum(float(row.get("expected_value_score") or 0.0) for row in windows), 6
            ),
            "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
            "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
            "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
            "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
            "max_drawdown_pct_worst": max(
                float(row.get("max_drawdown_pct") or 0.0) for row in windows
            ),
            "windows": windows,
        }
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "loaded": True,
        "expected_value_score": raw.get("expected_value_score"),
        "total_pnl": raw.get("total_pnl"),
        "trade_count": raw.get("total_trades") or raw.get("trade_count"),
        "signals_generated": raw.get("signals_generated"),
        "signals_survived": raw.get("signals_survived"),
        "survival_rate": raw.get("survival_rate"),
    }


def build_contract() -> dict[str, Any]:
    daily_sig = inspect.signature(daily_non_ohlcv_snapshot.persist_daily_non_ohlcv_snapshots)
    backfill_sig = inspect.signature(backfill_non_ohlcv.ensure_non_ohlcv_coverage)
    return {
        "daily_snapshot_accepts_refresh_form144_context": "refresh_form144_context"
        in daily_sig.parameters,
        "daily_snapshot_accepts_form144_context_lookback_days": "form144_context_lookback_days"
        in daily_sig.parameters,
        "backfill_accepts_refresh_form144_context": "refresh_form144_context"
        in backfill_sig.parameters,
        "backfill_accepts_form144_context_lookback_days": "form144_context_lookback_days"
        in backfill_sig.parameters,
        "default_refresh_enabled": daily_sig.parameters[
            "refresh_form144_context"
        ].default
        is True
        if "refresh_form144_context" in daily_sig.parameters
        else None,
        "fail_soft_helper": "daily_non_ohlcv_snapshot._run_form144_planned_sale_context",
        "ledger_partition": "data/non_ohlcv/form144_planned_sale_context_YYYYMMDD.jsonl",
        "summary_partition": "data/non_ohlcv/form144_planned_sale_context_summary_YYYYMMDD.json",
    }


def evaluate_gate4(summary: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if not contract["daily_snapshot_accepts_refresh_form144_context"]:
        failures.append("daily_snapshot_missing_refresh_form144_context_arg")
    if not contract["backfill_accepts_refresh_form144_context"]:
        failures.append("backfill_missing_refresh_form144_context_arg")
    if contract["default_refresh_enabled"] is not False:
        failures.append("form144_context_not_default_off")
    if not Path(str(summary.get("output_path") or "")).exists():
        failures.append("form144_context_ledger_not_written")
    if not Path(str(summary.get("summary_output") or "")).exists():
        failures.append("form144_context_summary_not_written")
    if not OUTCOME_JOIN_SCHEMA.get("join_keys"):
        failures.append("outcome_join_schema_missing")
    if not entry_context_schema().get("context_fields"):
        failures.append("entry_context_schema_missing")
    if summary.get("trade_enabled") is not False:
        failures.append("trade_enabled_not_false")
    return {
        "passed": not failures,
        "decision": DECISION if not failures else "rejected_form144_context_logger_wiring",
        "failed_reasons": failures,
        "measurement_repair_only": True,
        "accepted_alpha": False,
        "alpha_ready": False,
        "acceptance_rule": (
            "Accept only as alpha-enabling measurement repair if a PIT Form144 "
            "planned-sale ledger, daily default-off snapshot wiring, entry "
            "context schema, outcome join schema, and explicit forward reopen "
            "gate are present with no strategy behavior change."
        ),
        "forward_reopen_gate": FORWARD_REOPEN_GATE,
        "current_forward_gate_ready": False,
        "current_forward_gate_status": {
            "closed_forward_rows": 0,
            "high_planned_sale_float_bucket_rows": 0,
            "single_ticker_share": None,
            "reason": "forward outcome rows have not matured; this run only creates the PIT context logger",
        },
        "before_after_strategy_delta": {
            "strategy_behavior_changed": False,
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
        },
    }


def calibration(gate4: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4["passed"] else 0
    prob = float(prediction.get("success_probability") or 0.0)
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": prob,
        "brier_score": round((prob - actual_success) ** 2, 6),
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_mode": ";".join(gate4.get("failed_reasons") or []),
        "predicted_failure_mode_hit": bool(gate4.get("failed_reasons")),
        "surprise_note": (
            "Form144 planned-sale context logger materialized as default-off "
            "data plumbing; current alpha gate remains waiting on closed "
            "forward rows and cached/parseable Form144 documents."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") or {}
    before = baseline_metrics()
    summary = persist_form144_planned_sale_context(
        as_of=AS_OF,
        data_dir=NON_OHLCV_DIR,
        lookback_days=LOOKBACK_DAYS,
    )
    contract = build_contract()
    gate4 = evaluate_gate4(summary, contract)
    status = STATUS if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    why = (
        "The blocker was missing shared default-off Form144 planned-sale "
        "context plumbing. The new parser/logger writes a PIT daily ledger and "
        "daily plus catch-up wiring while leaving all strategy behavior unchanged. "
        "Local index rows are present, but cached primary documents and closed "
        "forward outcomes are still the reopen condition for an alpha test."
        if gate4["passed"]
        else "The Form144 context logger failed its default-off wiring or schema checks."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": gate4["passed"],
        "accepted_alpha": False,
        "accepted_measurement_repair": gate4["passed"],
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(gate4, prediction),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted exp-20260628-016 with override axis recorded and no blocking near-neighbor.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_criteria": gate4["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "as_of": AS_OF,
            "lookback_days": LOOKBACK_DAYS,
            "trade_enabled": False,
            "rule_version": RULE_VERSION,
            "default_refresh_form144_context": False,
        },
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "form144_context_summary": summary,
        "daily_snapshot_contract": contract,
        "entry_context_schema": entry_context_schema(),
        "outcome_join_schema": OUTCOME_JOIN_SCHEMA,
        "forward_reopen_gate": FORWARD_REOPEN_GATE,
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
        },
        "gate2": {
            "passed": gate4["passed"],
            "runtime_fields_required": [
                "entry_date",
                "target_price",
                "Form144 usable_trade_date",
                "Form144 planned_sale_shares",
                "Form144 planned_sale_to_float",
                "Form144 planned_sale_to_adv20",
                "Form144 outcome join keys",
            ],
            "contract": contract,
            "summary_fields_present": sorted(summary.keys()),
            "strategy_fields_changed": False,
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": "No signal generation, survival filter, ranking, sizing, exit, or order rule changed.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": gate4,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "daily_snapshot_exposed": True,
            "trade_enabled": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Data collection is opt-in through refresh_form144_context and "
                "fail-soft. It feeds no ranking, sizing, entry, exit, or order path."
            ),
        },
        "rejection_reason": ";".join(gate4["failed_reasons"]) if gate4["failed_reasons"] else None,
        "next_retry_requires": (
            "Do not use Form144 for any notional haircut, risk scalar, ranking, "
            "or candidate-pool retune until the forward reopen gate is met: "
            ">=25 closed rows with cash/SPY/QQQ replacement value, >=8 high "
            "planned-sale/float rows, and single-ticker share <=40%. If three "
            "materialization/readiness runs add no closable rows, park with the "
            "exact missing cache/forward-row condition."
        ),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune exp-014 Form4 sale-overhang buckets or change a "
                "risk response curve on this surface. Form144 may be reopened "
                "only with cached parseable planned-sale documents plus materially "
                "more closed forward rows, a new data source, or a new gate shape."
            ),
            "new_evidence_required": (
                "Cached Form144 primary documents with machine-parseable "
                "planned_sale_to_float or planned_sale_to_adv20 and closed "
                "forward replacement-value rows versus cash, SPY, and QQQ."
            ),
        },
        "related_files": [
            RUNNER,
            "quant/form144_planned_sale_context.py",
            "quant/daily_non_ohlcv_snapshot.py",
            "quant/backfill_non_ohlcv.py",
            "quant/test_form144_planned_sale_context.py",
            "quant/test_daily_non_ohlcv_snapshot.py",
            repo_rel(summary["output_path"]),
            repo_rel(summary["summary_output"]),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            RUNNER,
            "quant/form144_planned_sale_context.py",
            "quant/daily_non_ohlcv_snapshot.py",
            "quant/backfill_non_ohlcv.py",
            "quant/test_form144_planned_sale_context.py",
            "quant/test_daily_non_ohlcv_snapshot.py",
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
            repo_rel(summary["output_path"]),
            repo_rel(summary["summary_output"]),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_form144_planned_sale_context.py quant\\test_daily_non_ohlcv_snapshot.py -q",
            ".\\.venv\\Scripts\\python.exe -B -c \"from pathlib import Path; files=['quant/form144_planned_sale_context.py','quant/daily_non_ohlcv_snapshot.py','quant/backfill_non_ohlcv.py','quant/test_form144_planned_sale_context.py','quant/test_daily_non_ohlcv_snapshot.py','" + RUNNER + "']; [compile(Path(f).read_text(encoding='utf-8'), f, 'exec') for f in files]\"",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "uses_future_form144_rows": False,
        },
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "lane",
        "owner",
        "hypothesis",
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
        "parameters",
        "delta_metrics",
        "daily_snapshot_contract",
        "entry_context_schema",
        "outcome_join_schema",
        "forward_reopen_gate",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "rejection_reason",
        "next_retry_requires",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    row["form144_context_summary"] = payload["form144_context_summary"]
    row["lean_quality_passed"] = bool(payload["gate4"]["passed"])
    return row


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["form144_context_summary"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Form144 Planned-Sale Context Logger",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Accepted alpha: `{payload['accepted_alpha']}`",
            f"- Rows written: `{summary.get('rows_written')}`",
            f"- Cached primary documents: `{summary.get('rows_with_cached_primary_document')}`",
            f"- Rows with machine-parseable ratio: `{summary.get('rows_with_machine_parseable_ratio')}`",
            f"- Ledger: `{summary.get('output_path')}`",
            f"- Failed reasons: `{gate4['failed_reasons']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Forward Reopen Gate",
            "",
            "- `>=25` closed rows with cash/SPY/QQQ replacement value",
            "- `>=8` high planned-sale/float bucket rows",
            "- single ticker share `<=40%`",
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
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "form144_planned_sale_context.py",
        REPO_ROOT / "quant" / "daily_non_ohlcv_snapshot.py",
        REPO_ROOT / "quant" / "backfill_non_ohlcv.py",
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        REPO_ROOT / payload["form144_context_summary"]["output_path"],
        REPO_ROOT / payload["form144_context_summary"]["summary_output"],
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
        "gate4_passed": payload["gate4"]["passed"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
            "hypothesis",
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
            "parameters",
            "pre_run_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "rejection_reason",
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
        prediction=payload["prediction"],
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
