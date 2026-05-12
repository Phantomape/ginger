# exp-20260512-005 Space perfect-TQS trend target

- Decision: `rejected_space_perfect_tqs_trend_target`
- Single variable: target ATR multiple for official Space trend signals whose TQS is capped at 1.0.
- Best variant: `perfect_tqs_target_8_0`
- Aggregate EV delta vs accepted: `+0.3468`
- Aggregate PnL delta vs accepted: `$-1,832.25`

## Sweep

| Variant | Target ATR | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp004_stack | accepted | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| perfect_tqs_target_6_0 | 6.0 | fail | -0.9748 | -23,253.21 | 0 | 2 | 12 |
| perfect_tqs_target_7_0 | 7.0 | fail | -0.3441 | -12,516.76 | 0 | 1 | 12 |
| perfect_tqs_target_8_0 | 8.0 | fail | +0.3468 | -1,832.25 | 1 | 1 | 12 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Perfect-TQS target signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0287 | 5.0287 | +0.0000 | 106,092.97 | 106,092.97 | +0.00 | 23 | 0.0650 | 0.8070 | 3 |
| mid_weak | 5.3999 | 6.0448 | +0.6449 | 122,166.69 | 130,843.70 | +8,677.01 | 25 | 0.0471 | 0.7606 | 4 |
| old_thin | 1.0800 | 0.7819 | -0.2981 | 59,997.03 | 49,487.77 | -10,509.26 | 23 | 0.1056 | 0.9054 | 5 |

## Interpretation

Wider trend targets for the capped/perfect TQS Space bucket did not beat the accepted exp-20260512-004 stack under the three-window gate. The current evidence supports quality-conditioned risk, not another same-sample target-width extension.
