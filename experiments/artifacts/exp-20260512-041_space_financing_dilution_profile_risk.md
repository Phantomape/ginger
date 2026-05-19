# exp-20260512-041 Space financing/dilution profile risk

- Decision: `accepted_default_off_space_financing_dilution_profile_risk`
- Single variable: risk scalar for official Space signals whose `event_guard_profile` contains financing or dilution.
- Best variant: `financing_dilution_profile_1_075`
- Aggregate EV delta vs accepted: `+0.5022`
- Aggregate PnL delta vs accepted: `$+11,012.31`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| financing_dilution_profile_0_5 | 0.50 | fail | -3.5909 | -76,321.30 | 0 | 3 | 15 |
| financing_dilution_profile_0_75 | 0.75 | fail | -1.6956 | -37,135.10 | 0 | 3 | 15 |
| financing_dilution_profile_0_9 | 0.90 | fail | -0.6644 | -14,586.05 | 0 | 3 | 15 |
| financing_dilution_profile_1_0 | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 15 |
| financing_dilution_profile_1_05 | 1.05 | pass | +0.3068 | +6,986.48 | 3 | 0 | 15 |
| financing_dilution_profile_1_075 | 1.07 | pass | +0.5022 | +11,012.31 | 3 | 0 | 15 |
| financing_dilution_profile_1_1 | 1.10 | fail | +0.6538 | +14,698.76 | 3 | 0 | 15 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Profile signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5797 | 5.6712 | +0.0915 | 118,973.13 | 121,436.91 | +2,463.78 | 22 | 0.0813 | 0.7931 | 2 |
| mid_weak | 6.7018 | 7.0600 | +0.3582 | 143,204.97 | 149,258.40 | +6,053.43 | 24 | 0.0471 | 0.7746 | 8 |
| old_thin | 1.2250 | 1.2775 | +0.0525 | 66,936.85 | 69,431.95 | +2,495.10 | 24 | 0.1243 | 0.8919 | 5 |

## Field Check

{"field": "event_guard_profile", "missing_event_guard_profile": [], "passed": true, "path": "data/universe_registry.json", "profiles": {"ASTS": "satellite_launch_and_financing_sensitive", "BKSY": "defense_contract_and_liquidity_sensitive", "LUNR": "mission_binary_and_contract_sensitive", "PL": "data_contract_and_revenue_quality_sensitive", "RDW": "contract_concentration_and_dilution_sensitive", "RKLB": "launch_contract_and_dilution_sensitive"}, "target_profile_terms": ["financing", "dilution"], "target_tickers": ["ASTS", "RDW", "RKLB"]}

## Interpretation

The financing/dilution event-guard profile scalar improved the accepted default-off Space stack under the three-window gate. Promotion must stay shared and metadata-only with live Space slots at zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
