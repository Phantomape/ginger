# exp-20260514-020 Space forward benchmark-positive laggard risk

## Hypothesis
The accepted Space forward stack may be under-allocating official catalyst tickers whose 10d cash, SPY-relative, and UFO-relative profiles are positive even when same-theme replacement value is negative. This tests a benchmark-relative replacement-value scalar on top of accepted exp-20260514-009 without adding tickers, broad filters, LLM authority, lifecycle rules, or live Space slots.

## Single Changed Variable
`space_forward_benchmark_laggard_scalar` for accepted official Space tickers whose mature 10d forward profile is cash/SPY/UFO-positive but same-theme replacement-negative. Candidate pool, ranking, targets, stops, LLM/news, accepted exp-009 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.1`
- Aggregate delta vs exp-009: EV `0.173000`, PnL `3247.61`
- Benchmark-laggard signals changed: `5` of `7` eligible
- Target tickers: `PL`

## Three-Window Deltas vs Exp-009
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 2 |
| mid_weak | -0.001400 | -24.69 | 0.000000 | 23 | 0.653300 | 2 |
| old_thin | 0.174400 | 3272.30 | -0.001700 | 25 | 0.733300 | 3 |

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
