# exp-20260514-021 Space IRDM forward-candidate risk

## Hypothesis
Space candidate expansion should be narrow and catalyst-qualified. IRDM, unlike broad mature satcom breadth or VSAT, now has a closed official Golden Dome/defense-budget forward profile with positive 10d cash, SPY-relative, and UFO-relative value despite negative same-theme replacement value. Exp-20260514-015 showed broad VSAT admission was damaged by breakout losses, so trend-only IRDM risk may keep the replacement alpha while removing the non-trend tail.

## Single Changed Variable
`space_irdm_trend_forward_candidate_scalar`, where the accepted exp-009 default-off Space stack is unchanged and only IRDM `trend_long` signals receive bounded risk after passing the closed official Golden Dome forward replacement profile. Non-trend IRDM signals are forced to zero risk; broad satcom, VSAT/GSAT/SATS, LLM/news, entries, exits, ranking, targets, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.0`
- Aggregate delta vs exp-009: EV `0.654700`, PnL `19039.66`
- IRDM trend signals changed / non-trend zeroed: `0` / `1` from `3` eligible
- IRDM trend trades / non-trend trades: `1` / `0`, PnL `7851.72`

## Three-Window Deltas vs Exp-009
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted | IRDM trend trades | IRDM nontrend trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 0.737600 | 20285.29 | 0.020300 | 21 | 0.693500 | 2 | 1 | 0 |
| mid_weak | 0.000000 | 0.00 | 0.000000 | 23 | 0.657900 | 1 | 0 | 0 |
| old_thin | -0.082900 | -1245.63 | 0.000000 | 25 | 0.688300 | 0 | 0 | 0 |

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
