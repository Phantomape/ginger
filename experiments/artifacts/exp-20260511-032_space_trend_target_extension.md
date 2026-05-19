# exp-20260511-032 Space trend target extension

- decision: accepted_default_off_space_trend_target_extension
- changed_variable: space_official_trend_target_atr_mult
- before_state: exp-20260511-031 accepted Space stack
- best_space_trend_target_atr_mult: 5.0
- expected_value_score_delta_vs_before: 0.4081
- rejection_reason: None

## Sweep

| Target ATR | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows | Adjusted signals |
|---:|---|---:|---:|---:|---:|---:|
| 5.0 | pass | +0.4081 | +9149.60 | +0.0197 | 3/3 | 20 |
| 6.0 | fail | +0.4888 | +7113.90 | +0.0197 | 1/3 | 20 |
| 7.0 | fail | +0.9973 | +8846.72 | +0.0197 | 2/3 | 20 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.7764 | 4.8646 | +0.0882 | +0.6306 | 102943.03 | 104389.17 | +1446.14 | 4 |
| mid_weak | 3.0796 | 3.3220 | +0.2424 | +1.6531 | 79992.61 | 84531.21 | +4538.60 | 10 |
| old_thin | 0.6919 | 0.7694 | +0.0775 | +0.3841 | 44928.42 | 48093.28 | +3164.86 | 6 |

## Aggregate

- core: {'expected_value_score_sum': 6.2882, 'total_pnl_sum': 184444.42, 'trade_count_sum': 62, 'min_survival_rate': 0.7925, 'max_drawdown_pct_max': 0.0941}
- before_exp031_stack: {'expected_value_score_sum': 8.5479, 'total_pnl_sum': 227864.06, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_best: {'expected_value_score_sum': 8.956, 'total_pnl_sum': 237013.66, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- gate: {'passed': True, 'aggregate_delta_vs_before': {'expected_value_score_sum': 0.4081, 'total_pnl_sum': 9149.6, 'trade_count_sum': 0, 'min_survival_rate': 0.0, 'max_drawdown_pct_max': 0.0}, 'aggregate_delta_vs_core': {'expected_value_score_sum': 2.6678, 'total_pnl_sum': 52569.24, 'trade_count_sum': 9, 'min_survival_rate': 0.0145, 'max_drawdown_pct_max': 0.0071}, 'windows_ev_improved_vs_before': 3, 'windows_ev_regressed_vs_before': 0, 'windows_ev_improved_vs_core': 3, 'max_drawdown_worsening_vs_core': 0.0197, 'max_drawdown_change_vs_before': 0.0, 'adjusted_signal_count': 20}

## Production Impact

{"backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": true}

## Interpretation

Wider targets for official-catalyst Space trend entries improved the accepted default-off Space stack. Promotion must remain default-off metadata/helper only because live Space slots are zero.
