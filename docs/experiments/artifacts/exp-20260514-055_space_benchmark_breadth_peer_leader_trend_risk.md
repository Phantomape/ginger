# exp-20260514-055 Space benchmark-breadth peer-leader trend risk

## Hypothesis
Official Space `trend_long` signals with broad 10d confirmation versus cash, SPY, QQQ, UFO, and ARKX may deserve a small extra default-off allocation when the ticker leads the official Space peer basket.

## Single Changed Variable
`space_benchmark_breadth_peer_leader_trend_scalar` on top of the accepted `exp-20260514-053` Space stack.

## Gate 1 Baseline
- before experiment: `exp-20260514-053` / `space_benchmark_breadth_iwm_leader_trend_risk`
- aggregate before EV: `27.6442`
- aggregate before PnL: `688767.01`
- aggregate before max drawdown pct max: `0.1616`

## Gate 2 Field Check
- open position field check passed: `True`
- benchmark-breadth gate passed: `True`
- target peer state: `leader`
- benchmark-breadth target tickers: `['BKSY', 'LUNR', 'PL', 'RDW', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.6533`
- min survival after: `0.6533`
- no filter was added; trade count and survival should not decline except through sizing-side effects.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.850600 | 7.850600 | 0.000000 | 0.00 | 0.000000 | 20 | 20 |
| mid_weak | 14.987500 | 14.987500 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |
| old_thin | 4.806100 | 4.806100 | 0.000000 | 0.00 | 0.000000 | 25 | 25 |

## Best Variant
- scalar: `1.0`
- eligible signals: `1`
- adjusted signals: `0`
- adjusted counts: `{'space_benchmark_breadth_peer_leader_trend_risk_eligible_LUNR': 1, 'space_benchmark_breadth_peer_leader_trend_risk_eligible_signal': 1}`
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
