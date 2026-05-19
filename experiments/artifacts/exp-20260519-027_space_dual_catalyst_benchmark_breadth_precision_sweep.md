# exp-20260519-027 Space dual-catalyst benchmark-breadth precision sweep

## Hypothesis
The accepted source-diverse dual-catalyst benchmark-breadth Space trend cohort may be under-allocated at 1.0125; a finer scalar inside the prior 1.025 drawdown boundary could improve EV while keeping the original anchor drawdown guard intact.

## Single Changed Variable
`space_source_diversity_dual_catalyst_benchmark_breadth_trend_risk_scalar`.

## Gate 1 Baseline
- current accepted scalar: `1.0125` from `exp-20260516-029`
- current aggregate EV: `28.9969`
- current aggregate PnL: `737828.64`
- anchor scalar for drawdown ratchet check: `1.0`
- anchor aggregate max drawdown pct max: `0.2343`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- benchmark-breadth field check passed: `True`
- target tickers: `['LUNR', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.735600 | 8.762700 | 0.027100 | 1479.70 | 0.002100 | 17 | 17 |
| mid_weak | 19.022900 | 19.058800 | 0.035900 | 1733.08 | 0.000100 | 23 | 23 |
| old_thin | 1.238400 | 1.238400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.021875`
- eligible signals: `4`
- changed signals: `4`
- changed tickers: `['LUNR', 'RKLB']`
- changed windows: `['late_strong', 'mid_weak']`
- aggregate EV delta vs current: `0.063`
- aggregate PnL delta vs current: `3212.78`
- max drawdown delta vs current: `0.0021`
- max drawdown delta vs anchor: `0.0048`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0271, 'mid_weak': 0.0359}`
- regressed windows: `{}`

## Production Impact
```text
production_impact:
  shared_policy_changed: true
  backtester_adapter_changed: true
  run_adapter_changed: true
  replay_only: false
  parity_test_added: true
  live_slots: 0
```
