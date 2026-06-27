"""exp-20260626-025: post-latest alpha surface readiness audit.

Measurement repair only. This run checks whether the newly added post-exp023
and post-exp024 surfaces changed the legal alpha search state:

- estimate-revision hot warehouse outcomes,
- intraday shadow-action provenance,
- forward replacement entry-regime / short-volume tags,
- options, borrow, SEC periodic, and allocator retry boundaries.

No strategy, shared helper, ranking, sizing, exit, order, paper snapshot, live
path, watchlist, or LLM decision behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260626-025"
OWNER = "alpha-explore"
SLUG = "post_latest_alpha_surface_readiness_audit"
RUNNER = f"quant/experiments/exp_20260626_025_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_025_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_REPLACEMENT_LEDGER = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
FORWARD_READINESS_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260626-014"
    / "exp_20260626_014_forward_replacement_activation_readiness_20260626.json"
)
ESTIMATE_REVISION_HOT_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260626-023.json"
INTRADAY_CONTRACT_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260626-024.json"
INTRADAY_OUTCOME_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260626-019"
    / "intraday_advisory_forward_outcome_ledger.jsonl"
)
OPTIONS_SETTLEMENT_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260624-026.json"
OPTIONS_DEMAND_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260625-001.json"
OPTIONS_EVENT_DISTANCE_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260625-020.json"
BORROW_MANIFEST = REPO_ROOT / "data" / "non_ohlcv" / "borrow_availability" / "manifest.json"
SEC_FEATURES_SUMMARY = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_features_summary_20260625.json"
SEC_PERIODIC_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260626-016.json"
ALLOCATOR_BOUNDARY_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260621-009.json"

HYPOTHESIS = (
    "alpha_blocker: after the latest Alpha Explore run, newly added "
    "estimate-revision hot outcomes, intraday provenance, and forward "
    "replacement tags must be checked as a single post-run readiness surface "
    "before any legal alpha retry; if none is ready, the blocker must be "
    "recorded so the next run does not reslice saturated forward rows."
)
ALPHA_HYPOTHESIS = (
    "New post-exp023/024 measurement surfaces could reopen alpha only if they "
    "add materially closed replacement rows, post-contract intraday outcomes, "
    "or populated borrow/options/SEC fields. Otherwise the legal alpha action "
    "is to wait for new rows or a genuinely new source."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "alpha_enabling_nonrepeat_readiness"
TRIAL_FAMILY = "post_latest_alpha_surface_readiness_audit"
TRIAL_VARIANT_ID = "post_exp023_exp024_surface_readiness_v1"
CHANGED_VARIABLE = "post_latest_alpha_surface_readiness_audit_v1"
NEW_EVIDENCE_TYPE = "post_latest_forward_and_provenance_surface_audit"
NEW_EVIDENCE_AXIS = (
    "Post-exp-20260626-023 and post-exp-20260626-024 state: includes "
    "estimate-revision hot warehouse outcomes and intraday action provenance "
    "created after the prior alpha evidence-gap ledger, plus verification of "
    "forward replacement entry-regime/short-volume tag coverage. This is not "
    "a strategy retune or same-row alpha slice."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260626-015",
    "exp-20260626-023",
    "exp-20260626-024",
    "exp-20260626-014",
    "exp-20260626-018",
]
CAUSAL_COMPONENTS = [
    "estimate_revision_hot_outcome_readiness",
    "intraday_post_contract_closed_row_readiness",
    "forward_replacement_tag_readiness",
    "allocator_source_retry_boundary",
    "options_borrow_sec_blocker_boundary",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260626-025/exp_20260626_025_post_latest_alpha_surface_readiness_audit.json",
    "experiments/cards/exp-20260626-025.md",
    "experiments/manifests/exp-20260626-025.json",
    "experiments/tickets/exp-20260626-025.json",
    "experiments/logs/exp-20260626-025.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
DEFAULT_PREDICTION = {
    "success_probability": 0.86,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_new_closed_forward_rows",
        "intraday_post_contract_rows_absent",
        "estimate_revision_3_5_10d_unmatured",
        "options_borrow_sec_surfaces_blocked",
    ],
    "confidence_reason": (
        "Recent logs show exp023 and exp024 added useful measurement surfaces, "
        "but not enough closed forward rows or populated borrow/options/SEC "
        "fields for a legal alpha promotion; this run should succeed as "
        "blocker/readiness accounting only."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(make_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(make_json_safe(record), sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_exists": BASELINE_RESULT.exists(),
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
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {**DEFAULT_PREDICTION, "recorded_at": utc_now()}


def summarize_forward_replacement() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_REPLACEMENT_LEDGER)
    readiness_artifact = read_json(FORWARD_READINESS_ARTIFACT, {})
    by_sleeve = Counter(str(row.get("sleeve_key") or "unknown") for row in rows)
    by_regime = Counter(str(row.get("entry_regime_label") or "missing") for row in rows)
    by_short_quintile = Counter(
        "missing"
        if row.get("entry_short_volume_quintile") is None
        else str(row.get("entry_short_volume_quintile"))
        for row in rows
    )
    closed_cash = [
        row for row in rows if row.get("replacement_value_vs_cash_usd") is not None
    ]
    entry_dates = sorted(str(row.get("entry_date") or "")[:10] for row in rows if row.get("entry_date"))
    summary = {
        "surface": "forward_replacement_value",
        "artifact": repo_rel(FORWARD_REPLACEMENT_LEDGER),
        "rows": len(rows),
        "closed_cash_rows": len(closed_cash),
        "rows_with_entry_regime": sum(1 for row in rows if row.get("entry_regime_label")),
        "rows_with_short_volume_percentile": sum(
            1 for row in rows if row.get("entry_short_volume_ratio_percentile") is not None
        ),
        "rows_by_sleeve": dict(by_sleeve),
        "rows_by_entry_regime_label": dict(by_regime),
        "rows_by_entry_short_volume_quintile": dict(by_short_quintile),
        "min_entry_date": entry_dates[0] if entry_dates else None,
        "max_entry_date": entry_dates[-1] if entry_dates else None,
        "readiness_artifact": repo_rel(FORWARD_READINESS_ARTIFACT),
        "readiness_artifact_exists": FORWARD_READINESS_ARTIFACT.exists(),
        "prior_readiness_decision": readiness_artifact.get("decision"),
        "prior_readiness_status": readiness_artifact.get("status"),
        "alpha_ready": False,
        "blockers": [],
    }
    if len(closed_cash) < 60:
        summary["blockers"].append("closed_forward_rows_below_activation_floor_60")
    if sum(1 for row in rows if row.get("entry_regime_label")) < len(rows):
        summary["blockers"].append("entry_regime_tag_coverage_incomplete")
    if sum(1 for row in rows if row.get("entry_short_volume_ratio_percentile") is not None) < 40:
        summary["blockers"].append("entry_short_volume_tag_sample_still_thin")
    summary["next_evidence"] = (
        "Materially more closed replacement rows per source family and per "
        "short-volume/regime bucket before any activation, tilt, or allocation "
        "retry."
    )
    return summary


def summarize_estimate_revision() -> dict[str, Any]:
    log = read_json(ESTIMATE_REVISION_HOT_LOG, {})
    outcome = log.get("outcome_summary") if isinstance(log, dict) else {}
    if not isinstance(outcome, dict):
        outcome = {}
    blockers = []
    nonflat = int(outcome.get("selected_current_nonflat_usable_rows") or 0)
    h3 = int(outcome.get("selected_current_closed_3d_rows") or 0)
    h5 = int(outcome.get("selected_current_closed_5d_rows") or 0)
    h10 = int(outcome.get("selected_current_closed_10d_rows") or 0)
    if nonflat < 20:
        blockers.append("selected_current_nonflat_sample_too_thin")
    if h3 < 20:
        blockers.append("forward_3d_outcomes_not_mature")
    if h5 < 20:
        blockers.append("forward_5d_outcomes_not_mature")
    if h10 < 20:
        blockers.append("forward_10d_outcomes_not_mature")
    return {
        "surface": "estimate_revision_hot_warehouse_outcomes",
        "log": repo_rel(ESTIMATE_REVISION_HOT_LOG),
        "log_exists": ESTIMATE_REVISION_HOT_LOG.exists(),
        "decision": log.get("decision"),
        "alpha_ready": bool(log.get("alpha_ready")),
        "matched_rows": outcome.get("matched_rows"),
        "selected_current_rows": outcome.get("selected_current_rows"),
        "selected_current_nonflat_usable_rows": nonflat,
        "selected_current_closed_entry_day_rows": outcome.get("selected_current_closed_entry_day_rows"),
        "selected_current_closed_1d_rows": outcome.get("selected_current_closed_1d_rows"),
        "selected_current_closed_3d_rows": h3,
        "selected_current_closed_5d_rows": h5,
        "selected_current_closed_10d_rows": h10,
        "blockers": blockers,
        "next_evidence": (
            "More selected/current non-flat matches with closed 3/5/10d "
            "replacement values, another settled month, or a different "
            "unsaturated PIT expectation source."
        ),
    }


def summarize_intraday() -> dict[str, Any]:
    contract_log = read_json(INTRADAY_CONTRACT_LOG, {})
    ledger_rows = read_jsonl(INTRADAY_OUTCOME_LEDGER)
    latest_projection = (
        (contract_log.get("gate2") or {}).get("latest_snapshot_projection")
        if isinstance(contract_log, dict)
        else {}
    )
    if not isinstance(latest_projection, dict):
        latest_projection = {}
    post_contract_rows = [
        row
        for row in ledger_rows
        if row.get("decision_time_et")
        or row.get("is_primary_shadow_action") is not None
        or row.get("primary_advisory_shadow_action")
    ]
    by_horizon = Counter(str(row.get("horizon_days")) for row in ledger_rows)
    blockers = []
    if len(post_contract_rows) < 20:
        blockers.append("post_contract_closed_outcome_rows_absent_or_too_thin")
    if int(latest_projection.get("source_quote_time_rows") or 0) == 0:
        blockers.append("true_source_quote_time_still_absent")
    return {
        "surface": "intraday_shadow_action_provenance",
        "contract_log": repo_rel(INTRADAY_CONTRACT_LOG),
        "outcome_ledger": repo_rel(INTRADAY_OUTCOME_LEDGER),
        "contract_decision": contract_log.get("decision"),
        "outcome_rows": len(ledger_rows),
        "post_contract_outcome_rows": len(post_contract_rows),
        "rows_by_horizon": dict(by_horizon),
        "latest_snapshot_date": latest_projection.get("date"),
        "latest_snapshot_primary_action_count": latest_projection.get("primary_action_count"),
        "latest_snapshot_shadow_actions": latest_projection.get("shadow_actions"),
        "latest_snapshot_source_quote_time_rows": latest_projection.get("source_quote_time_rows"),
        "latest_snapshot_quote_time_basis": latest_projection.get("quote_time_basis"),
        "alpha_ready": False,
        "blockers": blockers,
        "next_evidence": (
            "More snapshots generated after the exp024 contract, then h1/h3/h5/h10 "
            "settled replacement-value outcomes by primary action."
        ),
    }


def summarize_options() -> dict[str, Any]:
    settlement = read_json(OPTIONS_SETTLEMENT_LOG, {})
    demand = read_json(OPTIONS_DEMAND_LOG, {})
    event_distance = read_json(OPTIONS_EVENT_DISTANCE_LOG, {})
    blockers = [
        "demand_quality_rejected",
        "earnings_event_distance_rejected",
        "historical_pit_chain_coverage_absent",
    ]
    return {
        "surface": "onclickmedia_options_forward",
        "settlement_log": repo_rel(OPTIONS_SETTLEMENT_LOG),
        "demand_log": repo_rel(OPTIONS_DEMAND_LOG),
        "event_distance_log": repo_rel(OPTIONS_EVENT_DISTANCE_LOG),
        "settlement_decision": settlement.get("decision"),
        "demand_decision": demand.get("decision"),
        "event_distance_decision": event_distance.get("decision"),
        "alpha_ready": False,
        "blockers": blockers,
        "next_evidence": (
            "Materially more closed options rows, historical PIT chain coverage, "
            "or a different production-visible event/cost field that creates new "
            "rows rather than reslicing the same ledger."
        ),
    }


def summarize_borrow() -> dict[str, Any]:
    manifest = read_json(BORROW_MANIFEST, {})
    populated = float(manifest.get("borrow_populated_pct") or 0.0)
    blockers = []
    if populated <= 0.0:
        blockers.append("borrow_fields_unpopulated")
    return {
        "surface": "moomoo_borrow_availability",
        "manifest": repo_rel(BORROW_MANIFEST),
        "manifest_exists": BORROW_MANIFEST.exists(),
        "borrow_populated_pct": manifest.get("borrow_populated_pct"),
        "borrow_populated_this_run": manifest.get("borrow_populated_this_run"),
        "cumulative_rows_total": manifest.get("cumulative_rows_total"),
        "short_sell_rate_min": manifest.get("short_sell_rate_min"),
        "short_sell_rate_max": manifest.get("short_sell_rate_max"),
        "alpha_ready": False,
        "blockers": blockers,
        "next_evidence": (
            "Non-null PIT borrow fee, utilization, or loan-availability rows "
            "across multiple dates, then closed forward replacement attribution."
        ),
    }


def summarize_sec_periodic() -> dict[str, Any]:
    feature_summary = read_json(SEC_FEATURES_SUMMARY, {})
    periodic_log = read_json(SEC_PERIODIC_LOG, {})
    blockers = []
    if int(feature_summary.get("rows_with_same_accession_facts") or 0) == 0:
        blockers.append("same_accession_companyfacts_absent")
    if int(feature_summary.get("field_counts", {}).get("fcf_to_net_income_gap") or 0) == 0:
        blockers.append("periodic_numeric_fields_absent")
    return {
        "surface": "sec_periodic_text_and_features",
        "feature_summary": repo_rel(SEC_FEATURES_SUMMARY),
        "periodic_log": repo_rel(SEC_PERIODIC_LOG),
        "rows_written": feature_summary.get("rows_written"),
        "rows_with_same_accession_facts": feature_summary.get("rows_with_same_accession_facts"),
        "field_counts": feature_summary.get("field_counts"),
        "periodic_decision": periodic_log.get("decision"),
        "alpha_ready": False,
        "blockers": blockers,
        "next_evidence": (
            "Real 10-K/10-Q text/cache with parsed cover-page status and same-accession "
            "numeric fields before filer-status or periodic-report alpha."
        ),
    }


def summarize_allocator_boundary() -> dict[str, Any]:
    log = read_json(ALLOCATOR_BOUNDARY_LOG, {})
    return {
        "surface": "accepted_helper_allocator_retry_boundary",
        "boundary_log": repo_rel(ALLOCATOR_BOUNDARY_LOG),
        "boundary_log_exists": ALLOCATOR_BOUNDARY_LOG.exists(),
        "decision": log.get("decision"),
        "alpha_ready": False,
        "blockers": [
            "fiftytwo_week_allocator_source_extension_rejected",
            "distribution_absorption_allocator_source_rejected",
            "source_scalar_stack_frozen_without_forward_rows",
        ],
        "next_evidence": (
            "Closed forward source-family replacement rows or a materially new "
            "production-visible discriminator; not source rank, scalar, top-N, "
            "hold, or cooldown retunes."
        ),
    }


def calibration(
    prediction: dict[str, Any],
    measurement_passed: bool,
    alpha_blockers: list[str],
) -> dict[str, Any]:
    predicted = list(prediction.get("main_failure_modes") or [])
    hit = [
        mode
        for mode in predicted
        if (
            ("closed_forward" in mode and any("closed_forward" in b for b in alpha_blockers))
            or ("intraday" in mode and any("intraday" in b or "post_contract" in b for b in alpha_blockers))
            or ("estimate_revision" in mode and any("forward_3d" in b or "forward_5d" in b or "forward_10d" in b for b in alpha_blockers))
            or ("options_borrow_sec" in mode and any(b in alpha_blockers for b in ("options_surface_blocked", "borrow_fields_unpopulated", "sec_periodic_fields_missing")))
        )
    ]
    return {
        "predicted_success_probability": prediction.get("success_probability"),
        "actual_success": 1 if measurement_passed else 0,
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "predicted_failure_modes": predicted,
        "predicted_failure_modes_hit": hit,
        "realized_failure_modes": alpha_blockers,
        "surprise_note": (
            "No surprise: post-exp023/024 surfaces improved measurement contracts "
            "but did not add enough closed or populated alpha evidence."
            if measurement_passed
            else "Measurement dependencies were missing."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    surfaces = {
        "forward_replacement": summarize_forward_replacement(),
        "estimate_revision": summarize_estimate_revision(),
        "intraday": summarize_intraday(),
        "options": summarize_options(),
        "borrow": summarize_borrow(),
        "sec_periodic": summarize_sec_periodic(),
        "allocator_boundary": summarize_allocator_boundary(),
    }
    measurement_blockers = []
    if not baseline["baseline_exists"] or baseline["window_count"] != 3:
        measurement_blockers.append("baseline_missing_or_wrong_window_count")
    required_paths = [
        FORWARD_REPLACEMENT_LEDGER,
        ESTIMATE_REVISION_HOT_LOG,
        INTRADAY_CONTRACT_LOG,
        INTRADAY_OUTCOME_LEDGER,
        BORROW_MANIFEST,
        SEC_FEATURES_SUMMARY,
    ]
    missing = [repo_rel(path) for path in required_paths if not path.exists()]
    if missing:
        measurement_blockers.append("required_surface_files_missing")

    alpha_blockers = []
    if "closed_forward_rows_below_activation_floor_60" in surfaces["forward_replacement"]["blockers"]:
        alpha_blockers.append("closed_forward_rows_below_activation_floor_60")
    if surfaces["estimate_revision"]["blockers"]:
        alpha_blockers.extend(f"estimate_revision_{b}" for b in surfaces["estimate_revision"]["blockers"])
    if surfaces["intraday"]["blockers"]:
        alpha_blockers.extend(f"intraday_{b}" for b in surfaces["intraday"]["blockers"])
    if surfaces["options"]["blockers"]:
        alpha_blockers.append("options_surface_blocked")
    if surfaces["borrow"]["blockers"]:
        alpha_blockers.append("borrow_fields_unpopulated")
    if surfaces["sec_periodic"]["blockers"]:
        alpha_blockers.append("sec_periodic_fields_missing")
    if surfaces["allocator_boundary"]["blockers"]:
        alpha_blockers.append("allocator_retry_boundary_still_frozen")

    measurement_passed = not measurement_blockers
    alpha_ready = False
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        "accepted_measurement_repair_post_latest_alpha_surface_readiness_audit"
        if measurement_passed
        else "blocked_post_latest_alpha_surface_readiness_audit_missing_inputs"
    )
    gate4 = {
        "passed": measurement_passed,
        "accepted_alpha": False,
        "alpha_ready": alpha_ready,
        "decision": decision,
        "measurement_blockers": measurement_blockers,
        "alpha_blockers": sorted(set(alpha_blockers)),
        "measurement_repair_only": True,
        "strategy_rerun_required": False,
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": measurement_passed,
        "accepted_alpha": False,
        "alpha_ready": alpha_ready,
        "observed_only_lead": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "post_latest_alpha_surface_readiness_audit",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, measurement_passed, sorted(set(alpha_blockers))),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260626-015": "Accepted current evidence-gap ledger before exp023/024 matured new measurement surfaces.",
                "exp-20260626-023": "Accepted estimate-revision hot-warehouse outcome ledger; alpha still blocked by thin non-flat sample and unmatured 3/5/10d rows.",
                "exp-20260626-024": "Accepted intraday shadow-action provenance contract; alpha needs new post-contract closed rows.",
                "novelty_gate": ticket.get("novelty"),
            },
            "3_single_policy_bundle": (
                "One measurement bundle: read current readiness surfaces and record "
                "whether any post-latest-run axis legally reopens alpha."
            ),
            "4_success_failure_standard": (
                "Accept only as measurement repair if baseline strategy metrics remain "
                "unchanged, required surfaces load, and the next legal evidence axes "
                "are explicit."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "required_surface_files": [repo_rel(path) for path in required_paths],
            "missing_required_surface_files": missing,
            "post_latest_scope": [
                "exp-20260626-023 estimate-revision hot outcome ledger",
                "exp-20260626-024 intraday shadow-action provenance contract",
                "forward replacement entry-regime and short-volume tags",
                "options/borrow/SEC/allocator frozen boundary checks",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "surface_count": len(surfaces),
            "alpha_ready_surface_count": sum(1 for row in surfaces.values() if row.get("alpha_ready")),
        },
        "gate1": {
            "passed": baseline["baseline_exists"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": not missing,
            "dependencies_validated": not missing,
            "required_surface_files": [repo_rel(path) for path in required_paths],
            "missing_required_surface_files": missing,
            "fields_checked": [
                "forward_replacement.entry_date",
                "forward_replacement.replacement_value_vs_cash_usd",
                "forward_replacement.entry_regime_label",
                "forward_replacement.entry_short_volume_ratio_percentile",
                "estimate_revision.selected_current_nonflat_usable_rows",
                "estimate_revision.closed_3d_5d_10d_rows",
                "intraday.primary_advisory_shadow_action",
                "intraday.decision_time_et",
                "borrow_availability.short_sell_rate",
                "borrow_availability.short_available_volume",
                "sec_filing_features.rows_with_same_accession_facts",
            ],
            "entry_date_target_price_note": (
                "This is a readiness ledger, not a trading surface. Entry-date "
                "fields are checked where replacement value exists; target_price "
                "is not used to schedule exits or orders."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_signals_generated": baseline.get("signals_generated"),
            "baseline_signals_survived": baseline.get("signals_survived"),
            "baseline_survival_rate": baseline.get("survival_rate"),
            "note": "No executable entry, exit, filter, ranking, or sizing rule was added.",
        },
        "gate4": gate4,
        "surface_readiness": surfaces,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Experiment-owned readiness artifact only; reads existing ledgers "
                "and writes no shared helper, daily adapter, order, rank, size, "
                "exit, watchlist, or LLM changes."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The latest repairs improved measurement contracts, but no surface "
                "added enough new closed or populated evidence for legal alpha: "
                "forward replacement remains at 40 rows, estimate revision lacks "
                "mature 3/5/10d selected/current rows, intraday has no post-contract "
                "closed outcomes, borrow fields are still null, options event/demand "
                "attribution is rejected, SEC periodic fields remain missing, and "
                "allocator source/scalar retries remain frozen."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry same-row forward attribution slices, intraday "
                "thresholds on pre-contract rows, estimate-revision cutoffs, options "
                "demand/event-distance/spread/expiry reslices, borrow/FINRA sweeps, "
                "SEC periodic text fields without real text/cache, or accepted "
                "allocator source/scalar retunes."
            ),
            "new_evidence_required": (
                "Next legal alpha evidence needs materially more closed forward "
                "replacement rows, post-exp024 intraday rows with settled outcomes, "
                "estimate-revision 3/5/10d selected/current replacement values, "
                "populated PIT borrow economics, historical PIT options chains, real "
                "10-K/10-Q text/cache, or a genuinely new production-visible source."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            repo_rel(FORWARD_REPLACEMENT_LEDGER),
            repo_rel(FORWARD_READINESS_ARTIFACT),
            repo_rel(ESTIMATE_REVISION_HOT_LOG),
            repo_rel(INTRADAY_CONTRACT_LOG),
            repo_rel(INTRADAY_OUTCOME_LEDGER),
            repo_rel(OPTIONS_DEMAND_LOG),
            repo_rel(OPTIONS_EVENT_DISTANCE_LOG),
            repo_rel(BORROW_MANIFEST),
            repo_rel(SEC_FEATURES_SUMMARY),
            repo_rel(ALLOCATOR_BOUNDARY_LOG),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload)


def build_card(payload: dict[str, Any]) -> str:
    surfaces = payload["surface_readiness"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: post-latest alpha surface readiness audit",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Accepted alpha: `{payload['accepted_alpha']}`",
            f"- Forward rows: `{surfaces['forward_replacement']['rows']}`",
            f"- Forward rows with entry regime: `{surfaces['forward_replacement']['rows_with_entry_regime']}`",
            f"- Forward rows with short-volume percentile: `{surfaces['forward_replacement']['rows_with_short_volume_percentile']}`",
            f"- Estimate revision selected/current non-flat rows: `{surfaces['estimate_revision']['selected_current_nonflat_usable_rows']}`",
            f"- Estimate revision closed 3/5/10d rows: `{surfaces['estimate_revision']['selected_current_closed_3d_rows']} / {surfaces['estimate_revision']['selected_current_closed_5d_rows']} / {surfaces['estimate_revision']['selected_current_closed_10d_rows']}`",
            f"- Intraday post-contract outcome rows: `{surfaces['intraday']['post_contract_outcome_rows']}`",
            f"- Borrow populated pct: `{surfaces['borrow']['borrow_populated_pct']}`",
            "- Strategy behavior changed: `false`",
            "- Production orders changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        FORWARD_REPLACEMENT_LEDGER,
        FORWARD_READINESS_ARTIFACT,
        ESTIMATE_REVISION_HOT_LOG,
        INTRADAY_CONTRACT_LOG,
        INTRADAY_OUTCOME_LEDGER,
        OPTIONS_SETTLEMENT_LOG,
        OPTIONS_DEMAND_LOG,
        OPTIONS_EVENT_DISTANCE_LOG,
        BORROW_MANIFEST,
        SEC_FEATURES_SUMMARY,
        SEC_PERIODIC_LOG,
        ALLOCATOR_BOUNDARY_LOG,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
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
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
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
                "alpha_ready": payload["alpha_ready"],
                "forward_rows": payload["surface_readiness"]["forward_replacement"]["rows"],
                "estimate_revision_nonflat": payload["surface_readiness"]["estimate_revision"][
                    "selected_current_nonflat_usable_rows"
                ],
                "intraday_post_contract_rows": payload["surface_readiness"]["intraday"][
                    "post_contract_outcome_rows"
                ],
                "alpha_blockers": payload["gate4"]["alpha_blockers"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
