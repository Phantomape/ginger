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
LOW_TQS_RISK_THRESHOLD  = 0.85       # De-risk lower-quality setups that still pass entry gates
LOW_TQS_RISK_MULTIPLIER = 0.25       # Keep only 25% of the normal risk budget below the TQS threshold
LOW_TQS_HAIRCUT_EXEMPT_SECTORS = ("Commodities",)
LOW_TQS_BREAKOUT_NON_EXEMPT_RISK_MULTIPLIER = 0.0
TREND_INDUSTRIALS_RISK_MULTIPLIER = 0.0
TREND_FINANCIALS_RISK_MULTIPLIER = 1.5
TREND_TECH_GAP_VULN_MIN = 0.04
TREND_TECH_GAP_VULN_MAX = 0.06
TREND_TECH_GAP_RISK_MULTIPLIER = 0.25
TREND_TECH_TIGHT_GAP_VULN_MIN = 0.02
TREND_TECH_TIGHT_GAP_VULN_MAX = 0.03
TREND_TECH_TIGHT_GAP_RISK_MULTIPLIER = 0.0
TREND_TECH_NEAR_HIGH_MAX_PULLBACK = -0.03
TREND_TECH_NEAR_HIGH_RISK_MULTIPLIER = 0.25
BREAKOUT_INDUSTRIALS_GAP_VULN_MIN = 0.03
BREAKOUT_INDUSTRIALS_GAP_VULN_MAX = 0.04
BREAKOUT_INDUSTRIALS_GAP_RISK_MULTIPLIER = 0.0
BREAKOUT_COMMS_NEAR_HIGH_MAX_PULLBACK = -0.03
BREAKOUT_COMMS_NEAR_HIGH_RISK_MULTIPLIER = 0.25
BREAKOUT_COMMS_GAP_VULN_MIN = 0.03
BREAKOUT_COMMS_GAP_VULN_MAX = 0.04
BREAKOUT_COMMS_GAP_RISK_MULTIPLIER = 0.25
BREAKOUT_FINANCIALS_DTE_MIN = 8
BREAKOUT_FINANCIALS_DTE_MAX = 14
BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER = 0.25
BREAKOUT_TECH_DTE_MIN = 26
BREAKOUT_TECH_DTE_MAX = 40
BREAKOUT_TECH_DTE_RISK_MULTIPLIER = 0.0
BREAKOUT_HEALTHCARE_DTE_MIN = 20
BREAKOUT_HEALTHCARE_DTE_MAX = 65
BREAKOUT_HEALTHCARE_DTE_RISK_MULTIPLIER = 0.25
TREND_TECH_DTE_MIN = 44
TREND_TECH_DTE_MAX = 64
TREND_TECH_DTE_RISK_MULTIPLIER = 0.25
TREND_HEALTHCARE_DTE_MIN = 6
TREND_HEALTHCARE_DTE_MAX = 12
TREND_HEALTHCARE_DTE_RISK_MULTIPLIER = 0.0
TREND_CONSUMER_NEAR_HIGH_DTE_MIN = 30
TREND_CONSUMER_NEAR_HIGH_DTE_MAX = 65
TREND_CONSUMER_NEAR_HIGH_MAX_PULLBACK = -0.01
TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER = 0.0
TREND_COMMODITIES_NEAR_HIGH_MAX_PULLBACK = -0.03
TREND_COMMODITIES_NEAR_HIGH_RISK_MULTIPLIER = 1.5
RISK_ON_UNMODIFIED_RISK_MULTIPLIER = 1.25
# Low-TQS breakouts were net-negative in Consumer Discretionary/Financials/Technology
# but net-positive in Commodities across the validated windows. Keep the accepted
# haircut everywhere else and exempt only the defensive commodity breakout pocket.
# The remaining non-commodity low-TQS breakout cohort stayed negative across the
# validated windows, so fully zero its marginal risk instead of merely shrinking it.
# Current repo-state cohort audit shows `trend_long` Industrials remained a drag
# across the primary, bull, and weak comparison windows. Zeroing only that
# strategy+sector bucket is the next minimal allocation experiment.
# The next surviving allocation leak is narrower: `trend_long` Technology names
# with a 4-6% stop gap repeatedly dragged in the bull and weak windows, while the
# primary window had no qualifying cohort. De-risk only that moderate-gap pocket.
# This is a sizing rule, not an entry ban: keep the cohort tradable, but at 25%
# of normal risk because 0x turned out worse than 0.25x in follow-up testing.
# A different residual leak remained below that band: `trend_long` Technology
# names with only a 2-3% stop gap were net-negative across the fixed late/mid/old
# windows, while the current late-strong window had zero qualifying trades. Zero
# only that tighter-gap pocket; it improves the weaker tapes without touching the
# dominant tape.
# The remaining residual trend-Tech leak is a different entry shape, not another
# nearby gap-band tweak: names entering within 3% of the 52-week high repeatedly
# dragged after the accepted stack, while deeper-pullback Technology trends still
# carried the surviving winners. Keep that near-high pocket tradable, but only at
# 25% of normal risk.
# The remaining breakout leak is narrower still: `breakout_long` Industrials with
# a 3-4% stop gap repeatedly lost in the weak windows, while the current late-strong
# winner sat just outside the band (>4%). Zero only that risk-shape pocket.
# The next surviving breakout leak is a different conditioning source, not another
# sector+gap retry: near-high Communication Services breakouts repeatedly lost in
# the weaker tapes while the dominant late-strong tape had zero qualifying names.
# Keep the pocket tradable, but only at 25% of normal risk so the branch stays
# aligned with the stronger breakout sleeve rather than turning into another full ban.
# After that accepted near-high rule, a narrower Communication Services
# risk-shape leak still remained: 3-4% gap-vulnerability breakouts kept
# dragging in the weaker tapes, while the dominant strong tape still had no
# qualifying names. Keep that pocket live, but only at 25% of whatever risk
# budget survives the earlier accepted stack.
# The next residual breakout leak is not another price-shape retry. Financials
# breakouts entering 8-14 calendar days before earnings lost in both the strong
# and weak validation tapes, while the old winner sat far from earnings. Keep
# that pocket live, but only at 25% of normal risk so the sleeve does not carry
# event-proximity exposure at full size.
# A later residual breakout leak appeared in Technology names 26-40 trading days
# before earnings. It is not the rejected Technology trend DTE+gap family: this
# pocket is breakout-only, event-proximity-only, absent from the dominant strong
# tape, and repeatedly weak in the mid/old tapes. Zero only this narrow sleeve.
# A separate Healthcare breakout event-distance leak survived after the rejected
# deep-pullback screen. De-risk only the 20-65 DTE sleeve at 25% risk; widening
# to 20-70 DTE cut the dominant late-window LLY winner and failed stability.
# A separate residual Technology trend leak survived the rejected 59-69 DTE+gap
# probe: the repeat drag clustered at 44-64 DTE after existing gap/near-high
# haircuts, while the 69 DTE APP winner that broke the old probe is excluded.
# Keep the sleeve live at 25% risk rather than banning it; 0x hurt old_thin.
# A separate residual trend leak remained in Healthcare names 6-12 trading days
# before earnings. The existing dte<=3 hard entry block avoids immediate gap
# exposure, but this wider pre-event pocket still lost in the strong and weak
# tapes while the mid window had no qualifier. Zero only this narrow sleeve.
# Another residual trend leak appeared in Consumer Discretionary names entering
# within 1% of the 52-week high while still 30-65 days from earnings. The fixed
# snapshot trio showed this MCD-like pocket losing in late/old windows and absent
# in mid. Zero only this replayable cross-state sleeve; do not generalize it into
# broad Consumer Discretionary or near-high trend cuts.
# Positive allocation sleeve: Commodities trend entries within 3% of the
# 52-week high repeatedly carried the system's convex winners. A 1.5x risk
# budget improved late_strong and mid_weak while leaving old_thin unchanged;
# wider/deeper commodity boosts were rejected because they increased old_thin
# exposure to the weaker SLV shape.
# Candidate allocation sleeve: accepted-stack cohort audit shows trend
# Financials were positive in mid_weak and old_thin while absent in late_strong.
# Keep this as sizing only; do not turn it into sector priority or new entry.
# Broad allocation sleeve: after the accepted de-risk/boost stack, plain
# risk-on signals with no other sizing modifier remained positive across all
# fixed windows. Give only that unmodified risk-on inventory a small lift; do
# not stack this on existing 1.5x sector boosts or 0.25x/0x haircuts.
MAX_POSITION_PCT        = 0.40       # Initial position cap; exp-20260428-025
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

# ── Follow-through add-ons / scarce-slot entry routing ──────────────────────
ADDON_ENABLED = True
ADDON_CHECKPOINT_DAYS = 2
ADDON_MIN_UNREALIZED_PCT = 0.02
ADDON_MIN_RS_VS_SPY = 0.0
ADDON_FRACTION_OF_ORIGINAL_SHARES = 0.50
ADDON_MAX_POSITION_PCT = 0.35
ADDON_REQUIRE_CHECKPOINT_CAP_ROOM = False
ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH = False
SECOND_ADDON_ENABLED = False
SECOND_ADDON_CHECKPOINT_DAYS = 5
SECOND_ADDON_MIN_UNREALIZED_PCT = 0.05
SECOND_ADDON_MIN_RS_VS_SPY = 0.0
SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES = 0.15
SECOND_ADDON_MAX_POSITION_PCT = 0.45
DEFER_BREAKOUT_WHEN_SLOTS_LTE = 1
DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA = None

# ── Stops & targets ─────────────────────────────────────────────────────────
HARD_STOP_PCT           = 0.12       # -12% hard stop from avg_cost
TRAILING_STOP_PCT       = 0.08       # -8% trailing stop from position high-water mark
PROFIT_TARGET_PCT       = 0.20       # +20% profit target from entry
TIME_STOP_DAYS          = 45         # Exit review after 45 trading days
ATR_STOP_MULT           = 1.5        # Stop = entry - 1.5 * ATR
ATR_TARGET_MULT         = 3.5        # Target = entry + 3.5 * ATR
TREND_TECH_TARGET_ATR_MULT = 6.0     # Let Technology trend winners run; exp-20260425-027
TREND_COMMODITIES_TARGET_ATR_MULT = 7.0  # Preserve commodity trend convexity; exp-20260425-031
ATR_PERIOD              = 14         # Standard ATR lookback
REGIME_AWARE_EXIT       = True       # Adopt entry-day regime-aware target width by default

# ── Execution ───────────────────────────────────────────────────────────────
ROUND_TRIP_COST_PCT     = 0.0035     # Slippage + commission round trip (matches performance_engine)
EXEC_LAG_PCT            = 0.005      # +0.5% assumed next-day open gap (conservative)
CANCEL_GAP_PCT          = 0.015      # Cancel entry if next-day Open > signal entry * (1 + CANCEL_GAP_PCT)
ADVERSE_GAP_CANCEL_PCT  = 0.02       # Cancel entry if next-day Open < signal entry * (1 - pct); exp-20260428-017
