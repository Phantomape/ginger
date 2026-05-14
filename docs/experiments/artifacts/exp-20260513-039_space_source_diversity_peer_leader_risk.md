# exp-20260513-039 Space source-diversity peer-leader risk

## Hypothesis
On top of accepted exp-038 Space source-diversity stack, official Space signals with diversified non-attention official catalyst evidence may deserve extra risk only when the ticker is also a Space peer momentum leader. This tests one risk-allocation scalar without changing the Space pool, event metadata, rankings, targets, stops, LLM boundary, or live slots.

## Single Changed Variable
`space_source_diversity_peer_leader_scalar` after the accepted source-diversity `1.075x` helper. Candidate pool, source-diversity definition, rankings, targets, stops, LLM/news, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.15`
- Aggregate delta vs exp-038: EV `0.769500`, PnL `20539.26`
- Peer-leader source-diverse signals changed: `8` of `8` eligible

## Three-Window Deltas vs Exp-038
| window | EV delta | PnL delta | max DD delta | trades | survival | peer-leader adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 1 |
| mid_weak | 0.550800 | 11504.29 | 0.002200 | 23 | 0.653300 | 3 |
| old_thin | 0.218700 | 9034.97 | 0.008000 | 25 | 0.733300 | 4 |

## Gate Checks
- Gate 2 passed: `False`
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
