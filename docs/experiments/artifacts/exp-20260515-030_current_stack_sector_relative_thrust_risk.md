# exp-20260515-030 Current-Stack Sector-Relative Thrust Risk

Decision: `rejected_current_stack_sector_relative_thrust_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` non-ETF/non-commodity stock signals whose signal-day ticker-minus-sector-proxy return is in the same-day top quartile. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | FAIL | +0.0104 | $+776.33 | late_strong, mid_weak | old_thin | 16 | +0.0020 |
| 1.050 | FAIL | -0.0035 | $+1,518.09 | late_strong | mid_weak, old_thin | 22 | +0.0036 |
| 1.075 | FAIL | +0.0103 | $+2,408.15 | late_strong, mid_weak | old_thin | 22 | +0.0056 |
| 1.100 | FAIL | +0.0062 | $+3,215.21 | late_strong, mid_weak | old_thin | 25 | +0.0072 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1141 | +0.0077 | $116,319.10 | $116,759.41 | $+440.31 | 0.8039 | 6 |
| mid_weak | 2.0987 | 2.1024 | +0.0037 | $76,035.04 | $76,448.30 | $+413.26 | 0.7925 | 4 |
| old_thin | 0.5294 | 0.5284 | -0.0010 | $37,282.59 | $37,205.35 | $-77.24 | 0.8667 | 6 |

Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.
