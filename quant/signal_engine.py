"""
Signal Engine: Generate trade candidates from simple, well-known strategies.

Strategy A – Trend Following:
  Conditions: price > 200MA + 20-day breakout + volume spike
  Signal:     trend_long

Strategy B – Volatility Breakout:
  Conditions: daily_range > 1.5 ATR + 20d high breakout + volume expansion
  Signal:     breakout_long

Strategy C – Earnings Event Setup:
  Conditions: earnings within 5–15 days + positive surprise history + momentum
  Signal:     earnings_event_long

Output format per signal:
  {ticker, strategy, entry_price, stop_price, confidence_score, conditions_met, ...}
"""

import logging

logger = logging.getLogger(__name__)


def _confidence(checks):
    """
    Compute confidence score as fraction of True checks.

    Args:
        checks (list): Mix of bool and (bool, weight) tuples

    Returns:
        float: 0.0 – 1.0
    """
    if not checks:
        return 0.0
    total_weight = 0.0
    true_weight  = 0.0
    for item in checks:
        if isinstance(item, tuple):
            val, w = item
        else:
            val, w = item, 1.0
        total_weight += w
        if val:
            true_weight += w
    return round(true_weight / total_weight, 2) if total_weight > 0 else 0.0


# Stop multiplier — 1.5 × ATR per inst_5.txt spec
ATR_STOP_MULT = 1.5


def strategy_a_trend(ticker, features):
    """
    Strategy A – Trend Following.

    Hard conditions (all 3 must be True):
      - price > 200MA
      - 20-day high breakout
      - volume spike (ratio > 1.5)

    Returns:
        dict or None
    """
    above_200 = features.get("above_200ma")
    breakout  = features.get("breakout_20d")
    vol_spike = features.get("volume_spike")
    close     = features.get("close")
    atr       = features.get("atr")

    # Need 200MA data (None means insufficient history)
    if above_200 is None:
        return None
    if not (above_200 and breakout and vol_spike):
        return None
    if not close or not atr:
        return None

    entry = close
    stop  = round(entry - ATR_STOP_MULT * atr, 2)

    confidence = _confidence([
        (above_200,  1.0),
        (breakout,   1.0),
        (vol_spike,  1.0),
        ((features.get("momentum_10d_pct") or 0) > 0,    0.5),
        ((features.get("price_vs_200ma_pct") or 0) > 0.05, 0.5),  # >5% above 200MA
    ])

    return {
        "ticker":           ticker,
        "strategy":         "trend_long",
        "entry_price":      round(entry, 2),
        "stop_price":       stop,
        "confidence_score": confidence,
        "conditions_met": {
            "above_200ma":         above_200,
            "breakout_20d":        breakout,
            "volume_spike":        vol_spike,
            "momentum_10d_pct":    features.get("momentum_10d_pct"),
            "price_vs_200ma_pct":  features.get("price_vs_200ma_pct"),
        },
    }


def strategy_b_breakout(ticker, features):
    """
    Strategy B – Volatility Breakout.

    Hard conditions (all 3 must be True):
      - daily_range > 1.5 ATR
      - 20-day high breakout
      - volume expansion (ratio > 1.2)

    Returns:
        dict or None
    """
    range_vs_atr = features.get("daily_range_vs_atr")
    breakout     = features.get("breakout_20d")
    vol_ratio    = features.get("volume_spike_ratio")
    close        = features.get("close")
    atr          = features.get("atr")

    if not close or not atr:
        return None
    if range_vs_atr is None or not breakout:
        return None

    range_expanded   = bool(range_vs_atr > 1.5)
    volume_expanded  = bool(vol_ratio is not None and vol_ratio > 1.2)

    if not (range_expanded and breakout and volume_expanded):
        return None

    entry = close
    stop  = round(entry - ATR_STOP_MULT * atr, 2)

    confidence = _confidence([
        (range_expanded,                      1.0),
        (breakout,                            1.0),
        (volume_expanded,                     1.0),
        (range_vs_atr > 2.0,                  0.5),   # extra: range > 2× ATR
        ((vol_ratio or 0) > 2.0,              0.5),   # extra: volume surge > 2×
    ])

    return {
        "ticker":           ticker,
        "strategy":         "breakout_long",
        "entry_price":      round(entry, 2),
        "stop_price":       stop,
        "confidence_score": confidence,
        "conditions_met": {
            "daily_range_vs_atr":  range_vs_atr,
            "breakout_20d":        breakout,
            "volume_spike_ratio":  vol_ratio,
        },
    }


def strategy_c_earnings(ticker, features):
    """
    Strategy C – Earnings Event Setup.

    Hard conditions:
      - earnings within 5–15 days
      - strong price momentum (10d > +2%)

    Soft conditions (boost confidence):
      - positive historical EPS surprise
      - stock above 200MA

    Returns:
        dict or None
    """
    event_window  = features.get("earnings_event_window")
    momentum_10d  = features.get("momentum_10d_pct")
    pos_surprise  = features.get("positive_surprise_history")  # may be None
    close         = features.get("close")
    atr           = features.get("atr")
    dte           = features.get("days_to_earnings")

    if not close or not atr:
        return None
    if not event_window:
        return None

    strong_momentum = bool(momentum_10d is not None and momentum_10d > 0.02)
    if not strong_momentum:
        return None

    entry = close
    stop  = round(entry - ATR_STOP_MULT * atr, 2)

    above_200ma = features.get("above_200ma")

    confidence = _confidence([
        (event_window,                        1.0),
        (strong_momentum,                     1.0),
        (bool(pos_surprise),                  1.0),   # positive surprise history
        ((momentum_10d or 0) > 0.05,          0.5),   # extra: >5% in 10 days
        (bool(above_200ma),                   0.5),   # trending stock preferred
    ])

    return {
        "ticker":           ticker,
        "strategy":         "earnings_event_long",
        "entry_price":      round(entry, 2),
        "stop_price":       stop,
        "confidence_score": confidence,
        "days_to_earnings": dte,
        "conditions_met": {
            "earnings_event_window":     event_window,
            "momentum_10d_pct":          momentum_10d,
            "positive_surprise_history": pos_surprise,
            "above_200ma":               above_200ma,
        },
    }


def generate_signals(features_dict):
    """
    Run all 3 strategies for every ticker in features_dict.

    Args:
        features_dict (dict): {ticker: features_dict or None}

    Returns:
        list[dict]: All triggered signals, sorted by confidence_score desc
    """
    signals = []

    for ticker, features in features_dict.items():
        if features is None:
            continue

        for fn in [strategy_a_trend, strategy_b_breakout, strategy_c_earnings]:
            try:
                sig = fn(ticker, features)
                if sig:
                    signals.append(sig)
                    logger.info(
                        f"SIGNAL  {ticker:6s}  {sig['strategy']:22s}  "
                        f"entry={sig['entry_price']}  conf={sig['confidence_score']}"
                    )
            except Exception as e:
                logger.error(f"{ticker} {fn.__name__}: {e}")

    signals.sort(key=lambda s: s["confidence_score"], reverse=True)
    return signals
