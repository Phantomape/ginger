"""Forward-only estimate revision ledger helpers.

The ledger is intentionally data-only. It does not rank candidates, size
positions, or alter the production signal path.
"""

from __future__ import annotations

import json
import hashlib
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from data_paths import atomic_write_text, daily_artifact_glob, resolve_daily_artifact_path

SNAPSHOT_RE = re.compile(r"earnings_snapshot_(\d{8})\.json$")
SCHEMA_VERSION = 3  # semantic decision-clock contract
MIN_QUALIFIED_SNAPSHOT_SCHEMA_VERSION = 3

QUANT_SIGNAL_LIST_KEYS = (
    ("signals", "selected_signal", True, True),
    ("pilot_signals", "selected_pilot_signal", True, True),
    ("heat_blocked_signals", "heat_blocked_signal", True, False),
    ("heat_blocked_pilot_signals", "heat_blocked_pilot_signal", True, False),
    ("cash_admission_observations", "cash_admission_observation", True, True),
)

ENTRY_PLAN_LIST_KEYS = (
    ("deferred_breakout_signals", "deferred_breakout_signal", True, False),
    ("slot_sliced_signals", "slot_sliced_signal", True, False),
)

PILOT_ENTRY_PLAN_LIST_KEYS = (
    ("pilot_slot_sliced_signals", "pilot_slot_sliced_signal", True, False),
    ("tradeable_pilot_signals", "tradeable_pilot_signal", True, False),
)

EVENT_QUEUE_KEYS = (
    "form4_event_queue",
    "sec_event_queue",
    "sec_governance_event_queue",
    "sec_leadership_event_queue",
)

EVENT_SLEEVE_KEYS = (
    "event_sleeve_bundle",
    "form4_event_sleeve",
    "sec_governance_event_sleeve",
    "sec_leadership_event_sleeve",
    "sec_negative_event_sleeve",
)


def parse_snapshot_date(path: str | Path, payload: dict[str, Any] | None = None) -> date:
    """Return the as-of date encoded by an earnings snapshot."""
    payload = payload or {}
    raw = payload.get("date")
    if raw:
        return datetime.strptime(str(raw), "%Y%m%d").date()
    match = SNAPSHOT_RE.search(Path(path).name)
    if not match:
        raise ValueError(f"not an earnings snapshot path: {path}")
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def load_snapshot_records(
    data_dir: str | Path,
    *,
    start: str | date | None = None,
    end: str | date | None = None,
) -> list[dict[str, Any]]:
    """Load earnings snapshot files with source file metadata."""
    root = Path(data_dir)
    start_date = _coerce_date(start) if start is not None else None
    end_date = _coerce_date(end) if end is not None else None
    records: list[dict[str, Any]] = []

    for path in daily_artifact_glob("earnings_snapshot", root):
        payload = _read_json(path)
        as_of_date = parse_snapshot_date(path, payload)
        if start_date and as_of_date < start_date:
            continue
        if end_date and as_of_date > end_date:
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        records.append(
            {
                "as_of_date": as_of_date,
                "path": path,
                "file_mtime_utc": mtime,
                "payload": payload,
            }
        )

    return _dedupe_snapshot_records(records, root)


def _dedupe_snapshot_records(
    records: list[dict[str, Any]],
    root: Path,
) -> list[dict[str, Any]]:
    by_date: dict[date, dict[str, Any]] = {}
    for record in records:
        as_of = record["as_of_date"]
        current = by_date.get(as_of)
        if current is None or _snapshot_record_prefer_key(record, root) < _snapshot_record_prefer_key(
            current,
            root,
        ):
            by_date[as_of] = record
    return sorted(by_date.values(), key=lambda item: item["as_of_date"])


def _snapshot_record_prefer_key(record: dict[str, Any], root: Path) -> tuple[int, int, datetime, str]:
    return (
        0 if _snapshot_pit_safe(record) else 1,
        _snapshot_path_priority(record["path"], root),
        record["file_mtime_utc"],
        _path_text(record["path"]),
    )


def _snapshot_path_priority(path: str | Path, root: Path) -> int:
    path = Path(path)
    organized = root / "daily" / "snapshots" / "earnings"
    try:
        relative = path.resolve(strict=False).relative_to(organized.resolve(strict=False))
    except ValueError:
        return 2
    if relative.parts and relative.parts[0] == "legacy_root":
        return 1
    return 0


def build_revision_ledger_rows(
    snapshot_records: list[dict[str, Any]],
    *,
    as_of: str | date | None = None,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build per-ticker estimate revision rows for one snapshot date.

    A row is usable for revision analysis only when the current and prior
    observation are both PIT-safe, use the same explicitly persisted estimate
    source and event identity, and have timezone-aware retrieval clocks.  This
    deliberately leaves legacy snapshots visible but unable to retro-qualify.
    """
    if not snapshot_records:
        return []

    generated_at = generated_at or datetime.now(timezone.utc)
    target_date = _coerce_date(as_of) if as_of is not None else snapshot_records[-1]["as_of_date"]
    by_date = {record["as_of_date"]: record for record in snapshot_records}
    current = by_date.get(target_date)
    if current is None:
        raise ValueError(f"no earnings snapshot for {target_date.isoformat()}")

    history_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for record in snapshot_records:
        if record["as_of_date"] >= target_date:
            continue
        for ticker, item in (record["payload"].get("earnings") or {}).items():
            history_by_ticker.setdefault(ticker.upper(), []).append(
                _observation_from_snapshot(record, ticker, item)
            )

    rows: list[dict[str, Any]] = []
    current_pit_safe = _snapshot_pit_safe(current)
    for ticker, item in sorted((current["payload"].get("earnings") or {}).items()):
        ticker = ticker.upper()
        obs = _observation_from_snapshot(current, ticker, item)
        same_event_history = [
            prior
            for prior in history_by_ticker.get(ticker, [])
            if (
                obs["estimate_event_identity"] is not None
                and prior["estimate_event_identity"] == obs["estimate_event_identity"]
            )
        ]
        prior = same_event_history[-1] if same_event_history else None
        prior_7d = _latest_prior_at_least_days_back(same_event_history, target_date, 7)
        prior_30d = _latest_prior_at_least_days_back(same_event_history, target_date, 30)

        prior_eps = prior.get("eps_estimate") if prior else None
        delta_prev = _delta(obs["eps_estimate"], prior_eps)
        delta_7d = _delta(obs["eps_estimate"], prior_7d.get("eps_estimate") if prior_7d else None)
        delta_30d = _delta(obs["eps_estimate"], prior_30d.get("eps_estimate") if prior_30d else None)
        prior_pit_safe = bool(prior and prior.get("source_snapshot_pit_safe"))
        revision_pit_safe = bool(current_pit_safe and prior_pit_safe)
        direction = _direction(delta_prev)
        rollback = _is_estimate_rollback(
            current_estimate=obs["eps_estimate"],
            prior=prior,
            same_event_history=same_event_history,
        )
        quarantine_reason = _revision_quarantine_reason(
            current_pit_safe=current_pit_safe,
            prior=prior,
            obs=obs,
            prior_eps=prior_eps,
            rollback=rollback,
        )
        usable = quarantine_reason is None
        decision_id = _decision_id(
            ticker=ticker,
            obs=obs,
            prior=prior,
            direction=direction,
        )

        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at.isoformat(timespec="seconds"),
                "ticker": ticker,
                "as_of_date": target_date.isoformat(),
                "source_snapshot_path": _path_text(current["path"]),
                "source_snapshot_timestamp": current["payload"].get("timestamp"),
                "source_snapshot_mtime_utc": current["file_mtime_utc"].isoformat(timespec="seconds"),
                "source_snapshot_pit_safe": current_pit_safe,
                "next_earnings_date": obs["next_earnings_date"],
                "fiscal_period": obs["estimate_fiscal_period"],
                "estimate_event_identity": obs["estimate_event_identity"],
                "estimate_source": obs["estimate_source"],
                "eps_estimate": obs["eps_estimate"],
                "revenue_estimate": item.get("revenue_estimate"),
                "vendor_asof": obs["vendor_asof"],
                "source_retrieved_at": obs["decision_clock"],
                "decision_clock": obs["decision_clock"],
                "decision_clock_valid": obs["decision_clock_valid"],
                "decision_clock_source": "row_observed_at",
                "first_seen_at": obs["decision_clock"] if direction != "flat" else None,
                "prior_snapshot_date": prior["as_of_date"] if prior else None,
                "prior_snapshot_eps_estimate": prior_eps,
                "prior_snapshot_pit_safe": prior_pit_safe,
                "prior_snapshot_schema_version": prior.get("snapshot_schema_version") if prior else None,
                "prior_estimate_source": prior.get("estimate_source") if prior else None,
                "prior_decision_clock": prior.get("decision_clock") if prior else None,
                "eps_estimate_delta_prev": delta_prev,
                "eps_estimate_delta_7d": delta_7d,
                "eps_estimate_delta_30d": delta_30d,
                "revision_direction_prev": direction,
                "same_event_history_count": len(same_event_history),
                "same_event_revision_identifiable": obs["estimate_event_identity"] is not None,
                "source_identity_stable": bool(
                    prior and obs["estimate_source"] == prior.get("estimate_source")
                ),
                "snapshot_schema_qualified": bool(
                    obs["snapshot_schema_version"] >= MIN_QUALIFIED_SNAPSHOT_SCHEMA_VERSION
                    and prior
                    and prior.get("snapshot_schema_version", 0)
                    >= MIN_QUALIFIED_SNAPSHOT_SCHEMA_VERSION
                ),
                "estimate_rollback_detected": rollback,
                "revision_quarantine_reason": quarantine_reason,
                "decision_id": decision_id,
                "decision_qualified": bool(
                    usable and decision_id and direction in {"up", "down"}
                ),
                "pit_safe_flag": revision_pit_safe,
                "estimate_revision_usable": usable,
                "pit_caveat": _pit_caveat(current_pit_safe, prior, obs),
                **_empty_match_fields(),
            }
        )

    return rows


def load_daily_signal_match_records(
    data_dir: str | Path,
    as_of: str | date,
) -> list[dict[str, Any]]:
    """Load same-day default-off match records from persisted Ginger outputs.

    The records are audit inputs only. Trend feature rows are deliberately
    separated from true candidate/signal objects so coverage metrics do not
    overstate alpha evidence when production generated no orders.
    """
    root = Path(data_dir)
    as_of_date = _coerce_date(as_of)
    tag = as_of_date.strftime("%Y%m%d")
    records: list[dict[str, Any]] = []

    quant_path = resolve_daily_artifact_path("quant_signals", tag, root)
    if quant_path.exists():
        payload = _read_json(quant_path)
        records.extend(_records_from_quant_signals(payload, quant_path, as_of_date))

    trend_path = resolve_daily_artifact_path("trend_signals", tag, root)
    if trend_path.exists():
        payload = _read_json(trend_path)
        records.extend(_records_from_trend_signals(payload, trend_path, as_of_date))

    return records


def annotate_rows_with_signal_matches(
    rows: list[dict[str, Any]],
    match_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach same-day feature/candidate/signal touch fields to ledger rows."""
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in match_records:
        ticker = str(record.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker].append(record)

    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        matches = by_ticker.get(ticker, [])
        feature_matches = [item for item in matches if item.get("record_type") == "feature_row"]
        candidate_matches = [item for item in matches if item.get("is_candidate_record")]
        selected_matches = [item for item in matches if item.get("is_selected_signal")]

        strategies = sorted(
            {
                strategy
                for item in matches
                for strategy in (item.get("strategies") or [])
                if strategy
            }
        )
        row.update(
            {
                "matched_feature_row_today": bool(feature_matches),
                "matched_candidate_today": bool(candidate_matches),
                "matched_selected_signal_today": bool(selected_matches),
                "matched_candidate_count": len(candidate_matches),
                "matched_selected_signal_count": len(selected_matches),
                "matched_signal_sources": sorted({item["source"] for item in matches}),
                "matched_signal_record_types": sorted({item["record_type"] for item in matches}),
                "matched_signal_strategies": strategies,
                "matched_signal_records": [_compact_match_record(item) for item in matches[:10]],
                "candidate_match_gap_reason": _candidate_match_gap_reason(
                    matches,
                    feature_matches,
                    candidate_matches,
                    bool(match_records),
                ),
            }
        )
    return rows


def summarize_ledger_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return compact coverage and usability metrics for a ledger run."""
    rows_with_eps = [row for row in rows if row.get("eps_estimate") is not None]
    usable = [row for row in rows if row.get("estimate_revision_usable")]
    up = [row for row in usable if row.get("revision_direction_prev") == "up"]
    down = [row for row in usable if row.get("revision_direction_prev") == "down"]
    feature_matched = [row for row in rows if row.get("matched_feature_row_today")]
    candidate_matched = [row for row in rows if row.get("matched_candidate_today")]
    selected_matched = [row for row in rows if row.get("matched_selected_signal_today")]
    usable_candidate_matched = [
        row
        for row in rows
        if row.get("estimate_revision_usable") and row.get("matched_candidate_today")
    ]
    qualified_decisions = [row for row in rows if row.get("decision_qualified")]
    quarantined = [row for row in rows if row.get("revision_quarantine_reason")]
    quarantine_counts: dict[str, int] = defaultdict(int)
    for row in quarantined:
        quarantine_counts[str(row["revision_quarantine_reason"])] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "row_count": len(rows),
        "tickers_with_eps_estimate": len(rows_with_eps),
        "rows_with_next_earnings_date": sum(row.get("next_earnings_date") is not None for row in rows),
        "rows_with_prior_same_event": sum(row.get("prior_snapshot_eps_estimate") is not None for row in rows),
        "estimate_revision_usable_rows": len(usable),
        "qualified_nonflat_decision_rows": len(qualified_decisions),
        "independent_decision_count": len(
            {row.get("decision_id") for row in qualified_decisions if row.get("decision_id")}
        ),
        "quarantined_rows": len(quarantined),
        "quarantine_reason_counts": dict(sorted(quarantine_counts.items())),
        "up_revision_rows": len(up),
        "down_revision_rows": len(down),
        "pit_safe_rate": round(len(usable) / len(rows), 6) if rows else None,
        "matched_feature_rows": len(feature_matched),
        "matched_candidate_rows": len(candidate_matched),
        "matched_selected_signal_rows": len(selected_matched),
        "estimate_revision_usable_and_matched_candidate_rows": len(usable_candidate_matched),
        "up_revision_matched_candidate_rows": sum(
            row.get("revision_direction_prev") == "up" for row in usable_candidate_matched
        ),
        "down_revision_matched_candidate_rows": sum(
            row.get("revision_direction_prev") == "down" for row in usable_candidate_matched
        ),
        "candidate_match_rate": round(len(candidate_matched) / len(rows), 6) if rows else None,
        "matched_candidate_tickers": sorted({row["ticker"] for row in candidate_matched}),
        "matched_selected_signal_tickers": sorted({row["ticker"] for row in selected_matched}),
    }


def persist_estimate_revision_ledger(
    *,
    as_of: str | date,
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/non_ohlcv",
    start: str | date | None = None,
    generated_at: datetime | None = None,
    run_adapter_changed: bool = True,
    signal_data_dir: str | Path | None = None,
    match_daily_signals: bool = True,
) -> dict[str, Any]:
    """Write the daily default-off estimate revision ledger and summary."""
    generated_at = generated_at or datetime.now(timezone.utc)
    as_of_date = _coerce_date(as_of)
    records = load_snapshot_records(data_dir, start=start, end=as_of_date)
    rows = build_revision_ledger_rows(
        records,
        as_of=as_of_date,
        generated_at=generated_at,
    )
    match_records: list[dict[str, Any]] = []
    if match_daily_signals:
        match_records = load_daily_signal_match_records(signal_data_dir or data_dir, as_of_date)
    annotate_rows_with_signal_matches(rows, match_records)
    summary = summarize_ledger_rows(rows)
    tag = as_of_date.strftime("%Y%m%d")

    output_root = Path(output_dir)
    ledger_path = output_root / f"estimate_revision_ledger_{tag}.jsonl"
    summary_path = output_root / f"estimate_revision_ledger_summary_{tag}.json"

    summary.update(
        {
            "generated_at": generated_at.isoformat(timespec="seconds"),
            "as_of_date": as_of_date.isoformat(),
            "data_dir": _path_text(data_dir),
            "signal_data_dir": _path_text(signal_data_dir or data_dir),
            "daily_signal_match_record_count": len(match_records),
            "daily_signal_match_sources": sorted(
                {record.get("source") for record in match_records if record.get("source")}
            ),
            "ledger_path": _path_text(ledger_path),
            "summary_path": _path_text(summary_path),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": bool(run_adapter_changed),
                "replay_only": False,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
                "scope": "default_off_forward_estimate_revision_data_ledger",
            },
        }
    )

    write_jsonl(ledger_path, rows)
    write_json(summary_path, summary)
    return summary


# Atomic temp+replace, never a truncating open("w") on the final path: on
# Windows, truncating a file that another process holds memory-mapped fails
# with ERROR_USER_MAPPED_FILE (OSError Errno 22), which dropped the 2026-07-07
# daily ledger (exp-20260708-007).
def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    atomic_write_text(
        "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows),
        path,
    )


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    atomic_write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        path,
    )


def _records_from_quant_signals(
    payload: dict[str, Any],
    path: Path,
    as_of_date: date,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for key, record_type, is_candidate, is_selected in QUANT_SIGNAL_LIST_KEYS:
        _extend_from_list(
            records,
            payload.get(key),
            source="quant_signals",
            source_path=path,
            as_of_date=as_of_date,
            record_type=record_type,
            is_candidate_record=is_candidate,
            is_selected_signal=is_selected,
        )

    entry_plan = payload.get("entry_execution_plan") or {}
    for key, record_type, is_candidate, is_selected in ENTRY_PLAN_LIST_KEYS:
        _extend_from_list(
            records,
            entry_plan.get(key),
            source=f"entry_execution_plan.{key}",
            source_path=path,
            as_of_date=as_of_date,
            record_type=record_type,
            is_candidate_record=is_candidate,
            is_selected_signal=is_selected,
        )

    pilot_plan = payload.get("pilot_entry_execution_plan") or {}
    for key, record_type, is_candidate, is_selected in PILOT_ENTRY_PLAN_LIST_KEYS:
        _extend_from_list(
            records,
            pilot_plan.get(key),
            source=f"pilot_entry_execution_plan.{key}",
            source_path=path,
            as_of_date=as_of_date,
            record_type=record_type,
            is_candidate_record=is_candidate,
            is_selected_signal=is_selected,
        )

    for key in EVENT_QUEUE_KEYS:
        queue = payload.get(key) or {}
        _extend_from_list(
            records,
            queue.get("candidates"),
            source=key,
            source_path=path,
            as_of_date=as_of_date,
            record_type="event_queue_candidate",
            is_candidate_record=True,
            is_selected_signal=False,
        )

    for key in EVENT_SLEEVE_KEYS:
        sleeve = payload.get(key) or {}
        _extend_from_list(
            records,
            sleeve.get("candidates"),
            source=f"{key}.candidates",
            source_path=path,
            as_of_date=as_of_date,
            record_type="event_sleeve_candidate",
            is_candidate_record=True,
            is_selected_signal=False,
        )
        _extend_from_list(
            records,
            sleeve.get("deduped_candidates"),
            source=f"{key}.deduped_candidates",
            source_path=path,
            as_of_date=as_of_date,
            record_type="event_sleeve_deduped_candidate",
            is_candidate_record=True,
            is_selected_signal=False,
        )

    return records


def _records_from_trend_signals(
    payload: dict[str, Any],
    path: Path,
    as_of_date: date,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    signal_features = payload.get("signals") or {}
    if not isinstance(signal_features, dict):
        return records

    for ticker, features in sorted(signal_features.items()):
        if not isinstance(features, dict):
            continue
        records.append(
            {
                "ticker": str(ticker).upper(),
                "source": "trend_signals",
                "source_path": _path_text(path),
                "as_of_date": as_of_date.isoformat(),
                "record_type": "feature_row",
                "is_candidate_record": False,
                "is_selected_signal": False,
                "strategies": _feature_strategy_hints(features),
                "feature_flags": {
                    "breakout": bool(features.get("breakout")),
                    "breakdown": bool(features.get("breakdown")),
                    "above_200ma": bool(features.get("above_200ma")),
                    "volume_spike": bool(features.get("volume_spike")),
                    "held_position": isinstance(features.get("position"), dict),
                },
            }
        )

    return records


def _extend_from_list(
    records: list[dict[str, Any]],
    items: Any,
    *,
    source: str,
    source_path: Path,
    as_of_date: date,
    record_type: str,
    is_candidate_record: bool,
    is_selected_signal: bool,
) -> None:
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or item.get("symbol") or "").upper()
        if not ticker:
            continue
        records.append(
            {
                "ticker": ticker,
                "source": source,
                "source_path": _path_text(source_path),
                "as_of_date": as_of_date.isoformat(),
                "record_type": record_type,
                "is_candidate_record": is_candidate_record,
                "is_selected_signal": is_selected_signal,
                "strategies": _record_strategies(item, source, record_type),
                "action": item.get("action") or item.get("decision") or item.get("status"),
                "trade_enabled": item.get("trade_enabled"),
                "alters_orders": item.get("alters_orders"),
                "cash_conflict": item.get("cash_conflict"),
                "cash_conflict_id": item.get("cash_conflict_id"),
                "available_cash_usd": item.get("available_cash_usd"),
                "requested_notional_usd": item.get("requested_notional_usd"),
                "cash_source": item.get("cash_source"),
                "capital_block_reason": item.get("capital_block_reason"),
                "skip_reason": item.get("skip_reason"),
                "reason": item.get("reason"),
            }
        )


def _record_strategies(item: dict[str, Any], source: str, record_type: str) -> list[str]:
    raw = (
        item.get("strategy")
        or item.get("signal_type")
        or item.get("source")
        or item.get("queue_name")
        or item.get("rule_version")
        or source
        or record_type
    )
    if isinstance(raw, list):
        return sorted({str(value) for value in raw if value})
    return [str(raw)] if raw else []


def _feature_strategy_hints(features: dict[str, Any]) -> list[str]:
    hints = []
    if features.get("breakout"):
        hints.append("breakout_feature")
    if features.get("above_200ma"):
        hints.append("trend_feature")
    if features.get("volume_spike"):
        hints.append("volume_spike_feature")
    return hints


def _compact_match_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "source",
            "source_path",
            "record_type",
            "strategies",
            "is_candidate_record",
            "is_selected_signal",
            "action",
            "trade_enabled",
            "alters_orders",
            "cash_conflict",
            "cash_conflict_id",
            "available_cash_usd",
            "requested_notional_usd",
            "cash_source",
            "capital_block_reason",
            "skip_reason",
            "reason",
            "feature_flags",
        )
        if key in record
    }


def _candidate_match_gap_reason(
    matches: list[dict[str, Any]],
    feature_matches: list[dict[str, Any]],
    candidate_matches: list[dict[str, Any]],
    any_match_records_loaded: bool,
) -> str | None:
    if candidate_matches:
        return None
    if feature_matches:
        return "feature_row_only_no_persisted_candidate_object"
    if matches:
        return "non_candidate_match_only"
    if any_match_records_loaded:
        return "no_same_day_signal_or_candidate_match"
    return "no_daily_signal_match_artifacts_loaded"


def _empty_match_fields() -> dict[str, Any]:
    return {
        "matched_feature_row_today": False,
        "matched_candidate_today": False,
        "matched_selected_signal_today": False,
        "matched_candidate_count": 0,
        "matched_selected_signal_count": 0,
        "matched_signal_sources": [],
        "matched_signal_record_types": [],
        "matched_signal_strategies": [],
        "matched_signal_records": [],
        "candidate_match_gap_reason": "not_annotated",
    }


def _observation_from_snapshot(
    record: dict[str, Any],
    ticker: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    payload = record.get("payload") or {}
    snapshot_schema_version = int(payload.get("schema_version") or 0)
    # An earnings calendar date does not identify the estimate's own source
    # vintage.  Generic forward-EPS fallbacks therefore remain visible but can
    # never acquire an event identity implicitly.
    event_date = item.get("eps_estimate_event_date")
    fiscal_period = item.get("eps_estimate_fiscal_period") or item.get("fiscal_period")
    estimate_source = item.get("eps_estimate_source") or item.get("estimate_source")
    # Merged broad-universe rows are retrieved after the core snapshot.  Their
    # availability clock must be the row clock; falling back to the top-level
    # snapshot timestamp would backdate those observations.
    decision_clock = _aware_timestamp(item.get("observed_at"))
    return {
        "ticker": ticker.upper(),
        "as_of_date": record["as_of_date"].isoformat(),
        "next_earnings_date": item.get("next_earnings_date"),
        "estimate_event_identity": _estimate_event_identity(event_date, fiscal_period),
        "estimate_fiscal_period": str(fiscal_period) if fiscal_period not in (None, "") else None,
        "estimate_source": str(estimate_source) if estimate_source not in (None, "") else None,
        "vendor_asof": item.get("eps_estimate_vendor_asof") or item.get("vendor_asof"),
        "eps_estimate": _float_or_none(item.get("eps_estimate")),
        "source_snapshot_pit_safe": _snapshot_pit_safe(record),
        "snapshot_schema_version": snapshot_schema_version,
        "decision_clock": decision_clock.isoformat(timespec="seconds") if decision_clock else None,
        "decision_clock_valid": decision_clock is not None,
    }


def _estimate_event_identity(event_date: Any, fiscal_period: Any) -> str | None:
    if event_date in (None, ""):
        return None
    period = str(fiscal_period).strip() if fiscal_period not in (None, "") else "unknown"
    return f"earnings:{str(event_date).strip()}:{period}"


def _aware_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _is_estimate_rollback(
    *,
    current_estimate: float | None,
    prior: dict[str, Any] | None,
    same_event_history: list[dict[str, Any]],
) -> bool:
    if current_estimate is None or prior is None:
        return False
    prior_estimate = prior.get("eps_estimate")
    if prior_estimate is None or _delta(current_estimate, prior_estimate) == 0:
        return False
    return any(
        candidate.get("eps_estimate") is not None
        and abs(float(candidate["eps_estimate"]) - float(current_estimate)) <= 1e-9
        for candidate in same_event_history[:-1]
    )


def _revision_quarantine_reason(
    *,
    current_pit_safe: bool,
    prior: dict[str, Any] | None,
    obs: dict[str, Any],
    prior_eps: float | None,
    rollback: bool,
) -> str | None:
    pit = _pit_caveat(current_pit_safe, prior, obs)
    if pit:
        return pit
    if (
        obs.get("snapshot_schema_version", 0) < MIN_QUALIFIED_SNAPSHOT_SCHEMA_VERSION
        or prior is None
        or prior.get("snapshot_schema_version", 0) < MIN_QUALIFIED_SNAPSHOT_SCHEMA_VERSION
    ):
        return "legacy_snapshot_schema"
    if obs.get("eps_estimate") is None or prior_eps is None:
        return "missing_eps_estimate"
    if not obs.get("estimate_source") or not prior.get("estimate_source"):
        return "missing_estimate_source"
    if obs.get("estimate_source") != prior.get("estimate_source"):
        return "estimate_source_switch"
    if not obs.get("decision_clock_valid") or not prior.get("decision_clock_valid"):
        return "naive_or_missing_decision_clock"
    if rollback:
        return "estimate_rollback_to_prior_value"
    return None


def _decision_id(
    *,
    ticker: str,
    obs: dict[str, Any],
    prior: dict[str, Any] | None,
    direction: str | None,
) -> str | None:
    if direction not in {"up", "down"} or prior is None or not obs.get("decision_clock"):
        return None
    payload = {
        "ticker": ticker,
        "estimate_source": obs.get("estimate_source"),
        "estimate_event_identity": obs.get("estimate_event_identity"),
        "old_estimate": prior.get("eps_estimate"),
        "new_estimate": obs.get("eps_estimate"),
        "first_seen_at": obs.get("decision_clock"),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:24]
    return f"estimate-revision:{digest}"


def _snapshot_pit_safe(record: dict[str, Any]) -> bool:
    # EOD snapshots may be written after the U.S. close and land on the next
    # UTC date. Anything later than that is treated as reconstructed/backfilled.
    return record["file_mtime_utc"].date() <= (record["as_of_date"] + timedelta(days=1))


def _latest_prior_at_least_days_back(
    same_event_history: list[dict[str, Any]],
    target_date: date,
    days: int,
) -> dict[str, Any] | None:
    cutoff = target_date.toordinal() - days
    candidates = [
        item
        for item in same_event_history
        if _coerce_date(item["as_of_date"]).toordinal() <= cutoff
    ]
    return candidates[-1] if candidates else None


def _pit_caveat(
    current_pit_safe: bool,
    prior: dict[str, Any] | None,
    obs: dict[str, Any],
) -> str | None:
    if obs["next_earnings_date"] is None:
        return "missing_next_earnings_date"
    if obs.get("estimate_event_identity") is None:
        return "missing_estimate_event_identity"
    if prior is None:
        return "no_prior_same_event_snapshot"
    if not current_pit_safe:
        return "current_snapshot_created_after_asof"
    if not prior.get("source_snapshot_pit_safe"):
        return "prior_snapshot_created_after_asof"
    return None


def _delta(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    return round(current - prior, 6)


def _direction(delta: float | None) -> str | None:
    if delta is None:
        return None
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _path_text(path: str | Path) -> str:
    return str(path).replace("\\", "/")
