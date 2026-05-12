# exp-20260512-044 Space satellite-connectivity theme risk

- Decision: `rejected_space_satellite_connectivity_theme_risk`
- Single variable: risk scalar for official Space signals whose universe-registry `theme_segment` is `satellite_connectivity`.
- Best variant: `satellite_connectivity_theme_1_25`
- Aggregate EV delta vs accepted: `+1.6464`
- Aggregate PnL delta vs accepted: `$+27,699.63`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| satellite_connectivity_theme_0_5 | 0.500 | fail | -1.9815 | -32,775.46 | 0 | 1 | 4 |
| satellite_connectivity_theme_0_75 | 0.750 | fail | -0.8846 | -14,126.39 | 0 | 1 | 4 |
| satellite_connectivity_theme_0_9 | 0.900 | fail | -0.3567 | -5,719.11 | 0 | 1 | 4 |
| satellite_connectivity_theme_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 4 |
| satellite_connectivity_theme_1_05 | 1.050 | fail | +0.1591 | +2,725.45 | 1 | 0 | 4 |
| satellite_connectivity_theme_1_075 | 1.075 | fail | +0.9265 | +15,751.67 | 1 | 0 | 4 |
| satellite_connectivity_theme_1_1 | 1.100 | fail | +1.0133 | +17,200.09 | 1 | 0 | 4 |
| satellite_connectivity_theme_1_25 | 1.250 | fail | +1.6464 | +27,699.63 | 1 | 0 | 4 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Satellite signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6712 | 5.6712 | +0.0000 | 121,436.91 | 121,436.91 | +0.00 | 22 | 0.0813 | 0.7931 | 0 |
| mid_weak | 7.0600 | 8.7064 | +1.6464 | 149,258.40 | 176,958.03 | +27,699.63 | 24 | 0.0471 | 0.7606 | 4 |
| old_thin | 1.2775 | 1.2775 | +0.0000 | 69,431.95 | 69,431.95 | +0.00 | 24 | 0.1243 | 0.8919 | 0 |

## Field Check

{"field": "theme_segment", "missing_theme_segment": [], "passed": true, "path": "data/universe_registry.json", "target_theme_segment": "satellite_connectivity", "target_tickers": ["ASTS"], "theme_segments": {"ASTS": "satellite_connectivity", "BKSY": "space_data_defense", "LUNR": "launch_lunar", "PL": "space_data_defense", "RDW": "space_data_defense", "RKLB": "launch_lunar"}}

## Interpretation

The satellite-connectivity theme-segment scalar did not clear the three-window gate on top of exp-20260512-041. Do not retry adjacent satellite-connectivity theme-segment scalars on these frozen snapshots.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
