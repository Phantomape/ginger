# exp-20260515-029 Space current-stack fast-5d satcom trend pool

## Hypothesis
Forward-qualified mature satcom tickers with all-positive 5d replacement evidence may add Space trend continuation value to the current accepted stack without broad noisy ticker admission.

## Single Changed Variable
`space_fast_5d_satcom_trend_only_pool_membership` on top of accepted `exp-20260515-024`.

## Gate 1 Baseline
- before experiment: `exp-20260515-024` / `space_source_diversity_peer_nonleader_trend_risk`
- aggregate before EV: `24.514`
- aggregate before PnL: `662636.78`
- aggregate before max drawdown pct max: `0.2025`

## Gate 2 Field Check
- open position field check passed: `True`
- satcom fast-5d gate passed: `True`
- added tickers: `['IRDM', 'VSAT']`
- allowed strategy for added tickers: `trend_long`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.6032`
- no core filter was added; this is default-off Space candidate-scope membership.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.132100 | 9.013800 | 0.881700 | 28711.18 | 0.027900 | 18 | 20 | 1 |
| mid_weak | 15.316000 | 19.512100 | 4.196100 | 75840.68 | 0.000000 | 24 | 25 | 1 |
| old_thin | 1.065900 | 0.776300 | -0.289600 | -11202.31 | -0.005300 | 23 | 23 | 0 |

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- aggregate EV delta: `4.7882`
- aggregate PnL delta: `93349.55`
- improved windows: `{'late_strong': 0.8817, 'mid_weak': 4.1961}`
- regressed windows: `{'old_thin': -0.2896}`
- extension trades: `2`
- non-trend extension signals filtered: `3`

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
