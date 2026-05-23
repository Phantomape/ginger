"""Market-state attribution engine.

This module evaluates whether replayable market-state surfaces correspond to
better realized trade outcomes.

Surfaces currently supported:
- leadership persistence
- residual strength
- expectation drift
- theme lifecycle

The engine is intentionally read-only and attribution-only.
"""

from __future__ import annotations


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _r_multiple(trade):
    entry = _float(trade.get("entry_price"))
    stop = _float(trade.get("stop_price"))
    shares = _float(trade.get("shares"))
    pnl = _float(trade.get("pnl"), None)
    if pnl is None:
        pnl = _float(trade.get("profit_loss"), None)
    if entry is None or stop is None or shares is None or pnl is None:
        return None
    if entry <= stop or shares <= 0:
        return None
    risk = (entry - stop) * shares
    if risk <= 0:
        return None
    return pnl / risk


def _bucket(score):
    score = _float(score, None)
    if score is None:
        return "unknown"
    if score >= 0.75:
        return "elite"
    if score >= 0.60:
        return "strong"
    if score >= 0.40:
        return "neutral"
    return "weak"


def _surface_map(surface, key):
    rows = []
    if isinstance(surface, dict):
        rows.extend(surface.get("leaders") or [])
        rows.extend(surface.get("laggards") or [])
        rows.extend(surface.get("weakening") or [])
        rows.extend(surface.get("negative_revision") or [])
    out = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = row
    return out


def annotate_trade_market_state(
    trade,
    *,
    leadership_surface=None,
    residual_surface=None,
    expectation_surface=None,
):
    ticker = str(trade.get("ticker") or "").upper()

    leadership = (_surface_map(leadership_surface, "leadership_persistence_score").get(ticker) or {})
    residual = (_surface_map(residual_surface, "residual_strength_score").get(ticker) or {})
    expectation = (_surface_map(expectation_surface, "expectation_drift_score").get(ticker) or {})

    return {
        "ticker": ticker,
        "leadership_persistence_score": leadership.get("leadership_persistence_score"),
        "leadership_state": leadership.get("leadership_state"),
        "residual_strength_score": residual.get("residual_strength_score"),
        "residual_state": residual.get("residual_state"),
        "expectation_drift_score": expectation.get("expectation_drift_score"),
        "expectation_state": expectation.get("expectation_state"),
    }


def _summarize(trades):
    pnl_values = []
    r_values = []
    wins = 0

    for trade in trades:
        pnl = _float(trade.get("pnl"), None)
        if pnl is None:
            pnl = _float(trade.get("profit_loss"), None)
        if pnl is None:
            continue

        pnl_values.append(pnl)
        if pnl > 0:
            wins += 1

        r = _r_multiple(trade)
        if r is not None:
            r_values.append(r)

    n = len(pnl_values)
    return {
        "trades": n,
        "win_rate": round(wins / n, 4) if n else None,
        "total_pnl": round(sum(pnl_values), 2) if pnl_values else 0.0,
        "avg_pnl": round(sum(pnl_values) / n, 2) if n else None,
        "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else None,
        "worst_trade": round(min(pnl_values), 2) if pnl_values else None,
        "best_trade": round(max(pnl_values), 2) if pnl_values else None,
    }


def build_market_state_attribution(
    result,
    *,
    leadership_surface=None,
    residual_surface=None,
    expectation_surface=None,
    theme_lifecycle_surface=None,
):
    trades = []

    for trade in result.get("trades", []):
        enriched = dict(trade)
        enriched.update(
            annotate_trade_market_state(
                trade,
                leadership_surface=leadership_surface,
                residual_surface=residual_surface,
                expectation_surface=expectation_surface,
            )
        )
        trades.append(enriched)

    attribution = {}

    # Leadership attribution
    leadership_buckets = {}
    for trade in trades:
        leadership_buckets.setdefault(
            _bucket(trade.get("leadership_persistence_score")),
            [],
        ).append(trade)

    attribution["leadership_persistence"] = {
        bucket: _summarize(rows)
        for bucket, rows in leadership_buckets.items()
    }

    # Residual attribution
    residual_buckets = {}
    for trade in trades:
        residual_buckets.setdefault(
            _bucket(trade.get("residual_strength_score")),
            [],
        ).append(trade)

    attribution["residual_strength"] = {
        bucket: _summarize(rows)
        for bucket, rows in residual_buckets.items()
    }

    # Expectation attribution
    expectation_buckets = {}
    for trade in trades:
        expectation_buckets.setdefault(
            _bucket(trade.get("expectation_drift_score")),
            [],
        ).append(trade)

    attribution["expectation_drift"] = {
        bucket: _summarize(rows)
        for bucket, rows in expectation_buckets.items()
    }

    # Theme lifecycle attribution (coarse current snapshot only)
    if isinstance(theme_lifecycle_surface, dict):
        theme_states = {
            row.get("theme"): row.get("theme_lifecycle_state")
            for row in theme_lifecycle_surface.get("themes", [])
        }
        attribution["theme_lifecycle_snapshot"] = theme_states

    return {
        "schema_version": 1,
        "read_only": True,
        "source_expected_value_score": result.get("expected_value_score"),
        "source_period": result.get("period"),
        "market_state_attribution": attribution,
        "coverage": {
            "trades_total": len(result.get("trades", [])),
            "trades_with_leadership_state": sum(1 for t in trades if t.get("leadership_persistence_score") is not None),
            "trades_with_residual_state": sum(1 for t in trades if t.get("residual_strength_score") is not None),
            "trades_with_expectation_state": sum(1 for t in trades if t.get("expectation_drift_score") is not None),
        },
        "notes": [
            "Read-only market-state attribution layer.",
            "Use this to validate whether continuous market-state surfaces correspond to higher realized R / PnL.",
            "Do not wire these surfaces into live allocation until attribution demonstrates stable monotonic value.",
        ],
    }
