# exp-20260514-048 Space customer-win failed 1d trend risk

## Hypothesis
Space customer-win events that immediately fail 1d follow-through against cash, same-theme replacement, SPY, QQQ, UFO, and ARKX may be lower-quality continuation catalysts, so benchmark-breadth trend signals for those tickers may deserve a conservative default-off risk downscale.

## Single Changed Variable
`space_customer_win_failed_1d_trend_scalar` for official Space `trend_long` benchmark-breadth signals whose closed customer-win event profile failed 1d against cash, same-theme replacement, SPY, QQQ, UFO, and ARKX. Candidate pool, LLM/news, ranking, targets, stops, accepted exp047 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.0`
- Aggregate delta vs exp047: EV `0.000000`, PnL `0.00`
- Customer-win failed-1d signals changed: `0` of `1` eligible
- Target tickers: `ASTS, LUNR`

## Three-Window Deltas vs Exp047
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 0 |
| mid_weak | 0.000000 | 0.00 | 0.000000 | 23 | 0.653300 | 0 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.706700 | 0 |

## Gate Checks
- Gate 2 passed: `True`
- Gate 3 survival passed: `True`
- Sample guard passed: `True`

## Production Impact
```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: True
  parity_test_added: False
```
