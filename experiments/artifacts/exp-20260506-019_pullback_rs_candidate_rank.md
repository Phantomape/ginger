# exp-20260506-019: pullback-RS candidate collision rank

Decision: rejected

## Best Variant

- Best: `collision_rank_momentum_60`
- Gate 4 passed: `False`
- Aggregate EV delta: `-0.2209`
- Aggregate PnL delta: `-10490.4`
- Rank-changed collisions: `9`

## Window Metrics

| Window | EV before | EV after | PnL delta | Sharpe delta | DD delta | Trades delta | Rank changes |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.4191 | 0.0 | 0.0 | 0.0 | 0.0 | 2 |
| mid_weak | 1.4415 | 1.3762 | -1461.62 | -0.05 | 0.0 | 1.0 | 3 |
| old_thin | 0.3179 | 0.1623 | -9028.78 | -0.25 | 0.0002 | -1.0 | 4 |

## Interpretation

The research-backed pullback/60d score did not clear Gate 4 in the slot-aware entry planner. Either the standalone rank IC does not survive portfolio collision costs, or this score needs a different state/context discriminator before it can improve live allocation.

Production impact: replay-only experiment. No live order, ranking, sizing, entry policy, or run.py behavior changed.
