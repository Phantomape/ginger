# exp-20260512-012 Space peer-nonleader breakout risk

- Decision: `accepted_default_off_space_peer_nonleader_breakout_risk`
- Single variable: risk scalar for official Space breakout_long signals whose own 20d momentum is not above the official Space basket average.
- Best variant: `peer_nonleader_breakout_0_0`
- Aggregate EV delta vs accepted: `+0.3297`
- Aggregate PnL delta vs accepted: `$+4,209.46`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp008_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| peer_nonleader_breakout_0_0 | 0.00 | pass | +0.3297 | +4,209.46 | 2 | 0 | 5 |
| peer_nonleader_breakout_0_25 | 0.25 | pass | +0.2558 | +3,200.53 | 2 | 0 | 5 |
| peer_nonleader_breakout_0_5 | 0.50 | pass | +0.1655 | +2,050.40 | 2 | 0 | 5 |
| peer_nonleader_breakout_0_75 | 0.75 | pass | +0.0832 | +1,014.44 | 2 | 0 | 5 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Nonleader breakout signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1258 | 5.1438 | +0.0180 | 108,141.30 | 108,516.68 | +375.38 | 22 | 0.0674 | 0.8103 | 1 |
| mid_weak | 5.5269 | 5.8386 | +0.3117 | 124,484.60 | 128,318.68 | +3,834.08 | 24 | 0.0471 | 0.7746 | 3 |
| old_thin | 1.0951 | 1.0951 | +0.0000 | 60,841.16 | 60,841.16 | +0.00 | 24 | 0.1077 | 0.8919 | 1 |

## Interpretation

Official Space peer-nonleader breakouts improved the accepted default-off Space stack under the three-window gate. Promotion should stay default-off metadata/helper only because Space live slots remain zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
