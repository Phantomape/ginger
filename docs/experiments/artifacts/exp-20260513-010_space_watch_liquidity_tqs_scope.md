# exp-20260513-010 Space watch-liquidity TQS scope

- Decision: `rejected_space_watch_liquidity_tqs_scope`
- Single variable: TQS bucket scope for the accepted watch-liquidity 1.10x top-up.
- Best variant: `watch_liquidity_tqs_near_perfect_or_better`
- Aggregate EV delta vs accepted: `+0.0000`
- Aggregate PnL delta vs accepted: `$+0.00`

## Sweep

| Variant | TQS scope | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted | Out of scope |
|---|---|---|---:|---:|---:|---:|---:|---:|
| watch_liquidity_tqs_near_perfect_or_better | min=0.95 max=None | fail | +0.0000 | +0.00 | 0 | 0 | 17 | 4 |
| watch_liquidity_tqs_perfect_only | min=1.0 max=None | fail | -0.8951 | -17,058.22 | 0 | 2 | 8 | 13 |
| watch_liquidity_tqs_below_near_perfect | min=None max=0.95 | fail | -1.1381 | -22,135.56 | 0 | 2 | 4 | 17 |
| watch_liquidity_tqs_nonperfect | min=None max=1.0 | fail | -0.2586 | -5,270.74 | 0 | 2 | 13 | 8 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Adjusted | Out of scope |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.9589 | 5.9589 | +0.0000 | 128,977.06 | 128,977.06 | +0.00 | 22 | 0.0868 | 0.7931 | 2 | 1 |
| mid_weak | 8.5242 | 8.5242 | +0.0000 | 176,120.07 | 176,120.07 | +0.00 | 24 | 0.0472 | 0.7606 | 10 | 2 |
| old_thin | 1.4352 | 1.4352 | +0.0000 | 76,753.86 | 76,753.86 | +0.00 | 24 | 0.1346 | 0.8919 | 5 | 1 |

## Field Check

{"field": "liquidity_tier", "missing_liquidity_tier": [], "passed": true, "path": "data/universe_registry.json", "target_liquidity_tier": "watch", "target_tickers": ["ASTS", "BKSY", "LUNR", "PL", "RDW"], "tiers": {"ASTS": "watch", "BKSY": "watch", "LUNR": "watch", "PL": "watch", "RDW": "watch", "RKLB": "ok"}}

## Interpretation

Restricting the accepted watch-liquidity top-up by established TQS bucket did not clear the three-window gate versus exp-20260512-112. Keep the current all-TQS watch-liquidity helper and do not retry nearby TQS-scope splits on the same frozen snapshots without forward evidence.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
