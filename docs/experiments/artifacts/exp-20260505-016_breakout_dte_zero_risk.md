# exp-20260505-016 breakout DTE zero-risk replay

## Decision

- decision: rejected
- gate4_passed: False
- aggregate EV delta: -0.2938 (-0.056735)
- aggregate PnL delta: -5548.11 (-0.035057)
- windows improved/regressed: 0 / 2

## Why This Was Tested

Financials and Healthcare breakout DTE trades were already reduced to 0.25x risk and appeared consistently negative in the current three-window attribution. This replay tests whether the residual event-proximity sleeve should be zero-risk.

## Window Deltas

- late_strong: EV -0.2677 | PnL -4971.95 | SharpeD -0.07 | trades 2
- mid_weak: EV -0.0261 | PnL -576.16 | SharpeD -0.02 | trades -1
- old_thin: EV 0.0 | PnL 0.0 | SharpeD 0.0 | trades 0

## Production Impact

Replay-only. If accepted, promotion would require changing the shared constants used by portfolio_engine so both backtester and run.py consume the same sizing policy.
