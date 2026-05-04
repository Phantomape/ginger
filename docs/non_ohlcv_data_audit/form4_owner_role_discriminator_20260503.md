# Form 4 Owner-Role Discriminator Shadow Replay

- experiment_id: `exp-20260503-053`
- timestamp: `2026-05-03T23:15:56+00:00`
- decision: `rejected`
- production_impact: `shadow_only_no_strategy_logic_changed`
- base event filter: `meaningful_purchase_v1 and total_purchase_value >= 500000`

## Core Baseline

| Window | EV | Return | Sharpe daily | Max DD | Win rate | Trades |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | 4.35 | 5.41% | 78.95% | 19 |
| mid_weak | 1.4415 | 55.02% | 2.62 | 8.79% | 52.38% | 21 |
| old_thin | 0.3179 | 24.64% | 1.29 | 8.05% | 40.91% | 22 |

## Shadow Role Variants

| Variant | Valid events | Avg net return | Avg excess | Excess win rate | Positive windows |
|---|---:|---:|---:|---:|---:|
| baseline_ge500k_any_role | 13 | 5.75% | 4.76% | 84.62% | 3/3 |
| ge500k_not_ceo_cfo_or_president | 9 | 6.15% | 4.91% | 88.89% | 3/3 |
| ge500k_director_not_officer | 7 | 4.66% | 3.69% | 85.71% | 3/3 |
| ge500k_not_officer | 7 | 4.66% | 3.69% | 85.71% | 3/3 |
| ge500k_single_owner | 11 | 5.77% | 4.69% | 90.91% | 3/3 |
| ge500k_ceo_cfo_or_president | 4 | 4.85% | 4.42% | 75.00% | 2/3 |
| ge500k_any_officer | 6 | 7.02% | 6.01% | 83.33% | 2/3 |
| ge500k_owner_cluster_2plus | 2 | 5.63% | 5.17% | 50.00% | 1/3 |

## Best Role Variant By Shadow Excess

- best_role_variant: `ge500k_not_ceo_cfo_or_president`
- avg_excess_delta_vs_plain_ge500k: `+0.15 pp`
- valid_event_delta_vs_plain_ge500k: `-4`

| Window | Events | Valid | Avg net return | Avg excess vs SPY | Excess win rate |
|---|---:|---:|---:|---:|---:|
| late_strong | 3 | 3 | 6.25% | 6.10% | 100.00% |
| mid_weak | 7 | 5 | 7.31% | 5.11% | 80.00% |
| old_thin | 3 | 1 | 0.06% | 0.33% | 100.00% |

## Decision

The best role filter was ge500k_not_ceo_cfo_or_president, with avg 10d excess delta +0.15 pp versus the plain >=$500k baseline and -4 valid events. That is not enough to justify a new role-gated branch: the apparent lift is small, sample count falls, and old_thin still has only one valid event.
