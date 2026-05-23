"""Expectation drift surface.

This module converts archived expectation snapshots into replayable expectation
state features:
- revision velocity
- revision acceleration
- analyst participation change
- expectation persistence

Goal:
- move from static EPS fields to expectation trajectory modeling
- measure how expectations evolve through time
- support future PEAD / continuation attribution

Read-only by design.
"""

from __future__ import annotations


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize(value, lo, hi):
    if hi <= lo:
        return 0.5
    value = max(lo, min(hi, value))
    return (value - lo) / (hi - lo)


def _safe_pct_change(current, previous):
    current = _float(current, None)
    previous = _float(previous, None)
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / abs(previous)


def compute_expectation_drift_state(
    *,
    current_snapshot,
    snapshot_7d_ago=None,
    snapshot_30d_ago=None,
):
    """Build replayable expectation drift state for one ticker."""
    current_snapshot = current_snapshot or {}
    snapshot_7d_ago = snapshot_7d_ago or {}
    snapshot_30d_ago = snapshot_30d_ago or {}

    cur_eps = current_snapshot.get("eps_estimate_current_qtr")
    eps_7d = snapshot_7d_ago.get("eps_estimate_current_qtr")
    eps_30d = snapshot_30d_ago.get("eps_estimate_current_qtr")

    rev_7d = _safe_pct_change(cur_eps, eps_7d)
    rev_30d = _safe_pct_change(cur_eps, eps_30d)

    acceleration = None
    if rev_7d is not None and rev_30d is not None:
        acceleration = rev_7d - rev_30d

    cur_analysts = current_snapshot.get("analyst_count_current_qtr")
    analysts_30d = snapshot_30d_ago.get("analyst_count_current_qtr")
    analyst_delta = None
    if cur_analysts is not None and analysts_30d is not None:
        analyst_delta = int(cur_analysts) - int(analysts_30d)

    persistence = 0.5
    if rev_7d is not None and rev_30d is not None:
        if rev_7d > 0 and rev_30d > 0:
            persistence = 0.85
        elif rev_7d < 0 and rev_30d < 0:
            persistence = 0.15
        elif rev_7d > 0 and rev_30d <= 0:
            persistence = 0.65
        elif rev_7d < 0 and rev_30d >= 0:
            persistence = 0.35

    score = (
        0.40 * _normalize(_float(rev_7d, 0.0), -0.25, 0.25)
        + 0.35 * _normalize(_float(rev_30d, 0.0), -0.40, 0.40)
        + 0.15 * _normalize(_float(acceleration, 0.0), -0.20, 0.20)
        + 0.10 * _normalize(_float(analyst_delta, 0.0), -10, 10)
    )

    return {
        "expectation_drift_score": round(score, 6),
        "eps_revision_velocity_7d": round(rev_7d, 6) if rev_7d is not None else None,
        "eps_revision_velocity_30d": round(rev_30d, 6) if rev_30d is not None else None,
        "eps_revision_acceleration": round(acceleration, 6) if acceleration is not None else None,
        "analyst_participation_delta_30d": analyst_delta,
        "expectation_persistence": round(persistence, 6),
        "expectation_state": (
            "strong_positive_revision"
            if score >= 0.75 else
            "positive_revision"
            if score >= 0.60 else
            "neutral"
            if score >= 0.40 else
            "negative_revision"
        ),
    }


def build_expectation_drift_surface(snapshot_history):
    """Build expectation drift surface from historical snapshot map.

    snapshot_history format:

    {
      "META": {
         "current": {...},
         "7d": {...},
         "30d": {...}
      }
    }
    """
    rows = []

    for ticker, snapshots in sorted((snapshot_history or {}).items()):
        metrics = compute_expectation_drift_state(
            current_snapshot=snapshots.get("current"),
            snapshot_7d_ago=snapshots.get("7d"),
            snapshot_30d_ago=snapshots.get("30d"),
        )

        rows.append({
            "ticker": str(ticker).upper(),
            **metrics,
        })

    ranked = sorted(
        rows,
        key=lambda r: r["expectation_drift_score"],
        reverse=True,
    )

    return {
        "schema_version": 1,
        "read_only": True,
        "leaders": ranked[:25],
        "negative_revision": ranked[-15:],
        "distribution": {
            "avg_score": round(sum(r["expectation_drift_score"] for r in ranked) / len(ranked), 6) if ranked else None,
            "strong_positive_revision_count": sum(1 for r in ranked if r["expectation_state"] == "strong_positive_revision"),
            "negative_revision_count": sum(1 for r in ranked if r["expectation_state"] == "negative_revision"),
        },
    }
