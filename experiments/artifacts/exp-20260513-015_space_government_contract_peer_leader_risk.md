# exp-20260513-015 Space government-contract peer-leader risk

- Decision: `accepted_default_off_space_government_contract_peer_leader_risk`
- Single variable: risk scalar for official Space government-contract signals that are also peer momentum leaders.
- Best variant: `government_contract_peer_leader_1_05`
- Aggregate EV delta vs accepted: `+0.2060`
- Aggregate PnL delta vs accepted: `$+5,728.24`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| government_contract_peer_leader_0_75 | 0.750 | fail | -0.9890 | -26,994.37 | 0 | 2 | 20 |
| government_contract_peer_leader_0_9 | 0.900 | fail | -0.4229 | -11,023.54 | 0 | 2 | 20 |
| government_contract_peer_leader_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 19 |
| government_contract_peer_leader_1_025 | 1.025 | pass | +0.1079 | +2,920.17 | 2 | 0 | 19 |
| government_contract_peer_leader_1_05 | 1.050 | pass | +0.2060 | +5,728.24 | 2 | 0 | 18 |
| government_contract_peer_leader_1_075 | 1.075 | fail | +0.3249 | +8,616.61 | 2 | 0 | 18 |
| government_contract_peer_leader_1_1 | 1.100 | fail | +0.4327 | +11,486.27 | 2 | 0 | 18 |
| government_contract_peer_leader_1_25 | 1.250 | fail | +1.0868 | +29,121.47 | 2 | 0 | 18 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Gov-contract peer-leader signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0447 | 6.0447 | +0.0000 | 131,975.34 | 131,975.34 | +0.00 | 22 | 0.0898 | 0.7931 | 3 |
| mid_weak | 9.1692 | 9.3164 | +0.1472 | 187,512.08 | 190,521.27 | +3,009.19 | 24 | 0.0472 | 0.7042 | 7 |
| old_thin | 1.4688 | 1.5276 | +0.0588 | 78,974.16 | 81,693.21 | +2,719.05 | 24 | 0.1474 | 0.8919 | 8 |

## Field Checks

{"event_field_counts": {"customer_win": 3, "government_space_contract": 2, "spacex_ipo_proxy": 1, "uap_attention_spike": 1}, "event_seed_count": 6, "excluded_semantic_buckets": ["attention_only"], "missing_required_fields": [], "passed": true, "path": "data\\space_catalyst_event_seeds.jsonl", "profiles": {"ASTS": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "BKSY": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "LUNR": {"event_count": 2, "event_fields": ["customer_win", "government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424", "lunr_nasa_clps_20260324"], "semantic_buckets": ["defense_budget_theme", "fundamental_contract_regulatory"], "source_types": ["official_government_release", "official_or_primary_release"]}, "PL": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "RDW": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}, "RKLB": {"event_count": 1, "event_fields": ["government_space_contract"], "event_ids": ["golden_dome_sbi_awards_20260424"], "semantic_buckets": ["defense_budget_theme"], "source_types": ["official_government_release"]}}, "semantic_bucket_counts": {"attention_only": 2, "defense_budget_theme": 1, "fundamental_contract_regulatory": 3}, "source_type_counts": {"company_release": 1, "market_attention_proxy": 1, "official_attention_release": 1, "official_government_release": 1, "official_or_primary_release": 1, "official_regulatory_release": 1}, "target_definition": "official Space ticker with government_space_contract from an official non-attention source", "target_event_field": "government_space_contract", "target_source_types": ["official_or_primary_release", "official_government_release"], "target_tickers": ["ASTS", "BKSY", "LUNR", "PL", "RDW", "RKLB"]}

{"field": "space_peer_momentum_state", "passed": true, "sample_runtime_values": [{"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.173417, "space_peer_momentum_state": "leader", "strategy": "breakout_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.0954, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.225517, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.173417, "space_peer_momentum_state": "leader", "strategy": "breakout_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.03995, "space_peer_momentum_state": "nonleader", "strategy": "breakout_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.0954, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": 0.225517, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "window": "late_strong"}, {"space_peer_excess_momentum_20d_pct": -0.15895, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "window": "mid_weak"}, {"space_peer_excess_momentum_20d_pct": -0.1677, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "ASTS", "window": "mid_weak"}], "source": "accepted Space basket momentum enrichment from exp-20260511-115 stack", "state_counts": {"leader": 42, "nonleader": 27}}

## Interpretation

The government-contract plus peer-leader scalar improved the accepted default-off Space stack under the three-window gate. Promotion must stay shared and metadata-only with live Space slots at zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
