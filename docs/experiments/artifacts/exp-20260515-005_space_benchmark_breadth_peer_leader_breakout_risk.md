# exp-20260515-005 Space benchmark-breadth peer-leader breakout risk

## Hypothesis
Official Space `breakout_long` signals with broad 10d confirmation versus cash, SPY, QQQ, UFO, and ARKX may need different sizing only when the ticker is also a Space peer-momentum leader.

## Single Changed Variable
`space_benchmark_breadth_peer_leader_breakout_scalar` on top of the accepted `exp-20260514-053` Space stack.

## Gate 1 Baseline
- before experiment: `exp-20260514-053` / `space_benchmark_breadth_iwm_leader_trend_risk`
- aggregate before EV: `27.6442`
- aggregate before PnL: `688767.01`
- aggregate before max drawdown pct max: `0.1616`

## Gate 2 Field Check
- open position field check passed: `True`
- benchmark-breadth gate passed: `True`
- benchmark-breadth target tickers: `['BKSY', 'LUNR', 'PL', 'RDW', 'RKLB']`
- target strategy: `breakout_long`
- target peer momentum state: `leader`

## Gate 3 Survival Audit
- min survival before: `0.6533`
- min survival after: `0.6533`
- no entry filter was added; only sizing changes.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.850600 | 7.850600 | 0.000000 | 0.00 | 0.000000 | 20 | 20 | 1 |
| mid_weak | 14.987500 | 15.709900 | 0.722400 | 8425.07 | -0.000100 | 23 | 23 | 2 |
| old_thin | 4.806100 | 4.256500 | -0.549600 | -22098.31 | -0.020400 | 25 | 25 | 4 |

## Best Variant
- scalar: `0.75`
- eligible signals: `7`
- adjusted signals: `7`
- adjusted counts: `{'space_benchmark_breadth_peer_leader_breakout_risk_changed_LUNR': 1, 'space_benchmark_breadth_peer_leader_breakout_risk_changed_PL': 1, 'space_benchmark_breadth_peer_leader_breakout_risk_changed_RKLB': 5, 'space_benchmark_breadth_peer_leader_breakout_risk_changed_signal': 7, 'space_benchmark_breadth_peer_leader_breakout_risk_eligible_LUNR': 1, 'space_benchmark_breadth_peer_leader_breakout_risk_eligible_PL': 1, 'space_benchmark_breadth_peer_leader_breakout_risk_eligible_RKLB': 5, 'space_benchmark_breadth_peer_leader_breakout_risk_eligible_signal': 7}`
- aggregate EV delta: `0.1728`
- aggregate PnL delta: `-13673.24`
- max drawdown pct max delta: `0.0`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'mid_weak': 0.7224}`
- regressed windows: `{'old_thin': -0.5496}`

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
