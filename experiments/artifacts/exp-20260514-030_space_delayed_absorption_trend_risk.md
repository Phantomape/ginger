# exp-20260514-030 Space delayed-absorption trend risk

## Hypothesis
Space official catalysts with delayed market absorption should be more valuable for trend continuation than same-day/5d confirmation. On top of accepted exp-20260514-028, a single extra trend_long scalar tests closed event-state profiles where average 5d cash reaction is weak but 10d cash and same-theme replacement value are strong.

## Single Changed Variable
`space_delayed_absorption_trend_scalar` for `trend_long` Space signals whose closed event-state profile has weak average 5d cash reaction but strong 10d cash and same-theme replacement value. Candidate pool, ranking, targets, stops, LLM/news, and accepted exp-028 stack stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.025`
- Aggregate delta vs exp-028: EV `0.137400`, PnL `5064.39`
- Delayed-absorption signals changed: `3` of `3` eligible
- Target tickers: `RDW, RKLB`

## Three-Window Deltas vs Exp-028
| window | EV delta | PnL delta | max DD delta | trades | survival | delayed adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.034000 | 2228.24 | 0.003600 | 20 | 0.706900 | 1 |
| mid_weak | 0.103400 | 2836.15 | -0.000100 | 23 | 0.653300 | 2 |
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
