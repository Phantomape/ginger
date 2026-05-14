# exp-20260514-003 RS60 Bottom-Quintile Haircut

Decision: `rejected_rs60_bottom_quintile_haircut`.

Single variable: post-sizing risk haircut for `trend_long` and `breakout_long` stock signals whose same-day 60-trading-day return is in the bottom quintile of the feature-complete non-ETF/non-commodity stock universe. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.50 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 0.75 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 0.90 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |

Selected multiplier: `0.5`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3768 | +0.0000 | $99,695.99 | $99,695.99 | $+0.00 | 0.8039 | 0 |
| mid_weak | 1.6788 | 1.6788 | +0.0000 | $62,644.67 | $62,644.67 | $+0.00 | 0.7925 | 0 |
| old_thin | 0.4292 | 0.4292 | +0.0000 | $31,563.29 | $31,563.29 | $+0.00 | 0.9167 | 0 |

Production impact: replay-only scout. A positive result must be promoted through shared `risk_engine.py` / `portfolio_engine.py` code and attribution-key parity before production-visible behavior changes.
