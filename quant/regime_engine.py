"""Shared market regime engine.

This module provides a small, explainable regime classifier that can be used by
backtests, daily runs, exits, sleeve selection, and capital allocation.

It deliberately avoids ML and only consumes same-day observable context fields.
"""

from __future__ import annotations


REGIME_TREND = "trend"
REGIME_CHOP = "chop"
REGIME_RISK_OFF = "risk_off"
REGIME_HIGH_VOL = "high_vol"
REGIME_LOW_VOL_GRIND = "low_vol_grind"
REGIME_THEME_MANIA = "theme_mania"
REGIME_BASELINE = "baseline"


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _avg(values):
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def classify_market_regime(market_context):
    """Classify market regime from observable market context.

    Expected optional fields:
      market_regime: legacy BULL/NEUTRAL/BEAR label
      spy_pct_from_ma, qqq_pct_from_ma
      spy_10d_return, qqq_10d_return
      spy_20d_return, qqq_20d_return
      vix, vix_10d_change
      qqq_minus_spy_ret20
      theme_signal_count, breakout_signal_count
    """
    ctx = market_context or {}
    legacy = str(ctx.get("market_regime") or "").upper()

    spy_pct = _float(ctx.get("spy_pct_from_ma"))
    qqq_pct = _float(ctx.get("qqq_pct_from_ma"))
    spy_ret10 = _float(ctx.get("spy_10d_return"))
    qqq_ret10 = _float(ctx.get("qqq_10d_return"))
    spy_ret20 = _float(ctx.get("spy_20d_return"))
    qqq_ret20 = _float(ctx.get("qqq_20d_return"))
    qqq_minus_spy20 = _float(ctx.get("qqq_minus_spy_ret20"))
    vix = _float(ctx.get("vix"))
    vix_change = _float(ctx.get("vix_10d_change"), 0.0)
    theme_signal_count = _float(ctx.get("theme_signal_count"), 0.0)
    breakout_signal_count = _float(ctx.get("breakout_signal_count"), 0.0)

    pct_score = _avg([spy_pct, qqq_pct])
    mom10 = _avg([spy_ret10, qqq_ret10])
    mom20 = _avg([spy_ret20, qqq_ret20])

    risk_off = False
    if legacy == "BEAR":
        risk_off = True
    if pct_score is not None and pct_score < -0.03:
        risk_off = True
    if mom20 is not None and mom20 < -0.05:
        risk_off = True
    if vix is not None and vix >= 28 and vix_change and vix_change > 0:
        risk_off = True

    high_vol = False
    if vix is not None and vix >= 24:
        high_vol = True
    if vix_change is not None and vix_change >= 0.20:
        high_vol = True

    trend = False
    if pct_score is not None and mom20 is not None:
        trend = pct_score > 0.02 and mom20 > 0.03
    elif legacy == "BULL" and (mom10 is None or mom10 > 0):
        trend = True

    low_vol_grind = False
    if trend and vix is not None and vix < 18 and mom10 is not None and mom10 > 0:
        low_vol_grind = True

    theme_mania = False
    if qqq_minus_spy20 is not None and qqq_minus_spy20 > 0.04 and theme_signal_count >= 3:
        theme_mania = True
    if breakout_signal_count >= 5 and qqq_ret20 is not None and qqq_ret20 > 0.06:
        theme_mania = True

    chop = False
    if not risk_off and not trend:
        if pct_score is not None and abs(pct_score) < 0.02:
            chop = True
        elif mom20 is not None and abs(mom20) < 0.02:
            chop = True

    if risk_off:
        regime = REGIME_RISK_OFF
    elif theme_mania:
        regime = REGIME_THEME_MANIA
    elif high_vol and trend:
        regime = REGIME_HIGH_VOL
    elif low_vol_grind:
        regime = REGIME_LOW_VOL_GRIND
    elif trend:
        regime = REGIME_TREND
    elif chop:
        regime = REGIME_CHOP
    else:
        regime = REGIME_BASELINE

    confidence_inputs = sum(
        value is not None
        for value in [pct_score, mom10, mom20, vix, qqq_minus_spy20]
    )
    confidence = min(1.0, confidence_inputs / 5.0)

    return {
        "regime": regime,
        "confidence": round(confidence, 2),
        "legacy_market_regime": legacy or None,
        "features": {
            "pct_score": round(pct_score, 4) if pct_score is not None else None,
            "mom10": round(mom10, 4) if mom10 is not None else None,
            "mom20": round(mom20, 4) if mom20 is not None else None,
            "vix": vix,
            "vix_10d_change": vix_change,
            "qqq_minus_spy_ret20": qqq_minus_spy20,
            "theme_signal_count": theme_signal_count,
            "breakout_signal_count": breakout_signal_count,
        },
        "flags": {
            "risk_off": risk_off,
            "high_vol": high_vol,
            "trend": trend,
            "low_vol_grind": low_vol_grind,
            "theme_mania": theme_mania,
            "chop": chop,
        },
    }


def regime_strategy_multiplier(regime, strategy_name):
    """Return sizing multiplier for a strategy under a regime."""
    r = str(regime or REGIME_BASELINE)
    s = str(strategy_name or "").lower()

    is_breakout = "breakout" in s or "trend" in s or "momentum" in s
    is_pullback = "pullback" in s or "reclaim" in s or "mean" in s
    is_smallcap = "small" in s or "spec" in s or "pilot" in s

    if r == REGIME_RISK_OFF:
        if is_smallcap:
            return 0.25
        if is_breakout:
            return 0.40
        return 0.60
    if r == REGIME_CHOP:
        if is_breakout:
            return 0.55
        if is_pullback:
            return 0.85
        return 0.75
    if r == REGIME_THEME_MANIA:
        if is_breakout:
            return 1.15
        return 0.90
    if r == REGIME_HIGH_VOL:
        if is_breakout:
            return 0.85
        return 0.75
    if r == REGIME_LOW_VOL_GRIND:
        if is_breakout:
            return 1.05
        return 0.95
    if r == REGIME_TREND:
        if is_breakout:
            return 1.10
        return 1.00
    return 1.00


def regime_sleeve_multiplier(regime, sleeve_name):
    """Return allocation multiplier for a sleeve under a regime."""
    r = str(regime or REGIME_BASELINE)
    sleeve = str(sleeve_name or "").lower()

    is_ai = "ai" in sleeve or "infra" in sleeve
    is_consumer = "consumer" in sleeve
    is_space = "space" in sleeve
    is_core = "core" in sleeve

    if r == REGIME_RISK_OFF:
        if is_space:
            return 0.20
        if is_ai:
            return 0.45
        if is_consumer:
            return 0.55
        return 0.70 if is_core else 0.50
    if r == REGIME_CHOP:
        if is_ai or is_space:
            return 0.70
        return 0.85
    if r == REGIME_THEME_MANIA:
        if is_ai:
            return 1.20
        if is_space:
            return 0.90
        return 1.00
    if r == REGIME_HIGH_VOL:
        if is_space:
            return 0.45
        if is_ai:
            return 0.80
        return 0.75
    if r == REGIME_TREND or r == REGIME_LOW_VOL_GRIND:
        if is_ai:
            return 1.10
        return 1.00
    return 1.00


def apply_regime_to_allocation(allocation_rows, regime_report):
    """Apply regime multipliers to allocation rows and renormalize weights."""
    rows = []
    regime = (regime_report or {}).get("regime", REGIME_BASELINE)

    for row in allocation_rows or []:
        out = dict(row)
        base_weight = _float(out.get("capital_weight"), 0.0)
        mult = regime_sleeve_multiplier(regime, out.get("name"))
        out["regime"] = regime
        out["regime_multiplier"] = mult
        out["pre_regime_capital_weight"] = base_weight
        out["regime_adjusted_raw_weight"] = base_weight * mult
        rows.append(out)

    total = sum(_float(row.get("regime_adjusted_raw_weight"), 0.0) for row in rows)
    for row in rows:
        raw = _float(row.get("regime_adjusted_raw_weight"), 0.0)
        row["capital_weight"] = round(raw / total, 4) if total > 0 else 0.0

    return sorted(rows, key=lambda row: row.get("capital_weight", 0.0), reverse=True)
