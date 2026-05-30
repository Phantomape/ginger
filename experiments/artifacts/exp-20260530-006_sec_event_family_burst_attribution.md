# exp-20260530-006 SEC Event-Family Burst Attribution

Decision: `rejected_sec_event_family_burst_field`.

The untried SEC event-family burst field did not clear the pre-set read-only promotion screen (failed checks: return_lift_ok, pnl_lift_ok, window_stability_ok). Do not create an event-graph sleeve from same-family burst count alone.

## Gate 4 Evidence

```json
{
  "avg_pnl_lift_vs_singleton": 12.4124,
  "avg_return_lift_vs_singleton": 0.001241,
  "concentration_ok": true,
  "field_candidate_passed": false,
  "high_burst_count": 245,
  "high_count_ok": true,
  "max_top_positive_ticker_share": 0.5,
  "min_avg_pnl_lift": 150.0,
  "min_avg_return_lift": 0.015,
  "min_high_burst_rows": 30,
  "min_window_lift_count": 2,
  "pnl_lift_ok": false,
  "return_lift_ok": false,
  "top_ticker_positive_share": 0.1467,
  "window_lift_count": 1,
  "window_stability_ok": false
}
```

## Core Buckets

| bucket | count | avg pnl | avg return | win rate | top positive share |
|---|---:|---:|---:|---:|---:|
| singleton | 373 | 28.5827 | 0.002858 | 0.479893 | 0.13719 |
| small_burst_2 | 192 | 115.8129 | 0.011581 | 0.552083 | 0.128653 |
| medium_burst_3_4 | 164 | -69.904 | -0.00699 | 0.426829 | 0.094727 |
| large_burst_5_plus | 81 | 265.5316 | 0.026553 | 0.592593 | 0.261657 |

## Window Summary

| window | high count | high avg pnl | low avg pnl | high win rate | low win rate |
|---|---:|---:|---:|---:|---:|
| old_thin | 67 | 85.0625 | -128.9661 | 0.507463 | 0.461538 |
| mid_weak | 87 | 198.3968 | 295.3813 | 0.632184 | 0.623529 |
| late_strong | 91 | -141.9331 | 39.1549 | 0.318681 | 0.445 |

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260530_006_sec_event_family_burst_attribution.py
```

## Related Files

- `quant/experiments/exp_20260530_006_sec_event_family_burst_attribution.py`
- `data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl`
- `data/ohlcv/ohlcv_snapshot_20241002_20250422.json`
- `data/ohlcv/ohlcv_snapshot_20250423_20251022.json`
- `data/ohlcv/ohlcv_snapshot_20251023_20260421.json`
- `data/experiments/exp-20260530-006/sec_event_family_burst_attribution.json`
- `data/experiments/exp-20260530-006/sec_event_family_burst_attribution_rows.json`
- `experiments/logs/exp-20260530-006.json`
- `experiments/tickets/exp-20260530-006.json`
- `docs/experiments/tickets/exp-20260530-006.json`
- `experiments/cards/exp-20260530-006.md`
- `experiments/artifacts/exp-20260530-006_sec_event_family_burst_attribution.md`
- `experiments/manifests/exp-20260530-006.json`
