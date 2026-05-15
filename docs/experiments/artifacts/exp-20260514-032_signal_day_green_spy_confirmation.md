# exp-20260514-032 Signal-Day Green SPY Confirmation

Decision: `rejected_signal_day_green_spy_confirmation`.

Single variable: the accepted signal-day green-candle 1.05x post-sizing top-up is removed when the ticker did not outperform SPY on that same signal day. Entries, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing rules stayed fixed.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.4853 | +0.0000 | $103,112.67 | $103,112.67 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 1.8580 | 1.8580 | +0.0000 | $69,070.09 | $69,070.09 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.4749 | 0.4749 | +0.0000 | $33,921.46 | $33,921.46 | $+0.00 | +0.0000 | 0.9167 | 1 |

## Runtime Field Audit

| Window | Signals | Green | Green Not SPY-Confirmed | Removed Topups Changed Shares | Missing Fields |
|---|---:|---:|---:|---:|---:|
| late_strong | 41 | 30 | 1 | 0 | 0 |
| mid_weak | 42 | 32 | 2 | 0 | 0 |
| old_thin | 55 | 48 | 2 | 1 | 0 |

Production impact: replay-only scout unless Gate 4 passes and the same condition is promoted into shared `portfolio_engine.py` with production/backtest parity tests.
