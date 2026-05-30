# exp-20260530-018 Pre-Entry Catalyst Freshness Attribution

Decision: `rejected_pre_entry_catalyst_freshness_field`.

Rejected: fresh high-confidence catalyst timing did not clear avg_pnl_lift, avg_return_lift.

## Gate 4 Evidence

```json
{
  "avg_pnl_lift_vs_stale_or_no_high_confidence": 68.9536,
  "avg_return_lift_vs_stale_or_no_high_confidence": 0.02808,
  "concentration_ok": true,
  "field_candidate_passed": false,
  "fresh_count_ok": true,
  "fresh_trade_count": 10,
  "max_top_positive_ticker_share": 0.5,
  "min_avg_pnl_lift": 500.0,
  "min_avg_return_lift": 0.05,
  "min_fresh_rows": 8,
  "min_window_lift_count": 2,
  "pnl_lift_ok": false,
  "return_lift_ok": false,
  "top_ticker_positive_share": 0.377967,
  "window_lift_count": 2,
  "window_stability_ok": true
}
```

## Freshness Buckets

| bucket | trades | avg pnl | avg return | win rate | top positive share |
|---|---:|---:|---:|---:|---:|
| fresh_high_confidence_catalyst | 10 | 3907.666 | 0.075042 | 0.6 | 0.377967 |
| stale_high_confidence_catalyst | 3 | 9339.5833 | 0.154752 | 1.0 | 0.455658 |
| no_high_confidence_catalyst | 48 | 3494.9079 | 0.040225 | 0.541667 | 0.177492 |

## Window Summary

| window | fresh trades | fresh avg pnl | stale/no-HC avg pnl | fresh win rate | stale/no-HC win rate |
|---|---:|---:|---:|---:|---:|
| old_thin | 6 | 5279.8433 | 499.3063 | 0.833333 | 0.25 |
| mid_weak | 3 | -17.57 | 4342.3789 | 0.0 | 0.611111 |
| late_strong | 1 | 7450.31 | 6448.3888 | 1.0 | 0.823529 |

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260530_018_pre_entry_catalyst_freshness_attribution.py
```

## Related Files

- `quant/experiments/exp_20260530_018_pre_entry_catalyst_freshness_attribution.py`
- `data/experiments/exp-20260530-014/pre_entry_catalyst_attribution_trade_rows.json`
- `data/experiments/exp-20260530-014/exp_20260530_014_pre_entry_catalyst_attribution.json`
- `data/experiments/exp-20260530-018/pre_entry_catalyst_freshness_attribution.json`
- `data/experiments/exp-20260530-018/pre_entry_catalyst_freshness_attribution_rows.json`
- `experiments/logs/exp-20260530-018.json`
- `experiments/tickets/exp-20260530-018.json`
- `docs/experiments/tickets/exp-20260530-018.json`
- `experiments/cards/exp-20260530-018.md`
- `experiments/artifacts/exp-20260530-018_pre_entry_catalyst_freshness_attribution.md`
- `experiments/manifests/exp-20260530-018.json`
