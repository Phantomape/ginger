# SEC Event-Sleeve Backtest

Experiment: `exp-20260504-010`
Status: `sleeve_promising_not_promoted`

## Headline

The fixed SEC negative-language + negative-reaction packet remains positive after portfolio-level event-sleeve simulation with costs; it is eligible for a default-off production queue / replacement-value test.

## Variants

| Variant | Trades | Total return | Sharpe daily | Max DD | Win rate | Exposure | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10d_max1 | 13 | 99.99% | 1.4757 | 10.37% | 84.62% | 17.65% | 3 |
| 10d_max2 | 16 | 52.74% | 1.6232 | 5.30% | 87.50% | 19.76% | 0 |
| 20d_max1 | 9 | 172.50% | 1.5666 | 17.20% | 100.00% | 25.79% | 7 |
| 20d_max2 | 15 | 72.09% | 1.4235 | 15.23% | 93.33% | 33.48% | 1 |

## Primary Trades By Window

| Window | Trades | Avg net return | Win rate | Total PnL |
|---|---:|---:|---:|---:|
| late_strong | 4 | 10.10% | 75.00% | 54618.33 |
| mid_weak | 6 | 6.69% | 100.00% | 45104.98 |
| old_thin | 3 | 0.10% | 66.67% | 269.98 |

## Caveat

- This is a standalone event-sleeve simulation, not a core A/B backtest change.
- Top-trade concentration: LITE contributed 69092.5 PnL (69.10% of primary total PnL); replacement-value testing must verify this is not a one-name artifact.
- Gate 4 is not passed for production because no shared production/backtest event policy changed.
- The packet rule is frozen from exp-20260504-008; nearby keyword or reaction-threshold tuning is explicitly out of scope.

## Next

Run replacement-value testing versus same-day accepted/skipped A/B candidates. If that survives, add a default-off production queue.
