# exp-20260513-009 Signal-Day Close-Location Risk

Decision: `rejected_signal_day_close_location_risk`.

Single variable: cap-aware post-sizing risk scalar for signals whose own signal-day close is in the upper quartile of the daily high-low range.

| Variant | Scalar | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse | Passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| close_location_scalar_1_05 | 1.05 | +0.0139 | $+1,379.78 | 1 | 2 | 27 | +0.0033 | False |
| close_location_scalar_1_1 | 1.10 | +0.0373 | $+2,903.10 | 2 | 1 | 28 | +0.0070 | False |
| close_location_scalar_1_15 | 1.15 | +0.0449 | $+4,126.60 | 2 | 1 | 29 | +0.0106 | False |
| close_location_scalar_1_25 | 1.25 | +0.0193 | $+6,324.91 | 2 | 1 | 33 | +0.0178 | False |

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.3414 | +0.0520 | $95,321.74 | $97,775.43 | $+2,453.69 | 0.8039 | 8 |
| mid_weak | 1.6747 | 1.6786 | +0.0039 | $62,490.66 | $64,557.89 | $+2,067.23 | 0.7925 | 7 |
| old_thin | 0.3867 | 0.3757 | -0.0110 | $28,855.61 | $28,461.29 | $-394.32 | 0.9167 | 14 |

Production impact: replay-only scout. Positive promotion would require shared feature/risk/sizing implementation and parity coverage before any live/default behavior change.
