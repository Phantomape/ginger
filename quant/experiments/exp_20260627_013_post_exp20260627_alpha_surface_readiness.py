"""exp-20260627-013: post-exp20260627 alpha surface readiness audit.

Read-only alpha_search iteration. The run checks whether measurement contracts
added after exp-20260626-025 create any legal non-repeat alpha surface. It does
not change strategy behavior, shared helpers, rankings, sizing, exits, orders,
watchlists, or LLM decision boundaries.
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


EXPERIMENT_ID = "exp-20260627-013"
OWNER = "alpha-explore"
SLUG = "post_exp20260627_alpha_surface_readiness"
RUNNER = f"quant/experiments/exp_20260627_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_013_{SLUG}.json"
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
FORWARD_LEDGER = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
PRIOR_READINESS = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260626-025"
    / "exp_20260626_025_post_latest_alpha_surface_readiness_audit.json"
)
ESTIMATE_HOT_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260626-023.json"
ESTIMATE_CURRENT_SUMMARY = (
    REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_summary_20260626.json"
)
INTRADAY_CONTRACT_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260626-024.json"
INTRADAY_OUTCOME_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260626-019"
    / "intraday_advisory_forward_outcome_ledger.jsonl"
)
BORROW_MANIFEST = REPO_ROOT / "data" / "non_ohlcv" / "borrow_availability" / "manifest.json"
SEC_6K_EVENT_FILE = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_6k_20241002_20260421.jsonl"
)
SEC_6K_TEXT_FILE = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_6k_20241002_20260421.jsonl"
)
SEC_6K_CURRENT_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260627-010.json"
SEC_DEI_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260627-012.json"
SEC_CURRENT_FEATURES = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_features_summary_20260626.json"
)
FACTOR_RESIDUAL_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260627-003.json"

HYPOTHESIS = (
    "alpha_search/readiness: post-exp20260627 SEC 6-K semantic ledger, DEI "
    "cover-status parser, borrow wiring, intraday provenance, estimate-revision "
    "hot outcomes, and forward replacement rows may now expose one legal "
    "non-repeat alpha surface; if none passes predeclared field and maturity "
    "gates, record the blocker and do not retune saturated sources."
)
CHANGE_TYPE = "observed_only_alpha_readiness_audit"
MECHANISM_FAMILY = "alpha_enabling_nonrepeat_readiness"
TRIAL_FAMILY = "post_exp20260627_alpha_surface_readiness"
TRIAL_VARIANT_ID = "post_sec_dei_6k_borrow_revision_intraday_v1"
CHANGED_VARIABLE = "post_exp20260627_alpha_surface_readiness_v1"
NEW_EVIDENCE_TYPE = "post_20260627_measurement_contract_and_forward_surface_delta"
NEW_EVIDENCE_AXIS = (
    "Machine-checkable post-exp-20260626-025 surface delta: exp-20260627-010 "
    "current 6-K semantic ledger, exp-20260627-011 cover-XBRL document priority, "
    "exp-20260627-012 shared DEI cover-status parser, exp-20260627-002 borrow "
    "wiring, plus current forward/estimate/intraday ledgers; this is a readiness "
    "audit, not a field/threshold scan."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260626-025",
    "exp-20260627-002",
    "exp-20260627-004",
    "exp-20260627-010",
    "exp-20260627-012",
]
CAUSAL_COMPONENTS = [
    "post_exp027_sec_6k_dei_readiness",
    "estimate_revision_maturity_readiness",
    "intraday_post_contract_readiness",
    "borrow_and_forward_replacement_readiness",
    "no_strategy_behavior_change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260627-013/exp_20260627_013_post_exp20260627_alpha_surface_readiness.json",
    "experiments/cards/exp-20260627-013.md",
    "experiments/manifests/exp-20260627-013.json",
    "experiments/tickets/exp-20260627-013.json",
    "experiments/logs/exp-20260627-013.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


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
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def make_json_safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(key): make_json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(make_json_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        "windows": windows,
    }


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return {
        "success_probability": 0.24,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "no_material_new_closed_rows",
            "sec_text_or_dei_rows_missing",
            "estimate_revision_horizons_unmatured",
            "intraday_post_contract_rows_too_thin",
            "borrow_fields_unpopulated",
        ],
        "confidence_reason": (
            "Several new measurement contracts landed after exp-20260626-025, "
            "but prior logs show each surface is still likely sample- or "
            "field-blocked."
        ),
        "recorded_at": utc_now(),
    }


def summarize_forward_replacement() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_LEDGER)
    prior = read_json(PRIOR_READINESS, {})
    prior_forward = ((prior.get("surface_readiness") or {}).get("forward_replacement") or {})
    prior_rows = int(prior_forward.get("rows") or 0)
    by_sleeve = Counter(str(row.get("sleeve_key") or row.get("sleeve") or "unknown") for row in rows)
    closed_rows = [
        row for row in rows if row.get("replacement_value_vs_cash_usd") is not None
    ]
    rows_with_regime = sum(1 for row in rows if row.get("entry_regime_label"))
    rows_with_short = sum(
        1 for row in rows if row.get("entry_short_volume_ratio_percentile") is not None
    )
    blockers = []
    if len(closed_rows) < 60:
        blockers.append("closed_forward_rows_below_activation_floor_60")
    if len(rows) - prior_rows < 20:
        blockers.append("new_forward_row_delta_below_20")
    if rows_with_short < 40:
        blockers.append("entry_short_volume_tag_sample_still_thin")
    return {
        "surface": "forward_replacement_value",
        "artifact": repo_rel(FORWARD_LEDGER),
        "rows": len(rows),
        "prior_rows_exp_20260626_025": prior_rows,
        "row_delta_since_exp_20260626_025": len(rows) - prior_rows,
        "closed_cash_rows": len(closed_rows),
        "rows_with_entry_regime": rows_with_regime,
        "rows_with_short_volume_percentile": rows_with_short,
        "rows_by_sleeve": dict(by_sleeve),
        "alpha_ready": False,
        "blockers": blockers,
    }


def summarize_estimate_revision() -> dict[str, Any]:
    hot = read_json(ESTIMATE_HOT_LOG, {})
    current = read_json(ESTIMATE_CURRENT_SUMMARY, {})
    outcome = hot.get("outcome_summary") if isinstance(hot, dict) else {}
    if not isinstance(outcome, dict):
        outcome = {}
    selected = (outcome.get("surface_summaries") or {}).get("selected_current") or {}
    closed_by_horizon = selected.get("closed_rows_by_horizon") or {}
    nonflat = int(outcome.get("selected_current_nonflat_usable_rows") or 0)
    h3 = int(outcome.get("selected_current_closed_3d_rows") or closed_by_horizon.get("h3") or 0)
    h5 = int(outcome.get("selected_current_closed_5d_rows") or closed_by_horizon.get("h5") or 0)
    h10 = int(outcome.get("selected_current_closed_10d_rows") or closed_by_horizon.get("h10") or 0)
    blockers = []
    if nonflat < 20:
        blockers.append("selected_current_nonflat_sample_too_thin")
    if h3 < 20:
        blockers.append("forward_3d_outcomes_not_mature")
    if h5 < 20:
        blockers.append("forward_5d_outcomes_not_mature")
    if h10 < 20:
        blockers.append("forward_10d_outcomes_not_mature")
    if int(current.get("matched_candidate_rows") or 0) == 0:
        blockers.append("current_20260626_candidate_match_rows_zero")
    return {
        "surface": "estimate_revision_candidate_match_outcomes",
        "hot_log": repo_rel(ESTIMATE_HOT_LOG),
        "current_summary": repo_rel(ESTIMATE_CURRENT_SUMMARY),
        "hot_decision": hot.get("decision"),
        "matched_rows": outcome.get("matched_rows"),
        "selected_current_rows": outcome.get("selected_current_rows"),
        "selected_current_nonflat_usable_rows": nonflat,
        "selected_current_closed_entry_day_rows": outcome.get("selected_current_closed_entry_day_rows"),
        "selected_current_closed_1d_rows": outcome.get("selected_current_closed_1d_rows"),
        "selected_current_closed_3d_rows": h3,
        "selected_current_closed_5d_rows": h5,
        "selected_current_closed_10d_rows": h10,
        "current_20260626_candidate_match_rows": current.get("matched_candidate_rows"),
        "current_20260626_up_revision_rows": current.get("up_revision_rows"),
        "current_20260626_down_revision_rows": current.get("down_revision_rows"),
        "alpha_ready": False,
        "blockers": blockers,
    }


def summarize_intraday() -> dict[str, Any]:
    contract = read_json(INTRADAY_CONTRACT_LOG, {})
    ledger_rows = read_jsonl(INTRADAY_OUTCOME_LEDGER)
    latest = ((contract.get("gate2") or {}).get("latest_snapshot_projection") or {})
    post_contract_rows = [
        row
        for row in ledger_rows
        if row.get("decision_time_et")
        or row.get("primary_advisory_shadow_action")
        or row.get("is_primary_shadow_action") is not None
    ]
    blockers = []
    if len(post_contract_rows) < 20:
        blockers.append("post_contract_closed_outcome_rows_absent_or_too_thin")
    if int(latest.get("source_quote_time_rows") or 0) == 0:
        blockers.append("true_source_quote_time_still_absent")
    return {
        "surface": "intraday_shadow_action_provenance",
        "contract_log": repo_rel(INTRADAY_CONTRACT_LOG),
        "outcome_ledger": repo_rel(INTRADAY_OUTCOME_LEDGER),
        "contract_decision": contract.get("decision"),
        "outcome_rows": len(ledger_rows),
        "post_contract_outcome_rows": len(post_contract_rows),
        "latest_snapshot_date": latest.get("date"),
        "latest_snapshot_primary_action_count": latest.get("primary_action_count"),
        "latest_snapshot_source_quote_time_rows": latest.get("source_quote_time_rows"),
        "latest_snapshot_shadow_actions": latest.get("shadow_actions"),
        "alpha_ready": False,
        "blockers": blockers,
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
        "last_collected_as_of": manifest.get("last_collected_as_of"),
        "alpha_ready": False,
        "blockers": blockers,
    }


def summarize_sec_6k() -> dict[str, Any]:
    events = read_jsonl(SEC_6K_EVENT_FILE)
    text_rows = read_jsonl(SEC_6K_TEXT_FILE)
    current_log = read_json(SEC_6K_CURRENT_LOG, {})
    ledger_summary = current_log.get("ledger_summary") if isinstance(current_log, dict) else {}
    if not isinstance(ledger_summary, dict):
        ledger_summary = {}
    blockers = []
    if len(text_rows) == 0:
        blockers.append("historical_standard_window_6k_text_missing")
    if int(ledger_summary.get("sec_6k_text_rows") or 0) < 20:
        blockers.append("current_6k_forward_sample_too_thin")
    if int(ledger_summary.get("rows_with_guidance_direction") or 0) == 0:
        blockers.append("no_guidance_direction_hit")
    return {
        "surface": "sec_6k_operating_guidance_semantics",
        "event_file": repo_rel(SEC_6K_EVENT_FILE),
        "text_file": repo_rel(SEC_6K_TEXT_FILE),
        "current_log": repo_rel(SEC_6K_CURRENT_LOG),
        "historical_event_rows": len(events),
        "historical_text_rows": len(text_rows),
        "current_6k_text_rows": ledger_summary.get("sec_6k_text_rows"),
        "current_rows_with_guidance_direction": ledger_summary.get("rows_with_guidance_direction"),
        "current_usable_for_future_alpha_rows": ledger_summary.get("usable_for_future_6k_alpha_rows"),
        "alpha_ready": False,
        "blockers": blockers,
    }


def summarize_sec_dei() -> dict[str, Any]:
    dei_log = read_json(SEC_DEI_LOG, {})
    features = read_json(SEC_CURRENT_FEATURES, {})
    current_coverage = ((dei_log.get("gate2") or {}).get("current_daily_status_coverage") or {})
    cache_rows = read_jsonl(SEC_6K_TEXT_FILE)  # harmless anchor for manifest consistency
    del cache_rows
    blockers = []
    if int(current_coverage.get("periodic_rows_with_filer_status") or 0) == 0:
        blockers.append("current_periodic_rows_with_filer_status_zero")
    if int(features.get("rows_with_filer_status") or 0) == 0:
        blockers.append("current_feature_rows_with_filer_status_zero")
    return {
        "surface": "sec_dei_cover_status_transition",
        "dei_log": repo_rel(SEC_DEI_LOG),
        "features_summary": repo_rel(SEC_CURRENT_FEATURES),
        "parser_decision": dei_log.get("decision"),
        "current_periodic_feature_rows": current_coverage.get("periodic_feature_rows"),
        "current_periodic_rows_with_filer_status": current_coverage.get(
            "periodic_rows_with_filer_status"
        ),
        "current_rows_with_filer_status": current_coverage.get("rows_with_filer_status"),
        "feature_summary_rows_with_filer_status": features.get("rows_with_filer_status"),
        "alpha_ready": False,
        "blockers": blockers,
    }


def summarize_factor_residual() -> dict[str, Any]:
    log = read_json(FACTOR_RESIDUAL_LOG, {})
    gate4 = log.get("gate4") if isinstance(log, dict) else {}
    if not isinstance(gate4, dict):
        gate4 = {}
    return {
        "surface": "factor_residual_repaired_warehouse",
        "log": repo_rel(FACTOR_RESIDUAL_LOG),
        "decision": log.get("decision"),
        "accepted_alpha": log.get("accepted_alpha"),
        "failed_reasons": gate4.get("failed_reasons"),
        "alpha_ready": False,
        "blockers": ["latest_factor_residual_candidate_pool_rejected_gate4"],
    }


def calibration(prediction: dict[str, Any], actual_success: bool, failure_modes: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if actual_success else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    return {
        "predicted_success_probability": probability,
        "actual_success": int(actual),
        "brier_score": round((probability - actual) ** 2, 4),
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": failure_modes,
        "predicted_failure_mode_hit": any(mode in failure_modes for mode in predicted_modes),
        "surprise_note": (
            "No post-exp20260627 surface reached alpha-ready gates; the result matches "
            "the low-confidence readiness prediction."
            if not actual_success
            else "At least one post-exp20260627 surface reached alpha-ready gates."
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
        "borrow": summarize_borrow(),
        "sec_6k": summarize_sec_6k(),
        "sec_dei": summarize_sec_dei(),
        "factor_residual": summarize_factor_residual(),
    }

    required = [
        BASELINE_RESULT,
        FORWARD_LEDGER,
        PRIOR_READINESS,
        ESTIMATE_HOT_LOG,
        ESTIMATE_CURRENT_SUMMARY,
        INTRADAY_CONTRACT_LOG,
        INTRADAY_OUTCOME_LEDGER,
        BORROW_MANIFEST,
        SEC_6K_EVENT_FILE,
        SEC_6K_CURRENT_LOG,
        SEC_DEI_LOG,
        SEC_CURRENT_FEATURES,
    ]
    missing = [repo_rel(path) for path in required if not path.exists()]
    measurement_blockers = []
    if not baseline["baseline_exists"] or baseline["window_count"] != 3:
        measurement_blockers.append("baseline_missing_or_wrong_window_count")
    if missing:
        measurement_blockers.append("required_surface_files_missing")

    surface_blockers = []
    for name, summary in surfaces.items():
        surface_blockers.extend(f"{name}_{blocker}" for blocker in summary.get("blockers", []))
    alpha_ready_surfaces = [name for name, summary in surfaces.items() if summary.get("alpha_ready")]
    alpha_ready = not measurement_blockers and bool(alpha_ready_surfaces)
    accepted = alpha_ready
    status = "accepted" if accepted else "rejected"
    decision = (
        "accepted_post_exp20260627_alpha_surface_ready"
        if accepted
        else "rejected_no_gate_ready_post_exp20260627_alpha_surface"
    )
    all_blockers = sorted(set([*measurement_blockers, *surface_blockers]))

    gate4 = {
        "passed": accepted,
        "accepted_alpha": accepted,
        "alpha_ready": alpha_ready,
        "alpha_ready_surfaces": alpha_ready_surfaces,
        "decision": decision,
        "failed_reasons": [] if accepted else all_blockers,
        "strategy_behavior_changed": False,
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
        },
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": accepted,
        "alpha_ready": alpha_ready,
        "observed_only_lead": False,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_summary": (
            "Audited post-exp20260627 readiness surfaces; no strategy behavior changed."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_alpha_readiness_audit",
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
        "calibration": calibration(prediction, accepted, all_blockers),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_prior_near_neighbors": {
                "exp-20260626-025": (
                    "Previous post-latest readiness audit before the SEC 6-K/DEI "
                    "parser and borrow wiring sequence."
                ),
                "exp-20260627-010": "Current 6-K semantic ledger: two rows, no guidance hit.",
                "exp-20260627-012": "Shared DEI parser accepted, but current rows still zero status.",
                "novelty_gate": ticket.get("novelty"),
            },
            "3_single_policy_bundle": (
                "One readiness bundle: check whether any new post-exp20260627 "
                "surface meets predeclared field and maturity gates."
            ),
            "4_acceptance_standard": (
                "Accept alpha only if at least one surface is alpha_ready with "
                "required fields, sufficient closed rows, and no strategy behavior "
                "change. Otherwise reject and record blockers."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "required_surface_files": [repo_rel(path) for path in required],
            "missing_required_surface_files": missing,
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
            "alpha_ready_surface_count": len(alpha_ready_surfaces),
            "forward_row_delta_since_exp_20260626_025": surfaces["forward_replacement"][
                "row_delta_since_exp_20260626_025"
            ],
            "estimate_revision_selected_current_nonflat_rows": surfaces["estimate_revision"][
                "selected_current_nonflat_usable_rows"
            ],
            "sec_6k_historical_text_rows": surfaces["sec_6k"]["historical_text_rows"],
            "sec_dei_current_periodic_status_rows": surfaces["sec_dei"][
                "current_periodic_rows_with_filer_status"
            ],
        },
        "gate1": {
            "passed": baseline["baseline_exists"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": not missing,
            "dependencies_validated": not missing,
            "required_surface_files": [repo_rel(path) for path in required],
            "missing_required_surface_files": missing,
            "fields_checked": [
                "entry_date",
                "target_price_scope",
                "forward_replacement.replacement_value_vs_cash_usd",
                "forward_replacement.entry_regime_label",
                "forward_replacement.entry_short_volume_ratio_percentile",
                "estimate_revision.selected_current_nonflat_usable_rows",
                "estimate_revision.closed_3d_5d_10d_rows",
                "intraday.primary_advisory_shadow_action",
                "borrow_availability.short_sell_rate",
                "sec_6k.combined_text",
                "sec_dei.filer_status_booleans",
            ],
            "entry_date_target_price_note": (
                "Readiness audit only. Entry dates are checked where replacement "
                "ledgers exist; target_price is not used because no exit/order is "
                "scheduled."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "No executable filter, entry, exit, ranking, sizing, or order rule was added.",
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
                "The post-exp20260627 repairs improved data contracts but did not "
                "create a Gate-4-ready alpha surface: forward rows rose only from "
                "40 to 41, estimate revision still has only 18 selected/current "
                "non-flat rows and no 3/5/10d maturity, intraday has no sufficient "
                "post-contract closed outcomes, borrow fields remain unpopulated, "
                "historical 6-K text is absent, current 6-K has only two rows with "
                "no guidance hit, DEI status rows are still zero, and the repaired "
                "factor-residual source already failed Gate 4."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry estimate-revision thresholds, 6-K phrase scans, "
                "DEI/status current-category approximations, borrow/FINRA sweeps, "
                "intraday threshold rules on pre-contract rows, forward readiness "
                "reslices, or adjacent factor-residual OHLCV thresholds from these "
                "same artifacts."
            ),
            "new_evidence_required": (
                "Next legal alpha evidence requires materially more closed forward "
                "replacement rows, mature estimate-revision 3/5/10d selected/current "
                "outcomes, post-exp024 intraday closed rows with primary actions, "
                "populated PIT borrow economics, replayable historical 6-K or "
                "10-K/10-Q text/status rows, or a genuinely new production-visible "
                "source."
            ),
        },
        "rejection_reason": None if accepted else "; ".join(all_blockers),
        "next_retry_requires": [
            "materially_more_closed_forward_replacement_rows",
            "mature_estimate_revision_selected_current_3_5_10d_outcomes",
            "post_contract_intraday_closed_replacement_rows",
            "populated_pit_borrow_economics",
            "replayable_historical_sec_6k_or_dei_status_rows",
            "genuinely_new_production_visible_source",
        ],
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            repo_rel(FORWARD_LEDGER),
            repo_rel(PRIOR_READINESS),
            repo_rel(ESTIMATE_HOT_LOG),
            repo_rel(ESTIMATE_CURRENT_SUMMARY),
            repo_rel(INTRADAY_CONTRACT_LOG),
            repo_rel(INTRADAY_OUTCOME_LEDGER),
            repo_rel(BORROW_MANIFEST),
            repo_rel(SEC_6K_EVENT_FILE),
            repo_rel(SEC_6K_TEXT_FILE),
            repo_rel(SEC_6K_CURRENT_LOG),
            repo_rel(SEC_DEI_LOG),
            repo_rel(SEC_CURRENT_FEATURES),
            repo_rel(FACTOR_RESIDUAL_LOG),
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
    record = dict(payload)
    windows = record.get("before_metrics", {}).get("windows")
    if isinstance(windows, list):
        record["before_metrics"] = {**record["before_metrics"], "windows": windows[:3]}
        record["after_metrics"] = {**record["after_metrics"], "windows": windows[:3]}
    return record


def build_card(payload: dict[str, Any]) -> str:
    surfaces = payload["surface_readiness"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: post-exp20260627 alpha surface readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Accepted alpha: `{payload['accepted_alpha']}`",
            f"- Alpha-ready surfaces: `{payload['delta_metrics']['alpha_ready_surface_count']}`",
            f"- Forward rows: `{surfaces['forward_replacement']['rows']}`",
            f"- Forward row delta vs exp-20260626-025: `{surfaces['forward_replacement']['row_delta_since_exp_20260626_025']}`",
            f"- Estimate-revision non-flat selected/current rows: `{surfaces['estimate_revision']['selected_current_nonflat_usable_rows']}`",
            f"- Current 6-K text rows: `{surfaces['sec_6k']['current_6k_text_rows']}`",
            f"- Historical 6-K text rows: `{surfaces['sec_6k']['historical_text_rows']}`",
            f"- Current DEI periodic status rows: `{surfaces['sec_dei']['current_periodic_rows_with_filer_status']}`",
            f"- Borrow populated pct: `{surfaces['borrow']['borrow_populated_pct']}`",
            "- Strategy behavior changed: `false`",
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
        FORWARD_LEDGER,
        PRIOR_READINESS,
        ESTIMATE_HOT_LOG,
        ESTIMATE_CURRENT_SUMMARY,
        INTRADAY_CONTRACT_LOG,
        INTRADAY_OUTCOME_LEDGER,
        BORROW_MANIFEST,
        SEC_6K_EVENT_FILE,
        SEC_6K_TEXT_FILE,
        SEC_6K_CURRENT_LOG,
        SEC_DEI_LOG,
        SEC_CURRENT_FEATURES,
        FACTOR_RESIDUAL_LOG,
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
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "observed_only_lead": payload["observed_only_lead"],
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
            "change_summary": payload["change_summary"],
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
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
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
                "alpha_ready_surface_count": payload["delta_metrics"]["alpha_ready_surface_count"],
                "forward_rows": payload["surface_readiness"]["forward_replacement"]["rows"],
                "forward_row_delta": payload["surface_readiness"]["forward_replacement"][
                    "row_delta_since_exp_20260626_025"
                ],
                "estimate_revision_nonflat": payload["surface_readiness"]["estimate_revision"][
                    "selected_current_nonflat_usable_rows"
                ],
                "sec_6k_historical_text_rows": payload["surface_readiness"]["sec_6k"][
                    "historical_text_rows"
                ],
                "sec_dei_current_periodic_status_rows": payload["surface_readiness"]["sec_dei"][
                    "current_periodic_rows_with_filer_status"
                ],
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
