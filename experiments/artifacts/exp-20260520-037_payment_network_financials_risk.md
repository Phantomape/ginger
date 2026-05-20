# exp-20260520-037 Payment-Network Financials Risk

Decision: `rejected_payment_network_financials_risk`.

Single variable: post-sizing risk multiplier for already-qualified core long signals whose ticker is `V` or `MA`.

## Trial Accounting

- trial_family: `current_ticker_pool_governance`
- prior_trial_count: `4`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_current_stack_three_window_contribution`

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|---:|
| 1.00 | CTRL | +0.0000 | $+0.00 | - | - | 0 | 0 | +0.0000 |
| 0.75 | FAIL | +0.0223 | $+950.20 | old_thin | - | 3 | 1 | +0.0000 |
| 0.50 | FAIL | +0.0489 | $+1,894.97 | old_thin | - | 3 | 1 | +0.0000 |
| 0.25 | FAIL | +0.0760 | $+2,819.52 | old_thin | - | 3 | 1 | +0.0000 |
| 0.00 | FAIL | +0.0993 | $+3,749.93 | old_thin | - | 3 | 1 | +0.0000 |

Selected non-control multiplier: `0.0`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | 0.8039 | 0 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $78,110.11 | $78,110.11 | $+0.00 | 0.7925 | 0 |
| old_thin | 0.5911 | 0.6904 | +0.0993 | $39,667.96 | $43,417.89 | $+3,749.93 | 0.8667 | 3 |

Production impact: replay-only. Any positive promotion would need shared constants/portfolio-engine implementation, parity tests, and another canonical three-window run.

No JavaScript was used.
