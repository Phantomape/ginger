# exp-20260512-020 Space breakout volume-confirmation risk

- Decision: `rejected_space_breakout_volume_confirmation_risk`
- Single variable: risk scalar for official Space breakout_long signals with `conditions_met.volume_spike_ratio > 2.0`.
- Best variant: `breakout_strong_volume_0_75`
- Aggregate EV delta vs accepted: `+0.0018`
- Aggregate PnL delta vs accepted: `$+39.09`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp013_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| breakout_strong_volume_0_75 | 0.75 | fail | +0.0018 | +39.09 | 1 | 0 | 2 |
| breakout_strong_volume_1_1 | 1.10 | fail | -0.0215 | -192.24 | 0 | 1 | 2 |
| breakout_strong_volume_1_25 | 1.25 | fail | -0.0233 | -231.07 | 0 | 1 | 2 |
| breakout_strong_volume_1_5 | 1.50 | fail | -0.0260 | -287.74 | 0 | 1 | 2 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Strong-volume adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1438 | 5.1438 | +0.0000 | 108,516.68 | 108,516.68 | +0.00 | 22 | 0.0674 | 0.8103 | 0 |
| mid_weak | 5.8386 | 5.8404 | +0.0018 | 128,318.68 | 128,357.77 | +39.09 | 24 | 0.0471 | 0.7746 | 1 |
| old_thin | 1.0951 | 1.0951 | +0.0000 | 60,841.16 | 60,841.16 | +0.00 | 24 | 0.1077 | 0.8919 | 1 |

## Field Check

{"field": "conditions_met.volume_spike_ratio", "missing_count": 0, "passed": true, "source": "feature_layer.compute_trend_features -> signal_engine.strategy_b", "standard_volume_count": 9, "strong_volume_count": 4, "strong_volume_definition": "volume_spike_ratio > 2.0"}

## Interpretation

The existing strong-volume breakout boundary did not identify a robust Space breakout risk scalar on top of exp-20260512-013. Do not retry nearby Space breakout volume-confirmation scalars on the same frozen snapshots; future Space work needs a different catalyst-quality field, forward replacement evidence, or a true candidate-pool improvement.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
