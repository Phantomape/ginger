# exp-20260526-023 Kova Signal-Day Breakout Quality Attribution

Decision: `observed_only_no_actionable_signal_day_breakout_quality_split`.

The `volume_expansion_high_close` bucket did not clear the observed-only attribution bar. Keep the VCP top-2 rank-notional sleeve unchanged and do not turn this frozen-sample split into a gate.

## Source

- Source population: `exp-20260526-007` `rank2_125` selected paper trades.
- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, exits, LLM/news, universe, and live/default orders unchanged.
- Tested field: `signal_day_breakout_quality_bucket_v1`.

## Aggregate Buckets

| bucket | trades | total pnl | avg pnl | win rate |
|---|---:|---:|---:|---:|
| volume_expansion_high_close | 16 | 7301.52 | 456.34 | 0.625 |
| volume_expansion_not_high_close | 16 | 3347.42 | 209.21 | 0.625 |
| high_close_without_volume_expansion | 54 | 18791.59 | 347.99 | 0.611111 |
| no_volume_expansion_or_high_close | 31 | 8201.99 | 264.58 | 0.645161 |
| unavailable | 0 | 0.0 | None | None |

## Window Buckets

| window | bucket | trades | total pnl | avg pnl | win rate |
|---|---|---:|---:|---:|---:|
| late_strong | volume_expansion_high_close | 1 | 810.19 | 810.19 | 1.0 |
| late_strong | volume_expansion_not_high_close | 1 | -6.37 | -6.37 | 0.0 |
| late_strong | high_close_without_volume_expansion | 2 | 662.83 | 331.41 | 0.5 |
| mid_weak | volume_expansion_high_close | 13 | 6848.19 | 526.78 | 0.692308 |
| mid_weak | volume_expansion_not_high_close | 13 | 2409.29 | 185.33 | 0.615385 |
| mid_weak | high_close_without_volume_expansion | 34 | 11999.06 | 352.91 | 0.617647 |
| mid_weak | no_volume_expansion_or_high_close | 28 | 6590.14 | 235.36 | 0.607143 |
| old_thin | volume_expansion_high_close | 2 | -356.86 | -178.43 | 0.0 |
| old_thin | volume_expansion_not_high_close | 2 | 944.5 | 472.25 | 1.0 |
| old_thin | high_close_without_volume_expansion | 18 | 6129.7 | 340.54 | 0.611111 |
| old_thin | no_volume_expansion_or_high_close | 3 | 1611.85 | 537.28 | 1.0 |

## Target Bucket Readout

- Target bucket: `volume_expansion_high_close`.
- Target trades: `16`.
- Target total PnL: `7301.52`.
- Target average PnL: `456.34`.
- Max single positive PnL share: `0.240996`.
- Positive PnL HHI: `0.179623`.

## Gate 4

No strategy promotion was possible in this experiment because this is read-only attribution.

```json
{
  "decision_evidence": {
    "other_avg_pnl": 300.41,
    "target_avg_pnl": 456.34,
    "target_beats_other_avg_pnl": true,
    "target_bucket": "volume_expansion_high_close",
    "target_concentration_passed": true,
    "target_max_single_positive_pnl_share": 0.240996,
    "target_positive_aggregate": true,
    "target_positive_pnl_hhi": 0.179623,
    "target_positive_windows": [
      "late_strong",
      "mid_weak"
    ],
    "target_trade_count_min_20": false,
    "target_trade_counts_by_window": {
      "late_strong": 1,
      "mid_weak": 13,
      "old_thin": 2
    }
  },
  "passed": false,
  "promotion_grade": false,
  "reason": "Observed-only metadata attribution; no strategy behavior changed.",
  "strategy_replacement_tested": false
}
```

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260526_023_kova_remaining_ohlcv_attributions.py
```
