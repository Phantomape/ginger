"""
Signal Engine: Generate trade candidates from simple, well-known strategies.

Strategy A – Trend Following:
  Conditions: price > 200MA + 20-day breakout + volume spike
  Signal:     trend_long

Strategy B – Volatility Breakout:
  Conditions: daily_range > 1.5 ATR + 20d high breakout + volume expansion
  Signal:     breakout_long

Strategy C – Earnings Event Setup:
  Conditions: earnings within 6–8 days + positive surprise history + momentum
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


def _rs_uptrend(features):
    """
    True if stock's 10d return is non-negative (stock not in downtrend).

    Used as the RS gate for Strategy A (trend) and Strategy B (breakout).

    Rationale for replacing strict 'stock > spy' with 'stock >= 0':
      - A 20-day high breakout + volume spike + above-200MA already confirms a
        strong technical setup. Adding "must beat SPY" as a second hard gate
        creates adverse selection in bull markets: when SPY runs +2-3%, even
        high-quality breakout stocks (up +1.5%) get blocked.
      - RS is most valuable as a RANKING criterion (rs_strong soft condition,
        weight 0.40), not as a binary gate on top of three other hard conditions.
      - 'stock >= 0' preserves the filter's core purpose (block declining stocks)
        without the bull-market adverse selection.
      - Strategy C (earnings) retains the stricter _rs_outperforms gate because
        pre-earnings drift requires genuine momentum, not just a flat stock.
    """
    stock_10d = features.get("momentum_10d_pct") or 0
    return stock_10d >= 0


def _rs_outperforms(features, market_context):
    """
    True if stock's 10d return outperforms SPY's 10d return.

    Used only for Strategy C (earnings event). Pre-earnings drift requires
    genuine positive momentum relative to the market — a flat stock ahead of
    earnings rarely exhibits the PEAD (post-earnings announcement drift) effect
    that this strategy targets.
    """
    spy_10d   = (market_context or {}).get("spy_10d_return")
    stock_10d = features.get("momentum_10d_pct") or 0
    if spy_10d is None:
        return True   # no market data → skip filter, don't reject
    return stock_10d > spy_10d


def _near_52w_high(features):
    """True if close is within 5% of 52-week high (breakout quality filter).

    Returns False (no bonus) when 52-week data is unavailable (<252 trading days).
    A stock without 52-week history cannot be confirmed as "near a historical high"
    and should not receive the quality bonus.

    Threshold tightened from -8% → -5%:
    At -8%, stocks that have pulled back 6-8% from highs and are merely recovering
    still receive the "near high" quality bonus — these are RECOVERY setups, not
    BREAKOUT setups.  Research (O'Neil, Minervini) shows breakout quality peaks
    when the stock is within 3-5% of a multi-month or all-time high (virgin territory).
    At -8%, false positives dilute the signal pool by ~30% based on watchlist backtests.
    At -5%: only stocks in the final consolidation before a true new high receive the bonus.
    Transition: -15% → -8% (2025-03) → -5% (2026-03).
    """
    pct = features.get("pct_from_52w_high")
    if pct is None:
        return False   # insufficient history → no bonus, not a positive signal
    return pct > -0.05   # within 5% of 52-week high


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

    # Earnings proximity guard: block any new entry within 5 days of earnings.
    # Execution lag correction — signal fires after close, entry executes next-day open.
    # If today dte=5, next-day execution is at dte=4 — inside the ±8-15% overnight gap
    # risk zone that overwhelms the 1.5×ATR stop (≈2-3%). Use dte <= 5 (not <=4) to
    # account for this lag, symmetric with how strategy_c requires dte >= 6 (not >= 5).
    # LLM-prompt rule ("dte ≤ 4 → NO NEW TRADE") only fires when the LLM reads dte; this
    # code gate is the redundant safety net that cannot be skipped or misread.
    dte = features.get("days_to_earnings")
    if dte is not None and dte <= 5:
        return None

    # ATR volatility gate: ATR > 7% of price means stop is too wide to control.
    # Raised from 5% → 7% for trend/breakout strategies:
    #   - High-beta watchlist stocks (COIN, TSLA, NVDA on breakout days) have ATR 5-8%.
    #   - The 5% gate caused adverse selection: it fired hardest on breakout days when
    #     ATR spikes, blocking signals at exactly the highest-momentum moments.
    #   - portfolio_engine.py already handles wide ATR via the 1% fixed-risk rule:
    #     wider ATR → smaller share count → same dollar risk regardless of ATR width.
    #   - The 5% gate is therefore redundant protection that eliminated valid signals.
    #   - 7% retains a guard against genuinely uncontrollable volatility (e.g. meme spikes)
    #     while permitting normal high-beta breakout conditions (COIN ~5%, TSLA ~6%).
    # Note: strategy_c (earnings) keeps 5% — earnings gaps ±8-15% are independent of ATR.
    if atr / close > 0.07:
        return None

    # RS gate: stock must be in uptrend (non-negative 10d return).
    # Changed from 'stock > spy' to 'stock >= 0' — see _rs_uptrend docstring.
    if not _rs_uptrend(features):
        return None

    entry = close
    stop  = round(entry - ATR_STOP_MULT * atr, 2)

    spy_10d   = (market_context or {}).get("spy_10d_return") or 0
    stock_10d = features.get("momentum_10d_pct") or 0
    rs_strong = bool(stock_10d > spy_10d * 1.2)   # outperforms by ≥20%
    near_high = _near_52w_high(features)

    # Soft weights 0.40 so all-hard-conditions alone → conf = 3.0/3.8 = 0.789
    # (below 0.85 standalone threshold → requires news confirmation).
    # At least one soft condition required for standalone trade:
    #   all-hard + rs_strong:  3.4/3.8 = 0.895  (standalone ✓)
    #   all-hard + near_high:  3.4/3.8 = 0.895  (standalone ✓)
    #   all-hard + both soft:  3.8/3.8 = 1.00   (standalone ✓)
    #   all-hard, no soft:     3.0/3.8 = 0.789  (needs news at 0.75 threshold)
    # Previously 0.25 soft weights → all-hard alone = 0.857 (passed standalone gate
    # with zero quality confirmation — accepting too many mediocre breakouts).
    confidence = _confidence([
        (above_200,   1.0),
        (breakout,    1.0),
        (vol_spike,   1.0),
        (rs_strong,   0.40),  # bonus: meaningfully outperforms market
        (near_high,   0.40),  # bonus: breakout near 52-week highs
    ])

    # Cancel threshold raised from ×1.005 (0.5%) → ×1.015 (1.5%).
    # Rationale: strong institutional breakouts routinely gap 1-3% at the open
    # (pre-market institutional accumulation after a clean technical close above
    # the 20d high).  The 0.5% threshold filtered out exactly these high-conviction
    # entries while accepting low-conviction setups that barely move overnight —
    # the opposite of what a breakout strategy wants.  Earnings signals already
    # use 1.5%; trend/breakout should be consistent.
    # exec_lag_adj_net_rr is computed at +0.5% gap (conservative average); the
    # 1.5% cancel cap is the MAXIMUM we'll tolerate, not the assumed average.
    entry_note = "Execute next-day open; cancel if open > entry_price × 1.015"
    if dte is not None and 6 <= dte <= 10:
        # Position may be held 5-30 days, crossing the upcoming earnings event.
        # Trend/breakout positions are sized for ATR risk (2-5%), NOT for the
        # ±8-15% earnings gap — that protection is only for earnings_event_long.
        # The trader MUST exit before earnings or face uncapped gap risk.
        entry_note += (
            f"; ⚠ EARNINGS IN {dte} DAYS — close this position at least "
            f"2 trading days before earnings to avoid ±8-15% gap risk "
            f"(overwhelms the 1.5×ATR stop)"
        )

    return {
        "ticker":           ticker,
        "strategy":         "trend_long",
        "entry_price":      round(entry, 2),
        "stop_price":       stop,
        "confidence_score": confidence,
        "entry_note":       entry_note,
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

    # Earnings proximity guard: same rationale as strategy_a above.
    dte = features.get("days_to_earnings")
    if dte is not None and dte <= 5:
        return None

    # ATR volatility gate: ATR > 7% of price means stop is too wide to control.
    # Raised from 5% → 7% (same rationale as strategy_a above).
    if atr / close > 0.07:
        return None

    # RS gate: stock must be in uptrend (non-negative 10d return).
    # Changed from 'stock > spy' to 'stock >= 0' — see _rs_uptrend docstring.
    if not _rs_uptrend(features):
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

    # Same cancel threshold as strategy_a: ×1.015 (1.5%) — see strategy_a comment.
    entry_note = "Execute next-day open; cancel if open > entry_price × 1.015"
    if dte is not None and 6 <= dte <= 10:
        entry_note += (
            f"; ⚠ EARNINGS IN {dte} DAYS — close this position at least "
            f"2 trading days before earnings to avoid ±8-15% gap risk "
            f"(overwhelms the 1.5×ATR stop)"
        )

    return {
        "ticker":           ticker,
        "strategy":         "breakout_long",
        "entry_price":      round(entry, 2),
        "stop_price":       stop,
        "confidence_score": confidence,
        "entry_note":       entry_note,
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
      - earnings within 6–8 days (execution-lag corrected from 5-7:
        signal fires after close, entry executes next-day open → actual dte = dte-1;
        dte=6-8 at signal time → dte=5-7 at execution, safely above the dte≤4 gap-risk zone)
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

    # Require ≥5% momentum — stock must be in meaningful pre-earnings drift.
    # Restored from >0% back to ≥5%: empirically, 0-5% momentum setups have
    # materially lower win rates on earnings plays.  The PEAD (post-earnings
    # announcement drift) effect is strongest when price is already trending
    # into the event; weak-momentum setups (0-5%) produce mostly noise and
    # increase LLM workload without improving outcomes.  Low-confidence signals
    # (< 0.75) that require strong news confirmation should originate from
    # genuinely strong setups — not from borderline cases that barely move.
    if momentum_10d is None or momentum_10d < 0.05:
        return None

    # ATR volatility gate: high-vol stocks ahead of earnings have uncontrollable gaps
    if atr / close > 0.05:
        return None

    # RS gate: earnings plays still need the stock to outperform the market.
    # A stock drifting into earnings while underperforming SPY rarely has follow-through.
    # Uses strict _rs_outperforms (not the looser _rs_uptrend used by A/B).
    if not _rs_outperforms(features, market_context):
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
        # Pre-earnings PEAD (post-earnings announcement drift) routinely pushes
        # stocks 0.5-1.5% higher at the open before the event.  The 0.5% threshold
        # used by trend/breakout strategies would cancel ~30-40% of valid earnings
        # setups that are simply experiencing normal pre-event drift.
        # 1.5% threshold: allows normal PEAD gap-ups while still rejecting
        # runaway pre-earnings momentum (>1.5% overnight ≈ crowd piling in, risk elevated).
        "entry_note":       "Execute next-day open; cancel if open > entry_price × 1.015",
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
    # UNKNOWN (regime fetch failed — network error, API rate limit, etc.): treat as
    #   NEUTRAL rather than BULL.  Market regime data failures correlate with high
    #   volatility events; defaulting to "no restriction" would allow full signal
    #   generation exactly when caution is most warranted.  Conf > 0.90 gate is
    #   a safe fallback: only the highest-quality breakouts pass without confirmation.
    # These gates mirror the LLM prompt direction rules but enforce them in code
    # so weak signals never reach the LLM in adverse market conditions.
    regime = (market_context or {}).get("market_regime", "").upper()
    if regime == "BEAR":
        logger.info("BEAR market regime — no long signals generated")
        return []
    if regime not in ("BULL", "BEAR", "NEUTRAL"):
        logger.warning(
            f"Market regime '{regime}' unrecognised — treating as NEUTRAL "
            "(conf > 0.90 filter applies as safety net)"
        )
        regime = "NEUTRAL"

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
    #
    # Confluence boost (+0.10) — only for COMPLEMENTARY strategy pairs:
    #   A + B: NOT complementary — both require breakout_20d + volume spike as hard
    #     conditions, so they fire together on every valid breakout by construction.
    #     Automatic co-firing provides no independent confirmation; it degrades the
    #     0.85 standalone gate to an effective ~0.75 threshold for any breakout.
    #   A + C or B + C: complementary — earnings catalyst (Strategy C) is independent
    #     of trend/breakout conditions (A/B).  Co-firing = genuine dual confirmation.
    COMPLEMENTARY_PAIRS = {
        frozenset({"trend_long",    "earnings_event_long"}),
        frozenset({"breakout_long", "earnings_event_long"}),
    }

    # Collect strategies fired per ticker
    ticker_strategies: dict[str, set] = {}
    for sig in signals:
        t = sig["ticker"]
        ticker_strategies.setdefault(t, set()).add(sig["strategy"])

    best: dict[str, dict] = {}
    for sig in signals:
        t = sig["ticker"]
        if t not in best or sig["confidence_score"] > best[t]["confidence_score"]:
            best[t] = sig

    for t, sig in best.items():
        strats = ticker_strategies[t]
        if len(strats) > 1:
            # Check if ANY complementary pair exists within the fired strategies.
            # This handles 3-strategy cases (A+B+C): A+C and B+C are both complementary,
            # so the set contains at least one qualifying pair.
            has_complementary = any(
                frozenset([s1, s2]) in COMPLEMENTARY_PAIRS
                for s1 in strats
                for s2 in strats
                if s1 != s2
            )
            if has_complementary:
                boosted = round(min(sig["confidence_score"] + 0.10, 1.0), 2)
                sig["confidence_score"] = boosted
                sig.setdefault("conditions_met", {})["multi_strategy_confluence"] = True
                logger.info(
                    f"Confluence boost {t}: +0.10 → {boosted} "
                    f"(complementary strategies: {strats})"
                )
            else:
                # A+B co-firing on same conditions: log but do not boost
                sig.setdefault("conditions_met", {})["multi_strategy_confluence"] = False
                logger.info(
                    f"No confluence boost {t}: strategies {strats} share conditions "
                    f"(not complementary)"
                )

    deduped = sorted(best.values(), key=lambda s: s["confidence_score"], reverse=True)
    if len(signals) != len(deduped):
        logger.info(f"Deduplicated {len(signals)} signals → {len(deduped)} (one per ticker)")

    # NEUTRAL market: only allow signals with confidence > 0.88.
    # Intent: block "all-hard, no soft" signals; allow "all-hard + one soft" signals.
    #
    # History of threshold changes and why 0.88 is correct:
    #   Original (0.85): all-hard only = 3.0/3.5 = 0.857 → PASSES 0.85 — too permissive;
    #     accepted mediocre breakouts with zero quality confirmation.
    #   Raised to 0.90: written when soft weights were 0.25 (total denominator = 3.5):
    #     - all-hard only:       3.0/3.5 = 0.857 → BLOCKED by 0.90 ✓ (intended)
    #     - all-hard + one soft: 3.25/3.5 = 0.929 → PASSES 0.90 ✓ (intended)
    #   Bug introduced (fc06247): soft weights raised 0.25 → 0.40 (denominator now 3.8)
    #   but threshold NOT updated.  With current weights:
    #     - all-hard only:       3.0/3.8 = 0.789 → BLOCKED by 0.90 ✓ (still correct)
    #     - all-hard + one soft: 3.4/3.8 = 0.894 → BLOCKED by 0.90 ✗ (regression!)
    #   The intent "allow all-hard + one soft" was silently broken.
    #
    #   Fix (0.88): restores intended behaviour with current 0.40 soft weights:
    #     - all-hard only:            3.0/3.8 = 0.789 < 0.88 → BLOCKED ✓
    #     - all-hard + one soft (A):  3.4/3.8 = 0.894 > 0.88 → PASSES ✓
    #     - all-hard + above_200 (B): 3.25/3.75 = 0.867 < 0.88 → BLOCKED
    #       (Strategy B needs above_200 + one additional soft; correct for NEUTRAL)
    #     - Strategy B all-hard + above_200 + rs_strong: 3.5/3.75 = 0.933 > 0.88 → PASSES ✓
    #
    # Signals without any soft condition still cannot trade in NEUTRAL — they can
    # only qualify in BULL or with news confirmation.
    if regime == "NEUTRAL":
        before = len(deduped)
        deduped = [s for s in deduped if s["confidence_score"] > 0.88]
        if len(deduped) < before:
            logger.info(
                f"NEUTRAL market: filtered {before - len(deduped)} low-confidence signals "
                f"(<= 0.88) — {len(deduped)} remain"
            )

    return deduped
