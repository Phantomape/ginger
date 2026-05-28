# exp-20260528-037 Ticker Accumulation-Quality Breakout

Decision: `rejected_ticker_accumulation_quality_breakout`.

Single variable: a default-off paper source admits stock-only OBV-new-high plus price-breakout candidates, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.2228 | -0.9400 | $117,072.92 | $107,452.44 | $-9,620.48 | +0.0099 | 66 | 152 |
| mid_weak | 2.1402 | 2.4762 | +0.3360 | $78,110.11 | $85,680.51 | $+7,570.40 | -0.0026 | 80 | 241 |
| old_thin | 0.5911 | 0.5325 | -0.0586 | $39,667.96 | $37,240.61 | $-2,427.35 | +0.0426 | 72 | 187 |

## Aggregate

- EV delta: `-0.6626` (`-0.083936`)
- PnL delta: `$-4477.43` (`-0.019065`)
- target trades: `218` across `3` windows
- max single positive share: `0.270137`
- positive PnL HHI: `0.156569`

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
  "max_drawdown_worse": 0.0426,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.270137,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.156569,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 218,
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
