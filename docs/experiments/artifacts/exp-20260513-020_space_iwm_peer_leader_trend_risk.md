# exp-20260513-020 Space IWM peer-leader trend risk

- decision: `accepted_default_off_space_iwm_peer_leader_trend_risk`
- best variant: `iwm_peer_leader_trend_1_15`
- aggregate EV delta: `+0.7810`
- aggregate PnL delta: `$+17,229.17`

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Target signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0447 | 6.0447 | +0.0000 | 131,975.34 | 131,975.34 | +0.00 | 22 | 0.0898 | 0.7931 | 2 |
| mid_weak | 9.3164 | 9.9541 | +0.6377 | 190,521.27 | 201,501.32 | +10,980.05 | 24 | 0.0503 | 0.7042 | 5 |
| old_thin | 1.5276 | 1.6709 | +0.1433 | 81,693.21 | 87,942.33 | +6,249.12 | 24 | 0.1518 | 0.8919 | 4 |

## Field Checks

{"fields": ["space_iwm_relative_state", "space_iwm_excess_vs_spy_20d_pct", "space_peer_momentum_state", "space_peer_excess_momentum_20d_pct", "strategy"], "iwm_relative_state_counts": {"smallcap_laggard": 14, "smallcap_leader": 55}, "passed": true, "peer_momentum_state_counts": {"leader": 42, "nonleader": 27}, "sample_trend_rows_with_peer_state": [{"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "trade_quality_score": 0.956}, {"space_peer_excess_momentum_20d_pct": 0.0954, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "trade_quality_score": 1.0}, {"space_peer_excess_momentum_20d_pct": 0.225517, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "trade_quality_score": 1.0}, {"space_peer_excess_momentum_20d_pct": -0.044117, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "trade_quality_score": 0.956}, {"space_peer_excess_momentum_20d_pct": 0.0954, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "trade_quality_score": 1.0}, {"space_peer_excess_momentum_20d_pct": 0.225517, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "PL", "trade_quality_score": 1.0}, {"space_peer_excess_momentum_20d_pct": -0.15895, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "trade_quality_score": 0.956}, {"space_peer_excess_momentum_20d_pct": -0.1677, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "ASTS", "trade_quality_score": 0.956}, {"space_peer_excess_momentum_20d_pct": -0.085183, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "BKSY", "trade_quality_score": 0.956}, {"space_peer_excess_momentum_20d_pct": -0.126333, "space_peer_momentum_state": "nonleader", "strategy": "trend_long", "ticker": "RKLB", "trade_quality_score": 1.0}, {"space_peer_excess_momentum_20d_pct": 0.136167, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "BKSY", "trade_quality_score": 0.956}, {"space_peer_excess_momentum_20d_pct": 0.149083, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "BKSY", "trade_quality_score": 0.956}, {"space_peer_excess_momentum_20d_pct": 0.11305, "space_peer_momentum_state": "leader", "strategy": "trend_long", "ticker": "RDW", "trade_quality_score": 0.956}]}

## Interpretation

The IWM-relative peer-leader trend scalar improved the accepted default-off Space stack under the three-window gate. Promotion must stay shared and metadata-only with live Space slots at zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
