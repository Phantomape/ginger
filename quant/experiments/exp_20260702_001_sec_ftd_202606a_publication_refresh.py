"""exp-20260702-001: audit SEC FTD 202606a publication refresh.

Measurement repair only. The SEC fails-to-deliver archive now contains the
2026-06 first-half file with publication date 2026-07-01. This runner records
that data advancement as an alpha-enabling input for the existing default-off
SEC_FTD_FINRA observer without changing strategy behavior or mutating the
paper sleeve state.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
for root in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260702-001"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_ftd_202606a_publication_refresh"
RUNNER = f"quant/experiments/exp_20260702_001_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_ftd_202606a_publication_refresh_audit_v1"
TRIAL_FAMILY = "sec_ftd_archive_publication_refresh"
TRIAL_VARIANT_ID = "202606a_publication_refresh_v1"
MECHANISM_FAMILY = "production_visible_sec_ftd_finra_forward_context"
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "archive_refresh_audit"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SEC_FTD_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "sec_ftd" / "rows.json"
SEC_FTD_SOURCE_FILES = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_ftd" / "source_files.json"
)
SEC_FTD_FINRA_STATE = (
    REPO_ROOT / "data" / "paper_sleeves" / "sec_ftd_finra" / "state.json"
)
SEC_FTD_FINRA_SNAPSHOTS = (
    REPO_ROOT / "data" / "paper_sleeves" / "sec_ftd_finra" / "snapshots.jsonl"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260702_001_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

TARGET_SOURCE_SUFFIX = "cnsfails202606a.zip"
NEXT_SOURCE_SUFFIX = "cnsfails202606b.zip"
TARGET_PUBLICATION_DATE = "2026-07-01"

ALPHA_HYPOTHESIS = (
    "Risk/candidate-pool alpha: SEC FTD pressure plus FINRA short-interest "
    "confirmation may identify default-off crowding/covering candidates, but "
    "it can only be evaluated after publication-date-safe SEC FTD rows are "
    "current and later produce closed forward replacement-value outcomes."
)
HYPOTHESIS = (
    "Repair and audit the newly published SEC fails-to-deliver 2026-06 first-half "
    "archive as an alpha-enabling input for the existing default-off "
    "SEC_FTD_FINRA observer, without changing any trading behavior."
)

CAUSAL_COMPONENTS = [
    "SEC FTD 202606a publication-row audit",
    "source-files status audit",
    "existing SEC_FTD_FINRA state audit",
    "baseline identity",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260604-027",
    "exp-20260612-003",
    "exp-20260625-016",
]
REQUIRED_FTD_FIELDS = [
    "ticker",
    "settlement_date",
    "publication_date",
    "usable_trade_date",
    "ftd_shares",
    "ftd_price",
    "ftd_notional",
    "pit_safe",
    "source_url",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


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
    if isinstance(value, Counter):
        return dict(value)
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
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
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
        "max_drawdown_pct_worst": round(max(drawdowns), 6) if drawdowns else None,
        "windows": windows,
    }


def missing_fields(rows: list[Mapping[str, Any]]) -> Counter:
    missing: Counter[str] = Counter()
    for row in rows:
        for field in REQUIRED_FTD_FIELDS:
            if field not in row or row.get(field) in (None, ""):
                missing[field] += 1
    return missing


def load_ftd_audit() -> dict[str, Any]:
    payload = read_json(SEC_FTD_ROWS, {})
    rows = payload.get("rows") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    target_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("source_url") or "").endswith(TARGET_SOURCE_SUFFIX)
    ]
    prior_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and not str(row.get("source_url") or "").endswith(TARGET_SOURCE_SUFFIX)
    ]
    duplicate_keys = Counter(
        (
            str(row.get("ticker") or ""),
            str(row.get("settlement_date") or ""),
            str(row.get("source_url") or ""),
        )
        for row in target_rows
    )
    duplicate_target_rows = sum(count - 1 for count in duplicate_keys.values() if count > 1)
    publication_dates = Counter(str(row.get("publication_date") or "") for row in target_rows)
    usable_dates = Counter(str(row.get("usable_trade_date") or "") for row in target_rows)
    settlement_dates = [
        str(row.get("settlement_date") or "") for row in target_rows if row.get("settlement_date")
    ]
    tickers = Counter(str(row.get("ticker") or "") for row in target_rows)
    missing = missing_fields(target_rows)
    target_notional = sum(float(row.get("ftd_notional") or 0.0) for row in target_rows)
    target_shares = sum(float(row.get("ftd_shares") or 0.0) for row in target_rows)
    return {
        "rows_path": repo_rel(SEC_FTD_ROWS),
        "rows_file_exists": SEC_FTD_ROWS.exists(),
        "rows_updated_at": payload.get("updated_at") if isinstance(payload, dict) else None,
        "total_rows": len(rows),
        "prior_rows": len(prior_rows),
        "target_source_suffix": TARGET_SOURCE_SUFFIX,
        "target_rows": len(target_rows),
        "target_duplicate_ticker_settlement_source_rows": duplicate_target_rows,
        "target_publication_dates": dict(publication_dates),
        "target_usable_trade_dates": dict(usable_dates),
        "target_settlement_date_min": min(settlement_dates, default=None),
        "target_settlement_date_max": max(settlement_dates, default=None),
        "target_ticker_count": len([ticker for ticker in tickers if ticker]),
        "target_top_tickers": dict(tickers.most_common(12)),
        "target_total_ftd_notional": round(target_notional, 2),
        "target_total_ftd_shares": int(target_shares),
        "target_required_field_audit": {
            "required_fields": REQUIRED_FTD_FIELDS,
            "all_required_fields_present": not missing,
            "missing_counts": dict(missing),
        },
        "latest_publication_date": max(
            (str(row.get("publication_date") or "") for row in rows if isinstance(row, dict)),
            default=None,
        ),
        "latest_settlement_date": max(
            (str(row.get("settlement_date") or "") for row in rows if isinstance(row, dict)),
            default=None,
        ),
        "sample_target_rows": target_rows[:10],
    }


def load_source_file_audit() -> dict[str, Any]:
    payload = read_json(SEC_FTD_SOURCE_FILES, {})
    files = payload.get("files") if isinstance(payload, dict) else []
    if not isinstance(files, list):
        files = []
    target_entries = [
        row for row in files if str(row.get("url") or "").endswith(TARGET_SOURCE_SUFFIX)
    ]
    next_entries = [
        row for row in files if str(row.get("url") or "").endswith(NEXT_SOURCE_SUFFIX)
    ]
    status_counts = Counter(str(row.get("status_code")) for row in files)
    return {
        "source_files_path": repo_rel(SEC_FTD_SOURCE_FILES),
        "source_files_exists": SEC_FTD_SOURCE_FILES.exists(),
        "updated_at": payload.get("updated_at") if isinstance(payload, dict) else None,
        "file_entries": len(files),
        "status_counts": dict(status_counts),
        "target_entries": target_entries,
        "next_half_entries": next_entries,
        "target_has_network_200": any(row.get("status_code") == 200 for row in target_entries),
        "next_half_404_recorded": any(row.get("status_code") == 404 for row in next_entries),
    }


def load_state_audit() -> dict[str, Any]:
    state = read_json(SEC_FTD_FINRA_STATE, {})
    if not isinstance(state, dict):
        state = {}
    snapshots = read_jsonl(SEC_FTD_FINRA_SNAPSHOTS)
    latest_snapshot = snapshots[-1] if snapshots else {}
    if not isinstance(latest_snapshot, dict):
        latest_snapshot = {}
    return {
        "state_path": repo_rel(SEC_FTD_FINRA_STATE),
        "state_exists": SEC_FTD_FINRA_STATE.exists(),
        "state_updated_at": state.get("updated_at"),
        "pending_entries": len(state.get("pending_entries") or []),
        "open_positions": len(state.get("open_positions") or []),
        "closed_positions": len(state.get("closed_positions") or []),
        "skipped_entries": len(state.get("skipped_entries") or []),
        "snapshots_path": repo_rel(SEC_FTD_FINRA_SNAPSHOTS),
        "snapshot_count": len(snapshots),
        "latest_snapshot_asof": latest_snapshot.get("asof_date"),
        "latest_snapshot_candidate_count": latest_snapshot.get("candidate_count"),
        "latest_snapshot_pending_count": latest_snapshot.get("pending_count"),
        "latest_snapshot_open_position_count": latest_snapshot.get("open_position_count"),
        "latest_snapshot_closed_position_count": latest_snapshot.get("closed_position_count"),
        "latest_snapshot_data_source": latest_snapshot.get("data_source") or {},
        "latest_snapshot_forward_paper_gate": latest_snapshot.get("forward_paper_gate") or {},
    }


def build_reopen_condition(state_audit: dict[str, Any]) -> dict[str, Any]:
    closed = int(state_audit.get("closed_positions") or 0)
    return {
        "surface": "SEC FTD + FINRA default-off observer",
        "status": "published_ftd_rows_current_not_alpha_ready",
        "blocking_reason": "no_closed_sec_ftd_finra_forward_replacement_rows",
        "current_counts": {
            "sec_ftd_202606a_rows": None,
            "paper_pending_entries": state_audit.get("pending_entries"),
            "paper_open_positions": state_audit.get("open_positions"),
            "paper_closed_positions": closed,
            "latest_snapshot_candidate_count": state_audit.get("latest_snapshot_candidate_count"),
        },
        "required_to_reopen": {
            "closed_sec_ftd_finra_true_trigger_rows_min": 20,
            "required_replacement_values": ["cash", "SPY", "QQQ"],
            "single_ticker_positive_share_max": 0.40,
            "top5_positive_share_max": 0.70,
            "additional_allowed_axis": [
                "PIT borrow fee",
                "loan availability",
                "materially more closed forward rows",
            ],
        },
        "reopen_rule": (
            "Do not reserve SEC FTD/FINRA threshold, age, notional, share, "
            "top-N, hold, notional, allocator, or response-curve experiments "
            "from this archive refresh alone. Reopen only when the unchanged "
            "observer has closed replacement-value rows or when a true PIT "
            "borrow/loan economics source arrives."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    before = baseline_metrics()
    ftd_audit = load_ftd_audit()
    source_audit = load_source_file_audit()
    state_audit = load_state_audit()
    reopen_condition = build_reopen_condition(state_audit)
    reopen_condition["current_counts"]["sec_ftd_202606a_rows"] = ftd_audit["target_rows"]

    failed_reasons: list[str] = []
    if not before.get("loaded"):
        failed_reasons.append("baseline_not_loaded")
    if not ftd_audit["rows_file_exists"]:
        failed_reasons.append("sec_ftd_rows_file_missing")
    if not source_audit["source_files_exists"]:
        failed_reasons.append("sec_ftd_source_files_missing")
    if not source_audit["target_has_network_200"]:
        failed_reasons.append("cnsfails202606a_not_recorded_as_network_200")
    if ftd_audit["target_rows"] <= 0:
        failed_reasons.append("cnsfails202606a_rows_missing")
    if ftd_audit["target_publication_dates"] != {TARGET_PUBLICATION_DATE: ftd_audit["target_rows"]}:
        failed_reasons.append("target_publication_date_not_uniform_20260701")
    if not ftd_audit["target_required_field_audit"]["all_required_fields_present"]:
        failed_reasons.append("target_rows_missing_required_fields")
    if ftd_audit["target_duplicate_ticker_settlement_source_rows"]:
        failed_reasons.append("duplicate_target_ticker_settlement_source_rows")
    if state_audit["pending_entries"] or state_audit["open_positions"]:
        failed_reasons.append("sec_ftd_finra_state_has_active_paper_positions")

    accepted = not failed_reasons
    decision = (
        "accepted_measurement_repair_sec_ftd_202606a_publication_refresh"
        if accepted
        else "blocked_sec_ftd_202606a_publication_refresh"
    )
    status = "accepted_measurement_repair" if accepted else "blocked"
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else {}
    if not isinstance(prediction, dict):
        prediction = {}
    raw_probability = prediction.get("success_probability")
    predicted: float | None = None
    if raw_probability not in (None, ""):
        try:
            predicted = float(raw_probability)
        except (TypeError, ValueError):
            predicted = None
    delta_metrics = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
        "sec_ftd_rows_total": ftd_audit["total_rows"],
        "sec_ftd_202606a_rows": ftd_audit["target_rows"],
        "sec_ftd_202606a_ticker_count": ftd_audit["target_ticker_count"],
        "sec_ftd_202606a_total_notional": ftd_audit["target_total_ftd_notional"],
        "sec_ftd_finra_pending_entries": state_audit["pending_entries"],
        "sec_ftd_finra_open_positions": state_audit["open_positions"],
        "sec_ftd_finra_closed_positions": state_audit["closed_positions"],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
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
        "new_evidence_type": "new_publication_date_sec_ftd_rows",
        "new_evidence_axis": (
            "New publication-date-safe SEC FTD archive batch cnsfails202606a.zip "
            "with usable_trade_date 2026-07-01. This run audits data currency "
            "only and does not reslice FTD/FINRA thresholds."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": predicted,
            "actual_success": accepted,
            "brier_score": (
                round((predicted - (1.0 if accepted else 0.0)) ** 2, 6)
                if predicted is not None
                else None
            ),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "surprise_note": (
                "The SEC FTD archive had advanced to the new first-half June file, "
                "but the default-off FTD+FINRA paper observer still has no active "
                "or closed paper rows from this batch."
            ),
        },
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": delta_metrics,
        "source_audit": {
            "sec_ftd_rows": ftd_audit,
            "sec_ftd_source_files": source_audit,
            "sec_ftd_finra_state": state_audit,
        },
        "gate1": {
            "passed": bool(before.get("loaded")),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": accepted,
            "runtime_fields_checked": REQUIRED_FTD_FIELDS
            + [
                "source_files.target_has_network_200",
                "paper_state.pending_entries",
                "paper_state.open_positions",
            ],
            "sec_ftd_target_rows": ftd_audit["target_rows"],
            "sec_ftd_source_files": {
                "target_has_network_200": source_audit["target_has_network_200"],
                "next_half_404_recorded": source_audit["next_half_404_recorded"],
                "target_entries": source_audit["target_entries"],
                "next_half_entries": source_audit["next_half_entries"],
            },
            "target_required_field_audit": ftd_audit["target_required_field_audit"],
            "target_price_scope": (
                "Not applicable. This is an archive/data-source audit and no entry, "
                "exit, order, or paper position is scheduled."
            ),
            "entry_date_scope": (
                "Not applicable. The source rows have publication_date and "
                "usable_trade_date; no trade entry_date is created here."
            ),
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": (
                "No signal, filter, ranking, sizing, exit, risk budget, paper "
                "entry, or order rule changed."
            ),
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
            "source_rows_audited": ftd_audit["target_rows"],
        },
        "gate4": {
            "passed": accepted,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "decision": decision,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "ranking_changed": False,
                "sizing_changed": False,
                "entry_changed": False,
                "exit_changed": False,
                "paper_order_changed": False,
                "live_order_changed": False,
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
            "daily_snapshot_exposed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "risk_budget_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Data audit over an existing archive and existing default-off "
                "paper observer. No helper, adapter, threshold, ledger state, "
                "or order path was changed."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "exp-20260604-027 accepted the default-off SEC FTD + FINRA shared "
                "adapter; exp-20260612-003 fixed stale archives; exp-20260625-016 "
                "rejected FTD forward context attribution. This run is legal only "
                "because SEC published a new 202606a archive batch; it is not a "
                "threshold or response retry."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if canonical strategy metrics "
                "remain unchanged, cnsfails202606a.zip is recorded as network 200, "
                "target rows exist with publication_date 2026-07-01 and required "
                "fields, no duplicate ticker/settlement/source rows exist, and the "
                "existing FTD+FINRA state has no active paper orders caused by this audit."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The prior staleness repair kept polling SEC FTD files, and the "
                "new 2026-06 first-half publication is now present locally. The "
                "archive is current, but the accepted FTD+FINRA observer still has "
                "no active or closed paper rows, so this is data readiness, not "
                "alpha evidence."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this archive refresh to retune FTD share/notional/ADV "
                "thresholds, publication-age windows, FINRA confirmation thresholds, "
                "candidate top-N, hold days, notional, allocator rank, or response "
                "curves."
            ),
            "new_evidence_required": (
                "A valid FTD+FINRA alpha retry requires materially more closed true "
                "trigger rows with cash/SPY/QQQ replacement values, PIT borrow fee "
                "or loan-availability fields, or a distinct non-saturated data source."
            ),
        },
        "next_retry_requires": [
            "closed SEC_FTD_FINRA true-trigger rows with cash/SPY/QQQ replacement values",
            "PIT borrow fee or loan-availability data",
            "a distinct non-saturated data source or gate shape",
        ],
        "anti_js": {
            "used_javascript": False,
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "response_curve_retune": False,
            "new_download_attempts": False,
        },
        "related_files": [
            RUNNER,
            repo_rel(SEC_FTD_ROWS),
            repo_rel(SEC_FTD_SOURCE_FILES),
            repo_rel(SEC_FTD_FINRA_STATE),
            repo_rel(SEC_FTD_FINRA_SNAPSHOTS),
            repo_rel(BASELINE_RESULT),
            "quant/sec_ftd_finra_paper_sleeve.py",
            "experiments/logs/exp-20260604-027.json",
            "experiments/logs/exp-20260612-003.json",
            "experiments/logs/exp-20260625-016.json",
        ],
        "changed_files": [
            RUNNER,
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
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_ftd_finra_archive_refresh.py quant\\test_sec_ftd_finra_paper_sleeve.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": accepted,
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
        "new_evidence_axis",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "source_audit",
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
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys if key in payload}


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    source = payload["source_audit"]["sec_ftd_source_files"]
    gate = payload["reopen_condition"]["required_to_reopen"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC FTD 202606a publication refresh",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            "- Accepted alpha: `false`",
            "- Strategy behavior changed: `false`",
            f"- 202606a rows: `{delta['sec_ftd_202606a_rows']}`",
            f"- 202606a tickers: `{delta['sec_ftd_202606a_ticker_count']}`",
            f"- 202606a notional: `${delta['sec_ftd_202606a_total_notional']:,.2f}`",
            f"- 202606a network 200: `{str(source['target_has_network_200']).lower()}`",
            f"- 202606b 404 recorded: `{str(source['next_half_404_recorded']).lower()}`",
            f"- Paper pending/open/closed: `{delta['sec_ftd_finra_pending_entries']}` / "
            f"`{delta['sec_ftd_finra_open_positions']}` / "
            f"`{delta['sec_ftd_finra_closed_positions']}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reopen Condition",
            "",
            (
                "Reopen FTD+FINRA alpha only after at least "
                f"`{gate['closed_sec_ftd_finra_true_trigger_rows_min']}` true-trigger "
                "closed rows with cash/SPY/QQQ replacement value, or after PIT borrow "
                "fee / loan-availability data arrives."
            ),
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
        SEC_FTD_ROWS,
        SEC_FTD_SOURCE_FILES,
        SEC_FTD_FINRA_STATE,
        SEC_FTD_FINRA_SNAPSHOTS,
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
            "new_evidence_axis",
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
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
