# exp-20260512-008 Space near-perfect TQS trend risk

- Decision: `accepted_default_off_space_near_perfect_tqs_trend_risk`
- Single variable: extra risk scalar for official Space trend_long signals with 0.95 <= TQS < 1.0.
- Best variant: `near_perfect_tqs_trend_1_1`
- Aggregate EV delta vs accepted: `+0.2392`
- Aggregate PnL delta vs accepted: `$+5,210.37`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp004_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| near_perfect_tqs_trend_1_1 | 1.10 | pass | +0.2392 | +5,210.37 | 3 | 0 | 8 |
| near_perfect_tqs_trend_1_25 | 1.25 | fail | +0.5860 | +12,824.05 | 3 | 0 | 8 |
| near_perfect_tqs_trend_1_5 | 1.50 | fail | +1.9797 | +40,751.29 | 3 | 0 | 8 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Near-perfect trend signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0287 | 5.1258 | +0.0971 | 106,092.97 | 108,141.30 | +2,048.33 | 23 | 0.0674 | 0.8070 | 1 |
| mid_weak | 5.3999 | 5.5269 | +0.1270 | 122,166.69 | 124,484.60 | +2,317.91 | 25 | 0.0471 | 0.7746 | 6 |
| old_thin | 1.0800 | 1.0951 | +0.0151 | 59,997.03 | 60,841.16 | +844.13 | 24 | 0.1077 | 0.8919 | 1 |

## Interpretation

The near-perfect Space trend TQS bucket improved the accepted default-off Space stack under the three-window gate. Promotion should stay default-off metadata/helper only because Space live slots remain zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
