# exp-20260515-042 Signal-Day Close-Location Risk

Decision: `rejected_signal_day_close_location_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` non-ETF/non-commodity stock signals whose signal-day close location is in the same-day top quartile. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0125 | FAIL | +0.0043 | $+303.46 | late_strong | mid_weak, old_thin | 11 | +0.0008 |
| 1.0250 | FAIL | +0.0104 | $+776.33 | late_strong, mid_weak | old_thin | 13 | +0.0020 |
| 1.0500 | FAIL | +0.0044 | $+1,520.92 | late_strong, mid_weak | old_thin | 15 | +0.0036 |
| 1.0750 | FAIL | +0.0110 | $+2,415.31 | late_strong, mid_weak | old_thin | 15 | +0.0056 |

Selected multiplier: `1.075`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1204 | +0.0140 | $116,319.10 | $117,706.32 | $+1,387.22 | +0.0030 | 0.8039 | 6 |
| mid_weak | 2.0987 | 2.1028 | +0.0041 | $76,035.04 | $77,307.71 | $+1,272.67 | +0.0056 | 0.7925 | 5 |
| old_thin | 0.5294 | 0.5223 | -0.0071 | $37,282.59 | $37,038.01 | $-244.58 | +0.0023 | 0.8667 | 4 |

Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.
