"""
Risk Engine: Compute risk parameters for each trade signal.

Standard trade structure per inst_5.txt:
  entry  = breakout price (current close)
  stop   = entry − 1.5 × ATR
  target = entry + 3.5 × ATR
  R:R    ≈ 2.33:1  (3.5 ATR reward / 1.5 ATR risk)

Every trade must include:
  entry_price, stop_loss, position_size, risk_reward_ratio
"""

import logging

logger = logging.getLogger(__name__)

ATR_STOP_MULT   = 1.5
ATR_TARGET_MULT = 3.5


def enrich_signal_with_risk(signal, atr):
    """
    Add target_price, risk_per_share, reward_per_share, risk_reward_ratio
    to a signal dict.

    stop_price is already set by the strategy (entry − 1.5×ATR).
    This function adds the target and computes R:R ratio.

    Args:
        signal (dict): Signal from signal_engine
        atr    (float): ATR value for this ticker

    Returns:
        dict: Enriched signal
    """
    entry = signal["entry_price"]
    stop  = signal.get("stop_price") or round(entry - ATR_STOP_MULT * atr, 2)

    target           = round(entry + ATR_TARGET_MULT * atr, 2)
    risk_per_share   = round(entry - stop, 2)
    reward_per_share = round(target - entry, 2)
    rr_ratio         = (round(reward_per_share / risk_per_share, 2)
                        if risk_per_share > 0 else None)

    return {
        **signal,
        "stop_price":        round(stop, 2),
        "target_price":      target,
        "risk_per_share":    risk_per_share,
        "reward_per_share":  reward_per_share,
        "risk_reward_ratio": rr_ratio,
    }


def _trade_quality_score(sig, features):
    """
    Compute Trade Quality Score (TQS) — pre-calculated so LLM reads it directly.

    Formula:
        TQS = 0.40 × confidence_score
            + 0.25 × trend_score           (0-1 from feature_layer)
            + 0.20 × vol_norm              (volume_spike_ratio / 2.0, capped at 1.0)
            + 0.15 × momentum_norm         (abs(momentum_10d_pct) / 0.10, capped at 1.0)

    Returns:
        float: 0.0 – 1.0
    """
    conf       = sig.get("confidence_score", 0)
    trend_sc   = (features or {}).get("trend_score") or 0
    vol_ratio  = (features or {}).get("volume_spike_ratio") or 0
    momentum   = max(0.0, (features or {}).get("momentum_10d_pct") or 0)

    vol_norm  = min(vol_ratio / 2.0, 1.0)
    mom_norm  = min(momentum / 0.10, 1.0)

    return round(0.40 * conf + 0.25 * trend_sc + 0.20 * vol_norm + 0.15 * mom_norm, 3)


def enrich_signals(signals, features_dict):
    """
    Enrich all signals with risk parameters and Trade Quality Score.

    Args:
        signals       (list[dict]): From signal_engine.generate_signals()
        features_dict (dict):       {ticker: features} for ATR + TQS fields

    Returns:
        list[dict]: Signals with risk fields + trade_quality_score added
    """
    enriched = []
    for sig in signals:
        ticker   = sig["ticker"]
        features = features_dict.get(ticker) or {}
        atr      = features.get("atr")

        if not atr or atr <= 0:
            logger.warning(f"{ticker}: ATR unavailable, skipping risk enrichment")
            enriched.append(sig)
            continue

        enriched_sig = enrich_signal_with_risk(sig, atr)
        enriched_sig["trade_quality_score"] = _trade_quality_score(sig, features)
        enriched.append(enriched_sig)

    return enriched
