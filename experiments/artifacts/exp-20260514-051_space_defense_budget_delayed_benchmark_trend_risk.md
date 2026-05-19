# exp-20260514-051 space_defense_budget_delayed_benchmark_trend_risk

## Hypothesis

Official Space `trend_long` signals tied to `defense_budget_theme` / `government_space_contract` catalysts may be under-sized when 5d cash absorption is weak but 10d cash, SPY, QQQ, UFO, and ARKX relative outcomes are all positive.

## Single Changed Variable

`space_defense_budget_delayed_benchmark_trend_risk_scalar` on top of the accepted `exp-20260514-047` Space stack.

## Gate 1 Baseline

- before experiment: `exp-20260514-047` / `space_benchmark_breadth_same_theme_strength_trend_risk`
- aggregate before EV: `27.3987`
- aggregate before PnL: `679878.08`
- aggregate before max drawdown pct max: `0.1557`

## Gate 2 Field Check

- open position field check passed: `True`
- Space catalyst profile gate passed: `True`
- target tickers: `['LUNR', 'RDW', 'RKLB']`
- target profile rows: `3`

## Gate 3 Survival Audit

- min survival before: `0.6533`
- min survival after: `0.6533`
- no filter was added; trade count and survival should not decline except through sizing-side effects.

## Gate 4 Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.786500 | 7.841400 | 0.054900 | 2386.68 | 20 | 20 |
| mid_weak | 14.806100 | 14.936100 | 0.130000 | 3464.42 | 23 | 23 |
| old_thin | 4.806100 | 4.806100 | 0.000000 | 0.00 | 25 | 25 |

## Best Variant

- scalar: `1.025`
- adjusted signals: `4`
- adjusted counts: `{'space_defense_budget_delayed_benchmark_trend_risk_changed_LUNR': 1, 'space_defense_budget_delayed_benchmark_trend_risk_changed_RKLB': 3, 'space_defense_budget_delayed_benchmark_trend_risk_changed_signal': 4, 'space_defense_budget_delayed_benchmark_trend_risk_eligible_LUNR': 1, 'space_defense_budget_delayed_benchmark_trend_risk_eligible_RKLB': 3, 'space_defense_budget_delayed_benchmark_trend_risk_eligible_signal': 4}`
- aggregate EV delta: `0.1849`
- aggregate PnL delta: `5851.1`
- max drawdown pct max delta: `0.0039`

## Decision

- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0549, 'mid_weak': 0.13}`
- regressed windows: `{}`

## Production Impact

```text
production_impact:
  shared_policy_changed: true
  backtester_adapter_changed: false
  run_adapter_changed: true
  replay_only: true
  parity_test_added: true
```
