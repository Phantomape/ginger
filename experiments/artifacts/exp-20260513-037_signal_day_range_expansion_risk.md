# exp-20260513-037 Signal-Day Range-Expansion Risk

Decision: `rejected_signal_day_range_expansion_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` stock signals whose `daily_range_vs_atr` is in the same-day top quartile of feature-complete non-ETF/non-commodity stocks. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.05 | FAIL | -0.0083 | $+1,606.95 | old_thin | late_strong, mid_weak | 32 | +0.0033 |
| 1.10 | FAIL | -0.0227 | $+3,279.32 | old_thin | late_strong, mid_weak | 36 | +0.0070 |
| 1.15 | FAIL | -0.0439 | $+4,651.16 | old_thin | late_strong, mid_weak | 39 | +0.0106 |
| 1.20 | FAIL | -0.0628 | $+5,618.94 | - | late_strong, mid_weak, old_thin | 42 | +0.0142 |

Selected multiplier: `1.05`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3670 | -0.0098 | $99,695.99 | $100,387.81 | $+691.82 | 0.8039 | 8 |
| mid_weak | 1.6788 | 1.6761 | -0.0027 | $62,644.67 | $63,250.36 | $+605.69 | 0.7925 | 10 |
| old_thin | 0.4292 | 0.4334 | +0.0042 | $31,563.29 | $31,872.73 | $+309.44 | 0.9167 | 14 |

Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.
