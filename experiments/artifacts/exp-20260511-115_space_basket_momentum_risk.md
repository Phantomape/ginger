# exp-20260511-115 Space basket momentum risk

- Decision: `accepted_default_off_space_basket_momentum_risk`
- Single variable: extra risk scalar when official Space basket 20d momentum is positive.
- Best variant: `basket_positive_1_1`
- Aggregate EV delta vs accepted: `+0.3211`
- Aggregate PnL delta vs accepted: `$+8,033.03`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp105_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 30 |
| basket_positive_0_75 | 0.75 | fail | -0.8670 | -20,460.63 | 0 | 3 | 30 |
| basket_positive_1_1 | 1.10 | pass | +0.3211 | +8,033.03 | 3 | 0 | 30 |
| basket_positive_1_25 | 1.25 | fail | +0.8771 | +21,498.97 | 3 | 0 | 30 |
| basket_positive_1_5 | 1.50 | fail | +1.8800 | +45,632.47 | 3 | 0 | 30 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Basket-positive signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9490 | 5.0287 | +0.0797 | 104,408.84 | 106,092.97 | +1,684.13 | 23 | 0.0650 | 0.8070 | 5 |
| mid_weak | 4.2195 | 4.3941 | +0.1746 | 101,425.02 | 104,872.57 | +3,447.55 | 26 | 0.0471 | 0.8169 | 16 |
| old_thin | 0.7694 | 0.8362 | +0.0668 | 48,093.28 | 50,994.63 | +2,901.35 | 24 | 0.1056 | 0.8919 | 9 |

## Interpretation

Official Space basket positive 20d momentum improved the accepted exp-105 default-off Space stack under the three-window gate. Shared production-visible observation metadata/helper wiring was added default-off; live Space slots remain zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
