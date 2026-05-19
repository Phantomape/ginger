# exp-20260514-041 Space benchmark-breadth trend risk

## Hypothesis
Space official catalysts with broad 10d confirmation against cash, SPY, QQQ, UFO, and ARKX may deserve conservative trend risk allocation even when the evidence is not purely same-theme. This tests a production-visible closed-forward breadth state without adding tickers, LLM authority, or lifecycle changes.

## Single Changed Variable
`space_benchmark_breadth_trend_scalar` for official Space `trend_long` signals whose closed 10d event-state profile has positive cash-relative, SPY-relative, QQQ-relative, UFO-relative, and ARKX-relative value. Candidate pool, ranking, targets, stops, LLM/news, and accepted exp030 stack stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.025`
- Aggregate delta vs exp030: EV `0.222600`, PnL `5848.12`
- Benchmark-breadth signals changed: `4` of `4` eligible
- Target tickers: `BKSY, LUNR, PL, RDW, RKLB`

## Three-Window Deltas vs Exp030
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.048200 | 2137.00 | 0.003700 | 20 | 0.706900 | 1 |
| mid_weak | 0.174400 | 3711.12 | 0.000100 | 23 | 0.653300 | 3 |
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

