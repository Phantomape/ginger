# exp-20260506-031: Broad-Rotation Trend Risk

Decision: `rejected`

## Baseline

| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.4191 | 78600.33 | 4.35 | 0.0541 | 0.7895 | 19 | 0.8039 |
| mid_weak | 1.4415 | 55015.08 | 2.62 | 0.0879 | 0.5238 | 21 | 0.7925 |
| old_thin | 0.3179 | 24642.07 | 1.29 | 0.0805 | 0.4091 | 22 | 0.9167 |

## Variant Summary

| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | PnL Windows + / - | Resized Signals | Touched Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| broad_rotation_trend_1_25x | False | 0.0518 | 5090.81 | 2/0 | 2/0 | 25 | 11 |
| broad_rotation_trend_1_50x | False | 0.103 | 9853.49 | 2/0 | 2/0 | 25 | 11 |
| broad_rotation_trend_2_00x | False | 0.1685 | 13607.33 | 2/1 | 2/1 | 25 | 11 |

## Interpretation

Broad-rotation trend risk expansion did not pass the three-window promotion gate. The best EV variant `broad_rotation_trend_2_00x` changed aggregate EV by 0.1685 and PnL by 13607.33, but the stronger variants paid for the PnL with worse mid_weak drawdown and lower Sharpe. This does not justify a new state-aware trend sizing branch.

## Production Impact

- shared_policy_changed: false
- backtester_adapter_changed: false
- run_adapter_changed: false
- replay_only: false
- parity_test_added: false

No trading rule was promoted by this replay script. A passing result must move the broad-rotation feature and sizing overlay into shared production/backtest policy before live behavior changes.
