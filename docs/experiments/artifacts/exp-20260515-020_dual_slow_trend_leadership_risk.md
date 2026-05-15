# exp-20260515-020 Dual Slow-Trend Leadership Risk

Decision: `rejected_dual_slow_trend_leadership_risk`.

Single variable: cap-aware post-sizing risk top-up for already-qualified `trend_long` and `breakout_long` non-ETF/non-commodity signals where both `rs60_top_quintile_state=true` and `price_vs_200ma_extension_state=true`. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0125 | FAIL | -0.0027 | $+325.63 | mid_weak, old_thin | late_strong | 11 | +0.0003 |
| 1.0250 | FAIL | +0.0096 | $+894.97 | mid_weak, old_thin | late_strong | 12 | +0.0010 |
| 1.0500 | FAIL | +0.0211 | $+1,874.80 | mid_weak, old_thin | late_strong | 17 | +0.0019 |
| 1.0750 | FAIL | +0.0290 | $+2,915.78 | mid_weak, old_thin | late_strong | 17 | +0.0029 |
| 1.1000 | FAIL | +0.0574 | $+4,012.58 | mid_weak, old_thin | late_strong | 21 | +0.0039 |

Selected multiplier: `1.1`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0334 | 5.0061 | -0.0273 | $115,183.05 | $116,422.92 | $+1,239.87 | 0.8039 | 3 |
| mid_weak | 2.0103 | 2.0722 | +0.0619 | $73,104.97 | $74,540.03 | $+1,435.06 | 0.7925 | 10 |
| old_thin | 0.5099 | 0.5327 | +0.0228 | $35,657.24 | $36,994.89 | $+1,337.65 | 0.9167 | 8 |

Production impact: replay-only scout. Positive promotion requires a shared portfolio sizing branch and attribution-key parity before production-visible behavior changes.
