# exp-20260512-111 Core Momentum Acceleration Risk

Decision: `rejected_core_momentum_acceleration_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals whose 10-day momentum is at least 20-day momentum, with both positive. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals |
|---:|:---:|---:|---:|---|---|---:|
| 1.05 | FAIL | +0.0209 | $+185.52 | late_strong, mid_weak | old_thin | 15 |
| 1.10 | FAIL | +0.0388 | $+344.10 | late_strong, mid_weak | old_thin | 16 |
| 1.15 | FAIL | +0.0667 | $+774.83 | late_strong, mid_weak | old_thin | 19 |
| 1.20 | FAIL | +0.0884 | $+987.89 | late_strong, mid_weak | old_thin | 21 |

Selected multiplier: `1.2`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.3352 | +0.1012 | $94,086.91 | $95,486.54 | $+1,399.63 | 0.8039 | 5 |
| mid_weak | 1.6689 | 1.6818 | +0.0129 | $61,813.40 | $62,290.17 | $+476.77 | 0.7925 | 5 |
| old_thin | 0.3853 | 0.3596 | -0.0257 | $28,544.11 | $27,655.60 | $-888.51 | 0.9167 | 11 |

Production impact: replay-only scout. Positive promotion would require shared `risk_engine` and `portfolio_engine` code plus attribution-key parity before live/default behavior changes.
