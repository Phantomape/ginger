# exp-20260507-001: Mid-Dispersion Breakout Risk

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
| mid_dispersion_breakout_1_25x | False | -0.025 | 2107.36 | 0/3 | 1/2 | 26 | 14 |
| mid_dispersion_breakout_1_50x | False | -0.0923 | 3872.57 | 0/3 | 1/2 | 26 | 14 |
| mid_dispersion_breakout_2_00x | False | -0.185 | 7622.3 | 0/3 | 1/2 | 26 | 14 |

## Interpretation

Mid-sector-dispersion breakout risk expansion did not pass the three-window promotion gate. The best EV variant `mid_dispersion_breakout_1_25x` changed aggregate EV by -0.025 and PnL by 2107.36; this does not justify a new breakout state-aware sizing branch.

## Production Impact

- shared_policy_changed: false
- backtester_adapter_changed: false
- run_adapter_changed: false
- replay_only: false
- parity_test_added: false

No trading rule was promoted by this replay script. A passing result must move the mid-dispersion breakout feature and sizing overlay into shared production/backtest policy before live behavior changes.
