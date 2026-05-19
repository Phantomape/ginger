# exp-20260516-004 Green Momentum Deceleration Risk

Decision: `rejected_green_momentum_deceleration_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals whose accepted signal-day own candle is green and whose 10-day momentum is below 20-day momentum, with both positive. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals |
|---:|:---:|---:|---:|---|---|---:|
| 1.01 | FAIL | +0.0074 | $+376.49 | late_strong | mid_weak, old_thin | 13 |
| 1.02 | FAIL | +0.0201 | $+1,000.61 | late_strong, mid_weak | old_thin | 14 |
| 1.05 | FAIL | +0.0493 | $+1,995.91 | late_strong, mid_weak | old_thin | 19 |
| 1.07 | FAIL | +0.0627 | $+3,323.90 | late_strong, mid_weak | old_thin | 19 |
| 1.10 | FAIL (DD +0.0071) | +0.0681 | $+4,252.59 | late_strong, mid_weak | old_thin | 21 |

Selected multiplier: `1.1`.
Selected max-drawdown drift: `+0.0071` vs guardrail `+0.0050`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1811 | +0.0747 | $116,319.10 | $119,382.32 | $+3,063.22 | 0.8039 | 6 |
| mid_weak | 2.0987 | 2.0994 | +0.0007 | $76,035.04 | $77,472.86 | $+1,437.82 | 0.7925 | 5 |
| old_thin | 0.5294 | 0.5221 | -0.0073 | $37,282.59 | $37,034.14 | $-248.45 | 0.8667 | 10 |

Production impact: replay-only scout. Positive promotion would require shared `risk_engine` and `portfolio_engine` code plus attribution-key parity before live/default behavior changes.
