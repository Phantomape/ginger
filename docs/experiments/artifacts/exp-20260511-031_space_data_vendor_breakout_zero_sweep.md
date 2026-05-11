# exp-20260511-031 Space data-vendor breakout zero sweep

- decision: accepted_default_off_data_vendor_breakout_0_1_scalar
- changed_variable: space_data_vendor_breakout_risk_scalar
- before_state: exp-20260511-021 accepted Space stack
- best_data_vendor_breakout_risk_scalar: 0.1
- expected_value_score_delta_vs_before: 0.0572
- rejection_reason: None

## Sweep

| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows | Data-vendor adjusted |
|---:|---|---:|---:|---:|---:|---:|
| 0.0 | fail | -0.7477 | -5656.09 | +0.0197 | 1/3 | 4 |
| 0.1 | pass | +0.0572 | +726.98 | +0.0197 | 2/3 | 4 |
| 0.25 | fail | +0.0000 | +0.00 | +0.0197 | 0/3 | 4 |
| 0.4 | fail | -0.0630 | -802.23 | +0.0197 | 0/3 | 4 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Data adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.7471 | 4.7764 | +0.0293 | +0.5424 | 102533.13 | 102943.03 | +409.90 | 1 |
| mid_weak | 3.0517 | 3.0796 | +0.0279 | +1.4107 | 79675.53 | 79992.61 | +317.08 | 2 |
| old_thin | 0.6919 | 0.6919 | +0.0000 | +0.3066 | 44928.42 | 44928.42 | +0.00 | 1 |

## Aggregate

- core: {'expected_value_score_sum': 6.2882, 'total_pnl_sum': 184444.42, 'trade_count_sum': 62, 'min_survival_rate': 0.7925, 'max_drawdown_pct_max': 0.0941}
- before_exp021_stack: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_best: {'expected_value_score_sum': 8.5479, 'total_pnl_sum': 227864.06, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- gate: {'passed': True, 'aggregate_delta_vs_before': {'expected_value_score_sum': 0.0572, 'total_pnl_sum': 726.98, 'trade_count_sum': 0, 'min_survival_rate': 0.0, 'max_drawdown_pct_max': 0.0}, 'aggregate_delta_vs_core': {'expected_value_score_sum': 2.2597, 'total_pnl_sum': 43419.64, 'trade_count_sum': 9, 'min_survival_rate': 0.0145, 'max_drawdown_pct_max': 0.0071}, 'windows_ev_improved_vs_before': 2, 'windows_ev_regressed_vs_before': 0, 'windows_ev_improved_vs_core': 3, 'max_drawdown_worsening_vs_core': 0.0197, 'max_drawdown_change_vs_before': 0.0, 'data_vendor_adjusted_signal_count': 4}
- data_vendor_trade_attribution: {'trade_count': 3, 'total_pnl': 7028.0, 'wins': 1, 'losses': 2, 'win_rate': 0.3333, 'single_ticker_positive_share': 1.0, 'by_ticker': {'PL': {'trade_count': 3, 'wins': 1, 'losses': 2, 'pnl': 7028.0}}}

## Production Impact

{"backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": true}

## Interpretation

A lower PL/BKSY breakout scalar improved the accepted Space stack under the three-window gate. Promote only as default-off forward metadata because Space live slots remain zero.
