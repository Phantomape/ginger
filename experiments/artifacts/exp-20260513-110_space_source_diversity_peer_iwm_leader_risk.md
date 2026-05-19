# exp-20260513-110 Space source-diversity peer+IWM-leader risk

## Hypothesis
On top of accepted exp-108 Space source-diversity peer-leader and IWM-leader stack, source-diverse official Space signals may deserve extra risk only when both ticker-level peer leadership and small-cap risk appetite confirm. This tests a production-visible catalyst-quality plus relative-strength plus tape-state interaction without changing the Space pool, event metadata, ranking, targets, stops, LLM boundary, or live slots.

## Single Changed Variable
`space_source_diversity_peer_iwm_leader_scalar` after the accepted exp-108 source-diversity peer-leader and IWM-leader stack. Candidate pool, event labels, ranking, targets, stops, LLM/news, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.05`
- Aggregate delta vs exp-108: EV `0.255600`, PnL `6353.99`
- Source-diverse peer+IWM-leader signals changed: `7` of `7` eligible

## Three-Window Deltas vs Exp-108
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 1 |
| mid_weak | 0.219900 | 4605.03 | 0.003600 | 23 | 0.653300 | 3 |
| old_thin | 0.035700 | 1748.96 | 0.004500 | 25 | 0.733300 | 3 |

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
