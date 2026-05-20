# exp-20260520-038 Current-Stack DTE Residual Risk

Decision: `rejected_current_stack_dte_residual_risk`.

Single variable: post-sizing residual risk scalar for already-qualified signals with an existing non-neutral DTE risk tag.

## Trial Accounting

- trial_family: `current_stack_dte_residual_risk`
- prior_trial_count: `4`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_current_stack_cross_dte_cohort`

## Sweep

| Residual scalar | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|---:|
| 1.00 | CTRL | +0.0000 | $+0.00 | - | - | 0 | 0 | +0.0000 |
| 0.75 | FAIL | -0.0664 | $-2,979.84 | late_strong, mid_weak | old_thin | 15 | 3 | +0.0000 |
| 0.50 | FAIL | -0.0557 | $-2,656.13 | late_strong, mid_weak | old_thin | 15 | 3 | +0.0000 |
| 0.25 | FAIL | -0.0360 | $-2,291.70 | late_strong, mid_weak | old_thin | 15 | 3 | +0.0000 |
| 0.00 | FAIL | -0.7291 | $-15,779.39 | - | late_strong, mid_weak, old_thin | 15 | 3 | +0.0000 |

Selected non-control residual scalar: `0.25`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1756 | +0.0128 | $117,072.92 | $117,355.37 | $+282.45 | 0.8039 | 3 |
| mid_weak | 2.1402 | 2.1779 | +0.0377 | $78,110.11 | $78,907.24 | $+797.13 | 0.7925 | 5 |
| old_thin | 0.5911 | 0.5046 | -0.0865 | $39,667.96 | $36,296.68 | $-3,371.28 | 0.8833 | 7 |

Production impact: replay-only. Any positive promotion would need shared portfolio-engine policy, parity tests, and another canonical three-window run.

No JavaScript was used.
