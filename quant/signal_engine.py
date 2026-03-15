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


def _rs_positive(features, market_context):
    """
    True if stock's 10d return outperforms SPY's 10d return.
    Relative strength is the single best predictor of breakout follow-through.
    """
    spy_10d   = (market_context or {}).get("spy_10d_return")
    stock_10d = features.get("momentum_10d_pct") or 0
    if spy_10d is None:
        return True   # no market data → skip filter, don't reject
    return stock_10d > spy_10d


def _near_52w_high(features):
    """True if close is within 15% of 52-week high (breakout quality filter)."""
    pct = features.get("pct_from_52w_high")
    if pct is None:
        return True   # insufficient history → skip, don't reject
    return pct > -0.15   # within 15% of 52-week high


def strategy_a_trend(ticker, features, market_context=None):
    """
    Strategy A – Trend Following.

    Hard conditions (all 3 must be True):
      - price > 200MA
      - 20-day high breakout
      - volume spike (ratio > 2.0)
      - RS: stock 10d return > SPY 10d return (relative strength gate)

    Soft conditions (boost confidence):
      - RS: stock meaningfully outperforms SPY (>20% faster)
      - Near 52-week high (within 15%) — breakout quality

    Returns:
        dict or None
    """
    above_200 = features.get("above_200ma")
    breakout  = features.get("breakout_20d")
    vol_spike = features.get("volume_spike")
    close     = features.get("close")
    atr       = features.get("atr")

    if above_200 is None:
        return None
    if not (above_200 and breakout and vol_spike):
        return None
    if not close or not atr:
        return None

    # RS gate: reject if stock is underperforming SPY over 10 days
    if not _rs_positive(features, market_context):
        return None

    entry = close
    stop  = round(entry - ATR_STOP_MULT * atr, 2)

    spy_10d   = (market_context or {}).get("spy_10d_return") or 0
    stock_10d = features.get("momentum_10d_pct") or 0
    rs_strong = bool(stock_10d > spy_10d * 1.2)   # outperforms by ≥20%
    near_high = _near_52w_high(features)

    # Soft weights 0.25 so all-hard-conditions alone → conf ≈ 0.857
    # (3.0 / 3.5), exceeding the 0.85 standalone-trade threshold in the prompt.
    # Previously 0.5 soft weights → conf = 0.75 (needed news; missed legit breakouts).
    confidence = _confidence([
        (above_200,   1.0),
        (breakout,    1.0),
        (vol_spike,   1.0),
        (rs_strong,   0.25),  # bonus: meaningfully outperforms market
        (near_high,   0.25),  # bonus: breakout near 52-week highs
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
            "rs_vs_spy":           round(stock_10d - spy_10d, 4),
            "pct_from_52w_high":   features.get("pct_from_52w_high"),
        },
    }


def strategy_b_breakout(ticker, features, market_context=None):
    """
    Strategy B – Volatility Breakout.

    Hard conditions (all 3 must be True):
      - daily_range > 1.5 ATR
      - 20-day high breakout
      - volume expansion (ratio > 1.2)
      - RS: stock 10d return > SPY 10d return

    Soft conditions:
      - RS strong (outperforms by ≥20%)
      - Near 52-week high

    Returns:
        dict or None
    """
    range_vs_atr = features.get("daily_range_vs_atr")
    breakout     = features.get("breakout_20d")
    vol_ratio    = features.get("volume_spike_ratio")
    close        = features.get("close")
    atr          = features.get("atr")
    high_20d     = features.get("high_20d")

    if not close or not atr:
        return None
    if range_vs_atr is None or not breakout:
        return None

    range_expanded  = bool(range_vs_atr > 1.5)
    volume_expanded = bool(vol_ratio is not None and vol_ratio > 1.2)

    if not (range_expanded and breakout and volume_expanded):
        return None

    # RS gate
    if not _rs_positive(features, market_context):
        return None

    entry = close
    # Stop just below breakout level (failed breakout = exit), or 1.5×ATR, whichever is tighter.
    atr_stop      = round(entry - ATR_STOP_MULT * atr, 2)
    breakout_stop = round(high_20d * 0.99, 2) if high_20d else atr_stop
    stop          = max(atr_stop, breakout_stop)

    spy_10d   = (market_context or {}).get("spy_10d_return") or 0
    stock_10d = features.get("momentum_10d_pct") or 0
    rs_strong = bool(stock_10d > spy_10d * 1.2)
    near_high = _near_52w_high(features)

    # Same soft-weight reduction as strategy_a: all-hard → conf ≈ 0.857.
    confidence = _confidence([
        (range_expanded,   1.0),
        (breakout,         1.0),
        (volume_expanded,  1.0),
        (rs_strong,        0.25),  # bonus: meaningfully outperforms market
        (near_high,        0.25),  # bonus: near 52-week highs
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
            "rs_vs_spy":           round(stock_10d - spy_10d, 4),
            "pct_from_52w_high":   features.get("pct_from_52w_high"),
        },
    }


def strategy_c_earnings(ticker, features, market_context=None):
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

    # RS gate: earnings plays still need the stock to outperform the market.
    # A stock drifting into earnings while underperforming SPY rarely has follow-through.
    if not _rs_positive(features, market_context):
        return None

    entry = close
    stop  = round(entry - ATR_STOP_MULT * atr, 2)

    above_200ma = features.get("above_200ma")

    # Build confidence checks; only include pos_surprise when data is available.
    # If missing (new stock / data gap), don't penalise — neutral treatment.
    confidence_checks = [
        (event_window,                        1.0),
        (strong_momentum,                     1.0),
        ((momentum_10d or 0) > 0.05,          0.5),   # extra: >5% in 10 days
        (bool(above_200ma),                   0.5),   # trending stock preferred
    ]
    if pos_surprise is not None:
        confidence_checks.append((bool(pos_surprise), 1.0))   # positive surprise history
    confidence = _confidence(confidence_checks)

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


def generate_signals(features_dict, market_context=None):
    """
    Run all 3 strategies for every ticker in features_dict.

    Args:
        features_dict  (dict): {ticker: features_dict or None}
        market_context (dict): Optional {"spy_10d_return": float} for RS filter.
                               Sourced from regime.py SPY momentum_10d_pct.

    Returns:
        list[dict]: All triggered signals, sorted by confidence_score desc
    """
    signals = []

    for ticker, features in features_dict.items():
        if features is None:
            continue

        for fn in [strategy_a_trend, strategy_b_breakout, strategy_c_earnings]:
            try:
                sig = fn(ticker, features, market_context=market_context)
                if sig:
                    signals.append(sig)
                    logger.info(
                        f"SIGNAL  {ticker:6s}  {sig['strategy']:22s}  "
                        f"entry={sig['entry_price']}  conf={sig['confidence_score']}"
                    )
            except Exception as e:
                logger.error(f"{ticker} {fn.__name__}: {e}")

    # Deduplicate: keep only the highest-confidence signal per ticker.
    # Strategy A and B can both fire on the same breakout day; showing both
    # confuses the LLM with two slightly different recommendations for one stock.
    best: dict[str, dict] = {}
    for sig in signals:
        t = sig["ticker"]
        if t not in best or sig["confidence_score"] > best[t]["confidence_score"]:
            best[t] = sig

    deduped = sorted(best.values(), key=lambda s: s["confidence_score"], reverse=True)
    if len(signals) != len(deduped):
        logger.info(f"Deduplicated {len(signals)} signals → {len(deduped)} (one per ticker)")
    return deduped
