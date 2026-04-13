"""
Preflight validator — runs BEFORE data is handed to the LLM.

Responsibility:
  1. Compute a unified account_state machine (FIRE / DEFENSIVE / NORMAL)
     so the LLM reads a pre-judged verdict, not a pile of raw flags.
  2. Flag delayed/historic stop breaches so the LLM can distinguish
     "stop just triggered" vs "stop was breached weeks ago — forced liquidation".
  3. Lock new_trade to "NO NEW TRADE" in the program layer when hard rules
     forbid it — the LLM must not override hard constraints.
  4. Pre-compute suggested_reduce_pct per HIGH_REDUCE position so the LLM
     doesn't need to look up the REDUCE framework table (removes a prose→data
     translation step that was a repeated source of errors).
  5. Pre-compute bear_emergency_stop per position when regime=BEAR so the LLM
     can enforce "current_price × 0.95" for ALL positions, including HOLD ones
     not surfaced in section 3b.
  6. Surface data consistency warnings (portfolio value mismatch, etc.).

account_state values:
  FIRE        — ≥1 CRITICAL position exists; all attention goes to fire-fighting
  DEFENSIVE   — BEAR regime OR portfolio heat ≥ 6%; no new positions, trim bias
  NORMAL      — clean slate, new positions permitted if signal is strong enough

breach_status per position:
  OK               — no stop breach
  DELAYED_BREACH   — hard_stop_price > current_price (stop based on avg_cost is
                     above market; stop should have fired but never did)
  HISTORIC_BREACH  — hard_stop_price >> current_price (>20% above market; position
                     has been in free-fall for an extended period)
"""

import logging

logger = logging.getLogger(__name__)

# Heat threshold for DEFENSIVE state (below full 8% cap to give early warning)
DEFENSIVE_HEAT_THRESHOLD = 0.06

# BEAR market tightened stop multiplier: current_price × (1 - BEAR_STOP_PCT)
BEAR_STOP_PCT = 0.05   # −5% from current price (vs default −12%)


def _classify_breach(current_price: float, hard_stop_price: float) -> str:
    """Classify the breach status of a position."""
    if hard_stop_price <= 0:
        return "OK"
    if current_price > hard_stop_price:
        return "OK"
    gap = (hard_stop_price - current_price) / current_price
    if gap >= 0.20:
        return "HISTORIC_BREACH"   # stop is ≥20% above current price
    return "DELAYED_BREACH"        # stop is above current price but <20% gap


def _suggested_reduce_pct(triggered_rules: list, unrealized_pnl_pct: float) -> int:
    """
    Pre-compute the suggested reduce percentage for a HIGH_REDUCE position.

    Encodes the REDUCE framework table from trade_advice.txt so the LLM reads
    a single number instead of performing a multi-step table lookup.

    Returns an integer percentage (25, 33, 50, or 100).
    """
    # Collect rule names (highest urgency was already determined by caller)
    rule_names = {r.get("rule", "") for r in triggered_rules}

    # Hard stop — should be CRITICAL_EXIT, but guard anyway
    if "HARD_STOP" in rule_names:
        return 100

    # ATR stop
    if "ATR_STOP" in rule_names:
        # Deeper loss → bigger cut; use 100% if significantly below stop
        return 100 if (unrealized_pnl_pct or 0) < -0.05 else 50

    # Trailing stop — split on profit level
    if "TRAILING_STOP" in rule_names:
        return 25 if (unrealized_pnl_pct or 0) > 0.30 else 50

    # APPROACHING_HARD_STOP — pre-emptive trim
    if "APPROACHING_HARD_STOP" in rule_names:
        return 50 if (unrealized_pnl_pct or 0) < 0 else 25

    # Signal target reached (3.5×ATR)
    if "SIGNAL_TARGET" in rule_names:
        return 33

    # Profit ladder rules
    if "PROFIT_TARGET" in rule_names:
        return 50
    if "PROFIT_LADDER_50" in rule_names:
        return 25

    # Fallback for any other HIGH urgency rule
    return 50


def enrich_positions_with_breach_status(trend_signals: dict) -> dict:
    """
    Walk trend_signals['signals'] and add breach_status to each position context.

    Returns the enriched trend_signals dict (mutates in place for efficiency).
    """
    signals = trend_signals.get("signals", {}) if trend_signals else {}
    for ticker, sig in signals.items():
        pos_ctx = sig.get("position")
        if not pos_ctx:
            continue
        exit_levels = pos_ctx.get("exit_levels", {})
        hard_stop = exit_levels.get("hard_stop_price", 0)
        current_price = sig.get("close", 0)
        pos_ctx["breach_status"] = _classify_breach(current_price, hard_stop)
    return trend_signals


def compute_account_state(
    trend_signals: dict,
    heat_data: dict,
    regime_data: dict,
) -> dict:
    """
    Compute the top-level account_state and per-position decision_state.

    Args:
        trend_signals: enriched trend_signals dict (after enrich_positions_with_breach_status)
        heat_data:     portfolio_heat dict from portfolio_engine
        regime_data:   market_regime dict from regime.py

    Returns:
        dict with keys:
          account_state         str  — FIRE | DEFENSIVE | NORMAL
          new_trade_locked      bool — True when program layer prohibits new trades
          lock_reason           str  — reason for lock (empty if not locked)
          position_states       dict — {ticker: decision_state str}
          suggested_reduce_pct  dict — {ticker: int} only for HIGH_REDUCE positions
          bear_emergency_stops  dict — {ticker: float} only when regime=BEAR
          data_warnings         list — data consistency issues found
    """
    data_warnings = []
    position_states: dict[str, str] = {}
    suggested_reduce_pct: dict[str, int] = {}

    # ── Regime ──────────────────────────────────────────────────────────────
    regime = regime_data.get("regime", "UNKNOWN") if regime_data else "UNKNOWN"

    # ── Heat ────────────────────────────────────────────────────────────────
    heat_pct       = heat_data.get("portfolio_heat_pct", 0) if heat_data else 0
    can_add        = heat_data.get("can_add_new_positions", True) if heat_data else True
    portfolio_val  = heat_data.get("portfolio_value_usd", 0) if heat_data else 0

    # ── Per-position states ──────────────────────────────────────────────────
    has_critical = False
    signals = trend_signals.get("signals", {}) if trend_signals else {}

    rank = {"CRITICAL": 4, "HIGH": 3, "WARNING": 2, "MEDIUM": 1, "LOW": 0, "REVIEW": 0}

    for ticker, sig in signals.items():
        pos_ctx   = sig.get("position", {})
        if not pos_ctx:
            continue
        exit_sigs        = pos_ctx.get("exit_signals", {})
        breach_st        = pos_ctx.get("breach_status", "OK")
        triggered        = exit_sigs.get("triggered_rules", [])
        unrealized_pnl   = pos_ctx.get("unrealized_pnl_pct", 0) or 0
        max_urgency      = "NONE"
        if triggered:
            max_urgency = max(triggered, key=lambda r: rank.get(r["urgency"], 0))["urgency"]

        if max_urgency == "CRITICAL" or breach_st in ("DELAYED_BREACH", "HISTORIC_BREACH"):
            decision_state = "CRITICAL_EXIT"
            has_critical = True
        elif max_urgency == "HIGH":
            decision_state = "HIGH_REDUCE"
        elif max_urgency in ("WARNING", "MEDIUM"):
            # Previously WATCH — sent to LLM for discretionary judgment.
            # Now resolved by code: _suggested_reduce_pct() already handles
            # APPROACHING_HARD_STOP, PROFIT_TARGET, PROFIT_LADDER_50.
            decision_state = "HIGH_REDUCE"
        else:
            decision_state = "HOLD"

        # Upgrade breach states + emit warnings
        if breach_st == "HISTORIC_BREACH":
            decision_state = "CRITICAL_EXIT"
            has_critical = True
            data_warnings.append(
                f"{ticker}: HISTORIC_BREACH — hard_stop "
                f"{pos_ctx.get('exit_levels', {}).get('hard_stop_price', '?')} is >20% "
                f"above current price {sig.get('close', '?')}. "
                f"Position should have been exited much earlier."
            )
        elif breach_st == "DELAYED_BREACH":
            decision_state = "CRITICAL_EXIT"
            has_critical = True
            data_warnings.append(
                f"{ticker}: DELAYED_BREACH — hard_stop "
                f"{pos_ctx.get('exit_levels', {}).get('hard_stop_price', '?')} "
                f"is above current price {sig.get('close', '?')}. "
                f"Forced liquidation — do not treat as a new stop trigger."
            )

        position_states[ticker] = decision_state

        # Pre-compute reduce % for HIGH_REDUCE — eliminates REDUCE table lookup in prompt
        if decision_state == "HIGH_REDUCE" and triggered:
            suggested_reduce_pct[ticker] = _suggested_reduce_pct(triggered, unrealized_pnl)

    # ── BEAR emergency stops (pre-compute for ALL positions with prices) ──────
    # When regime=BEAR the prompt rule requires current_price × 0.95 for every
    # position.  HOLD positions (AMD/GOOG/MCD/NFLX) are not in section 3b, so
    # the LLM had no price data to compute this.  Pre-computing here ensures the
    # rule fires even for positions that have no exit signals.
    bear_emergency_stops: dict[str, float] = {}
    if regime == "BEAR":
        for ticker, sig in signals.items():
            current_px = sig.get("close")
            if current_px and current_px > 0:
                bear_emergency_stops[ticker] = round(current_px * (1 - BEAR_STOP_PCT), 2)

    # ── Data consistency checks ──────────────────────────────────────────────
    if portfolio_val > 0:
        computed_value = 0.0
        for ticker, sig in signals.items():
            pos_ctx = sig.get("position", {})
            if pos_ctx:
                mv = pos_ctx.get("market_value_usd", 0)
                computed_value += mv
        if computed_value > 0:
            ratio = abs(computed_value - portfolio_val) / portfolio_val
            if ratio > 0.30:
                data_warnings.append(
                    f"Portfolio value mismatch: open_positions reports "
                    f"${portfolio_val:,.0f} but sum of market values = "
                    f"${computed_value:,.0f} (diff {ratio*100:.0f}%). "
                    f"Sizing and heat calculations may be unreliable."
                )

    # ── Derive account_state ─────────────────────────────────────────────────
    if has_critical:
        account_state = "FIRE"
    elif regime == "BEAR" or heat_pct >= DEFENSIVE_HEAT_THRESHOLD or not can_add:
        account_state = "DEFENSIVE"
    else:
        account_state = "NORMAL"

    # ── Lock new_trade at program layer ──────────────────────────────────────
    new_trade_locked = False
    lock_reason = ""
    if account_state == "FIRE":
        new_trade_locked = True
        lock_reason = "CRITICAL positions present — resolve fire first"
    elif regime == "BEAR":
        # Distinguish BEAR_SHALLOW (Commodities/Healthcare allowed) from BEAR_DEEP (fully locked).
        # BEAR_SHALLOW: both below 200MA but neither leg past -5% — defensive sectors permitted.
        # Without this check, new_trade_locked=True silently overrides the BEAR_SHALLOW rule
        # in the prompt, blocking valid defensive-sector signals the code already filtered for.
        _indices  = (regime_data or {}).get("indices", {})
        _spy_pct  = _indices.get("SPY", {}).get("pct_from_ma")
        _qqq_pct  = _indices.get("QQQ", {}).get("pct_from_ma")
        _is_shallow = (
            _spy_pct is not None and _qqq_pct is not None
            and min(_spy_pct, _qqq_pct) > -0.05
        )
        if _is_shallow:
            # BEAR_SHALLOW: signals are pre-filtered to Commodities/Healthcare in run.py.
            # Let LLM apply the BEAR_SHALLOW rules rather than locking at program layer.
            lock_reason = (
                f"BEAR_SHALLOW (min leg {min(_spy_pct, _qqq_pct):.1%} > -5%) — "
                "only Commodities/Healthcare signals permitted; other new trades blocked"
            )
            # new_trade_locked stays False — LLM enforces sector gate via BEAR_SHALLOW rules
        else:
            new_trade_locked = True
            lock_reason = "BEAR_DEEP regime — no new long positions (both legs ≤ -5%)"
    elif not can_add:
        new_trade_locked = True
        lock_reason = f"Portfolio heat {heat_pct*100:.1f}% >= cap — reduce risk first"

    return {
        "account_state":        account_state,
        "new_trade_locked":     new_trade_locked,
        "lock_reason":          lock_reason,
        "position_states":      position_states,
        "suggested_reduce_pct": suggested_reduce_pct,   # {ticker: int} — only HIGH_REDUCE tickers
        "bear_emergency_stops": bear_emergency_stops,   # {ticker: float} — only when BEAR
        "data_warnings":        data_warnings,
    }
