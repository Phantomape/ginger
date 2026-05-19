# exp-20260512-010 Space near-perfect TQS breakout risk

- Decision: `rejected_space_near_perfect_tqs_breakout_risk`
- Single variable: extra risk scalar for official Space breakout_long signals with 0.95 <= TQS < 1.0.
- Best variant: `near_perfect_tqs_breakout_0_25`
- Aggregate EV delta vs accepted: `+0.2498`
- Aggregate PnL delta vs accepted: `$+3,033.22`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp008_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| near_perfect_tqs_breakout_0_0 | 0.00 | fail | -2.4372 | -17,575.06 | 0 | 1 | 4 |
| near_perfect_tqs_breakout_0_25 | 0.25 | fail | +0.2498 | +3,033.22 | 1 | 0 | 4 |
| near_perfect_tqs_breakout_0_5 | 0.50 | fail | +0.1633 | +1,965.83 | 1 | 0 | 4 |
| near_perfect_tqs_breakout_0_75 | 0.75 | fail | +0.0821 | +991.33 | 1 | 0 | 4 |
| near_perfect_tqs_breakout_1_1 | 1.10 | fail | -0.0337 | -488.02 | 0 | 1 | 4 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Near-perfect breakout signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1258 | 5.1258 | +0.0000 | 108,141.30 | 108,141.30 | +0.00 | 23 | 0.0674 | 0.8070 | 0 |
| mid_weak | 5.5269 | 5.7767 | +0.2498 | 124,484.60 | 127,517.82 | +3,033.22 | 25 | 0.0471 | 0.7746 | 2 |
| old_thin | 1.0951 | 1.0951 | +0.0000 | 60,841.16 | 60,841.16 | +0.00 | 24 | 0.1077 | 0.8919 | 2 |

## Interpretation

Near-perfect TQS did not identify a robust Space breakout risk allocation edge on top of the accepted exp-20260512-008 Space stack. Do not add a separate high-TQS breakout scalar on the frozen Space snapshots; breakout alpha needs forward catalyst-quality evidence or a different ex-ante discriminator.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
