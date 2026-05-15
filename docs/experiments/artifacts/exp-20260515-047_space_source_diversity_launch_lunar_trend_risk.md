# exp-20260515-047 Space source-diversity launch/lunar trend risk

## Hypothesis
Source-diverse official Space `trend_long` signals may need a different default-off allocation when the ticker belongs to the production universe-registry `launch_lunar` theme segment.

## Single Changed Variable
`space_source_diversity_launch_lunar_trend_scalar` on top of accepted `exp-20260515-044`.

## Gate 1 Baseline
- before experiment: `exp-20260515-044` / `space_source_diversity_peer_nonleader_near_perfect_trend_risk`
- aggregate before EV: `26.5438`
- aggregate before PnL: `733923.08`

## Gate 2 Field Check
- open position field check passed: `True`
- theme segment field check passed: `True`
- target segment: `launch_lunar`
- target tickers: `['LUNR', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.444200 | 8.643600 | 0.199400 | 10306.29 | 0.015000 | 18 | 18 |
| mid_weak | 16.530200 | 18.061600 | 1.531400 | -10719.30 | -0.065200 | 24 | 23 |
| old_thin | 1.569400 | 1.569400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.075`
- eligible signals: `4`
- adjusted signals: `4`
- adjusted counts: `{'space_source_diversity_launch_lunar_trend_risk_changed_LUNR': 1, 'space_source_diversity_launch_lunar_trend_risk_changed_RKLB': 3, 'space_source_diversity_launch_lunar_trend_risk_changed_signal': 4, 'space_source_diversity_launch_lunar_trend_risk_eligible_LUNR': 1, 'space_source_diversity_launch_lunar_trend_risk_eligible_RKLB': 3, 'space_source_diversity_launch_lunar_trend_risk_eligible_signal': 4}`
- aggregate EV delta: `1.7308`
- aggregate PnL delta: `-413.01`
- max drawdown pct max delta: `0.015`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'late_strong': 0.1994, 'mid_weak': 1.5314}`
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
