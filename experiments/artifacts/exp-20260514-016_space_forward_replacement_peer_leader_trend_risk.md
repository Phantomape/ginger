# exp-20260514-016 Space forward replacement peer-leader trend risk

## Hypothesis
Space replacement-strength allocation may be strongest when forward same-theme cash evidence, trend continuation, and Space peer leadership agree. On top of accepted exp-20260514-009, a single extra peer-leader trend scalar tests the playbook's catalyst/source/peer bucket direction without adding noisy tickers, broad filters, LLM authority, lifecycle rules, or live Space slots.

## Single Changed Variable
`space_forward_replacement_peer_leader_trend_scalar` for `trend_long` signals already in the accepted forward same-theme replacement-strength bucket and whose Space peer momentum state is `leader`. Candidate pool, ranking, targets, stops, LLM/news, accepted exp-009 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.1`
- Aggregate delta vs exp-009: EV `0.282800`, PnL `7617.64`
- Peer-leader trend signals changed: `3` of `3` eligible
- Target tickers: `BKSY, RDW`

## Three-Window Deltas vs Exp-009
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 0 |
| mid_weak | 0.000000 | 0.00 | 0.000000 | 23 | 0.653300 | 1 |
| old_thin | 0.282800 | 7617.64 | -0.000100 | 25 | 0.733300 | 2 |

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
