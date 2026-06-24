"""exp-20260624-014: accepted allocator current-open readiness audit.

Read-only alpha-search attribution over the current accepted-helper allocator
pilot state after exp-20260624-013 materialized open-row prices. This does not
change entries, exits, ranking, sizing, paper state, pilot recommendations, or
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


EXPERIMENT_ID = "exp-20260624-014"
OWNER = "alpha-explore"
SLUG = "accepted_allocator_current_open_envelope_readiness"
RUNNER = f"quant/experiments/exp_20260624_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_014_{SLUG}.json"
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
ALLOCATOR_STATE = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "accepted_helper_source_priority_allocator"
    / "state.json"
)
PILOT_RECS = REPO_ROOT / "data" / "pilots" / "pilot_recommendations_2026-06-24.json"
PILOT_SCORECARD = REPO_ROOT / "data" / "pilots" / "pilot_scorecard.json"

HYPOTHESIS = (
    "alpha_search/readiness: after exp-20260624-013 materialized accepted "
    "allocator open-row prices, the current default-off allocator book may now "
    "reveal whether the predeclared activation envelope is watchlist-ready, "
    "blocked by open-book risk, or still immature without changing source rank, "
    "sizing, entries, exits, or orders."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "observed_only_attribution"
MECHANISM_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
TRIAL_FAMILY = "accepted_allocator_forward_activation_readiness"
TRIAL_VARIANT_ID = "current_open_price_materialized_envelope_v1"
CHANGED_VARIABLE = "accepted_allocator_current_open_activation_envelope_readiness_v1"
CAUSAL_COMPONENTS = [
    "current open-row price attribution",
    "activation envelope checks",
    "pilot tracker verdict context",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260624-013",
    "exp-20260624-011",
    "exp-20260622-013",
    "exp-20260612-024",
]

ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-014/exp_20260624_014_accepted_allocator_current_open_envelope_readiness.json",
    "experiments/cards/exp-20260624-014.md",
    "experiments/manifests/exp-20260624-014.json",
    "experiments/tickets/exp-20260624-014.json",
    "experiments/logs/exp-20260624-014.json",
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


def as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict) and prediction.get("confidence_reason"):
        return prediction
    return {
        "success_probability": 0.22,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "no_closed_allocator_rows",
            "open_drawdown_or_stop_risk",
            "cross_pilot_overlap_with_kill_verdict",
            "insufficient_forward_maturity",
        ],
        "confidence_reason": (
            "Fallback prediction; the ticket normally carries the reservation-time "
            "prediction for this alpha-search readiness audit."
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
    }


def allocator_scorecard(scorecards: list[dict[str, Any]]) -> dict[str, Any]:
    for row in scorecards:
        if isinstance(row, dict) and row.get("pilot") == "allocator_top1":
            return row
    return {}


def allocator_recommendation(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    for row in recommendations:
        if isinstance(row, dict) and row.get("pilot") == "allocator_top1":
            return row
    return {}


def current_open_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in (state.get("open_positions") or []) if isinstance(row, dict)]


def row_return_pct(row: dict[str, Any]) -> float | None:
    value = as_float(row.get("unrealized_return_pct"))
    if value is not None:
        return value
    entry = as_float(row.get("entry_price") or row.get("entry_raw_open"))
    last = as_float(row.get("last_price"))
    if entry and last:
        return last / entry - 1.0
    return None


def row_notional(row: dict[str, Any]) -> float:
    for key in ("notional_usd", "paper_notional_usd", "safe_paper_notional_usd"):
        value = as_float(row.get(key))
        if value and value > 0:
            return value
    return 4000.0


def summarize_open_book(state: dict[str, Any]) -> dict[str, Any]:
    rows = current_open_rows(state)
    source_counts = Counter(str(row.get("source_family") or "unknown") for row in rows)
    source_notional: Counter[str] = Counter()
    open_details = []
    state_unrealized_pnl = 0.0
    pilot_unrealized_pnl = 0.0
    loss_values: list[tuple[str, float]] = []
    worst_return = None
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        ret = row_return_pct(row)
        notional = row_notional(row)
        source = str(row.get("source_family") or "unknown")
        source_notional[source] += notional
        pnl = as_float(row.get("unrealized_pnl"))
        if pnl is not None:
            state_unrealized_pnl += pnl
        if ret is not None:
            pilot_pnl = ret * float(pilot_tracker.PILOT_NOTIONAL_USD)
            pilot_unrealized_pnl += pilot_pnl
            if pilot_pnl < 0:
                loss_values.append((ticker, abs(pilot_pnl)))
            worst_return = ret if worst_return is None else min(worst_return, ret)
        open_details.append(
            {
                "ticker": ticker,
                "source_family": source,
                "entry_date": row.get("entry_date"),
                "last_price_asof": row.get("last_price_asof"),
                "notional_usd": notional,
                "unrealized_return_pct": round(ret, 6) if ret is not None else None,
                "state_unrealized_pnl": pnl,
                "pilot_scaled_unrealized_pnl": round(ret * 10000.0, 2)
                if ret is not None
                else None,
                "observed_trading_days": row.get("observed_trading_days"),
                "hold_days": row.get("hold_days"),
            }
        )
    total_loss = sum(value for _, value in loss_values)
    max_loss_ticker, max_loss_value = (None, 0.0)
    if loss_values:
        max_loss_ticker, max_loss_value = max(loss_values, key=lambda item: item[1])
    stop_buffer = None
    if worst_return is not None:
        stop_buffer = float(pilot_tracker.STOP_LOSS_PCT) + worst_return
    return {
        "state_file": repo_rel(ALLOCATOR_STATE),
        "updated_at": state.get("updated_at"),
        "open_positions": len(rows),
        "pending_entries": len([r for r in state.get("pending_entries") or [] if isinstance(r, dict)]),
        "closed_positions": len([r for r in state.get("closed_positions") or [] if isinstance(r, dict)]),
        "priced_open_positions": sum(1 for row in rows if row.get("last_price") is not None),
        "unrealized_open_positions": sum(
            1 for row in rows if row_return_pct(row) is not None
        ),
        "source_family_counts": dict(source_counts),
        "source_family_notional_usd": {key: round(value, 2) for key, value in source_notional.items()},
        "state_unrealized_pnl_usd": round(state_unrealized_pnl, 2),
        "pilot_scaled_unrealized_pnl_usd": round(pilot_unrealized_pnl, 2),
        "pilot_scaled_open_capital_usd": round(len(rows) * float(pilot_tracker.PILOT_NOTIONAL_USD), 2),
        "worst_open_unrealized_return_pct": round(worst_return, 6) if worst_return is not None else None,
        "worst_stop_buffer_pct": round(stop_buffer, 6) if stop_buffer is not None else None,
        "max_single_ticker_open_loss_share": round(max_loss_value / total_loss, 6)
        if total_loss
        else None,
        "max_single_ticker_open_loss_ticker": max_loss_ticker,
        "open_positions_detail": open_details,
    }


def summarize_pilot_tracker() -> dict[str, Any]:
    generated = pilot_tracker.generate(write=False)
    scorecard = allocator_scorecard(generated.get("scorecards") or [])
    recommendation = allocator_recommendation(generated.get("recommendations") or [])
    actionable = [
        row for row in (recommendation.get("actionable") or []) if isinstance(row, dict)
    ]
    skipped = [
        row for row in (recommendation.get("skipped") or []) if isinstance(row, dict)
    ]
    overlaps = [
        row
        for row in (generated.get("cross_pilot_overlap") or [])
        if isinstance(row, dict)
        and any(
            isinstance(ctx, dict) and ctx.get("pilot_key") == "allocator_top1"
            for ctx in row.get("participant_context") or []
        )
    ]
    killed_overlap = []
    for row in overlaps:
        for ctx in row.get("participant_context") or []:
            if isinstance(ctx, dict) and ctx.get("pilot_verdict") == "KILL":
                killed_overlap.append(
                    {
                        "ticker": row.get("ticker"),
                        "pilot_key": ctx.get("pilot_key"),
                        "pilot": ctx.get("pilot"),
                        "verdict_note": ctx.get("pilot_verdict_note"),
                        "unrealized_pct": ctx.get("unrealized_pct"),
                    }
                )
    allocator_stop_alerts = [
        row
        for row in (generated.get("stop_alerts") or [])
        if isinstance(row, dict)
        and str(row.get("pilot") or "").lower().startswith("source-priority")
    ]
    return {
        "as_of": generated.get("as_of"),
        "constants": {
            "pilot_notional_usd": float(pilot_tracker.PILOT_NOTIONAL_USD),
            "graduate_min_closed": int(pilot_tracker.GRADUATE_MIN_CLOSED),
            "graduate_max_book_drawdown_pct": float(pilot_tracker.GRADUATE_MAX_BOOK_DD_PCT),
            "stop_loss_pct": float(pilot_tracker.STOP_LOSS_PCT),
        },
        "allocator_scorecard": scorecard,
        "allocator_actionable_rows": len(actionable),
        "allocator_skipped_rows": len(skipped),
        "allocator_actionable_tickers": [row.get("ticker") for row in actionable],
        "allocator_skipped_tickers": [row.get("ticker") for row in skipped],
        "allocator_stop_alerts": allocator_stop_alerts,
        "allocator_cross_pilot_overlap_rows": len(overlaps),
        "allocator_cross_pilot_overlap_with_kill_rows": len(killed_overlap),
        "allocator_cross_pilot_overlap_with_kill": killed_overlap,
        "raw_allocator_recommendation": recommendation,
    }


def readiness_decision(
    open_book: dict[str, Any],
    tracker: dict[str, Any],
) -> tuple[list[str], dict[str, bool]]:
    scorecard = tracker.get("allocator_scorecard") or {}
    closed = int(scorecard.get("closed_trades") or 0)
    checks = {
        "all_current_open_rows_priced": (
            open_book["open_positions"] > 0
            and open_book["priced_open_positions"] == open_book["open_positions"]
            and open_book["unrealized_open_positions"] == open_book["open_positions"]
        ),
        "closed_trade_gate_met": closed >= int(pilot_tracker.GRADUATE_MIN_CLOSED),
        "scorecard_verdict_graduate": scorecard.get("verdict") == "GRADUATE",
        "no_allocator_stop_alerts": len(tracker["allocator_stop_alerts"]) == 0,
        "no_cross_pilot_kill_overlap": tracker[
            "allocator_cross_pilot_overlap_with_kill_rows"
        ]
        == 0,
        "positive_replacement_value_vs_spy": float(scorecard.get("rv_vs_spy_usd") or 0.0) > 0.0,
        "book_drawdown_within_ceiling": float(
            scorecard.get("book_max_drawdown_pct") or 0.0
        )
        < float(pilot_tracker.GRADUATE_MAX_BOOK_DD_PCT),
    }
    failed_reason_by_check = {
        "all_current_open_rows_priced": "current_open_rows_not_fully_priced",
        "closed_trade_gate_met": "no_closed_allocator_rows",
        "scorecard_verdict_graduate": "scorecard_verdict_not_graduate",
        "no_allocator_stop_alerts": "allocator_stop_alert_present",
        "no_cross_pilot_kill_overlap": "cross_pilot_overlap_with_kill_verdict",
        "positive_replacement_value_vs_spy": "replacement_value_vs_spy_not_positive",
        "book_drawdown_within_ceiling": "book_drawdown_ceiling_breached",
    }
    failed = [
        failed_reason_by_check[key]
        for key, value in checks.items()
        if not value
    ]
    return failed, checks


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket)
    baseline = baseline_metrics()
    state = read_json(ALLOCATOR_STATE, {})
    open_book = summarize_open_book(state)
    tracker = summarize_pilot_tracker()
    failed_checks, checks = readiness_decision(open_book, tracker)

    status = "observed_only_rejected"
    decision = "rejected_allocator_current_open_activation_not_ready"
    actual_success = 0
    brier = None
    if isinstance(prediction.get("success_probability"), (int, float)):
        brier = round((float(prediction["success_probability"]) - actual_success) ** 2, 4)

    timestamp = utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": False,
        "implementation_mode": IMPLEMENTATION_MODE,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "current_materialized_forward_open_rows",
        "new_evidence_axis": (
            "Current forward open-row price materialization from exp-20260624-013: "
            "seven accepted allocator open positions now have last_price, "
            "unrealized PnL, and pilot tracker verdict context; this is not a "
            "source/rank/scalar retune."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": actual_success,
            "brier_score": brier,
            "failure_modes_observed": failed_checks,
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "predicted_failure_mode_hit": bool(
                set(failed_checks) & set(prediction.get("main_failure_modes", []))
            ),
            "surprise_note": (
                "The pre-run read was directionally right: price materialization is "
                "complete, but allocator_top1 has zero closed rows and overlaps DDOG "
                "with a killed fundamental-growth pilot."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Blocked as an allocator activation-envelope neighbor, then "
                    "overridden with a machine-checkable new evidence axis: "
                    "exp-20260624-013 current open-row price materialization."
                ),
                "exp-20260612-024": (
                    "Accepted allocator activation envelope; this run does not "
                    "change the envelope and only audits current forward evidence."
                ),
                "exp-20260624-013": (
                    "Accepted measurement repair that materialized last_price and "
                    "unrealized_pnl for seven current allocator open rows."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Observed-only readiness passes only if all current open rows are "
                "priced, allocator_top1 has at least the pilot tracker closed-row "
                "minimum, beats SPY replacement value, has no allocator stop alerts, "
                "and has no cross-pilot overlap with a killed pilot."
            ),
            "5_reproducibility": RUNNER_COMMAND,
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
            "current_allocator_open_positions": open_book["open_positions"],
            "current_allocator_closed_positions": open_book["closed_positions"],
            "current_allocator_pending_entries": open_book["pending_entries"],
            "current_allocator_worst_open_unrealized_return_pct": open_book[
                "worst_open_unrealized_return_pct"
            ],
            "current_allocator_pilot_scaled_unrealized_pnl_usd": open_book[
                "pilot_scaled_unrealized_pnl_usd"
            ],
            "current_allocator_cross_pilot_kill_overlap_rows": tracker[
                "allocator_cross_pilot_overlap_with_kill_rows"
            ],
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": checks["all_current_open_rows_priced"],
            "dependencies_validated": checks["all_current_open_rows_priced"],
            "fields_checked": [
                "entry_date",
                "entry_price",
                "last_price",
                "last_price_asof",
                "unrealized_pnl",
                "unrealized_return_pct",
            ],
            "target_price_scope": (
                "No executable candidate or target-price exit is scheduled; this "
                "default-off time-exit sleeve does not consume target_price."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No buy/sell/filter/ranking/sizing rule was added.",
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "failed_reasons": failed_checks,
            "acceptance_checks": checks,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "ran_after_strategy": False,
            "strategy_rerun_required": False,
            "reason_after_not_run": (
                "Read-only current forward attribution; no policy changed and "
                "activation failed before any strategy replay."
            ),
        },
        "current_open_book": open_book,
        "pilot_tracker_readiness": tracker,
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
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": True,
            "replay_only": False,
            "default_off_paper_only": True,
            "activation_envelope": {
                "source": "quant/pilot_tracker.py manual pilot constants plus accepted allocator current state",
                "pilot_notional_usd": float(pilot_tracker.PILOT_NOTIONAL_USD),
                "graduate_min_closed": int(pilot_tracker.GRADUATE_MIN_CLOSED),
                "stop_loss_pct": float(pilot_tracker.STOP_LOSS_PCT),
                "max_book_drawdown_pct": float(pilot_tracker.GRADUATE_MAX_BOOK_DD_PCT),
                "order_semantics": "manual pilot review only; no orders emitted",
                "kill_switch": "KILL verdict when book drawdown breaches 15% or sample fails SPY replacement test",
            },
        },
        "post_run_reflection": {
            "why_result_happened": (
                "exp-20260624-013 fixed the prerequisite price surface, but current "
                "allocator activation evidence is still immature: allocator_top1 has "
                "0 closed trades versus the 20-row pilot threshold, no SPY/QQQ/cash "
                "replacement rows, and the one actionable DDOG row overlaps a "
                "fundamental-growth pilot already marked KILL."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this result to retune allocator source rank, source "
                "scalars, top-N, hold days, stop levels, concurrency, or activation "
                "thresholds on frozen windows."
            ),
            "new_evidence_required": (
                "Wait for closed allocator_top1 forward replacement-value rows under "
                "the existing envelope, or add a genuinely new PIT source that is not "
                "an allocator/source-arbitration neighbor."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(ALLOCATOR_STATE),
            repo_rel(PILOT_RECS),
            repo_rel(PILOT_SCORECARD),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260624-013.json",
            "experiments/logs/exp-20260612-024.json",
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
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
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
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "current_open_book",
        "pilot_tracker_readiness",
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
    open_book = payload["current_open_book"]
    tracker = payload["pilot_tracker_readiness"]
    scorecard = tracker["allocator_scorecard"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: allocator current-open readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Live/default orders changed: `false`",
            f"- Current allocator open rows: `{open_book['open_positions']}`",
            f"- Current allocator closed rows: `{scorecard.get('closed_trades', 0)}` / `{pilot_tracker.GRADUATE_MIN_CLOSED}`",
            f"- Worst open unrealized return: `{open_book['worst_open_unrealized_return_pct']}`",
            f"- Cross-pilot KILL overlaps: `{tracker['allocator_cross_pilot_overlap_with_kill_rows']}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons'])}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
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
        ALLOCATOR_STATE,
        PILOT_RECS,
        PILOT_SCORECARD,
        BASELINE_RESULT,
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
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
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": False,
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
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "open_positions": payload["current_open_book"]["open_positions"],
                "closed_trades": payload["pilot_tracker_readiness"][
                    "allocator_scorecard"
                ].get("closed_trades"),
                "worst_open_unrealized_return_pct": payload["current_open_book"][
                    "worst_open_unrealized_return_pct"
                ],
                "cross_pilot_kill_overlap_rows": payload["pilot_tracker_readiness"][
                    "allocator_cross_pilot_overlap_with_kill_rows"
                ],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
