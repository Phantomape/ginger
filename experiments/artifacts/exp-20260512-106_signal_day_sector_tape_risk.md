# exp-20260512-106 Signal-Day Sector Tape Risk

Decision: `accepted_for_shared_policy_implementation`.

Single variable: 0.5x post-sizing risk multiplier when the signal-day sector proxy open-to-close return is <= -1%. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.5701 | +0.0848 | $103,112.67 | $104,582.95 | $+1,470.28 | 0.8039 | 2 |
| mid_weak | 1.8580 | 1.8824 | +0.0244 | $69,070.09 | $69,718.99 | $+648.90 | 0.7925 | 2 |
| old_thin | 0.4749 | 0.4749 | +0.0000 | $33,921.46 | $33,921.46 | $+0.00 | 0.9167 | 1 |

Production impact: replay-only scout. Positive promotion would require shared `feature_layer`, `risk_engine`, and `portfolio_engine` code plus attribution key parity before live/default behavior changes.
