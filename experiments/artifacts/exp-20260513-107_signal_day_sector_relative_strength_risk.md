# exp-20260513-107 Signal-Day Sector-Relative Strength Risk

Decision: `rejected_signal_day_sector_relative_strength_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` stock signals whose signal-day open-to-close return beats the mapped sector proxy open-to-close return. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | FAIL | -0.0002 | $+816.66 | mid_weak, old_thin | late_strong | 18 | +0.0013 |
| 1.050 | FAIL | -0.0065 | $+1,734.05 | old_thin | late_strong, mid_weak | 24 | +0.0033 |
| 1.075 | FAIL | -0.0089 | $+2,613.36 | old_thin | late_strong | 24 | +0.0049 |
| 1.100 | FAIL | -0.0017 | $+3,696.36 | mid_weak, old_thin | late_strong | 29 | +0.0070 |
| 1.150 | FAIL | -0.0209 | $+5,202.84 | mid_weak, old_thin | late_strong | 33 | +0.0106 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3739 | -0.0029 | $99,695.99 | $100,086.95 | $+390.96 | 0.8039 | 6 |
| mid_weak | 1.6788 | 1.6789 | +0.0001 | $62,644.67 | $62,878.93 | $+234.26 | 0.7925 | 4 |
| old_thin | 0.4292 | 0.4318 | +0.0026 | $31,563.29 | $31,754.73 | $+191.44 | 0.9167 | 8 |

Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.
