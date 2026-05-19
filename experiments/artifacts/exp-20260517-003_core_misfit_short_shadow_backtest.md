# exp-20260517-003 Core Misfit Short Shadow Backtest

Decision: `rejected_short_shadow`.

This is a replay-only historical short-shadow test. It does not change core, does not enable live shorting, and does not model borrow/locate constraints.

| Policy | Trades | PnL | Win rate | Positive windows | Worst trade | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| fixed_1d | 9 | $866.47 | 66.67% | 1 | -4.53% | 0.77% |
| fixed_3d | 9 | $3,687.84 | 77.78% | 1 | -4.53% | 0.75% |
| fixed_5d | 9 | $4,470.79 | 66.67% | 1 | -4.53% | 0.75% |
| fixed_10d | 9 | $6,079.66 | 66.67% | 1 | -4.53% | 0.73% |
| long_stop_target_mirror_10d | 9 | $2,613.18 | 77.78% | 1 | -4.53% | 0.76% |
| symmetric_1r_stop_10d | 9 | $2,542.48 | 66.67% | 1 | -6.37% | 0.82% |
| actual_long_exit | 9 | $4,385.29 | 88.89% | 1 | -0.82% | 0.14% |

Best policy: `fixed_10d`.
Shadow gate passed: `False`.
Live short promotable: `False`.
