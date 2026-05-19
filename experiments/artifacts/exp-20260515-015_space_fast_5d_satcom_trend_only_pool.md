# exp-20260515-015 Space fast-5d satcom trend-only pool

## Hypothesis
Forward-qualified mature satcom extension tickers may add Space replacement value only as trend continuation; allowing their breakout signals imports drawdown noise.

## Single Changed Variable
`space_fast_5d_satcom_trend_only_pool_membership`: add only mature fast-5d satcom tickers, and admit them only for `trend_long` signals on top of accepted `exp-20260514-053`.

## Gate 1 Baseline
- before experiment: `exp-20260514-053` / `space_benchmark_breadth_iwm_leader_trend_risk`
- aggregate before EV: `28.1981`
- aggregate before PnL: `701204.54`
- aggregate before max drawdown pct max: `0.1616`

## Gate 2 Field Check
- open position field check passed: `True`
- satcom fast-5d gate passed: `True`
- added tickers: `['IRDM', 'VSAT']`
- allowed strategy for added tickers: `trend_long`

## Gate 3 Survival Audit
- min survival before: `0.6533`
- min survival after: `0.6508`
- no core filter was added; this is default-off Space candidate-scope membership.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.161100 | 8.986300 | 0.825200 | 24394.36 | 0.023900 | 20 | 22 | 1 |
| mid_weak | 15.165500 | 18.771400 | 3.605900 | 57644.70 | -0.000400 | 23 | 24 | 1 |
| old_thin | 4.871500 | 4.596300 | -0.275200 | -5575.94 | 0.000900 | 25 | 25 | 0 |

## Trend-Only Filter Touches
- filtered non-trend extension signals: `3`
- filtered by window: `{'unknown': {'count': 3, 'tickers': {'IRDM': 1, 'VSAT': 2}, 'strategies': {'breakout_long': 3}}}`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- aggregate EV delta: `4.1559`
- aggregate PnL delta: `76463.12`
- improved windows: `{'late_strong': 0.8252, 'mid_weak': 3.6059}`
- regressed windows: `{'old_thin': -0.2752}`
- extension trades: `2`

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
