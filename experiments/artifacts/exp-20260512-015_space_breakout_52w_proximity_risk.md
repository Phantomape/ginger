# exp-20260512-015 Space breakout 52w proximity risk

- Decision: `rejected_space_breakout_52w_proximity_risk`
- Single variable: risk scalar for official Space breakout_long signals with pct_from_52w_high <= -5%.
- Best variant: `breakout_not_near_52w_0_25`
- Aggregate EV delta vs accepted: `+0.0059`
- Aggregate PnL delta vs accepted: `$+134.32`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp013_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| breakout_not_near_52w_0_0 | 0.00 | fail | -2.7489 | -21,409.14 | 0 | 1 | 4 |
| breakout_not_near_52w_0_25 | 0.25 | fail | +0.0059 | +134.32 | 1 | 0 | 4 |
| breakout_not_near_52w_0_5 | 0.50 | fail | +0.0036 | +84.43 | 1 | 0 | 4 |
| breakout_not_near_52w_0_75 | 0.75 | fail | +0.0018 | +39.09 | 1 | 0 | 4 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Not-near 52w signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1438 | 5.1438 | +0.0000 | 108,516.68 | 108,516.68 | +0.00 | 22 | 0.0674 | 0.8103 | 0 |
| mid_weak | 5.8386 | 5.8445 | +0.0059 | 128,318.68 | 128,453.00 | +134.32 | 24 | 0.0471 | 0.7746 | 1 |
| old_thin | 1.0951 | 1.0951 | +0.0000 | 60,841.16 | 60,841.16 | +0.00 | 24 | 0.1077 | 0.8919 | 3 |

## Field Check

{"field": "conditions_met.pct_from_52w_high", "missing_count": 0, "near_52w_high_count": 13, "not_near_52w_high_count": 10, "passed": true, "source": "feature_layer.compute_trend_features -> signal_engine strategy_b"}

## Interpretation

The existing near-52w-high quality boundary did not identify a robust Space breakout risk haircut on top of exp-20260512-013. Do not add a Space-specific pct_from_52w_high breakout scalar on the frozen Space snapshots; future breakout work needs a different catalyst-quality or candidate-replacement variable.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
