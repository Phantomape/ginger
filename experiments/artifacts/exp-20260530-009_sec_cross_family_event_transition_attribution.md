# exp-20260530-009 SEC Cross-Family Event Transition Attribution

Decision: `rejected_sec_cross_family_event_transition_field`.

Rejected: SEC cross-family event transitions did not clear avg_return_lift, avg_pnl_lift, window_stability.

## Gate 4 Evidence

```json
{
  "avg_pnl_lift_vs_no_recent_prior_event": -108.4813,
  "avg_return_lift_vs_no_recent_prior_event": -0.010848,
  "concentration_ok": true,
  "cross_family_transition_count": 457,
  "field_candidate_passed": false,
  "max_top_positive_ticker_share": 0.5,
  "min_avg_pnl_lift": 150.0,
  "min_avg_return_lift": 0.015,
  "min_transition_rows": 30,
  "min_window_lift_count": 2,
  "pnl_lift_ok": false,
  "return_lift_ok": false,
  "top_ticker_positive_share": 0.083913,
  "transition_count_ok": true,
  "window_lift_count": 1,
  "window_stability_ok": false
}
```

## Transition Buckets

| bucket | count | avg pnl | avg return | win rate | top positive share |
|---|---:|---:|---:|---:|---:|
| no_recent_prior_event | 326 | 119.4067 | 0.011941 | 0.542945 | 0.1539 |
| same_family_recent_prior | 27 | -36.2329 | -0.003623 | 0.481481 | 0.247451 |
| mixed_latest_prior_family_transition | 27 | -82.4047 | -0.00824 | 0.555556 | 0.317812 |
| periodic_to_nonperiodic | 56 | -85.6421 | -0.008564 | 0.410714 | 0.217377 |
| nonperiodic_to_periodic | 149 | 8.0989 | 0.00081 | 0.442953 | 0.100745 |
| cross_8k_item_transition | 224 | 39.3262 | 0.003933 | 0.482143 | 0.098917 |
| other_cross_family_transition | 1 | 1997.9945 | 0.199799 | 1.0 | 1.0 |

## Window Summary

| window | cross-family count | cross-family avg pnl | no-prior avg pnl | cross-family win rate | no-prior win rate |
|---|---:|---:|---:|---:|---:|
| old_thin | 146 | -148.1226 | 66.6062 | 0.424658 | 0.541284 |
| mid_weak | 139 | 196.9644 | 330.6233 | 0.618705 | 0.622807 |
| late_strong | 172 | -4.4141 | -58.4908 | 0.377907 | 0.456311 |

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260530_009_sec_cross_family_event_transition_attribution.py
```

## Related Files

- `quant/experiments/exp_20260530_009_sec_cross_family_event_transition_attribution.py`
- `data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl`
- `data/ohlcv/ohlcv_snapshot_20241002_20250422.json`
- `data/ohlcv/ohlcv_snapshot_20250423_20251022.json`
- `data/ohlcv/ohlcv_snapshot_20251023_20260421.json`
- `data/experiments/exp-20260530-009/sec_cross_family_event_transition_attribution.json`
- `data/experiments/exp-20260530-009/sec_cross_family_event_transition_attribution_rows.json`
- `experiments/logs/exp-20260530-009.json`
- `experiments/tickets/exp-20260530-009.json`
- `docs/experiments/tickets/exp-20260530-009.json`
- `experiments/cards/exp-20260530-009.md`
- `experiments/artifacts/exp-20260530-009_sec_cross_family_event_transition_attribution.md`
- `experiments/manifests/exp-20260530-009.json`
