# exp-20260512-113 Space watch-liquidity strategy scope

- Decision: `rejected_space_watch_liquidity_strategy_scope`
- Single variable: strategy scope for the accepted watch-liquidity 1.10x top-up.
- Best variant: `watch_liquidity_trend_only`
- Aggregate EV delta vs accepted: `+0.0181`
- Aggregate PnL delta vs accepted: `$+15.43`

## Sweep

| Variant | Scope | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted | Out of scope |
|---|---|---|---:|---:|---:|---:|---:|---:|
| watch_liquidity_trend_only | trend_long | fail | +0.0181 | +15.43 | 1 | 0 | 14 | 7 |
| watch_liquidity_breakout_only | breakout_long | fail | -1.1667 | -22,723.59 | 0 | 2 | 7 | 14 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Adjusted | Out of scope |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.7713 | 5.7713 | +0.0000 | 124,917.02 | 124,917.02 | +0.00 | 22 | 0.0849 | 0.7931 | 2 | 1 |
| mid_weak | 8.2798 | 8.2979 | +0.0181 | 171,071.72 | 171,087.15 | +15.43 | 24 | 0.0472 | 0.7606 | 8 | 4 |
| old_thin | 1.3937 | 1.3937 | +0.0000 | 74,534.90 | 74,534.90 | +0.00 | 24 | 0.1310 | 0.8919 | 4 | 2 |

## Field Check

{"field": "liquidity_tier", "missing_liquidity_tier": [], "passed": true, "path": "data/universe_registry.json", "target_liquidity_tier": "watch", "target_tickers": ["ASTS", "BKSY", "LUNR", "PL", "RDW"], "tiers": {"ASTS": "watch", "BKSY": "watch", "LUNR": "watch", "PL": "watch", "RDW": "watch", "RKLB": "ok"}}

## Interpretation

Restricting the accepted watch-liquidity top-up by strategy did not clear the three-window gate versus exp-20260512-112. Keep the current all-strategy watch-liquidity helper and do not retry nearby strategy scope splits on the same frozen snapshots without forward evidence.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
