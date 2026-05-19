# exp-20260512-110 Signal-Day Ticker Red Risk

Decision: `rejected_signal_day_ticker_red_risk`.

Single variable: post-sizing risk scalar for signals whose own signal-day close is below its open.

| Variant | Scalar | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals | Passed |
|---|---:|---:|---:|---:|---:|---:|---|
| red_scalar_0_0 | 0.00 | -2.1635 | $-68,338.74 | 0 | 3 | 26 | False |
| red_scalar_0_25 | 0.25 | -1.8267 | $-43,948.78 | 0 | 3 | 23 | False |
| red_scalar_0_5 | 0.50 | -1.1689 | $-29,059.83 | 0 | 3 | 23 | False |
| red_scalar_0_75 | 0.75 | -0.5534 | $-13,956.23 | 0 | 3 | 23 | False |

Production impact: replay-only scout. Positive promotion would require shared feature/risk/sizing implementation and parity coverage before any live/default behavior change.
