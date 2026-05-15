# exp-20260515-023 Space defense-budget early-RS60 trend risk

## Hypothesis
Accepted defense-budget same-theme winner `trend_long` signals that have not yet reached RS60 top-quintile status may deserve a small extra default-off allocation as earlier catalyst continuation.

## Single Changed Variable
`space_defense_budget_early_rs60_trend_scalar` on top of accepted `exp-20260515-021`.

## Gate 1 Baseline
- before experiment: `exp-20260515-021` / `space_defense_budget_same_theme_winner_trend_risk`
- aggregate before EV: `24.9753`
- aggregate before PnL: `665315.4`
- aggregate before max drawdown pct max: `0.1737`

## Gate 2 Field Check
- open position field check passed: `True`
- missing runtime `rs60_top_quintile_state`: `0`
- target tickers: `['BKSY', 'LUNR', 'RDW', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.64`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.322400 | 8.479700 | 0.157300 | 8106.45 | 0.012700 | 20 | 20 |
| mid_weak | 13.576300 | 13.576300 | 0.000000 | 0.00 | 0.000000 | 24 | 24 |
| old_thin | 3.076600 | 3.076600 | 0.000000 | 0.00 | 0.000000 | 24 | 24 |

## Best Variant
- scalar: `1.075`
- eligible signals: `2`
- adjusted signals: `2`
- adjusted counts: `{'space_defense_budget_early_rs60_trend_risk_changed_RKLB': 2, 'space_defense_budget_early_rs60_trend_risk_changed_signal': 2, 'space_defense_budget_early_rs60_trend_risk_eligible_RKLB': 2, 'space_defense_budget_early_rs60_trend_risk_eligible_signal': 2, 'space_defense_budget_early_rs60_trend_risk_skipped_rs60_top_quintile': 2}`
- aggregate EV delta: `0.1573`
- aggregate PnL delta: `8106.45`
- max drawdown pct max delta: `0.0127`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'late_strong': 0.1573}`
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
