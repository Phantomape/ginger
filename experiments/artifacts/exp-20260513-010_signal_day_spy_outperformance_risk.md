# exp-20260513-010 Signal-Day SPY Outperformance Risk

Decision: `rejected_signal_day_spy_outperformance_risk`.

Single variable: cap-aware post-sizing risk scalar for existing core signals whose signal-day ticker open-to-close return exceeds SPY's same-day open-to-close return. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.020 | FAIL | +0.0203 | $+761.25 | late_strong, old_thin | mid_weak | 25 | +0.0013 |
| 1.030 | FAIL | +0.0360 | $+1,437.99 | late_strong, old_thin | mid_weak | 28 | +0.0021 |
| 1.050 | FAIL | +0.0632 | $+2,395.98 | late_strong, old_thin | mid_weak | 34 | +0.0033 |
| 1.075 | FAIL | +0.0916 | $+3,635.14 | late_strong, old_thin | mid_weak | 34 | +0.0049 |
| 1.100 | FAIL | +0.1246 | $+4,839.12 | late_strong, mid_weak, old_thin | - | 37 | +0.0070 |

Selected multiplier: `1.1`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.3971 | +0.1077 | $95,321.74 | $97,928.60 | $+2,606.86 | 0.8039 | 11 |
| mid_weak | 1.6747 | 1.6806 | +0.0059 | $62,490.66 | $63,897.83 | $+1,407.17 | 0.7925 | 9 |
| old_thin | 0.3867 | 0.3977 | +0.0110 | $28,855.61 | $29,680.70 | $+825.09 | 0.9167 | 17 |

Production impact: replay-only scout unless Gate 4 passes and the rule is promoted into shared feature/risk/sizing policy with parity coverage.
