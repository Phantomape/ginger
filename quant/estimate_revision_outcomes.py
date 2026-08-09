"""Forward-only estimate revision outcome settlement helpers.

The outcome ledger attributes already-materialized estimate-revision rows to
fixed holding horizons. It does not rank candidates, size positions, alter
signals, or place paper/live orders.
"""

from __future__ import annotations

import json
import hashlib
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from constants import ROUND_TRIP_COST_PCT
from data_paths import atomic_write_text
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
from us_market_calendar import is_us_equity_session


SCHEMA_VERSION = 2
DEFAULT_HORIZONS = (0, 1, 3, 5, 10, 20)
COMPARATORS = ("SPY", "QQQ")
PROXY_NOTIONAL_USD = 4000.0
MARKET_TIMEZONE = ZoneInfo("America/New_York")
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
INSTRUMENT_MAP_SCHEMA_VERSION = 1
READINESS_SCHEMA_VERSION = 1

# Explicit mappings and qualified clocks are intentionally fail-closed.


def materialize_estimate_revision_instrument_map(
    *,
    as_of: str | date,
    ledger_path: str | Path,
    data_dir: str | Path = "data",
    output_path: str | Path | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Append explicit ticker mappings backed by the tracked SEC CIK file."""

    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    generated_at = generated_at.astimezone(timezone.utc)
    as_of_date = _coerce_date(as_of)
    effective_from = max(as_of_date, generated_at.date()).isoformat()
    source_path = Path(data_dir) / "reference" / "sec_company_tickers.json"
    target = (
        Path(output_path)
        if output_path is not None
        else Path(data_dir) / "reference" / "estimate_revision_instrument_map.jsonl"
    )
    ledger = Path(ledger_path)
    ledger_rows = _read_jsonl(ledger)
    source_payload = _read_json(source_path, default={})
    source_hash = (
        hashlib.sha256(source_path.read_bytes()).hexdigest() if source_path.exists() else None
    )

    by_ticker: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for item in source_payload.values():
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip().upper()
        cik = str(item.get("cik_str") or "").strip()
        if ticker and cik:
            by_ticker[ticker][cik.zfill(10)].add(str(item.get("title") or ""))

    requested_tickers = sorted(
        {
            str(row.get("ticker") or "").strip().upper()
            for row in ledger_rows
            if str(row.get("ticker") or "").strip()
        }
    )
    existing = _read_jsonl(target)
    valid_existing = load_effective_instrument_mappings(target)
    added: list[dict[str, Any]] = []
    ambiguous: list[str] = []
    supersession_ambiguous: list[str] = []
    missing: list[str] = []
    superseded_mapping_count = 0
    for ticker in requested_tickers:
        matches = by_ticker.get(ticker, {})
        if len(matches) != 1:
            (missing if not matches else ambiguous).append(ticker)
            continue
        cik, titles = next(iter(matches.items()))
        title = sorted(titles)[0] if titles else ""
        active_prior = _active_effective_instrument_mappings(
            ticker=ticker,
            decision_clock=generated_at,
            mappings=valid_existing,
        )
        active_identities = {
            (
                str(item.get("instrument_ticker") or "").strip().upper(),
                str(item.get("cik") or ""),
            )
            for item in active_prior
        }
        if len(active_identities) > 1 or len(active_prior) > 1:
            supersession_ambiguous.append(ticker)
            continue
        if active_identities == {(ticker, cik)}:
            continue
        superseded_ids = sorted(
            {
                str(item.get("mapping_id") or "").strip()
                for item in active_prior
                if str(item.get("mapping_id") or "").strip()
            }
        )
        payload = {
            "schema_version": INSTRUMENT_MAP_SCHEMA_VERSION,
            "source_ticker": ticker,
            "instrument_ticker": ticker,
            "cik": cik,
            "issuer_name": title,
            "effective_from": effective_from,
            "effective_to": None,
            "observed_at": generated_at.isoformat(timespec="seconds"),
            "supersedes_mapping_id": (
                superseded_ids[-1] if superseded_ids else None
            ),
            "provenance": {
                "source_path": _path_text(source_path),
                "source_sha256": source_hash,
                "match_rule": "exact_ticker_unique_cik",
            },
        }
        payload["mapping_id"] = "estimate-map:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        added.append(payload)
        superseded_mapping_count += len(superseded_ids)

    if added or not target.exists():
        _write_jsonl(target, [*existing, *added])
    return {
        "status": "ok" if source_hash else "missing_sec_reference",
        "schema_version": INSTRUMENT_MAP_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "effective_from": effective_from,
        "source_path": _path_text(source_path),
        "source_sha256": source_hash,
        "ledger_path": _path_text(ledger),
        "output_path": _path_text(target),
        "requested_ticker_count": len(requested_tickers),
        "added_mapping_count": len(added),
        "superseded_mapping_count": superseded_mapping_count,
        "total_mapping_count": len(existing) + len(added),
        "ambiguous_tickers": ambiguous,
        "supersession_ambiguous_tickers": supersession_ambiguous,
        "missing_tickers": missing,
    }


def load_effective_instrument_mappings(path: str | Path) -> list[dict[str, Any]]:
    """Load only structurally valid, explicitly observed mapping rows."""

    valid: list[dict[str, Any]] = []
    for row in _read_jsonl(Path(path)):
        if int(row.get("schema_version") or 0) != INSTRUMENT_MAP_SCHEMA_VERSION:
            continue
        if not row.get("source_ticker") or not row.get("instrument_ticker") or not row.get("cik"):
            continue
        if _parse_aware_datetime(row.get("observed_at")) is None:
            continue
        try:
            _coerce_date(row.get("effective_from"))
            if row.get("effective_to"):
                _coerce_date(row.get("effective_to"))
        except (TypeError, ValueError):
            continue
        valid.append(dict(row))
    return valid


def _active_effective_instrument_mappings(
    *,
    ticker: str,
    decision_clock: datetime,
    mappings: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return mappings active under the append-only supersession graph."""

    decision_date = decision_clock.date()
    known: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for mapping in mappings:
        if str(mapping.get("source_ticker") or "").strip().upper() != ticker:
            continue
        observed_at = _parse_aware_datetime(mapping.get("observed_at"))
        if observed_at is None or observed_at > decision_clock:
            continue
        try:
            start = _coerce_date(mapping["effective_from"])
            end = (
                _coerce_date(mapping["effective_to"])
                if mapping.get("effective_to")
                else None
            )
        except (KeyError, TypeError, ValueError):
            continue
        known.append(mapping)
        if decision_date >= start and (end is None or decision_date <= end):
            active.append(mapping)

    # Supersession is effective only once the new mapping was both observed
    # and effective. The old append-only row therefore remains resolvable for
    # earlier decision clocks, but never reactivates after a successor ends.
    superseded_ids: set[str] = set()
    for mapping in known:
        try:
            start = _coerce_date(mapping["effective_from"])
        except (KeyError, TypeError, ValueError):
            continue
        superseded_id = str(mapping.get("supersedes_mapping_id") or "").strip()
        if superseded_id and decision_date >= start:
            superseded_ids.add(superseded_id)
    return [
        mapping
        for mapping in active
        if str(mapping.get("mapping_id") or "").strip() not in superseded_ids
    ]


def resolve_effective_instrument_mapping(
    row: dict[str, Any],
    mappings: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    """Resolve one unambiguous mapping that was known by the decision clock."""

    ticker = str(row.get("ticker") or "").strip().upper()
    decision_clock = _parse_aware_datetime(row.get("decision_clock"))
    if not ticker or decision_clock is None:
        return None
    active = _active_effective_instrument_mappings(
        ticker=ticker,
        decision_clock=decision_clock,
        mappings=mappings,
    )
    identities = {
        (str(item.get("instrument_ticker")).upper(), str(item.get("cik"))) for item in active
    }
    if len(identities) != 1:
        return None
    active.sort(
        key=lambda item: (
            _parse_aware_datetime(item.get("observed_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
            str(item.get("mapping_id") or ""),
        )
    )
    return dict(active[-1])


def persist_estimate_revision_outcomes(
    *,
    as_of: str | date,
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/non_ohlcv",
    ledger_path: str | Path | None = None,
    source_summary_path: str | Path | None = None,
    warehouse_path: str | Path | None = None,
    instrument_map_path: str | Path | None = None,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    notional_usd: float = PROXY_NOTIONAL_USD,
    generated_at: datetime | None = None,
    run_adapter_changed: bool = True,
) -> dict[str, Any]:
    """Write the daily fixed-horizon estimate-revision outcome ledger.

    Rows are sourced from the post-quant estimate revision ledger for ``as_of``.
    Only rows that matched same-day candidates are settled; unmatched rows remain
    in the source ledger and are summarized as source coverage.
    """

    generated_at = generated_at or datetime.now(timezone.utc)
    as_of_date = _coerce_date(as_of)
    tag = as_of_date.strftime("%Y%m%d")
    output_root = Path(output_dir)
    source_ledger = Path(ledger_path) if ledger_path is not None else output_root / f"estimate_revision_ledger_{tag}.jsonl"
    source_summary = (
        Path(source_summary_path)
        if source_summary_path is not None
        else output_root / f"estimate_revision_ledger_summary_{tag}.json"
    )
    warehouse = (
        Path(warehouse_path)
        if warehouse_path is not None
        else Path(data_dir) / "warehouse" / "warehouse_main_hot.sqlite"
    )
    instrument_map = (
        Path(instrument_map_path)
        if instrument_map_path is not None
        else Path(data_dir) / "reference" / "estimate_revision_instrument_map.jsonl"
    )
    outcome_path = output_root / f"estimate_revision_outcomes_{tag}.jsonl"
    summary_path = output_root / f"estimate_revision_outcome_summary_{tag}.json"
    normalized_horizons = tuple(sorted({int(horizon) for horizon in horizons}))

    source_rows = _read_jsonl(source_ledger)
    source_summary_payload = _read_json(source_summary, default={})
    matched_rows = [
        row
        for row in source_rows
        if bool(row.get("matched_candidate_today") or row.get("matched_candidate_count"))
    ]
    matched_rows.sort(
        key=lambda row: (
            str(row.get("as_of_date") or as_of_date.isoformat()),
            str(row.get("ticker") or ""),
        )
    )

    warehouse_range = _warehouse_date_range(warehouse)
    latest_complete = _latest_completed_warehouse_date(
        warehouse_range.get("max_date"), generated_at
    )
    mappings = load_effective_instrument_mappings(instrument_map)
    mapped_rows = [
        (row, resolve_effective_instrument_mapping(row, mappings))
        for row in matched_rows
    ]
    tickers = {
        str(mapping.get("instrument_ticker") or "").upper()
        for _, mapping in mapped_rows
        if mapping
    }
    tickers.update(COMPARATORS)
    bars = _load_bars(warehouse, tickers, as_of_date.isoformat(), latest_complete)

    outcome_rows = [
        _build_outcome_row(
            row=row,
            instrument_mapping=mapping,
            as_of_date=as_of_date,
            source_ledger=source_ledger,
            source_summary=source_summary,
            bars=bars,
            latest_complete=latest_complete,
            horizons=normalized_horizons,
            notional_usd=notional_usd,
        )
        for row, mapping in mapped_rows
    ]
    summary = _summarize(
        as_of_date=as_of_date,
        generated_at=generated_at,
        data_dir=data_dir,
        source_rows=source_rows,
        source_summary_payload=source_summary_payload,
        source_ledger=source_ledger,
        source_summary=source_summary,
        instrument_map=instrument_map,
        outcome_rows=outcome_rows,
        warehouse=warehouse,
        warehouse_range=warehouse_range,
        bars=bars,
        horizons=normalized_horizons,
        notional_usd=notional_usd,
        output_path=outcome_path,
        summary_path=summary_path,
        run_adapter_changed=run_adapter_changed,
    )

    _write_jsonl(outcome_path, outcome_rows)
    _write_json(summary_path, summary)
    return summary


def persist_recent_estimate_revision_outcome_catchup(
    *,
    as_of: str | date,
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/non_ohlcv",
    warehouse_path: str | Path | None = None,
    instrument_map_path: str | Path | None = None,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    notional_usd: float = PROXY_NOTIONAL_USD,
    generated_at: datetime | None = None,
    run_adapter_changed: bool = True,
    lookback_days: int = 45,
    exclude_dates: Sequence[str | date] = (),
    max_ledgers: int | None = None,
) -> dict[str, Any]:
    """Refresh recent estimate-revision outcome ledgers as OHLCV matures.

    Daily runs first create candidate-matched estimate-revision ledgers. Their
    forward outcomes may close later when the hot warehouse advances, so the
    settlement pipeline refreshes recent prior ledgers instead of requiring a
    new manual materialization ID for each day.
    """

    generated_at = generated_at or datetime.now(timezone.utc)
    as_of_date = _coerce_date(as_of)
    output_root = Path(output_dir)
    warehouse = (
        Path(warehouse_path)
        if warehouse_path is not None
        else Path(data_dir) / "warehouse" / "warehouse_main_hot.sqlite"
    )
    min_date = as_of_date - timedelta(days=max(int(lookback_days), 0))
    excluded = {_coerce_date(item).isoformat() for item in exclude_dates}
    candidates: list[tuple[date, Path]] = []
    for ledger_path in output_root.glob("estimate_revision_ledger_*.jsonl"):
        tag = ledger_path.stem.replace("estimate_revision_ledger_", "", 1)
        try:
            ledger_date = datetime.strptime(tag, "%Y%m%d").date()
        except ValueError:
            continue
        if ledger_date > as_of_date or ledger_date < min_date:
            continue
        if ledger_date.isoformat() in excluded:
            continue
        candidates.append((ledger_date, ledger_path))

    candidates.sort(key=lambda item: item[0], reverse=True)
    if max_ledgers is not None:
        candidates = candidates[: max(int(max_ledgers), 0)]

    summaries: list[dict[str, Any]] = []
    for ledger_date, ledger_path in candidates:
        tag = ledger_date.strftime("%Y%m%d")
        summaries.append(
            persist_estimate_revision_outcomes(
                as_of=ledger_date,
                data_dir=data_dir,
                output_dir=output_root,
                ledger_path=ledger_path,
                source_summary_path=output_root / f"estimate_revision_ledger_summary_{tag}.json",
                warehouse_path=warehouse,
                instrument_map_path=instrument_map_path,
                horizons=horizons,
                notional_usd=notional_usd,
                generated_at=generated_at,
                run_adapter_changed=run_adapter_changed,
            )
        )

    closed_counts: Counter[str] = Counter()
    pending_counts: Counter[str] = Counter()
    comparator_counts: Counter[str] = Counter()
    for summary in summaries:
        closed_counts.update(
            {
                str(key): int(value or 0)
                for key, value in (summary.get("closed_rows_by_horizon") or {}).items()
            }
        )
        pending_counts.update(
            {
                str(key): int(value or 0)
                for key, value in (summary.get("pending_rows_by_horizon") or {}).items()
            }
        )
        comparator_counts.update(
            {
                str(key): int(value or 0)
                for key, value in (
                    summary.get("comparator_complete_rows_by_horizon") or {}
                ).items()
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok" if summaries else "no_recent_ledgers",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "as_of_date": as_of_date.isoformat(),
        "data_dir": _path_text(data_dir),
        "output_dir": _path_text(output_root),
        "warehouse_path": _path_text(warehouse),
        "lookback_days": int(lookback_days),
        "excluded_dates": sorted(excluded),
        "refreshed_ledger_count": len(summaries),
        "refreshed_ledger_dates": [summary.get("as_of_date") for summary in summaries],
        "closed_rows_by_horizon": dict(sorted(closed_counts.items())),
        "pending_rows_by_horizon": dict(sorted(pending_counts.items())),
        "comparator_complete_rows_by_horizon": dict(sorted(comparator_counts.items())),
        "summaries": summaries,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": bool(run_adapter_changed),
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "default_off_forward_estimate_revision_outcome_catchup",
        },
    }


def persist_estimate_revision_readiness(
    *,
    as_of: str | date,
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/non_ohlcv",
    instrument_map_path: str | Path | None = None,
    output_path: str | Path | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Persist a cross-file, decision-deduped readiness view.

    Legacy rows, flat observations, duplicate ledgers, rollbacks, source
    switches and missing mappings remain countable as raw evidence but cannot
    contribute to independent or settled readiness.
    """

    summary = build_estimate_revision_readiness(
        as_of=as_of,
        data_dir=data_dir,
        output_dir=output_dir,
        instrument_map_path=instrument_map_path,
        generated_at=generated_at,
    )
    target = (
        Path(output_path)
        if output_path is not None
        else Path(data_dir) / "non_ohlcv" / "estimate_revision_readiness_latest.json"
    )
    summary["readiness_path"] = _path_text(target)
    _write_json(target, summary)
    return summary


def build_estimate_revision_readiness(
    *,
    as_of: str | date,
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/non_ohlcv",
    instrument_map_path: str | Path | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    generated_at = generated_at.astimezone(timezone.utc)
    as_of_date = _coerce_date(as_of)
    output_root = Path(output_dir)
    map_path = (
        Path(instrument_map_path)
        if instrument_map_path is not None
        else Path(data_dir) / "reference" / "estimate_revision_instrument_map.jsonl"
    )
    mappings = load_effective_instrument_mappings(map_path)

    ledger_files, excluded_ledger_files = _dated_artifact_files(
        output_root,
        prefix="estimate_revision_ledger",
        as_of_date=as_of_date,
    )
    ledger_rows: list[dict[str, Any]] = []
    for path in ledger_files:
        for raw in _read_jsonl(path):
            row = dict(raw)
            row["_ledger_path"] = _path_text(path)
            ledger_rows.append(row)

    raw_rows = len(ledger_rows)
    candidate_rows = sum(
        bool(row.get("matched_candidate_today") or row.get("matched_candidate_count"))
        for row in ledger_rows
    )
    preliminary = [
        (
            row,
            resolve_effective_instrument_mapping(row, mappings),
        )
        for row in ledger_rows
    ]
    semantic_usable = [
        row
        for row, _ in preliminary
        if _raw_unqualified_reason(row) is None
    ]
    raw_unqualified_reasons: Counter[str] = Counter(
        reason
        for row, _ in preliminary
        if (reason := _raw_unqualified_reason(row)) is not None
    )
    nonflat_rows = [
        row
        for row, _ in preliminary
        if row.get("decision_id")
        and _revision_direction(row) in {"up", "down"}
    ]
    rollback_ids = _rollback_chain_decision_ids(nonflat_rows)
    quarantine_reasons: Counter[str] = Counter()
    qualified_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    annotations_by_id: dict[str, dict[str, bool]] = {}
    quarantined_ids: set[str] = set()
    for row, mapping in preliminary:
        decision_id = str(row.get("decision_id") or "")
        reason = _revision_decision_disqualification_reason(
            row,
            instrument_mapping=mapping,
            as_of_date=as_of_date,
            additional_quarantine_reason=(
                "rollback_chain" if decision_id in rollback_ids else None
            ),
        )
        if reason is not None:
            if not decision_id:
                continue
            quarantined_ids.add(decision_id)
            quarantine_reasons[str(reason)] += 1
            qualified_by_id.pop(decision_id, None)
            annotations_by_id.pop(decision_id, None)
            continue
        if decision_id in quarantined_ids:
            continue
        if decision_id not in qualified_by_id:
            # Identity is canonical-first. Later duplicate ledger rows may add
            # execution annotations, but cannot rewrite the decision clock,
            # ticker, source/event identity, or effective instrument mapping.
            qualified_by_id[decision_id] = (row, mapping)
            annotations_by_id[decision_id] = {
                "candidate_overlap": False,
                "selected_signal_overlap": False,
                "cash_conflict": False,
            }
        annotations = annotations_by_id[decision_id]
        annotations["candidate_overlap"] = bool(
            annotations["candidate_overlap"]
            or row.get("matched_candidate_today")
            or row.get("matched_candidate_count")
        )
        annotations["selected_signal_overlap"] = bool(
            annotations["selected_signal_overlap"]
            or row.get("matched_selected_signal_today")
            or row.get("matched_selected_signal_count")
        )
        annotations["cash_conflict"] = bool(
            annotations["cash_conflict"] or _has_explicit_cash_conflict(row)
        )

    mapped_tickers = sorted(
        {
            str(mapping.get("instrument_ticker") or "").upper()
            for _, mapping in qualified_by_id.values()
        }
    )
    overlap_ids = {
        decision_id
        for decision_id, annotations in annotations_by_id.items()
        if annotations["candidate_overlap"]
    }
    selected_overlap_ids = {
        decision_id
        for decision_id, annotations in annotations_by_id.items()
        if annotations["selected_signal_overlap"]
    }
    cash_conflict_ids = {
        decision_id
        for decision_id, annotations in annotations_by_id.items()
        if annotations["cash_conflict"]
    }

    outcome_files, excluded_outcome_files = _dated_artifact_files(
        output_root,
        prefix="estimate_revision_outcomes",
        as_of_date=as_of_date,
    )
    outcome_rows: list[dict[str, Any]] = []
    for path in outcome_files:
        outcome_rows.extend(_read_jsonl(path))
    required_horizons = (5, 10, 20)
    settled_ids = {
        f"h{horizon}": {
            str(row.get("decision_id"))
            for row in outcome_rows
            if row.get("decision_id") in qualified_by_id
            and row.get("settlement_qualified") is True
            and _horizon_closed_by_as_of(row, horizon, as_of_date)
        }
        for horizon in required_horizons
    }
    settled_counts = {key: len(value) for key, value in settled_ids.items()}
    conservative_settled = min(settled_counts.values(), default=0)
    independent_count = len(qualified_by_id)
    gate_ready = bool(
        independent_count >= 30
        and len(mapped_tickers) >= 10
        and len(cash_conflict_ids) >= 10
        and all(settled_counts[f"h{horizon}"] >= 30 for horizon in required_horizons)
    )

    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "surface_id": "analyst_estimate_revision_forward_decisions",
        "status": "gate_candidate" if gate_ready else "parked",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "as_of_date": as_of_date.isoformat(),
        "raw_count": raw_rows,
        "candidate_count": candidate_rows,
        "independent_count": independent_count,
        "settled_count": conservative_settled,
        "raw_rows": raw_rows,
        "usable_rows": len(semantic_usable),
        "nonflat_decision_rows": len(nonflat_rows),
        "independent_decisions": independent_count,
        "quarantined_rows": sum(raw_unqualified_reasons.values()),
        "raw_unqualified_reason_counts": dict(sorted(raw_unqualified_reasons.items())),
        "quarantined_decisions": len(quarantined_ids),
        "quarantine_reason_counts": dict(sorted(quarantine_reasons.items())),
        "mapped_ticker_count": len(mapped_tickers),
        "mapped_tickers": mapped_tickers,
        "candidate_overlap_decisions": len(overlap_ids),
        "selected_signal_overlap_decisions": len(selected_overlap_ids),
        "actual_cash_conflict_decisions": len(cash_conflict_ids),
        "settled_independent_decisions_by_horizon": settled_counts,
        "settled_independent_decisions": conservative_settled,
        "ledger_file_count": len(ledger_files),
        "excluded_ledger_files": [_path_text(path) for path in excluded_ledger_files],
        "outcome_file_count": len(outcome_files),
        "excluded_outcome_files": [_path_text(path) for path in excluded_outcome_files],
        "outcome_row_count": len(outcome_rows),
        "instrument_map_path": _path_text(map_path),
        "instrument_map_exists": map_path.exists(),
        "instrument_map_row_count": len(mappings),
        "artifact_commitments": {
            "ledger_set_sha256": _file_set_hash(ledger_files),
            "outcome_set_sha256": _file_set_hash(outcome_files),
            "instrument_map_sha256": (
                hashlib.sha256(map_path.read_bytes()).hexdigest() if map_path.exists() else None
            ),
        },
        "gate_ready": gate_ready,
        "reopen_condition": None
        if gate_ready
        else {
            "independent_decisions_gte": 30,
            "mapped_tickers_gte": 10,
            "actual_cash_conflict_decisions_gte": 10,
            "settled_h5_h10_h20_each_gte": 30,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "default_off_estimate_revision_semantic_readiness",
        },
    }


def _rollback_chain_decision_ids(rows: Sequence[dict[str, Any]]) -> set[str]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row.get("ticker") or "").upper(),
                str(row.get("estimate_event_identity") or ""),
                str(row.get("estimate_source") or ""),
            )
        ].append(row)
    quarantined: set[str] = set()
    for chain in grouped.values():
        chain.sort(key=lambda row: str(row.get("decision_clock") or ""))
        for previous, current in zip(chain, chain[1:]):
            if (
                _same_number(previous.get("prior_snapshot_eps_estimate"), current.get("eps_estimate"))
                and _same_number(previous.get("eps_estimate"), current.get("prior_snapshot_eps_estimate"))
            ):
                quarantined.update(
                    str(row.get("decision_id"))
                    for row in (previous, current)
                    if row.get("decision_id")
                )
    return quarantined


def _raw_unqualified_reason(row: dict[str, Any]) -> str | None:
    if int(row.get("schema_version") or 0) < 3:
        return "legacy_snapshot_or_ledger_schema"
    if row.get("revision_quarantine_reason"):
        return str(row["revision_quarantine_reason"])
    if row.get("estimate_revision_usable") is not True:
        return "unqualified_revision_observation"
    if _parse_aware_datetime(row.get("decision_clock")) is None:
        return "naive_or_missing_decision_clock"
    return None


def _revision_direction(row: dict[str, Any]) -> str:
    return str(
        row.get("revision_direction_prev") or row.get("revision_direction") or ""
    ).strip().lower()


def _revision_decision_disqualification_reason(
    row: dict[str, Any],
    *,
    instrument_mapping: dict[str, Any] | None,
    additional_quarantine_reason: str | None = None,
    as_of_date: date | None = None,
) -> str | None:
    """Return the single fail-closed qualification result for one decision."""

    if additional_quarantine_reason:
        return additional_quarantine_reason
    intrinsic_reason = _raw_unqualified_reason(row)
    if intrinsic_reason is not None:
        return intrinsic_reason
    decision_clock = _parse_aware_datetime(row.get("decision_clock"))
    if (
        as_of_date is not None
        and decision_clock
        and decision_clock.astimezone(MARKET_TIMEZONE).date() > as_of_date
    ):
        return "decision_clock_after_as_of"
    if _revision_direction(row) not in {"up", "down"}:
        return "flat_or_missing_revision_direction"
    if not row.get("decision_id"):
        return "missing_decision_id"
    if instrument_mapping is None:
        return "missing_effective_instrument_mapping"
    return None


def _horizon_closed_by_as_of(
    row: dict[str, Any], horizon: int, as_of_date: date
) -> bool:
    if row.get(f"h{horizon}_status") != "closed":
        return False
    exit_date = row.get(f"h{horizon}_exit_date")
    if not exit_date:
        return False
    try:
        return _coerce_date(exit_date) <= as_of_date
    except (TypeError, ValueError):
        return False


def _same_number(left: Any, right: Any) -> bool:
    left_number = _safe_float(left)
    right_number = _safe_float(right)
    return bool(
        left_number is not None
        and right_number is not None
        and abs(left_number - right_number) <= 1e-9
    )


def _file_set_hash(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(_path_text(path).encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _dated_artifact_files(
    root: Path,
    *,
    prefix: str,
    as_of_date: date,
) -> tuple[list[Path], list[Path]]:
    """Select canonical YYYYMMDD JSONL artifacts at or before ``as_of``."""

    included: list[Path] = []
    excluded: list[Path] = []
    marker = f"{prefix}_"
    for path in sorted(root.glob(f"{prefix}_*.jsonl")):
        stem = path.stem
        tag = stem[len(marker) :] if stem.startswith(marker) else ""
        if len(tag) != 8 or not tag.isascii() or not tag.isdigit():
            excluded.append(path)
            continue
        try:
            artifact_date = datetime.strptime(tag, "%Y%m%d").date()
        except ValueError:
            excluded.append(path)
            continue
        (included if artifact_date <= as_of_date else excluded).append(path)
    return included, excluded


def _build_outcome_row(
    *,
    row: dict[str, Any],
    instrument_mapping: dict[str, Any] | None,
    as_of_date: date,
    source_ledger: Path,
    source_summary: Path,
    bars: dict[str, list[dict[str, Any]]],
    latest_complete: str | None,
    horizons: Sequence[int],
    notional_usd: float,
) -> dict[str, Any]:
    source_ticker = str(row.get("ticker") or "").upper()
    ticker = (
        str(instrument_mapping.get("instrument_ticker") or "").upper()
        if instrument_mapping
        else source_ticker
    )
    entry_date = _entry_date(row, as_of_date)
    direction = _revision_direction(row)
    quarantine_reason = _revision_decision_disqualification_reason(
        row,
        instrument_mapping=instrument_mapping,
        as_of_date=as_of_date,
    )
    decision_qualified = quarantine_reason is None
    settlement_qualified = bool(decision_qualified and entry_date)
    if not quarantine_reason and not entry_date:
        quarantine_reason = "invalid_decision_clock"
    return {
        "schema_version": SCHEMA_VERSION,
        "source_revision_ledger": _path_text(source_ledger),
        "source_revision_summary": _path_text(source_summary),
        "source_ticker": source_ticker,
        "ticker": ticker,
        "instrument_ticker": ticker if instrument_mapping else None,
        "instrument_cik": instrument_mapping.get("cik") if instrument_mapping else None,
        "instrument_mapping_id": instrument_mapping.get("mapping_id") if instrument_mapping else None,
        "instrument_mapping_qualified": instrument_mapping is not None,
        "as_of_date": str(row.get("as_of_date") or as_of_date.isoformat()),
        "usable_entry_date": entry_date,
        "target_price": None,
        "target_price_scope": "not_applicable_fixed_horizon_replacement_value",
        "revision_direction": direction,
        "decision_id": row.get("decision_id"),
        "decision_clock": row.get("decision_clock"),
        "first_seen_at": row.get("first_seen_at"),
        "estimate_source": row.get("estimate_source"),
        "estimate_event_identity": row.get("estimate_event_identity"),
        "decision_qualified": decision_qualified,
        "settlement_qualified": settlement_qualified,
        "settlement_quarantine_reason": quarantine_reason,
        "estimate_revision_usable": bool(row.get("estimate_revision_usable")),
        "matched_candidate_today": bool(
            row.get("matched_candidate_today") or row.get("matched_candidate_count")
        ),
        "matched_selected_signal_today": bool(
            row.get("matched_selected_signal_today") or row.get("matched_selected_signal_count")
        ),
        "matched_candidate_count": row.get("matched_candidate_count"),
        "matched_selected_signal_count": row.get("matched_selected_signal_count"),
        "matched_signal_sources": row.get("matched_signal_sources"),
        "matched_signal_record_types": row.get("matched_signal_record_types"),
        "matched_signal_strategies": row.get("matched_signal_strategies"),
        "matched_signal_records": row.get("matched_signal_records"),
        "eps_estimate": row.get("eps_estimate"),
        "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
        "next_earnings_date": row.get("next_earnings_date"),
        "source_snapshot_timestamp": row.get("source_snapshot_timestamp"),
        "source_snapshot_pit_safe": row.get("source_snapshot_pit_safe"),
        "paper_notional_usd": float(notional_usd),
        **_settle_horizons(
            ticker=ticker,
            requested_entry_date=entry_date or as_of_date.isoformat(),
            bars=bars,
            latest_complete=latest_complete,
            horizons=horizons,
            notional_usd=notional_usd,
            qualified=settlement_qualified,
        ),
    }


def _settle_horizons(
    *,
    ticker: str,
    requested_entry_date: str,
    bars: dict[str, list[dict[str, Any]]],
    latest_complete: str | None,
    horizons: Sequence[int],
    notional_usd: float,
    qualified: bool = True,
) -> dict[str, Any]:
    if not qualified:
        result: dict[str, Any] = {
            "requested_entry_date": requested_entry_date,
            "entry_date": requested_entry_date,
            "actual_entry_date": None,
        }
        for horizon in horizons:
            result.update(_empty_horizon(f"h{horizon}", "unqualified_decision"))
        return result
    ticker_rows = bars.get(ticker, [])
    entry_index = _first_index_on_or_after(ticker_rows, requested_entry_date)
    actual_entry_date: str | None = None
    if entry_index is not None:
        actual_entry_date = str(ticker_rows[entry_index].get("date"))

    result: dict[str, Any] = {
        "requested_entry_date": requested_entry_date,
        "entry_date": actual_entry_date or requested_entry_date,
        "actual_entry_date": actual_entry_date,
    }
    for horizon in horizons:
        prefix = f"h{horizon}"
        if entry_index is None or actual_entry_date is None:
            result.update(_empty_horizon(prefix, "missing_entry_bar"))
            continue

        exit_index = entry_index + int(horizon)
        if exit_index >= len(ticker_rows):
            result.update(_empty_horizon(prefix, "pending_forward_close"))
            continue

        exit_row = ticker_rows[exit_index]
        exit_date = str(exit_row.get("date"))
        if latest_complete is None or exit_date > latest_complete:
            result.update(_empty_horizon(prefix, "pending_forward_close"))
            continue

        pnl = _pnl_between_bars(ticker_rows[entry_index], exit_row, notional_usd)
        status = "closed" if pnl is not None else "bad_price"
        spy_pnl = _pnl_for_dates(
            bars.get("SPY", []),
            actual_entry_date,
            exit_date if pnl is not None else None,
            notional_usd,
        )
        qqq_pnl = _pnl_for_dates(
            bars.get("QQQ", []),
            actual_entry_date,
            exit_date if pnl is not None else None,
            notional_usd,
        )
        result.update(
            {
                f"{prefix}_status": status,
                f"{prefix}_exit_date": exit_date if pnl is not None else None,
                f"{prefix}_return_pct": round(pnl / notional_usd, 6)
                if pnl is not None and notional_usd
                else None,
                f"{prefix}_pnl_usd": round(pnl, 2) if pnl is not None else None,
                f"{prefix}_replacement_value_vs_cash_usd": round(pnl, 2)
                if pnl is not None
                else None,
                f"{prefix}_replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2)
                if pnl is not None and spy_pnl is not None
                else None,
                f"{prefix}_replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2)
                if pnl is not None and qqq_pnl is not None
                else None,
                f"{prefix}_spy_same_window_pnl_usd": round(spy_pnl, 2)
                if spy_pnl is not None
                else None,
                f"{prefix}_qqq_same_window_pnl_usd": round(qqq_pnl, 2)
                if qqq_pnl is not None
                else None,
            }
        )
    return result


def _summarize(
    *,
    as_of_date: date,
    generated_at: datetime,
    data_dir: str | Path,
    source_rows: list[dict[str, Any]],
    source_summary_payload: dict[str, Any],
    source_ledger: Path,
    source_summary: Path,
    instrument_map: Path,
    outcome_rows: list[dict[str, Any]],
    warehouse: Path,
    warehouse_range: dict[str, Any],
    bars: dict[str, list[dict[str, Any]]],
    horizons: Sequence[int],
    notional_usd: float,
    output_path: Path,
    summary_path: Path,
    run_adapter_changed: bool,
) -> dict[str, Any]:
    matched_tickers = sorted({row["ticker"] for row in outcome_rows if row.get("ticker")})
    qualified_rows = [row for row in outcome_rows if row.get("settlement_qualified")]
    missing_tickers = sorted(ticker for ticker in matched_tickers if not bars.get(ticker))
    source_status = "ok"
    if not source_ledger.exists():
        source_status = "missing_source_ledger"
    elif not warehouse.exists():
        source_status = "missing_warehouse"
    elif not outcome_rows:
        source_status = "no_matched_candidate_rows"
    elif not qualified_rows:
        source_status = "no_qualified_mapped_decisions"

    closed_counts = {
        f"h{horizon}": sum(1 for row in outcome_rows if row.get(f"h{horizon}_status") == "closed")
        for horizon in horizons
    }
    pending_counts = {
        f"h{horizon}": sum(
            1 for row in outcome_rows if row.get(f"h{horizon}_status") == "pending_forward_close"
        )
        for horizon in horizons
    }
    comparator_complete = {
        f"h{horizon}": sum(
            1
            for row in outcome_rows
            if row.get(f"h{horizon}_status") == "closed"
            and row.get(f"h{horizon}_replacement_value_vs_spy_usd") is not None
            and row.get(f"h{horizon}_replacement_value_vs_qqq_usd") is not None
        )
        for horizon in horizons
    }
    status_counts = {
        f"h{horizon}": dict(
            sorted(
                Counter(str(row.get(f"h{horizon}_status") or "missing") for row in outcome_rows).items()
            )
        )
        for horizon in horizons
    }
    direction_counts = Counter(
        str(row.get("revision_direction") or "missing") for row in outcome_rows
    )
    nonflat_usable = [
        row
        for row in outcome_rows
        if row.get("estimate_revision_usable")
        and str(row.get("revision_direction") or "").lower() not in {"", "flat", "missing"}
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": source_status,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "as_of_date": as_of_date.isoformat(),
        "data_dir": _path_text(data_dir),
        "source_revision_ledger": _path_text(source_ledger),
        "source_revision_ledger_exists": source_ledger.exists(),
        "source_revision_summary": _path_text(source_summary),
        "source_revision_summary_exists": source_summary.exists(),
        "source_revision_summary_payload": source_summary_payload,
        "instrument_map_path": _path_text(instrument_map),
        "instrument_map_exists": instrument_map.exists(),
        "instrument_map_sha256": (
            hashlib.sha256(instrument_map.read_bytes()).hexdigest()
            if instrument_map.exists()
            else None
        ),
        "warehouse_path": _path_text(warehouse),
        "warehouse_exists": warehouse.exists(),
        "warehouse_date_range": warehouse_range,
        "warehouse_loaded_tickers": sorted(ticker for ticker, rows in bars.items() if rows),
        "warehouse_missing_matched_tickers": missing_tickers,
        "output_path": _path_text(output_path),
        "summary_path": _path_text(summary_path),
        "horizons": list(horizons),
        "proxy_notional_usd": float(notional_usd),
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "slippage_bps_target": SLIPPAGE_BPS_TARGET,
        "source_ledger_row_count": len(source_rows),
        "matched_candidate_rows": len(outcome_rows),
        "mapped_matched_candidate_rows": sum(
            1 for row in outcome_rows if row.get("instrument_mapping_qualified")
        ),
        "qualified_matched_decision_rows": len(qualified_rows),
        "qualified_independent_decision_count": len(
            {row.get("decision_id") for row in qualified_rows if row.get("decision_id")}
        ),
        "quarantined_matched_rows": sum(
            1 for row in outcome_rows if not row.get("settlement_qualified")
        ),
        "actual_cash_conflict_decisions": len(
            {
                row.get("decision_id")
                for row in qualified_rows
                if row.get("decision_id") and _has_explicit_cash_conflict(row)
            }
        ),
        "matched_candidate_tickers": matched_tickers,
        "usable_matched_candidate_rows": sum(
            1 for row in outcome_rows if row.get("estimate_revision_usable")
        ),
        "nonflat_usable_matched_candidate_rows": len(nonflat_usable),
        "direction_counts": dict(sorted(direction_counts.items())),
        "closed_rows_by_horizon": closed_counts,
        "pending_rows_by_horizon": pending_counts,
        "comparator_complete_rows_by_horizon": comparator_complete,
        "status_counts_by_horizon": status_counts,
        "replacement_value_by_horizon": _replacement_summary(outcome_rows, horizons),
        "sample_rows": outcome_rows[:5],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": bool(run_adapter_changed),
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "default_off_forward_estimate_revision_outcome_settlement",
        },
    }


def _replacement_summary(
    rows: list[dict[str, Any]],
    horizons: Sequence[int],
) -> dict[str, dict[str, dict[str, Any]]]:
    summary: dict[str, dict[str, dict[str, Any]]] = {}
    for horizon in horizons:
        prefix = f"h{horizon}"
        summary[prefix] = {
            "vs_cash": _summarize_values(
                [row.get(f"{prefix}_replacement_value_vs_cash_usd") for row in rows]
            ),
            "vs_spy": _summarize_values(
                [row.get(f"{prefix}_replacement_value_vs_spy_usd") for row in rows]
            ),
            "vs_qqq": _summarize_values(
                [row.get(f"{prefix}_replacement_value_vs_qqq_usd") for row in rows]
            ),
        }
    return summary


def _summarize_values(values: list[Any]) -> dict[str, Any]:
    numeric = [number for number in (_safe_float(value) for value in values) if number is not None]
    return {
        "count": len(numeric),
        "mean": round(mean(numeric), 4) if numeric else None,
        "median": round(median(numeric), 4) if numeric else None,
        "min": round(min(numeric), 4) if numeric else None,
        "max": round(max(numeric), 4) if numeric else None,
        "win_rate": round(sum(1 for value in numeric if value > 0) / len(numeric), 4)
        if numeric
        else None,
    }


def _empty_horizon(prefix: str, status: str) -> dict[str, Any]:
    return {
        f"{prefix}_status": status,
        f"{prefix}_exit_date": None,
        f"{prefix}_return_pct": None,
        f"{prefix}_pnl_usd": None,
        f"{prefix}_replacement_value_vs_cash_usd": None,
        f"{prefix}_replacement_value_vs_spy_usd": None,
        f"{prefix}_replacement_value_vs_qqq_usd": None,
        f"{prefix}_spy_same_window_pnl_usd": None,
        f"{prefix}_qqq_same_window_pnl_usd": None,
    }


def _load_bars(
    warehouse: Path,
    tickers: set[str],
    start: str,
    end: str | None,
) -> dict[str, list[dict[str, Any]]]:
    if not warehouse.exists() or not tickers or end is None:
        return {}
    placeholders = ",".join("?" for _ in sorted(tickers))
    query = (
        "select ticker, date, open, close from ohlcv "
        f"where ticker in ({placeholders}) and date >= ? and date <= ? "
        "order by ticker, date"
    )
    params = [*sorted(tickers), start, end]
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with sqlite3.connect(_sqlite_readonly_uri(warehouse), uri=True) as con:
        for ticker, day, open_, close in con.execute(query, params):
            if not is_us_equity_session(str(day)):
                continue
            rows_by_ticker[str(ticker).upper()].append(
                {
                    "date": str(day),
                    "open": _safe_float(open_),
                    "close": _safe_float(close),
                }
            )
    return dict(rows_by_ticker)


def _warehouse_date_range(warehouse: Path) -> dict[str, Any]:
    if not warehouse.exists():
        return {"min_date": None, "max_date": None, "rows": 0}
    with sqlite3.connect(_sqlite_readonly_uri(warehouse), uri=True) as con:
        min_date, max_date, rows = con.execute(
            "select min(date), max(date), count(*) from ohlcv"
        ).fetchone()
    return {"min_date": min_date, "max_date": max_date, "rows": int(rows or 0)}


def _latest_completed_warehouse_date(
    warehouse_max_date: str | None, generated_at: datetime
) -> str | None:
    """Cap daily bars at a completed regular U.S. equity session."""
    if not warehouse_max_date:
        return None
    try:
        candidate = _coerce_date(warehouse_max_date)
    except (TypeError, ValueError):
        return None
    market_now = generated_at.astimezone(MARKET_TIMEZONE)
    today = market_now.date()
    if candidate > today:
        candidate = today
    if candidate == today and (market_now.hour, market_now.minute) < (16, 15):
        candidate -= timedelta(days=1)
    while not is_us_equity_session(candidate):
        candidate -= timedelta(days=1)
    return candidate.isoformat()


def _pnl_for_dates(
    rows: list[dict[str, Any]],
    entry_date: str | None,
    exit_date: str | None,
    notional_usd: float,
) -> float | None:
    if not entry_date or not exit_date:
        return None
    by_date = {str(row.get("date")): row for row in rows}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    return _pnl_between_bars(entry, exit_, notional_usd)


def _pnl_between_bars(
    entry: dict[str, Any],
    exit_: dict[str, Any],
    notional_usd: float,
) -> float | None:
    entry_open = _safe_float(entry.get("open"))
    exit_close = _safe_float(exit_.get("close"))
    if entry_open is None or entry_open <= 0 or exit_close is None or exit_close <= 0:
        return None
    entry_price = apply_entry_fill(entry_open)
    exit_price = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell")
    return float(notional_usd) * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)


def _first_index_on_or_after(rows: list[dict[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        if str(row.get("date")) >= day:
            return index
    return None


def _entry_date(row: dict[str, Any], fallback: date) -> str | None:
    """Return the first possible U.S. market open strictly after evidence."""

    del fallback  # legacy as-of dates are intentionally not decision clocks
    decision_clock = _parse_aware_datetime(
        row.get("decision_clock") or row.get("first_seen_at")
    )
    if decision_clock is None:
        return None
    local = decision_clock.astimezone(MARKET_TIMEZONE)
    market_open = local.replace(
        hour=MARKET_OPEN_HOUR,
        minute=MARKET_OPEN_MINUTE,
        second=0,
        microsecond=0,
    )
    candidate = local.date() if local < market_open else local.date() + timedelta(days=1)
    return candidate.isoformat()


def _parse_aware_datetime(value: Any) -> datetime | None:
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


def _has_explicit_cash_conflict(row: dict[str, Any]) -> bool:
    for match in row.get("matched_signal_records") or []:
        if not isinstance(match, dict):
            continue
        if match.get("cash_conflict") is True:
            return True
    return False


def _coerce_date(value: str | date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _safe_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _read_json(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default
    return payload if isinstance(payload, dict) else default


# Atomic temp+replace, never a truncating open("w") on the final path: on
# Windows, truncating a file that another process holds memory-mapped fails
# with ERROR_USER_MAPPED_FILE (OSError Errno 22) — see exp-20260708-007.
def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    atomic_write_text(
        "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows),
        path,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str, sort_keys=True) + "\n",
        path,
    )


def _sqlite_readonly_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _path_text(path: str | Path) -> str:
    return str(path).replace("\\", "/")
