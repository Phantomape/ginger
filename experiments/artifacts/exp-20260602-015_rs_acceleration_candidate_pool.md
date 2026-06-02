# exp-20260602-015 Relative-Strength Acceleration Candidate Pool

Decision: `rejected_rs_acceleration_candidate_pool`.

Single variable: a default-off paper source admits stock-only recent RS-acceleration candidates, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 3.9545 | -1.2083 | $117,072.92 | $104,335.35 | $-12,737.57 | +0.0033 | 58 | 114 |
| mid_weak | 2.1402 | 3.3164 | +1.1762 | $78,110.11 | $96,967.48 | $+18,857.37 | -0.0090 | 70 | 144 |
| old_thin | 0.5911 | 0.3672 | -0.2239 | $39,667.96 | $30,345.44 | $-9,322.52 | +0.0695 | 70 | 139 |

## Aggregate

- EV delta: `-0.256` (`-0.032429`)
- PnL delta: `$-3202.72` (`-0.013637`)
- target trades: `198` across `3` windows
- max single positive share: `0.184041`
- positive PnL HHI: `0.100168`

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
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.0695,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.184041,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.100168,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 198,
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
