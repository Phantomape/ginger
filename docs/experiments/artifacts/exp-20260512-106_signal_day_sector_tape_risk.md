# exp-20260512-106 Signal-Day Sector Tape Risk

Decision: `rejected_signal_day_sector_tape_risk`.

Single variable: 0.5x post-sizing risk multiplier when the signal-day sector proxy open-to-close return is <= -1%. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.2340 | +0.0000 | $94,086.91 | $94,086.91 | $+0.00 | 0.8039 | 3 |
| mid_weak | 1.6689 | 1.6697 | +0.0008 | $61,813.40 | $61,837.11 | $+23.71 | 0.7925 | 1 |
| old_thin | 0.3853 | 0.3594 | -0.0259 | $28,544.11 | $26,618.45 | $-1,925.66 | 0.9167 | 2 |

Production impact: replay-only scout. Positive promotion would require shared `feature_layer`, `risk_engine`, and `portfolio_engine` code plus attribution key parity before live/default behavior changes.
