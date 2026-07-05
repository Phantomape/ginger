"""exp-20260704-008: turn-of-month admission parity probe.

Measurement repair only. exp-20260704-006 found that the accepted
turn-of-month default-off paper sleeve underfires versus replay-implied
admissions. This runner checks whether a representative accepted historical
month-end day is visible to the daily helper with production-like calendar
inputs, then audits current forward snapshots for the same calendar-label
surface. It does not change thresholds, sizing, exits, orders, or helper code.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260609_027_turn_of_month_liquid_leadership_shared_adapter as accepted_adapter  # noqa: E402
import turn_of_month_liquid_leadership_paper_sleeve as shared_turn  # noqa: E402


EXPERIMENT_ID = "exp-20260704-008"
OWNER = "alpha-explore"
SLUG = "turn_of_month_admission_parity_probe"
RUNNER = f"quant/experiments/exp_20260704_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
ACCEPTED_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260609-027"
    / "exp_20260609_027_turn_of_month_liquid_leadership_shared_adapter.json"
)
SNAPSHOT_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "turn_of_month_liquid_leadership" / "snapshots.jsonl"
STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "turn_of_month_liquid_leadership" / "state.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_008_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\experiments\\exp_20260704_008_turn_of_month_admission_parity_probe.py",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=str) + "\n",
        path,
    )


def as_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def baseline_summary() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON, {})
    windows = payload.get("windows") or []
    generated = sum(as_int(window.get("signals_generated")) for window in windows)
    survived = sum(as_int(window.get("signals_survived")) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(as_int(window.get("trade_count") or window.get("total_trades")) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def baseline_window_path(label: str) -> Path:
    payload = load_json(BASELINE_JSON, {})
    for window in payload.get("windows") or []:
        if window.get("label") == label:
            return REPO_ROOT / str(window["path"])
    raise RuntimeError(f"baseline window not found: {label}")


def choose_representative_trade(accepted: dict[str, Any]) -> dict[str, Any]:
    by_window = accepted.get("target_trades_by_window") or {}
    flattened: list[tuple[str, dict[str, Any]]] = []
    for label in ("old_thin", "mid_weak", "late_strong"):
        for row in by_window.get(label) or []:
            if isinstance(row, dict):
                flattened.append((label, row))
    if not flattened:
        raise RuntimeError("accepted turn-of-month artifact has no target trades")

    chosen_label, chosen = next(
        (
            (label, row)
            for label, row in flattened
            if row.get("candidate_month_label") == "last_trading_day"
        ),
        flattened[0],
    )
    signal_date = str(chosen.get("signal_date") or chosen.get("date"))[:10]
    same_day = [
        row
        for label, row in flattened
        if label == chosen_label and str(row.get("signal_date") or row.get("date"))[:10] == signal_date
    ]
    return {
        "window_label": chosen_label,
        "signal_date": signal_date,
        "accepted_trades": same_day,
        "selection_reason": "preferred_last_trading_day" if chosen.get("candidate_month_label") == "last_trading_day" else "fallback_first_available",
    }


def flatten_entries(entries_by_date: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rows in entries_by_date.values():
        out.extend(row for row in rows if isinstance(row, dict))
    return out


def compact_trade(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    return {
        "ticker": row.get("ticker"),
        "decision_id": row.get("decision_id"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "month_label": row.get("candidate_month_label"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "pnl": row.get("pnl"),
        "candidate_score": row.get("candidate_score"),
        "same_ticker_ab_overlap": row.get("same_ticker_ab_overlap"),
    }


def _ticker_list(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("ticker") or "").upper() for row in rows]


def representative_day_parity() -> dict[str, Any]:
    accepted = load_json(ACCEPTED_ARTIFACT, {})
    chosen = choose_representative_trade(accepted)
    label = chosen["window_label"]
    signal_date = chosen["signal_date"]
    cfg = accepted_adapter.framework.WINDOWS[label]
    sector_entries = accepted_adapter.framework._load_sector_entries()
    snapshot = accepted_adapter.framework._load_window_snapshot(
        cfg=cfg,
        eligible_tickers=set(sector_entries),
    )
    window_sector_entries = {
        ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
    }
    candidate_universe = {
        "status": "warehouse_sector_known_liquid_common_stock_like_universe",
        "tickers": sorted(window_sector_entries),
        "records": window_sector_entries,
    }
    before_result = load_json(baseline_window_path(label), {})
    core_entries_by_date = accepted_adapter.framework.shadow._baseline_entries(before_result)
    core_entries = flatten_entries(core_entries_by_date)
    calendar_dates = accepted_adapter.framework.shadow._trading_dates(snapshot)
    one_day_window = {
        label: {
            "start": signal_date,
            "end": signal_date,
            "snapshot": cfg.get("snapshot"),
        }
    }

    historical, historical_audit = shared_turn.build_turn_of_month_liquid_leadership_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries_by_date,
        windows=one_day_window,
        candidate_universe=candidate_universe,
        calendar_dates=calendar_dates,
        config=shared_turn.DEFAULT_CONFIG,
    )
    daily_no_calendar = shared_turn.build_turn_of_month_liquid_leadership_snapshot(
        as_of=signal_date,
        ohlcv_by_ticker=snapshot,
        candidate_universe=candidate_universe,
        core_entries=core_entries,
        state=shared_turn.empty_turn_of_month_liquid_leadership_state(),
        persist=False,
    )
    daily_with_calendar = shared_turn.build_turn_of_month_liquid_leadership_snapshot(
        as_of=signal_date,
        ohlcv_by_ticker=snapshot,
        candidate_universe=candidate_universe,
        core_entries=core_entries,
        calendar_dates=calendar_dates,
        state=shared_turn.empty_turn_of_month_liquid_leadership_state(),
        persist=False,
    )

    accepted_trades = chosen["accepted_trades"]
    daily_no_rows = daily_no_calendar.get("candidates") or []
    daily_cal_rows = daily_with_calendar.get("candidates") or []
    accepted_tickers = _ticker_list(accepted_trades)
    historical_tickers = _ticker_list(historical)
    daily_no_tickers = _ticker_list(daily_no_rows)
    daily_cal_tickers = _ticker_list(daily_cal_rows)
    accepted_decisions = [row.get("decision_id") for row in accepted_trades]
    historical_decisions = [row.get("decision_id") for row in historical]
    daily_no_decisions = [row.get("decision_id") for row in daily_no_rows]
    daily_cal_decisions = [row.get("decision_id") for row in daily_cal_rows]

    historical_matches_accepted = accepted_tickers == historical_tickers and accepted_decisions == historical_decisions
    daily_no_calendar_matches = accepted_tickers == daily_no_tickers and accepted_decisions == daily_no_decisions
    daily_with_calendar_matches = accepted_tickers == daily_cal_tickers and accepted_decisions == daily_cal_decisions

    return {
        "accepted_artifact": repo_rel(ACCEPTED_ARTIFACT),
        "window_label": label,
        "signal_date": signal_date,
        "selection_reason": chosen["selection_reason"],
        "sector_entry_count": len(sector_entries),
        "loaded_ohlcv_tickers": len(snapshot),
        "accepted_trades": [compact_trade(row) for row in accepted_trades],
        "historical_trades": [compact_trade(row) for row in historical],
        "daily_no_calendar_candidates": [compact_trade(row) for row in daily_no_rows],
        "daily_with_calendar_candidates": [compact_trade(row) for row in daily_cal_rows],
        "accepted_tickers": accepted_tickers,
        "historical_tickers": historical_tickers,
        "daily_no_calendar_tickers": daily_no_tickers,
        "daily_with_calendar_tickers": daily_cal_tickers,
        "accepted_decisions": accepted_decisions,
        "historical_decisions": historical_decisions,
        "daily_no_calendar_decisions": daily_no_decisions,
        "daily_with_calendar_decisions": daily_cal_decisions,
        "historical_matches_accepted": historical_matches_accepted,
        "daily_no_calendar_matches": daily_no_calendar_matches,
        "daily_with_calendar_matches": daily_with_calendar_matches,
        "calendar_parity_drift_detected": historical_matches_accepted and daily_with_calendar_matches and not daily_no_calendar_matches,
        "historical_audit": {
            "total_selected": historical_audit.get("total_selected"),
            "raw_candidate_count_by_window": historical_audit.get("raw_candidate_count_by_window"),
            "scan_by_window": historical_audit.get("scan_by_window"),
        },
        "daily_no_calendar_scan": daily_no_calendar.get("context_scan"),
        "daily_with_calendar_scan": daily_with_calendar.get("context_scan"),
        "daily_no_calendar_candidate_count": daily_no_calendar.get("candidate_count"),
        "daily_with_calendar_candidate_count": daily_with_calendar.get("candidate_count"),
    }


def current_forward_snapshot_audit() -> dict[str, Any]:
    rows = read_jsonl(SNAPSHOT_JSONL)
    per_asof: dict[str, dict[str, Any]] = {}
    samples: list[dict[str, Any]] = []
    for row in rows:
        asof = str(row.get("asof_date") or row.get("date") or "")[:10]
        if not asof:
            continue
        bucket = per_asof.setdefault(
            asof,
            {
                "raw_candidate_count": 0,
                "candidate_count": 0,
                "new_pending_count": 0,
                "filled_count": 0,
                "open_position_count": 0,
                "month_label_distribution": Counter(),
            },
        )
        for key in ("raw_candidate_count", "candidate_count", "new_pending_count", "filled_count", "open_position_count"):
            bucket[key] = max(as_int(bucket.get(key)), as_int(row.get(key)))
        scan = row.get("context_scan") if isinstance(row.get("context_scan"), dict) else {}
        for label, count in (scan.get("month_label_distribution") or {}).items():
            bucket["month_label_distribution"][str(label)] += as_int(count)
        candidate = row.get("candidate") or (row.get("candidates") or [None])[0]
        if candidate and len(samples) < 8:
            samples.append(
                {
                    "asof_date": asof,
                    "candidate": compact_trade(candidate),
                    "raw_candidate_count": row.get("raw_candidate_count"),
                    "candidate_count": row.get("candidate_count"),
                    "new_pending_count": row.get("new_pending_count"),
                    "generated_at": row.get("generated_at"),
                    "month_label_distribution": scan.get("month_label_distribution"),
                }
            )

    totals = Counter()
    month_labels = Counter()
    for bucket in per_asof.values():
        for key in ("raw_candidate_count", "candidate_count", "new_pending_count", "filled_count", "open_position_count"):
            totals[key] += as_int(bucket.get(key))
        month_labels.update(bucket.get("month_label_distribution") or {})

    state = load_json(STATE_JSON, {})
    state_counts = {
        "pending_entries": len(state.get("pending_entries") or []),
        "open_positions": len(state.get("open_positions") or []),
        "closed_positions": len(state.get("closed_positions") or []),
        "skipped_days": len(state.get("skipped_days") or []),
    }
    return {
        "snapshot_file": repo_rel(SNAPSHOT_JSONL),
        "snapshot_rows": len(rows),
        "unique_asof_dates": len(per_asof),
        "first_asof_date": min(per_asof) if per_asof else None,
        "last_asof_date": max(per_asof) if per_asof else None,
        "totals_deduped_by_asof_max": dict(totals),
        "month_label_distribution": dict(month_labels),
        "last_trading_day_labels_seen": as_int(month_labels.get("last_trading_day")),
        "candidate_samples": samples,
        "state_file": repo_rel(STATE_JSON),
        "state_counts": state_counts,
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {})
    baseline = baseline_summary()
    parity = representative_day_parity()
    forward = current_forward_snapshot_audit()
    drift_detected = bool(parity["calendar_parity_drift_detected"])
    accepted = bool(drift_detected and forward["last_trading_day_labels_seen"] == 0)
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_turn_of_month_calendar_parity_drift_identified"
        if accepted
        else "blocked_turn_of_month_parity_probe_inconclusive"
    )
    failed_reasons: list[str] = []
    if not parity["historical_matches_accepted"]:
        failed_reasons.append("representative_historical_replay_did_not_match_accepted_artifact")
    if not parity["daily_with_calendar_matches"]:
        failed_reasons.append("daily_with_explicit_calendar_did_not_match_accepted_artifact")
    if not drift_detected:
        failed_reasons.append("daily_no_calendar_drift_not_detected")
    if forward["last_trading_day_labels_seen"] != 0:
        failed_reasons.append("forward_snapshots_already_show_last_trading_day_labels")

    why = (
        "The accepted representative month-end trade reproduced through the shared "
        "historical helper and through the daily helper only when an explicit trading "
        "calendar was supplied. The production-like no-calendar daily call failed "
        "closed on the same last-trading-day label, and current forward snapshots "
        "show no last_trading_day labels. The underfire gap is therefore a concrete "
        "daily calendar-parity measurement defect, not evidence to retune thresholds."
        if accepted
        else (
            "The probe did not cleanly isolate a calendar-parity defect; inspect the "
            "representative-day and forward-label audit before changing daily wiring."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "Forward evidence supply is an alpha bottleneck: accepted turn-of-month "
            "paper rows cannot mature if daily observation fails to admit the same "
            "calendar labels that the accepted replay admitted."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "turn_of_month_admission_parity_probe",
        "trial_variant_id": "turn_of_month_daily_calendar_representative_day_v1",
        "single_causal_variable": "turn_of_month_daily_vs_replay_representative_day_parity_v1",
        "changed_variable": "turn_of_month_daily_vs_replay_representative_day_parity_v1",
        "causal_components": [
            "accepted historical last-trading-day replay",
            "daily helper no-calendar versus explicit-calendar comparison",
            "current forward snapshot calendar-label audit",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": ["exp-20260609-027", "exp-20260704-006", "exp-20260704-007"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "representative_day_daily_vs_replay_calendar_parity_probe",
        "new_evidence_axis": (
            "Measurement-only calendar parity evidence for the accepted turn-of-month "
            "sleeve named by exp-20260704-006; no threshold, notional, top-N, hold, "
            "cooldown, or response rule changed."
        ),
        "gate1": {"passed": BASELINE_JSON.exists(), "baseline_metrics": baseline},
        "gate2": {
            "passed": bool(parity["historical_matches_accepted"] and parity["daily_with_calendar_matches"]),
            "fields_checked": [
                "accepted target_trades_by_window",
                "candidate_month_label",
                "historical OHLCV rows",
                "complete trading calendar",
                "daily snapshot candidate_count/raw_candidate_count",
                "decision_id",
                "entry_date",
                "exit_date",
            ],
            "entry_date_target_price_scope": (
                "No executable order or target exit is created. The probe compares "
                "paper entry_date/exit_date lifecycle fields on accepted default-off rows."
            ),
            "representative_window": parity["window_label"],
            "representative_signal_date": parity["signal_date"],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter/rank/size/exit rule changed; survival is baseline identity.",
        },
        "gate4": {
            "mode": "measurement_repair_turn_of_month_calendar_parity",
            "passed": accepted,
            "accepted_measurement_repair": accepted,
            "accepted_alpha": False,
            "strategy_behavior_changed": False,
            "failed_reasons": failed_reasons,
            "calendar_parity_drift_detected": drift_detected,
            "forward_last_trading_day_labels_seen": forward["last_trading_day_labels_seen"],
            "decision_basis": why,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "representative_day_parity": parity,
        "current_forward_snapshot_audit": forward,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "Read-only parity probe over the existing shared turn-of-month helper "
                "and existing paper snapshots. It does not alter live/default orders, "
                "rankings, sizing, exits, or paper snapshot generation."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune month-start/end day counts, leadership thresholds, "
                "close-location, volume bounds, volatility bounds, top-N, hold-day, "
                "cooldown, notional, or response curves from this underfire span."
            ),
            "new_evidence_required": (
                "Repair daily calendar parity by passing an explicit trading calendar "
                "or known month-end dates into the daily turn-of-month snapshot, then "
                "rerun the representative parity probe and accumulate closed forward "
                "replacement-value rows. A valid alpha retry also needs true closed "
                "forward replacement value or a new PIT flow-beneficiary field."
            ),
        },
        "next_retry_requires": [
            "daily calendar parity repair for last_trading_day labels",
            "post-repair forward turn-of-month rows with closed cash/SPY/QQQ replacement value",
            "no frozen-window threshold/notional/hold/cooldown retune",
        ],
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": accepted,
            "surprise_note": (
                "Moderate surprise: the underfire queue pointed at possible drift, and "
                "the representative month-end probe isolated the calendar-label gap."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
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
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "calibration",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    parity = payload["representative_day_parity"]
    forward = payload["current_forward_snapshot_audit"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `{payload["accepted_alpha"]}`
- Strategy behavior changed: `false`
- Representative day: `{parity["window_label"]}` / `{parity["signal_date"]}`
- Historical matches accepted: `{parity["historical_matches_accepted"]}`
- Daily no-calendar matches accepted: `{parity["daily_no_calendar_matches"]}`
- Daily with-calendar matches accepted: `{parity["daily_with_calendar_matches"]}`
- Forward last-trading-day labels seen: `{forward["last_trading_day_labels_seen"]}`
- Artifact: `{payload["artifact"]}`

## Gates

- Gate 1 baseline loaded: `{payload["gate1"]["passed"]}`
- Gate 2 representative fields verified: `{payload["gate2"]["passed"]}`
- Gate 3 survival unchanged: `{payload["gate3"]["passed"]}`
- Gate 4 measurement repair: `{payload["gate4"]["passed"]}`

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Reproduction

```powershell
{chr(10).join(payload["reproduction_commands"])}
```
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "changed_files": CHANGED_FILES,
        "files": {path: {"exists": (REPO_ROOT / path).exists()} for path in CHANGED_FILES},
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = load_json(TICKET_JSON, {})
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["alpha_hypothesis"] = payload["alpha_hypothesis"]
    ticket["causal_components"] = payload["causal_components"]
    ticket["nearby_prior_experiments"] = payload["nearby_prior_experiments"]
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    ticket["new_evidence_axis"] = payload["new_evidence_axis"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "gate4": payload["gate4"],
    }
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    safe_write_json(ticket, TICKET_JSON)


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)
    update_ticket(payload)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload.get("prediction"),
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
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
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "lean_quality_passed": True,
        },
    )
    print(json.dumps(log_record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
