# exp-20260514-010 Space 5d forward replacement confirmation risk

## Hypothesis
Space forward replacement alpha may appear first at the 5-trading-day horizon before the accepted 10d profile fully closes. Official non-attention Space tickers with positive 5d cash-relative and same-theme replacement value may deserve an incremental default-off risk allocation on top of the accepted exp-20260514-009 stack.

## Single Changed Variable
`space_forward_replacement_5d_confirmation_scalar` for official Space tickers whose non-attention 5d forward profile is cash-positive and same-theme replacement-positive. Candidate pool, ranking, targets, stops, LLM/news, accepted exp-009 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.1`
- Aggregate delta vs exp-009: EV `0.155500`, PnL `3228.04`
- 5d confirmation signals changed: `7` of `9` eligible
- Target tickers: `BKSY, PL`

## Three-Window Deltas vs Exp-009
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 2 |
| mid_weak | -0.001000 | -24.69 | 0.000000 | 23 | 0.653300 | 4 |
| old_thin | 0.156500 | 3252.73 | -0.001700 | 25 | 0.733300 | 3 |

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
