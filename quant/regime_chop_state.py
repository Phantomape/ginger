"""Shared point-in-time regime / chop-exposure state.

Promotes the exp-20260615-019 finding into one shared, rule-versioned helper:
both an accepted sleeve (Fundamental Growth + RS) and the rejected
deferred-revenue scout lose specifically in the directionless `choppy_range`
regime (SPY near/below trend AND weak breadth, but NOT stressed), while staying
positive in both risk_on and risk_off. exp-20260615-023 separately REJECTED
Kaufman Efficiency Ratio as the chop axis (it mislabels steady grind-ups as
choppy), so the axis here is trend-state x breadth, not index path-efficiency.

This module computes, point-in-time, a regime probability vector
(`risk_on_trend / choppy_range / risk_off_stress`), a `bull_score`, a
`risk_off_score`, and a continuous `exposure_scalar` that softly down-tilts only
the choppy regime (vol-target style, never a hard on/off gate).

It is read-only infrastructure: importing or calling it changes no entry,
ranking, sizing, exit, or order behavior. Any execution use (e.g. a
portfolio-level capital tilt) requires a separate Gate 1-4 experiment plus
forward / live-pilot validation.

Two adapters share one core:

- `regime_chop_from_features(features)`  -- pure core, deterministic.
- `regime_chop_from_spy_universe(...)`   -- full-fidelity replay/daily adapter
  (trend, momentum, drawdown, vol, breadth, cross-index agreement from bars).
- `regime_chop_from_market_context(...)` -- thin production adapter from the
  daily market-state context dict (trend, momentum, VIX stress; no breadth).

The core degrades gracefully: `bull_score` re-weights across whichever of
{trend, breadth, index-agreement} are present, and `risk_off_score` takes the
strongest of whichever stress signals are present (SPY drawdown/vol and/or VIX).
"""

from __future__ import annotations

import math
import statistics
from typing import Any

RULE_VERSION = "regime_chop_state_v1"

REGIME_LABELS = ("risk_on_trend", "choppy_range", "risk_off_stress")

# Conventional, non-optimized constants (mirror exp-20260615-019).
TREND_GAIN = 8.0
MOM_GAIN = 6.0
DD_REF = 0.08
DD_GAIN = 14.0
VOL_RATIO_REF = 1.30
VOL_GAIN = 2.5
VIX_REF = 22.0
VIX_GAIN = 0.18
VIX_CHANGE_GAIN = 0.04
EXPOSURE_FLOOR = 0.5

# Bar-derived feature lookbacks (mirror exp-20260615-019).
SMA_LONG = 200
SMA_SHORT = 50
HIGH_LOOKBACK = 252
RET_LOOKBACK = 20
VOL_LOOKBACK = 20
VOL_MEDIAN_LOOKBACK = 100
MIN_BARS_FOR_REGIME = 150


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _f(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def regime_chop_from_features(features: dict[str, Any]) -> dict[str, Any]:
    """Pure, deterministic core. Returns regime probabilities + exposure scalar.

    Recognized feature keys (all optional except trend_pct_from_ma):
      trend_pct_from_ma, ret20, drawdown_from_high, vol_ratio, vix, vix_change,
      breadth, index_agreement.
    """
    trend = _f(features.get("trend_pct_from_ma"))
    if trend is None:
        return {
            "rule_version": RULE_VERSION,
            "regime_label": "unknown",
            "coverage": "missing_trend_feature",
            "exposure_scalar": 1.0,
        }
    ret20 = _f(features.get("ret20")) or 0.0
    trend_feature = _sigmoid(TREND_GAIN * trend + MOM_GAIN * ret20)

    # bull_score: weighted mean over whichever of trend/breadth/index-agree exist.
    parts: list[tuple[float, float]] = [(0.5, trend_feature)]
    breadth = _f(features.get("breadth"))
    if breadth is not None:
        parts.append((0.3, max(0.0, min(1.0, breadth))))
    idx_agree = _f(features.get("index_agreement"))
    if idx_agree is not None:
        parts.append((0.2, max(0.0, min(1.0, idx_agree))))
    wsum = sum(w for w, _ in parts)
    bull = sum(w * v for w, v in parts) / wsum if wsum > 0 else trend_feature

    # risk_off_score: strongest available stress signal.
    stress_sources: list[float] = []
    dd = _f(features.get("drawdown_from_high"))
    vr = _f(features.get("vol_ratio"))
    if dd is not None and vr is not None:
        stress_sources.append(_sigmoid(DD_GAIN * (-dd - DD_REF) + VOL_GAIN * (vr - VOL_RATIO_REF)))
    vix = _f(features.get("vix"))
    if vix is not None:
        vchg = _f(features.get("vix_change")) or 0.0
        stress_sources.append(_sigmoid(VIX_GAIN * (vix - VIX_REF) + VIX_CHANGE_GAIN * vchg))
    stress = max(stress_sources) if stress_sources else 0.0
    stress_confident = bool(stress_sources)

    aff_off = stress
    aff_on = bull * (1.0 - stress)
    aff_chop = (1.0 - bull) * (1.0 - stress)
    s = aff_on + aff_chop + aff_off
    if s <= 0:
        p_on = p_chop = p_off = 1.0 / 3.0
    else:
        p_on, p_chop, p_off = aff_on / s, aff_chop / s, aff_off / s

    probs = {"risk_on_trend": p_on, "choppy_range": p_chop, "risk_off_stress": p_off}
    label = max(probs, key=probs.get)
    # soft tilt: down-weight ONLY the choppy regime; risk_on and risk_off keep ~full.
    exposure_scalar = EXPOSURE_FLOOR + (1.0 - EXPOSURE_FLOOR) * (1.0 - p_chop)

    return {
        "rule_version": RULE_VERSION,
        "regime_label": label,
        "p_risk_on_trend": round(p_on, 6),
        "p_choppy_range": round(p_chop, 6),
        "p_risk_off_stress": round(p_off, 6),
        "bull_score": round(bull, 6),
        "risk_off_score": round(p_off, 6),
        "exposure_scalar": round(exposure_scalar, 6),
        "stress_confident": stress_confident,
        "coverage": "ok" if stress_confident else "no_stress_signal_low_confidence",
        "feature_keys_used": sorted(k for k in (
            "trend_pct_from_ma", "ret20", "drawdown_from_high", "vol_ratio",
            "vix", "vix_change", "breadth", "index_agreement",
        ) if _f(features.get(k)) is not None),
    }


# --------------------------------------------------------------------------- #
# Bar-derived feature builders (full fidelity: replay and any bar-having caller)
# --------------------------------------------------------------------------- #
def _sorted_bars(bars: list[dict[str, Any]]) -> tuple[list[str], list[float], list[float]]:
    rows = [b for b in (bars or []) if b.get("Date") and b.get("Close") is not None]
    rows.sort(key=lambda b: str(b["Date"])[:10])
    dates = [str(b["Date"])[:10] for b in rows]
    closes = [float(b["Close"]) for b in rows]
    highs = [float(b.get("High") or b["Close"]) for b in rows]
    return dates, closes, highs


def spy_features_at(
    spy_bars: list[dict[str, Any]],
    asof: str,
    *,
    breadth: float | None = None,
    index_agreement: float | None = None,
) -> dict[str, Any] | None:
    dates, closes, highs = _sorted_bars(spy_bars)
    asof = str(asof)[:10]
    i = None
    for j, d in enumerate(dates):
        if d <= asof:
            i = j
        else:
            break
    if i is None or i < MIN_BARS_FOR_REGIME:
        return None
    close = closes[i]
    n_long = min(SMA_LONG, i + 1)
    sma_long = sum(closes[i - n_long + 1 : i + 1]) / n_long
    trend = close / sma_long - 1.0 if sma_long > 0 else 0.0
    mom = close / closes[i - RET_LOOKBACK] - 1.0 if i >= RET_LOOKBACK and closes[i - RET_LOOKBACK] > 0 else 0.0
    hi_window = highs[max(0, i - HIGH_LOOKBACK + 1) : i + 1]
    hi = max(hi_window) if hi_window else close
    dd = close / hi - 1.0 if hi > 0 else 0.0
    rets = [closes[j] / closes[j - 1] - 1.0 for j in range(max(1, i - VOL_LOOKBACK + 1), i + 1) if closes[j - 1] > 0]
    vol20 = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    med_vols = []
    for k in range(max(VOL_LOOKBACK, i - VOL_MEDIAN_LOOKBACK + 1), i + 1):
        sub = [closes[j] / closes[j - 1] - 1.0 for j in range(k - VOL_LOOKBACK + 1, k + 1) if j >= 1 and closes[j - 1] > 0]
        if len(sub) > 1:
            med_vols.append(statistics.pstdev(sub))
    med_vol = statistics.median(med_vols) if med_vols else vol20
    vr = vol20 / med_vol if med_vol > 0 else 1.0
    return {
        "asof_index_date": dates[i],
        "trend_pct_from_ma": trend,
        "ret20": mom,
        "drawdown_from_high": dd,
        "vol_ratio": vr,
        "breadth": breadth,
        "index_agreement": index_agreement,
    }


def regime_chop_from_spy_universe(
    spy_bars: list[dict[str, Any]],
    asof: str,
    *,
    breadth: float | None = None,
    index_agreement: float | None = None,
) -> dict[str, Any]:
    feats = spy_features_at(spy_bars, asof, breadth=breadth, index_agreement=index_agreement)
    if feats is None:
        return {"rule_version": RULE_VERSION, "regime_label": "unknown", "coverage": "insufficient_lookback", "exposure_scalar": 1.0}
    out = regime_chop_from_features(feats)
    out["features"] = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in feats.items()}
    return out


# --------------------------------------------------------------------------- #
# Thin production adapter from the daily market-state context dict
# --------------------------------------------------------------------------- #
def regime_chop_from_market_context(context: dict[str, Any] | None) -> dict[str, Any]:
    """Production adapter using only fields the daily market-state context has.

    Note: the thin context carries SPY %-from-MA, 20d return, and VIX, but NOT
    breadth or SPY drawdown/vol. So this is a lower-fidelity view than the
    bar-based adapter; that replay-vs-production boundary is intentional and is
    why exp-20260615-025 re-validates both fidelities before any execution use.
    """
    ctx = dict(context or {})
    feats = {
        "trend_pct_from_ma": ctx.get("spy_pct_from_ma"),
        "ret20": ctx.get("spy_20d_return"),
        "vix": ctx.get("vix"),
        "vix_change": ctx.get("vix_10d_change"),
    }
    out = regime_chop_from_features(feats)
    out["fidelity"] = "thin_market_context_no_breadth_no_drawdown"
    return out
