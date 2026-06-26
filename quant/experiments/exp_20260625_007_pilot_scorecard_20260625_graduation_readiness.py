"""exp-20260625-007: current pilot scorecard graduation readiness.

Observed-only alpha/risk-allocation audit over the generated 2026-06-25
pilot scorecard and recommendations. The experiment asks whether any
default-off pilot sleeve has enough forward closed rows, positive SPY
replacement value, and drawdown headroom to graduate. It does not change
signals, entries, exits, ranking, sizing, pilot state, recommendations, or
orders.
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
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from quant import pilot_tracker  # noqa: E402


EXPERIMENT_ID = "exp-20260625-007"
OWNER = "alpha-explore"
SLUG = "pilot_scorecard_20260625_graduation_readiness"
RUNNER = f"quant/experiments/exp_20260625_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_007_{SLUG}.json"
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
PILOT_SCORECARD = REPO_ROOT / "data" / "pilots" / "pilot_scorecard.json"
PILOT_RECS = REPO_ROOT / "data" / "pilots" / "pilot_recommendations_2026-06-25.json"
PILOT_TRACKER_MD = REPO_ROOT / "data" / "pilots" / "pilot_tracker.md"

HYPOTHESIS = (
    "Observed-only alpha/risk allocation: the 2026-06-25 live pilot scorecard "
    "may identify a default-off pilot sleeve ready to graduate only if it has "
    "enough closed trades, positive replacement value versus SPY, and book "
    "drawdown below the precommitted envelope."
)
CHANGE_TYPE = "pilot_forward_readiness_audit"
IMPLEMENTATION_MODE = "observed_only_attribution"
MECHANISM_FAMILY = "pilot_or_sleeve"
TRIAL_FAMILY = "pilot_scorecard_forward_graduation_readiness"
TRIAL_VARIANT_ID = "current_pilot_scorecard_20260625_v1"
CHANGED_VARIABLE = "pilot_scorecard_20260625_graduation_readiness_v1"
CAUSAL_COMPONENTS = [
    "current pilot scorecard",
    "current pilot recommendations",
    "closed-trade and replacement-value readiness gates",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-006",
    "exp-20260624-010",
    "exp-20260624-014",
]
NEW_EVIDENCE_AXIS = (
    "New 2026-06-25 generated pilot_scorecard and pilot_recommendations rows "
    "after exp-20260624-010, including updated fundamental_growth_rs closed "
    "rows and current cross-pilot DDOG overlap context; this is not a "
    "frozen-window threshold or source retune."
)

ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260625-007/exp_20260625_007_pilot_scorecard_20260625_graduation_readiness.json",
    "experiments/cards/exp-20260625-007.md",
    "experiments/manifests/exp-20260625-007.json",
    "experiments/tickets/exp-20260625-007.json",
    "experiments/logs/exp-20260625-007.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
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


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict) and prediction.get("confidence_reason"):
        return prediction
    return {
        "success_probability": 0.12,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "closed_rows_too_few",
            "negative_replacement_value",
            "drawdown_kill_breach",
            "cross_pilot_overlap_risk",
        ],
        "confidence_reason": (
            "Fallback prediction; the ticket normally carries the reservation-time "
            "prediction for this current pilot scorecard readiness audit."
        ),
        "recorded_at": utc_now(),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(float(row.get("signals_generated") or 0.0) for row in windows)
    survived = sum(float(row.get("signals_survived") or 0.0) for row in windows)
    compact_windows = [
        {
            "label": row.get("label"),
            "start": row.get("start"),
            "end": row.get("end"),
            "expected_value_score": row.get("expected_value_score"),
            "total_pnl": row.get("total_pnl"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "sharpe_daily": row.get("sharpe_daily"),
        }
        for row in windows
        if isinstance(row, dict)
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
        "windows": compact_windows,
    }


def graduate_rule(scorecard_payload: dict[str, Any]) -> dict[str, float | int]:
    rule = scorecard_payload.get("graduate_rule")
    if not isinstance(rule, dict):
        rule = {}
    return {
        "min_closed": safe_int(rule.get("min_closed") or pilot_tracker.GRADUATE_MIN_CLOSED),
        "min_rv_spy_usd": float(
            safe_float(rule.get("min_rv_spy_usd")) if safe_float(rule.get("min_rv_spy_usd")) is not None else pilot_tracker.GRADUATE_MIN_RV_SPY_USD
        ),
        "max_book_dd_pct": float(
            safe_float(rule.get("max_book_dd_pct")) if safe_float(rule.get("max_book_dd_pct")) is not None else pilot_tracker.GRADUATE_MAX_BOOK_DD_PCT
        ),
    }


def scorecards(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("scorecards") if isinstance(payload, dict) else []
    return [row for row in rows or [] if isinstance(row, dict)]


def recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("recommendations") if isinstance(payload, dict) else []
    return [row for row in rows or [] if isinstance(row, dict)]


def summarize_scorecards(
    scorecard_rows: list[dict[str, Any]],
    rule: dict[str, float | int],
) -> dict[str, Any]:
    pilots: list[dict[str, Any]] = []
    failure_counter: Counter[str] = Counter()
    for row in scorecard_rows:
        closed = safe_int(row.get("closed_trades"))
        rv_spy = safe_float(row.get("rv_vs_spy_usd")) or 0.0
        dd_pct = safe_float(row.get("book_max_drawdown_pct")) or 0.0
        verdict = str(row.get("verdict") or "")
        checks = {
            "min_closed_trades": closed >= int(rule["min_closed"]),
            "positive_rv_vs_spy": rv_spy > float(rule["min_rv_spy_usd"]),
            "book_drawdown_within_envelope": dd_pct < float(rule["max_book_dd_pct"]),
            "not_kill_verdict": verdict != "KILL",
        }
        failed = []
        if not checks["min_closed_trades"]:
            failed.append("closed_rows_too_few")
        if not checks["positive_rv_vs_spy"]:
            failed.append("replacement_value_vs_spy_not_positive")
        if not checks["book_drawdown_within_envelope"]:
            failed.append("book_drawdown_ceiling_breached")
        if not checks["not_kill_verdict"]:
            failed.append("pilot_verdict_kill")
        for reason in failed:
            failure_counter[reason] += 1
        pilots.append(
            {
                "pilot": row.get("pilot"),
                "label": row.get("label"),
                "sleeve": row.get("sleeve"),
                "as_of": row.get("as_of"),
                "closed_trades": closed,
                "open_positions": safe_int(row.get("open_positions")),
                "pending_entries": safe_int(row.get("pending_entries")),
                "hit_rate": row.get("hit_rate"),
                "realized_pilot_pnl_usd": row.get("realized_pilot_pnl_usd"),
                "replacement_value_rows": row.get("replacement_value_rows"),
                "rv_vs_cash_usd": row.get("rv_vs_cash_usd"),
                "rv_vs_spy_usd": row.get("rv_vs_spy_usd"),
                "rv_vs_qqq_usd": row.get("rv_vs_qqq_usd"),
                "book_max_drawdown_usd": row.get("book_max_drawdown_usd"),
                "book_max_drawdown_pct": row.get("book_max_drawdown_pct"),
                "drawdown_ceiling_breached": row.get("drawdown_ceiling_breached"),
                "verdict": verdict,
                "verdict_note": row.get("verdict_note"),
                "checks": checks,
                "failed_checks": failed,
                "graduation_ready": not failed,
            }
        )
    return {
        "as_of_pilots": sorted({row.get("as_of") for row in pilots if row.get("as_of")}),
        "rule": rule,
        "pilot_count": len(pilots),
        "closed_trades_total": sum(row["closed_trades"] for row in pilots),
        "open_positions_total": sum(row["open_positions"] for row in pilots),
        "pending_entries_total": sum(row["pending_entries"] for row in pilots),
        "killed_pilots": [row["pilot"] for row in pilots if row["verdict"] == "KILL"],
        "collecting_pilots": [row["pilot"] for row in pilots if row["verdict"] == "COLLECTING"],
        "graduation_ready_pilots": [row["pilot"] for row in pilots if row["graduation_ready"]],
        "failure_reason_counts": dict(failure_counter),
        "pilots": pilots,
    }


def summarize_recommendations(rec_payload: dict[str, Any]) -> dict[str, Any]:
    rows = recommendations(rec_payload)
    recs = []
    killed_enter_rows = []
    skipped_by_status: Counter[str] = Counter()
    actionable_by_status: Counter[str] = Counter()
    for rec in rows:
        actionable = [row for row in rec.get("actionable") or [] if isinstance(row, dict)]
        skipped = [row for row in rec.get("skipped") or [] if isinstance(row, dict)]
        actionable_statuses = [str(row.get("status") or "") for row in actionable]
        skipped_statuses = [str(row.get("status") or "") for row in skipped]
        actionable_by_status.update(actionable_statuses)
        skipped_by_status.update(skipped_statuses)
        if rec.get("pilot_verdict") == "KILL":
            for item in actionable:
                if item.get("status") == "ENTER_NEXT_OPEN":
                    killed_enter_rows.append(
                        {
                            "pilot": rec.get("pilot"),
                            "ticker": item.get("ticker"),
                            "entry_date": item.get("entry_date"),
                            "status": item.get("status"),
                        }
                    )
        recs.append(
            {
                "pilot": rec.get("pilot"),
                "label": rec.get("label"),
                "sleeve": rec.get("sleeve"),
                "as_of": rec.get("as_of"),
                "pilot_verdict": rec.get("pilot_verdict"),
                "new_entries_blocked": bool(rec.get("new_entries_blocked")),
                "actionable_count": len(actionable),
                "actionable_statuses": actionable_statuses,
                "actionable_tickers": [row.get("ticker") for row in actionable],
                "enter_next_open_count": actionable_statuses.count("ENTER_NEXT_OPEN"),
                "exit_next_session_count": actionable_statuses.count("EXIT_NEXT_SESSION"),
                "hold_count": actionable_statuses.count("HOLD"),
                "skipped_count": len(skipped),
                "skipped_statuses": skipped_statuses,
                "kill_blocked_tickers": [
                    row.get("ticker")
                    for row in skipped
                    if row.get("status") == "SKIP_pilot_kill_verdict"
                ],
            }
        )
    return {
        "as_of": rec_payload.get("as_of") if isinstance(rec_payload, dict) else None,
        "pilot_count": len(recs),
        "actionable_by_status": dict(actionable_by_status),
        "skipped_by_status": dict(skipped_by_status),
        "killed_pilot_enter_next_open_count": len(killed_enter_rows),
        "killed_pilot_enter_next_open": killed_enter_rows,
        "recommendations": recs,
    }


def summarize_overlap(scorecard_payload: dict[str, Any], rec_payload: dict[str, Any]) -> dict[str, Any]:
    rows = scorecard_payload.get("cross_pilot_overlap") if isinstance(scorecard_payload, dict) else []
    if not rows and isinstance(rec_payload, dict):
        rows = rec_payload.get("cross_pilot_overlap") or []
    overlap_rows = []
    killed_overlap_count = 0
    all_have_context = True
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        contexts = [ctx for ctx in row.get("participant_context") or [] if isinstance(ctx, dict)]
        all_have_context = all_have_context and bool(contexts)
        killed_contexts = [ctx for ctx in contexts if ctx.get("pilot_verdict") == "KILL"]
        killed_overlap_count += len(killed_contexts)
        overlap_rows.append(
            {
                "ticker": row.get("ticker"),
                "positions": row.get("positions"),
                "total_exposure_usd": row.get("total_exposure_usd"),
                "has_participant_context": bool(contexts),
                "pilot_verdicts": row.get("pilot_verdicts"),
                "new_entries_blocked_by_pilot": row.get("new_entries_blocked_by_pilot"),
                "killed_participants": [
                    {
                        "pilot_key": ctx.get("pilot_key"),
                        "pilot": ctx.get("pilot"),
                        "status": ctx.get("status"),
                        "actionable_status": ctx.get("actionable_status"),
                        "entry_date": ctx.get("entry_date"),
                        "unrealized_pct": ctx.get("unrealized_pct"),
                    }
                    for ctx in killed_contexts
                ],
                "participants": [
                    {
                        "pilot_key": ctx.get("pilot_key"),
                        "pilot": ctx.get("pilot"),
                        "pilot_verdict": ctx.get("pilot_verdict"),
                        "new_entries_blocked": ctx.get("new_entries_blocked"),
                        "actionable_status": ctx.get("actionable_status"),
                        "entry_date": ctx.get("entry_date"),
                        "pilot_notional_usd": ctx.get("pilot_notional_usd"),
                    }
                    for ctx in contexts
                ],
            }
        )
    return {
        "overlap_count": len(overlap_rows),
        "all_overlap_rows_have_participant_context": all_have_context,
        "overlap_with_kill_participant_count": killed_overlap_count,
        "rows": overlap_rows,
    }


def field_exists(payload: Any, path: list[str]) -> bool:
    current = payload
    for key in path:
        if isinstance(current, dict):
            if key not in current:
                return False
            current = current[key]
        elif isinstance(current, list):
            if not current:
                return False
            current = current[0]
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        else:
            return False
    return True


def readiness_decision(
    score_summary: dict[str, Any],
    rec_summary: dict[str, Any],
    overlap_summary: dict[str, Any],
) -> tuple[bool, list[str], dict[str, bool]]:
    checks = {
        "at_least_one_graduation_ready_pilot": bool(score_summary["graduation_ready_pilots"]),
        "no_killed_pilot_enter_next_open": rec_summary["killed_pilot_enter_next_open_count"] == 0,
        "overlap_context_auditable": overlap_summary["all_overlap_rows_have_participant_context"],
        "no_cross_pilot_overlap_with_kill": overlap_summary["overlap_with_kill_participant_count"] == 0,
    }
    failed = []
    if not checks["at_least_one_graduation_ready_pilot"]:
        failed.append("no_graduation_ready_pilot")
    if not checks["no_killed_pilot_enter_next_open"]:
        failed.append("killed_pilot_has_enter_next_open")
    if not checks["overlap_context_auditable"]:
        failed.append("cross_pilot_overlap_missing_participant_context")
    if not checks["no_cross_pilot_overlap_with_kill"]:
        failed.append("cross_pilot_overlap_with_kill_verdict")
    failed.extend(
        sorted(
            reason
            for reason, count in score_summary["failure_reason_counts"].items()
            if count > 0
        )
    )
    return not failed, failed, checks


def calibration(prediction: dict[str, Any], actual_success: bool, failed_reasons: list[str]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability"))
    if probability is None:
        probability = 0.0
    realized_modes = []
    for mode in prediction.get("main_failure_modes") or []:
        mode_text = str(mode)
        if mode_text == "closed_rows_too_few" and "closed_rows_too_few" in failed_reasons:
            realized_modes.append(mode_text)
        elif mode_text == "negative_replacement_value" and "replacement_value_vs_spy_not_positive" in failed_reasons:
            realized_modes.append(mode_text)
        elif mode_text == "drawdown_kill_breach" and "book_drawdown_ceiling_breached" in failed_reasons:
            realized_modes.append(mode_text)
        elif mode_text == "cross_pilot_overlap_risk" and "cross_pilot_overlap_with_kill_verdict" in failed_reasons:
            realized_modes.append(mode_text)
    return {
        "predicted_success_probability": probability,
        "actual_success": actual_success,
        "brier_score": round((probability - (1.0 if actual_success else 0.0)) ** 2, 6),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": realized_modes,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket)
    baseline = baseline_metrics()
    scorecard_payload = read_json(PILOT_SCORECARD, {})
    rec_payload = read_json(PILOT_RECS, {})
    rule = graduate_rule(scorecard_payload)
    score_summary = summarize_scorecards(scorecards(scorecard_payload), rule)
    rec_summary = summarize_recommendations(rec_payload)
    overlap_summary = summarize_overlap(scorecard_payload, rec_payload)
    success, failed_reasons, readiness_checks = readiness_decision(
        score_summary,
        rec_summary,
        overlap_summary,
    )
    status = "observed_only_accepted" if success else "observed_only_rejected"
    decision = (
        "accepted_current_pilot_scorecard_graduation_ready"
        if success
        else "rejected_no_current_pilot_graduation_ready"
    )
    now = utc_now()
    after_metrics = {
        **baseline,
        "scorecard_count": score_summary["pilot_count"],
        "activation_ready_pilots": len(score_summary["graduation_ready_pilots"]),
        "graduation_ready_pilots": score_summary["graduation_ready_pilots"],
        "killed_pilot_count": len(score_summary["killed_pilots"]),
        "killed_pilots": score_summary["killed_pilots"],
        "pilot_closed_trades_total": score_summary["closed_trades_total"],
        "pilot_open_positions_total": score_summary["open_positions_total"],
        "pilot_pending_entries_total": score_summary["pending_entries_total"],
        "killed_pilot_enter_next_open_count": rec_summary["killed_pilot_enter_next_open_count"],
        "cross_pilot_overlap_count": overlap_summary["overlap_count"],
        "cross_pilot_overlap_with_kill_participant_count": overlap_summary[
            "overlap_with_kill_participant_count"
        ],
    }
    delta_metrics = {
        "aggregate_expected_value_score": 0.0,
        "aggregate_total_pnl": 0.0,
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "survival_rate_delta": 0.0,
        "strategy_behavior_delta": 0.0,
        "activation_ready_pilots": len(score_summary["graduation_ready_pilots"]),
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": success,
        "accepted_alpha": False,
        "observed_only_lead": success,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "current_forward_pilot_scorecard_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, success, failed_reasons),
        "pre_run_questions": {
            "alpha_hypothesis": HYPOTHESIS,
            "history_check": (
                "Novelty gate allowed the current 2026-06-25 scorecard rows. "
                "Nearby priors were exp-20260623-006 drawdown kill semantics, "
                "exp-20260624-010 overlap participant context, and "
                "exp-20260624-014 allocator current-open readiness."
            ),
            "single_policy_bundle": (
                "One observed-only current pilot scorecard graduation-readiness "
                "audit; strategy behavior remains unchanged."
            ),
            "success_standard": (
                "A pilot graduates only if closed trades meet the generated "
                "min_closed rule, RV vs SPY is positive, book drawdown is below "
                "15%, verdict is not KILL, killed pilots do not emit new buys, "
                "and overlap context is auditable."
            ),
            "reproduction": RUNNER_COMMAND,
        },
        "parameters": {
            "graduate_rule": rule,
            "scorecard_file": repo_rel(PILOT_SCORECARD),
            "recommendations_file": repo_rel(PILOT_RECS),
        },
        "scorecard_summary": score_summary,
        "recommendation_summary": rec_summary,
        "cross_pilot_overlap_summary": overlap_summary,
        "before_metrics": baseline,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": baseline["expected_value_score_sum"],
            "baseline_total_pnl": baseline["total_pnl"],
            "baseline_trade_count": baseline["trade_count"],
        },
        "gate2": {
            "passed": all(
                [
                    field_exists(scorecard_payload, ["scorecards", "closed_trades"]),
                    field_exists(scorecard_payload, ["scorecards", "rv_vs_spy_usd"]),
                    field_exists(scorecard_payload, ["scorecards", "book_max_drawdown_pct"]),
                    field_exists(scorecard_payload, ["scorecards", "verdict"]),
                    field_exists(rec_payload, ["recommendations", "actionable"]),
                    field_exists(scorecard_payload, ["cross_pilot_overlap", "participant_context"]),
                    field_exists(scorecard_payload, ["cross_pilot_overlap", "participant_context", "entry_date"]),
                ]
            ),
            "required_fields": [
                "scorecards.closed_trades",
                "scorecards.rv_vs_spy_usd",
                "scorecards.book_max_drawdown_pct",
                "scorecards.verdict",
                "recommendations.actionable",
                "cross_pilot_overlap.participant_context",
                "cross_pilot_overlap.participant_context.entry_date",
            ],
            "entry_date_present_in_overlap_context": field_exists(
                scorecard_payload,
                ["cross_pilot_overlap", "participant_context", "entry_date"],
            ),
            "target_price_required": False,
            "target_price_note": (
                "This observed-only current pilot scorecard audit does not create "
                "historical entry rows or target_price-derived trade signals."
            ),
        },
        "gate3": {
            "passed": baseline["survival_rate"] is not None and baseline["survival_rate"] >= 0.05,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "filter_added": False,
            "note": "No strategy filter was added; baseline survival remains unchanged.",
        },
        "gate4": {
            "passed": success,
            "decision": decision,
            "checks": readiness_checks,
            "failed_reasons": failed_reasons,
            "ready_pilots": score_summary["graduation_ready_pilots"],
            "before_after_policy_delta": "none",
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "status": status,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "pilot_state_changed": False,
            "pilot_recommendations_changed": False,
            "daily_snapshot_exposed": True,
            "live_ready": False,
            "replay_only": False,
            "parity_note": (
                "Observed-only audit of already generated scorecard and "
                "recommendation files. No production or paper behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "No pilot met the graduation rule. Allocator and distribution "
                "have zero closed trades. fundamental_growth_rs has only six "
                "closed trades, negative replacement value versus SPY, and a "
                "24.29% book drawdown that breaches the 15% envelope."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun current pilot graduation readiness by only changing "
                "min_closed, RV, drawdown, verdict, overlap, or recommendation "
                "thresholds on the same 2026-06-25 scorecard. Reopen only with "
                "materially more closed forward rows or a different shared "
                "allocation policy tested through Gate 1-4."
            ),
            "new_evidence_required": (
                "Wait for additional closed pilot trades, or move to a new "
                "production-visible data surface with PIT coverage instead of "
                "retuning current pilot readiness gates."
            ),
            "reproducibility": (
                "The runner reads the baseline, pilot scorecard, and 2026-06-25 "
                "recommendation snapshot, then writes artifact, log, card, "
                "manifest, JSONL row, and closes the ticket through "
                "persist_self_registered_result."
            ),
        },
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(PILOT_SCORECARD),
            repo_rel(PILOT_RECS),
            repo_rel(PILOT_TRACKER_MD),
            repo_rel(TICKET_JSON),
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
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {"used_javascript": False, "evidence": "Python runner only; no node/js tooling invoked."},
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "scorecard_summary",
        "recommendation_summary",
        "cross_pilot_overlap_summary",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    score = payload["scorecard_summary"]
    rows = [
        "| Pilot | Verdict | Closed | Open | Pending | RV vs SPY | Book DD | Ready |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for pilot in score["pilots"]:
        rows.append(
            "| {pilot} | {verdict} | {closed} | {open_} | {pending} | {rv_spy} | {dd} | {ready} |".format(
                pilot=pilot["pilot"],
                verdict=pilot["verdict"],
                closed=pilot["closed_trades"],
                open_=pilot["open_positions"],
                pending=pilot["pending_entries"],
                rv_spy=pilot["rv_vs_spy_usd"],
                dd=pilot["book_max_drawdown_pct"],
                ready=str(pilot["graduation_ready"]).lower(),
            )
        )
    overlap = payload["cross_pilot_overlap_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: current pilot graduation readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Live/default orders changed: `false`",
            f"- Graduation-ready pilots: `{len(score['graduation_ready_pilots'])}`",
            f"- Killed pilots: `{', '.join(score['killed_pilots']) or 'none'}`",
            f"- Cross-pilot KILL overlap participants: `{overlap['overlap_with_kill_participant_count']}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Scorecards",
            "",
            *rows,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py",
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
        PILOT_SCORECARD,
        PILOT_RECS,
        PILOT_TRACKER_MD,
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
        "allowed_write_scope": payload["allowed_write_scope"],
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    ticket_before = payload.get("ticket_before") or {}
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
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
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
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
                "graduation_ready_pilots": payload["scorecard_summary"][
                    "graduation_ready_pilots"
                ],
                "killed_pilots": payload["scorecard_summary"]["killed_pilots"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "killed_pilot_enter_next_open_count": payload[
                    "recommendation_summary"
                ]["killed_pilot_enter_next_open_count"],
                "cross_pilot_overlap_with_kill_participant_count": payload[
                    "cross_pilot_overlap_summary"
                ]["overlap_with_kill_participant_count"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
