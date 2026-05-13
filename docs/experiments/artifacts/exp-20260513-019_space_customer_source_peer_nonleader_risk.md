# exp-20260513-019 Space customer-source peer-nonleader risk

- Decision: `rejected_space_customer_source_peer_nonleader_risk`
- Single variable: risk scalar for official Space customer_win source signals whose ticker is not a peer momentum leader.
- Best variant: `customer_source_peer_nonleader_1_25`
- Aggregate EV delta vs accepted: `+0.1320`
- Aggregate PnL delta vs accepted: `$+10,822.63`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| customer_source_peer_nonleader_0_5 | 0.500 | fail | -3.9502 | -77,131.34 | 0 | 2 | 6 |
| customer_source_peer_nonleader_0_75 | 0.750 | fail | -2.2480 | -44,825.32 | 0 | 2 | 6 |
| customer_source_peer_nonleader_0_9 | 0.900 | fail | -0.4728 | -10,882.14 | 0 | 2 | 6 |
| customer_source_peer_nonleader_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 6 |
| customer_source_peer_nonleader_1_05 | 1.050 | fail | -0.7190 | -10,461.97 | 1 | 1 | 6 |
| customer_source_peer_nonleader_1_1 | 1.100 | fail | -0.5207 | -5,361.37 | 1 | 1 | 6 |
| customer_source_peer_nonleader_1_25 | 1.250 | fail | +0.1320 | +10,822.63 | 1 | 1 | 6 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Source-nonleader signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0447 | 6.3308 | +0.2861 | 131,975.34 | 143,229.70 | +11,254.36 | 22 | 0.1001 | 0.7586 | 1 |
| mid_weak | 9.3164 | 9.1623 | -0.1541 | 190,521.27 | 190,089.54 | -431.73 | 23 | 0.0637 | 0.6533 | 5 |
| old_thin | 1.5276 | 1.5276 | +0.0000 | 81,693.21 | 81,693.21 | +0.00 | 24 | 0.1474 | 0.8919 | 0 |

## Field Checks

{"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "missing_required_fields": [], "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"ASTS": {"event_fields": ["customer_win"], "event_ids": ["asts_fcc_d2d_authorization_20260421"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_regulatory_release"]}, "LUNR": {"event_fields": ["customer_win", "government_space_contract"], "event_ids": ["lunr_nasa_clps_20260324"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_or_primary_release"]}, "RKLB": {"event_fields": ["customer_win"], "event_ids": ["rklb_record_backlog_launch_deal_20260507"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["company_release"]}}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_event_field": "customer_win", "target_source_types": ["official_or_primary_release", "official_regulatory_release", "company_release"], "target_tickers": ["ASTS", "LUNR", "RKLB"]}

{"field": "space_peer_momentum_state", "passed": true, "sample_runtime_values": [{"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.173417, "space_peer_momentum_state": "leader", "strategy": "breakout_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.0954, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.225517, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.173417, "space_peer_momentum_state": "leader", "strategy": "breakout_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.03995, "space_peer_momentum_state": "nonleader", "strategy": "breakout_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.0954, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.225517, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.15895, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "mid_weak"}, {"space_peer_excess_momentum_20d_pct": -0.1677, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "ASTS", "window": "mid_weak"}], "source": "accepted Space basket momentum enrichment from exp-20260511-115 stack", "state_counts": {"leader": 42, "nonleader": 27}}

## Interpretation

The customer-source peer-nonleader scalar did not clear the three-window gate on top of exp-20260513-015. Keep the current customer-source and peer-leader helpers unchanged on these frozen snapshots.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
