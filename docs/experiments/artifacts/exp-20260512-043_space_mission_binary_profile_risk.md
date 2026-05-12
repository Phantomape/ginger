# exp-20260512-043 Space mission-binary profile risk

- Decision: `rejected_space_mission_binary_profile_risk`
- Single variable: risk scalar for official Space signals whose `event_guard_profile` contains mission_binary.
- Best variant: `mission_binary_profile_0_5`
- Aggregate EV delta vs accepted: `+0.0000`
- Aggregate PnL delta vs accepted: `$+0.00`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| mission_binary_profile_0_5 | 0.500 | fail | +0.0000 | +0.00 | 0 | 0 | 2 |
| mission_binary_profile_0_75 | 0.750 | fail | +0.0000 | +0.00 | 0 | 0 | 2 |
| mission_binary_profile_0_9 | 0.900 | fail | +0.0000 | +0.00 | 0 | 0 | 2 |
| mission_binary_profile_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 2 |
| mission_binary_profile_1_05 | 1.050 | fail | +0.0000 | +0.00 | 0 | 0 | 2 |
| mission_binary_profile_1_075 | 1.075 | fail | +0.0000 | +0.00 | 0 | 0 | 2 |
| mission_binary_profile_1_1 | 1.100 | fail | +0.0000 | +0.00 | 0 | 0 | 2 |
| mission_binary_profile_1_25 | 1.250 | fail | +0.0000 | +0.00 | 0 | 0 | 2 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Mission signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6712 | 5.6712 | +0.0000 | 121,436.91 | 121,436.91 | +0.00 | 22 | 0.0813 | 0.7931 | 0 |
| mid_weak | 7.0600 | 7.0600 | +0.0000 | 149,258.40 | 149,258.40 | +0.00 | 24 | 0.0471 | 0.7746 | 1 |
| old_thin | 1.2775 | 1.2775 | +0.0000 | 69,431.95 | 69,431.95 | +0.00 | 24 | 0.1243 | 0.8919 | 1 |

## Field Check

{"field": "event_guard_profile", "missing_event_guard_profile": [], "passed": true, "path": "data/universe_registry.json", "profiles": {"ASTS": "satellite_launch_and_financing_sensitive", "BKSY": "defense_contract_and_liquidity_sensitive", "LUNR": "mission_binary_and_contract_sensitive", "PL": "data_contract_and_revenue_quality_sensitive", "RDW": "contract_concentration_and_dilution_sensitive", "RKLB": "launch_contract_and_dilution_sensitive"}, "target_profile_terms": ["mission_binary"], "target_tickers": ["LUNR"]}

## Interpretation

The mission-binary event-guard profile scalar did not clear the three-window gate on top of exp-20260512-041. Do not retry adjacent mission-binary registry-profile scalars on these frozen snapshots.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
