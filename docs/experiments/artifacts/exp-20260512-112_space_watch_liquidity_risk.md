# exp-20260512-112 Space watch-liquidity risk

- Decision: `accepted_default_off_space_watch_liquidity_risk`
- Single variable: risk scalar for official Space signals whose production registry `liquidity_tier` is `watch`.
- Best variant: `watch_liquidity_1_1`
- Aggregate EV delta vs accepted: `+1.1662`
- Aggregate PnL delta vs accepted: `$+22,708.16`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| watch_liquidity_0_5 | 0.500 | fail | -2.5115 | -54,202.39 | 0 | 2 | 21 |
| watch_liquidity_0_75 | 0.750 | fail | -1.1572 | -25,165.47 | 0 | 2 | 21 |
| watch_liquidity_0_9 | 0.900 | fail | -0.4628 | -10,190.41 | 0 | 2 | 21 |
| watch_liquidity_1_0 | 1.000 | fail | +0.0000 | +0.00 | 0 | 0 | 21 |
| watch_liquidity_1_05 | 1.050 | pass | +0.2108 | +4,829.72 | 2 | 0 | 21 |
| watch_liquidity_1_1 | 1.100 | pass | +1.1662 | +22,708.16 | 2 | 0 | 21 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Watch-liquidity signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.7713 | 5.7713 | +0.0000 | 124,917.02 | 124,917.02 | +0.00 | 22 | 0.0849 | 0.7931 | 3 |
| mid_weak | 7.2114 | 8.2798 | +1.0684 | 152,464.45 | 171,071.72 | +18,607.27 | 24 | 0.0472 | 0.7606 | 12 |
| old_thin | 1.2959 | 1.3937 | +0.0978 | 70,434.01 | 74,534.90 | +4,100.89 | 24 | 0.1310 | 0.8919 | 6 |

## Field Check

{"field": "liquidity_tier", "missing_liquidity_tier": [], "passed": true, "path": "data/universe_registry.json", "target_liquidity_tier": "watch", "target_tickers": ["ASTS", "BKSY", "LUNR", "PL", "RDW"], "tiers": {"ASTS": "watch", "BKSY": "watch", "LUNR": "watch", "PL": "watch", "RDW": "watch", "RKLB": "ok"}}

## Interpretation

The production registry `liquidity_tier=watch` scalar improved the accepted default-off Space stack under the three-window gate. Promotion must remain shared and metadata-only with live Space slots at zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
