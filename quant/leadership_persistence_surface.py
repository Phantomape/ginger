"""Leadership persistence surface.

This module measures whether relative strength leadership is persistent,
accelerating, broadening, or collapsing.

Goal:
- move beyond one-day breakout logic
- identify durable cross-sectional leadership
- build replayable leadership state history

Read-only by design.
"""

from __future__ import annotations


def _float(value, default=0.0):
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


def compute_leadership_persistence(features):
    """Compute continuous leadership persistence score from replayable features."""
    features = features or {}

    mom10 = _float(features.get("momentum_10d_pct"), 0.0)
    mom20 = _float(features.get("momentum_20d_pct"), 0.0)
    mom60 = _float(features.get("momentum_60d_pct"), 0.0)
    trend = _float(features.get("trend_score"), 0.0)
    above_200ma = 1.0 if features.get("above_200ma") else 0.0
    breakout = 1.0 if features.get("breakout_20d") else 0.0

    # Persistence prefers aligned medium-term momentum, not short-term spikes.
    persistence = (
        0.20 * _normalize(mom10, -0.15, 0.25)
        + 0.45 * _normalize(mom20, -0.25, 0.50)
        + 0.35 * _normalize(mom60, -0.40, 1.00)
    )

    structure = (
        0.50 * trend
        + 0.25 * above_200ma
        + 0.25 * breakout
    )

    acceleration = _normalize(mom20 - mom60, -0.30, 0.30)

    score = (
        0.60 * persistence
        + 0.25 * structure
        + 0.15 * acceleration
    )

    return {
        "leadership_persistence_score": round(score, 6),
        "leadership_persistence_component": round(persistence, 6),
        "leadership_structure_component": round(structure, 6),
        "leadership_acceleration_component": round(acceleration, 6),
        "leadership_state": (
            "persistent_leader"
            if score >= 0.75 else
            "emerging_leader"
            if score >= 0.60 else
            "neutral"
            if score >= 0.40 else
            "weakening"
        ),
    }


def build_leadership_surface(features_dict):
    rows = []
    for ticker, features in sorted((features_dict or {}).items()):
        if not isinstance(features, dict):
            continue

        metrics = compute_leadership_persistence(features)
        rows.append({
            "ticker": str(ticker).upper(),
            **metrics,
            "momentum_20d_pct": _float(features.get("momentum_20d_pct"), 0.0),
            "momentum_60d_pct": _float(features.get("momentum_60d_pct"), 0.0),
        })

    ranked = sorted(
        rows,
        key=lambda r: r["leadership_persistence_score"],
        reverse=True,
    )

    return {
        "schema_version": 1,
        "read_only": True,
        "leaders": ranked[:25],
        "weakening": ranked[-15:],
        "distribution": {
            "avg_score": round(sum(r["leadership_persistence_score"] for r in ranked) / len(ranked), 6) if ranked else None,
            "persistent_leader_count": sum(1 for r in ranked if r["leadership_state"] == "persistent_leader"),
            "emerging_leader_count": sum(1 for r in ranked if r["leadership_state"] == "emerging_leader"),
            "weakening_count": sum(1 for r in ranked if r["leadership_state"] == "weakening"),
        },
    }
