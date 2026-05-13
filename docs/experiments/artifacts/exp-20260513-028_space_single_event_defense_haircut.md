# exp-20260513-028 Space single-event defense-only risk

- decision: `accepted_default_off_space_single_event_defense_risk`
- best variant: `single_event_defense_1_05`
- aggregate EV delta: `+0.0841`
- aggregate PnL delta: `$+3,217.66`

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Target signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0447 | 6.0447 | +0.0000 | 131,975.34 | 131,975.34 | +0.00 | 22 | 0.0898 | 0.7931 | 3 |
| mid_weak | 9.9541 | 9.9744 | +0.0203 | 201,501.32 | 202,316.30 | +814.98 | 24 | 0.0503 | 0.7042 | 5 |
| old_thin | 1.6709 | 1.7347 | +0.0638 | 87,942.33 | 90,345.01 | +2,402.68 | 24 | 0.1534 | 0.8919 | 5 |

## Field Checks

{"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "excluded_event_field": "customer_win", "excluded_semantic_buckets": ["attention_only"], "missing_required_fields": [], "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"ASTS": {"event_count": 2, "event_fields": ["customer_win", "government_space_contract"], "event_ids": ["asts_fcc_d2d_authorization_20260421", "golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme", "fundamental_contract_regulatory"], "source_types": ["official_government_release", "official_regulatory_release"]}, "BKSY": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "LUNR": {"event_count": 2, "event_fields": ["customer_win", "government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424", "lunr_nasa_clps_20260324"], "semantic_buckets": ["defense_budget_theme", "fundamental_contract_regulatory"], "source_types": ["official_government_release", "official_or_primary_release"]}, "PL": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "RDW": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "RKLB": {"event_count": 2, "event_fields": ["customer_win", "government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424", "rklb_record_backlog_launch_deal_20260507"], "semantic_buckets": ["defense_budget_theme", "fundamental_contract_regulatory"], "source_types": ["company_release", "official_government_release"]}}, "semantic_bucket_counts": {"attention_only": 2, "defense_budget_theme": 1, "fundamental_contract_regulatory": 3}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_definition": "official Space ticker with exactly one official non-attention seed, government_space_contract present, no customer_win, and defense_budget_theme", "target_event_field": "government_space_contract", "target_semantic_bucket": "defense_budget_theme", "target_source_types": ["official_or_primary_release", "official_regulatory_release", "official_government_release", "company_release"], "target_tickers": ["BKSY", "PL", "RDW"]}

## Interpretation

The single-event defense-only Space scalar cleared the three-window gate on top of the exp-020 accepted stack. The retained change is promoted through shared default-off Space policy metadata with live Space slots still zero, so production observation and replay attribution use the same production-visible event-seed profile boundary.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "promotion_required_if_accepted": false, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
