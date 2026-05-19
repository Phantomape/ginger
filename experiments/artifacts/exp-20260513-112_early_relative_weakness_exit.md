# exp-20260513-112 Early Relative-Weakness Exit

Decision: `rejected_early_relative_weakness_exit`.

Single variable: next-open full exit for fresh core positions with negative day-3 holding return and <= -3pp return versus SPY.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3768 | +0.0000 | $99,695.99 | $99,695.99 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 1.6788 | 1.6788 | +0.0000 | $62,644.67 | $62,644.67 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.4292 | 0.3884 | -0.0408 | $31,563.29 | $29,877.18 | $-1,686.11 | -0.0001 | 0.9138 | 3 |

## Aggregate

- Expected value score delta: -0.0408
- Total PnL delta: $-1,686.11
- Executed early exits: 3
- Max drawdown worse: +0.0000

Interpretation: The early relative-weakness full exit did not clear the canonical three-window Gate 4.

Production impact: accepted only if the shared production_parity helper is wired into quant/run.py and covered by parity tests.
