# exp-20260514-042 Space 20d durability trend risk

## Hypothesis
Space official catalysts whose 20d closed event-state profile is still positive versus cash, same-theme replacement, SPY, QQQ, UFO, and ARKX may deserve an extra conservative trend allocation because durability should be a stronger continuation state than the accepted 10d benchmark-breadth signal.

## Single Changed Variable
`space_forward_replacement_20d_durability_trend_scalar` for official Space `trend_long` signals whose mature 20d event-state profile is positive versus cash, same-theme replacement, SPY, QQQ, UFO, and ARKX. Candidate pool, ranking, targets, stops, LLM/news, live slots, and the accepted exp041 stack stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.0`
- Aggregate delta vs exp041: EV `0.000000`, PnL `0.00`
- 20d-durability signals changed: `0` of `1` eligible
- Target tickers: `LUNR`

## Three-Window Deltas vs Exp041
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 0 |
| mid_weak | 0.000000 | 0.00 | 0.000000 | 23 | 0.653300 | 0 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.706700 | 0 |

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
