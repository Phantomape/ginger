# exp-20260512-019 Space low execution-adjusted R/R risk

- Decision: `rejected_space_low_exec_rr_risk`
- Single variable: risk scalar for official Space signals with `exec_lag_adj_net_rr < 2.75`.
- Best variant: `low_exec_rr_0_25`
- Aggregate EV delta vs accepted: `+0.1160`
- Aggregate PnL delta vs accepted: `$-2,739.67`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals | Missing R/R |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| accepted_exp013_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 0 | 0 |
| low_exec_rr_0_0 | 0.00 | fail | -2.9669 | -31,566.29 | 0 | 2 | 8 | 0 |
| low_exec_rr_0_25 | 0.25 | fail | +0.1160 | -2,739.67 | 1 | 1 | 8 | 0 |
| low_exec_rr_0_5 | 0.50 | fail | +0.0687 | -1,841.87 | 1 | 1 | 8 | 0 |
| low_exec_rr_0_75 | 0.75 | fail | +0.0309 | -923.27 | 1 | 1 | 8 | 0 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Low-R/R signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1438 | 5.1438 | +0.0000 | 108,516.68 | 108,516.68 | +0.00 | 22 | 0.0674 | 0.8103 | 1 |
| mid_weak | 5.8386 | 6.0430 | +0.2044 | 128,318.68 | 130,802.26 | +2,483.58 | 24 | 0.0471 | 0.7746 | 3 |
| old_thin | 1.0951 | 1.0067 | -0.0884 | 60,841.16 | 55,617.91 | -5,223.25 | 24 | 0.0999 | 0.8919 | 4 |

## Interpretation

Execution-adjusted net R/R below the floor did not identify a robust Space risk haircut on top of the accepted exp-20260512-013 stack. It mostly re-weights already sparse low-R/R breakout exposure and does not pass the multi-window EV gate.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "promotion_requires_shared_policy_patch": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
