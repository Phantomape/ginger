# exp-20260505-006 Active-Position Sector Cap

## Result

Rejected. Counting already-open position sectors inside the entry sector cap reduced capital deployment in the two windows where it fired and did not improve old_thin.

| window | EV before | EV after | PnL delta | Sharpe delta | Win-rate delta | Trades delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.1766 | -4384.20 | -0.07 | -0.0117 | -1.0 |
| mid_weak | 1.4415 | 0.9517 | -14349.99 | -0.28 | -0.0476 | 0.0 |
| old_thin | 0.3179 | 0.3179 | 0.00 | 0.00 | 0.0000 | 0.0 |

## Decision

- Do not promote active-position sector counting into the entry sector cap.
- Do not retry nearby sector-crowding entry filters without candidate-level replacement evidence.
- The current same-day sector cap is preserving useful clustered winners despite apparent concentration risk.
