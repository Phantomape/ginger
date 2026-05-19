# exp-20260513-038 Space source-diversity risk

## Hypothesis
On top of accepted exp-032 Space attention overlay stack, official Space signals backed by heterogeneous non-attention official evidence may have better catalyst durability than single-channel official evidence. A single risk scalar tests this source/family diversity without changing the Space pool, rankings, targets, stops, LLM boundary, or live slots.

## Single Changed Variable
`space_source_diversity_scalar` applied after the accepted exp-032 attention-overlay stack to official Space tickers with at least two non-attention official source types and at least two semantic buckets.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.075`
- Aggregate delta vs exp-032: EV `0.746300`, PnL `20399.50`
- Source-diversity signals changed: `12` of `14` eligible

## Three-Window Deltas vs Exp-032
| window | EV delta | PnL delta | max DD delta | trades | survival | source-diverse signals |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.102200 | 4569.26 | 0.003900 | 20 | 0.706900 | 2 |
| mid_weak | 0.537200 | 11683.55 | 0.004200 | 23 | 0.653300 | 8 |
| old_thin | 0.106900 | 4146.69 | 0.002000 | 25 | 0.733300 | 4 |

## Target Tickers
ASTS, LUNR, RKLB

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
