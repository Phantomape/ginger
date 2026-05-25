# exp-20260525-011 Opening-Range Top-1 Fixed-Notional Sleeve

Decision: `rejected_opening_range_top1_fixed_notional_sleeve`.

Single variable: a default-off paper sleeve admits at most one opening-range continuation candidate per day, enters at next open, and exits after ten trading days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.2860 | -0.8768 | $117,072.92 | $106,090.13 | $-10,982.79 | +0.0094 | 59 | 209 |
| mid_weak | 2.1402 | 3.5312 | +1.3910 | $78,110.11 | $99,472.82 | $+21,362.71 | -0.0135 | 76 | 212 |
| old_thin | 0.5911 | 0.7478 | +0.1567 | $39,667.96 | $43,993.22 | $+4,325.26 | +0.0595 | 72 | 207 |

## Aggregate

- EV delta: `0.6709` (`0.084988`)
- PnL delta: `$14705.18` (`0.062615`)
- target trades: `207` across `3` windows
- max single positive share: `0.150045`
- positive PnL HHI: `0.089339`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0595,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.150045,
    "max_single_positive_pnl_share_guardrail": 0.35,
    "passed": true,
    "positive_pnl_hhi": 0.089339,
    "positive_pnl_hhi_guardrail": 0.25
  },
  "target_trade_count": 207,
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
