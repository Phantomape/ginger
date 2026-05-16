# exp-20260516-015 Space dual-catalyst IWM-leader trend risk

## Hypothesis
Accepted dual-catalyst source-diverse official Space trend signals may still be under-sized only when IWM-relative small-cap risk appetite is confirmed.

## Single Changed Variable
`space_dual_catalyst_iwm_leader_trend_scalar` on top of accepted `exp-20260516-014`.

## Gate 1 Baseline
- before experiment: `exp-20260516-014` / `space_dual_catalyst_source_diversity_trend_risk`
- aggregate before EV: `28.2947`
- aggregate before PnL: `728824.64`
- aggregate before max drawdown pct max: `0.2241`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- target IWM state: `smallcap_leader`
- target tickers: `['ASTS', 'LUNR', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.533600 | 8.546100 | 0.012500 | 1695.08 | 0.002500 | 18 | 18 |
| mid_weak | 18.156200 | 18.381400 | 0.225200 | 4975.21 | -0.000200 | 23 | 23 |
| old_thin | 1.604900 | 1.604900 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.0125`
- eligible signals: `5`
- adjusted signals: `5`
- changed tickers: `['ASTS', 'LUNR', 'RKLB']`
- changed windows: `['late_strong', 'mid_weak']`
- adjusted counts: `{'space_dual_catalyst_iwm_leader_trend_risk_changed_ASTS': 1, 'space_dual_catalyst_iwm_leader_trend_risk_changed_LUNR': 1, 'space_dual_catalyst_iwm_leader_trend_risk_changed_RKLB': 3, 'space_dual_catalyst_iwm_leader_trend_risk_changed_signal': 5, 'space_dual_catalyst_iwm_leader_trend_risk_eligible_ASTS': 1, 'space_dual_catalyst_iwm_leader_trend_risk_eligible_LUNR': 1, 'space_dual_catalyst_iwm_leader_trend_risk_eligible_RKLB': 3, 'space_dual_catalyst_iwm_leader_trend_risk_eligible_signal': 5}`
- aggregate EV delta: `0.2377`
- aggregate PnL delta: `6670.29`
- max drawdown pct max delta: `0.0025`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0125, 'mid_weak': 0.2252}`
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
