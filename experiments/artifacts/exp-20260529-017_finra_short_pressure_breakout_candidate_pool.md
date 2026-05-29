# exp-20260529-017 FINRA Short-Pressure Breakout Candidate Pool

Decision: `rejected_finra_short_pressure_breakout`.

Single variable: a default-off paper candidate source using latest published FINRA short-interest pressure plus OHLCV breakout confirmation, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3520 | +0.1892 | $117,072.92 | $120,000.12 | $+2,927.20 | +0.0008 | 22 | 26 |
| mid_weak | 2.1402 | 2.0754 | -0.0648 | $78,110.11 | $77,440.68 | $-669.43 | +0.0010 | 27 | 41 |
| old_thin | 0.5911 | 0.7792 | +0.1881 | $39,667.96 | $45,044.82 | $+5,376.86 | -0.0001 | 38 | 53 |

## Aggregate

- EV delta: `0.3125` (`0.039587`)
- PnL delta: `$7634.63` (`0.032508`)
- target trades: `87` across `3` windows
- max single positive share: `0.370854`
- positive PnL HHI: `0.215594`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression"
  ],
  "max_drawdown_worse": 0.001,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.370854,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.215594,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 87,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_improved": 2,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
