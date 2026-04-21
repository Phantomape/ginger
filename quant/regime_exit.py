"""Shared regime-aware exit profile for backtest and production.

This module keeps the exit-target mapping in one place so the backtester and
daily production pipelines use the same logic. Inputs are restricted to fields
that are observable on the signal day.
"""

from constants import ATR_TARGET_MULT


def _clamp(value, lo, hi):
    """Clamp a float into a closed interval."""
    return max(lo, min(hi, value))


def compute_regime_exit_profile(market_context, base_target_mult=ATR_TARGET_MULT):
    """Return an entry-day exit profile using only same-day observable market data."""
    if not market_context:
        return {
            "target_mult": round(base_target_mult, 2),
            "bucket": "baseline",
            "score": None,
            "inputs_used": 0,
        }

    pct_values = [
        v for v in (
            market_context.get("spy_pct_from_ma"),
            market_context.get("qqq_pct_from_ma"),
        )
        if v is not None
    ]
    mom_values = [
        v for v in (
            market_context.get("spy_10d_return"),
            market_context.get("qqq_10d_return"),
        )
        if v is not None
    ]

    if not pct_values and not mom_values:
        return {
            "target_mult": round(base_target_mult, 2),
            "bucket": "baseline",
            "score": None,
            "inputs_used": 0,
        }

    avg_pct = sum(pct_values) / len(pct_values) if pct_values else 0.0
    avg_mom = sum(mom_values) / len(mom_values) if mom_values else 0.0
    score = avg_pct + 0.5 * avg_mom

    normalized = _clamp((score + 0.06) / 0.12, 0.0, 1.0)
    target_mult = 3.0 + 1.5 * normalized

    regime = (market_context.get("market_regime") or "").upper()
    if regime == "NEUTRAL":
        target_mult = min(target_mult, 3.75)
    elif regime == "BEAR":
        target_mult = min(target_mult, 3.25)

    if score >= 0.03:
        bucket = "risk_on"
    elif score <= 0.0:
        bucket = "defensive"
    else:
        bucket = "balanced"

    return {
        "target_mult": round(target_mult, 2),
        "bucket": bucket,
        "score": round(score, 4),
        "inputs_used": len(pct_values) + len(mom_values),
    }
