# exp-20260526-018 VBB Rank Monotonic Attribution

Decision: `rejected_vbb_rank_monotonicity_not_stable`.

Single variable: read-only monotonic validation of the existing VBB same-day score rank.

## Rank Monotonicity

| Window | Rank 1 avg ret | Rank 2 avg ret | Rank 3+ avg ret | Rank 1 n | Rank 2 n | Rank 3+ n | Monotonic |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | 0.052279 | -0.061632 | -0.004252 | 8 | 6 | 10 | False |
| mid_weak | 0.015709 | 0.034591 | 0.009067 | 17 | 13 | 43 | False |
| old_thin | 0.028967 | -0.008048 | 0.008421 | 22 | 20 | 42 | False |
| aggregate | 0.028139 | -0.002079 | 0.007379 | 47 | 39 | 95 | False |

## Top-1 Overlay Sanity Check

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.5780 | +0.4152 | $117,072.92 | $121,255.25 | $+4,182.33 |
| mid_weak | 2.1402 | 2.2780 | +0.1378 | $78,110.11 | $80,780.62 | $+2,670.51 |
| old_thin | 0.5911 | 0.7505 | +0.1594 | $39,667.96 | $46,040.62 | $+6,372.66 |

## Gate 4

```json
{
  "aggregate_monotonic": false,
  "min_bucket_trades": 8,
  "monotonic_by_window": {
    "late_strong": false,
    "mid_weak": false,
    "old_thin": false
  },
  "monotonic_window_count": 0,
  "passed": false,
  "required_monotonic_windows": 3,
  "top1_overlay_ev_delta_sum": 0.7124,
  "top1_overlay_pnl_delta_sum": 13225.5
}
```

## Production Impact

Read-only replay attribution. No shared policy, adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
