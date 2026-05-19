# exp-20260512-032 Space launch/lunar theme-segment risk

- Decision: `accepted_default_off_space_launch_lunar_theme_risk`
- Single variable: risk scalar for official Space signals whose universe-registry `theme_segment` is `launch_lunar`.
- Best variant: `launch_lunar_1_1`
- Aggregate EV delta vs accepted: `+0.2404`
- Aggregate PnL delta vs accepted: `$+5,233.68`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| launch_lunar_0_75 | 0.75 | fail | -0.6216 | -13,220.37 | 0 | 3 | 11 |
| launch_lunar_0_9 | 0.90 | fail | -0.2493 | -5,500.48 | 0 | 3 | 11 |
| launch_lunar_1_1 | 1.10 | pass | +0.2404 | +5,233.68 | 3 | 0 | 11 |
| launch_lunar_1_25 | 1.25 | fail | +0.5542 | +13,167.50 | 3 | 0 | 11 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Launch/lunar signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.2510 | 5.3558 | +0.1048 | 110,784.02 | 113,231.15 | +2,447.13 | 22 | 0.0726 | 0.7931 | 2 |
| mid_weak | 6.0524 | 6.1751 | +0.1227 | 131,860.36 | 133,953.19 | +2,092.83 | 24 | 0.0471 | 0.7746 | 5 |
| old_thin | 1.1883 | 1.2012 | +0.0129 | 64,582.88 | 65,276.60 | +693.72 | 24 | 0.1128 | 0.8919 | 4 |

## Interpretation

The launch/lunar theme-segment risk scalar improved the accepted default-off Space stack under the three-window gate. Promotion must be shared production-visible metadata/helper wiring only; live Space slots remain zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
