"""Market sentiment surface.

Read-only market sentiment classification for attribution and future allocation
experiments. This module intentionally does not change trade eligibility or
live sizing.
"""

from __future__ import annotations


SENTIMENT_PANIC_RISK_OFF = "panic_risk_off"
SENTIMENT_VOLATILE_REBOUND = "volatile_rebound"
SENTIMENT_CHOPPY_UNCERTAIN = "choppy_uncertain"
SENTIMENT_HEALTHY_TREND = "healthy_trend"
SENTIMENT_LOW_VOL_GRIND = "low_vol_grind"
SENTIMENT_THEME_MANIA = "theme_mania"
SENTIMENT_BASELINE = "baseline"


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def classify_sentiment_surface(market_context):
    """Classify fine-grained market sentiment state.

    Expected optional fields:
      spy_pct_from_ma
      qqq_pct_from_ma
      spy_10d_return
      qqq_10d_return
      spy_20d_return
      qqq_20d_return
      qqq_minus_spy_ret20
      vix
      vix_10d_change
      breakout_signal_count
      ai_signal_count
      crypto_signal_count
      space_signal_count
    """
    ctx = market_context or {}

    spy_pct = _float(ctx.get("spy_pct_from_ma"), 0.0)
    qqq_pct = _float(ctx.get("qqq_pct_from_ma"), 0.0)
    spy_10d = _float(ctx.get("spy_10d_return"), 0.0)
    qqq_10d = _float(ctx.get("qqq_10d_return"), 0.0)
    spy_20d = _float(ctx.get("spy_20d_return"), 0.0)
    qqq_20d = _float(ctx.get("qqq_20d_return"), 0.0)
    qqq_rel = _float(ctx.get("qqq_minus_spy_ret20"), 0.0)
    vix = _float(ctx.get("vix"), 18.0)
    vix_change = _float(ctx.get("vix_10d_change"), 0.0)

    breakout_count = _float(ctx.get("breakout_signal_count"), 0.0)
    ai_count = _float(ctx.get("ai_signal_count"), 0.0)
    crypto_count = _float(ctx.get("crypto_signal_count"), 0.0)
    space_count = _float(ctx.get("space_signal_count"), 0.0)

    theme_density = ai_count + crypto_count + space_count

    if vix >= 30 or (spy_20d < -0.08 and qqq_20d < -0.10):
        return {
            "sentiment": SENTIMENT_PANIC_RISK_OFF,
            "confidence": 0.90,
            "why": ["high_vix_or_broad_drawdown"],
        }

    if vix >= 24 and qqq_10d > 0 and spy_10d > 0:
        return {
            "sentiment": SENTIMENT_VOLATILE_REBOUND,
            "confidence": 0.75,
            "why": ["high_vol_positive_rebound"],
        }

    if (
        spy_pct > 0.02
        and qqq_pct > 0.03
        and qqq_20d > 0.05
        and vix < 20
        and breakout_count >= 3
        and theme_density >= 2
        and qqq_rel > 0.03
    ):
        return {
            "sentiment": SENTIMENT_THEME_MANIA,
            "confidence": 0.85,
            "why": ["strong_growth_leadership_and_theme_density"],
        }

    if (
        spy_pct > 0.01
        and qqq_pct > 0.01
        and spy_20d > 0.03
        and qqq_20d > 0.04
        and vix < 19
    ):
        if vix < 15:
            return {
                "sentiment": SENTIMENT_LOW_VOL_GRIND,
                "confidence": 0.80,
                "why": ["stable_trend_low_volatility"],
            }
        return {
            "sentiment": SENTIMENT_HEALTHY_TREND,
            "confidence": 0.75,
            "why": ["broad_positive_trend"],
        }

    if (
        abs(spy_20d) < 0.03
        and abs(qqq_20d) < 0.04
        and vix >= 17
    ):
        return {
            "sentiment": SENTIMENT_CHOPPY_UNCERTAIN,
            "confidence": 0.70,
            "why": ["weak_directional_conviction"],
        }

    return {
        "sentiment": SENTIMENT_BASELINE,
        "confidence": 0.50,
        "why": ["mixed_or_incomplete_context"],
    }


def build_sentiment_trade_attribution(trades):
    """Aggregate closed-trade attribution by sentiment label."""
    buckets = {}

    for trade in trades or []:
        sentiment = trade.get("sentiment_surface") or SENTIMENT_BASELINE
        bucket = buckets.setdefault(sentiment, {
            "trades": 0,
            "wins": 0,
            "total_pnl": 0.0,
            "pnl_values": [],
            "r_values": [],
        })

        pnl = trade.get("pnl")
        if pnl is None:
            pnl = trade.get("profit_loss")
        pnl = _float(pnl, 0.0)

        bucket["trades"] += 1
        bucket["total_pnl"] += pnl
        bucket["pnl_values"].append(pnl)
        if pnl > 0:
            bucket["wins"] += 1

        entry = _float(trade.get("entry_price"), 0.0)
        stop = _float(trade.get("stop_price"), 0.0)
        shares = _float(trade.get("shares"), 0.0)
        if entry > stop > 0 and shares > 0:
            risk = (entry - stop) * shares
            if risk > 0:
                bucket["r_values"].append(pnl / risk)

    rows = []
    for sentiment, bucket in buckets.items():
        trades_n = bucket["trades"]
        pnl_values = bucket["pnl_values"]
        r_values = bucket["r_values"]

        avg_pnl = sum(pnl_values) / trades_n if trades_n else 0.0
        avg_r = sum(r_values) / len(r_values) if r_values else None

        rows.append({
            "sentiment": sentiment,
            "trades": trades_n,
            "win_rate": round(bucket["wins"] / trades_n, 4) if trades_n else 0.0,
            "total_pnl": round(bucket["total_pnl"], 2),
            "avg_pnl": round(avg_pnl, 2),
            "avg_r": round(avg_r, 4) if avg_r is not None else None,
            "worst_trade": round(min(pnl_values), 2) if pnl_values else None,
            "best_trade": round(max(pnl_values), 2) if pnl_values else None,
        })

    return sorted(rows, key=lambda row: row["total_pnl"], reverse=True)
