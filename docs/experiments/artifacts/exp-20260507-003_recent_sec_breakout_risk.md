# exp-20260507-003: Recent SEC Filing Breakout Risk

Decision: `rejected`

## Baseline

| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.7435 | 83562.53 | 4.48 | 0.0539 | 0.7895 | 19 | 0.8039 |
| mid_weak | 1.5478 | 57542.74 | 2.69 | 0.0879 | 0.5238 | 21 | 0.7925 |
| old_thin | 0.3359 | 26242.68 | 1.28 | 0.0905 | 0.4091 | 22 | 0.9167 |

## Variant Summary

| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | PnL Windows + / - | Resized Signals | Touched Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| recent_sec_breakout_1_25x | False | 0.1344 | 4708.21 | 1/1 | 2/0 | 21 | 12 |
| recent_sec_breakout_1_50x | False | 0.0823 | 6781.57 | 1/1 | 1/1 | 21 | 12 |
| recent_sec_breakout_2_00x | False | -0.0267 | 10381.18 | 0/2 | 1/1 | 21 | 12 |

## Interpretation

Recent SEC filing breakout risk expansion did not pass the three-window promotion gate. The best EV variant `recent_sec_breakout_1_25x` changed aggregate EV by 0.1344 and PnL by 4708.21; this does not justify adding an event-confirmed breakout sizing branch.

## Production Impact

- shared_policy_changed: False
- backtester_adapter_changed: False
- run_adapter_changed: False
- replay_only: False
- parity_test_added: False
