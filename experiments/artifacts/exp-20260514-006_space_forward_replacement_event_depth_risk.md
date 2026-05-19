# exp-20260514-006 Space forward replacement event-depth risk

## Hypothesis
On top of accepted exp-20260514-001, official Space signals whose closed 10d forward event-state profile has at least two positive official non-attention events may deserve incremental default-off risk. This tests the playbook's catalyst-family/source/profile replacement-value direction without LLM soft-ranking, ticker expansion, or live Space slots.

## Single Changed Variable
`space_forward_replacement_event_depth_scalar` for the narrower closed-forward profile bucket with at least two positive official non-attention events. Candidate pool, event labels, ranking, targets, stops, LLM/news, accepted exp-001 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best min-events/scalar: `2` / `0.75`
- Aggregate delta vs exp-001: EV `0.000000`, PnL `0.00`
- Event-depth signals changed: `2` of `2` eligible
- Target tickers: `LUNR`
- Target set narrowed vs exp-001: `True`

## Three-Window Deltas vs Exp-001
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 0 |
| mid_weak | 0.000000 | 0.00 | 0.000000 | 23 | 0.653300 | 1 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.733300 | 1 |

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
