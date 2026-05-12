# exp-20260512-023 Space GSAT candidate pool

- Decision: `rejected_space_gsat_candidate_pool`
- Single variable: add `GSAT` to the default-off official Space candidate pool.
- Aggregate EV delta vs accepted: `-1.1993`
- Aggregate PnL delta vs accepted: `$-4,496.98`
- GSAT signals / trades: `7` / `2`

## Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | GSAT signals | GSAT trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1438 | 5.3478 | +0.2040 | 108,516.68 | 111,178.77 | +2,662.09 | 23 | 0.0665 | 0.7903 | 4 | 1 |
| mid_weak | 5.8386 | 4.5063 | -1.3323 | 128,318.68 | 124,142.11 | -4,176.57 | 24 | 0.0739 | 0.7917 | 2 | 1 |
| old_thin | 1.0951 | 1.0241 | -0.0710 | 60,841.16 | 57,858.66 | -2,982.50 | 24 | 0.1082 | 0.8667 | 1 | 0 |

## Interpretation

Adding GSAT to the official Space candidate pool did not clear the three-window gate on top of the accepted exp-20260512-013 stack. Do not admit GSAT from the frozen Space snapshots; candidate-pool expansion should wait for forward catalyst replacement evidence or a cleaner non-noisy operating-name field.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "promotion_requirement_if_accepted": "Add GSAT through shared Space sleeve metadata/helpers and production observe-only wiring before retaining any positive variant.", "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
