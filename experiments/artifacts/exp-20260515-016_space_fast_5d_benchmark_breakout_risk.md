# exp-20260515-016 Space fast-5d benchmark breakout risk

## Hypothesis
Official Space `breakout_long` signals with mature all-positive 5d confirmation versus cash, same-theme replacement, SPY, QQQ, UFO, and ARKX may be mis-sized by the accepted stack.

## Single Changed Variable
`space_fast_5d_benchmark_breakout_scalar` on top of the accepted `exp-20260514-053` Space stack.

## Gate 1 Baseline
- before experiment: `exp-20260514-053` / `space_benchmark_breadth_iwm_leader_trend_risk`
- aggregate before EV: `28.1981`
- aggregate before PnL: `701204.54`
- aggregate before max drawdown pct max: `0.1616`

## Gate 2 Field Check
- open position field check passed: `True`
- fast 5d benchmark gate passed: `True`
- target tickers: `['BKSY', 'PL']`
- target profile rows: `2`
- target strategy: `breakout_long`

## Gate 3 Survival Audit
- min survival before: `0.6533`
- min survival after: `0.6761`
- no entry filter was added; only sizing changes.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.161100 | 8.161100 | 0.000000 | 0.00 | 0.000000 | 20 | 20 | 1 |
| mid_weak | 15.165500 | 16.054800 | 0.889300 | 6272.37 | -0.014100 | 23 | 22 | 1 |
| old_thin | 4.871500 | 4.871500 | 0.000000 | 0.00 | 0.000000 | 25 | 25 | 1 |

## Best Variant
- scalar: `0.0`
- eligible signals: `3`
- adjusted signals: `3`
- adjusted counts: `{'space_fast_5d_benchmark_breakout_risk_changed_PL': 3, 'space_fast_5d_benchmark_breakout_risk_changed_signal': 3, 'space_fast_5d_benchmark_breakout_risk_eligible_PL': 3, 'space_fast_5d_benchmark_breakout_risk_eligible_signal': 3}`
- aggregate EV delta: `0.8893`
- aggregate PnL delta: `6272.37`
- max drawdown pct max delta: `0.0`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'mid_weak': 0.8893}`
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
