# exp-20260511-026 Space satcom breadth low-risk

- decision: rejected_satcom_breadth_low_risk_extension
- hypothesis: A bounded, low-risk mature-satcom extension (IRDM/VSAT/SATS) may add replacement value to the accepted default-off Space sleeve without repeating broad static Space pool drawdown damage.
- changed_variable: space_satcom_breadth_risk_scalar
- best_satcom_breadth_risk_scalar: 0.75
- expected_value_score_delta_vs_before: 0.9043
- rejection_reason: No IRDM/VSAT/SATS risk scalar cleared the pre-registered three-window gate versus the accepted exp-20260511-021 Space forward stack.

## Aggregate

- core: {'expected_value_score_sum': 6.2882, 'total_pnl_sum': 184444.42, 'trade_count_sum': 62, 'min_survival_rate': 0.7925, 'max_drawdown_pct_max': 0.0941}
- before_exp021_stack: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_best: {'expected_value_score_sum': 9.395, 'total_pnl_sum': 242349.79, 'trade_count_sum': 83, 'min_survival_rate': 0.8462, 'max_drawdown_pct_max': 0.1013}
- gate: {'passed': False, 'aggregate_delta_vs_before': {'expected_value_score_sum': 0.9043, 'total_pnl_sum': 15212.71, 'trade_count_sum': 12, 'min_survival_rate': 0.0392, 'max_drawdown_pct_max': 0.0001}, 'aggregate_delta_vs_core': {'expected_value_score_sum': 3.1068, 'total_pnl_sum': 57905.37, 'trade_count_sum': 21, 'min_survival_rate': 0.0537, 'max_drawdown_pct_max': 0.0072}, 'windows_ev_improved_vs_before': 1, 'windows_ev_regressed_vs_before': 2, 'windows_ev_improved_vs_core': 3, 'max_drawdown_worsening_vs_core': 0.0198, 'max_drawdown_change_vs_before': 0.0121}
- satcom_trade_attribution: {'trade_count': 11, 'total_pnl': 22828.59, 'wins': 4, 'losses': 7, 'win_rate': 0.3636, 'single_ticker_positive_share': 0.7388, 'by_ticker': {'IRDM': {'trade_count': 3, 'wins': 1, 'losses': 2, 'pnl': 1363.35}, 'SATS': {'trade_count': 5, 'wins': 2, 'losses': 3, 'pnl': 16865.57}, 'VSAT': {'trade_count': 3, 'wins': 1, 'losses': 2, 'pnl': 4599.67}}}

## Window Deltas Vs Before

- late_strong: {'expected_value_score': -0.2927, 'sharpe_daily': -0.28, 'total_pnl': -128.36, 'strategy_total_return_pct': -0.0013, 'max_drawdown_pct': 0.0058, 'win_rate': -0.1081, 'trade_count': 5, 'signals_generated': 8, 'signals_survived': 9, 'survival_rate': 0.0392, 'worst_trade_pct': -0.0009, 'max_consecutive_losses': 1, 'tail_loss_share': -0.0941}
- mid_weak: {'expected_value_score': 1.3637, 'sharpe_daily': 0.54, 'total_pnl': 21365.03, 'strategy_total_return_pct': 0.2136, 'max_drawdown_pct': 0.0121, 'win_rate': -0.0213, 'trade_count': 3, 'signals_generated': 10, 'signals_survived': 10, 'survival_rate': 0.0209, 'worst_trade_pct': 0.0, 'max_consecutive_losses': -2, 'tail_loss_share': 0.0224}
- old_thin: {'expected_value_score': -0.1667, 'sharpe_daily': -0.19, 'total_pnl': -6023.96, 'strategy_total_return_pct': -0.0603, 'max_drawdown_pct': 0.0001, 'win_rate': -0.0654, 'trade_count': 4, 'signals_generated': 8, 'signals_survived': 7, 'survival_rate': -0.003, 'worst_trade_pct': -0.0335, 'max_consecutive_losses': 2, 'tail_loss_share': -0.1415}

## Production Impact

{"backtester_adapter_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
