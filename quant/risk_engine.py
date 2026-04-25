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

from constants import (
    ATR_STOP_MULT,
    ATR_TARGET_MULT,
    TREND_TECH_TARGET_ATR_MULT,
    TREND_COMMODITIES_TARGET_ATR_MULT,
    ROUND_TRIP_COST_PCT,
    EXEC_LAG_PCT,
)

logger = logging.getLogger(__name__)

# Static sector map for the watchlist + common holdings.
# Used by LLM prompt to enforce the 40% sector concentration rule.
# Without this data the LLM cannot compute actual sector weights — the rule was blind.
# Source: GICS sector classification.  Update when adding new tickers.
SECTOR_MAP = {
    # Technology / Semiconductors
    "NVDA": "Technology", "AMD":  "Technology", "MU":   "Technology",
    "CRDO": "Technology", "INTC": "Technology", "AVGO": "Technology",
    "TSM":  "Technology", "QCOM": "Technology", "AMAT": "Technology",
    "ASML": "Technology",
    # Technology / Software & Internet
    "META": "Technology", "GOOG": "Technology", "GOOGL": "Technology",
    "MSFT": "Technology", "AAPL": "Technology", "CRM":  "Technology",
    "NOW":  "Technology", "SNOW": "Technology", "DDOG": "Technology",
    "APP":  "Technology", "PLTR": "Technology",
    # Consumer Discretionary
    "TSLA": "Consumer Discretionary", "AMZN": "Consumer Discretionary",
    "MCD":  "Consumer Discretionary", "SBUX": "Consumer Discretionary",
    "BKNG": "Consumer Discretionary",
    # Communication Services
    "NFLX": "Communication Services", "DIS":  "Communication Services",
    "SPOT": "Communication Services",
    # Financials
    "COIN": "Financials", "V":    "Financials", "MA":   "Financials",
    "GS":   "Financials", "JPM":  "Financials",
    # Healthcare
    "LLY":  "Healthcare", "NVO":  "Healthcare",
    "UNH":  "Healthcare", "ISRG": "Healthcare",
    # Energy
    "XOM":  "Energy",     "CVX":  "Energy",
    # Industrials
    "CAT":  "Industrials", "DE":   "Industrials",
    "GE":   "Industrials", "RTX":  "Industrials",
    # ETFs (broad market)
    "QQQ":  "ETF", "SPY": "ETF", "IWM": "ETF",
    # Commodities / Safe Haven
    "IAU":  "Commodities", "GLD": "Commodities", "SLV": "Commodities",
    "GDX":  "Commodities",
}


def enrich_signal_with_risk(signal, atr, atr_target_mult=None):
    """
    Add target_price, risk_per_share, reward_per_share, risk_reward_ratio,
    and net_risk_reward_ratio to a signal dict.

    stop_price is already set by the strategy (entry − 1.5×ATR).
    This function adds the target and computes both gross and cost-adjusted R:R.

    Cost model (matches performance_engine.py):
        cost = entry_price × ROUND_TRIP_COST_PCT  (per share)
        net_reward = reward_per_share - cost
        net_risk   = risk_per_share   + cost
        net_rr     = net_reward / net_risk

    For the standard 3.5/1.5 ATR structure at entry=$100:
        gross R:R  ≈ 2.33:1
        net R:R    ≈ 1.70:1  (cost eats ~27% due to fixed-dollar cost vs variable reward)

    The gross risk_reward_ratio is kept for position-sizing gates; the net ratio
    is informational for the LLM when evaluating marginal trade quality.

    Args:
        signal (dict): Signal from signal_engine
        atr    (float): ATR value for this ticker
        atr_target_mult (float): Optional override for ATR_TARGET_MULT constant

    Returns:
        dict: Enriched signal
    """
    entry = signal["entry_price"]
    stop  = signal.get("stop_price") or round(entry - ATR_STOP_MULT * atr, 2)

    _target_mult = atr_target_mult if atr_target_mult is not None else ATR_TARGET_MULT
    target           = round(entry + _target_mult * atr, 2)
    risk_per_share   = round(entry - stop, 2)
    reward_per_share = round(target - entry, 2)
    rr_ratio         = (round(reward_per_share / risk_per_share, 2)
                        if risk_per_share > 0 else None)

    # Cost-adjusted R:R: reflects actual expected value per the performance engine's P&L model.
    # cost is fixed per share (% of entry price), so it shrinks reward AND enlarges risk equally.
    cost_per_share    = round(entry * ROUND_TRIP_COST_PCT, 4)
    net_reward        = reward_per_share - cost_per_share
    net_risk          = risk_per_share   + cost_per_share
    net_rr_ratio      = (round(net_reward / net_risk, 2)
                         if net_risk > 0 and net_reward > 0 else None)

    # Execution-lag-adjusted R:R: accounts for next-day open slippage.
    # Entry is today's close; actual fill is next-day open (typically +0.3–1.0% higher
    # on breakout days). At +0.5% gap on entry=$100: adj_entry=$100.50, stop stays $98.50.
    # adj_reward = $103.50 - $100.50 = $3.00  vs  adj_risk = $100.50 - $98.50 = $2.00 → 1.50:1
    # This field is informational — the LLM uses it to reject trades where the gap cost
    # pushes net expected value below breakeven. The gross R:R gate (≥2.0) uses close price.
    adj_entry    = round(entry * (1 + EXEC_LAG_PCT), 2)
    adj_reward   = round(target   - adj_entry, 2)
    adj_risk     = round(adj_entry - stop,     2)
    adj_net_cost = round(adj_entry * ROUND_TRIP_COST_PCT, 4)
    exec_lag_adj_rr = (
        round((adj_reward - adj_net_cost) / (adj_risk + adj_net_cost), 2)
        if adj_risk > 0 and adj_reward > adj_net_cost else None
    )

    return {
        **signal,
        "stop_price":                round(stop, 2),
        "target_price":              target,
        "risk_per_share":            risk_per_share,
        "reward_per_share":          reward_per_share,
        "risk_reward_ratio":         rr_ratio,
        "net_risk_reward_ratio":     net_rr_ratio,       # after 0.35% round-trip execution cost
        "exec_lag_adj_net_rr":       exec_lag_adj_rr,    # after +0.5% assumed next-day open gap
    }


def _retarget_signal_with_atr_mult(signal, atr, target_mult):
    """Recompute target/R:R fields for a strategy-specific target width."""
    entry = signal["entry_price"]
    stop = signal["stop_price"]
    target = round(entry + target_mult * atr, 2)
    risk_per_share = round(entry - stop, 2)
    reward_per_share = round(target - entry, 2)
    rr_ratio = (
        round(reward_per_share / risk_per_share, 2)
        if risk_per_share > 0 else None
    )

    cost_per_share = round(entry * ROUND_TRIP_COST_PCT, 4)
    net_reward = reward_per_share - cost_per_share
    net_risk = risk_per_share + cost_per_share
    net_rr_ratio = (
        round(net_reward / net_risk, 2)
        if net_risk > 0 and net_reward > 0 else None
    )

    adj_entry = round(entry * (1 + EXEC_LAG_PCT), 2)
    adj_reward = round(target - adj_entry, 2)
    adj_risk = round(adj_entry - stop, 2)
    adj_net_cost = round(adj_entry * ROUND_TRIP_COST_PCT, 4)
    exec_lag_adj_rr = (
        round((adj_reward - adj_net_cost) / (adj_risk + adj_net_cost), 2)
        if adj_risk > 0 and adj_reward > adj_net_cost else None
    )

    return {
        **signal,
        "target_price": target,
        "reward_per_share": reward_per_share,
        "risk_reward_ratio": rr_ratio,
        "net_risk_reward_ratio": net_rr_ratio,
        "exec_lag_adj_net_rr": exec_lag_adj_rr,
        "target_mult_used": target_mult,
        "target_width_applied": target_mult,
    }


def _trade_quality_score(sig, features):
    """
    Compute Trade Quality Score (TQS) — pre-calculated so LLM reads it directly.

    Formula:
        TQS = 0.40 × confidence_score
            + 0.25 × trend_score           (0-1 from feature_layer)
            + 0.20 × vol_norm              (volume_spike_ratio / 2.0, capped at 1.0)
            + 0.15 × momentum_norm         (momentum_10d_pct / 0.10, clamped to [-1, 1])

    NOTE: Weights (0.40/0.25/0.20/0.15) are heuristic — chosen by domain intuition,
    not calibrated against historical data.  Once the forward_tester accumulates 30+
    trades per configuration, these weights should be calibrated by running a
    single-parameter sweep via the backtester.  Until then, treat them as reasonable
    defaults subject to revision.

    Returns:
        float: 0.0 – 1.0
    """
    conf       = sig.get("confidence_score", 0)
    trend_sc   = (features or {}).get("trend_score") or 0
    vol_ratio  = (features or {}).get("volume_spike_ratio") or 0
    momentum   = (features or {}).get("momentum_10d_pct") or 0

    vol_norm  = min(vol_ratio / 2.0, 1.0)
    # Negative momentum actively penalises TQS — falling stocks should not be tradeable.
    # Clamped to [-1, 1] so a -10% mover gets full -0.15 penalty (pushing TQS below 0.60).
    mom_norm  = max(-1.0, min(momentum / 0.10, 1.0))

    tqs = 0.40 * conf + 0.25 * trend_sc + 0.20 * vol_norm + 0.15 * mom_norm
    return round(max(0.0, min(tqs, 1.0)), 3)


def enrich_signals(signals, features_dict, atr_target_mult=None):
    """
    Enrich all signals with risk parameters and Trade Quality Score.

    Args:
        signals       (list[dict]): From signal_engine.generate_signals()
        features_dict (dict):       {ticker: features} for ATR + TQS fields
        atr_target_mult (float):    Optional override for ATR_TARGET_MULT constant

    Returns:
        list[dict]: Signals with risk fields + trade_quality_score added.
        Dropped signals are stored in the module-level ``last_dropped_signals``
        list so callers (run.py, report_generator) can surface them.
    """
    enriched = []
    dropped  = []

    for sig in signals:
        ticker   = sig["ticker"]
        features = features_dict.get(ticker) or {}
        atr      = features.get("atr")

        if not atr or atr <= 0:
            logger.warning(
                f"{ticker}: ATR unavailable — signal dropped. "
                "LLM cannot size or gate without risk parameters (no stop/target/R:R)."
            )
            dropped.append({
                "ticker": ticker, "strategy": sig.get("strategy"),
                "confidence": sig.get("confidence_score"),
                "reason": "ATR unavailable",
            })
            continue  # Drop: an incomplete signal is worse than no signal

        enriched_sig = enrich_signal_with_risk(sig, atr, atr_target_mult=atr_target_mult)

        # Code-level exec_lag gate: drop signals where the overnight-gap-adjusted
        # net R:R is < 1.2.  The LLM prompt contains the same rule, but LLMs can
        # occasionally misread or skip this field.  Enforcing it here guarantees
        # no negative-EV-after-friction signal ever reaches the LLM.
        #
        # Threshold 1.2 (not 1.0) provides a margin above breakeven to account
        # for model error in the +0.5% assumed gap (actual gap can reach +1.0%
        # on strong breakout days).  At exec_lag_adj_net_rr = 1.2:
        #   adj_reward = 1.2 × (adj_risk + adj_net_cost) + adj_net_cost = EV > 0
        # Signals with standard 1.5×ATR stop on liquid watchlist stocks
        # (ATR ≥ 1.5% of price) always produce exec_lag_adj_net_rr ≥ 1.40,
        # so this gate only drops genuinely thin-stop situations.
        exec_lag_rr = enriched_sig.get("exec_lag_adj_net_rr")
        if exec_lag_rr is not None and exec_lag_rr < 1.2:
            logger.warning(
                f"{ticker}: signal dropped — exec_lag_adj_net_rr={exec_lag_rr:.2f} < 1.2 "
                "(negative EV after overnight gap + round-trip cost)"
            )
            dropped.append({
                "ticker": ticker, "strategy": sig.get("strategy"),
                "confidence": sig.get("confidence_score"),
                "exec_lag_rr": exec_lag_rr,
                "reason": f"exec_lag_adj_net_rr={exec_lag_rr:.2f} < 1.2",
            })
            continue

        # Gap vulnerability: how tight is the stop relative to typical overnight gaps?
        # Breakout stocks commonly gap 2-3% overnight.  A stop < 2% below entry
        # means a gap-through-stop can turn a planned 1% risk into 8-15% loss.
        # Surface a warning so the LLM can factor this into its decision; do NOT auto-reject.
        _entry = enriched_sig["entry_price"]
        gap_vuln = round((_entry - enriched_sig["stop_price"]) / _entry, 4) if _entry > 0 else 0
        enriched_sig["gap_vulnerability_pct"] = gap_vuln
        if gap_vuln < 0.02:
            enriched_sig["gap_warning"] = (
                f"Stop is only {gap_vuln*100:.1f}% below entry — typical overnight gaps "
                "on breakout stocks are 2-3%.  A gap through the stop would cause a loss "
                "far exceeding planned risk.  Consider widening stop or reducing size."
            )

        enriched_sig["trade_quality_score"] = _trade_quality_score(sig, features)
        # Inject sector so LLM can enforce the 40% sector concentration rule.
        # Without this field the rule was enforced blindly from LLM training knowledge.
        enriched_sig["sector"] = SECTOR_MAP.get(ticker, "Unknown")
        if (
            enriched_sig.get("strategy") == "trend_long"
            and enriched_sig["sector"] == "Technology"
        ):
            # exp-20260425-027: Technology trend alpha was being clipped by the
            # shared target width. Keep the override narrow to avoid replaying
            # the rejected broad trend-widening family.
            enriched_sig = _retarget_signal_with_atr_mult(
                enriched_sig,
                atr,
                TREND_TECH_TARGET_ATR_MULT,
            )
            enriched_sig["tech_trend_target_width_applied"] = (
                TREND_TECH_TARGET_ATR_MULT
            )
        if (
            enriched_sig.get("strategy") == "trend_long"
            and enriched_sig["sector"] == "Commodities"
        ):
            # exp-20260425-031: commodity trend exposure carried useful
            # convexity; the alpha leak was clipping winners, not oversizing.
            enriched_sig = _retarget_signal_with_atr_mult(
                enriched_sig,
                atr,
                TREND_COMMODITIES_TARGET_ATR_MULT,
            )
            enriched_sig["commodity_trend_target_width_applied"] = (
                TREND_COMMODITIES_TARGET_ATR_MULT
            )
        # Inject days_to_earnings for ALL signal types (not just earnings_event_long).
        # The LLM prompt blocks ANY new trade when dte ≤ 4 — including trend_long and
        # breakout_long — but the LLM has no way to enforce this rule without the data.
        # A valid 20-day breakout 3 days before earnings exposes the position to an
        # ±8-15% overnight gap that overwhelms the 1.5×ATR stop.
        dte = features.get("days_to_earnings")
        if dte is not None:
            enriched_sig["days_to_earnings"] = dte
        enriched.append(enriched_sig)

    # Store for inspection by callers (report_generator, run.py logging).
    # Mutate in-place so that callers holding a reference to the list see updates.
    last_dropped_signals.clear()
    last_dropped_signals.extend(dropped)
    if dropped:
        logger.info(
            f"Enrichment dropped {len(dropped)} signal(s): "
            + ", ".join(f"{d['ticker']}({d['reason']})" for d in dropped)
        )

    return enriched


# Module-level storage for signals dropped during the last enrich_signals() call.
# Callers can read this after enrich_signals() returns to surface dropped signals
# in reports, logs, or LLM prompts.  Reset on each enrich_signals() invocation.
last_dropped_signals: list[dict] = []
