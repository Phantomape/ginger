# exp-20260514-033 Space benchmark-breadth delayed trend risk

## Hypothesis
Space official catalysts can be alpha-positive even when same-theme replacement strength is below the accepted $500 floor, provided the 5d reaction is still weak and the 10d move beats cash, SPY, QQQ, UFO, and ARKX. This should help trend continuation allocation without adding tickers or LLM authority.

## Single Changed Variable
`space_benchmark_breadth_delayed_trend_scalar` for official Space `trend_long` signals whose closed event-state profile has weak average 5d cash reaction, positive 10d cash and same-theme value, same-theme value below the accepted $500 strength floor, and positive 10d SPY/QQQ/UFO/ARKX relative value. Candidate pool, ranking, targets, stops, LLM/news, and accepted exp030 stack stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.0`
- Aggregate delta vs exp030: EV `0.000000`, PnL `0.00`
- Benchmark-breadth signals changed: `0` of `1` eligible
- Target tickers: `LUNR`

## Three-Window Deltas vs Exp030
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
