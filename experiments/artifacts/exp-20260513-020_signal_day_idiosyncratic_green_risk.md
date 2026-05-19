# exp-20260513-020 Signal-Day Idiosyncratic Green Risk

Decision: `rejected_signal_day_idiosyncratic_green_risk`.

Single variable: cap-aware post-sizing risk scalar for core `trend_long`/`breakout_long` signals whose own signal-day candle is green while SPY's same-day candle is red. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.050 | FAIL | +0.0505 | $+687.65 | late_strong | old_thin | 10 | +0.0000 |
| 1.075 | FAIL | +0.0726 | $+951.99 | late_strong | old_thin | 10 | +0.0000 |
| 1.100 | FAIL | +0.0934 | $+1,197.68 | late_strong | mid_weak, old_thin | 11 | +0.0000 |
| 1.150 | FAIL | +0.1012 | $+1,327.35 | late_strong | mid_weak, old_thin | 12 | +0.0000 |
| 1.200 | FAIL | +0.1009 | $+1,309.61 | late_strong | mid_weak, old_thin | 13 | +0.0000 |

Selected multiplier: `1.15`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.3920 | +0.1026 | $95,321.74 | $96,739.00 | $+1,417.26 | 0.8039 | 5 |
| mid_weak | 1.6747 | 1.6745 | -0.0002 | $62,490.66 | $62,482.83 | $-7.83 | 0.7925 | 2 |
| old_thin | 0.3867 | 0.3855 | -0.0012 | $28,855.61 | $28,773.53 | $-82.08 | 0.9167 | 5 |

Production impact: replay-only scout unless Gate 4 passes and the rule is promoted into shared feature/risk/sizing policy with parity coverage.
