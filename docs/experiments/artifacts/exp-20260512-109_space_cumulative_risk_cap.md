# exp-20260512-109 Space cumulative risk cap

- Decision: `rejected_space_cumulative_risk_cap`
- Single variable: cap final cumulative Space shares versus the pre-Space-policy baseline shares after all accepted Space top-ups.
- Best variant: `cumulative_risk_cap_2_0`
- Aggregate EV delta vs accepted: `-0.3704`
- Aggregate PnL delta vs accepted: `$-6,316.76`

## Sweep

| Variant | Cap | Gate | dEV | dPnL | Improved windows | Regressed windows | Capped signals |
|---|---:|---|---:|---:|---:|---:|---:|
| cumulative_risk_cap_1_0 | 1.00 | fail | -3.4586 | -69,844.99 | 0 | 3 | 20 |
| cumulative_risk_cap_1_25 | 1.25 | fail | -2.3529 | -44,466.94 | 0 | 3 | 16 |
| cumulative_risk_cap_1_5 | 1.50 | fail | -1.4104 | -24,829.35 | 0 | 2 | 4 |
| cumulative_risk_cap_1_75 | 1.75 | fail | -0.8075 | -13,325.93 | 0 | 2 | 4 |
| cumulative_risk_cap_2_0 | 2.00 | fail | -0.3704 | -6,316.76 | 0 | 1 | 2 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Capped signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6712 | 5.6712 | +0.0000 | 121,436.91 | 121,436.91 | +0.00 | 22 | 0.0813 | 0.7931 | 0 |
| mid_weak | 7.0600 | 6.6896 | -0.3704 | 149,258.40 | 142,941.64 | -6,316.76 | 24 | 0.0471 | 0.7746 | 2 |
| old_thin | 1.2775 | 1.2775 | +0.0000 | 69,431.95 | 69,431.95 | +0.00 | 24 | 0.1243 | 0.8919 | 0 |

## Field Check

{"accepted_financing_profiles": {"field": "event_guard_profile", "missing_event_guard_profile": [], "passed": true, "path": "data/universe_registry.json", "profiles": {"ASTS": "satellite_launch_and_financing_sensitive", "BKSY": "defense_contract_and_liquidity_sensitive", "LUNR": "mission_binary_and_contract_sensitive", "PL": "data_contract_and_revenue_quality_sensitive", "RDW": "contract_concentration_and_dilution_sensitive", "RKLB": "launch_contract_and_dilution_sensitive"}, "target_profile_terms": ["financing", "dilution"], "target_tickers": ["ASTS", "RDW", "RKLB"]}, "baseline_share_key": "space_official_base_risk_baseline_shares", "official_customer_source_profile": {"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "missing_required_fields": [], "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"ASTS": {"event_fields": ["customer_win"], "event_ids": ["asts_fcc_d2d_authorization_20260421"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_regulatory_release"]}, "LUNR": {"event_fields": ["customer_win", "government_space_contract"], "event_ids": ["lunr_nasa_clps_20260324"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_or_primary_release"]}, "RKLB": {"event_fields": ["customer_win"], "event_ids": ["rklb_record_backlog_launch_deal_20260507"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["company_release"]}}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_event_field": "customer_win", "target_source_types": ["official_or_primary_release", "official_regulatory_release", "company_release"], "target_tickers": ["ASTS", "LUNR", "RKLB"]}, "open_positions": {"missing_entry_date_or_target_price": [], "passed": true, "path": "operator_inputs\\open_positions.json", "position_count": 14}, "passed": true}

## Interpretation

Capping cumulative Space risk did not clear the three-window gate on top of exp-20260512-041. The supported Space direction remains new production-visible catalyst-quality evidence, not another generic risk-saturation layer on the frozen sample.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
