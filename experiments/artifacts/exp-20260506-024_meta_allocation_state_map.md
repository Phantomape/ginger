# exp-20260506-024: Meta-Allocation State Map

Decision: `observed_only`

## Three-Window Metrics

| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.4191 | 78600.33 | 4.35 | 0.0541 | 0.7895 | 19 | 0.8039 |
| mid_weak | 1.4415 | 55015.08 | 2.62 | 0.0879 | 0.5238 | 21 | 0.7925 |
| old_thin | 0.3179 | 24642.07 | 1.29 | 0.0805 | 0.4091 | 22 | 0.9167 |

## Positive Cohorts

| Window | Map | Cohort | Trades | Win rate | PnL |
| --- | --- | --- | ---: | ---: | ---: |
| late_strong | state_strategy | state.state_bucket=broad_rotation, strategy=breakout_long | 8 | 1.0 | 40322.11 |
| late_strong | state_sizing_family | state.state_bucket=broad_rotation, sizing_family=spy_relative_leader | 8 | 1.0 | 40322.11 |
| late_strong | breadth_strategy | state.breadth_bucket=mixed_breadth, strategy=breakout_long | 9 | 0.7778 | 37847.92 |
| mid_weak | breadth_strategy | state.breadth_bucket=broad_breadth, strategy=trend_long | 11 | 0.6364 | 33262.86 |
| late_strong | dispersion_strategy | state.dispersion_bucket=mid_sector_dispersion, strategy=breakout_long | 9 | 0.7778 | 31005.14 |
| mid_weak | state_strategy | state.state_bucket=balanced_risk_on, strategy=trend_long | 10 | 0.5 | 28847.79 |
| old_thin | dispersion_strategy | state.dispersion_bucket=mid_sector_dispersion, strategy=trend_long | 11 | 0.5455 | 22880.8 |
| late_strong | state_sector | state.state_bucket=broad_rotation, sector=Energy | 3 | 1.0 | 21957.74 |

## Negative Cohorts

| Window | Map | Cohort | Trades | Win rate | PnL |
| --- | --- | --- | ---: | ---: | ---: |
| old_thin | dispersion_strategy | state.dispersion_bucket=high_sector_dispersion, strategy=trend_long | 4 | 0.0 | -4407.85 |
| old_thin | breadth_strategy | state.breadth_bucket=thin_breadth, strategy=trend_long | 2 | 0.0 | -2059.12 |
| old_thin | breadth_strategy | state.breadth_bucket=broad_breadth, strategy=breakout_long | 2 | 0.0 | -1834.17 |
| old_thin | state_sector | state.state_bucket=balanced_risk_on, sector=Technology | 4 | 0.25 | -1499.11 |
| late_strong | state_sector | state.state_bucket=balanced_risk_on, sector=Energy | 3 | 0.3333 | -620.97 |
| mid_weak | state_sector | state.state_bucket=balanced_risk_on, sector=Healthcare | 2 | 0.0 | -548.43 |
| mid_weak | state_sizing_family | state.state_bucket=balanced_risk_on, sizing_family=trend_tech_dte_risk_multiplier_applied+trend_tech_near_high_risk_multiplier_applied | 2 | 0.0 | -96.71 |

## Interpretation

This is an alpha-search map, not a promoted rule. The strongest recurring positive surface remains state-aware capital allocation, but the map does not justify another simple SPY-relative leader, broad ETF, or raw collision ranking retest. Any executable follow-up should target a cohort that appears in at least two windows and is implemented in shared run/backtester policy.

## Next Alpha Candidate

Use this map to test a single shared-policy allocation rule only if the same state/sleeve cohort has enough touched trades in at least two windows; otherwise continue with event-overlay forward evidence rather than local threshold mining.

