# exp-20260515-031 Space VSAT same-theme satcom trend pool

## Hypothesis
VSAT has the mature satcom profile that the rejected IRDM/VSAT bundle lacked: all-positive 5d replacement evidence and positive 10d same-theme replacement value. Adding only that ticker, trend only, may preserve the useful mid-window continuation while avoiding IRDM-driven breadth noise.

## Single Changed Variable
`space_fast_5d_10d_same_theme_satcom_trend_pool_membership` on top of accepted `exp-20260515-024`.

## Gate 1 Baseline
- before experiment: `exp-20260515-024` / `space_source_diversity_peer_nonleader_trend_risk`
- aggregate before EV: `26.4644`
- aggregate before PnL: `730466.28`
- aggregate before max drawdown pct max: `0.2147`

## Gate 2 Field Check
- open position field check passed: `True`
- 5d+10d same-theme satcom gate passed: `True`
- added tickers: `['VSAT']`
- allowed strategy for added tickers: `trend_long`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.6271`
- no core filter was added; this is default-off Space candidate-scope membership.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.375200 | 8.726100 | 0.350900 | 19389.63 | 0.029800 | 18 | 19 | 0 |
| mid_weak | 16.519800 | 21.221200 | 4.701400 | 87210.80 | 0.000000 | 24 | 25 | 1 |
| old_thin | 1.569400 | 1.538800 | -0.030600 | -1229.23 | -0.002400 | 23 | 23 | 0 |

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- aggregate EV delta: `5.0217`
- aggregate PnL delta: `105371.2`
- improved windows: `{'late_strong': 0.3509, 'mid_weak': 4.7014}`
- regressed windows: `{'old_thin': -0.0306}`
- extension trades: `1`
- non-trend extension signals filtered: `2`

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
