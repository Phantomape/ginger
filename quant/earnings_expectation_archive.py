"""Earnings expectation archive.

This module snapshots expectation-related fields so the system can study
expectation drift over time instead of only current EPS values.

Design goals:
- replayable
- append-only snapshots
- provider-agnostic
- no trading logic
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE_DIR = DEFAULT_ROOT / "data" / "daily" / "earnings_expectations"


@dataclass
class EarningsExpectationSnapshot:
    ticker: str
    captured_at: str

    eps_estimate_current_qtr: float | None = None
    eps_estimate_next_qtr: float | None = None
    revenue_estimate_current_qtr: float | None = None
    revenue_estimate_next_qtr: float | None = None

    analyst_count_current_qtr: int | None = None
    analyst_count_next_qtr: int | None = None

    trailing_eps_actual: float | None = None
    trailing_revenue_actual: float | None = None

    guidance_sentiment: str | None = None
    surprise_history_strength: str | None = None

    provider: str | None = None
    source_version: str | None = None


def snapshot_path(day=None, root=DEFAULT_ARCHIVE_DIR):
    day = day or datetime.now(timezone.utc).strftime("%Y%m%d")
    return Path(root) / f"earnings_expectations_{day}.json"


def load_snapshot(day=None, root=DEFAULT_ARCHIVE_DIR):
    path = snapshot_path(day, root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def append_snapshot(snapshot, root=DEFAULT_ARCHIVE_DIR):
    """Append/update one ticker snapshot for a trading day."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    day = snapshot.captured_at[:10].replace("-", "")
    path = snapshot_path(day, root)

    payload = load_snapshot(day, root)
    payload[snapshot.ticker.upper()] = asdict(snapshot)

    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def compute_revision_features(current_snapshot, previous_snapshot=None):
    """Compute replayable expectation drift features."""
    current_snapshot = current_snapshot or {}
    previous_snapshot = previous_snapshot or {}

    def _f(value):
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    cur_eps = _f(current_snapshot.get("eps_estimate_current_qtr"))
    prev_eps = _f(previous_snapshot.get("eps_estimate_current_qtr"))

    cur_rev = _f(current_snapshot.get("revenue_estimate_current_qtr"))
    prev_rev = _f(previous_snapshot.get("revenue_estimate_current_qtr"))

    eps_revision_pct = None
    if cur_eps is not None and prev_eps not in (None, 0):
        eps_revision_pct = round((cur_eps - prev_eps) / abs(prev_eps), 6)

    revenue_revision_pct = None
    if cur_rev is not None and prev_rev not in (None, 0):
        revenue_revision_pct = round((cur_rev - prev_rev) / abs(prev_rev), 6)

    analyst_delta = None
    cur_analysts = current_snapshot.get("analyst_count_current_qtr")
    prev_analysts = previous_snapshot.get("analyst_count_current_qtr")
    if cur_analysts is not None and prev_analysts is not None:
        analyst_delta = int(cur_analysts) - int(prev_analysts)

    return {
        "eps_revision_pct": eps_revision_pct,
        "revenue_revision_pct": revenue_revision_pct,
        "analyst_count_delta": analyst_delta,
        "guidance_sentiment": current_snapshot.get("guidance_sentiment"),
        "surprise_history_strength": current_snapshot.get("surprise_history_strength"),
    }


def build_expectation_surface(ticker, snapshots_by_day):
    """Build longitudinal expectation surface from historical snapshots."""
    rows = []
    for day in sorted(snapshots_by_day):
        snap = snapshots_by_day[day]
        rows.append({
            "day": day,
            "eps_estimate_current_qtr": snap.get("eps_estimate_current_qtr"),
            "revenue_estimate_current_qtr": snap.get("revenue_estimate_current_qtr"),
            "analyst_count_current_qtr": snap.get("analyst_count_current_qtr"),
            "guidance_sentiment": snap.get("guidance_sentiment"),
        })

    return {
        "ticker": ticker,
        "history_points": len(rows),
        "surface": rows,
    }
