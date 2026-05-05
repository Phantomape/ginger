# exp-20260504-022 SEC Other-Filing Mild Negative Shadow

- decision: `shadow_promising_not_promoted`
- primary branch: `other_sec_filing` + `negative_excess_0_to_minus_2pct`
- event rows: 22
- valid 10d observations: 20
- 10d avg excess: 2.5478%
- 10d positive rate: 55.0%
- positive 10d windows: 3/3
- same-day A/B overlap count: 4
- replacement proxy avg: -9.7802%
- production impact: `shadow_only_no_strategy_logic_changed`

## Window Summary

| window | events | valid 10d | avg 10d excess % | positive rate % |
|---|---:|---:|---:|---:|
| late_strong | 4 | 3 | 0.0089 | 33.33 |
| mid_weak | 13 | 12 | 2.3445 | 58.33 |
| old_thin | 5 | 5 | 4.5589 | 60.0 |

## Interpretation

Primary branch is positive in all three canonical windows, but remains shadow-only pending semantic and replacement-value evidence.

This is a shadow alpha-search result only. It does not alter entries, exits, ranking, sizing, candidate generation, or production orders.
