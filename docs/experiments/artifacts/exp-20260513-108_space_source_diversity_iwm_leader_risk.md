# exp-20260513-108 Space source-diversity IWM-leader risk

## Hypothesis
On top of accepted exp-039 Space source-diversity peer-leader stack, source-diverse official Space signals may deserve extra risk when IWM 20d momentum beats SPY 20d momentum. This tests a production-visible catalyst-quality plus small-cap risk-appetite interaction without changing the Space pool, event metadata, ranking, targets, stops, LLM boundary, or live slots.

## Single Changed Variable
`space_source_diversity_iwm_leader_scalar` after the accepted exp-039 source-diversity peer-leader stack. Candidate pool, event labels, ranking, targets, stops, LLM/news, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.05`
- Aggregate delta vs exp-039: EV `0.475700`, PnL `14030.20`
- Source-diverse IWM-leader signals changed: `10` of `11` eligible

## Three-Window Deltas vs Exp-039
| window | EV delta | PnL delta | max DD delta | trades | survival | IWM-leader adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.059700 | 3305.73 | 0.004700 | 20 | 0.706900 | 2 |
| mid_weak | 0.382900 | 9078.67 | 0.003400 | 23 | 0.653300 | 6 |
| old_thin | 0.033100 | 1645.80 | 0.004300 | 25 | 0.733300 | 3 |

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
