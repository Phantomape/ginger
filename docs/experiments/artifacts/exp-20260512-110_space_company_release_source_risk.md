# exp-20260512-110 Space company-release source risk

- Decision: `accepted_default_off_space_company_release_source_risk`
- Single variable: risk scalar for official Space customer-win signals from company_release event seeds.
- Best variant: `company_release_source_1_1`
- Aggregate EV delta vs accepted: `+0.2699`
- Aggregate PnL delta vs accepted: `$+7,688.22`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| company_release_source_0_75 | 0.750 | fail | -0.8014 | -19,194.79 | 0 | 3 | 9 |
| company_release_source_0_9 | 0.900 | fail | -0.3054 | -7,687.38 | 0 | 3 | 9 |
| company_release_source_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 9 |
| company_release_source_1_05 | 1.050 | pass | +0.1319 | +3,935.86 | 3 | 0 | 9 |
| company_release_source_1_075 | 1.075 | pass | +0.2128 | +5,781.87 | 3 | 0 | 9 |
| company_release_source_1_1 | 1.100 | pass | +0.2699 | +7,688.22 | 3 | 0 | 9 |
| company_release_source_1_25 | 1.250 | fail | +0.6711 | +19,054.29 | 3 | 0 | 9 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Company-release signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6712 | 5.7713 | +0.1001 | 121,436.91 | 124,917.02 | +3,480.11 | 22 | 0.0849 | 0.7931 | 2 |
| mid_weak | 7.0600 | 7.2114 | +0.1514 | 149,258.40 | 152,464.45 | +3,206.05 | 24 | 0.0471 | 0.7746 | 4 |
| old_thin | 1.2775 | 1.2959 | +0.0184 | 69,431.95 | 70,434.01 | +1,002.06 | 24 | 0.1285 | 0.8919 | 3 |

## Field Check

{"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "missing_fields": [], "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"RKLB": {"event_fields": ["customer_win"], "event_ids": ["rklb_record_backlog_launch_deal_20260507"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["company_release"]}}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_event_field": "customer_win", "target_source_types": ["company_release"], "target_tickers": ["RKLB"]}

## Interpretation

The company-release customer-source scalar improved the accepted default-off Space stack under the three-window gate. Promotion must stay shared and metadata-only with live Space slots at zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
