# exp-20260515-044 Space source-diversity peer-nonleader near-perfect trend risk

## Hypothesis
Source-diverse official Space `trend_long` signals may need a different default-off allocation when the ticker is still a Space peer nonleader and TQS is near-perfect but not perfect.

## Single Changed Variable
`space_source_diversity_peer_nonleader_near_perfect_trend_scalar` on top of accepted `exp-20260515-024`.

## Gate 1 Baseline
- before experiment: `exp-20260515-024` / `space_source_diversity_peer_nonleader_trend_risk`
- aggregate before EV: `26.4644`
- aggregate before PnL: `730466.28`
- aggregate before max drawdown pct max: `0.2147`

## Gate 2 Field Check
- open position field check passed: `True`
- target peer state: `nonleader`
- target TQS: `0.95 <= TQS < 1.0`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.64`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.375200 | 8.444200 | 0.069000 | 3198.10 | 0.004900 | 18 | 18 |
| mid_weak | 16.519800 | 16.530200 | 0.010400 | 258.70 | -0.000100 | 24 | 24 |
| old_thin | 1.569400 | 1.569400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.025`
- eligible signals: `3`
- adjusted signals: `3`
- adjusted counts: `{'space_source_diversity_peer_nonleader_near_perfect_trend_risk_changed_ASTS': 1, 'space_source_diversity_peer_nonleader_near_perfect_trend_risk_changed_RKLB': 2, 'space_source_diversity_peer_nonleader_near_perfect_trend_risk_changed_signal': 3, 'space_source_diversity_peer_nonleader_near_perfect_trend_risk_eligible_ASTS': 1, 'space_source_diversity_peer_nonleader_near_perfect_trend_risk_eligible_RKLB': 2, 'space_source_diversity_peer_nonleader_near_perfect_trend_risk_eligible_signal': 3}`
- aggregate EV delta: `0.0794`
- aggregate PnL delta: `3456.8`
- max drawdown pct max delta: `0.0049`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.069, 'mid_weak': 0.0104}`
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
