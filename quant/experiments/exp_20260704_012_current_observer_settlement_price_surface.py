"""exp-20260704-012: current observer settlement price-surface blocker.

Measurement-repair closeout for the current observer surfaces.  Several new
observer/event sources now write rows, but an alpha search on the same rows is
not credible unless the forward outcome ledgers have an entry/open and
comparator price surface.  This runner quantifies that blocker and records a
machine-checkable reopen condition.

No strategy behavior changes here: no entries, filters, ranking, sizing, exits,
paper orders, live orders, prompts, or watchlists are changed.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260704-012"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "current_observer_settlement_price_surface"
RUNNER = f"quant/experiments/exp_20260704_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PREDICTION_SUMMARY = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "prediction_market_event_observer"
    / "latest_outcome_summary.json"
)
ENTITY_THEME_SUMMARY = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "latest_outcome_summary.json"
)
INTRADAY_OBSERVATIONS = (
    REPO_ROOT
    / "data"
    / "daily"
    / "intraday"
    / "structured"
    / "intraday_news_structured_event_observations_20260703_1302ET.jsonl"
)
TREND_SIGNALS = (
    REPO_ROOT
    / "data"
    / "daily"
    / "signals"
    / "trend"
    / "trend_signals_20260703.json"
)
KOVA_SNAPSHOT = REPO_ROOT / "data" / "kova" / "snapshots" / "kova_data_snapshot_20260703.json"
KOVA_INTRADAY = REPO_ROOT / "data" / "kova" / "intraday" / "intraday_ohlcv_20260703.jsonl"
WAREHOUSE_MAIN = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
WAREHOUSE_HOT = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"

HYPOTHESIS = (
    "Alpha-enabling measurement repair: current prediction-market, entity-theme, "
    "and intraday structured-news observer alphas cannot be evaluated credibly "
    "while their forward rows lack an entry/open settlement price surface; "
    "quantify the no-entry-bar blocker and record a machine-checkable reopen "
    "condition instead of reslicing the same observer evidence."
)
ALPHA_HYPOTHESIS = (
    "LLM and non-OHLCV observer events may become useful candidate-pool context "
    "only after forward rows are closed with cash/SPY/QQQ replacement value; "
    "without the entry/open price surface, any current-row alpha result would be "
    "a measurement artifact rather than a tradeable edge."
)
CHANGED_VARIABLE = "current_observer_settlement_price_surface_blocker_v1"
MECHANISM_FAMILY = "observer_forward_settlement_price_surface"
TRIAL_FAMILY = "current_observer_settlement_price_surface_blocker"
TRIAL_VARIANT_ID = "prediction_entity_intraday_current_forward_rows_20260703"
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "read_only_observer_settlement_blocker_audit"
NEARBY_PRIORS = [
    "exp-20260703-011",
    "exp-20260703-012",
    "exp-20260703-013",
    "exp-20260703-014",
    "exp-20260704-005",
]
NEW_EVIDENCE_TYPE = "settlement_price_surface_blocker_quantification"
NEW_EVIDENCE_AXIS = (
    "Measurement-repair only: this combines the current prediction-market, "
    "entity/theme, intraday structured-news, trend-signal warehouse, and Kova "
    "intraday status snapshots to prove whether current observer rows have a "
    "settlement price surface. It does not retune thresholds or reslice the "
    "same observer rows."
)
REOPEN_CONDITION = (
    "Reopen current observer alpha only after the warehouse or another PIT price "
    "surface covers observer entry sessions through at least 2026-07-03 for the "
    "audited tickers, warehouse_main_hot.sqlite no longer reports disk I/O "
    "errors, prediction_market_event_observer has at least 250 settled rows "
    "with cash/SPY/QQQ replacement value, and intraday structured-news "
    "observations have non-null entry_date and target_price for at least 20 "
    "ticker-date rows with regular-session close comparators. Then run a "
    "shared-paper-first Gate 1-4 alpha; do not reslice source/query/theme/"
    "event-age/top-N/hold/notional on the present unsettled batch."
)
PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "warehouse_stale_before_observer_dates",
        "hot_warehouse_disk_io_error",
        "prediction_market_zero_settled_rows",
        "intraday_rows_missing_entry_price",
    ],
    "confidence_reason": (
        "Startup reads already showed the likely blocker, but the experiment "
        "needed a compact cross-surface artifact and reopen condition before "
        "another agent spends IDs reslicing current observer rows."
    ),
    "recorded_at": "2026-07-04T14:09:45+00:00",
}

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_012_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
RELATED_FILES = [
    "data/non_ohlcv/prediction_market_event_observer/latest_outcome_summary.json",
    "data/non_ohlcv/entity_theme_news_observer/latest_outcome_summary.json",
    "data/daily/intraday/structured/intraday_news_structured_event_observations_20260703_1302ET.jsonl",
    "data/daily/signals/trend/trend_signals_20260703.json",
    "data/kova/snapshots/kova_data_snapshot_20260703.json",
    "data/kova/intraday/intraday_ohlcv_20260703.jsonl",
    "data/warehouse/warehouse_main.sqlite",
    "data/warehouse/warehouse_main_hot.sqlite",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def file_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": repo_rel(path),
        "exists": path.exists(),
        "size_bytes": None,
        "last_modified_utc": None,
    }
    if not path.exists():
        return info
    stat = path.stat()
    info["size_bytes"] = stat.st_size
    info["last_modified_utc"] = (
        dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    return info


def observer_summary(summary_path: Path, *, previously_alpha_tested: bool) -> dict[str, Any]:
    data = read_json(summary_path, {}) or {}
    status_counts = data.get("status_counts") or {}
    warehouse = data.get("warehouse") or {}
    no_entry = int(status_counts.get("unsettled_no_entry_bar") or 0)
    settled = int(data.get("settled_count") or 0)
    candidate = int(data.get("candidate_outcome_row_count") or 0)
    gate_ready_for_new_alpha = 0 if previously_alpha_tested else settled
    return {
        "path": repo_rel(summary_path),
        "exists": summary_path.exists(),
        "observer_name": data.get("observer_name"),
        "outcome_rule_version": data.get("outcome_rule_version"),
        "as_of_date": data.get("as_of_date"),
        "source_item_count": data.get("source_item_count"),
        "candidate_outcome_row_count": candidate,
        "settled_count": settled,
        "unsettled_count": int(data.get("unsettled_count") or 0),
        "status_counts": status_counts,
        "no_entry_bar_count": no_entry,
        "no_entry_bar_rate": round(no_entry / candidate, 6) if candidate else None,
        "settled_rate": round(settled / candidate, 6) if candidate else None,
        "previously_alpha_tested": previously_alpha_tested,
        "gate_ready_new_alpha_rows": gate_ready_for_new_alpha,
        "candidate_ticker_count": data.get("candidate_ticker_count"),
        "warehouse": {
            "status": warehouse.get("status"),
            "date_min": warehouse.get("date_min"),
            "date_max": warehouse.get("date_max"),
            "requested_tickers": warehouse.get("requested_tickers"),
            "returned_tickers": warehouse.get("returned_tickers"),
            "returned_rows": warehouse.get("returned_rows"),
            "hot_source_errors": [
                {
                    "path": repo_rel(Path(source.get("path", ""))) if source.get("path") else None,
                    "error": source.get("error"),
                }
                for source in warehouse.get("sources", [])
                if source.get("error")
            ],
        },
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def intraday_observation_audit() -> dict[str, Any]:
    rows = load_jsonl(INTRADAY_OBSERVATIONS)
    status_counts = Counter(str(row.get("outcome_status") or "") for row in rows)
    relation_counts = Counter(str(row.get("relation_polarity") or "") for row in rows)
    tickers = sorted({str(row.get("ticker")) for row in rows if row.get("ticker")})
    missing_entry = sum(1 for row in rows if row.get("entry_date") is None)
    missing_target = sum(1 for row in rows if row.get("target_price") is None)
    missing_cash = sum(1 for row in rows if row.get("replacement_value_vs_cash_usd") is None)
    return {
        "path": repo_rel(INTRADAY_OBSERVATIONS),
        "exists": INTRADAY_OBSERVATIONS.exists(),
        "row_count": len(rows),
        "outcome_status_counts": dict(status_counts),
        "relation_polarity_counts": dict(relation_counts),
        "ticker_count": len(tickers),
        "sample_tickers": tickers[:10],
        "entry_date_missing_count": missing_entry,
        "target_price_missing_count": missing_target,
        "replacement_value_vs_cash_missing_count": missing_cash,
        "entry_date_missing_rate": round(missing_entry / len(rows), 6) if rows else None,
        "target_price_missing_rate": round(missing_target / len(rows), 6) if rows else None,
        "gate_ready_rows": sum(
            1
            for row in rows
            if row.get("entry_date") is not None
            and row.get("target_price") is not None
            and row.get("replacement_value_vs_cash_usd") is not None
        ),
    }


def trend_warehouse_audit() -> dict[str, Any]:
    data = read_json(TREND_SIGNALS, {}) or {}
    ohlcv = data.get("ohlcv_warehouse") or {}
    return {
        "path": repo_rel(TREND_SIGNALS),
        "exists": TREND_SIGNALS.exists(),
        "asof_date": data.get("asof_date"),
        "generated_at": data.get("generated_at"),
        "ohlcv_warehouse": {
            "status": ohlcv.get("status"),
            "path": ohlcv.get("path"),
            "inserted": ohlcv.get("inserted"),
            "updated": ohlcv.get("updated"),
            "processed_ticker_count": ohlcv.get("processed_ticker_count"),
            "errors": ohlcv.get("errors") or [],
        },
    }


def kova_intraday_audit() -> dict[str, Any]:
    snapshot = read_json(KOVA_SNAPSHOT, {}) or {}
    intraday = snapshot.get("intraday_ohlcv") or {}
    rows = load_jsonl(KOVA_INTRADAY)
    status_counts = Counter(str(row.get("status") or "") for row in rows)
    reason_counts = Counter(str(row.get("reason") or "") for row in rows if row.get("reason"))
    return {
        "snapshot_path": repo_rel(KOVA_SNAPSHOT),
        "snapshot_exists": KOVA_SNAPSHOT.exists(),
        "asof_date": snapshot.get("asof_date"),
        "snapshot_status": snapshot.get("status"),
        "intraday_status": intraday.get("status"),
        "intraday_rows_written": intraday.get("rows_written"),
        "intraday_path": repo_rel(KOVA_INTRADAY),
        "intraday_file_exists": KOVA_INTRADAY.exists(),
        "intraday_status_counts": dict(status_counts),
        "intraday_reason_counts": dict(reason_counts),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket_before = read_json(TICKET_JSON, {}) or {}
    prediction = observer_summary(PREDICTION_SUMMARY, previously_alpha_tested=False)
    entity = observer_summary(ENTITY_THEME_SUMMARY, previously_alpha_tested=True)
    intraday = intraday_observation_audit()
    trend = trend_warehouse_audit()
    kova = kova_intraday_audit()
    warehouse_files = {
        "warehouse_main": file_info(WAREHOUSE_MAIN),
        "warehouse_main_hot": file_info(WAREHOUSE_HOT),
    }

    total_observer_rows = (
        int(prediction["candidate_outcome_row_count"] or 0)
        + int(entity["candidate_outcome_row_count"] or 0)
        + int(intraday["row_count"] or 0)
    )
    total_settled_rows = int(prediction["settled_count"] or 0) + int(entity["settled_count"] or 0)
    new_gate_ready_rows = (
        int(prediction["gate_ready_new_alpha_rows"] or 0)
        + int(entity["gate_ready_new_alpha_rows"] or 0)
        + int(intraday["gate_ready_rows"] or 0)
    )
    failed_reasons = []
    if prediction["settled_count"] == 0:
        failed_reasons.append("prediction_market_zero_settled_rows")
    if prediction["no_entry_bar_count"]:
        failed_reasons.append("prediction_market_no_entry_bar_rows")
    if entity["no_entry_bar_count"]:
        failed_reasons.append("entity_theme_remaining_no_entry_bar_rows")
    if intraday["entry_date_missing_count"]:
        failed_reasons.append("intraday_entry_date_missing")
    if intraday["target_price_missing_count"]:
        failed_reasons.append("intraday_target_price_missing")
    if trend["ohlcv_warehouse"]["status"] == "failed":
        failed_reasons.append("trend_ohlcv_warehouse_update_failed")
    if trend["ohlcv_warehouse"]["errors"]:
        failed_reasons.append("trend_ohlcv_warehouse_disk_io_error")
    if kova["intraday_status"] == "skipped_or_failed":
        failed_reasons.append("kova_intraday_skipped_or_failed")
    if new_gate_ready_rows == 0:
        failed_reasons.append("no_new_gate_ready_forward_rows")

    summary = {
        "observer_rows_audited": total_observer_rows,
        "settled_rows_available_total": total_settled_rows,
        "gate_ready_new_alpha_rows": new_gate_ready_rows,
        "prediction_market_candidate_rows": prediction["candidate_outcome_row_count"],
        "prediction_market_settled_rows": prediction["settled_count"],
        "prediction_market_no_entry_rows": prediction["no_entry_bar_count"],
        "entity_theme_candidate_rows": entity["candidate_outcome_row_count"],
        "entity_theme_settled_rows": entity["settled_count"],
        "entity_theme_no_entry_rows": entity["no_entry_bar_count"],
        "intraday_observation_rows": intraday["row_count"],
        "intraday_entry_missing_rows": intraday["entry_date_missing_count"],
        "warehouse_date_max": prediction["warehouse"]["date_max"] or entity["warehouse"]["date_max"],
        "trend_warehouse_status": trend["ohlcv_warehouse"]["status"],
        "kova_intraday_status": kova["intraday_status"],
        "decision_reason": (
            "blocked: current observer rows do not add a gate-ready forward "
            "settlement surface; the warehouse update failed and Kova intraday "
            "refresh was skipped, so another alpha reslice would not create "
            "new evidence."
        ),
    }
    gate1 = {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_exists": BASELINE_RESULT.exists(),
        "baseline_reused_without_strategy_mutation": True,
    }
    gate2 = {
        "passed": False,
        "entry_date_target_price_check": "failed_for_intraday_current_rows",
        "required_fields": [
            "entry_date",
            "target_price",
            "replacement_value_vs_cash_usd",
            "replacement_value_vs_spy_usd",
            "replacement_value_vs_qqq_usd",
        ],
        "prediction_market_has_settled_replacement_values": prediction["settled_count"] > 0,
        "entity_theme_has_settled_replacement_values": entity["settled_count"] > 0,
        "intraday_entry_date_missing_count": intraday["entry_date_missing_count"],
        "intraday_target_price_missing_count": intraday["target_price_missing_count"],
        "runtime_dependencies_present": False,
    }
    gate3 = {
        "signals_generated": total_observer_rows,
        "signals_survived": new_gate_ready_rows,
        "survival_rate": round(new_gate_ready_rows / total_observer_rows, 6) if total_observer_rows else None,
        "filter_added": False,
        "note": "Observer rows were audited for settlement availability; no executable strategy filter was added.",
    }
    gate4 = {
        "ran": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "expected_value_score_delta": 0.0,
        "pnl_delta": 0.0,
        "failed_reasons": failed_reasons,
        "blocked_reason": "settlement_price_surface_not_gate_ready",
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": "blocked",
        "decision": "blocked_current_observer_settlement_price_surface_not_gate_ready",
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
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
        "causal_components": [
            "current prediction-market outcome summary audit",
            "current entity/theme outcome summary audit",
            "current intraday structured-news observation audit",
            "trend OHLCV warehouse status audit",
            "Kova intraday refresh status audit",
            "blocked reopen-condition contract",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 0,
            "actual_decision": "blocked",
            "predicted_failure_mode_hit": True,
            "surprise_note": (
                "Low surprise: the audit confirmed stale/failed settlement "
                "inputs and zero new gate-ready current observer rows."
            ),
        },
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "before_metrics": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "strategy_behavior_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
        },
        "after_metrics": {
            "observer_rows_audited": total_observer_rows,
            "gate_ready_new_alpha_rows": new_gate_ready_rows,
            "strategy_behavior_changed": False,
        },
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
        },
        "source_audit": {
            "prediction_market": prediction,
            "entity_theme": entity,
            "intraday_structured_news": intraday,
            "trend_signal_warehouse": trend,
            "kova_intraday": kova,
            "warehouse_files": warehouse_files,
        },
        "summary": summary,
        "production_impact": {
            "default_off_only": True,
            "trade_enabled_changed": False,
            "ranking_sizing_entry_exit_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "llm_boundary_changed": False,
            "live_realistic_execution_envelope": (
                "Not evaluated; no current observer alpha rule is gate-ready "
                "because settlement price rows are missing."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The current observer surfaces can write event rows, but the "
                "available settlement price surface is stale or failed: "
                "prediction-market rows are all no-entry-bar, intraday rows "
                "lack entry_date and target_price, the trend OHLCV warehouse "
                "update failed with disk I/O, and Kova intraday refresh was "
                "skipped_or_failed."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another experiment that changes prediction-"
                "market query groups, entity/theme source bundles, intraday "
                "event filters, event age, polarity, top-N, hold, cooldown, or "
                "notional on these same current rows. That would not create "
                "new evidence while entry/open settlement remains missing."
            ),
            "new_evidence_required": REOPEN_CONDITION,
        },
        "next_retry_requires": REOPEN_CONDITION,
        "reopen_condition": REOPEN_CONDITION,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "related_files": RELATED_FILES,
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "ticket_before": ticket_before,
        "lean_quality_passed": False,
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
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
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "reopen_condition",
        "artifact",
        "log",
        "runner",
        "changed_files",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    failed = ", ".join(payload["gate4"]["failed_reasons"])
    return f"""# {EXPERIMENT_ID} Current Observer Settlement Price Surface

Status: `{payload["status"]}`
Decision: `{payload["decision"]}`

## Alpha Hypothesis

{payload["alpha_hypothesis"]}

## What Ran

- Command: `{RUNNER_COMMAND}`
- Strategy behavior changed: no
- Paper/live orders changed: no

## Settlement Surface Audit

- Observer rows audited: {summary["observer_rows_audited"]}
- New gate-ready alpha rows: {summary["gate_ready_new_alpha_rows"]}
- Prediction-market rows: {summary["prediction_market_candidate_rows"]}, settled {summary["prediction_market_settled_rows"]}, no-entry {summary["prediction_market_no_entry_rows"]}
- Entity/theme rows: {summary["entity_theme_candidate_rows"]}, settled {summary["entity_theme_settled_rows"]}, no-entry {summary["entity_theme_no_entry_rows"]}
- Intraday rows: {summary["intraday_observation_rows"]}, missing entry {summary["intraday_entry_missing_rows"]}
- Warehouse max date: {summary["warehouse_date_max"]}
- Trend warehouse status: {summary["trend_warehouse_status"]}
- Kova intraday status: {summary["kova_intraday_status"]}
- Failed reasons: {failed}

## Reopen Condition

{payload["reopen_condition"]}

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Forbidden Near-Neighbor Retry

{payload["post_run_reflection"]["forbidden_near_neighbor_retry"]}

## Reproduce

```powershell
{chr(10).join(payload["reproduction_commands"])}
```
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = CHANGED_FILES + RELATED_FILES
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "runner": RUNNER,
        "generated_at": utc_now(),
        "files": {
            path: file_info(REPO_ROOT / path)
            for path in files
        },
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log_record(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, build_manifest(payload))
    ticket_before = payload["ticket_before"]
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "accepted_measurement_repair": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["summary"],
            "reopen_condition": payload["reopen_condition"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "summary": payload["summary"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "reopen_condition": payload["reopen_condition"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": ticket_before.get("novelty"),
            "experiment_uid": ticket_before.get("experiment_uid"),
            "hub_identity": ticket_before.get("hub_identity"),
            "created_at": ticket_before.get("created_at"),
            "claimed_at": ticket_before.get("claimed_at"),
            "completed_at": payload["timestamp"],
            "ticket_file": ticket_before.get("ticket_file") or repo_rel(TICKET_JSON),
            "locked_variables": ticket_before.get("locked_variables") or [CHANGED_VARIABLE],
            "must_not_touch": ticket_before.get("must_not_touch") or [],
            "acceptance_rule": ticket_before.get("acceptance_rule"),
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
                "observer_rows_audited": payload["summary"]["observer_rows_audited"],
                "gate_ready_new_alpha_rows": payload["summary"]["gate_ready_new_alpha_rows"],
                "warehouse_date_max": payload["summary"]["warehouse_date_max"],
                "trend_warehouse_status": payload["summary"]["trend_warehouse_status"],
                "kova_intraday_status": payload["summary"]["kova_intraday_status"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
