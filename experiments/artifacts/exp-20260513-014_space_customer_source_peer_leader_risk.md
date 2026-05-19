# exp-20260513-014 Space customer-source peer-leader risk

- Decision: `accepted_default_off_space_customer_source_peer_leader_risk`
- Single variable: risk scalar for official Space customer_win source signals that are also peer momentum leaders.
- Best variant: `customer_source_peer_leader_1_1`
- Aggregate EV delta vs accepted: `+0.2687`
- Aggregate PnL delta vs accepted: `$+5,712.63`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| customer_source_peer_leader_0_75 | 0.750 | fail | -0.5397 | -11,083.19 | 0 | 2 | 8 |
| customer_source_peer_leader_0_9 | 0.900 | fail | -0.2553 | -5,318.75 | 0 | 2 | 8 |
| customer_source_peer_leader_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 8 |
| customer_source_peer_leader_1_025 | 1.025 | fail | +0.0466 | +1,295.33 | 1 | 1 | 8 |
| customer_source_peer_leader_1_05 | 1.050 | pass | +0.1275 | +2,806.05 | 2 | 0 | 8 |
| customer_source_peer_leader_1_075 | 1.075 | pass | +0.1898 | +4,286.17 | 2 | 0 | 8 |
| customer_source_peer_leader_1_1 | 1.100 | pass | +0.2687 | +5,712.63 | 2 | 0 | 8 |
| customer_source_peer_leader_1_25 | 1.250 | fail | +0.6235 | +13,912.85 | 2 | 0 | 8 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Source-peer-leader signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0447 | 6.0447 | +0.0000 | 131,975.34 | 131,975.34 | +0.00 | 22 | 0.0898 | 0.7931 | 1 |
| mid_weak | 8.9165 | 9.1692 | +0.2527 | 183,086.66 | 187,512.08 | +4,425.42 | 24 | 0.0472 | 0.7183 | 3 |
| old_thin | 1.4528 | 1.4688 | +0.0160 | 77,686.95 | 78,974.16 | +1,287.21 | 24 | 0.1430 | 0.8919 | 4 |

## Field Checks

{"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "missing_required_fields": [], "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"ASTS": {"event_fields": ["customer_win"], "event_ids": ["asts_fcc_d2d_authorization_20260421"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_regulatory_release"]}, "LUNR": {"event_fields": ["customer_win", "government_space_contract"], "event_ids": ["lunr_nasa_clps_20260324"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["official_or_primary_release"]}, "RKLB": {"event_fields": ["customer_win"], "event_ids": ["rklb_record_backlog_launch_deal_20260507"], "semantic_buckets": ["fundamental_contract_regulatory"], "source_types": ["company_release"]}}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_event_field": "customer_win", "target_source_types": ["official_or_primary_release", "official_regulatory_release", "company_release"], "target_tickers": ["ASTS", "LUNR", "RKLB"]}

{"field": "space_peer_momentum_state", "passed": true, "sample_runtime_values": [{"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.173417, "space_peer_momentum_state": "leader", "strategy": "breakout_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.0954, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.225517, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.173417, "space_peer_momentum_state": "leader", "strategy": "breakout_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.03995, "space_peer_momentum_state": "nonleader", "strategy": "breakout_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.0954, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.225517, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.15895, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "mid_weak"}, {"space_peer_excess_momentum_20d_pct": -0.1677, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "ASTS", "window": "mid_weak"}], "source": "accepted Space basket momentum enrichment from exp-20260511-115 stack", "state_counts": {"leader": 42, "nonleader": 27}}

## Interpretation

The source-qualified peer-leader scalar improved the accepted default-off Space stack under the three-window gate. Promotion must stay shared and metadata-only with live Space slots at zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
