# exp-20260510-009: Trend Add-on Upper Bound

Decision: `rejected_upper_bound`

## Gate 4

- Passed: `False`
- Aggregate EV delta: `0.0796`
- Aggregate PnL delta: `$2144.24`
- EV improved/regressed windows: `3` / `0`
- Single-ticker positive contribution share: `0.4298`

## Window Results

| Window | EV before | EV upper-bound | PnL upper-bound delta | Sharpe delta | DD delta | Eligible add-ons |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.1033 | 597.57 | 0.01 | 0.0 | 2 |
| mid_weak | 1.6195 | 1.6315 | 219.72 | 0.01 | 0.0 | 1 |
| old_thin | 0.3583 | 0.39 | 1326.95 | 0.05 | -0.0009 | 3 |

## Interpretation

Rejected: even the optimistic upper bound for filling all unfilled trend_long follow-through add-on shares did not clear the EV-first three-window Gate 4 and/or sample concentration guard. Do not spend production work on a trend-only add-on budget without new forward evidence.

Production impact: replay-only. No production/default strategy path changed. Any positive future version requires a shared run/backtester capital-allocation policy with explicit hard-risk semantics and parity tests.
