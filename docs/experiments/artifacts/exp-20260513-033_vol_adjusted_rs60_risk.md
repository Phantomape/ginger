# exp-20260513-033 Vol-Adjusted RS60 Risk

Decision: `rejected_vol_adjusted_rs60_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` stock signals whose same-day `momentum_60d_pct / (atr / close)` score is in the top quintile of feature-complete non-ETF/non-commodity stocks. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.05 | FAIL | -0.0093 | $+976.43 | old_thin | late_strong, mid_weak | 13 | +0.0013 |
| 1.10 | FAIL | -0.0092 | $+2,219.83 | old_thin | late_strong, mid_weak | 18 | +0.0034 |
| 1.15 | FAIL | -0.0194 | $+3,162.80 | old_thin | late_strong, mid_weak | 20 | +0.0051 |
| 1.20 | FAIL | -0.0233 | $+4,464.33 | old_thin | late_strong, mid_weak | 22 | +0.0071 |

Selected multiplier: `1.1`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3663 | 4.3441 | -0.0222 | $98,115.26 | $99,179.84 | $+1,064.58 | 0.8039 | 3 |
| mid_weak | 1.6788 | 1.6733 | -0.0055 | $62,644.67 | $62,671.15 | $+26.48 | 0.7925 | 7 |
| old_thin | 0.4151 | 0.4336 | +0.0185 | $30,524.01 | $31,652.78 | $+1,128.77 | 0.9167 | 8 |

Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.
