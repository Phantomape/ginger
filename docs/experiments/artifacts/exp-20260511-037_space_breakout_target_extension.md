# exp-20260511-037 Space breakout target extension

- decision: rejected_space_breakout_target_extension
- changed_variable: space_official_breakout_target_atr_mult
- before_state: exp-20260511-032 accepted Space stack
- best_space_breakout_target_atr_mult: 6.0
- expected_value_score_delta_vs_before: 0.0179
- rejection_reason: No tested official-catalyst Space breakout target width cleared the three-window Gate 4 standard versus the accepted exp-20260511-032 Space stack.

## Sweep

| Target ATR | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows | Adjusted signals |
|---:|---|---:|---:|---:|---:|---:|
| 4.5 | fail | +0.0000 | +0.00 | +0.0197 | 0/3 | 17 |
| 5.0 | fail | +0.0000 | +0.00 | +0.0197 | 0/3 | 17 |
| 6.0 | fail | +0.0179 | +803.96 | +0.0197 | 1/3 | 17 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.8646 | 4.8646 | +0.0000 | +0.6306 | 104389.17 | 104389.17 | +0.00 | 3 |
| mid_weak | 3.3220 | 3.3220 | +0.0000 | +1.6531 | 84531.21 | 84531.21 | +0.00 | 8 |
| old_thin | 0.7694 | 0.7873 | +0.0179 | +0.4020 | 48093.28 | 48897.24 | +803.96 | 6 |

## Aggregate

- core: {'expected_value_score_sum': 6.2882, 'total_pnl_sum': 184444.42, 'trade_count_sum': 62, 'min_survival_rate': 0.7925, 'max_drawdown_pct_max': 0.0941}
- before_exp032_stack: {'expected_value_score_sum': 8.956, 'total_pnl_sum': 237013.66, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_best: {'expected_value_score_sum': 8.9739, 'total_pnl_sum': 237817.62, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- gate: {'passed': False, 'aggregate_delta_vs_before': {'expected_value_score_sum': 0.0179, 'total_pnl_sum': 803.96, 'trade_count_sum': 0, 'min_survival_rate': 0.0, 'max_drawdown_pct_max': 0.0}, 'aggregate_delta_vs_core': {'expected_value_score_sum': 2.6857, 'total_pnl_sum': 53373.2, 'trade_count_sum': 9, 'min_survival_rate': 0.0145, 'max_drawdown_pct_max': 0.0071}, 'windows_ev_improved_vs_before': 1, 'windows_ev_regressed_vs_before': 0, 'windows_ev_improved_vs_core': 3, 'max_drawdown_worsening_vs_core': 0.0197, 'max_drawdown_change_vs_before': 0.0, 'adjusted_signal_count': 17}

## Production Impact

{"backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}

## Interpretation

Space breakout convexity is not the next supported same-sample refinement. Keep the accepted trend target extension, PL/BKSY breakout haircut, and RKLB/ASTS trend top-up unchanged.
