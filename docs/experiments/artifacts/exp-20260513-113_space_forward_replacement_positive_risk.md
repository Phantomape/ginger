# exp-20260513-113 Space forward replacement-positive risk

## Hypothesis
On top of accepted exp-110 Space default-off stack, official Space signals whose closed event-state ledger profile is both 10d cash-positive and same-theme replacement-positive may deserve incremental default-off risk. This tests forward replacement value as the catalyst-quality allocator requested by the Space playbook without changing the Space pool, event metadata, ranking, targets, stops, LLM boundary, or live slots.

## Single Changed Variable
`space_forward_replacement_positive_scalar` after the accepted exp-110 Space stack. The bucket is official Space tickers whose closed event-state ledger profile is 10d cash-positive and same-theme replacement-positive. Candidate pool, event labels, ranking, targets, stops, LLM/news, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.05`
- Aggregate delta vs exp-110: EV `0.353800`, PnL `14086.46`
- Forward replacement-positive signals changed: `14` of `14` eligible
- Target tickers: `BKSY, LUNR, RDW, RKLB`

## Three-Window Deltas vs Exp-110
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.062200 | 3456.37 | 0.005000 | 20 | 0.706900 | 2 |
| mid_weak | 0.097000 | 3726.52 | 0.003700 | 23 | 0.653300 | 6 |
| old_thin | 0.194600 | 6903.57 | 0.004800 | 25 | 0.733300 | 6 |

## Gate Checks
- Gate 2 passed: `True`
- Gate 3 survival passed: `True`

## Production Impact
```text
production_impact:
  shared_policy_changed: True
  backtester_adapter_changed: False
  run_adapter_changed: True
  replay_only: True
  parity_test_added: True
```
