# exp-20260512-038 Space official customer-source risk

- Decision: `accepted_default_off_space_official_customer_source_risk`
- Single variable: risk scalar for official Space signals whose event seed profile has `customer_win` from official/regulatory/company sources.
- Best variant: `official_customer_source_1_1`
- Aggregate EV delta vs accepted: `+0.5354`
- Aggregate PnL delta vs accepted: `$+10,864.99`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| official_customer_source_0_75 | 0.75 | fail | -1.5417 | -30,200.00 | 0 | 3 | 15 |
| official_customer_source_0_9 | 0.90 | fail | -0.5537 | -10,963.68 | 0 | 3 | 15 |
| official_customer_source_1_1 | 1.10 | pass | +0.5354 | +10,864.99 | 3 | 0 | 15 |
| official_customer_source_1_25 | 1.25 | fail | +1.3537 | +27,782.09 | 3 | 0 | 15 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Source signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.4641 | 5.5797 | +0.1156 | 116,007.29 | 118,973.13 | +2,965.84 | 22 | 0.0787 | 0.7931 | 2 |
| mid_weak | 6.2911 | 6.7018 | +0.4107 | 136,167.44 | 143,204.97 | +7,037.53 | 24 | 0.0471 | 0.7746 | 9 |
| old_thin | 1.2159 | 1.2250 | +0.0091 | 66,075.23 | 66,936.85 | +861.62 | 24 | 0.1197 | 0.8919 | 4 |

## Field Check

{"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "missing_required_fields": [], "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"ASTS": {"event_fields": ["customer_win"], "event_ids": ["asts_fcc_d2d_authorization_20260421"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_regulatory_release"]}, "LUNR": {"event_fields": ["customer_win", "government_space_contract"], "event_ids": ["lunr_nasa_clps_20260324"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_or_primary_release"]}, "RKLB": {"event_fields": ["customer_win"], "event_ids": ["rklb_record_backlog_launch_deal_20260507"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["company_release"]}}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_event_field": "customer_win", "target_source_types": ["official_or_primary_release", "official_regulatory_release", "company_release"], "target_tickers": ["ASTS", "LUNR", "RKLB"]}

## Interpretation

The official customer-source risk scalar improved the accepted default-off Space stack under the three-window gate. Promotion must be wired through shared production-visible source metadata only; live Space slots remain zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
