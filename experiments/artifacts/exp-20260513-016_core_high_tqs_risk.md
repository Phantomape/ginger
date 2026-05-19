# exp-20260513-016 Core Near-Perfect TQS Risk

Decision: `rejected_core_high_tqs_risk`.

Single variable: cap-aware post-sizing risk top-up for core `trend_long` and `breakout_long` signals with `trade_quality_score >= 0.95`. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.05 | FAIL | +0.0166 | $+983.53 | late_strong | mid_weak, old_thin | 27 | +0.0033 |
| 1.10 | FAIL | +0.0351 | $+2,169.39 | late_strong, mid_weak | old_thin | 28 | +0.0070 |
| 1.15 | FAIL | +0.0361 | $+3,105.46 | late_strong, mid_weak | old_thin | 31 | +0.0106 |
| 1.20 | FAIL | +0.0376 | $+4,016.23 | late_strong, mid_weak | old_thin | 35 | +0.0142 |

Selected multiplier: `1.2`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.3233 | +0.0339 | $95,321.74 | $95,860.78 | $+539.04 | 0.8039 | 7 |
| mid_weak | 1.6747 | 1.6785 | +0.0038 | $62,490.66 | $65,314.84 | $+2,824.18 | 0.7925 | 13 |
| old_thin | 0.3867 | 0.3866 | -0.0001 | $28,855.61 | $29,508.62 | $+653.01 | 0.9167 | 15 |

Production impact: replay-only scout. Positive promotion requires shared `portfolio_engine` attribution and production parity coverage before live/default behavior changes.
