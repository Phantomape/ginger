# exp-20260524-028 Core Alpha-Score Monotonicity Audit

Decision: `rejected_raw_alpha_score_monotonicity`.

Observed-only alpha search: no entries, exits, ranking, sizing, LLM/news, or orders changed.

## Three-Window Metrics

| Window | EV | PnL | Trades | PIT Coverage | Alpha Coverage |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | $117,072.92 | 18 | 100.00% | 100.00% |
| mid_weak | 2.1402 | $78,110.11 | 21 | 100.00% | 100.00% |
| old_thin | 0.5911 | $39,667.96 | 22 | 100.00% | 100.00% |

## Aggregate Bucket Evidence

| Bucket | Trades | Win Rate | Total PnL | Avg PnL |
|---|---:|---:|---:|---:|
| top_decile | 56 | 55.36% | $194,570.00 | $3,474.46 |
| top_quartile | 5 | 80.00% | $40,280.99 | $8,056.20 |

## Monotonic Gate

```json
{
  "coverage_passed": true,
  "lower_rank_summary": {
    "avg_pnl": null,
    "total_pnl": 0.0,
    "trades": 0,
    "win_rate": null
  },
  "minimum_point_in_time_coverage": 0.95,
  "passed": false,
  "rank_bucket_monotonicity": {
    "adjacent_pairs": [
      {
        "higher_avg_pnl": 3474.46,
        "higher_bucket": "top_decile",
        "lower_avg_pnl": 8056.2,
        "lower_bucket": "top_quartile",
        "passed": false
      }
    ],
    "minimum_nonempty_rank_buckets": 3,
    "nonempty_rank_buckets": 2,
    "passed": false,
    "violations": [
      {
        "higher_avg_pnl": 3474.46,
        "higher_bucket": "top_decile",
        "lower_avg_pnl": 8056.2,
        "lower_bucket": "top_quartile",
        "passed": false
      }
    ]
  },
  "top_rank_outperformed_lower_rank": false,
  "top_rank_summary": {
    "avg_pnl": 3850.02,
    "total_pnl": 234850.99,
    "trades": 61,
    "win_rate": 0.5738
  }
}
```

No JavaScript was used.
