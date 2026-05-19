# exp-20260513-022 Closeout

hypothesis: If government/defense Space catalysts only deserve top-up when peer momentum leads, then government-contract profile signals that are peer nonleaders should get a small risk haircut to reduce broad-theme drawdown while preserving official-catalyst coverage.
change_type: alpha_search
changed_variable: space_government_contract_peer_nonleader_risk_scalar
backtest_protocol: docs/backtesting.md fixed three-window Space pilot sleeve replay, include-pilot-sleeve equivalent
baseline_metrics: {"expected_value_score_sum": 17.0211, "max_drawdown_pct_max": 0.161, "min_survival_rate": 0.6533, "signals_generated_sum": 207, "signals_survived_sum": 160, "total_pnl_sum": 418278.3, "trade_count_sum": 69}
after_metrics: {"expected_value_score_sum": 17.5961, "max_drawdown_pct_max": 0.161, "min_survival_rate": 0.7042, "signals_generated_sum": 203, "signals_survived_sum": 161, "total_pnl_sum": 425004.54, "trade_count_sum": 70}
expected_value_score_delta: 0.575
production_impact: {"backtester_adapter_changed": false, "live_slots": 0, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false, "space_sleeve_default": "shadow/default-off"}
why_not_other_changes: LLM soft-ranking is data-limited; noisy ticker expansion was avoided; this tests one risk-allocation variable inside official-catalyst Space coverage.
known_risks: Space remains default-off live with zero slots; historical replay windows predate live Space slots; decision depends on synthetic Space snapshot replay artifacts.
decision: rejected
