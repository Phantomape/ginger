# exp-20260513-004 Signal-Day Ticker Green Risk

Decision: `rejected_signal_day_ticker_green_risk`.

Single variable: cap-aware post-sizing risk scalar for signals whose own signal-day close is above its open.

| Variant | Scalar | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals | Max DD worse | Passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| green_scalar_1_05 | 1.05 | +0.0632 | $+2,395.98 | 2 | 1 | 35 | +0.0033 | False |
| green_scalar_1_1 | 1.10 | +0.1246 | $+4,839.12 | 3 | 0 | 38 | +0.0070 | False |
| green_scalar_1_15 | 1.15 | +0.1484 | $+6,857.61 | 3 | 0 | 43 | +0.0106 | False |
| green_scalar_1_25 | 1.25 | +0.1397 | $+10,115.38 | 3 | 0 | 47 | +0.0178 | False |
| green_scalar_1_5 | 1.50 | +0.0847 | $+14,478.49 | 3 | 0 | 50 | +0.0209 | False |

Production impact: replay-only scout. Positive promotion would require shared feature/risk/sizing implementation and parity coverage before any live/default behavior change.
