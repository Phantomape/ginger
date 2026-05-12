# exp-20260512-035 Space data/defense theme-segment risk

- Decision: `rejected_space_data_defense_theme_risk`
- Single variable: risk scalar for official Space signals whose universe-registry `theme_segment` is `space_data_defense`.
- Best variant: `data_defense_1_25`
- Aggregate EV delta vs accepted: `+0.1986`
- Aggregate PnL delta vs accepted: `$+8,204.94`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| data_defense_0_5 | 0.50 | fail | -0.4810 | -19,633.99 | 1 | 1 | 15 |
| data_defense_0_75 | 0.75 | fail | -0.2491 | -10,046.51 | 1 | 1 | 15 |
| data_defense_0_9 | 0.90 | fail | -0.1040 | -4,067.86 | 1 | 1 | 15 |
| data_defense_1_1 | 1.10 | fail | +0.0920 | +3,683.08 | 1 | 1 | 15 |
| data_defense_1_25 | 1.25 | fail | +0.1986 | +8,204.94 | 1 | 1 | 15 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Data/defense signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.3558 | 5.3558 | +0.0000 | 113,231.15 | 113,231.15 | +0.00 | 22 | 0.0726 | 0.7931 | 3 |
| mid_weak | 6.1751 | 6.1686 | -0.0065 | 133,953.19 | 133,807.23 | -145.96 | 24 | 0.0471 | 0.7746 | 7 |
| old_thin | 1.2012 | 1.4063 | +0.2051 | 65,276.60 | 73,627.50 | +8,350.90 | 24 | 0.1191 | 0.8919 | 5 |

## Field Check

{"base_registry_gate": {"mismatched_theme_segment": [], "missing_theme_segment": [], "passed": true, "path": "data\\universe_registry.json", "segments": {"ASTS": {"actual": "satellite_connectivity", "expected": "satellite_connectivity", "liquidity_tier": "watch", "status": "research"}, "BKSY": {"actual": "space_data_defense", "expected": "space_data_defense", "liquidity_tier": "watch", "status": "research"}, "LUNR": {"actual": "launch_lunar", "expected": "launch_lunar", "liquidity_tier": "watch", "status": "research"}, "PL": {"actual": "space_data_defense", "expected": "space_data_defense", "liquidity_tier": "watch", "status": "research"}, "RDW": {"actual": "space_data_defense", "expected": "space_data_defense", "liquidity_tier": "watch", "status": "research"}, "RKLB": {"actual": "launch_lunar", "expected": "launch_lunar", "liquidity_tier": "ok", "status": "research"}}, "target_theme_segment": "launch_lunar", "target_tickers": ["LUNR", "RKLB"]}, "passed": true, "target_theme_segment": "space_data_defense", "target_tickers": ["BKSY", "PL", "RDW"]}

## Interpretation

The space_data_defense theme-segment risk scalar did not clear the three-window gate on top of exp-20260512-032. Do not retry adjacent Space data/defense theme scalar values on these frozen snapshots; the next Space edge needs forward catalyst replacement value or a different production-observable catalyst-quality field.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
