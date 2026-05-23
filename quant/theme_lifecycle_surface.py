"""Theme lifecycle surface.

This module measures whether a theme is emerging, broadening, entering mania,
exhausting, or collapsing.

Goal:
- distinguish durable theme leadership from late-stage crowded moves
- turn raw theme density into lifecycle state
- support future theme-aware allocation attribution

Read-only by design.
"""

from __future__ import annotations


DEFAULT_THEME_MAP = {
    "ai": {
        "NVDA", "AMD", "AVGO", "TSM", "ASML", "AMAT", "LRCX", "MU",
        "SMCI", "DELL", "ARM", "CRDO", "ANET", "MRVL", "LITE", "COHR",
    },
    "ai_power": {"VST", "TLN", "CEG", "BE", "GEV", "ETN"},
    "crypto": {"COIN", "MSTR", "MARA", "RIOT", "IREN", "CIFR", "WULF", "CLSK"},
    "space": {"RKLB", "ASTS", "LUNR", "PL", "IRDM", "VSAT"},
    "mega_cap": {"META", "GOOG", "GOOGL", "AMZN", "MSFT", "AAPL", "NVDA", "TSLA"},
    "gold": {"GLD", "IAU", "GDX", "NEM", "AEM"},
}


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


def _theme_rows(features_dict, tickers):
    rows = []
    for ticker in tickers:
        f = (features_dict or {}).get(ticker) or (features_dict or {}).get(ticker.lower())
        if isinstance(f, dict):
            rows.append(f)
    return rows


def compute_theme_lifecycle_state(theme, rows):
    n = len(rows)
    if n == 0:
        return {
            "theme": theme,
            "members_in_universe": 0,
            "theme_lifecycle_state": "no_coverage",
            "theme_lifecycle_score": None,
        }

    breakout_count = sum(1 for f in rows if bool(f.get("breakout_20d")))
    volume_spike_count = sum(1 for f in rows if bool(f.get("volume_spike")))
    mom20_positive_count = sum(1 for f in rows if _float(f.get("momentum_20d_pct"), 0.0) > 0)
    mom60_positive_count = sum(1 for f in rows if _float(f.get("momentum_60d_pct"), 0.0) > 0)
    above_200ma_count = sum(1 for f in rows if f.get("above_200ma") is True)

    avg_mom20 = sum(_float(f.get("momentum_20d_pct"), 0.0) for f in rows) / n
    avg_mom60 = sum(_float(f.get("momentum_60d_pct"), 0.0) for f in rows) / n
    avg_trend = sum(_float(f.get("trend_score"), 0.0) for f in rows) / n

    breadth = mom20_positive_count / n
    breakout_breadth = breakout_count / n
    volume_breadth = volume_spike_count / n
    trend_breadth = above_200ma_count / n
    acceleration = avg_mom20 - avg_mom60

    lifecycle_score = (
        0.25 * breadth
        + 0.20 * breakout_breadth
        + 0.15 * trend_breadth
        + 0.15 * avg_trend
        + 0.15 * _normalize(avg_mom20, -0.20, 0.50)
        + 0.10 * _normalize(acceleration, -0.30, 0.30)
    )

    # Lifecycle state is intentionally rule-explainable, not fit.
    if breadth >= 0.80 and breakout_breadth >= 0.45 and avg_mom20 >= 0.12:
        state = "mania"
    elif breadth >= 0.65 and acceleration > 0.03 and avg_mom20 > 0.04:
        state = "expansion"
    elif breadth >= 0.35 and acceleration > 0.02 and avg_mom20 > 0:
        state = "birth"
    elif breadth >= 0.55 and acceleration < -0.05 and volume_breadth >= 0.20:
        state = "exhaustion"
    elif breadth <= 0.35 and avg_mom20 < -0.05:
        state = "collapse"
    else:
        state = "neutral"

    return {
        "theme": theme,
        "members_in_universe": n,
        "theme_lifecycle_state": state,
        "theme_lifecycle_score": round(lifecycle_score, 6),
        "breadth": round(breadth, 4),
        "breakout_breadth": round(breakout_breadth, 4),
        "volume_spike_breadth": round(volume_breadth, 4),
        "above_200ma_breadth": round(trend_breadth, 4),
        "avg_momentum_20d_pct": round(avg_mom20, 6),
        "avg_momentum_60d_pct": round(avg_mom60, 6),
        "momentum_acceleration": round(acceleration, 6),
        "avg_trend_score": round(avg_trend, 4),
        "members": sorted(str(f.get("ticker")).upper() for f in rows if f.get("ticker")),
    }


def build_theme_lifecycle_surface(features_dict, theme_map=None):
    theme_map = theme_map or DEFAULT_THEME_MAP
    rows = []
    for theme, tickers in sorted(theme_map.items()):
        rows.append(compute_theme_lifecycle_state(theme, _theme_rows(features_dict, tickers)))

    active = [r for r in rows if r.get("theme_lifecycle_score") is not None]
    return {
        "schema_version": 1,
        "read_only": True,
        "themes": sorted(active, key=lambda r: r.get("theme_lifecycle_score", 0), reverse=True),
        "state_counts": {
            state: sum(1 for r in active if r.get("theme_lifecycle_state") == state)
            for state in ["birth", "expansion", "mania", "exhaustion", "collapse", "neutral"]
        },
        "highest_heat_themes": sorted(
            [r for r in active if r.get("theme_lifecycle_state") in {"mania", "exhaustion"}],
            key=lambda r: r.get("theme_lifecycle_score", 0),
            reverse=True,
        ),
        "notes": [
            "Read-only theme lifecycle surface.",
            "Use for attribution before any theme-conditioned allocation changes.",
        ],
    }
