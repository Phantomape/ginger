# exp-20260530-008 SEC First/Follow-On Attribution

Decision: `rejected_sec_first_reaction_followon_field`.

Rejected: SEC follow-on sequencing did not clear avg_return_lift, avg_pnl_lift, window_stability.

## Gate 4 Evidence

```json
{
  "avg_pnl_lift_vs_first_or_isolated": -129.9512,
  "avg_return_lift_vs_first_or_isolated": -0.012995,
  "concentration_ok": true,
  "field_candidate_passed": false,
  "followon_count": 79,
  "followon_count_ok": true,
  "max_top_positive_ticker_share": 0.5,
  "min_avg_pnl_lift": 150.0,
  "min_avg_return_lift": 0.015,
  "min_followon_rows": 30,
  "min_window_lift_count": 2,
  "pnl_lift_ok": false,
  "return_lift_ok": false,
  "top_ticker_positive_share": 0.145324,
  "window_lift_count": 1,
  "window_stability_ok": false
}
```

## Sequence Buckets

| bucket | count | avg pnl | avg return | win rate | top positive share |
|---|---:|---:|---:|---:|---:|
| first_or_isolated | 731 | 65.6881 | 0.006569 | 0.49658 | 0.081093 |
| followon_1_7d | 21 | -209.0962 | -0.02091 | 0.428571 | 0.351437 |
| followon_8_30d | 51 | -21.7874 | -0.002179 | 0.529412 | 0.197779 |
| repeat_cluster_3plus_30d | 7 | 60.7707 | 0.006077 | 0.571429 | 0.629787 |

## Window Summary

| window | follow-on count | follow-on avg pnl | first avg pnl | follow-on win rate | first win rate |
|---|---:|---:|---:|---:|---:|
| old_thin | 23 | -488.4227 | -34.3744 | 0.478261 | 0.472803 |
| mid_weak | 22 | 261.6209 | 262.6369 | 0.772727 | 0.612766 |
| late_strong | 34 | 11.8023 | -21.3471 | 0.352941 | 0.412451 |

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260530_008_sec_first_reaction_followon_attribution.py
```

## Related Files

- `quant/experiments/exp_20260530_008_sec_first_reaction_followon_attribution.py`
- `data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl`
- `data/ohlcv/ohlcv_snapshot_20241002_20250422.json`
- `data/ohlcv/ohlcv_snapshot_20250423_20251022.json`
- `data/ohlcv/ohlcv_snapshot_20251023_20260421.json`
- `data/experiments/exp-20260530-008/sec_first_reaction_followon_attribution.json`
- `data/experiments/exp-20260530-008/sec_first_reaction_followon_attribution_rows.json`
- `experiments/logs/exp-20260530-008.json`
- `experiments/tickets/exp-20260530-008.json`
- `docs/experiments/tickets/exp-20260530-008.json`
- `experiments/cards/exp-20260530-008.md`
- `experiments/artifacts/exp-20260530-008_sec_first_reaction_followon_attribution.md`
- `experiments/manifests/exp-20260530-008.json`
