# exp-20260506-020: index-state gated breakout defer

Decision: `rejected`

## Best Variant

- Best: `defer_when_index_le_10pct_from_ma`
- Gate 4 passed: `False`
- Aggregate EV delta: `0.0`
- Aggregate PnL delta: `0.0`
- Deferred breakout delta: `0`

## Window Metrics

| Window | EV before | EV after | PnL delta | Sharpe delta | DD delta | Deferred delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.4191 | 0.0 | 0.0 | 0.0 | 0 |
| mid_weak | 1.4415 | 1.4415 | 0.0 | 0.0 | 0.0 | 0 |
| old_thin | 0.3179 | 0.3179 | 0.0 | 0.0 | 0.0 | 0 |

## Interpretation

Index-distance gating did not improve the accepted one-slot breakout defer rule enough to clear Gate 4. The accepted unconditional hook remains the best tested version; do not retry nearby SPY/QQQ distance-from-MA thresholds without a richer capacity-timing signal.

Production impact: replay-only experiment. No live order, ranking, sizing, entry policy, or run.py behavior changed.
