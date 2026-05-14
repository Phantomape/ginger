# exp-20260514-044 Space benchmark-breadth peer-nonleader trend risk

## Hypothesis
Space peer-nonleader trend signals may represent delayed catch-up rather than weakness when the closed 10d event-state profile is positive versus cash, SPY, QQQ, UFO, and ARKX. A conservative extra allocation should improve the default-off Space replay without changing entries, exits, ranking, LLM/news, ticker pool, or live slots.

## Single Changed Variable
`space_benchmark_breadth_peer_nonleader_trend_scalar` for official Space `trend_long` signals whose accepted benchmark-breadth profile is true and whose Space peer momentum state is `nonleader`. Candidate pool, ranking, targets, stops, LLM/news, accepted exp041 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.025`
- Aggregate delta vs exp041: EV `0.203500`, PnL `5903.12`
- Peer-nonleader benchmark-breadth signals changed: `3` of `3` eligible

## Three-Window Deltas vs Exp041
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.032700 | 2255.92 | 0.003800 | 20 | 0.706900 | 1 |
| mid_weak | 0.170800 | 3647.20 | -0.000200 | 23 | 0.653300 | 2 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.706700 | 0 |

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
