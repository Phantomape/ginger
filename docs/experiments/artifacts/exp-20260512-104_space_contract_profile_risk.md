# exp-20260512-104 Space contract-sensitive profile risk

- Decision: `rejected_space_contract_profile_risk`
- Single variable: risk scalar for official Space signals whose `event_guard_profile` contains `contract` but not `financing` or `dilution`.
- Best variant: `contract_profile_1_25`
- Aggregate EV delta vs accepted: `+0.0537`
- Aggregate PnL delta vs accepted: `$+2,227.76`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| contract_profile_0_5 | 0.500 | fail | -0.2395 | -8,532.30 | 1 | 1 | 15 |
| contract_profile_0_75 | 0.750 | fail | -0.1152 | -4,173.81 | 1 | 1 | 15 |
| contract_profile_0_9 | 0.900 | fail | -0.0520 | -1,733.10 | 1 | 1 | 15 |
| contract_profile_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 15 |
| contract_profile_1_05 | 1.050 | fail | +0.0231 | +887.89 | 1 | 1 | 15 |
| contract_profile_1_075 | 1.075 | fail | +0.0363 | +1,213.17 | 1 | 1 | 15 |
| contract_profile_1_1 | 1.100 | fail | +0.0392 | +1,392.25 | 1 | 1 | 15 |
| contract_profile_1_25 | 1.250 | fail | +0.0537 | +2,227.76 | 1 | 1 | 15 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Contract signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6712 | 5.6712 | +0.0000 | 121,436.91 | 121,436.91 | +0.00 | 22 | 0.0813 | 0.7931 | 3 |
| mid_weak | 7.0600 | 7.0432 | -0.0168 | 149,258.40 | 149,216.23 | -42.17 | 24 | 0.0471 | 0.7746 | 8 |
| old_thin | 1.2775 | 1.3480 | +0.0705 | 69,431.95 | 71,701.88 | +2,269.93 | 24 | 0.1243 | 0.8919 | 4 |

## Field Check

{"excluded_financing_or_dilution_tickers": ["ASTS", "RDW", "RKLB"], "excluded_profile_terms": ["financing", "dilution"], "field": "event_guard_profile", "missing_event_guard_profile": [], "passed": true, "path": "data/universe_registry.json", "profiles": {"ASTS": "satellite_launch_and_financing_sensitive", "BKSY": "defense_contract_and_liquidity_sensitive", "LUNR": "mission_binary_and_contract_sensitive", "PL": "data_contract_and_revenue_quality_sensitive", "RDW": "contract_concentration_and_dilution_sensitive", "RKLB": "launch_contract_and_dilution_sensitive"}, "target_profile_term": "contract", "target_tickers": ["BKSY", "LUNR", "PL"]}

## Interpretation

Contract-sensitive non-financing Space registry profiles did not clear the three-window gate on top of exp-20260512-041. This argues against more adjacent registry-profile scalar mining on the frozen Space snapshots without forward replacement-value evidence.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
