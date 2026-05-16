# exp-20260516-029 Space dual-catalyst benchmark-breadth trend risk

## Hypothesis
Accepted dual-catalyst source-diverse official Space trend signals may still be mis-sized when closed replacement rows show positive 10d outcomes versus cash, SPY, QQQ, UFO, and ARKX; this tests whether broad replacement quality strengthens that already accepted customer-plus-government catalyst stack.

## Single Changed Variable
`space_dual_catalyst_benchmark_breadth_trend_scalar` on top of accepted `exp-20260516-024`.

## Gate 1 Baseline
- before experiment: `exp-20260516-024` / `space_dual_catalyst_financing_profile_trend_risk`
- aggregate before EV: `29.0538`
- aggregate before PnL: `750703.48`
- aggregate before max drawdown pct max: `0.2343`

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
| late_strong | 8.664000 | 8.711600 | 0.047600 | 2042.92 | 0.002700 | 18 | 18 |
| mid_weak | 18.784700 | 18.923900 | 0.139200 | 3081.47 | 0.000000 | 23 | 23 |
| old_thin | 1.605100 | 1.605100 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.0125`
- eligible signals: `4`
- changed signals: `4`
- changed tickers: `['LUNR', 'RKLB']`
- changed windows: `['late_strong', 'mid_weak']`
- aggregate EV delta: `0.1868`
- aggregate PnL delta: `5124.39`
- max drawdown pct max delta: `0.0027`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0476, 'mid_weak': 0.1392}`
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
