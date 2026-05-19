# exp-20260514-053 Space benchmark-breadth IWM-leader trend risk

## Hypothesis
Official Space `trend_long` signals with broad 10d confirmation versus cash, SPY, QQQ, UFO, and ARKX may deserve a small extra default-off allocation when IWM 20d momentum leads SPY.

## Single Changed Variable
`space_benchmark_breadth_iwm_leader_trend_scalar` on top of the accepted `exp-20260514-051` Space stack.

## Gate 1 Baseline
- before experiment: `exp-20260514-051` / `space_defense_budget_delayed_benchmark_trend_risk`
- aggregate before EV: `27.5836`
- aggregate before PnL: `685729.18`
- aggregate before max drawdown pct max: `0.1596`

## Gate 2 Field Check
- open position field check passed: `True`
- benchmark-breadth gate passed: `True`
- target IWM state: `smallcap_leader`
- benchmark-breadth target tickers: `['BKSY', 'LUNR', 'PL', 'RDW', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.6533`
- min survival after: `0.6533`
- no filter was added; trade count and survival should not decline except through sizing-side effects.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.841400 | 7.850600 | 0.009200 | 1250.44 | 0.002000 | 20 | 20 |
| mid_weak | 14.936100 | 14.987500 | 0.051400 | 1787.39 | 0.000000 | 23 | 23 |
| old_thin | 4.806100 | 4.806100 | 0.000000 | 0.00 | 0.000000 | 25 | 25 |

## Best Variant
- scalar: `1.0125`
- eligible signals: `4`
- adjusted signals: `4`
- adjusted counts: `{'space_benchmark_breadth_iwm_leader_trend_risk_changed_LUNR': 1, 'space_benchmark_breadth_iwm_leader_trend_risk_changed_RKLB': 3, 'space_benchmark_breadth_iwm_leader_trend_risk_changed_signal': 4, 'space_benchmark_breadth_iwm_leader_trend_risk_eligible_LUNR': 1, 'space_benchmark_breadth_iwm_leader_trend_risk_eligible_RKLB': 3, 'space_benchmark_breadth_iwm_leader_trend_risk_eligible_signal': 4}`
- aggregate EV delta: `0.0606`
- aggregate PnL delta: `3037.83`
- max drawdown pct max delta: `0.002`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0092, 'mid_weak': 0.0514}`
- regressed windows: `{}`

## Production Impact
```text
production_impact:
  shared_policy_changed: true
  backtester_adapter_changed: false
  run_adapter_changed: true
  replay_only: true
  parity_test_added: true
  live_slots: 0
```
