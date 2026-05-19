# exp-20260510-004: Breakout Add-on Upper Bound

Decision: `rejected_upper_bound`

## Gate 4

- Passed: `False`
- Aggregate EV delta: `0.3017`
- Aggregate PnL delta: `$5843.77`
- EV improved/regressed windows: `3` / `0`
- Single-event positive contribution share: `0.3346`

## Window Results

| Window | EV before | EV upper-bound | PnL upper-bound delta | Sharpe delta | DD delta | Eligible add-ons |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.3264 | 3880.9 | 0.09 | -0.0002 | 5 |
| mid_weak | 1.6195 | 1.6416 | 1036.72 | -0.01 | 0.0 | 1 |
| old_thin | 0.3583 | 0.3789 | 926.15 | 0.03 | -0.0006 | 1 |

## Interpretation

Rejected: even the optimistic upper bound for filling all unfilled breakout_long follow-through add-on shares did not clear the EV-first three-window Gate 4 and/or sample concentration guard. Do not build a production adapter for this cohort without new forward evidence.

Production impact: no production/default strategy path changed. A positive future version would require a shared run/backtester policy; this upper-bound failed before that step.
