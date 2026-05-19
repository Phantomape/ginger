# exp-20260515-021 Space defense-budget same-theme winner trend risk

## Hypothesis
Official Space `trend_long` signals tied to defense-budget government-contract events may deserve a small extra default-off allocation only when the mature 10d event profile is positive versus cash and the same-theme basket.

## Single Changed Variable
`space_defense_budget_same_theme_winner_trend_scalar` on top of the accepted `exp-20260514-053` Space stack.

## Gate 1 Baseline
- before experiment: `exp-20260514-053` / `space_benchmark_breadth_iwm_leader_trend_risk`
- aggregate before EV: `24.6984`
- aggregate before PnL: `652524.4`
- aggregate before max drawdown pct max: `0.1703`

## Gate 2 Field Check
- open position field check passed: `True`
- defense-budget same-theme winner gate passed: `True`
- target semantic bucket: `defense_budget_theme`
- target event field: `government_space_contract`
- target tickers: `['BKSY', 'LUNR', 'RDW', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.64`
- no filter was added; trade count and survival should not decline except through sizing-side effects.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.219100 | 8.322400 | 0.103300 | 5372.59 | 0.008100 | 20 | 20 |
| mid_weak | 13.402700 | 13.576300 | 0.173600 | 7418.41 | 0.005100 | 24 | 24 |
| old_thin | 3.076600 | 3.076600 | 0.000000 | 0.00 | 0.000000 | 24 | 24 |

## Best Variant
- scalar: `1.05`
- eligible signals: `4`
- adjusted signals: `4`
- adjusted counts: `{'space_defense_budget_same_theme_winner_trend_risk_changed_LUNR': 1, 'space_defense_budget_same_theme_winner_trend_risk_changed_RKLB': 3, 'space_defense_budget_same_theme_winner_trend_risk_changed_signal': 4, 'space_defense_budget_same_theme_winner_trend_risk_eligible_LUNR': 1, 'space_defense_budget_same_theme_winner_trend_risk_eligible_RKLB': 3, 'space_defense_budget_same_theme_winner_trend_risk_eligible_signal': 4}`
- aggregate EV delta: `0.2769`
- aggregate PnL delta: `12791.0`
- max drawdown pct max delta: `0.0034`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.1033, 'mid_weak': 0.1736}`
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
