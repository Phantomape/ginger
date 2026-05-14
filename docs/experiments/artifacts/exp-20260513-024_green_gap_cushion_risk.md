# exp-20260513-024 Green Gap-Cushion Risk

Decision: `rejected_green_gap_cushion_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals whose accepted signal-day own candle is green and whose existing `gap_vulnerability_pct` is outside the tight-gap warning zone. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.05 | FAIL | +0.0632 | $+2,395.98 | late_strong, old_thin | mid_weak | 35 | +0.0033 |
| 1.10 | FAIL | +0.1246 | $+4,839.12 | late_strong, mid_weak, old_thin | - | 38 | +0.0070 |
| 1.15 | FAIL | +0.1484 | $+6,857.61 | late_strong, mid_weak, old_thin | - | 43 | +0.0106 |
| 1.20 | FAIL | +0.1330 | $+8,374.71 | late_strong, mid_weak, old_thin | - | 47 | +0.0142 |
| 1.25 | FAIL | +0.1397 | $+10,115.38 | late_strong, mid_weak, old_thin | - | 47 | +0.0178 |

Selected multiplier: `1.15`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.4123 | +0.1229 | $95,321.74 | $98,712.53 | $+3,390.79 | 0.8039 | 12 |
| mid_weak | 1.6747 | 1.6845 | +0.0098 | $62,490.66 | $64,786.90 | $+2,296.24 | 0.7925 | 11 |
| old_thin | 0.3867 | 0.4024 | +0.0157 | $28,855.61 | $30,026.19 | $+1,170.58 | 0.9167 | 20 |

Production impact: replay-only scout. Positive promotion would require shared `risk_engine` and `portfolio_engine` implementation plus attribution-key parity before live/default behavior changes.
