"""Canonical state vectors.

This module compresses the growing set of market-state surfaces into a small
number of canonical, high-information vectors.

Goal:
- reduce surface explosion
- keep the system evidence-first
- provide a stable representation for future ranking / attribution / allocation

Canonical vectors:
1. leadership_vector
2. expectation_vector
3. theme_structure_vector
4. risk_heat_vector
5. market_regime_vector

Read-only by design. This module must not alter entries, exits, rankings,
sizing, or orders unless a future experiment explicitly promotes it.
"""

from __future__ import annotations


def _float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def _normalize(value, lo, hi):
    if hi <= lo:
        return 0.5
    return _clamp((value - lo) / (hi - lo))


def _state_from_score(score, *, strong=0.70, weak=0.35):
    if score >= strong:
        return "strong"
    if score <= weak:
        return "weak"
    return "neutral"


def build_leadership_vector(
    *,
    leadership_row=None,
    residual_row=None,
    ranking_row=None,
):
    """Compress RS / residual / persistence into one leadership vector."""
    leadership_row = leadership_row or {}
    residual_row = residual_row or {}
    ranking_row = ranking_row or {}

    persistence = _float(leadership_row.get("leadership_persistence_score"), 0.5)
    residual = _normalize(_float(residual_row.get("residual_strength_score"), 0.0), -0.20, 0.25)
    rank_score = _float(ranking_row.get("alpha_score"), 0.5)
    acceleration = _float(
        leadership_row.get("leadership_acceleration_component"),
        0.5,
    )

    score = (
        0.35 * persistence
        + 0.30 * residual
        + 0.20 * rank_score
        + 0.15 * acceleration
    )

    return {
        "score": round(score, 6),
        "state": _state_from_score(score),
        "persistence": round(persistence, 6),
        "residual_strength": round(residual, 6),
        "rank_score": round(rank_score, 6),
        "acceleration": round(acceleration, 6),
        "source_states": {
            "leadership_state": leadership_row.get("leadership_state"),
            "residual_state": residual_row.get("residual_state"),
        },
    }


def build_expectation_vector(
    *,
    expectation_row=None,
    earnings_row=None,
):
    """Compress revision / PEAD / surprise into one expectation vector."""
    expectation_row = expectation_row or {}
    earnings_row = earnings_row or {}

    drift_score = _float(expectation_row.get("expectation_drift_score"), 0.5)
    persistence = _float(expectation_row.get("expectation_persistence"), 0.5)
    surprise = _normalize(_float(earnings_row.get("avg_historical_surprise_pct"), 0.0), -20, 20)
    pead_proxy = 0.6 if earnings_row.get("post_event_followthrough_proxy") == "positive" else 0.4 if earnings_row.get("post_event_followthrough_proxy") == "negative" else 0.5

    score = (
        0.45 * drift_score
        + 0.25 * persistence
        + 0.20 * surprise
        + 0.10 * pead_proxy
    )

    return {
        "score": round(score, 6),
        "state": _state_from_score(score),
        "revision_velocity_7d": expectation_row.get("eps_revision_velocity_7d"),
        "revision_velocity_30d": expectation_row.get("eps_revision_velocity_30d"),
        "revision_acceleration": expectation_row.get("eps_revision_acceleration"),
        "analyst_participation_delta_30d": expectation_row.get("analyst_participation_delta_30d"),
        "surprise_component": round(surprise, 6),
        "pead_proxy": round(pead_proxy, 6),
        "source_state": expectation_row.get("expectation_state"),
    }


def build_theme_structure_vector(*, theme_rows=None, ticker_themes=None):
    """Compress density / lifecycle / crowding into one theme structure vector."""
    theme_rows = theme_rows or []
    ticker_themes = ticker_themes or []
    by_theme = {row.get("theme"): row for row in theme_rows if row.get("theme")}

    relevant = [by_theme[t] for t in ticker_themes if t in by_theme]
    if not relevant:
        return {
            "score": 0.5,
            "state": "neutral",
            "themes": ticker_themes,
            "lifecycle_states": {},
            "crowding_risk": 0.0,
            "exhaustion_risk": 0.0,
        }

    lifecycle_scores = [_float(row.get("theme_lifecycle_score"), 0.5) for row in relevant]
    mania_count = sum(1 for row in relevant if row.get("theme_lifecycle_state") == "mania")
    exhaustion_count = sum(1 for row in relevant if row.get("theme_lifecycle_state") == "exhaustion")
    collapse_count = sum(1 for row in relevant if row.get("theme_lifecycle_state") == "collapse")

    raw_score = sum(lifecycle_scores) / len(lifecycle_scores)
    crowding_risk = mania_count / len(relevant)
    exhaustion_risk = (exhaustion_count + collapse_count) / len(relevant)

    # Theme strength is useful, but late-stage crowding/exhaustion reduces quality.
    quality_score = _clamp(raw_score - 0.15 * crowding_risk - 0.25 * exhaustion_risk)

    return {
        "score": round(quality_score, 6),
        "state": _state_from_score(quality_score),
        "themes": ticker_themes,
        "lifecycle_states": {row.get("theme"): row.get("theme_lifecycle_state") for row in relevant},
        "raw_lifecycle_score": round(raw_score, 6),
        "crowding_risk": round(crowding_risk, 6),
        "exhaustion_risk": round(exhaustion_risk, 6),
    }


def build_risk_heat_vector(*, portfolio_heat=None, theme_vector=None, market_regime_vector=None):
    """Compress heat / crowding / regime stress into one risk vector."""
    portfolio_heat = portfolio_heat or {}
    theme_vector = theme_vector or {}
    market_regime_vector = market_regime_vector or {}

    explicit_heat = _float(portfolio_heat.get("heat_score"), 0.5)
    crowding = _float(theme_vector.get("crowding_risk"), 0.0)
    exhaustion = _float(theme_vector.get("exhaustion_risk"), 0.0)
    regime_stress = 1.0 - _float(market_regime_vector.get("score"), 0.5)

    risk = _clamp(
        0.40 * explicit_heat
        + 0.25 * crowding
        + 0.20 * exhaustion
        + 0.15 * regime_stress
    )

    return {
        "score": round(risk, 6),
        "state": "hot" if risk >= 0.70 else "cool" if risk <= 0.35 else "normal",
        "heat": round(explicit_heat, 6),
        "crowding": round(crowding, 6),
        "exhaustion": round(exhaustion, 6),
        "regime_stress": round(regime_stress, 6),
    }


def build_market_regime_vector(*, market_regime=None, breadth_context=None, sentiment=None):
    """Compress regime / breadth / sentiment into one market regime vector."""
    market_regime = market_regime or {}
    breadth_context = breadth_context or {}
    sentiment = sentiment or {}

    regime_name = str(market_regime.get("regime") or "UNKNOWN").upper()
    if regime_name in {"BULL", "RISK_ON", "AGGRESSIVE"}:
        regime_score = 0.75
    elif regime_name in {"BEAR", "RISK_OFF", "DEFENSIVE"}:
        regime_score = 0.25
    else:
        regime_score = 0.50

    breadth = _float(breadth_context.get("momentum_20d_positive_fraction"), 0.5)
    breakout_breadth = _float(breadth_context.get("breakout_20d_fraction"), 0.0)

    sentiment_name = str(sentiment.get("sentiment") or "baseline")
    if sentiment_name in {"healthy_trend", "low_vol_grind"}:
        sentiment_score = 0.75
    elif sentiment_name in {"panic_risk_off", "choppy_uncertain"}:
        sentiment_score = 0.25
    elif sentiment_name == "theme_mania":
        sentiment_score = 0.60
    else:
        sentiment_score = 0.50

    score = (
        0.40 * regime_score
        + 0.35 * breadth
        + 0.15 * breakout_breadth
        + 0.10 * sentiment_score
    )

    return {
        "score": round(score, 6),
        "state": _state_from_score(score),
        "regime": regime_name,
        "breadth": round(breadth, 6),
        "breakout_breadth": round(breakout_breadth, 6),
        "sentiment": sentiment_name,
    }


def _rows_by_ticker(surface, row_keys=("leaders", "laggards", "weakening", "negative_revision")):
    rows = []
    if isinstance(surface, dict):
        for key in row_keys:
            rows.extend(surface.get(key) or [])
        rows.extend(surface.get("rows") or [])
    out = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = row
    return out


def build_canonical_state_vectors(
    *,
    market_state_bundle,
    breadth_context=None,
    earnings_context=None,
    post_earnings_context=None,
    market_regime=None,
    portfolio_heat=None,
    sentiment=None,
):
    """Build canonical vectors for all tickers covered by the market-state bundle."""
    market_state_bundle = market_state_bundle or {}
    breadth_context = breadth_context or {}
    earnings_context = earnings_context or {}
    post_earnings_context = post_earnings_context or {}

    leadership_rows = _rows_by_ticker(market_state_bundle.get("leadership_persistence_surface"))
    residual_rows = _rows_by_ticker(market_state_bundle.get("residual_strength_surface"))
    ranking_rows = _rows_by_ticker(market_state_bundle.get("cross_sectional_ranking_surface"))
    expectation_rows = _rows_by_ticker(market_state_bundle.get("expectation_drift_surface"))

    earnings_rows = {
        str(row.get("ticker") or "").upper(): row
        for row in earnings_context.get("rows", [])
        if row.get("ticker")
    }
    post_earnings_rows = {
        str(row.get("ticker") or "").upper(): row
        for row in post_earnings_context.get("rows", [])
        if row.get("ticker")
    }

    theme_rows = (market_state_bundle.get("theme_lifecycle_surface") or {}).get("themes", [])

    tickers = sorted(
        set(leadership_rows)
        | set(residual_rows)
        | set(ranking_rows)
        | set(expectation_rows)
        | set(earnings_rows)
        | set(post_earnings_rows)
    )

    market_regime_vector = build_market_regime_vector(
        market_regime=market_regime,
        breadth_context=breadth_context,
        sentiment=sentiment,
    )

    ticker_vectors = {}
    for ticker in tickers:
        leadership_vector = build_leadership_vector(
            leadership_row=leadership_rows.get(ticker),
            residual_row=residual_rows.get(ticker),
            ranking_row=ranking_rows.get(ticker),
        )
        expectation_vector = build_expectation_vector(
            expectation_row=expectation_rows.get(ticker),
            earnings_row=post_earnings_rows.get(ticker) or earnings_rows.get(ticker),
        )
        themes = (ranking_rows.get(ticker) or residual_rows.get(ticker) or {}).get("themes") or []
        theme_vector = build_theme_structure_vector(
            theme_rows=theme_rows,
            ticker_themes=themes,
        )
        risk_vector = build_risk_heat_vector(
            portfolio_heat=portfolio_heat,
            theme_vector=theme_vector,
            market_regime_vector=market_regime_vector,
        )
        ticker_vectors[ticker] = {
            "leadership_vector": leadership_vector,
            "expectation_vector": expectation_vector,
            "theme_structure_vector": theme_vector,
            "risk_heat_vector": risk_vector,
            "market_regime_vector": market_regime_vector,
        }

    return {
        "schema_version": 1,
        "read_only": True,
        "vector_names": [
            "leadership_vector",
            "expectation_vector",
            "theme_structure_vector",
            "risk_heat_vector",
            "market_regime_vector",
        ],
        "ticker_vectors": ticker_vectors,
        "summary": {
            "ticker_count": len(ticker_vectors),
            "strong_leadership_count": sum(1 for v in ticker_vectors.values() if v["leadership_vector"]["state"] == "strong"),
            "strong_expectation_count": sum(1 for v in ticker_vectors.values() if v["expectation_vector"]["state"] == "strong"),
            "hot_risk_count": sum(1 for v in ticker_vectors.values() if v["risk_heat_vector"]["state"] == "hot"),
            "market_regime_state": market_regime_vector.get("state"),
        },
        "notes": [
            "Canonical compressed state-vector representation.",
            "Use this layer to reduce surface explosion and centralize future ranking/attribution.",
            "Read-only until a future accepted experiment promotes it.",
        ],
    }
