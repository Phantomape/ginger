# exp-20260506-029: High-Dispersion Trend Risk

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
| trend_high_dispersion_0_50x | False | -0.5324 | -18617.7 | 1/2 | 1/2 | 16 | 10 |
| trend_high_dispersion_0_25x | False | -0.8336 | -25962.54 | 1/2 | 1/2 | 16 | 10 |
| trend_high_dispersion_0_00x | False | -0.4713 | -30013.99 | 0/3 | 0/3 | 23 | 0 |

## Interpretation

High-sector-dispersion trend de-risking did not pass Gate 4. The best variant `trend_high_dispersion_0_00x` changed aggregate EV by -0.4713 and PnL by -30013.99; it does not justify a new state-aware trend sizing branch.

## Production Impact

- shared_policy_changed: false
- backtester_adapter_changed: false
- run_adapter_changed: false
- replay_only: false
- parity_test_added: false

No trading rule was promoted. If a future retry passes Gate 4, the dispersion feature must move into shared enrichment before production use.
