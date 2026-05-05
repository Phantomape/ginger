# SEC Negative-Reaction Replacement Value

Experiment: `exp-20260504-011`
Status: `replacement_inconclusive_not_promoted`

## Headline

The frozen SEC packet remains standalone-positive, but replacement evidence is not yet strong enough across same-day A/B alternatives to promote a core entry or ranking rule.

## Aggregate

- Candidates: `16`
- Closed primary outcomes: `16`
- Same-day accepted conflicts: `2`
- Full-before-core active-slot cases: `1`
- Capacity states: `{'spare_slot_after_core_entries': 15, 'full_before_core_entries': 1}`

## Candidate 10d Outcome

- Avg net return: `5.71%`
- Avg net excess vs SPY: `4.74%`
- Excess win rate: `62.50%`

## Replacement Proxies

- Vs same-day accepted avg: count `2`, avg `1.91%`, positive rate `50.00%`
- Vs active-slot avg: count `13`, avg `0.99%`, positive rate `53.85%`

## By Window

| Window | Candidates | Avg 10d net excess vs SPY | Vs accepted avg | Vs active-slot avg |
|---|---:|---:|---:|---:|
| old_thin | 4 | 0.29% | n/a | -4.19% |
| mid_weak | 7 | 4.52% | 1.91% | 4.43% |
| late_strong | 5 | 8.61% | n/a | 1.89% |

## Caveats

- This is shadow-only and does not change entries, ranking, sizing, exits, or production orders.
- Active-slot replacement is a proxy based on accepted trade remaining returns, not a full portfolio counterfactual.
- Top-skipped rows are oracle upper bounds and are not production evidence.
- The packet rule is frozen from exp-20260504-010; keyword and reaction-threshold tuning are out of scope.
