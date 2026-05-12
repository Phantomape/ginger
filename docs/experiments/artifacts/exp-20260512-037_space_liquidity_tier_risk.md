# exp-20260512-037 Space liquidity-tier risk

- Decision: `accepted_default_off_space_liquidity_tier_risk`
- Single variable: risk scalar for official Space signals whose universe-registry `liquidity_tier` is `ok`.
- Best variant: `liquidity_ok_1_1`
- Aggregate EV delta vs accepted: `+0.2390`
- Aggregate PnL delta vs accepted: `$+5,789.02`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| liquidity_ok_0_75 | 0.75 | fail | -0.6654 | -14,433.47 | 0 | 3 | 9 |
| liquidity_ok_1_1 | 1.10 | pass | +0.2390 | +5,789.02 | 3 | 0 | 9 |
| liquidity_ok_1_25 | 1.25 | fail | +0.5786 | +14,381.94 | 3 | 0 | 9 |
| liquidity_ok_1_5 | 1.50 | fail | +1.1157 | +28,789.76 | 3 | 0 | 9 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Liquidity-tier signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.3558 | 5.4641 | +0.1083 | 113,231.15 | 116,007.29 | +2,776.14 | 22 | 0.0756 | 0.7931 | 2 |
| mid_weak | 6.1751 | 6.2911 | +0.1160 | 133,953.19 | 136,167.44 | +2,214.25 | 24 | 0.0471 | 0.7746 | 4 |
| old_thin | 1.2012 | 1.2159 | +0.0147 | 65,276.60 | 66,075.23 | +798.63 | 24 | 0.1161 | 0.8919 | 3 |

## Field Check

{"field": "liquidity_tier", "missing_liquidity_tier": [], "passed": true, "path": "data/universe_registry.json", "target_liquidity_tier": "ok", "target_tickers": ["RKLB"], "tiers": {"ASTS": "watch", "BKSY": "watch", "LUNR": "watch", "PL": "watch", "RDW": "watch", "RKLB": "ok"}}

## Interpretation

The official Space `liquidity_tier=ok` anchor risk scalar improved the accepted default-off Space stack under the three-window gate. Promotion must remain shared production-visible metadata/helper wiring only; live Space slots remain zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
