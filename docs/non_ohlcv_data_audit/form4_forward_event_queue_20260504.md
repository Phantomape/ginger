# Form 4 Forward Event Queue

- experiment_id: `exp-20260504-001`
- timestamp: `2026-05-04T00:17:43+00:00`
- decision: `accepted_forward_observation_queue`
- production_impact: `observe_only_forward_queue_no_core_strategy_change`

## Alpha Read

Large PIT-safe meaningful Form 4 open-market purchase event-days can be a candidate-source alpha scout, but require forward replacement-value samples before trade promotion.

This is an alpha-search scout, not a bug fix. The prior `$500k` Form 4 branch was shadow-promising but sample-limited, so the valid next step is production-visible forward observation with frozen alternatives.

## Fixed-Window Metrics

| Window | EV | Return | Sharpe daily | Max DD | Win rate | Trades |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78.60% | 4.35 | 5.41% | 78.95% | 19 |
| mid_weak | 1.4415 | 55.02% | 2.62 | 8.79% | 52.38% | 21 |
| old_thin | 0.3179 | 24.64% | 1.29 | 8.05% | 40.91% | 22 |

## Shadow Evidence Carried Forward

- source_experiment: `exp-20260503-052`
- variant: `meaningful_ge_500k`
- valid_events: `13`
- avg_net_return: `5.75%`
- avg_excess_vs_spy: `4.76%`
- positive_excess_windows: `3/3`

## Production Smoke

- as_of: `2026-05-04`
- enabled: `False`
- candidate_count: `0`
- alters_orders: `False`

## Decision

Accepted as a default-off observation queue only. It does not pass as a strategy promotion because no core trades are added and the old_thin shadow sample remains too small.

## Next Action

Accumulate closed forward queue outcomes and replacement-value snapshots; do not promote to entries until sample stability improves beyond the old_thin one-event limitation.
