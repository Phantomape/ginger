# exp-20260526-008 Kova VCP Top-2 Follow-Through Failure Attribution

Decision: `observed_only_no_actionable_followthrough_split`.

The first-three-session follow-through split did not produce a stable promotable bucket. Keep exp037 unchanged and avoid adding another post-entry rule on this frozen sample.

## Source

- Source population: `exp-20260525-037` top2_equal_notional selected paper trades.
- Core, entry, ranking, sizing, exits, LLM/news, universe, and live/default orders unchanged.
- Tested field is post-entry attribution only: `post_entry_follow_through_status_3d`.

## Aggregate Buckets

| status | trades | total pnl | avg pnl | win rate | avg net pct |
|---|---:|---:|---:|---:|---:|
| failed_below_pivot_3d | 47 | 10842.17 | 230.68 | 0.553191 | 0.023068 |
| advanced_above_signal_close_3d | 60 | 22728.93 | 378.82 | 0.716667 | 0.037882 |
| held_pivot_without_advance_3d | 10 | 1224.82 | 122.48 | 0.4 | 0.012248 |
| unavailable | 0 | 0.0 | None | None | None |

## Window Buckets

| window | status | trades | total pnl | avg pnl | win rate |
|---|---|---:|---:|---:|---:|
| late_strong | failed_below_pivot_3d | 4 | 1237.73 | 309.43 | 0.5 |
| mid_weak | failed_below_pivot_3d | 37 | 7476.82 | 202.08 | 0.540541 |
| mid_weak | advanced_above_signal_close_3d | 43 | 16205.34 | 376.87 | 0.72093 |
| mid_weak | held_pivot_without_advance_3d | 8 | 1712.14 | 214.02 | 0.5 |
| old_thin | failed_below_pivot_3d | 6 | 2127.62 | 354.6 | 0.666667 |
| old_thin | advanced_above_signal_close_3d | 17 | 6523.59 | 383.74 | 0.705882 |
| old_thin | held_pivot_without_advance_3d | 2 | -487.32 | -243.66 | 0.0 |

## Failed Bucket Readout

- Failed bucket trades: `47`.
- Failed bucket total PnL: `10842.17`.
- Failed bucket average PnL: `230.68`.
- Non-tradable PnL if failed bucket were removed after the fact: `23953.75`.

This counterfactual is not a trading rule. The failed bucket is known only after entry.

## Gate 4

No promotion was possible in this experiment because no actionable PIT-safe rule was tested.

```json
{
  "decision_evidence": {
    "failed_avg_pnl": 230.68,
    "failed_bucket_negative_aggregate": false,
    "failed_bucket_negative_windows": [],
    "failed_bucket_trade_count_min_20": true,
    "nonfailed_avg_pnl": 342.2
  },
  "passed": false,
  "promotion_grade": false,
  "reason": "Observed-only post-entry field. A later experiment must test an actionable PIT-safe exit/risk rule before any strategy change.",
  "strategy_replacement_tested": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260526_008_vcp_top2_followthrough_failure_attribution.py
```
