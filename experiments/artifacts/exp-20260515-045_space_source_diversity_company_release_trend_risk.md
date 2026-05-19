# exp-20260515-045 Space source-diversity company-release trend risk

## Hypothesis
Source-diverse official Space `trend_long` signals may need a different default-off allocation when their source-diversity evidence profile includes `company_release`.

## Single Changed Variable
`space_source_diversity_company_release_trend_scalar` on top of accepted `exp-20260515-044`.

## Gate 1 Baseline
- before experiment: `exp-20260515-044` / `space_source_diversity_peer_nonleader_near_perfect_trend_risk`
- aggregate before EV: `26.5438`
- aggregate before PnL: `733923.08`

## Gate 2 Field Check
- open position field check passed: `True`
- target source type: `company_release`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.444200 | 8.698900 | 0.254700 | 13981.27 | 0.020000 | 18 | 18 |
| mid_weak | 16.530200 | 18.244200 | 1.714000 | -4860.57 | -0.065300 | 24 | 23 |
| old_thin | 1.569400 | 1.569400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.1`
- eligible signals: `3`
- adjusted signals: `3`
- adjusted counts: `{'space_source_diversity_company_release_trend_risk_changed_RKLB': 3, 'space_source_diversity_company_release_trend_risk_changed_signal': 3, 'space_source_diversity_company_release_trend_risk_eligible_RKLB': 3, 'space_source_diversity_company_release_trend_risk_eligible_signal': 3}`
- aggregate EV delta: `1.9687`
- aggregate PnL delta: `9120.7`
- max drawdown pct max delta: `0.02`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'late_strong': 0.2547, 'mid_weak': 1.714}`
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
