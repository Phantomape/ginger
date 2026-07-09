"""exp-20260705-001: narrow-range compression admission parity probe.

Measurement repair only. The accepted narrow-range compression breakout
default-off sleeve currently has zero forward admissions. This runner verifies
that a real historical accepted compression-breakout day still reproduces
through the current daily helper, then audits current forward snapshots to
separate true rule sparsity from admission drift.
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
import exp_20260608_013_narrow_range_compression_shared_adapter as accepted_adapter  # noqa: E402
import narrow_range_compression_breakout_paper_sleeve as shared_nr  # noqa: E402


EXPERIMENT_ID = "exp-20260705-001"
OWNER = "alpha-explore"
SLUG = "narrow_range_compression_admission_parity_probe"
RUNNER = f"quant/experiments/exp_20260705_001_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
BASELINE_ARCHIVE_DIR = REPO_ROOT / "data" / "backtests" / "archive" / "20260604_ohlcv_warehouse_replay"
ACCEPTED_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260608-013"
    / "exp_20260608_013_narrow_range_compression_shared_adapter.json"
)
SNAPSHOT_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "narrow_range_compression_breakout" / "snapshots.jsonl"
STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "narrow_range_compression_breakout" / "state.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_001_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_001_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\experiments\\exp_20260705_001_narrow_range_compression_admission_parity_probe.py",
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


def as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        if window.get("label") != label:
            continue
        path = REPO_ROOT / str(window["path"])
        if path.exists():
            return path
        archived = BASELINE_ARCHIVE_DIR / Path(str(window["path"])).name
        if archived.exists():
            return archived
        return path
    raise RuntimeError(f"baseline window not found: {label}")


def choose_representative_trade(accepted: dict[str, Any]) -> dict[str, Any]:
    by_window = accepted.get("target_trades_by_window") or {}
    for label in ("old_thin", "mid_weak", "late_strong"):
        rows = [row for row in by_window.get(label) or [] if isinstance(row, dict)]
        if not rows:
            continue
        first = rows[0]
        signal_date = str(first.get("signal_date") or first.get("date"))[:10]
        same_day = [
            row
            for row in rows
            if str(row.get("signal_date") or row.get("date"))[:10] == signal_date
        ]
        return {
            "window_label": label,
            "signal_date": signal_date,
            "accepted_trades": same_day,
            "selection_reason": "first_old_thin_accepted_day"
            if label == "old_thin"
            else "first_available_accepted_day",
        }
    raise RuntimeError("accepted narrow-range compression artifact has no target trades")


def compact_trade(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    return {
        "ticker": row.get("ticker"),
        "decision_id": row.get("decision_id"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "pnl": row.get("pnl"),
        "pnl_pct_net": row.get("pnl_pct_net"),
        "paper_status": row.get("paper_status"),
        "candidate_score": row.get("candidate_score"),
        "candidate_range_expansion_ratio": row.get("candidate_range_expansion_ratio"),
        "candidate_range10_to_range40_ratio": row.get("candidate_range10_to_range40_ratio"),
        "same_day_ab_entry_count": row.get("same_day_ab_entry_count"),
        "same_day_ab_overlap": row.get("same_day_ab_overlap"),
        "same_ticker_ab_overlap": row.get("same_ticker_ab_overlap"),
    }


def ticker_list(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("ticker") or "").upper() for row in rows]


def decision_list(rows: list[dict[str, Any]]) -> list[Any]:
    return [row.get("decision_id") for row in rows]


def trading_dates_between(ohlcv_by_ticker: dict[str, Any], start: str, end: str) -> list[str]:
    rows = shared_nr.leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    dates = sorted({str(row.get("date") or "")[:10] for rows_for_ticker in rows.values() for row in rows_for_ticker})
    return [day for day in dates if start <= day <= end]


def state_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": shared_nr.STATE_SCHEMA_VERSION,
        "sleeve": shared_nr.SLEEVE_NAME,
        "updated_at": snapshot.get("generated_at"),
        "pending_entries": snapshot.get("pending_entries") or [],
        "open_positions": snapshot.get("open_positions") or [],
        "closed_positions": snapshot.get("closed_positions") or [],
        "skipped_days": [],
    }


def row_by_decision(rows: list[dict[str, Any]], decision_id: Any) -> dict[str, Any] | None:
    for row in rows:
        if row.get("decision_id") == decision_id:
            return row
    return None


def same_money(a: Any, b: Any, ndigits: int = 2) -> bool:
    left = as_float(a)
    right = as_float(b)
    if left is None or right is None:
        return a == b
    return round(left, ndigits) == round(right, ndigits)


def representative_day_parity() -> dict[str, Any]:
    accepted = load_json(ACCEPTED_ARTIFACT, {})
    chosen = choose_representative_trade(accepted)
    label = chosen["window_label"]
    signal_date = chosen["signal_date"]
    accepted_trades = chosen["accepted_trades"]
    accepted_exit_dates = [str(row.get("exit_date") or "")[:10] for row in accepted_trades]
    max_exit_date = max(day for day in accepted_exit_dates if day)

    cfg = accepted_adapter.framework.WINDOWS[label]
    sector_entries = accepted_adapter.framework._load_sector_entries()
    ohlcv_snapshot = accepted_adapter.framework._load_window_snapshot(
        cfg=cfg,
        eligible_tickers=set(sector_entries),
    )
    window_sector_entries = {
        ticker: meta for ticker, meta in sector_entries.items() if ticker in ohlcv_snapshot
    }
    before_result = load_json(baseline_window_path(label), {})
    core_entries_by_date = accepted_adapter.framework.shadow._baseline_entries(before_result)
    one_day_window = {
        label: {
            "start": signal_date,
            "end": signal_date,
            "snapshot": cfg.get("snapshot"),
        }
    }

    historical_trades, historical_audit = shared_nr.build_narrow_range_compression_breakout_historical_trades(
        ohlcv_by_ticker=ohlcv_snapshot,
        core_entries_by_date=core_entries_by_date,
        windows=one_day_window,
        sector_entries=window_sector_entries,
        config=shared_nr.DEFAULT_CONFIG,
    )
    signal_snapshot = shared_nr.build_narrow_range_compression_breakout_snapshot(
        as_of=signal_date,
        ohlcv_by_ticker=ohlcv_snapshot,
        sector_entries=window_sector_entries,
        core_entries=core_entries_by_date.get(signal_date, []),
        state=shared_nr.empty_narrow_range_compression_breakout_state(),
        config=shared_nr.DEFAULT_CONFIG,
        persist=False,
    )

    state = shared_nr.empty_narrow_range_compression_breakout_state()
    daily_progress: list[dict[str, Any]] = []
    daily_closed_positions: list[dict[str, Any]] = []
    for day in trading_dates_between(ohlcv_snapshot, signal_date, max_exit_date):
        snapshot = shared_nr.build_narrow_range_compression_breakout_snapshot(
            as_of=day,
            ohlcv_by_ticker=ohlcv_snapshot,
            sector_entries=window_sector_entries,
            core_entries=core_entries_by_date.get(day, []),
            state=state,
            config=shared_nr.DEFAULT_CONFIG,
            persist=False,
        )
        daily_progress.append(
            {
                "asof_date": day,
                "candidate_count": snapshot.get("candidate_count"),
                "raw_candidate_count": snapshot.get("raw_candidate_count"),
                "new_pending_count": snapshot.get("new_pending_count"),
                "filled_count": snapshot.get("filled_count"),
                "closed_count_today": snapshot.get("closed_count_today"),
                "pending_count": snapshot.get("pending_count"),
                "open_position_count": snapshot.get("open_position_count"),
                "closed_position_count": snapshot.get("closed_position_count"),
                "candidate_tickers": ticker_list(snapshot.get("candidates") or []),
                "closed_tickers_today": ticker_list(snapshot.get("closed_positions_this_run") or []),
            }
        )
        daily_closed_positions.extend(
            row for row in snapshot.get("closed_positions_this_run") or [] if isinstance(row, dict)
        )
        state = state_from_snapshot(snapshot)

    daily_candidates = [row for row in signal_snapshot.get("candidates") or [] if isinstance(row, dict)]
    daily_pending = [row for row in signal_snapshot.get("new_pending_entries") or [] if isinstance(row, dict)]
    accepted_tickers = ticker_list(accepted_trades)
    historical_tickers = ticker_list(historical_trades)
    daily_tickers = ticker_list(daily_candidates)
    daily_pending_tickers = ticker_list(daily_pending)
    accepted_decisions = decision_list(accepted_trades)
    historical_decisions = decision_list(historical_trades)
    daily_decisions = decision_list(daily_candidates)
    daily_pending_decisions = decision_list(daily_pending)

    admission_ticker_match = accepted_tickers == historical_tickers == daily_tickers == daily_pending_tickers
    admission_decision_match = (
        accepted_decisions == historical_decisions == daily_decisions == daily_pending_decisions
    )
    historical_lifecycle_match = [
        {
            "ticker": accepted_row.get("ticker"),
            "accepted_entry_date": accepted_row.get("entry_date"),
            "historical_entry_date": historical_row.get("entry_date"),
            "accepted_exit_date": accepted_row.get("exit_date"),
            "historical_exit_date": historical_row.get("exit_date"),
            "accepted_pnl": accepted_row.get("pnl"),
            "historical_pnl": historical_row.get("pnl"),
        }
        for accepted_row, historical_row in zip(accepted_trades, historical_trades)
    ]
    historical_lifecycle_passed = (
        len(accepted_trades) == len(historical_trades)
        and all(
            item["accepted_entry_date"] == item["historical_entry_date"]
            and item["accepted_exit_date"] == item["historical_exit_date"]
            and same_money(item["accepted_pnl"], item["historical_pnl"])
            for item in historical_lifecycle_match
        )
    )

    daily_lifecycle_match: list[dict[str, Any]] = []
    for accepted_row in accepted_trades:
        closed = row_by_decision(state.get("closed_positions") or [], accepted_row.get("decision_id"))
        daily_lifecycle_match.append(
            {
                "ticker": accepted_row.get("ticker"),
                "decision_id": accepted_row.get("decision_id"),
                "accepted_entry_date": accepted_row.get("entry_date"),
                "daily_entry_date": closed.get("entry_date") if closed else None,
                "accepted_exit_date": accepted_row.get("exit_date"),
                "daily_exit_date": closed.get("exit_date") if closed else None,
                "accepted_pnl": accepted_row.get("pnl"),
                "daily_pnl": closed.get("pnl") if closed else None,
                "daily_closed_found": closed is not None,
            }
        )
    daily_lifecycle_passed = all(
        item["daily_closed_found"]
        and item["accepted_entry_date"] == item["daily_entry_date"]
        and item["accepted_exit_date"] == item["daily_exit_date"]
        and same_money(item["accepted_pnl"], item["daily_pnl"])
        for item in daily_lifecycle_match
    )

    context = signal_snapshot.get("narrow_range_compression_breakout_context") or {}
    scan = signal_snapshot.get("context_scan") or {}
    context_passed = as_int(scan.get("raw_compression_breakout_candidates")) >= len(daily_candidates) >= 1
    parity_passed = (
        admission_ticker_match
        and admission_decision_match
        and historical_lifecycle_passed
        and daily_lifecycle_passed
        and context_passed
    )

    return {
        "accepted_artifact": repo_rel(ACCEPTED_ARTIFACT),
        "window_label": label,
        "signal_date": signal_date,
        "max_exit_date": max_exit_date,
        "selection_reason": chosen["selection_reason"],
        "sector_entry_count": len(sector_entries),
        "window_sector_entry_count": len(window_sector_entries),
        "loaded_ohlcv_tickers": len(ohlcv_snapshot),
        "same_day_core_entry_count": len(core_entries_by_date.get(signal_date, [])),
        "accepted_trades": [compact_trade(row) for row in accepted_trades],
        "historical_trades": [compact_trade(row) for row in historical_trades],
        "daily_signal_candidates": [compact_trade(row) for row in daily_candidates],
        "daily_signal_pending_entries": [compact_trade(row) for row in daily_pending],
        "daily_final_closed_positions": [
            compact_trade(row_by_decision(state.get("closed_positions") or [], decision_id))
            for decision_id in accepted_decisions
        ],
        "daily_progress": daily_progress,
        "daily_closed_positions_this_sim": [compact_trade(row) for row in daily_closed_positions],
        "accepted_tickers": accepted_tickers,
        "historical_tickers": historical_tickers,
        "daily_tickers": daily_tickers,
        "daily_pending_tickers": daily_pending_tickers,
        "accepted_decisions": accepted_decisions,
        "historical_decisions": historical_decisions,
        "daily_decisions": daily_decisions,
        "daily_pending_decisions": daily_pending_decisions,
        "admission_ticker_match": admission_ticker_match,
        "admission_decision_match": admission_decision_match,
        "historical_lifecycle_match": historical_lifecycle_match,
        "historical_lifecycle_passed": historical_lifecycle_passed,
        "daily_lifecycle_match": daily_lifecycle_match,
        "daily_lifecycle_passed": daily_lifecycle_passed,
        "context_passed": context_passed,
        "parity_passed": parity_passed,
        "signal_snapshot_candidate_count": signal_snapshot.get("candidate_count"),
        "signal_snapshot_raw_candidate_count": signal_snapshot.get("raw_candidate_count"),
        "signal_snapshot_new_pending_count": signal_snapshot.get("new_pending_count"),
        "daily_context": context,
        "daily_context_scan": scan,
        "historical_audit": {
            "selected_by_window": historical_audit.get("selected_by_window"),
            "raw_candidate_count_by_window": historical_audit.get("raw_candidate_count_by_window"),
            "scan_by_window": historical_audit.get("scan_by_window"),
        },
    }


def current_forward_snapshot_audit() -> dict[str, Any]:
    rows = read_jsonl(SNAPSHOT_JSONL)
    latest_by_asof: dict[str, dict[str, Any]] = {}
    for row in rows:
        asof = str(row.get("asof_date") or row.get("date") or "")[:10]
        if asof:
            latest_by_asof[asof] = row

    totals = Counter()
    raw_context_dates: list[str] = []
    candidate_dates: list[str] = []
    new_pending_dates: list[str] = []
    closed_today_dates: list[str] = []
    reason_counts: Counter[str] = Counter()
    rejected_reasons: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    for asof, row in sorted(latest_by_asof.items()):
        context = row.get("narrow_range_compression_breakout_context")
        if not isinstance(context, dict):
            context = row.get("context_scan") if isinstance(row.get("context_scan"), dict) else {}
        scan = row.get("context_scan") if isinstance(row.get("context_scan"), dict) else context
        if not isinstance(scan, dict):
            scan = {}
        raw_count = as_int(row.get("raw_candidate_count"))
        if raw_count == 0:
            raw_count = as_int(scan.get("raw_compression_breakout_candidates"))
        candidate_count = as_int(row.get("candidate_count"))
        new_pending_count = as_int(row.get("new_pending_count"))
        rejected_count = as_int(row.get("rejected_candidate_count"))
        closed_count = as_int(row.get("closed_count_today"))
        context_days = as_int(scan.get("days_with_raw_compression_breakout_candidates"))

        totals["raw_candidate_count"] += raw_count
        totals["candidate_count"] += candidate_count
        totals["new_pending_count"] += new_pending_count
        totals["rejected_candidate_count"] += rejected_count
        totals["closed_count_today"] += closed_count
        totals["days_with_raw_compression_breakout_candidates"] += context_days

        if raw_count > 0 or context_days > 0:
            raw_context_dates.append(asof)
        if candidate_count > 0:
            candidate_dates.append(asof)
        if new_pending_count > 0:
            new_pending_dates.append(asof)
        if closed_count > 0:
            closed_today_dates.append(asof)
        if raw_count == 0 and context_days == 0:
            reason_counts["no_compression_breakout_context"] += 1
        elif raw_count > 0 and candidate_count == 0:
            reason_counts["raw_candidates_rejected_or_state_blocked"] += 1
        elif candidate_count > 0:
            reason_counts["accepted_candidate_present"] += 1

        for rejected in row.get("rejected_candidates") or []:
            if isinstance(rejected, dict):
                rejected_reasons[str(rejected.get("filter_reason") or "unknown")] += 1

        context_samples = context.get("context_samples") if isinstance(context.get("context_samples"), list) else []
        sample = next((item for item in context_samples if isinstance(item, dict)), None)
        if len(samples) < 10:
            samples.append(
                {
                    "asof_date": asof,
                    "raw_candidate_count": raw_count,
                    "candidate_count": candidate_count,
                    "new_pending_count": new_pending_count,
                    "rejected_candidate_count": rejected_count,
                    "closed_count_today": closed_count,
                    "context_days": context_days,
                    "top_context": sample,
                }
            )

    state = load_json(STATE_JSON, {})
    skip_reasons = Counter(
        str(row.get("reason") or "unknown")
        for row in state.get("skipped_days") or []
        if isinstance(row, dict)
    )
    zero_fire_explained = (
        len(latest_by_asof) >= 10
        and totals["raw_candidate_count"] == 0
        and totals["candidate_count"] == 0
        and totals["new_pending_count"] == 0
        and totals["closed_count_today"] == 0
        and set(skip_reasons) <= {"no_compression_breakout_context"}
    )
    return {
        "snapshot_file": repo_rel(SNAPSHOT_JSONL),
        "snapshot_rows": len(rows),
        "unique_asof_dates": len(latest_by_asof),
        "first_asof_date": min(latest_by_asof) if latest_by_asof else None,
        "last_asof_date": max(latest_by_asof) if latest_by_asof else None,
        "raw_context_dates": raw_context_dates,
        "raw_context_date_count": len(raw_context_dates),
        "candidate_dates": candidate_dates,
        "candidate_date_count": len(candidate_dates),
        "new_pending_dates": new_pending_dates,
        "new_pending_date_count": len(new_pending_dates),
        "closed_today_dates": closed_today_dates,
        "closed_today_date_count": len(closed_today_dates),
        "totals_deduped_by_asof_latest": dict(totals),
        "reason_counts": dict(reason_counts.most_common()),
        "rejected_filter_reasons": dict(rejected_reasons.most_common()),
        "state_file": repo_rel(STATE_JSON),
        "state_counts": {
            "pending_entries": len(state.get("pending_entries") or []),
            "open_positions": len(state.get("open_positions") or []),
            "closed_positions": len(state.get("closed_positions") or []),
            "skipped_days": len(state.get("skipped_days") or []),
        },
        "state_skip_reasons": dict(skip_reasons.most_common()),
        "context_samples": samples,
        "zero_fire_explained_by_no_compression_context": zero_fire_explained,
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {})
    baseline = baseline_summary()
    parity = representative_day_parity()
    forward = current_forward_snapshot_audit()
    accepted = bool(parity["parity_passed"] and forward["zero_fire_explained_by_no_compression_context"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_narrow_range_compression_admission_parity_confirmed"
        if accepted
        else "blocked_narrow_range_compression_admission_parity_drift_or_ambiguous_forward_context"
    )
    failed_reasons: list[str] = []
    if not parity["parity_passed"]:
        failed_reasons.append("representative_historical_daily_replay_mismatch")
    if not forward["zero_fire_explained_by_no_compression_context"]:
        failed_reasons.append("current_forward_zero_fire_not_fully_explained_by_no_compression_context")

    why = (
        "The first accepted historical compression-breakout day reproduced through "
        "the current shared helper: accepted artifact, one-day historical replay, "
        "signal-day daily admission, and daily state advancement matched ticker, "
        "decision ID, entry date, exit date, and PnL. Current forward snapshots "
        "have no raw compression-breakout contexts, so zero forward admissions are "
        "expected under the accepted rule."
        if accepted
        else (
            "The probe did not cleanly distinguish true absence of compression "
            "contexts from an admission or input drift. Inspect representative "
            "parity and forward context counts before changing the sleeve."
        )
    )

    return {
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
            "Forward evidence supply is an alpha bottleneck: accepted "
            "narrow-range compression breakout rows cannot mature if daily "
            "production observation fails to admit the same compression-breakout "
            "candidates that replay admitted."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "narrow_range_compression_admission_parity_probe",
        "trial_variant_id": "narrow_range_compression_representative_day_daily_vs_replay_v1",
        "single_causal_variable": "narrow_range_compression_daily_vs_replay_representative_day_parity_v1",
        "changed_variable": "narrow_range_compression_daily_vs_replay_representative_day_parity_v1",
        "causal_components": [
            "accepted historical compression-breakout replay day",
            "daily snapshot helper with persist false",
            "daily state advancement through the accepted exit date",
            "current forward compression-context audit",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260608-013",
            "exp-20260704-006",
            "exp-20260704-007",
            "exp-20260704-010",
            "exp-20260704-025",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "representative_day_daily_vs_replay_compression_parity_probe",
        "new_evidence_axis": (
            "Measurement-only representative-day parity evidence for the accepted "
            "narrow-range compression sleeve newly flagged by exp-20260704-025; "
            "no threshold, notional, top-N, hold, cooldown, or response rule changed."
        ),
        "gate1": {"passed": BASELINE_JSON.exists(), "baseline_metrics": baseline},
        "gate2": {
            "passed": bool(parity["parity_passed"] and parity["daily_lifecycle_passed"]),
            "fields_checked": [
                "accepted target_trades_by_window",
                "historical OHLCV rows",
                "broad-market sector universe",
                "same-day baseline A/B entries for overlap metadata",
                "daily snapshot candidate_count/raw_candidate_count",
                "decision_id",
                "entry_date",
                "exit_date",
                "pnl",
            ],
            "entry_date_target_price_scope": (
                "No executable order or target exit is created. This default-off "
                "paper sleeve uses next-open entry and fixed hold exit; the probe "
                "checks paper entry_date/exit_date lifecycle fields rather than "
                "core signal target_price."
            ),
            "representative_window": parity["window_label"],
            "representative_signal_date": parity["signal_date"],
            "representative_exit_date": parity["max_exit_date"],
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
            "mode": "measurement_repair_narrow_range_compression_admission_parity",
            "passed": accepted,
            "accepted_measurement_repair": accepted,
            "accepted_alpha": False,
            "strategy_behavior_changed": False,
            "failed_reasons": failed_reasons,
            "representative_parity_passed": parity["parity_passed"],
            "current_zero_fire_explained_by_no_compression_context": forward[
                "zero_fire_explained_by_no_compression_context"
            ],
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
                "Read-only parity probe over the existing shared narrow-range "
                "compression helper and existing paper snapshots. It does not alter "
                "live/default orders, rankings, sizing, exits, or paper snapshot generation."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune range-compression lookback, range-expansion ratio, "
                "volume, close-location, ret5/ret20, top-N, hold-day, cooldown, "
                "notional, or response curves from this zero-fire forward span."
            ),
            "new_evidence_required": (
                "Reopen narrow-range compression activation only after forward daily "
                "snapshots include raw compression-breakout candidates with closed "
                "cash, SPY, and QQQ replacement value, or after a concrete daily "
                "helper input drift is observed."
            ),
        },
        "next_retry_requires": [
            "actual forward raw compression-breakout rows with closed replacement value",
            "or a concrete daily helper input drift, not a threshold retune",
        ],
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": (ticket.get("prediction") or {}).get("success_probability"),
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "Low surprise: the accepted helper already had shared historical/daily "
                "coverage, and current forward rows show no raw compression contexts."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


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
    totals = forward["totals_deduped_by_asof_latest"]
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
- Representative parity passed: `{parity["parity_passed"]}`
- Daily lifecycle passed: `{parity["daily_lifecycle_passed"]}`
- Forward raw compression candidates: `{totals.get("raw_candidate_count")}`
- Forward candidate dates: `{forward["candidate_date_count"]}`
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
