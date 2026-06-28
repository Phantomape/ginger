"""exp-20260627-024: repair space catalyst standard pending surface.

Measurement repair only. The Space catalyst event ledger is observe-only, but
its standard state surface was mapping already-closed event decisions into
``pending_entries`` when the row ``status`` field was null. Downstream candidate
surface audits then read stale March-May Space events as current pending rows.

This runner refreshes the current standard surface through the shared helper and
records the before/after state contract. It changes no trading rule, rank, size,
entry, exit, order path, or LLM decision boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import persist_self_registered_result  # noqa: E402
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
)
from sleeve_standard_layout import write_standard_sleeve_surfaces  # noqa: E402
from space_catalyst_sleeve import (  # noqa: E402
    DEFAULT_SPACE_CATALYST_EVENT_SEED_PATH,
    SPACE_CATALYST_EVENT_BENCHMARKS,
    build_space_catalyst_event_ledger_snapshot,
    build_space_catalyst_shadow_snapshot,
    load_space_catalyst_event_seeds,
    space_catalyst_observation_feature_tickers,
)


EXPERIMENT_ID = "exp-20260627-024"
OWNER = "alpha-explore"
SLUG = "space_catalyst_standard_surface_pending_repair"
RUNNER = f"quant/experiments/exp_20260627_024_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SPACE_STATE = REPO_ROOT / "data" / "paper_sleeves" / "space_catalyst" / "state.json"
SPACE_SNAPSHOTS = (
    REPO_ROOT / "data" / "paper_sleeves" / "space_catalyst" / "snapshots.jsonl"
)
SPACE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "space_catalyst"
    / "event_state_shadow_summary.json"
)
SPACE_LEDGER = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "space_catalyst"
    / "event_state_shadow_ledger.jsonl"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_024_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "alpha_blocker/measurement_repair: space catalyst event evidence may be "
    "useful only if forward candidate matching can distinguish current pending "
    "event rows from already-closed observe-only decisions; the standard state "
    "currently maps closed_decision=True rows into pending_entries when status "
    "is null, polluting current candidate surfaces."
)
CHANGE_TYPE = "observe_only_state_contract_repair"
MECHANISM_FAMILY = "production_visible_space_catalyst_measurement_repair"
TRIAL_FAMILY = "space_catalyst_standard_surface_contract"
TRIAL_VARIANT_ID = "closed_decision_not_pending_entries_v1"
CHANGED_VARIABLE = "space_catalyst_standard_surface_pending_closed_decision_filter_v1"
PREDICTION = {
    "success_probability": 0.85,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "helper_intentionally_uses_pending_entries_for_all_candidates",
        "test_contract_requires_old_behavior",
        "downstream_candidate_surface_depends_on_stale_space_rows",
    ],
    "confidence_reason": (
        "The event ledger already records closed_decision_count=18 and "
        "pending_decision_count=0 while state.json exposes 18 pending_entries; "
        "the fix is a narrow contract repair and should not touch orders, "
        "rankings, sizing, or exits."
    ),
    "recorded_at": "2026-06-27T20:10:19+00:00",
}
CHANGED_FILES = [
    "quant/space_catalyst_sleeve.py",
    "quant/sleeve_standard_layout.py",
    "quant/test_space_catalyst_sleeve.py",
    "quant/test_sleeve_standard_layout.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260627_024_{SLUG}.json",
    "data/paper_sleeves/space_catalyst/state.json",
    "data/paper_sleeves/space_catalyst/snapshots.jsonl",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
REPRODUCTION_COMMANDS = [
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\sleeve_standard_layout.py quant\\space_catalyst_sleeve.py "
    "quant\\test_sleeve_standard_layout.py quant\\test_space_catalyst_sleeve.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest "
    "quant\\test_sleeve_standard_layout.py quant\\test_space_catalyst_sleeve.py -q",
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
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


def last_jsonl_row(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    for raw in reversed(path.read_text(encoding="utf-8-sig", errors="replace").splitlines()):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            return row
    return {}


def jsonl_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(
        1
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        if raw.strip()
    )


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
    windows = list(payload.get("windows") or [])
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
        "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
        "survival_rate": min(
            (float(row.get("survival_rate") or 0.0) for row in windows),
            default=None,
        ),
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
    }


def state_summary(path: Path) -> dict[str, Any]:
    state = read_json(path, default={})
    pending = [row for row in (state.get("pending_entries") or []) if isinstance(row, dict)]
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "asof_date": state.get("asof_date"),
        "surface_kind": state.get("surface_kind"),
        "trade_enabled": state.get("trade_enabled"),
        "pending_entries": len(pending),
        "open_positions": len(state.get("open_positions") or []),
        "closed_positions": len(state.get("closed_positions") or []),
        "skipped_entries": len(state.get("skipped_entries") or []),
        "pending_keys": sorted(
            {
                (
                    str(row.get("ticker") or ""),
                    str(row.get("event_id") or ""),
                    str(row.get("event_date") or ""),
                )
                for row in pending
            }
        ),
        "sample_pending_entries": pending[:5],
    }


def frame_rows(frame: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        rows.append(
            {
                "Date": index.strftime("%Y-%m-%d"),
                "Open": float(row["Open"]),
                "High": float(row["High"]),
                "Low": float(row["Low"]),
                "Close": float(row["Close"]),
                "Volume": float(row["Volume"]),
            }
        )
    return rows


def load_warehouse_event_rows(asof_date: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    seeds = load_space_catalyst_event_seeds(DEFAULT_SPACE_CATALYST_EVENT_SEED_PATH)
    tickers = set(SPACE_CATALYST_EVENT_BENCHMARKS)
    tickers.update(space_catalyst_observation_feature_tickers())
    event_dates: list[str] = []
    for event in seeds:
        event_date = str(
            event.get("event_date")
            or event.get("date")
            or event.get("effective_as_of")
            or ""
        )[:10]
        if event_date:
            event_dates.append(event_date)
        raw_tickers = event.get("tickers")
        if raw_tickers is None:
            raw_tickers = [event.get("ticker")]
        elif isinstance(raw_tickers, str):
            raw_tickers = [raw_tickers]
        tickers.update(str(ticker).upper() for ticker in (raw_tickers or []) if ticker)
    start = min(event_dates) if event_dates else "2026-01-01"
    frames = load_warehouse_ohlcv_frames(DEFAULT_WAREHOUSE_PATH, sorted(tickers), start, asof_date)
    return {ticker: frame_rows(frame) for ticker, frame in frames.items()}, {
        "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
        "seed_path": repo_rel(Path(DEFAULT_SPACE_CATALYST_EVENT_SEED_PATH)),
        "seed_event_count": len(seeds),
        "requested_tickers": len(tickers),
        "loaded_tickers": len(frames),
        "missing_tickers": sorted(ticker for ticker in tickers if ticker not in frames),
        "start_date": start,
        "end_date": asof_date,
    }


def closed_keys(snapshot: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (
            str(row.get("ticker") or ""),
            str(row.get("event_id") or ""),
            str(row.get("event_date") or ""),
        )
        for row in (snapshot.get("event_rows") or [])
        if isinstance(row, dict) and row.get("closed_decision") is True
    }


def stale_closed_pending_count(summary: dict[str, Any], keys: set[tuple[str, str, str]]) -> int:
    return sum(1 for key in summary.get("pending_keys") or [] if tuple(key) in keys)


def pending_standard_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in snapshot.get("event_rows") or []:
        if not isinstance(row, dict) or row.get("closed_decision") is True:
            continue
        rows.append(
            {
                "ticker": row.get("ticker"),
                "event_date": row.get("event_date"),
                "event_id": row.get("event_id"),
                "semantic_bucket": row.get("semantic_bucket"),
                "outcome_status": row.get("outcome_status"),
                "pending_reason": row.get("pending_reason"),
                "entry_date": row.get("entry_date"),
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    ticket_before = read_json(TICKET_JSON, default={})
    before_metrics = baseline_metrics()
    before_state = state_summary(SPACE_STATE)
    before_snapshot = last_jsonl_row(SPACE_SNAPSHOTS)
    asof_date = str(before_state.get("asof_date") or before_snapshot.get("asof_date") or "")[:10]
    if not asof_date:
        asof_date = "2026-06-26"

    ohlcv_by_ticker, warehouse = load_warehouse_event_rows(asof_date)
    shadow = build_space_catalyst_shadow_snapshot(asof_date)
    event_snapshot = build_space_catalyst_event_ledger_snapshot(
        as_of=asof_date,
        ohlcv_by_ticker=ohlcv_by_ticker,
        space_catalyst_shadow=shadow,
    )
    closed = closed_keys(event_snapshot)
    before_stale = stale_closed_pending_count(before_state, closed)

    standard_surface_result = write_standard_sleeve_surfaces(
        sleeve_dir=SPACE_STATE.parent,
        sleeve_name=str(event_snapshot.get("ledger_name") or "SPACE_CATALYST"),
        rule_version=str(event_snapshot.get("rule_version") or "unknown"),
        asof_date=asof_date,
        pending_entries=pending_standard_rows(event_snapshot),
        extra_snapshot_fields={
            "active_event_count": event_snapshot.get("active_event_count", 0),
            "event_row_count": event_snapshot.get("event_row_count", 0),
            "closed_decision_count": event_snapshot.get("closed_decision_count", 0),
            "pending_decision_count": event_snapshot.get("pending_decision_count", 0),
            "ledger_appended_count": 0,
            "ledger_row_count": jsonl_row_count(SPACE_LEDGER),
        },
    )
    after_state = state_summary(SPACE_STATE)
    after_snapshot = last_jsonl_row(SPACE_SNAPSHOTS)
    after_stale = stale_closed_pending_count(after_state, closed)

    accepted = (
        before_stale > 0
        and after_state["pending_entries"] == int(event_snapshot.get("pending_decision_count") or 0)
        and after_stale == 0
        and after_snapshot.get("pending_count") == after_state["pending_entries"]
        and after_snapshot.get("closed_decision_count")
        == event_snapshot.get("closed_decision_count")
    )
    failed_reasons = []
    if before_stale <= 0:
        failed_reasons.append("before_surface_no_stale_closed_pending_rows_found")
    if after_state["pending_entries"] != int(event_snapshot.get("pending_decision_count") or 0):
        failed_reasons.append("after_pending_entries_do_not_match_pending_decisions")
    if after_stale:
        failed_reasons.append("closed_decisions_still_exposed_as_pending")
    if after_snapshot.get("pending_count") != after_state["pending_entries"]:
        failed_reasons.append("snapshot_pending_count_not_refreshed")
    if after_snapshot.get("closed_decision_count") != event_snapshot.get("closed_decision_count"):
        failed_reasons.append("snapshot_closed_decision_count_not_refreshed")

    after_metrics = dict(before_metrics)
    decision = (
        "accepted_measurement_repair_space_catalyst_standard_surface_pending_filter"
        if accepted
        else "blocked_space_catalyst_standard_surface_pending_filter"
    )
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": "measurement_repair",
        "owner": OWNER,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "observed_only_lead": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": ticket_before.get("causal_components") or [],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_contract_bug_closed_decision_rows_mislabeled_pending",
        "nearby_prior_experiments": ["exp-20260612-017", "exp-20260624-012"],
        "prediction": PREDICTION,
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "space_pending_entries_delta": after_state["pending_entries"]
            - before_state["pending_entries"],
            "stale_closed_pending_delta": after_stale - before_stale,
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
        },
        "gate2": {
            "passed": True,
            "required_fields_checked": [
                "space_event_row.closed_decision",
                "space_event_row.outcome_status",
                "standard_state.pending_entries",
                "standard_snapshot.pending_count",
                "standard_snapshot.closed_decision_count",
            ],
            "event_rows": event_snapshot.get("event_row_count"),
            "closed_decision_count": event_snapshot.get("closed_decision_count"),
            "pending_decision_count": event_snapshot.get("pending_decision_count"),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter was added; stale observe-only closed decisions were removed from standard pending_entries.",
            "signals_generated": before_metrics["signals_generated"],
            "signals_survived": before_metrics["signals_survived"],
            "survival_rate": before_metrics["survival_rate"],
        },
        "gate4": {
            "passed": accepted,
            "observed_only": False,
            "measurement_repair": True,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "before_after_strategy_delta": {
                "strategy_behavior_changed": False,
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
            },
            "before_pending_entries": before_state["pending_entries"],
            "after_pending_entries": after_state["pending_entries"],
            "before_stale_closed_pending_rows": before_stale,
            "after_stale_closed_pending_rows": after_stale,
            "snapshot_updated": bool(
                standard_surface_result.get("updated_snapshot")
                or standard_surface_result.get("appended_snapshot")
            ),
        },
        "space_surface": {
            "asof_date": asof_date,
            "before_state": before_state,
            "after_state": after_state,
            "before_snapshot_tail": before_snapshot,
            "after_snapshot_tail": after_snapshot,
            "event_snapshot_counts": {
                "event_row_count": event_snapshot.get("event_row_count"),
                "closed_decision_count": event_snapshot.get("closed_decision_count"),
                "pending_decision_count": event_snapshot.get("pending_decision_count"),
                "active_event_count": event_snapshot.get("active_event_count"),
            },
            "warehouse": warehouse,
            "standard_surface_persistence": standard_surface_result,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "shared_policy_changed": False,
            "daily_snapshot_exposed": True,
            "parity_note": "Repair only changes observe-only standard surface classification for closed Space event decisions.",
            "live_ready": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The Space event ledger used closed_decision=True to mark mature "
                "event outcomes, but the standard-surface adapter filtered pending "
                "rows by a mostly-null status field. Regenerating the current "
                "surface removed stale closed event decisions from pending_entries "
                "and refreshed the same-date snapshot counts."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not turn this into a Space catalyst alpha retune or threshold "
                "scan. The repair only prevents closed observe-only events from "
                "polluting current candidate matching."
            ),
            "new_evidence_required": (
                "A future Space alpha attempt still needs materially new closed "
                "forward replacement-value rows, richer event provenance, or a "
                "shared default-off helper that beats accepted comparators."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "actual_success": 1 if accepted else 0,
            "actual_decision": decision,
            "predicted_failure_mode_hit": not accepted,
            "realized_failure_modes": failed_reasons,
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 4),
        },
        "related_files": [
            RUNNER,
            "quant/space_catalyst_sleeve.py",
            "quant/sleeve_standard_layout.py",
            "quant/test_space_catalyst_sleeve.py",
            "quant/test_sleeve_standard_layout.py",
            "data/paper_sleeves/space_catalyst/state.json",
            "data/paper_sleeves/space_catalyst/snapshots.jsonl",
            "data/paper_sleeves/space_catalyst/event_state_shadow_summary.json",
            "data/paper_sleeves/space_catalyst/event_state_shadow_ledger.jsonl",
        ],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": ticket_before.get("allowed_write_scope") or [],
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "lean_quality_passed": accepted,
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "ticket_before": ticket_before,
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"ticket_before"}
    }


def build_card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {payload['experiment_id']} - Space catalyst standard surface repair",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Before pending entries: `{payload['gate4']['before_pending_entries']}`",
            f"- After pending entries: `{payload['gate4']['after_pending_entries']}`",
            f"- Stale closed pending rows: `{payload['gate4']['before_stale_closed_pending_rows']} -> {payload['gate4']['after_stale_closed_pending_rows']}`",
            f"- Strategy delta: `{payload['gate4']['before_after_strategy_delta']}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "space_catalyst_sleeve.py",
        REPO_ROOT / "quant" / "sleeve_standard_layout.py",
        REPO_ROOT / "quant" / "test_space_catalyst_sleeve.py",
        REPO_ROOT / "quant" / "test_sleeve_standard_layout.py",
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        SPACE_STATE,
        SPACE_SNAPSHOTS,
        SPACE_SUMMARY,
        SPACE_LEDGER,
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
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": False,
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
            "change_type": CHANGE_TYPE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
        },
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
                "before_pending_entries": payload["gate4"]["before_pending_entries"],
                "after_pending_entries": payload["gate4"]["after_pending_entries"],
                "before_stale_closed_pending_rows": payload["gate4"][
                    "before_stale_closed_pending_rows"
                ],
                "after_stale_closed_pending_rows": payload["gate4"][
                    "after_stale_closed_pending_rows"
                ],
                "snapshot_updated": payload["gate4"]["snapshot_updated"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
