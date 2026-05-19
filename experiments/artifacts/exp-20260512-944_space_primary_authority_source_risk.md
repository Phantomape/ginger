# exp-20260512-944 Space primary-authority source risk

- Decision: `rejected_space_primary_authority_source_risk`
- Single variable: risk scalar for official Space customer-win signals from official_or_primary_release or official_regulatory_release.
- Best variant: `primary_authority_source_1_25`
- Aggregate EV delta vs accepted: `+1.6464`
- Aggregate PnL delta vs accepted: `$+27,699.63`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| primary_authority_source_0_75 | 0.750 | fail | -0.8846 | -14,126.39 | 0 | 1 | 6 |
| primary_authority_source_0_9 | 0.900 | fail | -0.3567 | -5,719.11 | 0 | 1 | 6 |
| primary_authority_source_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 6 |
| primary_authority_source_1_05 | 1.050 | fail | +0.1591 | +2,725.45 | 1 | 0 | 6 |
| primary_authority_source_1_075 | 1.075 | fail | +0.9265 | +15,751.67 | 1 | 0 | 6 |
| primary_authority_source_1_1 | 1.100 | fail | +1.0133 | +17,200.09 | 1 | 0 | 6 |
| primary_authority_source_1_25 | 1.250 | fail | +1.6464 | +27,699.63 | 1 | 0 | 6 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Primary-authority signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6712 | 5.6712 | +0.0000 | 121,436.91 | 121,436.91 | +0.00 | 22 | 0.0813 | 0.7931 | 0 |
| mid_weak | 7.0600 | 8.7064 | +1.6464 | 149,258.40 | 176,958.03 | +27,699.63 | 24 | 0.0471 | 0.7606 | 5 |
| old_thin | 1.2775 | 1.2775 | +0.0000 | 69,431.95 | 69,431.95 | +0.00 | 24 | 0.1243 | 0.8919 | 1 |

## Field Check

{"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "missing_fields": [], "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"ASTS": {"event_fields": ["customer_win"], "event_ids": ["asts_fcc_d2d_authorization_20260421"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_regulatory_release"]}, "LUNR": {"event_fields": ["customer_win", "government_space_contract"], "event_ids": ["lunr_nasa_clps_20260324"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_or_primary_release"]}}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_event_field": "customer_win", "target_source_types": ["official_or_primary_release", "official_regulatory_release"], "target_tickers": ["ASTS", "LUNR"]}

## Interpretation

The primary-authority customer-source scalar did not clear the three-window gate on top of exp-20260512-041. Do not retry adjacent official/regulatory customer-source scalars on these frozen snapshots.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
