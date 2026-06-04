# exp-20260604-001 Post-Earnings Surprise-Acceleration Support

Decision: `rejected_post_earnings_surprise_acceleration_support`.

Single variable: already-selected `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidates with `latest_surprise_pct - avg_historical_surprise_pct >= 5.0` receive `1.05x` paper notional.

Baseline: `exp-20260603-022` accepted after metrics.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Surprise dPnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5416 | 5.5624 | +0.0208 | $120,469.55 | $120,663.96 | $+194.41 | -0.0001 | 5 | 4 | $+194.40 |
| mid_weak | 2.2038 | 2.1956 | -0.0082 | $78,989.68 | $78,982.44 | $-7.24 | -0.0001 | 9 | 4 | $-7.25 |
| old_thin | 0.5985 | 0.5978 | -0.0007 | $39,897.97 | $39,851.41 | $-46.56 | +0.0000 | 6 | 2 | $-46.57 |

## Aggregate

- EV delta: `0.0119` (`0.001426`)
- PnL delta: `$140.61` (`0.000587`)
- target trades: `20`
- supported trades: `10` across `['late_strong', 'mid_weak', 'old_thin']`
- target max single positive share: `0.314284`
- target positive PnL HHI: `0.198111`
- supported max single positive incremental share: `0.39418`
- supported positive incremental HHI: `0.310706`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "mid_weak_ev_not_improved_vs_exp022",
    "mid_weak_pnl_not_improved_vs_exp022",
    "old_thin_ev_not_improved_vs_exp022",
    "old_thin_pnl_not_improved_vs_exp022",
    "window_ev_regression",
    "window_pnl_regression"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.314284,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.198111,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 20,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 2
}
```

## Production Impact

Replay-only default-off paper support scout. No shared helper, backtester adapter, run adapter, live/default orders, core ranking/sizing/exits, watchlists, LLM, or news behavior changed.

No JavaScript was used.
