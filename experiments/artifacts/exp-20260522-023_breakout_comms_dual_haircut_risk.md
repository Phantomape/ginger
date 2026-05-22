# exp-20260522-023 Breakout Communication Services Dual-Haircut Risk

Decision: `rejected_breakout_comms_dual_haircut_risk`.

Single variable: post-sizing risk multiplier for already-qualified Communication Services breakout signals that have both accepted 0.25x risk tags.

## Trial Accounting

- trial_family: `current_stack_existing_haircut_residual_risk`
- prior_trial_count: `5`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_current_stack_three_window_multiplier_attribution`

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|---:|
| 1.00 | CTRL | +0.0000 | $+0.00 | - | - | 0 | 0 | +0.0000 |
| 0.75 | FAIL | +0.0009 | $+41.17 | mid_weak, old_thin | - | 2 | 2 | +0.0000 |
| 0.50 | FAIL | +0.0014 | $+72.61 | mid_weak, old_thin | - | 2 | 2 | +0.0000 |
| 0.25 | FAIL | +0.0023 | $+104.06 | mid_weak, old_thin | - | 2 | 2 | +0.0000 |
| 0.00 | FAIL | +0.3222 | $-3,895.37 | mid_weak, old_thin | - | 2 | 2 | +0.0001 |

Selected non-control multiplier: `0.0`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | 0.8039 | 0 |
| mid_weak | 2.1402 | 2.4614 | +0.3212 | $78,110.11 | $74,144.83 | $-3,965.28 | 0.7818 | 1 |
| old_thin | 0.5911 | 0.5921 | +0.0010 | $39,667.96 | $39,737.87 | $+69.91 | 0.8667 | 1 |

Production impact: replay-only. Any positive promotion would need shared portfolio-engine implementation, run.py parity, and a fresh canonical rerun.

No JavaScript was used.
