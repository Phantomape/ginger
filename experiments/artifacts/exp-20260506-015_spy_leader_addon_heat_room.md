# exp-20260506-015: SPY-leader add-on heat room

Decision: rejected

## Best Variant

- Best: `addon_heat_12pct`
- Gate 4 passed: `False`
- Aggregate EV delta: `0.1318`
- Aggregate PnL delta: `3924.94`

## Window Metrics

| Window | EV before | EV after | PnL delta | Sharpe delta | DD delta | Add-ons delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.4629 | 1193.31 | -0.01 | 0.0 | 0 |
| mid_weak | 1.4415 | 1.5133 | 1877.97 | 0.04 | 0.0 | 2 |
| old_thin | 0.3179 | 0.3341 | 853.66 | 0.02 | -0.0003 | 1 |

## Interpretation

The narrower add-on-only heat exception did not clear Gate 4 across the canonical windows. Treat add-on heat capacity as directionally interesting but still below production materiality without forward concentration evidence.

Production impact: replay-only experiment. No live order, ranking, sizing, or entry policy changed.
