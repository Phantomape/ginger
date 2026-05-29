# exp-20260529-013 Residual-Leadership Pullback Candidate Pool

Decision: `rejected_residual_leadership_pullback_pool`.

Single variable: a default-off paper source admits stock-only residual-leadership pullback candidates, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.3655 | -0.7973 | $117,072.92 | $107,785.76 | $-9,287.16 | +0.0024 | 34 | 118 |
| mid_weak | 2.1402 | 3.3236 | +1.1834 | $78,110.11 | $98,041.73 | $+19,931.62 | -0.0128 | 86 | 458 |
| old_thin | 0.5911 | 0.7585 | +0.1674 | $39,667.96 | $44,623.36 | $+4,955.40 | +0.0574 | 63 | 321 |

## Aggregate

- EV delta: `0.5535` (`0.070116`)
- PnL delta: `$15599.86` (`0.066425`)
- target trades: `183` across `3` windows
- max single positive share: `0.385814`
- positive PnL HHI: `0.214179`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.0574,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.385814,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.214179,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 183,
  "target_trade_count_min": 30,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
