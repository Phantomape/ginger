# exp-20260516-005 Space VSAT smallcap-leader trend pool

## Hypothesis
VSAT's mature satcom profile may be useful only in a favorable small-cap appetite regime: admit VSAT into the official Space pool only for trend_long signals where space_iwm_relative_state is smallcap_leader.

## Single Changed Variable
`space_vsat_smallcap_leader_trend_pool_membership` on top of accepted `exp-20260515-044`.

## Gate 1 Baseline
- before experiment: `exp-20260515-044` / `space_source_diversity_peer_nonleader_near_perfect_trend_risk`
- aggregate before EV: `26.5438`
- aggregate before PnL: `733923.08`
- aggregate before max drawdown pct max: `0.2196`

## Gate 2 Field Check
- open position field check passed: `True`
- 5d+10d same-theme satcom gate passed: `True`
- added tickers: `['VSAT']`
- required state: `smallcap_leader`
- kept extension signals: `1`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.6203`
- this is a candidate-scope membership test, not a new core filter.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.444200 | 8.793700 | 0.349500 | 20330.73 | 0.030500 | 18 | 19 | 0 |
| mid_weak | 16.530200 | 16.545100 | 0.014900 | 378.47 | 0.000000 | 24 | 24 | 0 |
| old_thin | 1.569400 | 1.538800 | -0.030600 | -1229.23 | -0.002400 | 23 | 23 | 0 |

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- aggregate EV delta: `0.3338`
- aggregate PnL delta: `19479.97`
- max drawdown pct max delta: `0.0305`
- improved windows: `{'late_strong': 0.3495, 'mid_weak': 0.0149}`
- regressed windows: `{'old_thin': -0.0306}`
- extension filter counts: `{'extension_signal_seen': 6, 'filtered_VSAT': 5, 'filtered_extension_non_trend_signal': 2, 'filtered_extension_not_smallcap_leader_signal': 3, 'filtered_extension_signal': 5, 'kept_VSAT': 1, 'kept_extension_signal': 1, 'seen_VSAT': 6, 'seen_iwm_state_smallcap_laggard': 4, 'seen_iwm_state_smallcap_leader': 2, 'seen_strategy_breakout_long': 2, 'seen_strategy_trend_long': 4}`

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
