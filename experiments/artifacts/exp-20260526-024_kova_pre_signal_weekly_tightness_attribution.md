# exp-20260526-024 Kova Pre-Signal Weekly Tightness Attribution

Decision: `observed_only_no_actionable_weekly_tightness_split`.

The `three_week_tight` bucket did not clear the observed-only attribution bar. Keep the VCP top-2 rank-notional sleeve unchanged and do not turn this frozen-sample split into a gate.

## Source

- Source population: `exp-20260526-007` `rank2_125` selected paper trades.
- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, exits, LLM/news, universe, and live/default orders unchanged.
- Tested field: `pre_signal_weekly_tightness_bucket_v1`.

## Aggregate Buckets

| bucket | trades | total pnl | avg pnl | win rate |
|---|---:|---:|---:|---:|
| three_week_tight | 6 | 1900.18 | 316.7 | 0.833333 |
| not_three_week_tight | 111 | 35742.34 | 322.0 | 0.612613 |
| unavailable | 0 | 0.0 | None | None |

## Window Buckets

| window | bucket | trades | total pnl | avg pnl | win rate |
|---|---|---:|---:|---:|---:|
| late_strong | not_three_week_tight | 4 | 1466.65 | 366.66 | 0.5 |
| mid_weak | three_week_tight | 5 | 1492.32 | 298.46 | 0.8 |
| mid_weak | not_three_week_tight | 83 | 26354.36 | 317.52 | 0.614458 |
| old_thin | three_week_tight | 1 | 407.86 | 407.86 | 1.0 |
| old_thin | not_three_week_tight | 24 | 7921.33 | 330.06 | 0.625 |

## Target Bucket Readout

- Target bucket: `three_week_tight`.
- Target trades: `6`.
- Target total PnL: `1900.18`.
- Target average PnL: `316.7`.
- Max single positive PnL share: `0.560869`.
- Positive PnL HHI: `0.420829`.

## Gate 4

No strategy promotion was possible in this experiment because this is read-only attribution.

```json
{
  "decision_evidence": {
    "other_avg_pnl": 322.0,
    "target_avg_pnl": 316.7,
    "target_beats_other_avg_pnl": false,
    "target_bucket": "three_week_tight",
    "target_concentration_passed": false,
    "target_max_single_positive_pnl_share": 0.560869,
    "target_positive_aggregate": true,
    "target_positive_pnl_hhi": 0.420829,
    "target_positive_windows": [
      "mid_weak",
      "old_thin"
    ],
    "target_trade_count_min_20": false,
    "target_trade_counts_by_window": {
      "late_strong": 0,
      "mid_weak": 5,
      "old_thin": 1
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
