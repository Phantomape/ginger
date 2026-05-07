# exp-20260505-010 Form 4 sale-pressure de-risk

Status: rejected

## Hypothesis

Recent large, non-10b5-1, non-option-exercise Form 4 insider sale pressure may identify lower-quality long entries; reducing risk for those otherwise valid signals should improve EV without adding noisy tickers.

## Gate 4

- passed: False
- best_variant: sale_pressure_0_25x
- aggregate_ev_delta_sum: -0.1203
- aggregate_ev_delta_pct: -0.023231
- aggregate_pnl_delta_sum: -8321.39
- touched_candidates: None (entry_audit does not retain experiment-only form4_sale_pressure annotations; use sale_pressure_trades_after for touched executed sample.)
- touched_trades_after: 6

## Fixed Windows

### late_strong

- before: {'expected_value_score': 3.4191, 'sharpe_daily': 4.35, 'total_pnl': 78600.33, 'total_return_pct': 0.786, 'max_drawdown_pct': 0.0541, 'win_rate': 0.7895, 'trade_count': 19, 'survival_rate': 0.8039, 'signals_generated': 51, 'signals_survived': 41, 'converged': True}
- after: {'expected_value_score': 3.3116, 'sharpe_daily': 4.7, 'total_pnl': 70458.91, 'total_return_pct': 0.7046, 'max_drawdown_pct': 0.0498, 'win_rate': 0.7895, 'trade_count': 19, 'survival_rate': 0.8039, 'signals_generated': 51, 'signals_survived': 41, 'converged': True}
- delta: {'expected_value_score': -0.1075, 'sharpe_daily': 0.35, 'total_pnl': -8141.42, 'total_return_pct': -0.0814, 'max_drawdown_pct': -0.0043, 'win_rate': 0.0, 'trade_count': 0.0, 'survival_rate': 0.0, 'signals_generated': 0.0, 'signals_survived': 0.0}

### mid_weak

- before: {'expected_value_score': 1.4415, 'sharpe_daily': 2.62, 'total_pnl': 55015.08, 'total_return_pct': 0.5502, 'max_drawdown_pct': 0.0879, 'win_rate': 0.5238, 'trade_count': 21, 'survival_rate': 0.7925, 'signals_generated': 53, 'signals_survived': 42, 'converged': True}
- after: {'expected_value_score': 1.4112, 'sharpe_daily': 2.61, 'total_pnl': 54065.82, 'total_return_pct': 0.5407, 'max_drawdown_pct': 0.0879, 'win_rate': 0.5238, 'trade_count': 21, 'survival_rate': 0.7925, 'signals_generated': 53, 'signals_survived': 42, 'converged': True}
- delta: {'expected_value_score': -0.0303, 'sharpe_daily': -0.01, 'total_pnl': -949.26, 'total_return_pct': -0.0095, 'max_drawdown_pct': 0.0, 'win_rate': 0.0, 'trade_count': 0.0, 'survival_rate': 0.0, 'signals_generated': 0.0, 'signals_survived': 0.0}

### old_thin

- before: {'expected_value_score': 0.3179, 'sharpe_daily': 1.29, 'total_pnl': 24642.07, 'total_return_pct': 0.2464, 'max_drawdown_pct': 0.0805, 'win_rate': 0.4091, 'trade_count': 22, 'survival_rate': 0.9167, 'signals_generated': 60, 'signals_survived': 55, 'converged': True}
- after: {'expected_value_score': 0.3354, 'sharpe_daily': 1.32, 'total_pnl': 25411.36, 'total_return_pct': 0.2541, 'max_drawdown_pct': 0.0751, 'win_rate': 0.4091, 'trade_count': 22, 'survival_rate': 0.9167, 'signals_generated': 60, 'signals_survived': 55, 'converged': True}
- delta: {'expected_value_score': 0.0175, 'sharpe_daily': 0.03, 'total_pnl': 769.29, 'total_return_pct': 0.0077, 'max_drawdown_pct': -0.0054, 'win_rate': 0.0, 'trade_count': 0.0, 'survival_rate': 0.0, 'signals_generated': 0.0, 'signals_survived': 0.0}

## Rejection Reason

Form 4 sale-pressure de-risking did not clear three-window Gate 4. Either the touched cohort was too small, or the sale-pressure signal does not improve replacement-value quality under the current core stack.
