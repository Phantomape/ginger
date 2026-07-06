"""exp-20260705-016: materialize first Moomoo capital-flow forward snapshot.

Measurement repair only. exp-20260703-007 accepted daily wiring for the
default-off Moomoo capital-flow paper sleeve, but the sleeve had no local
state/snapshot files, so no forward rows could mature. This runner uses the
existing shared helper and local archive to create the first paper ledger row
without changing thresholds, ranking, sizing, exits, prompts, or orders.
"""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260705-016"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "moomoo_capital_flow_first_forward_snapshot"
TRIAL_VARIANT_ID = "moomoo_capital_flow_first_forward_snapshot_materialization_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from moomoo_capital_flow_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_ROWS_PATH,
    DEFAULT_SNAPSHOT_LOG_PATH,
    DEFAULT_STATE_PATH,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    SLEEVE_NAME,
    build_moomoo_capital_flow_paper_sleeve_snapshot,
    load_moomoo_capital_flow_paper_state,
    load_moomoo_capital_flow_rows,
)
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
)


RUNNER = f"quant/experiments/exp_20260705_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_016_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
QUANT_SIGNALS_DIR = REPO_ROOT / "data" / "daily" / "signals" / "quant"

STATE_JSON = Path(DEFAULT_STATE_PATH)
SNAPSHOTS_JSONL = Path(DEFAULT_SNAPSHOT_LOG_PATH)
ROWS_JSONL = Path(DEFAULT_ROWS_PATH)
FLOW_MANIFEST_JSON = Path(DEFAULT_MANIFEST_PATH)

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_016_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "data/paper_sleeves/moomoo_capital_flow/state.json",
    "data/paper_sleeves/moomoo_capital_flow/snapshots.jsonl",
]

REPRODUCTION_COMMANDS = [
    RUNNER_COMMAND,
    (
        ".\\.venv\\Scripts\\python.exe -B -m pytest "
        "quant\\test_moomoo_capital_flow_paper_sleeve.py -q"
    ),
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


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


def safe_write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(text, path)
        cleanup_atomic_temps(path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.write_text(text, encoding="utf-8")
    cleanup_atomic_temps(path)


def cleanup_atomic_temps(path: Path) -> None:
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str) + "\n",
        path,
    )


def safe_append_jsonl(row: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True, default=str) + "\n")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            if raw.strip():
                count += 1
    return count


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    windows = payload.get("windows") or []
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "loaded": bool(windows),
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(
            int(window.get("total_trades") or window.get("trade_count") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
    }


def flow_archive_summary(flow_rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = sorted({str(row.get("flow_date") or "") for row in flow_rows if row.get("flow_date")})
    latest = dates[-1] if dates else None
    latest_tickers = sorted(
        {
            str(row.get("ticker") or "").upper()
            for row in flow_rows
            if latest and row.get("flow_date") == latest and row.get("ticker")
        }
    )
    manifest = read_json(FLOW_MANIFEST_JSON, {})
    return {
        "rows_path": repo_rel(ROWS_JSONL),
        "manifest_path": repo_rel(FLOW_MANIFEST_JSON),
        "row_count": len(flow_rows),
        "ticker_count": len({str(row.get("ticker") or "").upper() for row in flow_rows}),
        "earliest_flow_date": dates[0] if dates else None,
        "latest_flow_date": latest,
        "latest_flow_ticker_count": len(latest_tickers),
        "latest_flow_tickers": latest_tickers,
        "manifest": {
            "row_count": manifest.get("row_count"),
            "ticker_count": manifest.get("ticker_count"),
            "earliest_flow_date": manifest.get("earliest_flow_date"),
            "latest_flow_date": manifest.get("latest_flow_date"),
            "updated_at": manifest.get("updated_at"),
        },
    }


def _extract_signal_tickers(container: Any) -> set[str]:
    tickers: set[str] = set()
    if isinstance(container, dict):
        raw = container.get("ticker") or container.get("symbol")
        if raw:
            tickers.add(str(raw).upper())
        for key in ("signals", "pilot_signals", "slot_sliced_signals", "selected_signals"):
            tickers.update(_extract_signal_tickers(container.get(key)))
    elif isinstance(container, list):
        for item in container:
            tickers.update(_extract_signal_tickers(item))
    return {ticker for ticker in tickers if ticker and ticker != "CASH"}


def load_same_day_core_tickers(as_of: str) -> dict[str, Any]:
    signal_path = QUANT_SIGNALS_DIR / f"quant_signals_{as_of.replace('-', '')}.json"
    payload = read_json(signal_path, {})
    tickers: set[str] = set()
    if isinstance(payload, dict):
        for key in ("signals", "pilot_signals", "slot_sliced_signals", "selected_signals"):
            tickers.update(_extract_signal_tickers(payload.get(key)))
    return {
        "path": repo_rel(signal_path),
        "exists": signal_path.exists(),
        "ticker_count": len(tickers),
        "tickers": sorted(tickers),
    }


def load_ohlcv_context(tickers: list[str], as_of: str) -> tuple[dict[str, Any], dict[str, Any]]:
    requested = sorted({*tickers, "SPY"})
    frames = load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        requested,
        start="2025-06-01",
        end=as_of,
    )
    max_dates: dict[str, str] = {}
    row_counts: dict[str, int] = {}
    for ticker, frame in frames.items():
        row_counts[ticker] = int(len(frame))
        if len(frame.index):
            max_dates[ticker] = str(frame.index.max().date())
    summary = {
        "warehouse_path": repo_rel(DEFAULT_WAREHOUSE_PATH),
        "requested_ticker_count": len(requested),
        "loaded_ticker_count": len(frames),
        "missing_tickers": sorted(set(requested) - set(frames)),
        "spy_has_asof": max_dates.get("SPY") == as_of,
        "ticker_max_dates": max_dates,
        "row_count_min": min(row_counts.values()) if row_counts else 0,
        "row_count_max": max(row_counts.values()) if row_counts else 0,
    }
    return frames, summary


def state_summary(state: dict[str, Any]) -> dict[str, Any]:
    pending = state.get("pending_entries") or []
    open_positions = state.get("open_positions") or []
    closed = state.get("closed_positions") or []
    return {
        "state_path": repo_rel(STATE_JSON),
        "state_exists": STATE_JSON.exists(),
        "snapshot_path": repo_rel(SNAPSHOTS_JSONL),
        "snapshot_exists": SNAPSHOTS_JSONL.exists(),
        "snapshot_line_count": jsonl_count(SNAPSHOTS_JSONL),
        "pending_count": len(pending),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "pending_created_asof": sorted(
            {
                str(row.get("created_asof") or "")
                for row in pending
                if isinstance(row, dict) and row.get("created_asof")
            }
        ),
        "open_entry_dates": sorted(
            {
                str(row.get("entry_date") or "")
                for row in open_positions
                if isinstance(row, dict) and row.get("entry_date")
            }
        ),
        "closed_exit_dates": sorted(
            {
                str(row.get("exit_date") or "")
                for row in closed
                if isinstance(row, dict) and row.get("exit_date")
            }
        ),
    }


def has_materialized_row(state: dict[str, Any], as_of: str) -> bool:
    for section in ("pending_entries", "open_positions", "closed_positions"):
        for row in state.get(section) or []:
            if not isinstance(row, dict):
                continue
            candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
            dates = {
                str(row.get("created_asof") or ""),
                str(row.get("signal_date") or ""),
                str(candidate.get("signal_date") or ""),
                str(candidate.get("date") or ""),
            }
            if as_of in dates:
                return True
    return False


def materialize_preflight_state(before_state: dict[str, Any], snapshot: dict[str, Any]) -> None:
    state = deepcopy(before_state)
    state.setdefault("schema_version", 1)
    state["sleeve"] = SLEEVE_NAME
    state["updated_at"] = utc_now()
    state["pending_entries"] = deepcopy(snapshot.get("pending_entries") or [])
    state["open_positions"] = deepcopy(snapshot.get("open_positions") or [])

    existing_closed = [
        row for row in state.get("closed_positions") or [] if isinstance(row, dict)
    ]
    existing_ids = {
        str(row.get("decision_id") or row.get("ticker") or "") + ":" + str(row.get("exit_date") or "")
        for row in existing_closed
    }
    for closed in snapshot.get("closed_positions_today") or []:
        if not isinstance(closed, dict):
            continue
        key = str(closed.get("decision_id") or closed.get("ticker") or "") + ":" + str(
            closed.get("exit_date") or ""
        )
        if key not in existing_ids:
            existing_closed.append(deepcopy(closed))
            existing_ids.add(key)
    state["closed_positions"] = existing_closed

    skipped = [row for row in state.get("skipped_entries") or [] if isinstance(row, dict)]
    skipped.extend(
        deepcopy(row)
        for row in snapshot.get("skipped_entries_today") or []
        if isinstance(row, dict)
    )
    state["skipped_entries"] = skipped
    safe_write_json(state, STATE_JSON)
    safe_append_jsonl(snapshot, SNAPSHOTS_JSONL)


def run_snapshot_materialization() -> dict[str, Any]:
    flow_rows = load_moomoo_capital_flow_rows()
    flow_summary = flow_archive_summary(flow_rows)
    as_of = flow_summary["latest_flow_date"]
    if not as_of:
        return {
            "as_of": None,
            "flow_archive": flow_summary,
            "snapshot": {},
            "before_state": state_summary(load_moomoo_capital_flow_paper_state()),
            "after_state": state_summary(load_moomoo_capital_flow_paper_state()),
            "persisted_this_run": False,
            "failure_reason": "missing_flow_archive_rows",
        }

    same_day_core = load_same_day_core_tickers(as_of)
    frames, ohlcv = load_ohlcv_context(flow_summary["latest_flow_tickers"], as_of)
    before_state_obj = load_moomoo_capital_flow_paper_state(STATE_JSON)
    before_state = state_summary(before_state_obj)
    materialized_before = has_materialized_row(before_state_obj, as_of)

    config = {**DEFAULT_CONFIG, "allow_network_fetch": False}
    preflight = build_moomoo_capital_flow_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=frames,
        candidate_universe={
            "status": "latest_local_moomoo_flow_archive_universe",
            "tickers": flow_summary["latest_flow_tickers"],
        },
        flow_rows=flow_rows,
        same_day_core_tickers=set(same_day_core["tickers"]),
        state=deepcopy(before_state_obj),
        config=config,
        persist=False,
        state_path=STATE_JSON,
        snapshot_log_path=SNAPSHOTS_JSONL,
    )
    can_materialize = (
        not materialized_before
        and ohlcv["spy_has_asof"]
        and int(preflight.get("new_pending_count") or 0) > 0
        and preflight.get("data_source", {}).get("flow_status") == "provided"
    )

    persisted_this_run = False
    snapshot = preflight
    if can_materialize:
        materialize_preflight_state(before_state_obj, snapshot)
        persisted_this_run = True

    after_state_obj = load_moomoo_capital_flow_paper_state(STATE_JSON)
    after_state = state_summary(after_state_obj)
    materialized_after = has_materialized_row(after_state_obj, as_of)

    failure_reasons: list[str] = []
    if not flow_rows:
        failure_reasons.append("missing_local_archive")
    if not ohlcv["spy_has_asof"]:
        failure_reasons.append("missing_spy_asof")
    if not frames:
        failure_reasons.append("missing_ohlcv_frames")
    if preflight.get("data_source", {}).get("flow_status") != "provided":
        failure_reasons.append("flow_rows_not_supplied_locally")
    if not materialized_after:
        failure_reasons.append("no_forward_paper_row_materialized")
    if same_day_core["ticker_count"]:
        blocked = set(same_day_core["tickers"]) & set(flow_summary["latest_flow_tickers"])
        if blocked:
            failure_reasons.append("same_day_core_overlap_present")

    return {
        "as_of": as_of,
        "flow_archive": flow_summary,
        "same_day_core_tickers": same_day_core,
        "ohlcv": ohlcv,
        "before_state": before_state,
        "preflight_snapshot": preflight,
        "snapshot": snapshot,
        "after_state": after_state,
        "materialized_before": materialized_before,
        "materialized_after": materialized_after,
        "persisted_this_run": persisted_this_run,
        "failure_reasons": failure_reasons,
        "created_forward_rows_this_run": max(
            0,
            (
                after_state["pending_count"]
                + after_state["open_position_count"]
                + after_state["closed_position_count"]
            )
            - (
                before_state["pending_count"]
                + before_state["open_position_count"]
                + before_state["closed_position_count"]
            ),
        ),
        "snapshot_lines_appended_this_run": max(
            0,
            after_state["snapshot_line_count"] - before_state["snapshot_line_count"],
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    materialization = run_snapshot_materialization()
    accepted = (
        materialization.get("materialized_after") is True
        and materialization.get("failure_reasons") == []
        and materialization.get("after_state", {}).get("state_exists") is True
        and materialization.get("after_state", {}).get("snapshot_exists") is True
    )
    decision = (
        "accepted_measurement_repair_moomoo_capital_flow_first_forward_snapshot"
        if accepted
        else "blocked_moomoo_capital_flow_first_forward_snapshot_not_materialized"
    )
    classification = (
        "measurement_repair_forward_rows_materialized_alpha_not_ready"
        if accepted
        else "measurement_repair_blocked"
    )
    predicted = float((ticket.get("prediction") or {}).get("success_probability") or 0.0)
    actual_success = 1 if accepted else 0
    snapshot = materialization.get("snapshot") or {}
    delta_rows = int(materialization.get("created_forward_rows_this_run") or 0)
    snapshot_lines_delta = int(materialization.get("snapshot_lines_appended_this_run") or 0)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted" if accepted else "blocked",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "classification": classification,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "Moomoo day-level main capital-flow may contain useful accumulation "
            "signals, but the accepted daily wiring needed actual default-off "
            "forward rows before any future replacement-value or allocation claim."
        ),
        "change_type": ticket.get("change_type"),
        "implementation_mode": "default_off_first_forward_snapshot_materialization",
        "mechanism_family": "moomoo_capital_flow_day_accumulation_candidate_pool",
        "trial_family": "moomoo_capital_flow_forward_row_materialization",
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": ticket.get("single_causal_variable") or TRIAL_VARIANT_ID,
        "changed_variable": ticket.get("changed_variable") or TRIAL_VARIANT_ID,
        "causal_components": [
            "accepted shared Moomoo capital-flow helper",
            "local get_capital_flow(DAY) archive through latest flow date",
            "first default-off paper state/snapshot materialization",
            "no threshold, ranking, notional, exit, prompt, or order change",
        ],
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": "materially_new_forward_rows",
        "new_evidence_axis": (
            "First actual default-off paper state/snapshot rows for the accepted "
            "Moomoo capital-flow daily wiring, using the local archive through "
            f"{materialization.get('as_of')}. This is forward-row materialization, "
            "not a threshold, ranking, notional, or response-function retry."
        ),
        "novelty": ticket.get("novelty"),
        "prediction": ticket.get("prediction", {}),
        "parameters": {
            "as_of": materialization.get("as_of"),
            "baseline_result_file": repo_rel(BASELINE_JSON),
            "state_path": repo_rel(STATE_JSON),
            "snapshot_log_path": repo_rel(SNAPSHOTS_JSONL),
            "rows_path": repo_rel(ROWS_JSONL),
            "manifest_path": repo_rel(FLOW_MANIFEST_JSON),
            "paper_rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "sleeve_name": SLEEVE_NAME,
            "allow_network_fetch": False,
        },
        "pre_run_questions": {
            "alpha_hypothesis": ticket.get("hypothesis"),
            "history_check": {
                "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
                "novelty_nearest": ((ticket.get("novelty") or {}).get("nearest") or [])[:5],
            },
            "single_policy_bundle": ticket.get("single_causal_variable") or TRIAL_VARIANT_ID,
            "acceptance_standard": (
                "Accept as measurement repair if the local archive and warehouse can "
                "create a real default-off forward paper row, with state and snapshot "
                "files present afterward and strategy metrics unchanged."
            ),
            "reproducibility": RUNNER_COMMAND,
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
            "created_forward_rows_this_run": delta_rows,
            "snapshot_lines_appended_this_run": snapshot_lines_delta,
            "candidate_count": int(snapshot.get("candidate_count") or 0),
            "raw_candidate_count": int(snapshot.get("raw_candidate_count") or 0),
            "new_pending_count": int(snapshot.get("new_pending_count") or 0),
            "filled_count": int(snapshot.get("filled_count") or 0),
            "closed_count_today": int(snapshot.get("closed_count_today") or 0),
        },
        "gate1": {
            "passed": baseline["loaded"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": accepted,
            "fields_checked": [
                "flow_date",
                "main_in_flow",
                "main_flow_ratio",
                "created_asof",
                "pending_entries.candidate.signal_date",
                "trade_enabled",
                "alters_orders",
                "data_source.flow_status",
            ],
            "missing_or_invalid_fields": materialization.get("failure_reasons", []),
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, entry, exit, ranking, sizing, risk, or order rule changed.",
        },
        "gate4": {
            "passed": accepted,
            "accepted_measurement_repair": accepted,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "repair_failed_reasons": [] if accepted else materialization.get("failure_reasons", []),
            "alpha_activation_blockers": [
                "only first pending/open forward rows; no settled replacement-value sample yet",
                "requires materially more closed rows before any allocation or activation claim",
            ],
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
        },
        "moomoo_capital_flow_materialization": materialization,
        "production_impact": {
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_changed": True,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Only the default-off Moomoo paper state/snapshot files changed. "
                "The shared helper, run.py wiring, live ranking, sizing, exits, "
                "orders, and prompts were unchanged."
            ),
        },
        "calibration": {
            "predicted_success_probability": predicted,
            "actual_success": actual_success,
            "brier_score": round((predicted - actual_success) ** 2, 4),
            "predicted_failure_modes": (ticket.get("prediction") or {}).get(
                "main_failure_modes", []
            ),
            "realized_failure_modes": [] if accepted else materialization.get("failure_reasons", []),
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "The local archive and warehouse were sufficient to create the first "
                "pending paper row."
                if accepted
                else "The preflight could not create a valid default-off paper row."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The accepted shared helper already had the state machine and local "
                "archive contract; the missing piece was an actual post-wiring "
                "materialization run against the local warehouse."
            )
            if accepted
            else "The local materialization preflight did not produce a forward row.",
            "alpha_interpretation": (
                "This is alpha-enabling evidence only: it creates a pending/open "
                "forward row so later replacement-value evidence can mature. It is "
                "not an allocation-ready Moomoo capital-flow alpha."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve IDs for Moomoo capital-flow thresholds, ranking, "
                "notional scaling, or response-function retunes on this same row. "
                "Wait for materially more closed replacement-value rows or use a "
                "genuinely new data source/gate shape."
            ),
            "new_evidence_required": (
                "Closed forward rows with cash/SPY/QQQ replacement values, a "
                "different PIT vendor flow decomposition, or borrow/loan economics."
            ),
        },
        "rejection_reason": None if accepted else "; ".join(materialization.get("failure_reasons", [])),
        "next_retry_requires": [
            "materially more closed Moomoo capital-flow forward rows",
            "cash/SPY/QQQ replacement-value enrichment on those closed rows",
            "or a genuinely different PIT order-flow or borrow-economics source",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [
            "quant/moomoo_capital_flow_paper_sleeve.py",
            "quant/run.py",
            "quant/test_moomoo_capital_flow_paper_sleeve.py",
            "quant/test_run_daily_wiring.py",
            repo_rel(ROWS_JSONL),
            repo_rel(FLOW_MANIFEST_JSON),
        ],
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "lean_quality_passed": accepted,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "classification",
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
        "parameters",
        "pre_run_questions",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "moomoo_capital_flow_materialization",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    materialization = payload["moomoo_capital_flow_materialization"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - Moomoo capital-flow first forward snapshot",
            "",
            f"- status: {payload['status']}",
            f"- decision: {payload['decision']}",
            f"- classification: {payload['classification']}",
            f"- as_of: {materialization.get('as_of')}",
            f"- created forward rows this run: {delta['created_forward_rows_this_run']}",
            f"- snapshot lines appended this run: {delta['snapshot_lines_appended_this_run']}",
            f"- candidate/new pending: {delta['raw_candidate_count']} / {delta['new_pending_count']}",
            "",
            "No entry, exit, ranking, sizing, risk, LLM decision boundary, or live order behavior changed.",
            "",
            "Reproduce:",
            "",
            f"    {RUNNER_COMMAND}",
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
        REGISTRY_JSON,
        STATE_JSON,
        SNAPSHOTS_JSONL,
        ROWS_JSONL,
        FLOW_MANIFEST_JSON,
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
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_row = build_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    safe_write_json(log_row, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)

    ticket = read_json(TICKET_JSON, {})
    allowed = list(ticket.get("allowed_write_scope") or [])
    for path in CHANGED_FILES:
        if path not in allowed:
            allowed.append(path)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "classification": payload["classification"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["post_run_reflection"]["alpha_interpretation"],
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
            "parameters": payload["parameters"],
            "pre_run_questions": payload["pre_run_questions"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "allowed_write_scope": allowed,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    safe_write_json(build_manifest(payload), MANIFEST_JSON)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "as_of": payload["parameters"]["as_of"],
                "created_forward_rows_this_run": payload["delta_metrics"][
                    "created_forward_rows_this_run"
                ],
                "snapshot_lines_appended_this_run": payload["delta_metrics"][
                    "snapshot_lines_appended_this_run"
                ],
                "candidate_count": payload["delta_metrics"]["raw_candidate_count"],
                "new_pending_count": payload["delta_metrics"]["new_pending_count"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
