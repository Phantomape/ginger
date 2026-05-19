# exp-20260512-040 Space defense-budget source risk

- Decision: `rejected_space_defense_budget_source_risk`
- Single variable: risk scalar for official Space signals whose event seed profile has `defense_budget_theme` + `government_space_contract` from an official government source.
- Best variant: `defense_budget_source_1_25`
- Aggregate EV delta vs accepted: `+2.3678`
- Aggregate PnL delta vs accepted: `$+52,220.36`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| defense_budget_source_0_75 | 0.75 | fail | -1.7996 | -41,208.92 | 0 | 3 | 30 |
| defense_budget_source_0_9 | 0.90 | fail | -0.7127 | -16,280.05 | 0 | 3 | 30 |
| defense_budget_source_1_1 | 1.10 | fail | +0.6927 | +16,082.42 | 3 | 0 | 30 |
| defense_budget_source_1_25 | 1.25 | fail | +2.3678 | +52,220.36 | 3 | 0 | 30 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Defense signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5797 | 5.8494 | +0.2697 | 118,973.13 | 127,160.60 | +8,187.47 | 22 | 0.0872 | 0.7931 | 5 |
| mid_weak | 6.7018 | 8.5549 | +1.8531 | 143,204.97 | 176,392.65 | +33,187.68 | 24 | 0.0471 | 0.7606 | 16 |
| old_thin | 1.2250 | 1.4700 | +0.2450 | 66,936.85 | 77,782.06 | +10,845.21 | 24 | 0.1351 | 0.8919 | 9 |

## Field Check

{"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "missing_required_fields": [], "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"ASTS": {"event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "BKSY": {"event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "LUNR": {"event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "PL": {"event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "RDW": {"event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "RKLB": {"event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}}, "semantic_bucket_counts": {"attention_only": 2, "defense_budget_theme": 1, "fundamental_contract_regulatory": 3}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_event_field": "government_space_contract", "target_semantic_bucket": "defense_budget_theme", "target_source_types": ["official_government_release"], "target_tickers": ["ASTS", "BKSY", "LUNR", "PL", "RDW", "RKLB"]}

## Interpretation

The official government defense-budget source scalar did not clear the three-window gate on top of exp-20260512-038. Do not retry adjacent defense-budget source scalars on these frozen snapshots; future Space work needs forward replacement value or a different catalyst-quality field.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
