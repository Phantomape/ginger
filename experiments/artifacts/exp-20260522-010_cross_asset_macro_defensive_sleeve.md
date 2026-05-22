# exp-20260522-010 cross_asset_macro_defensive_sleeve

## Hypothesis
A defensive macro sleeve should only compete for slots when a cross-asset risk-off state is visible: stock pressure, precious metal leadership, defensive sector ETF leadership, and a non-positive TLT/IEF rates basket.

## Trial Accounting
- trial_family: cross_asset_macro_defensive_sleeve_activation
- changed_variable: macro_defensive_long_activation_state
- prior_trial_count: 4
- nearby_prior_experiments: exp-20260425-005, exp-20260425-008, exp-20260425-010, exp-20260515-017
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_pit_universe_proxy_ohlcv_rows

## Three-Window Results
| window | baseline EV | after EV | EV delta | baseline PnL | after PnL | PnL delta | macro trades | state days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | 0.0000 | 117072.92 | 117072.92 | 0.00 | 0 | 16 |
| mid_weak | 2.1435 | 1.9518 | -0.1917 | 80284.57 | 75645.63 | -4638.94 | 2 | 1 |
| old_thin | 0.6058 | 0.7281 | 0.1223 | 41206.02 | 45787.87 | 4581.85 | 7 | 18 |

## Aggregate
- baseline_expected_value_score: 7.9121
- after_expected_value_score: 7.8427
- expected_value_score_delta: -0.0694
- expected_value_score_delta_pct: -0.008771
- total_pnl_delta: -57.09
- macro_trade_count: 9
- macro_trade_windows: 2

## Gate Checks
- aggregate_expected_value_score_improved: False
- aggregate_total_pnl_improved: False
- at_least_two_windows_ev_improved: False
- no_window_ev_regressed: False
- drawdown_worse_within_guardrail: True
- survival_rate_above_5pct: True
- enough_macro_trades: True
- macro_trades_in_multiple_windows: True
- macro_concentration_guardrail: True

## Decision
- decision: rejected
- rejection_reason: aggregate_expected_value_score_improved; aggregate_total_pnl_improved; at_least_two_windows_ev_improved; no_window_ev_regressed

## Production Impact
- shared_policy_changed: false
- backtester_adapter_changed: false
- run_adapter_changed: false
- replay_only: true
- parity_test_added: false
