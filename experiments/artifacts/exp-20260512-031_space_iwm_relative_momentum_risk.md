# exp-20260512-031 Space IWM-relative momentum risk

- Decision: `accepted_default_off_space_iwm_relative_momentum_risk`
- Single variable: risk scalar for official Space signals by IWM-vs-SPY 20d momentum state.
- Best variant: `smallcap_leader_1_10`
- Aggregate EV delta vs accepted: `+0.4142`
- Aggregate PnL delta vs accepted: `$+9,550.74`

## Sweep

| Variant | State scalars | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---|---|---:|---:|---:|---:|---:|
| accepted_exp013_stack | `{}` | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| smallcap_laggard_0_50 | `{'smallcap_laggard': 0.5}` | fail | -0.7935 | -16,355.26 | 0 | 2 | 5 |
| smallcap_laggard_0_75 | `{'smallcap_laggard': 0.75}` | fail | -0.4055 | -8,336.89 | 0 | 2 | 5 |
| smallcap_leader_1_10 | `{'smallcap_leader': 1.1}` | pass | +0.4142 | +9,550.74 | 3 | 0 | 25 |
| smallcap_leader_1_25 | `{'smallcap_leader': 1.25}` | fail | +1.0267 | +23,112.84 | 3 | 0 | 25 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | IWM-state adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1438 | 5.2510 | +0.1072 | 108,516.68 | 110,784.02 | +2,267.34 | 22 | 0.0699 | 0.8103 | 5 |
| mid_weak | 5.8386 | 6.0524 | +0.2138 | 128,318.68 | 131,860.36 | +3,541.68 | 24 | 0.0471 | 0.7746 | 12 |
| old_thin | 1.0951 | 1.1883 | +0.0932 | 60,841.16 | 64,582.88 | +3,741.72 | 24 | 0.1101 | 0.8919 | 8 |

## Interpretation

IWM-vs-SPY small-cap relative momentum improved the accepted default-off Space stack under the three-window gate. Promotion must remain shared default-off metadata/helper only because Space live slots remain zero.

## Production Impact

{"alters_candidate_ranking": false, "alters_orders": false, "alters_signal_generation": false, "alters_sizing": false, "backtester_adapter_changed": false, "daily_report_metadata_changed": true, "live_slots": 0, "live_slots_changed": false, "parity_test_added": true, "replay_only": true, "run_adapter_changed": true, "shared_policy_changed": true}
