# exp-20260513-011 Signal-Day SPY Excess-Margin Risk

Decision: `rejected_signal_day_spy_excess_margin_risk`.

Single variable: minimum signal-day ticker-minus-SPY open-to-close excess return required for a fixed 1.10x cap-aware top-up.

## Sweep

| Excess margin | Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|---:|:---:|---:|---:|---|---|---:|---:|
| 0.000% | 1.10 | FAIL | +0.1246 | $+4,839.12 | late_strong, mid_weak, old_thin | - | 37 | +0.0070 |
| 1.000% | 1.10 | FAIL | +0.1237 | $+4,766.27 | late_strong, mid_weak, old_thin | - | 36 | +0.0070 |
| 1.500% | 1.10 | FAIL | +0.1237 | $+4,772.81 | late_strong, mid_weak, old_thin | - | 35 | +0.0070 |
| 2.000% | 1.10 | FAIL | +0.0961 | $+4,393.86 | late_strong, mid_weak, old_thin | - | 31 | +0.0070 |
| 2.500% | 1.10 | FAIL | +0.0961 | $+4,397.80 | late_strong, mid_weak, old_thin | - | 29 | +0.0070 |
| 3.000% | 1.10 | FAIL | +0.0538 | $+3,895.31 | late_strong, mid_weak, old_thin | - | 28 | +0.0070 |
| 4.000% | 1.10 | FAIL | -0.0007 | $+3,051.76 | mid_weak, old_thin | late_strong | 21 | +0.0070 |
| 5.000% | 1.10 | FAIL | +0.0004 | $+3,034.60 | mid_weak, old_thin | late_strong | 17 | +0.0070 |

Selected excess margin: `0.000%`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.3971 | +0.1077 | $95,321.74 | $97,928.60 | $+2,606.86 | 0.8039 | 11 |
| mid_weak | 1.6747 | 1.6806 | +0.0059 | $62,490.66 | $63,897.83 | $+1,407.17 | 0.7925 | 9 |
| old_thin | 0.3867 | 0.3977 | +0.0110 | $28,855.61 | $29,680.70 | $+825.09 | 0.9167 | 17 |

Production impact: replay-only scout unless Gate 4 passes and the rule is promoted into shared feature/risk/sizing policy with parity coverage.
