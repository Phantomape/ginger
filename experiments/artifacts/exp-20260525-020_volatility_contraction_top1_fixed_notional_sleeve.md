# exp-20260525-020 Volatility-Contraction Top-1 Fixed-Notional Sleeve

Decision: `rejected_volatility_contraction_top1_fixed_notional_sleeve`.

Single variable: a default-off paper sleeve admits at most one volatility-contraction breakout candidate per day, enters at next open, and exits after ten trading days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.6783 | -0.4845 | $117,072.92 | $112,464.49 | $-4,608.43 | +0.0078 | 13 | 22 |
| mid_weak | 2.1402 | 3.2202 | +1.0800 | $78,110.11 | $94,989.04 | $+16,878.93 | -0.0097 | 58 | 215 |
| old_thin | 0.5911 | 0.8188 | +0.2277 | $39,667.96 | $47,057.79 | $+7,389.83 | -0.0049 | 22 | 46 |

## Aggregate

- EV delta: `0.8232` (`0.10428`)
- PnL delta: `$19660.33` (`0.083714`)
- target trades: `93` across `3` windows
- max single positive share: `0.178493`
- positive PnL HHI: `0.106386`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0078,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.178493,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.106386,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 93,
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
