# exp-20260530-014 Pre-Entry Catalyst Attribution

- Decision: `observed_useful_pre_entry_catalyst_context`
- High-confidence tagged trades: `13`
- High-confidence avg PnL lift: `1666.28`
- Any-catalyst tagged trades: `28`
- Any-catalyst avg PnL lift: `2551.74`
- Useful-for-next-experiment gate passed: `True`

| Window | Trades | High-conf tagged | High-conf avg lift | Any-context tagged | Any-context avg lift |
| --- | ---: | ---: | ---: | ---: | ---: |
| late_strong | 18 | 2 | 591.52 | 8 | 3574.87 |
| mid_weak | 21 | 5 | 724.24 | 9 | 107.98 |
| old_thin | 22 | 6 | 4780.53 | 11 | 4484.96 |

Observed-only result. The joined catalyst context is not consumed by entries, ranking, sizing, exits, or production orders.

## Gate

```json
{
  "failed_reasons": [],
  "high_confidence_avg_pnl_lift": 1666.28,
  "high_confidence_tagged_trades": 13,
  "max_single_ticker_positive_pnl_share": 0.221282,
  "passed": true,
  "positive_lift_windows": 3,
  "rule": "Observed-only usefulness gate: high-confidence catalyst tagged trades >= 10, average PnL lift versus no high-confidence catalyst > 0, at least two windows with positive lift, and tagged positive PnL max single-ticker share <= 50%."
}
```
