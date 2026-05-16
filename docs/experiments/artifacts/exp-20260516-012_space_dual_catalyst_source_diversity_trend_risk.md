# exp-20260516-012 Space dual-catalyst source-diversity trend risk

## Hypothesis
Source-diverse official Space trend signals whose event profile contains both customer demand validation and government budget validation may deserve a distinct default-off allocation scalar.

## Single Changed Variable
`space_dual_catalyst_source_diversity_trend_scalar` on top of accepted `exp-20260515-044`.

## Gate 1 Baseline
- before experiment: `exp-20260515-044` / `space_source_diversity_peer_nonleader_near_perfect_trend_risk`
- aggregate before EV: `27.7373`
- aggregate before PnL: `714738.55`
- aggregate before max drawdown pct max: `0.2191`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- target event fields: `['customer_win', 'government_space_contract']`
- target tickers: `['ASTS', 'LUNR', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.453200 | 8.533600 | 0.080400 | 3558.31 | 0.005000 | 18 | 18 |
| mid_weak | 17.679200 | 18.156200 | 0.477000 | 10527.78 | 0.000100 | 23 | 23 |
| old_thin | 1.604900 | 1.604900 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.025`
- eligible signals: `6`
- adjusted signals: `6`
- adjusted counts: `{'space_dual_catalyst_source_diversity_trend_risk_changed_ASTS': 2, 'space_dual_catalyst_source_diversity_trend_risk_changed_LUNR': 1, 'space_dual_catalyst_source_diversity_trend_risk_changed_RKLB': 3, 'space_dual_catalyst_source_diversity_trend_risk_changed_signal': 6, 'space_dual_catalyst_source_diversity_trend_risk_eligible_ASTS': 2, 'space_dual_catalyst_source_diversity_trend_risk_eligible_LUNR': 1, 'space_dual_catalyst_source_diversity_trend_risk_eligible_RKLB': 3, 'space_dual_catalyst_source_diversity_trend_risk_eligible_signal': 6}`
- aggregate EV delta: `0.5574`
- aggregate PnL delta: `14086.09`
- max drawdown pct max delta: `0.005`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0804, 'mid_weak': 0.477}`
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
