# exp-20260602-030 Post-Earnings Surprise-Acceleration Support

Decision: `rejected_post_earnings_surprise_acceleration_support`.

Single variable: on top of accepted exp027, already-selected `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidates with `latest_surprise_pct - avg_historical_surprise_pct >= 5pp` receive `1.05x` incremental paper notional.

## Three-Window Result

| Window | Exp027 EV | After EV | dEV | Exp027 PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Support dPnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5140 | 5.5338 | +0.0198 | $120,128.53 | $120,304.71 | $+176.18 | -0.0001 | 5 | 4 | $+176.18 |
| mid_weak | 2.1937 | 2.1937 | +0.0000 | $78,912.25 | $78,905.13 | $-7.12 | +0.0000 | 9 | 4 | $-7.10 |
| old_thin | 0.5980 | 0.5975 | -0.0005 | $39,868.54 | $39,826.31 | $-42.23 | +0.0000 | 6 | 2 | $-42.24 |

## Aggregate

- EV delta vs exp027: `0.0193` (`0.002324`)
- PnL delta vs exp027: `$126.83` (`0.000531`)
- target trades: `20`
- supported trades: `10` across `['late_strong', 'mid_weak', 'old_thin']`
- supported max positive incremental share: `0.393698`
- supported positive incremental HHI: `0.310009`

## Gate 4

```json
{
  "acceptance_rule": "Metric Gate 4 uses docs/backtesting.md three canonical windows versus exp-20260602-027 accepted after-state. Retention also requires shared-adapter promotion, which this scout intentionally does not do.",
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "support_incremental_hhi_failed"
  ],
  "max_single_positive_incremental_share_limit": 0.5,
  "metric_gate4_passed": false,
  "passed": false,
  "positive_incremental_hhi_limit": 0.3,
  "support_min_trade_count": 10
}
```

## Production Impact

No strategy behavior is retained in this scout. The support field is evaluated through replay only; a positive result requires a separate shared-adapter promotion before it can be considered production/backtest consistent.

No JavaScript was used.
