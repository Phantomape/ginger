# exp-20260513-012 Space multi-event catalyst depth risk

- Decision: `accepted_default_off_space_multi_event_depth_risk`
- Single variable: risk scalar for official Space signals whose event seed profile has at least two official, non-attention catalyst rows.
- Best variant: `multi_event_depth_1_075`
- Aggregate EV delta vs accepted: `+0.4957`
- Aggregate PnL delta vs accepted: `$+10,897.96`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| multi_event_depth_0_5 | 0.500 | fail | -4.6124 | -91,804.83 | 0 | 3 | 15 |
| multi_event_depth_0_75 | 0.750 | fail | -2.5396 | -51,095.26 | 0 | 3 | 15 |
| multi_event_depth_0_9 | 0.900 | fail | -1.4220 | -28,008.90 | 0 | 3 | 15 |
| multi_event_depth_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 15 |
| multi_event_depth_1_05 | 1.050 | pass | +0.3159 | +7,073.88 | 3 | 0 | 15 |
| multi_event_depth_1_075 | 1.075 | pass | +0.4957 | +10,897.96 | 3 | 0 | 15 |
| multi_event_depth_1_1 | 1.100 | fail | -0.2313 | +152.68 | 2 | 1 | 15 |
| multi_event_depth_1_25 | 1.250 | fail | +0.6940 | +22,010.71 | 3 | 0 | 14 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Multi-event signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.9589 | 6.0447 | +0.0858 | 128,977.06 | 131,975.34 | +2,998.28 | 22 | 0.0898 | 0.7931 | 2 |
| mid_weak | 8.5242 | 8.9165 | +0.3923 | 176,120.07 | 183,086.66 | +6,966.59 | 24 | 0.0472 | 0.7606 | 9 |
| old_thin | 1.4352 | 1.4528 | +0.0176 | 76,753.86 | 77,686.95 | +933.09 | 24 | 0.1381 | 0.8919 | 4 |

## Field Check

{"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "excluded_semantic_buckets": ["attention_only"], "missing_required_fields": [], "multi_event_min_count": 2, "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"ASTS": {"event_count": 2, "event_fields": ["customer_win", "government_space_contract"], "event_ids": ["asts_fcc_d2d_authorization_20260421", "golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme", "fundamental_contract_regulatory"], "source_types": ["official_government_release", "official_regulatory_release"]}, "BKSY": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "LUNR": {"event_count": 2, "event_fields": ["customer_win", "government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424", "lunr_nasa_clps_20260324"], "semantic_buckets": ["defense_budget_theme", "fundamental_contract_regulatory"], "source_types": ["official_government_release", "official_or_primary_release"]}, "PL": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "RDW": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "RKLB": {"event_count": 2, "event_fields": ["customer_win", "government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424", "rklb_record_backlog_launch_deal_20260507"], "semantic_buckets": ["defense_budget_theme", "fundamental_contract_regulatory"], "source_types": ["company_release", "official_government_release"]}}, "semantic_bucket_counts": {"attention_only": 2, "defense_budget_theme": 1, "fundamental_contract_regulatory": 3}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_definition": "official Space ticker with at least two official, non-attention event seed rows", "target_source_types": ["official_or_primary_release", "official_regulatory_release", "official_government_release", "company_release"], "target_tickers": ["ASTS", "LUNR", "RKLB"]}

## Interpretation

Official non-attention catalyst-depth risk scaling improved the accepted default-off Space stack under the three-window gate. Promotion must stay shared and metadata-only with live Space slots at zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
