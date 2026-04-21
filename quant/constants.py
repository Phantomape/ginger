"""Single source of truth for all numerical constants in the quant system.

CLAUDE3.md §三-3 — repeated local definitions have drifted across 6 files
in past iterations.  Any tuning sweep must now modify this file only.

Scope: parameters that callers share (risk sizing, stops/targets, execution).
Strictly local values (e.g. fill_model.SLIPPAGE_BPS_*) remain in their own
module because they belong to a single domain.
"""

# ── Risk sizing ─────────────────────────────────────────────────────────────
RISK_PER_TRADE_PCT      = 0.01       # 1% portfolio risk per new trade (BULL default)
RISK_PER_TRADE_NEUTRAL  = 0.0075     # 0.75% for NEUTRAL regime
RISK_PER_TRADE_BEAR     = 0.005      # 0.50% for BEAR_SHALLOW regime
MAX_POSITION_PCT        = 0.20       # Single position capped at 20% of portfolio
MAX_PORTFOLIO_HEAT      = 0.08       # Total portfolio heat ceiling (per inst_5.txt)
MAX_POSITIONS           = 5          # Concurrent open positions cap
MAX_PER_SECTOR          = 2          # Same-day sector concentration cap
ENABLED_STRATEGIES      = ("trend_long", "breakout_long")
# earnings_event_long stays implemented but disabled by default until P-ERN
# data quality is strong enough to re-validate it without partial-data drag.
BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH = -0.20
# breakout_long now rejects deep-recovery breakouts more than 20% below the
# 52-week high. This preserves true continuation setups while filtering the
# weak follow-through pattern seen in exp-20260419-007.
BREAKOUT_RANK_BY_52W_HIGH = True
# Allocation ranking now re-orders only the breakout_long subsequence by
# pct_from_52w_high so closer-to-high continuation setups get earlier slot access.

# ── Stops & targets ─────────────────────────────────────────────────────────
HARD_STOP_PCT           = 0.12       # -12% hard stop from avg_cost
TRAILING_STOP_PCT       = 0.08       # -8% trailing stop from position high-water mark
PROFIT_TARGET_PCT       = 0.20       # +20% profit target from entry
TIME_STOP_DAYS          = 45         # Exit review after 45 trading days
ATR_STOP_MULT           = 1.5        # Stop = entry - 1.5 * ATR
ATR_TARGET_MULT         = 3.5        # Target = entry + 3.5 * ATR
ATR_PERIOD              = 14         # Standard ATR lookback
REGIME_AWARE_EXIT       = True       # Adopt entry-day regime-aware target width by default

# ── Execution ───────────────────────────────────────────────────────────────
ROUND_TRIP_COST_PCT     = 0.0035     # Slippage + commission round trip (matches performance_engine)
EXEC_LAG_PCT            = 0.005      # +0.5% assumed next-day open gap (conservative)
CANCEL_GAP_PCT          = 0.015      # Cancel entry if next-day Open > signal entry * (1 + CANCEL_GAP_PCT)
