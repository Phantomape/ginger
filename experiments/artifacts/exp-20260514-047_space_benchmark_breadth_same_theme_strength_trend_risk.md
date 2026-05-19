# exp-20260514-047 Space benchmark-breadth same-theme strength trend risk

## Hypothesis
Space trend signals may deserve a small extra default-off risk allocation when the closed 10d event-state profile is both broadly positive versus cash, SPY, QQQ, UFO, and ARKX and also clears the already accepted same-theme replacement-strength floor. This should capture stronger catalyst quality without adding tickers, LLM authority, filters, or live slots.

## Single Changed Variable
`space_benchmark_breadth_same_theme_strength_trend_scalar` for official Space `trend_long` signals whose accepted benchmark-breadth profile is true and whose average 10d same-theme replacement value clears the already accepted $500 strength floor. Candidate pool, ranking, targets, stops, LLM/news, accepted exp044 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.025`
- Aggregate delta vs exp044: EV `0.180200`, PnL `5700.54`
- Benchmark + same-theme strength signals changed: `3` of `3` eligible
- Target tickers: `BKSY, RDW, RKLB`

## Three-Window Deltas vs Exp044
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.054500 | 2355.29 | 0.003800 | 20 | 0.706900 | 1 |
| mid_weak | 0.125700 | 3345.25 | 0.000200 | 23 | 0.653300 | 2 |
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
