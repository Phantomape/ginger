# exp-20260513-026 Green Sector-Cushion Risk

Decision: `rejected_green_sector_cushion_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals whose accepted signal-day own candle is green, whose signal-day sector proxy candle is positive, and whose existing `gap_vulnerability_pct` is outside the tight-gap warning zone. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | FAIL | +0.0083 | $+737.82 | late_strong, old_thin | mid_weak | 22 | +0.0013 |
| 1.050 | FAIL | +0.0156 | $+1,768.65 | late_strong, old_thin | mid_weak | 26 | +0.0033 |
| 1.075 | FAIL | +0.0207 | $+2,735.90 | late_strong, old_thin | mid_weak | 26 | +0.0049 |
| 1.100 | FAIL | +0.0331 | $+3,704.94 | late_strong, mid_weak, old_thin | - | 28 | +0.0070 |
| 1.150 | FAIL | +0.0357 | $+5,464.78 | late_strong, mid_weak, old_thin | - | 33 | +0.0106 |

Selected multiplier: `1.15`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.2989 | +0.0095 | $95,321.74 | $97,258.66 | $+1,936.92 | 0.8039 | 7 |
| mid_weak | 1.6747 | 1.6845 | +0.0098 | $62,490.66 | $64,794.73 | $+2,304.07 | 0.7925 | 9 |
| old_thin | 0.3867 | 0.4031 | +0.0164 | $28,855.61 | $30,079.40 | $+1,223.79 | 0.9167 | 17 |

Production impact: replay-only scout. Positive promotion would require shared `feature_layer`, `risk_engine`, and `portfolio_engine` implementation plus attribution-key parity before live/default behavior changes.
