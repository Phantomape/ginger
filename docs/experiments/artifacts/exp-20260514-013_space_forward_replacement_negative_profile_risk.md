# exp-20260514-013 Space forward replacement negative-profile risk

## Hypothesis
Space forward replacement profiles should be useful on both sides of allocation. Official non-attention Space tickers whose mature 10d forward profile has negative cash-relative PnL or negative same-theme replacement value may deserve a default-off risk haircut on top of the accepted exp-20260514-009 stack.

## Single Changed Variable
`space_forward_replacement_negative_profile_scalar` for official Space tickers whose mature non-attention 10d profile has negative cash-relative PnL or negative same-theme replacement value. Candidate pool, ranking, targets, stops, LLM/news, accepted exp-009 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.0`
- Aggregate delta vs exp-009: EV `0.000000`, PnL `0.00`
- Negative-profile signals changed: `0` of `11` eligible
- Target tickers: `ASTS, PL`

## Three-Window Deltas vs Exp-009
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 2 |
| mid_weak | 0.000000 | 0.00 | 0.000000 | 23 | 0.653300 | 6 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.733300 | 3 |

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
