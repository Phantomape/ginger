# exp-20260511-110 Space Breakout Stop Width

Decision: `rejected_space_breakout_stop_width`

Single variable: official Space `breakout_long` stop ATR multiple.

| Variant | Window | EV | EV delta vs accepted | PnL delta vs accepted | Trades | Max DD | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_exp105_stack | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| accepted_exp105_stack | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| accepted_exp105_stack | old_thin | 0.7694 | +0.0000 | +0.00 | 24 | 0.1012 | 0.8919 |
| breakout_stop_2_0 | late_strong | 5.0202 | +0.0693 | +2,812.42 | 21 | 0.0629 | 0.8070 |
| breakout_stop_2_0 | mid_weak | 3.8974 | -0.3225 | -464.29 | 26 | 0.0787 | 0.8169 |
| breakout_stop_2_0 | old_thin | 0.7474 | -0.0220 | -1,383.56 | 24 | 0.0988 | 0.8919 |
| breakout_stop_2_5 | late_strong | 5.0095 | +0.0586 | +2,818.50 | 21 | 0.0629 | 0.8070 |
| breakout_stop_2_5 | mid_weak | 3.5208 | -0.6991 | -12,524.50 | 25 | 0.0471 | 0.7887 |
| breakout_stop_2_5 | old_thin | 0.7336 | -0.0358 | -2,243.81 | 24 | 0.0994 | 0.8919 |

## Best Variant

- Best variant: `breakout_stop_2_0`
- Aggregate EV delta vs accepted: `-0.2752`
- Aggregate PnL delta vs accepted: `$+964.57`
- Gate 4 passed: `False`

## Interpretation

Wider official Space breakout stops did not beat the accepted exp-105 Space stack under the three-window gate. Space breakout fragility is not solved by simply giving breakouts more stop room.

## Production Impact

Default-off Space replay. Live Space slots remain zero; no core production orders, ranking, signal generation, or live sizing changed.
