"""Residual strength surface.

This module removes broad market / theme beta from raw momentum so the system
can distinguish:
- true cross-sectional leadership
vs
- passive beta participation.

Goal:
- move from absolute momentum to residual momentum
- identify durable leaders within strong themes
- reduce fake alpha caused by broad market beta

Read-only by design.
"""

from __future__ import annotations


THEME_TICKERS = {
    "ai": {
        "NVDA", "AMD", "AVGO", "TSM", "ASML", "AMAT", "LRCX", "MU",
        "SMCI", "DELL", "ARM", "CRDO", "ANET", "MRVL",
    },
    "crypto": {"COIN", "MSTR", "MARA", "RIOT", "IREN", "CIFR", "WULF"},
    "space": {"RKLB", "ASTS", "LUNR", "PL"},
    "mega_cap": {"META", "MSFT", "AMZN", "GOOG", "NVDA", "AAPL"},
}


def _float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _themes(ticker):
    t = str(ticker or "").upper()
    return [theme for theme, members in THEME_TICKERS.items() if t in members]


def _theme_average(features_dict, tickers, key):
    vals = []
    for ticker in tickers:
        f = (features_dict or {}).get(ticker) or (features_dict or {}).get(ticker.lower())
        if isinstance(f, dict):
            value = _float(f.get(key), None)
            if value is not None:
                vals.append(value)
    if not vals:
        return None
    return sum(vals) / len(vals)


def _sector_average(features_dict, sector, key):
    if not sector or sector == "Unknown":
        return None
    vals = []
    for features in (features_dict or {}).values():
        if not isinstance(features, dict):
            continue
        if str(features.get("sector") or "Unknown") != sector:
            continue
        value = _float(features.get(key), None)
        if value is not None:
            vals.append(value)
    if not vals:
        return None
    return sum(vals) / len(vals)


def compute_residual_strength(
    ticker,
    features,
    *,
    features_dict,
):
    """Compute replayable residual strength state."""
    ticker = str(ticker or "").upper()
    features = features or {}

    mom20 = _float(features.get("momentum_20d_pct"), None)
    mom60 = _float(features.get("momentum_60d_pct"), None)
    if mom20 is None:
        return None

    spy = (features_dict or {}).get("SPY") or {}
    qqq = (features_dict or {}).get("QQQ") or {}

    spy20 = _float(spy.get("momentum_20d_pct"), 0.0)
    qqq20 = _float(qqq.get("momentum_20d_pct"), 0.0)
    sector = str(features.get("sector") or "Unknown")

    excess_spy20 = mom20 - spy20
    excess_qqq20 = mom20 - qqq20
    sector20 = _sector_average(features_dict, sector, "momentum_20d_pct")
    excess_sector20 = mom20 - sector20 if sector20 is not None else None

    theme_residuals = {}
    for theme in _themes(ticker):
        avg_theme20 = _theme_average(features_dict, THEME_TICKERS[theme], "momentum_20d_pct")
        if avg_theme20 is not None:
            theme_residuals[theme] = round(mom20 - avg_theme20, 6)

    # Conservative continuous residual score.
    residual_score = (
        0.45 * excess_spy20
        + 0.35 * excess_qqq20
        + 0.20 * max(theme_residuals.values())
        if theme_residuals else
        0.55 * excess_spy20 + 0.45 * excess_qqq20
    )

    state = (
        "strong_residual_leader"
        if residual_score >= 0.10 else
        "residual_leader"
        if residual_score >= 0.04 else
        "neutral"
        if residual_score >= -0.03 else
        "beta_lagging"
    )

    return {
        "ticker": ticker,
        "residual_strength_score": round(residual_score, 6),
        "ret20_excess_spy": round(excess_spy20, 6),
        "ret20_excess_qqq": round(excess_qqq20, 6),
        "ret20_excess_sector": round(excess_sector20, 6) if excess_sector20 is not None else None,
        "sector": sector,
        "theme_residuals": theme_residuals,
        "themes": _themes(ticker),
        "momentum_20d_pct": round(mom20, 6),
        "momentum_60d_pct": round(mom60, 6) if mom60 is not None else None,
        "residual_state": state,
    }


def build_residual_strength_surface(features_dict):
    rows = []
    for ticker, features in sorted((features_dict or {}).items()):
        if not isinstance(features, dict):
            continue
        result = compute_residual_strength(
            ticker,
            features,
            features_dict=features_dict,
        )
        if result is not None:
            rows.append(result)

    ranked = sorted(
        rows,
        key=lambda r: r["residual_strength_score"],
        reverse=True,
    )

    return {
        "schema_version": 1,
        "read_only": True,
        "leaders": ranked[:25],
        "laggards": ranked[-15:],
        "distribution": {
            "avg_score": round(sum(r["residual_strength_score"] for r in ranked) / len(ranked), 6) if ranked else None,
            "strong_residual_leader_count": sum(1 for r in ranked if r["residual_state"] == "strong_residual_leader"),
            "residual_leader_count": sum(1 for r in ranked if r["residual_state"] == "residual_leader"),
            "beta_lagging_count": sum(1 for r in ranked if r["residual_state"] == "beta_lagging"),
        },
        "notes": [
            "Read-only residual strength surface.",
            "Residual momentum attempts to separate true leadership from broad beta participation.",
        ],
    }
