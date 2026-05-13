# exp-20260513-023 Green Momentum Deceleration Risk

Decision: `rejected_green_momentum_deceleration_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals whose accepted signal-day own candle is green and whose 10-day momentum is below 20-day momentum, with both positive. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals |
|---:|:---:|---:|---:|---|---|---:|
| 1.05 | FAIL | +0.0404 | $+2,110.50 | late_strong, old_thin | mid_weak | 23 |
| 1.10 | FAIL (DD +0.0070) | +0.0635 | $+4,158.43 | late_strong, mid_weak, old_thin | - | 25 |
| 1.15 | FAIL | +0.0553 | $+5,554.73 | late_strong, old_thin | mid_weak | 27 |
| 1.20 | FAIL | +0.0546 | $+7,217.69 | late_strong, old_thin | mid_weak | 29 |
| 1.25 | FAIL | +0.0383 | $+8,766.29 | late_strong, old_thin | mid_weak | 29 |

Selected multiplier: `1.1`.
Selected max-drawdown drift: `+0.0070` vs guardrail `+0.0050`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.3333 | +0.0439 | $95,321.74 | $97,163.23 | $+1,841.49 | 0.8039 | 6 |
| mid_weak | 1.6747 | 1.6779 | +0.0032 | $62,490.66 | $63,799.66 | $+1,309.00 | 0.7925 | 6 |
| old_thin | 0.3867 | 0.4031 | +0.0164 | $28,855.61 | $29,863.55 | $+1,007.94 | 0.9167 | 13 |

Production impact: replay-only scout. Positive promotion would require shared `risk_engine` and `portfolio_engine` code plus attribution-key parity before live/default behavior changes.
