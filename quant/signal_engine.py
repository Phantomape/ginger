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
    """True if close is within 15% of 52-week high (breakout quality filter).

    Returns False (no bonus) when 52-week data is unavailable (<252 trading days).
    A stock without 52-week history cannot be confirmed as "near a historical high"
    and should not receive the quality bonus.
    """
    pct = features.get("pct_from_52w_high")
    if pct is None:
        return False   # insufficient history → no bonus, not a positive signal
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

    # ATR volatility gate: ATR > 5% of price means stop is too wide to control
    # (mirrors the LLM prompt filter "ATR / close > 0.05 → NO NEW TRADE")
    if atr / close > 0.05:
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
      - volume expansion (ratio > 1.5)
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
    above_200ma  = features.get("above_200ma")

    if not close or not atr:
        return None
    if range_vs_atr is None or not breakout:
        return None

    range_expanded  = bool(range_vs_atr > 1.5)
    # 1.5× volume minimum for Strategy B — intentionally lower than feature_layer's
    # 2.0× boolean threshold for Strategy A.  Rationale: volatility breakouts already
    # require daily_range > 1.5 ATR + 20d high as primary quality gates; the range
    # expansion itself signals institutional activity.  Requiring 2.0× would eliminate
    # many genuine breakouts where range confirmation substitutes for raw volume surge.
    # Previously 1.2×; raised to 1.5× to filter weak-volume false breakouts.
    volume_expanded = bool(vol_ratio is not None and vol_ratio > 1.5)

    if not (range_expanded and breakout and volume_expanded):
        return None

    # ATR volatility gate: ATR > 5% of price means stop is too wide to control
    if atr / close > 0.05:
        return None

    # RS gate
    if not _rs_positive(features, market_context):
        return None

    entry = close
    # Use ATR stop only — breakout_stop at high_20d*0.99 is too tight and causes
    # premature stop-outs when price retests the breakout level (very common, ~50% of
    # breakouts retest before continuing). ATR already accounts for typical volatility.
    stop = round(entry - ATR_STOP_MULT * atr, 2)

    spy_10d   = (market_context or {}).get("spy_10d_return") or 0
    stock_10d = features.get("momentum_10d_pct") or 0
    rs_strong = bool(stock_10d > spy_10d * 1.2)
    near_high = _near_52w_high(features)

    # above_200ma as soft quality filter: breakouts in established uptrends have
    # far better follow-through than below-200MA "dead-cat bounce" type breakouts.
    # Weight 0.25 (same as other soft conditions):
    #   all-hard + above_200ma → (3+0.25)/(3.5+0.25) = 3.25/3.75 ≈ 0.867  (standalone ≥ 0.85 ✓)
    #   all-hard, no above_200ma → 3.0/3.75 = 0.80  (needs news/confirmation)
    above_200_bonus = bool(above_200ma) if above_200ma is not None else False
    confidence = _confidence([
        (range_expanded,   1.0),
        (breakout,         1.0),
        (volume_expanded,  1.0),
        (rs_strong,        0.25),  # bonus: meaningfully outperforms market
        (near_high,        0.25),  # bonus: near 52-week highs
        (above_200_bonus,  0.25),  # bonus: breakout in established uptrend
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
            "above_200ma":         above_200ma,
            "rs_vs_spy":           round(stock_10d - spy_10d, 4),
            "pct_from_52w_high":   features.get("pct_from_52w_high"),
        },
    }


def strategy_c_earnings(ticker, features, market_context=None):
    """
    Strategy C – Earnings Event Setup.

    Hard conditions:
      - earnings within 5–15 days
      - positive price momentum (10d > 0%) — minimum gate: stock must not be declining
        into earnings; flat/falling setups have much higher miss-risk

    Soft conditions (boost confidence, tiered by strength):
      - momentum > 5%  (was previously the hard gate; now a quality tier, weight 1.0)
      - momentum > 10% (very strong pre-earnings momentum, weight 0.5)
      - stock above 200MA (established trend quality, weight 0.5)
      - positive historical EPS surprise (weight 1.0, only when data available)

    Confidence tiers (illustrative, no pos_surprise data):
      event + >5% + >10% + 200ma = 3.0/3.0 = 1.00  (standalone)
      event + >5% + 200ma        = 2.5/3.0 = 0.833 (needs news confirmation)
      event + >5%                = 2.0/3.0 = 0.667 (needs news + high TQS)
      event only (0-5% momentum) = 1.0/3.0 = 0.333 (too low to trade)
    With pos_surprise (total weight 4.0):
      event + >5% + 200ma + surprise = 3.5/4.0 = 0.875 (standalone ≥ 0.85 ✓)

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

    # Require any positive momentum — stock must not be declining into earnings.
    # Lowered from >5% to >0%: mild-momentum setups (1–5%) can qualify when supported
    # by positive surprise history and above-200MA, but their low confidence score
    # (< 0.75) means they will require strong news confirmation to generate a trade.
    if momentum_10d is None or momentum_10d <= 0.0:
        return None

    # ATR volatility gate: high-vol stocks ahead of earnings have uncontrollable gaps
    if atr / close > 0.05:
        return None

    # RS gate: earnings plays still need the stock to outperform the market.
    # A stock drifting into earnings while underperforming SPY rarely has follow-through.
    if not _rs_positive(features, market_context):
        return None

    entry = close
    stop  = round(entry - ATR_STOP_MULT * atr, 2)

    above_200ma = features.get("above_200ma")

    # Tiered confidence: >5% momentum is the quality threshold that was previously the
    # hard gate — keeping it as a weight-1.0 soft condition preserves the differentiation
    # between "barely positive" and "strong momentum" setups while allowing the former
    # to reach the LLM (where confidence and TQS gates will filter most of them out).
    # NOTE: only include pos_surprise when data is available; missing data → neutral.
    confidence_checks = [
        (event_window,                        1.0),
        ((momentum_10d or 0) > 0.05,          1.0),   # medium momentum tier (prev. hard gate)
        ((momentum_10d or 0) > 0.10,          0.5),   # bonus: very strong momentum >10%
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
    # Market regime gate: hard-block in BEAR; soft-filter in NEUTRAL.
    # BEAR  (both SPY + QQQ below 200MA): no new long signals — trend is down.
    # NEUTRAL (mixed): only standalone-quality signals (confidence ≥ 0.85) pass.
    # These gates mirror the LLM prompt direction rules but enforce them in code
    # so weak signals never reach the LLM in adverse market conditions.
    regime = (market_context or {}).get("market_regime", "").upper()
    if regime == "BEAR":
        logger.info("BEAR market regime — no long signals generated")
        return []

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

    # NEUTRAL market: only allow signals with confidence strictly > 0.85.
    # The LLM prompt requires confidence > 0.85 (not >=) for NEUTRAL market —
    # signals at exactly 0.85 need news confirmation even in BULL, so in a mixed
    # market they should not reach the LLM at all without news already present.
    if regime == "NEUTRAL":
        before = len(deduped)
        deduped = [s for s in deduped if s["confidence_score"] > 0.85]
        if len(deduped) < before:
            logger.info(
                f"NEUTRAL market: filtered {before - len(deduped)} low-confidence signals "
                f"(< 0.85) — {len(deduped)} remain"
            )

    return deduped
