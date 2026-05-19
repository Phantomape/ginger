# exp-20260513-111 Space source-diversity strong peer-excess risk

## Hypothesis
On top of accepted exp-110 Space source-diversity stack, source-diverse official Space signals may deserve extra risk only when peer leadership is large in magnitude: ticker 20-day momentum must beat the official Space peer basket by at least 10 percentage points. This tests a production-visible peer-strength discriminator without changing the Space pool, event metadata, ranking, targets, stops, LLM boundary, or live slots.

## Single Changed Variable
`space_source_diversity_strong_peer_excess_scalar` after the accepted exp-110 source-diversity stack. Candidate pool, event labels, ranking, targets, stops, LLM/news, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `0.9`
- Strong peer-excess floor: `0.10`
- Aggregate delta vs exp-110: EV `0.048800`, PnL `-4754.62`
- Source-diverse strong-peer-excess signals changed: `6` of `6` eligible

## Three-Window Deltas vs Exp-110
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 1 |
| mid_weak | 0.229500 | 2579.65 | -0.007200 | 23 | 0.653300 | 1 |
| old_thin | -0.180700 | -7334.27 | -0.009500 | 25 | 0.733300 | 4 |

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
