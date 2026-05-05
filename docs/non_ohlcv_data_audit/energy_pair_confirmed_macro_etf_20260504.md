# exp-20260504-045 Energy pair-confirmed macro ETF

- decision: `rejected`
- best variant: `xle_uso_pair_confirmed`
- aggregate EV delta: `0.96`
- aggregate PnL delta: `$1665.95`
- EV improved windows: `1`
- EV regressed windows: `2`
- production impact: `experiment_only_no_live_or_default_backtest_strategy_change`

## Window Summary

| Window | Before EV | After EV | EV delta | Before PnL | After PnL | PnL delta | Extra trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 4.7927 | 1.3736 | 78600.33 | 94527.41 | 15927.08 | 4 |
| mid_weak | 1.4415 | 1.079 | -0.3625 | 55015.08 | 43161.91 | -11853.17 | 2 |
| old_thin | 0.3179 | 0.2668 | -0.0511 | 24642.07 | 22234.11 | -2407.96 | 1 |

## Interpretation

Rejected. Pair-confirming XLE/USO reduced ticker-list-only noise but did not clear the three-window materiality gate without EV regression.

This is an experiment-only replay. It does not alter production entries, default backtests, ranking, sizing, universe membership, or orders.
