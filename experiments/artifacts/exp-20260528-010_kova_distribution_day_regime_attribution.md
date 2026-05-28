# exp-20260528-010 Kova Distribution-Day Regime Attribution

Decision: `observed_only_kova_distribution_day_regime_attribution`.

Single variable: a read-only Kova distribution-pressure bucket joined to the accepted exp-20260526-007 VCP top-2 paper trades.

## Bucket Attribution

| Bucket | Trades | PnL | Avg PnL | Median PnL | Win rate | Avg fwd 10d | Rank counts |
|---|---:|---:|---:|---:|---:|---:|---|
| confirmed_low_distribution | 14 | $3,305.91 | $236.14 | $17.48 | 0.571429 | 0.02357 | `{'1': 8, '2': 6}` |
| confirmed_moderate_distribution | 59 | $24,765.23 | $419.75 | $294.09 | 0.644068 | 0.044034 | `{'1': 35, '2': 24}` |
| unconfirmed_or_downtrend | 7 | $4,207.93 | $601.13 | $798.88 | 0.857143 | 0.061442 | `{'1': 5, '2': 2}` |
| uptrend_high_distribution_pressure | 37 | $5,363.45 | $144.96 | $14.78 | 0.567568 | 0.020276 | `{'1': 23, '2': 14}` |

## Window Split

| Window | Bucket | Trades | PnL | Avg PnL | Win rate |
|---|---|---:|---:|---:|---:|
| late_strong | unconfirmed_or_downtrend | 1 | $810.19 | $810.19 | 1.0 |
| late_strong | uptrend_high_distribution_pressure | 3 | $656.46 | $218.82 | 0.333333 |
| mid_weak | confirmed_low_distribution | 14 | $3,305.91 | $236.14 | 0.571429 |
| mid_weak | confirmed_moderate_distribution | 35 | $16,843.90 | $481.25 | 0.657143 |
| mid_weak | unconfirmed_or_downtrend | 5 | $2,989.88 | $597.98 | 0.8 |
| mid_weak | uptrend_high_distribution_pressure | 34 | $4,706.99 | $138.44 | 0.588235 |
| old_thin | confirmed_moderate_distribution | 24 | $7,921.33 | $330.06 | 0.625 |
| old_thin | unconfirmed_or_downtrend | 1 | $407.86 | $407.86 | 1.0 |

## Coverage

```json
{
  "by_window": {
    "late_strong": {
      "context_ok": 4,
      "coverage": 1.0,
      "trades": 4
    },
    "mid_weak": {
      "context_ok": 88,
      "coverage": 1.0,
      "trades": 88
    },
    "old_thin": {
      "context_ok": 25,
      "coverage": 1.0,
      "trades": 25
    }
  },
  "context_ok": 117,
  "coverage": 1.0,
  "trades": 117
}
```

## Actionability Gate

```json
{
  "coverage_ok": true,
  "failed_reasons": [
    "high_pressure_bucket_positive_pnl"
  ],
  "high_pressure_avg_pnl": 144.96,
  "high_pressure_sample_ok": true,
  "high_pressure_total_pnl": 5363.45,
  "materially_weaker_than_rest": true,
  "passed": false,
  "promotion_boundary": "This is read-only attribution. A future rule would require forward replacement-value evidence and a separate Gate 1-4 strategy experiment.",
  "rest_avg_pnl": 403.49,
  "status": "observed_only_not_promotable"
}
```

## Interpretation

Distribution-day pressure is a useful read-only context field, but not a promotable VCP gate on this frozen sample. The high-pressure bucket had 37 trades and $5363.45 PnL (avg $144.96), versus the rest at avg $403.49. Gate status: observed_only_not_promotable.

No live/default orders, core entry, ranking, sizing, exits, paper notional, LLM/news, or production watchlist behavior changed.

No JavaScript was used.
