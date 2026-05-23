"""Continuous cross-sectional ranking surface.

This module builds continuous alpha scores from replayable context layers:
- trend
- relative strength
- breadth participation
- theme density
- expectation revision state
- post-earnings drift state

It is intentionally read-only:
- no signal gating
- no sizing
- no order generation
- no slot mutation

The goal is to measure whether continuous ranking contains more information than
hard threshold breakout logic.
"""

from __future__ import annotations


DEFAULT_COMPONENT_WEIGHTS = {
    "trend": 0.30,
    "relative_strength": 0.25,
    "expectation_revision": 0.20,
    "post_earnings_drift": 0.10,
    "theme_participation": 0.10,
    "breadth_alignment": 0.05,
}


def _float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


THEME_TICKERS = {
    "ai": {
        "NVDA", "AMD", "AVGO", "TSM", "ASML", "AMAT", "LRCX", "MU",
        "SMCI", "DELL", "ARM", "CRDO", "ANET", "MRVL",
    },
    "crypto": {"COIN", "MSTR", "MARA", "RIOT", "IREN", "CIFR", "WULF"},
    "space": {"RKLB", "ASTS", "LUNR", "PL"},
    "mega_cap": {"META", "MSFT", "AMZN", "GOOG", "NVDA", "AAPL"},
}


def _themes(ticker):
    t = str(ticker or "").upper()
    return [theme for theme, members in THEME_TICKERS.items() if t in members]


def _normalize(value, lo, hi):
    if hi <= lo:
        return 0.5
    value = max(lo, min(hi, value))
    return (value - lo) / (hi - lo)


def build_component_scores(
    ticker,
    features,
    *,
    breadth_context=None,
    theme_density_context=None,
    expectation_context=None,
):
    """Build replayable component scores for one ticker."""
    ticker = str(ticker or "").upper()
    features = features or {}

    trend_score = _float(features.get("trend_score"), 0.0)
    breakout = 1.0 if features.get("breakout_20d") else 0.0
    above_200ma = 1.0 if features.get("above_200ma") else 0.0

    momentum20 = _float(features.get("momentum_20d_pct"), 0.0)
    momentum60 = _float(features.get("momentum_60d_pct"), 0.0)
    rs_component = (
        0.60 * _normalize(momentum20, -0.20, 0.40)
        + 0.40 * _normalize(momentum60, -0.40, 0.80)
    )

    trend_component = (
        0.50 * trend_score
        + 0.25 * breakout
        + 0.25 * above_200ma
    )

    breadth_alignment = 0.5
    breadth_context = breadth_context or {}
    if momentum20 > 0:
        breadth_alignment += 0.25 * _float(
            breadth_context.get("momentum_20d_positive_fraction"),
            0.5,
        )
    if breakout:
        breadth_alignment += 0.25 * _float(
            breadth_context.get("breakout_20d_fraction"),
            0.0,
        )
    breadth_alignment = min(1.0, breadth_alignment)

    theme_participation = 0.5
    theme_density_context = theme_density_context or {}
    ticker_themes = _themes(ticker)
    if ticker_themes:
        vals = []
        for theme in ticker_themes:
            theme_data = (
                (theme_density_context.get("themes") or {}).get(theme)
                or {}
            )
            vals.append(
                _normalize(
                    _float(theme_data.get("breakout_count"), 0.0),
                    0,
                    6,
                )
            )
        if vals:
            theme_participation = sum(vals) / len(vals)

    expectation_revision = 0.5
    expectation_context = expectation_context or {}
    for row in expectation_context.get("rows", []):
        if str(row.get("ticker") or "").upper() != ticker:
            continue
        avg_surprise = _float(row.get("avg_historical_surprise_pct"), 0.0)
        expectation_revision = _normalize(avg_surprise, -20, 20)
        break

    post_earnings_drift = 0.5
    avg_surprise = _float(features.get("avg_historical_surprise_pct"), 0.0)
    if avg_surprise > 0 and momentum20 > 0:
        post_earnings_drift = 0.8
    elif avg_surprise < 0 and momentum20 < 0:
        post_earnings_drift = 0.2

    return {
        "trend": round(trend_component, 4),
        "relative_strength": round(rs_component, 4),
        "expectation_revision": round(expectation_revision, 4),
        "post_earnings_drift": round(post_earnings_drift, 4),
        "theme_participation": round(theme_participation, 4),
        "breadth_alignment": round(breadth_alignment, 4),
    }


def compute_alpha_score(component_scores, weights=None):
    """Continuous alpha score from weighted replayable components."""
    weights = weights or DEFAULT_COMPONENT_WEIGHTS
    score = 0.0
    for key, weight in weights.items():
        score += weight * _float(component_scores.get(key), 0.0)
    return round(score, 6)


def build_cross_sectional_ranking_surface(
    features_dict,
    *,
    breadth_context=None,
    theme_density_context=None,
    expectation_context=None,
    weights=None,
):
    """Return continuous ranking surface across the full universe."""
    rows = []

    for ticker, features in sorted((features_dict or {}).items()):
        if not isinstance(features, dict):
            continue

        components = build_component_scores(
            ticker,
            features,
            breadth_context=breadth_context,
            theme_density_context=theme_density_context,
            expectation_context=expectation_context,
        )

        alpha_score = compute_alpha_score(components, weights)

        rows.append({
            "ticker": str(ticker).upper(),
            "alpha_score": alpha_score,
            "components": components,
            "themes": _themes(ticker),
            "breakout_20d": bool(features.get("breakout_20d")),
            "trend_score": _float(features.get("trend_score"), 0.0),
            "momentum_20d_pct": _float(features.get("momentum_20d_pct"), 0.0),
            "momentum_60d_pct": _float(features.get("momentum_60d_pct"), 0.0),
        })

    ranked = sorted(rows, key=lambda r: r["alpha_score"], reverse=True)

    return {
        "schema_version": 1,
        "read_only": True,
        "weights": weights or DEFAULT_COMPONENT_WEIGHTS,
        "universe_count": len(ranked),
        "leaders": ranked[:25],
        "laggards": ranked[-15:],
        "distribution": {
            "max_alpha_score": ranked[0]["alpha_score"] if ranked else None,
            "min_alpha_score": ranked[-1]["alpha_score"] if ranked else None,
            "avg_alpha_score": round(sum(r["alpha_score"] for r in ranked) / len(ranked), 6) if ranked else None,
        },
        "notes": [
            "Continuous replayable ranking surface.",
            "No signal gating or sizing decisions are made here.",
            "The goal is to evaluate whether continuous ranking contains more predictive information than hard thresholds.",
        ],
    }
