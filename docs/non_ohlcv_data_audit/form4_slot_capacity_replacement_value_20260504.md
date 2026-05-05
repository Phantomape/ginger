# Form 4 Slot Capacity Replacement Value

- experiment_id: `exp-20260504-006`
- timestamp: `2026-05-04T01:03:11+00:00`
- decision: `shadow_only_capacity_inconclusive`
- production_impact: `shadow_slot_capacity_audit_only_no_strategy_change`

## Read

Form 4 queue candidates still look positive as standalone 10d events, but capacity-aware replacement evidence is too thin for promotion. Only 2 candidates have same-day accepted-trade alternatives for tradable slot comparison, so the slot value cannot yet be treated as stable alpha.

## Aggregate

- candidate_count: `17`
- priced_candidate_count: `13`
- closed_primary_count: `13`
- same_day_accepted_conflict_count: `2`
- same_day_top_skipped_conflict_count: `2`
- capacity_state_counts: `{'full_before_core_entries': 2, 'missing_price_history_no_slot_value': 4, 'spare_slot_after_core_entries': 11}`

## Primary 10d Candidate Outcome

- avg_return_pct: `6.1010`
- avg_excess_vs_spy_pct: `4.7594`
- excess_win_rate: `0.8462`

## Replacement Value

- same-day accepted comparison_count: `2`
- avg_vs_accepted_avg_spy_excess_pct: `-2.1946`
- positive_vs_accepted_avg_rate: `0.5000`
- top-skipped upper-bound comparison_count: `2`
- avg_vs_best_upper_bound_return_pct: `6.5188`

## By Window

| Window | Candidates | Closed 10d | Same-day accepted conflicts | Avg 10d SPY excess | Avg replacement vs accepted avg |
|---|---:|---:|---:|---:|---:|
| old_thin | 3 | 1 | 1 | 0.3253 | -5.6308 |
| mid_weak | 10 | 8 | 0 | 5.2740 | n/a |
| late_strong | 4 | 4 | 1 | 4.8388 | 1.2416 |

## Caveats

- Same-day accepted alternatives are tradable proxies; top-skipped rows are oracle upper bounds and biased.
- Existing full candidate signal history is not available, so this is not a full candidate-rank replay.
- No production rule, sizing, or queue definition changed.

## Next Action

Do not promote Form 4 entries yet. The next useful step is to capture full same-day candidate-rank snapshots from the production/backtest entry loop, so Form 4 can be compared against all rankable A/B candidates rather than only accepted trades and top-skipped oracle rows.
