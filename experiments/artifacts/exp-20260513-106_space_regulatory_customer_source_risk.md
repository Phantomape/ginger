# exp-20260513-106 Space regulatory customer-source risk

## Hypothesis
On top of accepted exp-039 Space source-diversity peer-leader stack, official Space signals backed by customer_win regulatory authorization may have more durable catalyst quality than generic customer-source events. A single risk scalar tests this without changing the Space pool, event metadata, ranking, targets, stops, LLM boundary, or live slots.

## Single Changed Variable
`space_regulatory_customer_source_scalar` after the accepted exp-039 Space source-diversity peer-leader stack. Candidate pool, event labels, ranking, targets, stops, LLM/news, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.25`
- Aggregate delta vs exp-039: EV `1.775700`, PnL `32335.35`
- Regulatory customer-source signals changed: `2` of `4` eligible

## Three-Window Deltas vs Exp-039
| window | EV delta | PnL delta | max DD delta | trades | survival | regulatory adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 0 |
| mid_weak | 1.775700 | 32335.35 | 0.000200 | 23 | 0.653300 | 4 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.733300 | 0 |

## Target Tickers
ASTS

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
