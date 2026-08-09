"""Deterministic incumbent selection for cash-conflict rotation.

This module deliberately contains no price, return, or signal-strength logic.
It only identifies the oldest already-effective core position when a caller has
independently established that a qualified fresh core entry has a cash conflict.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any


POLICY_VERSION = "cash_conflict_oldest_incumbent_full_rotation_v1"


def _field(position: Any, name: str, default: Any = None) -> Any:
    if isinstance(position, Mapping):
        return position.get(name, default)
    return getattr(position, name, default)


def _ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    candidate = text[:10]
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        return None


def select_oldest_core_incumbent(
    positions: Iterable[Any] | None,
    signal_date: Any,
    candidate_ticker: Any,
) -> dict[str, Any]:
    """Return an auditable oldest-core rotation decision.

    Eligible incumbents are core positions whose ``entry_date`` is no later
    than ``signal_date``.  The fresh candidate itself, future-dated positions,
    and non-core sleeves are excluded.  Selection is deterministic: earliest
    entry date first, then ticker lexicographically, then source-list order.

    ``position`` returns the original selected object for direct execution;
    the remaining selection and exclusion fields form the stable audit record.
    No market data or outcome field is inspected.
    """

    as_of = _iso_date(signal_date)
    if as_of is None:
        raise ValueError("signal_date must contain a valid ISO calendar date")
    candidate = _ticker(candidate_ticker)
    if not candidate:
        raise ValueError("candidate_ticker must be non-empty")

    source_positions = list(positions or [])
    eligible: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []

    for source_index, position in enumerate(source_positions):
        ticker = _ticker(_field(position, "ticker"))
        entry_date = _iso_date(_field(position, "entry_date"))
        sleeve = str(_field(position, "sleeve", "core") or "core").strip().lower()

        reason: str | None = None
        if not ticker:
            reason = "missing_ticker"
        elif ticker == candidate:
            reason = "candidate_ticker"
        elif sleeve != "core":
            reason = "non_core_sleeve"
        elif entry_date is None:
            reason = "missing_or_invalid_entry_date"
        elif entry_date > as_of:
            reason = "future_dated"

        row = {
            "source_index": source_index,
            "ticker": ticker or None,
            "entry_date": entry_date,
            "sleeve": sleeve,
        }
        if reason is not None:
            exclusions.append({**row, "reason": reason})
        else:
            eligible.append(row)

    eligible.sort(
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
            row["source_index"],
        )
    )
    selected = eligible[0] if eligible else None

    excluded_counts: dict[str, int] = {}
    for row in exclusions:
        reason = row["reason"]
        excluded_counts[reason] = excluded_counts.get(reason, 0) + 1

    return {
        "policy_version": POLICY_VERSION,
        "status": "selected" if selected else "no_eligible_incumbent",
        "decision": "rotate" if selected else "no_rotation",
        "reason": (
            "oldest_eligible_core_selected"
            if selected
            else "no_eligible_core_position"
        ),
        "signal_date": as_of,
        "candidate_ticker": candidate,
        "selected_position_index": (
            selected["source_index"] if selected is not None else None
        ),
        "position": (
            source_positions[selected["source_index"]]
            if selected is not None
            else None
        ),
        "ticker": selected["ticker"] if selected is not None else None,
        "entry_date": selected["entry_date"] if selected is not None else None,
        "selected_ticker": selected["ticker"] if selected is not None else None,
        "selected_entry_date": (
            selected["entry_date"] if selected is not None else None
        ),
        "considered_count": len(source_positions),
        "eligible_count": len(eligible),
        "excluded_counts": excluded_counts,
        "eligible_positions": eligible,
        "excluded_positions": exclusions,
    }
