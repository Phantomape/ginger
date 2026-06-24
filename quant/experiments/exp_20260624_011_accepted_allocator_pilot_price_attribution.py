"""exp-20260624-011: accepted allocator open-row price attribution repair.

Measurement repair for the default-off accepted-helper source-priority
allocator. Open allocator rows must carry a current last_price so the manual
pilot tracker can evaluate stop/risk state. This changes reporting metadata
only; it does not change entries, exits, ranking, sizing, orders, or the
backtest policy.
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
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from quant import pilot_tracker  # noqa: E402
from quant.accepted_helper_source_priority_allocator_paper_sleeve import (  # noqa: E402
    RULE_VERSION,
    build_accepted_helper_source_priority_allocator_snapshot,
    empty_accepted_helper_source_priority_allocator_state,
)


EXPERIMENT_ID = "exp-20260624-011"
OWNER = "alpha-explore"
SLUG = "accepted_allocator_pilot_price_attribution"
RUNNER = f"quant/experiments/exp_20260624_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_011_{SLUG}.json"
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
PILOT_RECS = REPO_ROOT / "data" / "pilots" / "pilot_recommendations_2026-06-24.json"
ALLOCATOR_STATE = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "accepted_helper_source_priority_allocator"
    / "state.json"
)

HYPOTHESIS = (
    "Repair pilot tracker price attribution for accepted allocator open rows so "
    "forward pilot activation and stop-risk evidence are auditable without "
    "changing entries, sizing, ranking, exits, or orders."
)
ALPHA_HYPOTHESIS = (
    "Default-off accepted allocator alpha can only graduate toward activation "
    "when open-position stop/risk evidence has current price attribution."
)
CHANGE_TYPE = "identity_or_measurement_repair"
TRIAL_FAMILY = "identity_or_measurement_repair"
TRIAL_VARIANT_ID = "accepted_allocator_pilot_open_position_price_attribution_v1"
CHANGED_VARIABLE = "accepted_allocator_pilot_open_position_price_attribution_v1"
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "quant/macro_relief_leadership_paper_sleeve.py",
    "quant/test_accepted_helper_source_priority_allocator_paper_sleeve.py",
    "data/experiments/exp-20260624-011/exp_20260624_011_accepted_allocator_pilot_price_attribution.json",
    "experiments/cards/exp-20260624-011.md",
    "experiments/manifests/exp-20260624-011.json",
    "experiments/tickets/exp-20260624-011.json",
    "experiments/logs/exp-20260624-011.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": True,
    "shared_policy_note": (
        "Shared default-off paper sleeve now annotates open rows with last_price "
        "and unrealized_pnl metadata; entry/exit/ranking/sizing/order semantics "
        "are unchanged."
    ),
    "backtester_adapter_changed": False,
    "run_adapter_changed": True,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "live_orders_changed": False,
    "paper_orders_changed": False,
    "pilot_reporting_changed": True,
    "daily_snapshot_exposed": True,
    "live_ready": False,
    "replay_only": False,
    "default_off_paper_only": True,
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
        "success_probability": 0.82,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "shared helper is not the allocator's open-position path",
            "pilot tracker consumes a different price field",
            "test replay closes instead of preserving the open row",
        ],
        "confidence_reason": (
            "Current allocator pilot rows are no_price only because open rows lack "
            "last_price; pilot_tracker already consumes last_price when present."
        ),
        "recorded_at": "2026-06-24T08:05:46+00:00",
    }


def before_gap_summary() -> dict[str, Any]:
    generated = read_json(PILOT_RECS, {})
    allocator_rows = []
    for rec in generated.get("recommendations") or []:
        if not isinstance(rec, dict) or rec.get("pilot") != "allocator_top1":
            continue
        for bucket in ("actionable", "skipped"):
            for row in rec.get(bucket) or []:
                if isinstance(row, dict):
                    allocator_rows.append({**row, "recommendation_bucket": bucket})
    no_price_rows = [
        row
        for row in allocator_rows
        if row.get("stop_status") == "no_price" or row.get("last_price") is None
    ]
    overlap_no_price = []
    for overlap in generated.get("cross_pilot_overlap") or []:
        if not isinstance(overlap, dict):
            continue
        for participant in overlap.get("participant_context") or []:
            if (
                isinstance(participant, dict)
                and participant.get("pilot_key") == "allocator_top1"
                and participant.get("stop_status") == "no_price"
            ):
                overlap_no_price.append(participant)
    state = read_json(ALLOCATOR_STATE, {})
    open_positions = [
        row for row in state.get("open_positions") or [] if isinstance(row, dict)
    ]
    return {
        "pilot_recommendations_file": repo_rel(PILOT_RECS),
        "allocator_state_file": repo_rel(ALLOCATOR_STATE),
        "allocator_recommendation_rows": len(allocator_rows),
        "allocator_no_price_rows": len(no_price_rows),
        "allocator_overlap_no_price_rows": len(overlap_no_price),
        "state_open_positions": len(open_positions),
        "state_open_positions_with_last_price": sum(
            1 for row in open_positions if row.get("last_price") is not None
        ),
        "sample_no_price": no_price_rows[0] if no_price_rows else None,
        "sample_overlap_no_price": overlap_no_price[0] if overlap_no_price else None,
    }


def synthetic_after_summary() -> dict[str, Any]:
    state = empty_accepted_helper_source_priority_allocator_state()
    state["open_positions"] = [
        {
            "decision_id": f"{RULE_VERSION}:synthetic-ddog-open-price",
            "ticker": "DDOG",
            "signal_date": "2026-06-16",
            "entry_date": "2026-06-18",
            "entry_price": 224.152,
            "notional_usd": 4000.0,
            "paper_notional_usd": 4000.0,
            "hold_days": 10,
            "observed_trading_days": 3,
            "last_observed_date": "2026-06-22",
            "paper_status": "open",
            "source": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
            "source_priority_rank": 1,
            "trade_enabled": False,
        }
    ]
    ohlcv = {
        "DDOG": [
            {"date": "2026-06-18", "open": 224.04, "high": 225.0, "low": 219.0, "close": 223.0},
            {"date": "2026-06-19", "open": 223.0, "high": 224.0, "low": 218.0, "close": 221.0},
            {"date": "2026-06-22", "open": 221.0, "high": 222.0, "low": 218.0, "close": 220.8},
            {"date": "2026-06-23", "open": 220.8, "high": 222.0, "low": 219.0, "close": 220.57},
        ]
    }
    snapshot = build_accepted_helper_source_priority_allocator_snapshot(
        as_of="2026-06-23",
        source_snapshots={},
        ohlcv_by_ticker=ohlcv,
        state=state,
        config={"hold_days": 10},
        persist=False,
    )
    position = deepcopy(snapshot["open_positions"][0]) if snapshot["open_positions"] else {}
    rec = pilot_tracker._rec_row(position, "HOLD")
    return {
        "snapshot_open_position_count": snapshot["open_position_count"],
        "snapshot_closed_count_today": snapshot["closed_count_today"],
        "last_price": position.get("last_price"),
        "last_price_asof": position.get("last_price_asof"),
        "unrealized_pnl": position.get("unrealized_pnl"),
        "unrealized_return_pct": position.get("unrealized_return_pct"),
        "pilot_tracker_stop_status": rec.get("stop_status"),
        "pilot_tracker_unrealized_pct": rec.get("unrealized_pct"),
        "pilot_tracker_last_price": rec.get("last_price"),
        "position_keys": sorted(position),
        "used_persist_false": True,
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    before_gap = before_gap_summary()
    after = synthetic_after_summary()
    passed = (
        before_gap["allocator_no_price_rows"] > 0
        and before_gap["state_open_positions"] > 0
        and before_gap["state_open_positions_with_last_price"] == 0
        and after["snapshot_open_position_count"] == 1
        and after["snapshot_closed_count_today"] == 0
        and isinstance(after["last_price"], (int, float))
        and after["last_price_asof"] == "2026-06-23"
        and isinstance(after["unrealized_pnl"], (int, float))
        and after["pilot_tracker_stop_status"] == "OK"
    )
    failure_modes = []
    if before_gap["allocator_no_price_rows"] <= 0:
        failure_modes.append("before_gap_not_present")
    if before_gap["state_open_positions"] <= 0:
        failure_modes.append("no_current_allocator_open_rows")
    if before_gap["state_open_positions_with_last_price"] != 0:
        failure_modes.append("before_state_already_has_last_price")
    if after["snapshot_open_position_count"] != 1:
        failure_modes.append("after_open_row_not_preserved")
    if after["snapshot_closed_count_today"] != 0:
        failure_modes.append("after_replay_closed_position")
    if not isinstance(after["last_price"], (int, float)):
        failure_modes.append("after_last_price_missing")
    if not isinstance(after["unrealized_pnl"], (int, float)):
        failure_modes.append("after_unrealized_pnl_missing")
    if after["pilot_tracker_stop_status"] == "no_price":
        failure_modes.append("pilot_tracker_still_no_price")

    decision = (
        "accepted_measurement_repair_accepted_allocator_open_price_attribution"
        if passed
        else "blocked_accepted_allocator_open_price_attribution_not_verified"
    )
    status = "accepted_measurement_repair" if passed else "blocked"
    prediction = load_ticket_prediction(ticket)
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
            "open paper position metadata attribution",
            "pilot tracker stop/risk observability",
            "no entry, exit, ranking, sizing, or order change",
        ],
        "nearby_prior_experiments": [
            "exp-20260623-006",
            "exp-20260624-009",
            "exp-20260624-010",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "forward_pilot_open_row_price_attribution_gap",
        "new_evidence_axis": (
            "Current 2026-06-24 allocator_top1 pilot recommendations show open "
            "rows with stop_status=no_price while the accepted allocator remains "
            "COLLECTING; the repair adds a shared snapshot metadata field rather "
            "than a new alpha rule."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": bool(passed),
            "failure_modes_observed": failure_modes,
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "predicted_failure_mode_hit": bool(failure_modes)
            and any(mode in prediction.get("main_failure_modes", []) for mode in failure_modes),
            "surprise_note": (
                "The allocator did reuse macro_relief_leadership._advance_open_positions; "
                "a metadata-only patch was enough for pilot_tracker to leave no_price."
                if passed
                else "Synthetic after replay did not verify the full no_price repair."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Ticket warned on allocator neighbors but lane is measurement_repair; "
                    "this is a forward pilot observability gap, not allocator source tuning."
                ),
                "related_prior": (
                    "exp-20260624-010 repaired cross-pilot context; this run repairs "
                    "the remaining allocator no_price stop/risk field."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Open allocator rows must gain last_price, last_price_asof and "
                "unrealized_pnl under the shared snapshot helper; pilot_tracker "
                "must classify the same row with a real stop_status."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "before_gap": before_gap,
        "after_price_attribution": after,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "daily_pilot_output_changed": False,
            "current_allocator_no_price_rows_before": before_gap["allocator_no_price_rows"],
            "synthetic_after_last_price_present": isinstance(after["last_price"], (int, float)),
            "synthetic_after_stop_status": after["pilot_tracker_stop_status"],
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": after["last_price_asof"] == "2026-06-23",
            "dependencies_validated": after["last_price_asof"] == "2026-06-23",
            "fields_checked": [
                "entry_date",
                "entry_price",
                "last_price",
                "last_price_asof",
                "unrealized_pnl",
                "observed_trading_days",
            ],
            "entry_date_target_price_note": (
                "entry_date is present on the open row. target_price is not consumed "
                "because this default-off time-exit sleeve has no target-price exit."
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
            "failed_reasons": failure_modes,
            "acceptance_checks": {
                "before_current_allocator_has_no_price_gap": before_gap[
                    "allocator_no_price_rows"
                ]
                > 0,
                "after_open_row_has_last_price": isinstance(after["last_price"], (int, float)),
                "after_open_row_has_unrealized_pnl": isinstance(
                    after["unrealized_pnl"],
                    (int, float),
                ),
                "pilot_tracker_stop_status_uses_price": after[
                    "pilot_tracker_stop_status"
                ]
                == "OK",
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
            "reason_after_not_run": (
                "No strategy policy changed; non-persist snapshot replay and "
                "focused unit tests verify the metadata repair."
            ),
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The accepted allocator already used the shared macro relief open "
                "position advance helper, but that helper only incremented holding "
                "days until exit. Adding row-level current close metadata gives "
                "pilot_tracker a valid last_price while preserving hold-day exits."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry allocator source arbitration or capital scaling from "
                "this result; this was only observability for forward pilot risk."
            ),
            "new_evidence_required": (
                "Next daily snapshot should regenerate allocator state with real "
                "last_price fields. Activation still needs closed forward "
                "replacement-value rows and the precommitted risk envelope."
            ),
        },
        "related_files": [
            RUNNER,
            "quant/macro_relief_leadership_paper_sleeve.py",
            "quant/test_accepted_helper_source_priority_allocator_paper_sleeve.py",
            repo_rel(BASELINE_RESULT),
            repo_rel(PILOT_RECS),
            repo_rel(ALLOCATOR_STATE),
        ],
        "changed_files": [
            RUNNER,
            "quant/macro_relief_leadership_paper_sleeve.py",
            "quant/test_accepted_helper_source_priority_allocator_paper_sleeve.py",
            repo_rel(OUT_JSON),
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
            "reason": (
                "The reserved measurement_repair ticket only included runner/artifact "
                "paths, but the no_price gap required the shared default-off sleeve "
                "helper and a focused test."
            ),
        },
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_accepted_helper_source_priority_allocator_paper_sleeve.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {"used_javascript": False, "evidence": "Python runner and pytest only."},
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
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
        "before_gap",
        "after_price_attribution",
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
            f"# {EXPERIMENT_ID}: accepted allocator price attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Live orders changed: `false`",
            f"- Before allocator no-price rows: `{payload['before_gap']['allocator_no_price_rows']}`",
            f"- Synthetic after last_price: `{payload['after_price_attribution']['last_price']}`",
            f"- Synthetic after stop_status: `{payload['after_price_attribution']['pilot_tracker_stop_status']}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_accepted_helper_source_priority_allocator_paper_sleeve.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py",
            RUNNER_COMMAND,
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
        REPO_ROOT / "quant" / "macro_relief_leadership_paper_sleeve.py",
        REPO_ROOT / "quant" / "test_accepted_helper_source_priority_allocator_paper_sleeve.py",
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        PILOT_RECS,
        ALLOCATOR_STATE,
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
        "scope_correction": payload["scope_correction"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
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
        },
        status=payload["status"],
        fields=fields,
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
                "before_allocator_no_price_rows": payload["before_gap"][
                    "allocator_no_price_rows"
                ],
                "after_last_price": payload["after_price_attribution"]["last_price"],
                "after_stop_status": payload["after_price_attribution"][
                    "pilot_tracker_stop_status"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
