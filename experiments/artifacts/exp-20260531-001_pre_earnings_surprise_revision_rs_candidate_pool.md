# exp-20260531-001 Pre-Earnings Surprise/Revision RS Candidate Pool

Decision: `rejected_pre_earnings_surprise_revision_rs_candidate_pool`.

Single variable: a default-off paper candidate source using canonical earnings snapshots plus OHLCV confirmation, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.0064 | -0.1564 | $117,072.92 | $115,092.29 | $-1,980.63 | +0.0000 | 8 | 14 |
| mid_weak | 2.1402 | 2.2450 | +0.1048 | $78,110.11 | $79,330.42 | $+1,220.31 | -0.0019 | 15 | 22 |
| old_thin | 0.5911 | 0.4931 | -0.0980 | $39,667.96 | $35,734.10 | $-3,933.86 | +0.0201 | 11 | 16 |

## Aggregate

- EV delta: `-0.1496` (`-0.018951`)
- PnL delta: `$-4694.18` (`-0.019988`)
- target trades: `34` across `3` windows
- max single positive share: `0.44321`
- positive PnL HHI: `0.313271`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "failed_reasons": [
    "aggregate_ev_not_positive",
    "aggregate_pnl_not_positive",
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0201,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.44321,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.313271,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 34,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
