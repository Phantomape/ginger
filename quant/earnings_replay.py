"""Point-in-time earnings replay helpers.

The canonical backtester can reconstruct days-to-earnings from a factual
calendar and supplement EPS/surprise fields from persisted production snapshots.
This is useful, but it is unsafe to attach an EPS estimate from a snapshot whose
stored next earnings date does not match the replayed event date.

This module centralizes safer earnings replay behavior:
- prefer production earnings snapshots when they contain a valid future event;
- recompute DTE from the selected event date and replay date;
- attach EPS estimate only when it belongs to the same replayed event;
- allow historical surprise fields as PIT snapshot context;
- expose source metadata so parity gaps are visible, not silent.

Read-only utility: no trading logic, sizing, ranking, or order generation.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd


def _coerce_date(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return pd.Timestamp(value).date()
    except Exception:
        return None


def _date_key(value) -> str:
    d = _coerce_date(value)
    if d is not None:
        return d.strftime("%Y%m%d")
    return str(value).replace("-", "")[:8]


def _busday_count(start, end):
    start_d = _coerce_date(start)
    end_d = _coerce_date(end)
    if start_d is None or end_d is None:
        return None
    try:
        return int(np.busday_count(start_d, end_d))
    except Exception:
        return None


def _select_snapshot_on_or_before(earnings_snapshots, today):
    """Return (snapshot_date, snapshot_payload) for latest snapshot <= today."""
    snapshots = earnings_snapshots or {}
    today_key = _date_key(today)
    candidates = [str(key) for key in snapshots if str(key) <= today_key]
    if not candidates:
        return None, None
    key = max(candidates)
    return key, snapshots.get(key) or {}


def _first_future_event(calendar_dates, today):
    today_d = _coerce_date(today)
    if today_d is None:
        return None
    future = sorted(
        d for d in (_coerce_date(x) for x in (calendar_dates or []))
        if d is not None and d > today_d
    )
    return future[0] if future else None


def build_replayed_earnings_dict(
    *,
    today,
    calendar_dates,
    ticker=None,
    earnings_snapshots=None,
):
    """Build PIT-safer earnings input for feature_layer.compute_features.

    EPS estimate is event-specific and is attached only when the snapshot's
    stored next earnings date matches the selected replay event. This prevents
    silent mismatches such as: calendar says event A, but latest available
    snapshot is already pointing at event B after a newly reported quarter.
    """
    today_d = _coerce_date(today)
    base = {
        "next_earnings_date": None,
        "days_to_earnings": None,
        "eps_estimate": None,
        "eps_actual_last": None,
        "historical_surprise_pct": [],
        "avg_historical_surprise_pct": None,
        "earnings_replay_source": "none",
        "earnings_snapshot_date": None,
        "earnings_event_match": None,
        "eps_estimate_pit_status": "not_available",
    }
    if today_d is None:
        return base

    ticker_key = str(ticker or "").upper()
    snapshot_date, snapshot_payload = _select_snapshot_on_or_before(
        earnings_snapshots,
        today_d,
    )
    snapshot_row = {}
    if ticker_key and isinstance(snapshot_payload, dict):
        snapshot_row = (
            snapshot_payload.get(ticker_key)
            or snapshot_payload.get(str(ticker or ""))
            or {}
        )
        if not isinstance(snapshot_row, dict):
            snapshot_row = {}

    snapshot_next = _coerce_date(snapshot_row.get("next_earnings_date"))
    calendar_next = _first_future_event(calendar_dates, today_d)

    # Prefer production's persisted event date when it is a valid future event.
    # This improves latest-window production/backtest comparability because the
    # production run used the same DTE source embedded in the snapshot.
    if snapshot_next is not None and snapshot_next > today_d:
        event_date = snapshot_next
        source = "earnings_snapshot"
    else:
        event_date = calendar_next
        source = "calendar_fallback" if event_date is not None else "none"

    if event_date is not None:
        base["next_earnings_date"] = event_date.isoformat()
        base["days_to_earnings"] = _busday_count(today_d, event_date)
    base["earnings_replay_source"] = source
    base["earnings_snapshot_date"] = snapshot_date

    same_event = (
        snapshot_next is not None
        and event_date is not None
        and snapshot_next == event_date
    )
    base["earnings_event_match"] = bool(same_event) if snapshot_row else None

    if same_event and snapshot_row.get("eps_estimate") is not None:
        base["eps_estimate"] = snapshot_row.get("eps_estimate")
        base["eps_estimate_pit_status"] = "snapshot_same_event"
    elif snapshot_row.get("eps_estimate") is not None:
        base["eps_estimate_pit_status"] = "blocked_event_mismatch"

    # These describe already-known historical context as of the snapshot date.
    if snapshot_row.get("eps_actual_last") is not None:
        base["eps_actual_last"] = snapshot_row.get("eps_actual_last")
    if snapshot_row.get("avg_historical_surprise_pct") is not None:
        base["avg_historical_surprise_pct"] = snapshot_row.get("avg_historical_surprise_pct")
    if snapshot_row.get("historical_surprise_pct"):
        base["historical_surprise_pct"] = snapshot_row.get("historical_surprise_pct")

    return base
