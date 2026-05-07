# exp-20260506-032: Mid-Dispersion Trend Risk

Decision: `accepted_shared_policy`

## Baseline

| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.4191 | 78600.33 | 4.35 | 0.0541 | 0.7895 | 19 | 0.8039 |
| mid_weak | 1.4415 | 55015.08 | 2.62 | 0.0879 | 0.5238 | 21 | 0.7925 |
| old_thin | 0.3179 | 24642.07 | 1.29 | 0.0805 | 0.4091 | 22 | 0.9167 |

## Variant Summary

| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | PnL Windows + / - | Resized Signals | Touched Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mid_dispersion_trend_1_25x | True | 0.4487 | 9090.47 | 3/0 | 3/0 | 42 | 24 |
| mid_dispersion_trend_1_50x | False | 0.6313 | 13270.3 | 3/0 | 3/0 | 42 | 24 |
| mid_dispersion_trend_2_00x | False | 0.7173 | 17405.4 | 3/0 | 3/0 | 42 | 24 |

## Interpretation

The best variant `mid_dispersion_trend_1_25x` passed the three-window Gate 4 screen and was promoted into shared production/backtest policy. `risk_engine.enrich_signals` now computes the sector-dispersion state and `portfolio_engine.size_signals` applies the 1.25x trend allocation overlay.

Post-promotion canonical backtests matched the replayed best variant:

| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.7435 | 83562.53 | 4.48 | 0.0539 | 0.7895 | 19 | 0.8039 |
| mid_weak | 1.5478 | 57542.74 | 2.69 | 0.0879 | 0.5238 | 21 | 0.7925 |
| old_thin | 0.3359 | 26242.68 | 1.28 | 0.0905 | 0.4091 | 22 | 0.9167 |

Risk note: old_thin drawdown rose from 0.0805 to 0.0905, using the full 1 pp drawdown guardrail without exceeding it. Do not tune nearby mid-dispersion trend multipliers again without a new drawdown discriminator.

## Production Impact

- shared_policy_changed: true
- backtester_adapter_changed: true
- run_adapter_changed: true
- replay_only: false
- parity_test_added: true

Production and backtest both consume the same enriched `mid_sector_dispersion` field and sizing branch. Backtester attribution now reports `trend_mid_sector_dispersion_risk_multiplier_applied`.
