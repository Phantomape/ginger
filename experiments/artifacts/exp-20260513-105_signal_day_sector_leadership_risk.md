# exp-20260513-105 Signal-Day Sector-Leadership Risk

Decision: `rejected_signal_day_sector_leadership_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` stock signals whose mapped sector proxy is the strongest positive signal-day proxy among QQQ/SPY/GLD. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | FAIL | -0.0042 | $+464.06 | mid_weak, old_thin | late_strong | 15 | +0.0013 |
| 1.050 | FAIL | -0.0080 | $+972.24 | mid_weak, old_thin | late_strong | 18 | +0.0027 |
| 1.075 | FAIL | -0.0134 | $+1,476.76 | mid_weak, old_thin | late_strong | 18 | +0.0043 |
| 1.100 | FAIL | -0.0279 | $+1,964.48 | old_thin | late_strong, mid_weak | 19 | +0.0060 |
| 1.150 | FAIL | -0.0389 | $+2,828.70 | old_thin | late_strong, mid_weak | 19 | +0.0093 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3700 | -0.0068 | $99,695.99 | $100,003.07 | $+307.08 | 0.8039 | 4 |
| mid_weak | 1.6788 | 1.6796 | +0.0008 | $62,644.67 | $62,671.04 | $+26.37 | 0.7925 | 3 |
| old_thin | 0.4292 | 0.4310 | +0.0018 | $31,563.29 | $31,693.90 | $+130.61 | 0.9167 | 8 |

Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.
