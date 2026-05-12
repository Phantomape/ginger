# exp-20260511-105 Space launch/connectivity trend target

- decision: accepted_default_off_launch_connectivity_trend_target_extension
- changed_variable: space_launch_connectivity_trend_target_atr_mult
- before_state: exp-20260511-032 accepted Space stack
- best_launch_connectivity_trend_target_atr_mult: 7.0
- expected_value_score_delta_vs_before: 0.9838
- rejection_reason: None

## Sweep

| RKLB/ASTS trend target ATR | Gate | dEV vs before | dPnL vs before | EV improved windows | EV regressed windows |
|---:|---|---:|---:|---:|---:|
| 5.0 | baseline | +0.0000 | +0.00 | 0/3 | 0/3 |
| 6.0 | fail | +0.2703 | +5,073.77 | 1/3 | 1/3 |
| 7.0 | pass | +0.9838 | +16,954.81 | 2/3 | 0/3 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | Before PnL | After PnL | dPnL | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.8650 | 4.9509 | +0.0859 | 104,403.85 | 104,454.52 | +50.67 | 80.70% |
| mid_weak | 3.3220 | 4.2199 | +0.8979 | 84,533.74 | 101,437.88 | +16,904.14 | 81.69% |
| old_thin | 0.7694 | 0.7694 | +0.0000 | 48,093.28 | 48,093.28 | +0.00 | 89.19% |

## Aggregate

- core: {'expected_value_score_sum': 6.2882, 'total_pnl_sum': 184444.42, 'trade_count_sum': 62, 'min_survival_rate': 0.7925, 'max_drawdown_pct_max': 0.0941}
- before_exp032_stack: {'expected_value_score_sum': 8.9564, 'total_pnl_sum': 237030.87, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_best: {'expected_value_score_sum': 9.9402, 'total_pnl_sum': 253985.68, 'trade_count_sum': 73, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- gate: {'passed': True, 'aggregate_delta_vs_before': {'expected_value_score_sum': 0.9838, 'total_pnl_sum': 16954.81, 'trade_count_sum': 2, 'min_survival_rate': 0.0, 'max_drawdown_pct_max': 0.0}, 'windows_ev_improved_vs_before': 2, 'windows_ev_regressed_vs_before': 0}

## Production Impact

{"shared_policy_changed": true, "backtester_adapter_changed": false, "run_adapter_changed": true, "replay_only": true, "parity_test_added": true, "daily_report_metadata_changed": true, "live_slots_changed": false, "live_slots": 0}

## Interpretation

RKLB/ASTS launch/connectivity trend winners support a wider default-off target than the accepted 5 ATR Space trend target. Keep other official Space trend targets at 5 ATR, keep PL/BKSY breakout at 0.1x risk, and keep live Space slots at zero.

Artifact: `data/experiments/exp-20260511-105/space_launch_connectivity_trend_target.json`.
