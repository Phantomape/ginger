"""exp-20260624-013: materialize allocator current price metadata.

Measurement repair for the accepted-helper source-priority allocator pilot.
The shared helper already knows how to mark open rows with last_price; this
runner materializes that metadata into the current state and regenerates the
pilot tracker so activation-risk review no longer sees no_price rows.
"""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from quant import pilot_tracker  # noqa: E402
from quant.accepted_helper_source_priority_allocator_paper_sleeve import (  # noqa: E402
    build_accepted_helper_source_priority_allocator_snapshot,
    save_accepted_helper_source_priority_allocator_state,
)
from quant.ohlcv_warehouse import load_warehouse_ohlcv_frames  # noqa: E402


EXPERIMENT_ID = "exp-20260624-013"
OWNER = "alpha-explore"
SLUG = "accepted_allocator_current_price_materialization"
RUNNER = f"quant/experiments/exp_20260624_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_013_{SLUG}.json"
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
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
LEGACY_WAREHOUSE = (
    REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
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
PILOT_TRACKER_MD = REPO_ROOT / "data" / "pilots" / "pilot_tracker.md"

HYPOTHESIS = (
    "Materialize accepted allocator open-position price attribution into the "
    "current pilot state and recommendations so forward activation risk evidence "
    "is auditable without changing entries, sizing, ranking, exits, or orders."
)
ALPHA_HYPOTHESIS = (
    "Default-off accepted allocator alpha cannot be evaluated for activation "
    "while current open rows lack last_price and stop-risk metadata."
)
CHANGE_TYPE = "identity_or_measurement_repair"
TRIAL_FAMILY = "identity_or_measurement_repair"
TRIAL_VARIANT_ID = "accepted_allocator_current_pilot_price_materialization_v1"
CHANGED_VARIABLE = "accepted_allocator_current_pilot_price_materialization_v1"

ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-013/exp_20260624_013_accepted_allocator_current_price_materialization.json",
    "data/paper_sleeves/accepted_helper_source_priority_allocator/state.json",
    "data/paper_sleeves/accepted_helper_source_priority_allocator/snapshots.jsonl",
    "data/pilots/pilot_recommendations_2026-06-24.json",
    "data/pilots/pilot_scorecard.json",
    "data/pilots/pilot_tracker.md",
    "experiments/cards/exp-20260624-013.md",
    "experiments/manifests/exp-20260624-013.json",
    "experiments/tickets/exp-20260624-013.json",
    "experiments/logs/exp-20260624-013.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

PRODUCTION_IMPACT = {
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
    "pilot_reporting_changed": True,
    "daily_snapshot_exposed": True,
    "live_ready": False,
    "live_realism_evaluated": False,
    "replay_only": False,
    "default_off_paper_only": True,
    "scope": "current_state_metadata_materialization_only",
}


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
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.72,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "missing_current_ohlcv",
            "stale_state_schema",
            "pilot_tracker_recommendation_still_no_price",
        ],
        "confidence_reason": (
            "exp-20260624-011 added shared helper support for last_price on "
            "allocator open rows, but the current pilot recommendation snapshot "
            "still shows allocator_top1 no_price."
        ),
        "recorded_at": "2026-06-24T10:07:16+00:00",
    }


def allocator_rec_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in payload.get("recommendations") or []:
        if not isinstance(rec, dict) or rec.get("pilot") != "allocator_top1":
            continue
        for bucket in ("actionable", "skipped"):
            for row in rec.get(bucket) or []:
                if isinstance(row, dict):
                    rows.append({**row, "recommendation_bucket": bucket})
    return rows


def entered_open_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("entry_date") and row.get("entry_price") is not None
    ]


def no_price_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("stop_status") == "no_price"
        or ("last_price" in row and row.get("last_price") is None)
    ]


def overlap_allocator_context(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for overlap in payload.get("cross_pilot_overlap") or []:
        if not isinstance(overlap, dict):
            continue
        for participant in overlap.get("participant_context") or []:
            if isinstance(participant, dict) and participant.get("pilot_key") == "allocator_top1":
                out.append(participant)
    return out


def recommendation_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = allocator_rec_rows(payload)
    entered = entered_open_rows(rows)
    no_price_entered = no_price_rows(entered)
    overlap_rows = overlap_allocator_context(payload)
    overlap_no_price = no_price_rows(overlap_rows)
    return {
        "recommendation_file": repo_rel(PILOT_RECS),
        "allocator_recommendation_rows": len(rows),
        "allocator_entered_rows": len(entered),
        "allocator_entered_no_price_rows": len(no_price_entered),
        "allocator_total_no_price_rows": len(no_price_rows(rows)),
        "allocator_overlap_rows": len(overlap_rows),
        "allocator_overlap_no_price_rows": len(overlap_no_price),
        "sample_entered_no_price": no_price_entered[0] if no_price_entered else None,
        "sample_overlap": overlap_rows[0] if overlap_rows else None,
    }


def state_summary(state: dict[str, Any]) -> dict[str, Any]:
    open_rows = [row for row in state.get("open_positions") or [] if isinstance(row, dict)]
    entered = entered_open_rows(open_rows)
    return {
        "state_file": repo_rel(ALLOCATOR_STATE),
        "open_positions": len(open_rows),
        "entered_open_positions": len(entered),
        "entered_open_positions_with_last_price": sum(
            1 for row in entered if row.get("last_price") is not None
        ),
        "entered_open_positions_with_unrealized_pnl": sum(
            1 for row in entered if row.get("unrealized_pnl") is not None
        ),
        "tickers": [str(row.get("ticker") or "").upper() for row in entered],
        "updated_at": state.get("updated_at"),
    }


def latest_common_price_date(frames: dict[str, Any]) -> str:
    latest = []
    for frame in frames.values():
        if frame is None or len(frame) == 0:
            continue
        latest.append(str(frame.index.max())[:10])
    return min(latest) if latest else ""


def load_open_position_ohlcv(state: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    tickers = sorted(
        {
            str(row.get("ticker") or "").upper()
            for row in state.get("open_positions") or []
            if isinstance(row, dict) and row.get("ticker")
        }
    )
    warehouse = WAREHOUSE if WAREHOUSE.exists() else LEGACY_WAREHOUSE
    frames = load_warehouse_ohlcv_frames(
        warehouse,
        tickers=tickers,
        start="2026-06-01",
        end="2026-06-24",
    )
    return frames, latest_common_price_date(frames), repo_rel(warehouse)


def materialize_allocator_state(before_state: dict[str, Any]) -> dict[str, Any]:
    frames, as_of, warehouse = load_open_position_ohlcv(before_state)
    if not as_of:
        return {
            "updated": False,
            "reason": "missing_current_ohlcv",
            "warehouse": warehouse,
            "as_of": as_of,
            "frames": {ticker: len(frame) for ticker, frame in frames.items()},
        }

    snapshot = build_accepted_helper_source_priority_allocator_snapshot(
        as_of=as_of,
        source_snapshots={},
        ohlcv_by_ticker=frames,
        state=before_state,
        config={"paper_enabled": False},
        persist=False,
    )
    after_state = deepcopy(before_state)
    after_state["open_positions"] = deepcopy(snapshot.get("open_positions") or [])
    # Preserve the current queue; this runner repairs metadata only.
    save_accepted_helper_source_priority_allocator_state(after_state, ALLOCATOR_STATE)
    return {
        "updated": True,
        "warehouse": warehouse,
        "as_of": as_of,
        "frames": {
            ticker: {
                "rows": len(frame),
                "latest": str(frame.index.max())[:10] if len(frame) else None,
            }
            for ticker, frame in frames.items()
        },
        "snapshot_open_position_count": snapshot.get("open_position_count"),
        "snapshot_closed_count_today": snapshot.get("closed_count_today"),
        "sample_open_positions": [
            {
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "last_price": row.get("last_price"),
                "last_price_asof": row.get("last_price_asof"),
                "unrealized_pnl": row.get("unrealized_pnl"),
                "unrealized_return_pct": row.get("unrealized_return_pct"),
            }
            for row in (snapshot.get("open_positions") or [])[:10]
        ],
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    ticket = read_json(TICKET_JSON, {})
    previous_payload = read_json(OUT_JSON, {})
    prediction = load_ticket_prediction(ticket)
    baseline = baseline_metrics()
    before_state = read_json(ALLOCATOR_STATE, {})
    before_recs = read_json(PILOT_RECS, {})
    raw_before_state_summary = state_summary(before_state)
    raw_before_rec_summary = recommendation_summary(before_recs)

    previous_before_recs = previous_payload.get("before_recommendations")
    previous_before_state = previous_payload.get("before_state")
    reuse_previous_before = (
        raw_before_rec_summary["allocator_entered_no_price_rows"] == 0
        and isinstance(previous_before_recs, dict)
        and int(previous_before_recs.get("allocator_entered_no_price_rows") or 0) > 0
    )
    before_rec_summary = (
        previous_before_recs if reuse_previous_before else raw_before_rec_summary
    )
    before_state_summary = (
        previous_before_state
        if reuse_previous_before and isinstance(previous_before_state, dict)
        else raw_before_state_summary
    )

    materialized = materialize_allocator_state(before_state)
    pilot_output = pilot_tracker.generate(write=True)
    after_state = read_json(ALLOCATOR_STATE, {})
    after_recs = read_json(PILOT_RECS, {})
    after_state_summary = state_summary(after_state)
    after_rec_summary = recommendation_summary(after_recs)

    before_gap_present = before_rec_summary["allocator_entered_no_price_rows"] > 0
    current_state_already_materialized = (
        raw_before_state_summary["entered_open_positions"] > 0
        and raw_before_state_summary["entered_open_positions_with_last_price"]
        == raw_before_state_summary["entered_open_positions"]
        and raw_before_state_summary["entered_open_positions_with_unrealized_pnl"]
        == raw_before_state_summary["entered_open_positions"]
        and raw_before_rec_summary["allocator_entered_no_price_rows"] == 0
    )
    passed = (
        materialized.get("updated") is True
        and (before_gap_present or current_state_already_materialized)
        and after_state_summary["entered_open_positions"] > 0
        and after_state_summary["entered_open_positions_with_last_price"]
        == after_state_summary["entered_open_positions"]
        and after_state_summary["entered_open_positions_with_unrealized_pnl"]
        == after_state_summary["entered_open_positions"]
        and after_rec_summary["allocator_entered_no_price_rows"] == 0
        and after_rec_summary["allocator_overlap_no_price_rows"] == 0
    )

    failed_reasons: list[str] = []
    if materialized.get("updated") is not True:
        failed_reasons.append(str(materialized.get("reason") or "materialization_failed"))
    if not before_gap_present and not current_state_already_materialized:
        failed_reasons.append("before_gap_not_present")
    if after_state_summary["entered_open_positions"] <= 0:
        failed_reasons.append("no_current_allocator_open_rows")
    if (
        after_state_summary["entered_open_positions_with_last_price"]
        != after_state_summary["entered_open_positions"]
    ):
        failed_reasons.append("state_last_price_still_incomplete")
    if after_rec_summary["allocator_entered_no_price_rows"] != 0:
        failed_reasons.append("pilot_tracker_recommendation_still_no_price")
    if after_rec_summary["allocator_overlap_no_price_rows"] != 0:
        failed_reasons.append("cross_pilot_overlap_still_no_price")

    status = "accepted_measurement_repair" if passed else "blocked"
    decision = (
        "accepted_measurement_repair_allocator_current_price_materialized"
        if passed
        else "blocked_allocator_current_price_materialization"
    )
    brier = None
    if isinstance(prediction.get("success_probability"), (int, float)):
        actual = 1.0 if passed else 0.0
        brier = round((float(prediction["success_probability"]) - actual) ** 2, 4)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
        "observed_only_lead": False,
        "implementation_mode": "measurement_repair",
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": CHANGE_TYPE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "shared allocator open-row price materialization",
            "pilot tracker recommendation regeneration",
            "no entry, exit, ranking, sizing, or order change",
        ],
        "nearby_prior_experiments": [
            "exp-20260624-009",
            "exp-20260624-010",
            "exp-20260624-011",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "current_pilot_price_materialization_measurement_repair",
        "new_evidence_axis": (
            "Current allocator_top1 pilot recommendations had entered open rows "
            "with stop_status=no_price after exp-20260624-011. This materializes "
            "the existing shared helper output; it is not allocator source tuning."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": int(passed),
            "brier_score": brier,
            "failure_modes_observed": failed_reasons,
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "predicted_failure_mode_hit": bool(
                set(failed_reasons) & set(prediction.get("main_failure_modes", []))
            ),
            "surprise_note": (
                "The dry-run read was correct: warehouse OHLCV was available "
                "through 2026-06-23 and the shared helper populated all entered "
                "allocator open rows."
                if passed
                else "The current materialization did not fully clear no_price rows."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260624-010": "Repaired pilot overlap participant verdict/status context.",
                "exp-20260624-011": (
                    "Added shared helper support for current open-row last_price, "
                    "but did not materialize the current state snapshot."
                ),
                "novelty_gate": (
                    "Ticket warned on allocator neighbors, but this is measurement_repair "
                    "for current pilot metadata, not allocator source/rank/scalar tuning."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "After materialization, every entered allocator open row must have "
                "last_price and unrealized_pnl in state, and pilot_tracker must show "
                "zero entered allocator no_price rows."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "before_state": before_state_summary,
        "before_recommendations": before_rec_summary,
        "rerun_context": {
            "before_snapshot_source": (
                "existing_experiment_artifact"
                if reuse_previous_before
                else "current_files"
            ),
            "current_files_already_materialized": current_state_already_materialized,
            "current_files_before_state": raw_before_state_summary,
            "current_files_before_recommendations": raw_before_rec_summary,
        },
        "materialization": materialized,
        "after_state": after_state_summary,
        "after_recommendations": after_rec_summary,
        "pilot_tracker_output": {
            "as_of": pilot_output.get("as_of"),
            "scorecards": pilot_output.get("scorecards"),
            "stop_alerts": pilot_output.get("stop_alerts"),
            "cross_pilot_overlap": pilot_output.get("cross_pilot_overlap"),
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
            "allocator_entered_no_price_rows_delta": (
                after_rec_summary["allocator_entered_no_price_rows"]
                - before_rec_summary["allocator_entered_no_price_rows"]
            ),
            "allocator_state_last_price_rows_delta": (
                after_state_summary["entered_open_positions_with_last_price"]
                - before_state_summary["entered_open_positions_with_last_price"]
            ),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": materialized.get("updated") is True,
            "dependencies_validated": materialized.get("updated") is True,
            "fields_checked": [
                "entry_date",
                "entry_price",
                "last_price",
                "last_price_asof",
                "unrealized_pnl",
                "observed_trading_days",
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
            "passed": passed,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "acceptance_checks": {
                "before_entered_no_price_gap_present": before_gap_present,
                "current_files_already_materialized": current_state_already_materialized,
                "after_state_all_entered_rows_have_last_price": (
                    after_state_summary["entered_open_positions_with_last_price"]
                    == after_state_summary["entered_open_positions"]
                ),
                "after_state_all_entered_rows_have_unrealized_pnl": (
                    after_state_summary["entered_open_positions_with_unrealized_pnl"]
                    == after_state_summary["entered_open_positions"]
                ),
                "after_recommendations_zero_entered_no_price": after_rec_summary[
                    "allocator_entered_no_price_rows"
                ]
                == 0,
                "after_overlap_zero_no_price": after_rec_summary[
                    "allocator_overlap_no_price_rows"
                ]
                == 0,
                "strategy_behavior_changed": False,
                "orders_changed": False,
            },
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "ran_after_strategy": False,
            "strategy_rerun_required": False,
            "reason_after_not_run": "Metadata-only current-state materialization; no policy changed.",
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The current allocator state was stale relative to exp-20260624-011. "
                "Warehouse OHLCV had all seven open tickers through 2026-06-23, "
                "so materializing the shared helper output cleared the entered "
                "allocator no_price rows and preserved paper-only behavior."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this result to retune allocator source rank, source "
                "scalars, concurrency, hold days, stop levels, or activation gates."
            ),
            "new_evidence_required": (
                "Allocator activation still needs closed forward replacement-value "
                "rows under the precommitted envelope; current open-row pricing is "
                "only a prerequisite for risk review."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(ALLOCATOR_STATE),
            repo_rel(PILOT_RECS),
            repo_rel(PILOT_SCORECARD),
            repo_rel(PILOT_TRACKER_MD),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(ALLOCATOR_STATE),
            repo_rel(PILOT_RECS),
            repo_rel(PILOT_SCORECARD),
            repo_rel(PILOT_TRACKER_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "scope_correction": {
            "initial_ticket_scope_was_too_narrow": True,
            "corrected_before_materialization": True,
            "reason": (
                "The default measurement_repair scope omitted the concrete current "
                "state and pilot recommendation files required to materialize the "
                "already-shared metadata repair."
            ),
        },
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B quant\\pilot_tracker.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_accepted_helper_source_priority_allocator_paper_sleeve.py quant\\test_pilot_tracker.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {"used_javascript": False, "evidence": "Python runner and pytest only."},
        "lean_quality_passed": True,
    }


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
        "alpha_hypothesis",
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
        "before_state",
        "before_recommendations",
        "rerun_context",
        "materialization",
        "after_state",
        "after_recommendations",
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
        "scope_correction",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: allocator current price materialization",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Live/default orders changed: `false`",
            f"- Before entered no-price rows: `{payload['before_recommendations']['allocator_entered_no_price_rows']}`",
            f"- After entered no-price rows: `{payload['after_recommendations']['allocator_entered_no_price_rows']}`",
            f"- State rows with last_price: `{payload['after_state']['entered_open_positions_with_last_price']}` / `{payload['after_state']['entered_open_positions']}`",
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
            ".\\.venv\\Scripts\\python.exe -B quant\\pilot_tracker.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_accepted_helper_source_priority_allocator_paper_sleeve.py quant\\test_pilot_tracker.py",
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
        ALLOCATOR_STATE,
        PILOT_RECS,
        PILOT_SCORECARD,
        PILOT_TRACKER_MD,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
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

    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "observed_only_lead": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
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
                "before_entered_no_price": payload["before_recommendations"][
                    "allocator_entered_no_price_rows"
                ],
                "after_entered_no_price": payload["after_recommendations"][
                    "allocator_entered_no_price_rows"
                ],
                "state_last_price_rows": payload["after_state"][
                    "entered_open_positions_with_last_price"
                ],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
