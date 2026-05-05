# exp-20260504-023 SEC Other-Filing Semantic Decomposition

- decision: `shadow_promising_sample_limited_not_promoted`
- primary branch: `other_sec_filing` + `shareholder_vote` + `negative_excess_0_to_minus_2pct`
- event rows: 11
- valid 10d observations: 11
- 10d avg excess: 5.0618%
- 10d positive rate: 63.64%
- positive 10d windows: 2/3
- same-day A/B overlap count: 1
- replacement proxy avg: -13.0963%
- production impact: `shadow_only_no_strategy_logic_changed`

## Window Summary

| window | events | valid 10d | avg 10d excess % | positive rate % |
|---|---:|---:|---:|---:|
| late_strong | 1 | 1 | -3.0532 | 0.0 |
| mid_weak | 8 | 8 | 3.7949 | 62.5 |
| old_thin | 2 | 2 | 14.1869 | 100.0 |

## Top Semantic Cells

| semantic | reaction bucket | valid 10d | avg 10d excess % | positive windows |
|---|---|---:|---:|---:|
| shareholder_vote | negative_excess_0_to_minus_2pct | 11 | 5.0618 | 2 |
| charter_or_securities_change | positive_excess_0_to_2pct | 5 | 3.099 | 2 |
| exhibit_only | negative_excess_0_to_minus_2pct | 3 | 2.0914 | 2 |
| exhibit_only | positive_excess_0_to_2pct | 5 | 1.669 | 2 |
| shareholder_vote | positive_excess_ge_2pct | 4 | 2.7347 | 1 |
| shareholder_vote | negative_excess_le_minus_2pct | 4 | 1.9816 | 1 |
| shareholder_vote | positive_excess_0_to_2pct | 15 | -0.149 | 1 |
| charter_or_securities_change | negative_excess_0_to_minus_2pct | 6 | -1.8331 | 0 |

## Interpretation

The shareholder-vote mild-negative branch is positive on average, but has fewer than 20 valid 10d samples and is not production-promotable.

This is a shadow alpha-search result only. It does not alter entries, exits, ranking, sizing, candidate generation, or production orders.
