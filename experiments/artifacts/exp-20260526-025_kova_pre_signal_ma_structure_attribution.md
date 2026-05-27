# exp-20260526-025 Kova Pre-Signal Moving-Average Structure Attribution

Decision: `observed_only_no_actionable_ma_structure_split`.

The `bullish_ma_stack_close_above_10_21_50` bucket did not clear the observed-only attribution bar. Keep the VCP top-2 rank-notional sleeve unchanged and do not turn this frozen-sample split into a gate.

## Source

- Source population: `exp-20260526-007` `rank2_125` selected paper trades.
- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, exits, LLM/news, universe, and live/default orders unchanged.
- Tested field: `pre_signal_ma_structure_bucket_v1`.

## Aggregate Buckets

| bucket | trades | total pnl | avg pnl | win rate |
|---|---:|---:|---:|---:|
| bullish_ma_stack_close_above_10_21_50 | 90 | 19688.17 | 218.76 | 0.555556 |
| close_above_50_without_full_stack | 23 | 13776.68 | 598.99 | 0.869565 |
| below_50_or_broken_stack | 4 | 4177.67 | 1044.42 | 0.75 |
| unavailable | 0 | 0.0 | None | None |

## Window Buckets

| window | bucket | trades | total pnl | avg pnl | win rate |
|---|---|---:|---:|---:|---:|
| late_strong | bullish_ma_stack_close_above_10_21_50 | 3 | 656.46 | 218.82 | 0.333333 |
| late_strong | below_50_or_broken_stack | 1 | 810.19 | 810.19 | 1.0 |
| mid_weak | bullish_ma_stack_close_above_10_21_50 | 64 | 11647.02 | 181.98 | 0.546875 |
| mid_weak | close_above_50_without_full_stack | 21 | 12832.18 | 611.06 | 0.857143 |
| mid_weak | below_50_or_broken_stack | 3 | 3367.48 | 1122.49 | 0.666667 |
| old_thin | bullish_ma_stack_close_above_10_21_50 | 23 | 7384.69 | 321.07 | 0.608696 |
| old_thin | close_above_50_without_full_stack | 2 | 944.5 | 472.25 | 1.0 |

## Target Bucket Readout

- Target bucket: `bullish_ma_stack_close_above_10_21_50`.
- Target trades: `90`.
- Target total PnL: `19688.17`.
- Target average PnL: `218.76`.
- Max single positive PnL share: `0.20222`.
- Positive PnL HHI: `0.117432`.

## Gate 4

No strategy promotion was possible in this experiment because this is read-only attribution.

```json
{
  "decision_evidence": {
    "other_avg_pnl": 664.98,
    "target_avg_pnl": 218.76,
    "target_beats_other_avg_pnl": false,
    "target_bucket": "bullish_ma_stack_close_above_10_21_50",
    "target_concentration_passed": true,
    "target_max_single_positive_pnl_share": 0.20222,
    "target_positive_aggregate": true,
    "target_positive_pnl_hhi": 0.117432,
    "target_positive_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "target_trade_count_min_20": true,
    "target_trade_counts_by_window": {
      "late_strong": 3,
      "mid_weak": 64,
      "old_thin": 23
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
