# exp-20260520-041 Current-Stack DTE Non-Confirming Candle Risk

Decision: `rejected_current_dte_nonconfirming_candle_risk`.

Single variable: post-sizing residual risk scalar for already-qualified signals with an existing non-neutral DTE risk tag and no same-day green candle confirmation.

## Trial Accounting

- trial_family: `current_stack_dte_nonconfirming_candle_risk`
- prior_trial_count: `5`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `new_dte_diagnostic_subcohort`

## Sweep

| Residual scalar | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|---:|
| 1.00 | CTRL | +0.0000 | $+0.00 | - | - | 0 | 0 | +0.0000 |
| 0.75 | FAIL | +0.0044 | $+161.08 | mid_weak | - | 4 | 2 | +0.0000 |
| 0.50 | FAIL | +0.0044 | $+158.67 | mid_weak | - | 4 | 2 | +0.0000 |
| 0.25 | FAIL | +0.0158 | $+286.33 | mid_weak | - | 4 | 2 | +0.0000 |
| 0.00 | FAIL | +0.0183 | $+380.06 | mid_weak | - | 4 | 2 | +0.0000 |

Selected non-control non-confirming scalar: `0.0`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | 0.8039 | 0 |
| mid_weak | 2.1402 | 2.1585 | +0.0183 | $78,110.11 | $78,490.17 | $+380.06 | 0.7925 | 3 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $39,667.96 | $39,667.96 | $+0.00 | 0.8667 | 1 |

Production impact: replay-only. Any positive promotion would need shared portfolio-engine policy, parity tests, and another canonical three-window run.

No JavaScript was used.
