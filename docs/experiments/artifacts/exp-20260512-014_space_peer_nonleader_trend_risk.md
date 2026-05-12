# exp-20260512-014 Space peer-nonleader trend risk

- Decision: `rejected_space_peer_nonleader_trend_risk`
- Single variable: risk scalar for official Space trend_long signals whose own 20d momentum is not above the official Space basket average.
- Best variant: `peer_nonleader_trend_0_75`
- Aggregate EV delta vs accepted: `-0.9824`
- Aggregate PnL delta vs accepted: `$-17,574.37`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp013_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| peer_nonleader_trend_0_0 | 0.00 | fail | -4.2725 | -61,796.06 | 0 | 2 | 4 |
| peer_nonleader_trend_0_25 | 0.25 | fail | -2.8893 | -49,725.34 | 0 | 2 | 5 |
| peer_nonleader_trend_0_5 | 0.50 | fail | -1.7984 | -31,895.11 | 0 | 2 | 5 |
| peer_nonleader_trend_0_75 | 0.75 | fail | -0.9824 | -17,574.37 | 0 | 2 | 5 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Nonleader trend signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1438 | 4.8564 | -0.2874 | 108,516.68 | 102,892.93 | -5,623.75 | 22 | 0.0608 | 0.8103 | 1 |
| mid_weak | 5.8386 | 5.1436 | -0.6950 | 128,318.68 | 116,368.06 | -11,950.62 | 24 | 0.0471 | 0.7746 | 4 |
| old_thin | 1.0951 | 1.0951 | +0.0000 | 60,841.16 | 60,841.16 | +0.00 | 24 | 0.1077 | 0.8919 | 0 |

## Interpretation

Peer-nonleader status did not identify a robust Space trend haircut on top of the accepted exp-20260512-013 stack. Keep the accepted trend risk ladder unchanged; future Space trend work needs forward catalyst replacement value or a genuinely new catalyst-quality field.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
