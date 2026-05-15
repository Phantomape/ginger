# exp-20260515-024 Space source-diversity peer-nonleader trend risk

## Hypothesis
Source-diverse official Space `trend_long` signals may need a different default-off allocation when the ticker is still a Space peer nonleader.

## Single Changed Variable
`space_source_diversity_peer_nonleader_trend_scalar` on top of accepted `exp-20260515-021`.

## Gate 1 Baseline
- before experiment: `exp-20260515-021` / `space_defense_budget_same_theme_winner_trend_risk`
- aggregate before EV: `24.9753`
- aggregate before PnL: `665315.4`
- aggregate before max drawdown pct max: `0.1737`

## Gate 2 Field Check
- open position field check passed: `True`
- missing source-diversity profile count: `0`
- target peer state: `nonleader`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.64`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.322400 | 8.379500 | 0.057100 | 2604.86 | 0.004200 | 20 | 20 |
| mid_weak | 13.576300 | 13.726300 | 0.150000 | 4492.43 | 0.002400 | 24 | 24 |
| old_thin | 3.076600 | 3.076600 | 0.000000 | 0.00 | 0.000000 | 24 | 24 |

## Best Variant
- scalar: `1.025`
- eligible signals: `4`
- adjusted signals: `4`
- adjusted counts: `{'space_source_diversity_peer_nonleader_trend_risk_changed_ASTS': 1, 'space_source_diversity_peer_nonleader_trend_risk_changed_RKLB': 3, 'space_source_diversity_peer_nonleader_trend_risk_changed_signal': 4, 'space_source_diversity_peer_nonleader_trend_risk_eligible_ASTS': 1, 'space_source_diversity_peer_nonleader_trend_risk_eligible_RKLB': 3, 'space_source_diversity_peer_nonleader_trend_risk_eligible_signal': 4, 'space_source_diversity_peer_nonleader_trend_risk_skipped_peer_state': 2, 'space_source_diversity_peer_nonleader_trend_risk_skipped_peer_state_ASTS': 1, 'space_source_diversity_peer_nonleader_trend_risk_skipped_peer_state_LUNR': 1}`
- aggregate EV delta: `0.2071`
- aggregate PnL delta: `7097.29`
- max drawdown pct max delta: `0.0042`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0571, 'mid_weak': 0.15}`
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
