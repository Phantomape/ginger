# exp-20260516-023 Space dual-catalyst near-perfect trend risk

## Hypothesis
Accepted dual-catalyst source-diverse official Space trend signals may still be mis-sized when their setup quality is near-perfect but not perfect, because the catalyst stack may make this established TQS bucket behave differently from ordinary Space near-perfect signals.

## Single Changed Variable
`space_dual_catalyst_near_perfect_trend_scalar` on top of accepted `exp-20260516-019`.

## Gate 1 Baseline
- before experiment: `exp-20260516-019` / `space_dual_catalyst_same_theme_winner_trend_risk`
- aggregate before EV: `28.6882`
- aggregate before PnL: `740771.51`
- aggregate before max drawdown pct max: `0.2292`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- near-perfect signal field check passed: `True`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.588200 | 8.622700 | 0.034500 | 1658.86 | 0.002600 | 18 | 18 |
| mid_weak | 18.494900 | 18.541300 | 0.046400 | 118.79 | -0.000100 | 23 | 23 |
| old_thin | 1.605100 | 1.605100 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.0125`
- eligible signals: `4`
- changed signals: `4`
- changed tickers: `['ASTS', 'LUNR', 'RKLB']`
- changed windows: `['late_strong', 'mid_weak']`
- aggregate EV delta: `0.0809`
- aggregate PnL delta: `1777.65`
- max drawdown pct max delta: `0.0026`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0345, 'mid_weak': 0.0464}`
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
