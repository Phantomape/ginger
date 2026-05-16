# exp-20260515-032 Confirmed Sector-Thrust Risk

Decision: `rejected_confirmed_sector_thrust_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` non-ETF/non-commodity stock signals that satisfy both `core_confirmed_quality_state=true` and same-day top-quartile ticker-minus-sector-proxy thrust. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0125 | FAIL | -0.0045 | $+101.88 | - | mid_weak, old_thin | 6 | +0.0008 |
| 1.0250 | FAIL | +0.0019 | $+309.65 | mid_weak | old_thin | 8 | +0.0020 |
| 1.0500 | FAIL | -0.0109 | $+500.93 | - | mid_weak, old_thin | 12 | +0.0036 |
| 1.0750 | FAIL | -0.0076 | $+845.44 | - | mid_weak, old_thin | 12 | +0.0056 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1064 | +0.0000 | $116,319.10 | $116,319.10 | $+0.00 | 0.8039 | 1 |
| mid_weak | 2.0987 | 2.1016 | +0.0029 | $76,035.04 | $76,421.93 | $+386.89 | 0.7925 | 3 |
| old_thin | 0.5294 | 0.5284 | -0.0010 | $37,282.59 | $37,205.35 | $-77.24 | 0.8667 | 4 |

Production impact: replay-only scout. A positive promotion would require shared feature/risk/sizing implementation, attribution keys, and parity tests before production behavior changes.
