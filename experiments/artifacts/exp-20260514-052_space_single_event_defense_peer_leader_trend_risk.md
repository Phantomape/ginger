# exp-20260514-052 Space single-event defense peer-leader trend risk

## Hypothesis
Single-event defense-only official Space `trend_long` signals may deserve an extra default-off risk top-up when the ticker also leads the official Space peer basket.

## Single Changed Variable
`space_single_event_defense_peer_leader_trend_risk_scalar` on top of the accepted `exp-20260514-051` Space stack.

## Gate 1 Baseline
- before experiment: `exp-20260514-051` / `space_defense_budget_delayed_benchmark_trend_risk`
- aggregate before EV: `27.5836`
- aggregate before PnL: `685729.18`
- aggregate before max drawdown pct max: `0.1596`

## Gate 2 Field Check
- open position field check passed: `True`
- single-event defense gate passed: `True`
- target tickers: `['BKSY', 'PL', 'RDW']`
- target peer state: `leader`

## Gate 3 Survival Audit
- min survival before: `0.6533`
- min survival after: `0.6533`
- no filter was added; trade count and survival should not decline except through sizing-side effects.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.841400 | 7.841400 | 0.000000 | 0.00 | 0.000000 | 20 | 20 |
| mid_weak | 14.936100 | 14.936100 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |
| old_thin | 4.806100 | 5.039300 | 0.233200 | 5696.96 | -0.001000 | 25 | 25 |

## Best Variant
- scalar: `1.05`
- eligible signals: `6`
- adjusted signals: `6`
- adjusted counts: `{'space_single_event_defense_peer_leader_trend_risk_changed_BKSY': 1, 'space_single_event_defense_peer_leader_trend_risk_changed_PL': 3, 'space_single_event_defense_peer_leader_trend_risk_changed_RDW': 2, 'space_single_event_defense_peer_leader_trend_risk_changed_signal': 6, 'space_single_event_defense_peer_leader_trend_risk_eligible_BKSY': 1, 'space_single_event_defense_peer_leader_trend_risk_eligible_PL': 3, 'space_single_event_defense_peer_leader_trend_risk_eligible_RDW': 2, 'space_single_event_defense_peer_leader_trend_risk_eligible_signal': 6}`
- aggregate EV delta: `0.2332`
- aggregate PnL delta: `5696.96`
- max drawdown pct max delta: `0.0`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'old_thin': 0.2332}`
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
