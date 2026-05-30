# exp-20260530-019 Pre-Entry Catalyst Diversity Attribution

Decision: `rejected_pre_entry_catalyst_diversity_field`.

## Readout

- Diverse high-confidence rows: `0`
- Single-source/category high-confidence rows: `13`
- No high-confidence rows: `48`
- Avg PnL lift vs single high-confidence: `None`
- Avg return lift vs single high-confidence: `None`
- Positive-lift windows: `0`
- Gate passed: `False`

| Bucket | Trades | Avg PnL | Avg Return | Win Rate | Top positive share |
|---|---:|---:|---:|---:|---:|
| source_or_category_diverse_high_confidence | 0 | None | None | None | 0.0 |
| single_source_single_category_high_confidence | 13 | 5161.19 | 0.093437 | 0.692308 | 0.221282 |
| no_high_confidence_catalyst | 48 | 3494.91 | 0.040225 | 0.541667 | 0.177492 |

## Gate

```json
{
  "avg_pnl_lift_vs_single_high_confidence": null,
  "avg_return_lift_vs_single_high_confidence": null,
  "concentration_ok": true,
  "diverse_count_ok": false,
  "diverse_rows": 0,
  "max_top_positive_ticker_share": 0.5,
  "min_avg_pnl_lift_vs_single": 1000.0,
  "min_avg_return_lift_vs_single": 0.03,
  "min_diverse_rows": 4,
  "min_positive_lift_windows": 2,
  "pnl_lift_ok": false,
  "positive_lift_windows": 0,
  "return_lift_ok": false,
  "top_ticker_positive_share": 0.0,
  "window_stability_ok": false
}
```

Read-only attribution only. No core entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.
