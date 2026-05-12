# exp-20260512-016 Space basket breadth risk

- Decision: `rejected_space_basket_breadth_risk`
- Single variable: minimum positive official Space basket member count required before applying the accepted basket-positive 1.10x top-up.
- Best variant: `basket_breadth_min_2`
- Aggregate EV delta vs accepted: `+0.0000`
- Aggregate PnL delta vs accepted: `$+0.00`

## Sweep

| Variant | Min positive members | Gate | dEV | dPnL | Improved windows | Regressed windows | Skipped top-ups |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp013_stack | avg>0 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| basket_breadth_min_2 | 2 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| basket_breadth_min_3 | 3 | fail | +0.0000 | +0.00 | 0 | 0 | 1 |
| basket_breadth_min_4 | 4 | fail | +0.0000 | +0.00 | 0 | 0 | 1 |
| basket_breadth_min_5 | 5 | fail | -0.0151 | -844.13 | 0 | 1 | 2 |
| basket_breadth_min_6 | 6 | fail | -0.2229 | -5,959.17 | 0 | 2 | 14 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Skipped top-ups |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1438 | 5.1438 | +0.0000 | 108,516.68 | 108,516.68 | +0.00 | 22 | 0.0674 | 0.8103 | 0 |
| mid_weak | 5.8386 | 5.8386 | +0.0000 | 128,318.68 | 128,318.68 | +0.00 | 24 | 0.0471 | 0.7746 | 0 |
| old_thin | 1.0951 | 1.0951 | +0.0000 | 60,841.16 | 60,841.16 | +0.00 | 24 | 0.1077 | 0.8919 | 0 |

## Field Check

{"available_counts": [6], "breadth_day_counts": {"0_of_6": 124, "1_of_6": 51, "2_of_6": 41, "3_of_6": 63, "4_of_6": 75, "5_of_6": 131, "6_of_6": 224}, "field": "momentum_20d_pct", "passed": true, "source": "feature_layer trend features from augmented Space snapshots"}

## Interpretation

Official Space basket breadth did not improve the accepted exp-20260512-013 stack. Keep the accepted average-positive basket 1.10x top-up unchanged; future Space work should use forward catalyst replacement value or a genuinely new event-quality field.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
