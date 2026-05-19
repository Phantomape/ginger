# exp-20260514-016 Space VSAT trend-only forward-candidate risk

## Hypothesis
Space candidate expansion should be narrow and catalyst-qualified. VSAT, unlike broad mature satcom or GSAT, now has a closed official Golden Dome/defense-budget forward profile with positive 10d cash, same-theme, SPY-relative, and UFO-relative replacement value. Exp-20260514-015 showed broad VSAT admission was damaged by breakout losses, so trend-only VSAT risk may keep the replacement alpha while removing the non-trend tail.

## Single Changed Variable
`space_vsat_trend_forward_candidate_scalar`, where the accepted exp-009 default-off Space stack is unchanged and only VSAT `trend_long` signals receive bounded risk after passing the closed official Golden Dome forward replacement profile. Non-trend VSAT signals are forced to zero risk; broad satcom, GSAT, LLM/news, entries, exits, ranking, targets, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.0`
- Aggregate delta vs exp-009: EV `2.581900`, PnL `48422.55`
- VSAT trend signals changed / non-trend zeroed: `0` / `2` from `6` eligible
- VSAT trend trades / non-trend trades: `1` / `0`, PnL `19523.6`

## Three-Window Deltas vs Exp-009
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted | VSAT trend trades | VSAT nontrend trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 0.217000 | 12133.47 | 0.020300 | 20 | 0.716700 | 2 | 0 | 0 |
| mid_weak | 2.364900 | 36289.08 | -0.006700 | 24 | 0.670900 | 4 | 1 | 0 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.733300 | 0 | 0 | 0 |

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
