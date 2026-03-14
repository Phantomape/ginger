"""
Risk Engine: Compute risk parameters for each trade signal.

Standard trade structure per inst_5.txt:
  entry  = breakout price (current close)
  stop   = entry − 1.5 × ATR
  target = entry + 3.0 × ATR
  R:R    = 2:1  (3 ATR reward / 1.5 ATR risk)

Every trade must include:
  entry_price, stop_loss, position_size, risk_reward_ratio
"""

import logging

logger = logging.getLogger(__name__)

ATR_STOP_MULT   = 1.5
ATR_TARGET_MULT = 3.0


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


def enrich_signals(signals, features_dict):
    """
    Enrich all signals with risk parameters.

    Args:
        signals       (list[dict]): From signal_engine.generate_signals()
        features_dict (dict):       {ticker: features} for ATR lookup

    Returns:
        list[dict]: Signals with risk fields added
    """
    enriched = []
    for sig in signals:
        ticker = sig["ticker"]
        atr    = (features_dict.get(ticker) or {}).get("atr")

        if not atr or atr <= 0:
            logger.warning(f"{ticker}: ATR unavailable, skipping risk enrichment")
            enriched.append(sig)
            continue

        enriched.append(enrich_signal_with_risk(sig, atr))

    return enriched
