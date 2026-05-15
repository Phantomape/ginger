# exp-20260514-028 Space source-diversity trend risk

## Hypothesis
Space source-diverse, multi-event official catalyst evidence should be most useful when the market setup is trend continuation rather than a generic event flag. On top of accepted exp-20260514-026, a single extra source-diversity trend scalar tests that semantic quality interaction without adding tickers, filters, lifecycle rules, LLM authority, or live Space slots.

## Single Changed Variable
`space_source_diversity_trend_scalar` for official Space signals whose non-attention official event profile spans multiple source types and semantic buckets, restricted to `trend_long`. Candidate pool, ranking, targets, stops, LLM/news, accepted exp-026 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.025`
- Aggregate delta vs exp-026: EV `0.402700`, PnL `9616.74`
- Source-diversity trend signals changed: `6` of `6` eligible
- Target tickers: `ASTS, LUNR, RKLB`

## Three-Window Deltas vs Exp-026
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.045200 | 2019.32 | 0.003400 | 20 | 0.706900 | 1 |
| mid_weak | 0.357500 | 7597.42 | 0.000000 | 23 | 0.653300 | 5 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.720000 | 0 |

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
