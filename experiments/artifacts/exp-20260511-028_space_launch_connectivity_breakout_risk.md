# exp-20260511-028 Space launch/connectivity breakout risk

- decision: rejected_launch_connectivity_breakout_risk_haircut
- hypothesis: risk allocation: RKLB/ASTS launch/connectivity breakout_long entries may have a weaker payoff distribution than their trend_long entries, so they should receive a separate risk scalar inside the accepted Space official-catalyst stack.
- changed_variable: space_launch_connectivity_breakout_risk_scalar
- before_state: exp-20260511-021 accepted Space stack
- best_launch_connectivity_breakout_scalar: 0.25
- expected_value_score_delta_vs_before: 0.2184
- rejection_reason: No tested RKLB/ASTS breakout_long scalar cleared the pre-registered three-window gate versus the accepted exp-20260511-021 Space stack.

## Sweep

| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows |
|---:|---|---:|---:|---:|---:|
| 0.25 | fail | +0.2184 | -44.75 | +0.0201 | 1/3 |
| 0.5 | fail | +0.1286 | -386.28 | +0.0189 | 1/3 |
| 0.75 | fail | +0.0667 | -150.62 | +0.0178 | 1/3 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Launch adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.7471 | 4.7471 | +0.0000 | +0.5131 | 102533.13 | 102533.13 | +0.00 | 1 |
| mid_weak | 3.0517 | 3.3404 | +0.2887 | +1.6715 | 79675.53 | 83931.95 | +4256.42 | 5 |
| old_thin | 0.6919 | 0.6216 | -0.0703 | +0.2363 | 44928.42 | 40627.25 | -4301.17 | 3 |

## Aggregate

- core: {'expected_value_score_sum': 6.2882, 'total_pnl_sum': 184444.42, 'trade_count_sum': 62, 'min_survival_rate': 0.7925, 'max_drawdown_pct_max': 0.0941}
- before_exp021_stack: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_best: {'expected_value_score_sum': 8.7091, 'total_pnl_sum': 227092.33, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1016}
- gate: {'passed': False, 'aggregate_delta_vs_before': {'expected_value_score_sum': 0.2184, 'total_pnl_sum': -44.75, 'trade_count_sum': 0, 'min_survival_rate': 0.0, 'max_drawdown_pct_max': 0.0004}, 'aggregate_delta_vs_core': {'expected_value_score_sum': 2.4209, 'total_pnl_sum': 42647.91, 'trade_count_sum': 9, 'min_survival_rate': 0.0145, 'max_drawdown_pct_max': 0.0075}, 'windows_ev_improved_vs_before': 1, 'windows_ev_regressed_vs_before': 1, 'windows_ev_improved_vs_core': 3, 'max_drawdown_worsening_vs_core': 0.0201, 'max_drawdown_change_vs_before': 0.0004}
- launch_breakout_trade_attribution: {'trade_count': 7, 'total_pnl': 30087.02, 'wins': 5, 'losses': 2, 'win_rate': 0.7143, 'single_ticker_positive_share': 0.5132, 'by_ticker': {'ASTS': {'trade_count': 3, 'wins': 2, 'losses': 1, 'pnl': 15442.08}, 'RKLB': {'trade_count': 4, 'wins': 3, 'losses': 1, 'pnl': 14644.94}}}

## Production Impact

{"backtester_adapter_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}

## Interpretation

The RKLB/ASTS trend top-up remains the supported launch/connectivity refinement. Do not add a separate breakout haircut for RKLB/ASTS on this frozen replay sample.
