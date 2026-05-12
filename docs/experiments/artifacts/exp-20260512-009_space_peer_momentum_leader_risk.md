# exp-20260512-009 Space peer-momentum leader risk

- Decision: `rejected_space_peer_momentum_leader_risk`
- Single variable: extra risk scalar for official Space signals whose own 20d momentum is above the official Space basket average.
- Best variant: `peer_momentum_leader_1_5`
- Aggregate EV delta vs accepted: `+0.8628`
- Aggregate PnL delta vs accepted: `$+26,068.23`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp008_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| peer_momentum_leader_0_75 | 0.75 | fail | -0.6757 | -18,115.70 | 0 | 2 | 20 |
| peer_momentum_leader_1_1 | 1.10 | fail | +0.1859 | +5,665.18 | 2 | 0 | 20 |
| peer_momentum_leader_1_25 | 1.25 | fail | +0.4548 | +13,746.58 | 2 | 0 | 20 |
| peer_momentum_leader_1_5 | 1.50 | fail | +0.8628 | +26,068.23 | 2 | 0 | 20 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Peer-leader signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1258 | 5.1258 | +0.0000 | 108,141.30 | 108,141.30 | +0.00 | 23 | 0.0674 | 0.8070 | 3 |
| mid_weak | 5.5269 | 5.9465 | +0.4196 | 124,484.60 | 131,270.91 | +6,786.31 | 25 | 0.0471 | 0.7746 | 9 |
| old_thin | 1.0951 | 1.5383 | +0.4432 | 60,841.16 | 80,123.08 | +19,281.92 | 24 | 0.1331 | 0.8919 | 8 |

## Interpretation

Peer-relative 20d momentum did not beat the accepted exp-20260512-008 Space stack under the three-window gate. Do not add a peer-leader risk top-up on the frozen Space snapshots; future Space work needs forward catalyst replacement value or a genuinely new catalyst-quality field.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
