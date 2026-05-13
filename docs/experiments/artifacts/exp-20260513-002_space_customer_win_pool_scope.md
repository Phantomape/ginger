# exp-20260513-002 Space customer-win pool scope

- Decision: `rejected_space_customer_win_pool_scope`
- Single variable: restrict official Space pool membership to tickers with direct `customer_win` event-seed coverage.
- Aggregate EV delta vs accepted: `-1.4476`
- Aggregate PnL delta vs accepted: `$-57,777.78`
- Included tickers: `ASTS, LUNR, RKLB`
- Excluded tickers: `BKSY, PL, RDW`

## Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.7713 | 5.7713 | +0.0000 | 124,917.02 | 124,917.02 | +0.00 | 22 | 0.0849 | 0.7818 |
| mid_weak | 8.2798 | 7.9043 | -0.3755 | 171,071.72 | 163,646.30 | -7,425.42 | 22 | 0.0471 | 0.7344 |
| old_thin | 1.3937 | 0.3216 | -1.0721 | 74,534.90 | 24,182.54 | -50,352.36 | 24 | 0.0853 | 0.8889 |

## Field Check

{"excluded_official_space_tickers": ["BKSY", "PL", "RDW"], "passed": true, "profiles": {"ASTS": {"event_fields": ["customer_win"], "event_ids": ["asts_fcc_d2d_authorization_20260421"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_regulatory_release"]}, "LUNR": {"event_fields": ["customer_win", "government_space_contract"], "event_ids": ["lunr_nasa_clps_20260324"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_or_primary_release"]}, "RKLB": {"event_fields": ["customer_win"], "event_ids": ["rklb_record_backlog_launch_deal_20260507"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["company_release"]}}, "source_gate_path": "data\\space_catalyst_event_seeds.jsonl", "target_event_field": "customer_win", "target_tickers": ["ASTS", "LUNR", "RKLB"]}

## Interpretation

Restricting the default-off Space pool to direct customer-win tickers did not beat the accepted exp-20260512-112 all-official operating pool. The evidence supports keeping non-customer official Space tickers in the observe-only pool and allocating risk by quality fields instead of pruning the pool.

## Production Impact

{"alters_candidate_pool_scope": false, "alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
