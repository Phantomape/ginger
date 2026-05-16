# exp-20260516-010 Space forward-cash satcom fallback pool

## Hypothesis
IRDM and VSAT have the newest defense-budget satellite-connectivity forward rows with positive 5d and 10d cash PnL outside the base official Space pool; they may add alpha only as trend fallback exposure when base official Space has no same-day signal.

## Single Changed Variable
`space_forward_cash_satcom_trend_fallback_pool_membership` on top of accepted `exp-20260515-044`.

## Gate 1 Baseline
- before experiment: `exp-20260515-044` / `space_source_diversity_peer_nonleader_near_perfect_trend_risk`
- aggregate before EV: `27.7373`
- aggregate before PnL: `714738.55`
- aggregate before max drawdown pct max: `0.2191`

## Gate 2 Field Check
- open position field check passed: `True`
- forward-cash satcom gate passed: `True`
- added tickers: `['IRDM', 'VSAT']`
- forward rows: `{'IRDM': {'asof_date': '2026-05-15', 'ticker': 'IRDM', 'event_id': 'golden_dome_sbi_awards_20260424', 'event_date': '2026-04-24', 'closed_decision': True, 'outcome_status': 'partially_mature', '5d_cash_relative_pnl': 665.77, '10d_cash_relative_pnl': 1537.43, '10d_same_theme_replacement_value': -390.33, '10d_spy_relative_value': 1200.03, '10d_ufo_relative_value': 419.74}, 'VSAT': {'asof_date': '2026-05-15', 'ticker': 'VSAT', 'event_id': 'golden_dome_sbi_awards_20260424', 'event_date': '2026-04-24', 'closed_decision': True, 'outcome_status': 'partially_mature', '5d_cash_relative_pnl': 879.65, '10d_cash_relative_pnl': 2456.53, '10d_same_theme_replacement_value': 528.77, '10d_spy_relative_value': 2119.13, '10d_ufo_relative_value': 1338.84}}`
- fallback kept extension signals: `5`
- official-same-day extension signals filtered: `0`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6032`
- this is a candidate-scope membership test, not a new core filter.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.453200 | 9.339300 | 0.886100 | 30513.02 | 0.030400 | 18 | 20 | 1 |
| mid_weak | 17.679200 | 22.164300 | 4.485100 | 74394.17 | -0.004800 | 23 | 24 | 1 |
| old_thin | 1.604900 | 0.830500 | -0.774400 | -36427.77 | -0.025000 | 23 | 23 | 0 |

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- aggregate EV delta: `4.5968`
- aggregate PnL delta: `68479.42`
- max drawdown pct max delta: `0.0304`
- improved windows: `{'late_strong': 0.8861, 'mid_weak': 4.4851}`
- regressed windows: `{'old_thin': -0.7744}`
- extension trades: `2`
- fallback filter counts: `{'filtered_IRDM': 1, 'filtered_VSAT': 2, 'filtered_breakout_long': 3, 'filtered_extension_non_trend_signal': 3, 'filtered_extension_signal': 3, 'kept_IRDM': 1, 'kept_VSAT': 4, 'kept_extension_signal': 5}`

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
