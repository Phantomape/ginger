# exp-20260513-031 Signal-Day Range-Compression Risk

Decision: `rejected_signal_day_range_compression_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` stock signals whose `daily_range_vs_atr` is in the same-day bottom quartile of feature-complete non-ETF/non-commodity stocks. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.05 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 1.10 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 1.15 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 1.20 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |

Selected multiplier: `1.05`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3663 | 4.3663 | +0.0000 | $98,115.26 | $98,115.26 | $+0.00 | 0.8039 | 0 |
| mid_weak | 1.6788 | 1.6788 | +0.0000 | $62,644.67 | $62,644.67 | $+0.00 | 0.7925 | 0 |
| old_thin | 0.4151 | 0.4151 | +0.0000 | $30,524.01 | $30,524.01 | $+0.00 | 0.9167 | 0 |

Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.
