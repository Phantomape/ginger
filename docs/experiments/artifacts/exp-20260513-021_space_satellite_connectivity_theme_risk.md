# exp-20260513-021 space_satellite_connectivity_theme_risk

Decision: `rejected_space_satellite_connectivity_theme_risk`

Hypothesis: The accepted Space stack has shown value in production-visible catalyst quality fields. Satellite-connectivity signals may deserve a separate risk allocation because their regulatory/direct-to-device catalysts differ from launch/lunar and data/defense catalysts, without adding tickers, changing ranking, or using LLM soft-ranking.

Changed variable: `space_satellite_connectivity_theme_risk_scalar`

Best scalar: `1.25`

## Gate 4

{"adjusted_signal_count": 4, "aggregate_delta_vs_before": {"expected_value_score_sum": 1.1146, "max_drawdown_pct_max": 0.0, "min_survival_rate": 0.0, "signals_generated_sum": 0, "signals_survived_sum": 0, "total_pnl_sum": 18099.33, "trade_count_sum": 0}, "aggregate_delta_vs_core": {"expected_value_score_sum": 11.6525, "max_drawdown_pct_max": 0.0504, "min_survival_rate": -0.0883, "signals_generated_sum": 39, "signals_survived_sum": 24, "total_pnl_sum": 235621.14, "trade_count_sum": 8}, "by_window_delta_vs_before": {"late_strong": {"expected_value_score": 0.0, "max_drawdown_pct": 0.0, "sharpe_daily": 0.0, "signals_generated": 0.0, "signals_survived": 0.0, "strategy_total_return_pct": 0.0, "survival_rate": 0.0, "tail_loss_share": 0.0, "total_pnl": 0.0, "trade_count": 0.0, "win_rate": 0.0, "worst_trade_pct": 0.0}, "mid_weak": {"expected_value_score": 1.1146, "max_drawdown_pct": 0.0056, "sharpe_daily": 0.11, "signals_generated": 0.0, "signals_survived": 0.0, "strategy_total_return_pct": 0.181, "survival_rate": 0.0, "tail_loss_share": -0.0018, "total_pnl": 18099.33, "trade_count": 0.0, "win_rate": 0.0, "worst_trade_pct": 0.0}, "old_thin": {"expected_value_score": 0.0, "max_drawdown_pct": 0.0, "sharpe_daily": 0.0, "signals_generated": 0.0, "signals_survived": 0.0, "strategy_total_return_pct": 0.0, "survival_rate": 0.0, "tail_loss_share": 0.0, "total_pnl": 0.0, "trade_count": 0.0, "win_rate": 0.0, "worst_trade_pct": 0.0}}, "improved_windows": ["mid_weak"], "passed": false, "regressed_windows": []}

## Window Metrics vs Accepted exp-20260513-015 Stack

| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Trades | Max DD | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0447 | 6.0447 | +0.0000 | 131,975.34 | 131,975.34 | +0.00 | 22 | 0.0898 | 0.7931 | 0 |
| mid_weak | 9.3164 | 10.4310 | +1.1146 | 190,521.27 | 208,620.60 | +18,099.33 | 24 | 0.0528 | 0.7042 | 4 |
| old_thin | 1.5276 | 1.5276 | +0.0000 | 81,693.21 | 81,693.21 | +0.00 | 24 | 0.1474 | 0.8919 | 0 |

## Sweep Summary

[{"adjusted_signal_count": 4, "expected_value_score_delta": -3.1992, "improved_windows": [], "max_drawdown_worse": 0.0, "passed": false, "regressed_windows": ["mid_weak"], "risk_scalar": 0.5, "total_pnl_delta": -54279.13, "variant": "satellite_connectivity_theme_0_5"}, {"adjusted_signal_count": 4, "expected_value_score_delta": -2.0032, "improved_windows": [], "max_drawdown_worse": 0.0, "passed": false, "regressed_windows": ["mid_weak"], "risk_scalar": 0.75, "total_pnl_delta": -34917.07, "variant": "satellite_connectivity_theme_0_75"}, {"adjusted_signal_count": 4, "expected_value_score_delta": -0.6084, "improved_windows": [], "max_drawdown_worse": 0.0, "passed": false, "regressed_windows": ["mid_weak"], "risk_scalar": 0.9, "total_pnl_delta": -10230.99, "variant": "satellite_connectivity_theme_0_9"}, {"adjusted_signal_count": 4, "expected_value_score_delta": 0.0, "improved_windows": [], "max_drawdown_worse": 0.0, "passed": false, "regressed_windows": [], "risk_scalar": 1.0, "total_pnl_delta": 0.0, "variant": "satellite_connectivity_theme_1_0"}, {"adjusted_signal_count": 4, "expected_value_score_delta": 0.2638, "improved_windows": ["mid_weak"], "max_drawdown_worse": 0.0, "passed": false, "regressed_windows": [], "risk_scalar": 1.05, "total_pnl_delta": 4197.84, "variant": "satellite_connectivity_theme_1_05"}, {"adjusted_signal_count": 4, "expected_value_score_delta": 0.4712, "improved_windows": ["mid_weak"], "max_drawdown_worse": 0.0, "passed": false, "regressed_windows": [], "risk_scalar": 1.1, "total_pnl_delta": 7613.38, "variant": "satellite_connectivity_theme_1_1"}, {"adjusted_signal_count": 4, "expected_value_score_delta": 1.1146, "improved_windows": ["mid_weak"], "max_drawdown_worse": 0.0, "passed": false, "regressed_windows": [], "risk_scalar": 1.25, "total_pnl_delta": 18099.33, "variant": "satellite_connectivity_theme_1_25"}]

## Field Checks

{"missing_required_fields": [], "passed": true, "records": {"ASTS": {"eligible_as_of": "2026-05-10", "first_trade_allowed_as_of": null, "status": "research", "theme": "space_satellite_connectivity", "theme_segment": "satellite_connectivity"}}, "source": "data/universe_registry.json plus data/universe_events.jsonl", "target_theme_segment": "satellite_connectivity", "target_tickers": ["ASTS"]}

{"field": "space_theme_segment", "passed": true, "sample_runtime_values": [{"space_theme_segment": "launch_lunar", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_theme_segment": "launch_lunar", "strategy": "breakout_long", "ticker": "RKLB", "window": "late_strong"}, {"space_theme_segment": "launch_lunar", "strategy": "trend_long", "ticker": "RKLB", "window": "mid_weak"}, {"space_theme_segment": "launch_lunar", "strategy": "trend_long", "ticker": "RKLB", "window": "mid_weak"}, {"space_theme_segment": "launch_lunar", "strategy": "breakout_long", "ticker": "RKLB", "window": "mid_weak"}, {"space_theme_segment": "launch_lunar", "strategy": "trend_long", "ticker": "LUNR", "window": "mid_weak"}, {"space_theme_segment": "launch_lunar", "strategy": "breakout_long", "ticker": "RKLB", "window": "old_thin"}, {"space_theme_segment": "launch_lunar", "strategy": "breakout_long", "ticker": "LUNR", "window": "old_thin"}, {"space_theme_segment": "launch_lunar", "strategy": "breakout_long", "ticker": "RKLB", "window": "old_thin"}, {"space_theme_segment": "launch_lunar", "strategy": "breakout_long", "ticker": "RKLB", "window": "old_thin"}], "state_counts": {"launch_lunar": 26, "satellite_connectivity": 12, "space_data_defense": 31}, "target_theme_segment": "satellite_connectivity"}

## Interpretation

The satellite-connectivity theme scalar did not clear the three-window gate on top of exp-20260513-015. Keep Space theme-segment risk allocation limited to the accepted launch/lunar helper.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
