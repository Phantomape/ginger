# exp-20260513-003 Signal-Day Ticker Green Risk

Decision: `accepted_for_shared_policy_implementation`.

Single variable: cap-aware post-sizing risk scalar for signals whose own signal-day close is above its open.

| Variant | Scalar | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals | Max DD worse | Passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| green_scalar_1_05 | 1.05 | +0.0626 | $+2,223.59 | 3 | 0 | 37 | +0.0029 | True |
| green_scalar_1_1 | 1.10 | +0.1227 | $+4,805.44 | 3 | 0 | 40 | +0.0066 | False |
| green_scalar_1_15 | 1.15 | +0.1774 | $+7,311.74 | 3 | 0 | 45 | +0.0103 | False |
| green_scalar_1_25 | 1.25 | +0.1979 | $+10,653.01 | 3 | 0 | 49 | +0.0171 | False |
| green_scalar_1_5 | 1.50 | +0.1637 | $+16,171.76 | 3 | 0 | 52 | +0.0238 | False |

Production impact: replay-only scout. Positive promotion would require shared feature/risk/sizing implementation and parity coverage before any live/default behavior change.
