# Form 4 Standalone Event Sleeve Shadow Replay

- experiment_id: `exp-20260503-052`
- timestamp: `2026-05-03T22:11:47+00:00`
- decision: `shadow_promising_not_promoted`
- production_impact: `shadow_only_no_strategy_logic_changed`
- primary horizon: `10` trading days

## Baseline

| Window | EV | Return | Sharpe daily | Max DD | Win rate | Trades |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | 4.35 | 5.41% | 78.95% | 19 |
| mid_weak | 1.4415 | 55.02% | 2.62 | 8.79% | 52.38% | 21 |
| old_thin | 0.3179 | 24.64% | 1.29 | 8.05% | 40.91% | 22 |

## Variant Summary

| Variant | Min buy | Valid events | Avg net return | Avg excess | Positive windows | Decision cue |
|---|---:|---:|---:|---:|---:|---|
| meaningful_ge_0 | $0 | 27 | 4.36% | 2.83% | 2/3 | unstable |
| meaningful_ge_100k | $100,000 | 25 | 4.62% | 3.07% | 2/3 | unstable |
| meaningful_ge_250k | $250,000 | 18 | 4.17% | 3.06% | 2/3 | unstable |
| meaningful_ge_500k | $500,000 | 13 | 5.75% | 4.76% | 3/3 | stable-positive |
| meaningful_ge_1m | $1,000,000 | 9 | 5.20% | 4.17% | 2/3 | unstable |

## Best Shadow Variant

- best_variant: `meaningful_ge_500k`
- min_total_purchase_value: `$500,000`

| Window | Events | Valid | Avg net return | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|
| late_strong | 4 | 4 | 4.98% | 4.84% | 100.00% |
| mid_weak | 10 | 8 | 6.85% | 5.27% | 75.00% |
| old_thin | 3 | 1 | 0.06% | 0.33% | 100.00% |

## Read

The >=$500k meaningful-purchase variant is the first stable Form 4 branch in this run: it has positive 10-day excess return in all three fixed windows. It is still not promoted because the old_thin sample has only one valid event and no shared production/backtest event-sleeve policy exists.

## Next Action

Do not add core entries yet. Put >=$500k meaningful Form 4 purchases into a default-off forward/pilot event queue with frozen same-day alternatives, then require closed outcome and replacement-value evidence before any shared production/backtest policy promotion.
