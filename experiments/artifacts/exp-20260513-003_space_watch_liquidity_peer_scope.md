# exp-20260513-003 Space watch-liquidity peer scope

- Decision: `rejected_space_watch_liquidity_peer_scope`
- Single variable: peer-momentum scope for the accepted watch-liquidity 1.10x top-up.
- Best variant: `watch_liquidity_peer_nonleader_only`
- Aggregate EV delta vs accepted: `-0.3263`
- Aggregate PnL delta vs accepted: `$-8,133.37`

## Sweep

| Variant | Peer scope | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted | Out of scope |
|---|---|---|---:|---:|---:|---:|---:|---:|
| watch_liquidity_peer_leader_only | leader | fail | -0.9113 | -16,272.76 | 0 | 1 | 15 | 6 |
| watch_liquidity_peer_nonleader_only | nonleader | fail | -0.3263 | -8,133.37 | 0 | 2 | 6 | 15 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Adjusted | Out of scope |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.7713 | 5.7713 | +0.0000 | 124,917.02 | 124,917.02 | +0.00 | 22 | 0.0849 | 0.7931 | 1 | 2 |
| mid_weak | 8.2798 | 8.0513 | -0.2285 | 171,071.72 | 167,039.24 | -4,032.48 | 24 | 0.0471 | 0.7606 | 4 | 8 |
| old_thin | 1.3937 | 1.2959 | -0.0978 | 74,534.90 | 70,434.01 | -4,100.89 | 24 | 0.1285 | 0.8919 | 1 | 5 |

## Field Check

{"field": "liquidity_tier", "missing_liquidity_tier": [], "passed": true, "path": "data/universe_registry.json", "target_liquidity_tier": "watch", "target_tickers": ["ASTS", "BKSY", "LUNR", "PL", "RDW"], "tiers": {"ASTS": "watch", "BKSY": "watch", "LUNR": "watch", "PL": "watch", "RDW": "watch", "RKLB": "ok"}}

## Interpretation

Restricting the accepted watch-liquidity top-up by peer momentum state did not clear the three-window gate versus exp-20260512-112. Keep the current all-peer-state watch-liquidity helper and do not retry nearby peer-scope splits on the same frozen snapshots without forward evidence.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
