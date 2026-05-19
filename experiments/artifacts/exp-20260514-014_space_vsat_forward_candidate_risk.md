# exp-20260514-014 Space VSAT forward-candidate risk

## Hypothesis
Space candidate expansion should be narrow and catalyst-qualified. VSAT, unlike broad mature satcom or GSAT, now has a closed official Golden Dome/defense-budget forward profile with positive 10d cash, same-theme, SPY-relative, and UFO-relative replacement value. A bounded VSAT-only risk budget may add replacement alpha on top of the accepted exp-20260514-009 default-off Space stack.

## Single Changed Variable
`space_vsat_forward_candidate_scalar`, where the accepted exp-009 default-off Space stack is unchanged and only VSAT is admitted with bounded risk after passing the closed official Golden Dome forward replacement profile. Broad satcom, GSAT, LLM/news, entries, exits, ranking, targets, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.0`
- Aggregate delta vs exp-009: EV `1.919200`, PnL `38605.24`
- VSAT signals changed: `0` of `6` eligible
- VSAT trades: `3`, PnL `12109.92`

## Three-Window Deltas vs Exp-009
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted | VSAT trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | -0.445700 | 2316.16 | 0.020300 | 22 | 0.716700 | 2 | 2 |
| mid_weak | 2.364900 | 36289.08 | -0.006700 | 24 | 0.670900 | 4 | 1 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.733300 | 0 | 0 |

## Gate Checks
- Gate 2 passed: `True`
- Gate 3 survival passed: `True`

## Production Impact
```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: True
  parity_test_added: False
```
