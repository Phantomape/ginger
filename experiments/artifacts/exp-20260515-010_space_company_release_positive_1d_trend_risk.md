# exp-20260515-010 Space company-release positive 1d trend risk

## Hypothesis
Official Space `trend_long` signals with a mature positive 1d company-release customer-win profile may be under-sized by the accepted default-off Space stack.

## Single Changed Variable
`space_company_release_positive_1d_trend_scalar` on top of the accepted `exp-20260514-053` Space stack.

## Gate 1 Baseline
- before experiment: `exp-20260514-053` / `space_benchmark_breadth_iwm_leader_trend_risk`
- aggregate before EV: `27.7694`
- aggregate before PnL: `692238.43`
- aggregate before max drawdown pct max: `0.1616`

## Gate 2 Field Check
- open position field check passed: `True`
- benchmark-breadth gate passed: `True`
- company-release positive-1d gate passed: `True`
- target tickers: `['RKLB']`
- target profile rows: `1`

## Gate 3 Survival Audit
- min survival before: `0.6533`
- min survival after: `0.6533`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.894100 | 7.894100 | 0.000000 | 0.00 | 0.000000 | 20 | 20 |
| mid_weak | 15.067200 | 15.067200 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |
| old_thin | 4.808100 | 4.808100 | 0.000000 | 0.00 | 0.000000 | 25 | 25 |

## Best Variant
- scalar: `1.0`
- eligible signals: `3`
- adjusted signals: `0`
- adjusted counts: `{'space_company_release_positive_1d_trend_risk_eligible_RKLB': 3, 'space_company_release_positive_1d_trend_risk_eligible_signal': 3}`
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
