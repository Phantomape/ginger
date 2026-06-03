# exp-20260603-026 accepted consensus core-overlap replacement value

- Trial family: `accepted_free_data_cross_source_consensus_displacement_value`
- Changed variable: `accepted_consensus_same_day_core_overlap_replacement_value_v1`
- Decision: `rejected_positive_vs_core_but_worse_than_current_accepted_consensus`
- Aggregate EV delta vs core: +1.1991
- Aggregate PnL delta vs core: $+20,435.79
- Aggregate EV delta vs accepted comparator: -0.1067
- Aggregate PnL delta vs accepted comparator: $-2,961.97
- No-core target trades: 38
- Filtered same-day core-overlap trades: 9
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | No-core trades | Overlap trades | EV before | EV after | EV delta | Accepted EV | Delta vs accepted | PnL delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8 | 1 | 5.1628 | 5.7720 | +0.6092 | 5.8860 | -0.1140 | $+5,993.92 |
| mid_weak | 19 | 3 | 2.1402 | 2.5321 | +0.3919 | 2.4133 | +0.1188 | $+6,862.98 |
| old_thin | 11 | 5 | 0.5911 | 0.7891 | +0.1980 | 0.9006 | -0.1115 | $+7,578.89 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: True
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: True
- `all_windows_pnl_improved`: True
- `target_trade_count_passed`: True
- `target_window_count_passed`: True
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: True
- `beats_current_accepted_consensus_ev`: False
- `beats_current_accepted_consensus_pnl`: False
- `all_windows_beat_current_accepted_consensus_ev`: False
- `all_windows_beat_current_accepted_consensus_pnl`: False

## Interpretation

The no-core-overlap consensus slice is positive versus the core baseline, but it removes profitable accepted-consensus rows and does not beat the current accepted comparator. Do not retain it.

The overlap context is derived from the same before-result core trades used for the replay, keyed by paper `entry_date`. It is replay-only in this experiment and does not change live orders.

