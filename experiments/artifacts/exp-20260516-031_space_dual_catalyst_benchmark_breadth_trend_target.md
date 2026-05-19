# exp-20260516-031 Space dual-catalyst benchmark-breadth trend target

## Hypothesis
The current accepted Space alpha is concentrated in source-diverse dual-catalyst benchmark-breadth trend signals. If this is a true convex event-trend state rather than only a sizing state, widening the target ATR floor should capture more upside without adding tickers, LLM soft-ranking, or another risk scalar.

## Single Changed Variable
`space_dual_catalyst_benchmark_breadth_trend_target_atr_floor` on top of accepted `exp-20260516-029`.

## Gate 1 Baseline
- before experiment: `exp-20260516-029` / `space_dual_catalyst_benchmark_breadth_trend_risk`
- aggregate before EV: `29.2406`
- aggregate before PnL: `755827.87`
- aggregate before max drawdown pct max: `0.237`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- benchmark-breadth target field check passed: `True`
- target input check passed: `True`
- target tickers: `['LUNR', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a target-width sweep.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.711600 | 8.711600 | 0.000000 | 0.00 | 0.000000 | 18 | 18 |
| mid_weak | 18.923900 | 18.923900 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |
| old_thin | 1.605100 | 1.605100 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- target ATR floor: `5.0`
- eligible signals: `5`
- changed signals: `5`
- changed tickers: `['LUNR', 'RKLB']`
- changed windows: `['late_strong', 'mid_weak']`
- aggregate EV delta: `0.0`
- aggregate PnL delta: `0.0`
- max drawdown pct max delta: `0.0`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{}`
- regressed windows: `{}`

## Production Impact
```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
  live_slots: 0
```
