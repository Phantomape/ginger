# exp-20260602-018 Sector-Relative Risk-Adjusted Momentum

Decision: `rejected_sector_relative_risk_adjusted_momentum_candidate_pool`.

Single variable: a default-off paper source admits stock-only sector-residual momentum candidates with a volatility guardrail, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.0560 | -0.1068 | $117,072.92 | $115,172.15 | $-1,900.77 | -0.0022 | 75 | 171 |
| mid_weak | 2.1402 | 2.7025 | +0.5623 | $78,110.11 | $88,030.78 | $+9,920.67 | -0.0042 | 98 | 235 |
| old_thin | 0.5911 | 0.4346 | -0.1565 | $39,667.96 | $32,427.21 | $-7,240.75 | +0.1024 | 99 | 227 |

## Aggregate

- EV delta: `0.299` (`0.037876`)
- PnL delta: `$779.15` (`0.003318`)
- target trades: `272` across `3` windows
- max single positive share: `0.391537`
- positive PnL HHI: `0.217401`

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
  "max_drawdown_worse": 0.1024,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.391537,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.217401,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 272,
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
