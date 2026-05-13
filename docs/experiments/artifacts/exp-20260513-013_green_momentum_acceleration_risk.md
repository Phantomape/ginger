# exp-20260513-013 Green Momentum Acceleration Risk

Decision: `rejected_green_momentum_acceleration_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals whose accepted signal-day own candle is green and whose 10-day momentum is at least 20-day momentum, with both positive. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals |
|---:|:---:|---:|---:|---|---|---:|
| 1.05 | FAIL | +0.0274 | $+350.49 | late_strong, mid_weak | old_thin | 12 |
| 1.10 | FAIL | +0.0533 | $+677.67 | late_strong, mid_weak | old_thin | 13 |
| 1.15 | FAIL | +0.0818 | $+1,236.60 | late_strong, mid_weak | old_thin | 16 |
| 1.20 | FAIL | +0.0817 | $+1,204.70 | late_strong, mid_weak | old_thin | 18 |
| 1.25 | FAIL | +0.0869 | $+1,344.23 | late_strong, mid_weak | old_thin | 18 |

Selected multiplier: `1.25`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.3660 | +0.0766 | $95,321.74 | $96,378.32 | $+1,056.58 | 0.8039 | 5 |
| mid_weak | 1.6747 | 1.6930 | +0.0183 | $62,490.66 | $63,166.10 | $+675.44 | 0.7925 | 4 |
| old_thin | 0.3867 | 0.3787 | -0.0080 | $28,855.61 | $28,467.82 | $-387.79 | 0.9167 | 9 |

Production impact: replay-only scout. Positive promotion would require shared `risk_engine` and `portfolio_engine` code plus attribution-key parity before live/default behavior changes.
