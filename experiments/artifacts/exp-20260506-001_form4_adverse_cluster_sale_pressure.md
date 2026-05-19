# exp-20260506-001 Form 4 adverse cluster sale-pressure

Status: rejected

## Hypothesis

Large non-10b5, non-option Form 4 sale clusters that are followed by an adverse SPY-relative reaction may identify core long entries with poorer forward replacement value; reducing their risk to 0.25x should improve multi-window EV without adding noisy tickers.

## Gate 4

- passed: False
- aggregate_ev_delta_sum: -0.0303
- aggregate_ev_delta_pct: -0.005851
- aggregate_pnl_delta_sum: -949.26
- touched_trades_after: 1
- touched_trades_pnl_after: 158.33

## Fixed Windows

### late_strong

- before: {'expected_value_score': 3.4191, 'sharpe_daily': 4.35, 'total_pnl': 78600.33, 'total_return_pct': 0.786, 'max_drawdown_pct': 0.0541, 'win_rate': 0.7895, 'trade_count': 19, 'survival_rate': 0.8039, 'signals_generated': 51, 'signals_survived': 41, 'converged': True}
- after: {'expected_value_score': 3.4191, 'sharpe_daily': 4.35, 'total_pnl': 78600.33, 'total_return_pct': 0.786, 'max_drawdown_pct': 0.0541, 'win_rate': 0.7895, 'trade_count': 19, 'survival_rate': 0.8039, 'signals_generated': 51, 'signals_survived': 41, 'converged': True}
- delta: {'expected_value_score': 0.0, 'sharpe_daily': 0.0, 'total_pnl': 0.0, 'total_return_pct': 0.0, 'max_drawdown_pct': 0.0, 'win_rate': 0.0, 'trade_count': 0.0, 'survival_rate': 0.0, 'signals_generated': 0.0, 'signals_survived': 0.0}
- source_coverage: {'raw_cluster_events': 86, 'snapshot_ticker_missing': 11, 'reaction_window_missing': 0, 'reaction_computed': 75, 'adverse_cluster_events': 14, 'adverse_cluster_tickers': 9}
- touched_trade_attribution_after: {'trade_count': 0, 'wins': 0, 'losses': 0, 'total_pnl_usd': 0.0, 'trades': []}

### mid_weak

- before: {'expected_value_score': 1.4415, 'sharpe_daily': 2.62, 'total_pnl': 55015.08, 'total_return_pct': 0.5502, 'max_drawdown_pct': 0.0879, 'win_rate': 0.5238, 'trade_count': 21, 'survival_rate': 0.7925, 'signals_generated': 53, 'signals_survived': 42, 'converged': True}
- after: {'expected_value_score': 1.4112, 'sharpe_daily': 2.61, 'total_pnl': 54065.82, 'total_return_pct': 0.5407, 'max_drawdown_pct': 0.0879, 'win_rate': 0.5238, 'trade_count': 21, 'survival_rate': 0.7925, 'signals_generated': 53, 'signals_survived': 42, 'converged': True}
- delta: {'expected_value_score': -0.0303, 'sharpe_daily': -0.01, 'total_pnl': -949.26, 'total_return_pct': -0.0095, 'max_drawdown_pct': 0.0, 'win_rate': 0.0, 'trade_count': 0.0, 'survival_rate': 0.0, 'signals_generated': 0.0, 'signals_survived': 0.0}
- source_coverage: {'raw_cluster_events': 86, 'snapshot_ticker_missing': 17, 'reaction_window_missing': 28, 'reaction_computed': 41, 'adverse_cluster_events': 8, 'adverse_cluster_tickers': 6}
- touched_trade_attribution_after: {'trade_count': 1, 'wins': 1, 'losses': 0, 'total_pnl_usd': 158.33, 'trades': [{'ticker': 'APP', 'strategy': 'trend_long', 'entry_date': '2025-09-09', 'exit_date': '2025-09-29', 'pnl': 158.33, 'exit_reason': 'target', 'sizing_multipliers': {'trend_tech_near_high_risk_multiplier_applied': 0.25, 'form4_adverse_cluster_sale_pressure_risk_multiplier_applied': 0.25}}]}

### old_thin

- before: {'expected_value_score': 0.3179, 'sharpe_daily': 1.29, 'total_pnl': 24642.07, 'total_return_pct': 0.2464, 'max_drawdown_pct': 0.0805, 'win_rate': 0.4091, 'trade_count': 22, 'survival_rate': 0.9167, 'signals_generated': 60, 'signals_survived': 55, 'converged': True}
- after: {'expected_value_score': 0.3179, 'sharpe_daily': 1.29, 'total_pnl': 24642.07, 'total_return_pct': 0.2464, 'max_drawdown_pct': 0.0805, 'win_rate': 0.4091, 'trade_count': 22, 'survival_rate': 0.9167, 'signals_generated': 60, 'signals_survived': 55, 'converged': True}
- delta: {'expected_value_score': 0.0, 'sharpe_daily': 0.0, 'total_pnl': 0.0, 'total_return_pct': 0.0, 'max_drawdown_pct': 0.0, 'win_rate': 0.0, 'trade_count': 0.0, 'survival_rate': 0.0, 'signals_generated': 0.0, 'signals_survived': 0.0}
- source_coverage: {'raw_cluster_events': 86, 'snapshot_ticker_missing': 17, 'reaction_window_missing': 53, 'reaction_computed': 16, 'adverse_cluster_events': 4, 'adverse_cluster_tickers': 3}
- touched_trade_attribution_after: {'trade_count': 0, 'wins': 0, 'losses': 0, 'total_pnl_usd': 0.0, 'trades': []}

## Rejection Reason

Adverse Form 4 sale-cluster de-risking did not clear three-window Gate 4. The discriminator either did not touch enough core winners and losers to matter, or it reduced replacement-value quality under the current core stack.

## Production Parity

{'shared_policy_changed': False, 'backtester_adapter_changed': True, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'promotion_requirement': 'If this shadow result is promoted later, the Form 4 event feature and sizing multiplier must be implemented in shared production/backtest policy and exposed in run.py outputs before enabling.'}
