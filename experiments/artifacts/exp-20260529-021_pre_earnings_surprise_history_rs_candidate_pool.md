# exp-20260529-021 Pre-Earnings Surprise-History RS Candidate Pool

Decision: `rejected_pre_earnings_surprise_history_rs_pool`.

Single variable: a default-off paper source admits stock-only pre-earnings surprise-history + RS candidates, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.7963 | -0.3665 | $117,072.92 | $110,766.05 | $-6,306.87 | +0.0108 | 55 | 124 |
| mid_weak | 2.1402 | 6.0175 | +3.8773 | $78,110.11 | $133,129.86 | $+55,019.75 | -0.0196 | 87 | 179 |
| old_thin | 0.5911 | 2.3694 | +1.7783 | $39,667.96 | $85,230.57 | $+45,562.61 | +0.0318 | 67 | 181 |

## Aggregate

- EV delta: `5.2891` (`0.670007`)
- PnL delta: `$94275.49` (`0.401427`)
- target trades: `209` across `3` windows
- max single positive share: `0.389084`
- positive PnL HHI: `0.202941`

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
  "max_drawdown_worse": 0.0318,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.389084,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.202941,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 209,
  "target_trade_count_min": 20,
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
