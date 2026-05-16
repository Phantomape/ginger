# exp-20260515-045 Reversal-Green Confirmation Risk

Decision: `rejected_reversal_green_confirmation_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` non-ETF/non-commodity stock signals whose prior daily candle was red and whose signal-day candle is green. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0125 | FAIL | +0.0039 | $+294.61 | late_strong | mid_weak, old_thin | 6 | +0.0008 |
| 1.0250 | FAIL | +0.0087 | $+739.63 | late_strong, mid_weak | old_thin | 7 | +0.0020 |
| 1.0500 | FAIL | -0.0067 | $+1,418.75 | late_strong | mid_weak, old_thin | 12 | +0.0036 |
| 1.0750 | FAIL | +0.0049 | $+2,256.50 | late_strong | mid_weak, old_thin | 12 | +0.0056 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1132 | +0.0068 | $116,319.10 | $116,741.71 | $+422.61 | +0.0010 | 0.8039 | 2 |
| mid_weak | 2.0987 | 2.1016 | +0.0029 | $76,035.04 | $76,421.93 | $+386.89 | +0.0020 | 0.7925 | 1 |
| old_thin | 0.5294 | 0.5284 | -0.0010 | $37,282.59 | $37,212.72 | $-69.87 | +0.0008 | 0.8667 | 4 |

Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.
